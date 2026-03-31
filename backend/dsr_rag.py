import os
import operator
from typing import TypedDict, Annotated, List, Dict, Any, Optional
from bson import ObjectId
import motor.motor_asyncio
import logging
import warnings
import asyncio
import json

logging.getLogger("langchain_google_genai._function_utils").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from langgraph.graph import StateGraph, START, END

from langgraph.prebuilt import ToolNode
from langchain_core.tools import tool
import numexpr
import pandas as pd
import io

# ==========================================
# State Management (TypedDict)
# ==========================================
class GraphState(TypedDict):
    """
    Represents the state of the "Dual-State Reflexive RAG" (DSR-RAG) graph.
    Golden Rule: Long source files NEVER enter here. 
    Retrieved chunks (metadata + text) are allowed for efficient processing.

    Attributes:
        messages (List[BaseMessage]): A list of messages forming the conversation history.
        file_ids (List[str]): A list of GridFS file IDs of retrieved documents.
        filenames (List[str]): A list of filenames corresponding to the retrieved documents.
        documents (List[Dict[str, Any]]): A list of retrieved document chunks, including their text content.
        query (str): The current user query.
        generation (Optional[str]): The generated answer from the LLM.
        rewrite_count (int): The number of times the query has been rewritten.
    """
    messages: Annotated[List[BaseMessage], operator.add]
    file_ids: List[str] 
    filenames: List[str]
    documents: List[Dict[str, Any]] # NEW: List of retrieved chunks with text
    query: str
    generation: Optional[str]
    rewrite_count: int

def emit_log(config: RunnableConfig, message: str):
    """Helper to emit logs to the SSE queue if available."""
    queue = config.get("configurable", {}).get("queue")
    if queue:
        try:
            queue.put_nowait({"type": "log", "message": message})
        except asyncio.QueueFull:
            pass
    print(message)

# ==========================================
# MongoDB and GridFS Configuration
# ==========================================
MONGO_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = client.dsr_rag_db
vector_collection = db.vectors
fs = motor.motor_asyncio.AsyncIOMotorGridFSBucket(db)

# ==========================================
# Artifact Offloading to GridFS
# ==========================================
async def save_to_gridfs(content: Any, filename: str, metadata: Dict = None) -> str:
    """
    Saves content to MongoDB GridFS.

    Args:
        content (Any): The content to save. Can be bytes or a string.
        filename (str): The name of the file.
        metadata (Dict, optional): Additional metadata to store with the file. Defaults to None.

    Returns:
        str: The string representation of the ObjectId of the saved file.
    """
    if isinstance(content, str):
        content = content.encode('utf-8')
    file_id = await fs.upload_from_stream(
        filename,
        content,
        metadata=metadata or {}
    )
    return str(file_id)

async def load_from_gridfs(file_id: str) -> str:
    """
    Loads content from MongoDB GridFS and decodes it as UTF-8.

    Args:
        file_id (str): The string representation of the ObjectId of the file to load.

    Returns:
        str: The decoded content of the file.
    """
    grid_out = await fs.open_download_stream(ObjectId(file_id))
    content = await grid_out.read()
    return content.decode('utf-8')

async def load_binary_from_gridfs(file_id: ObjectId) -> bytes:
    """
    Loads binary content from MongoDB GridFS.

    Args:
        file_id (ObjectId): The ObjectId of the file to load.

    Returns:
        bytes: The binary content of the file.
    """
    grid_out = await fs.open_download_stream(file_id)
    return await grid_out.read()

# ==========================================
# Native Vector Search and Lookup (Aggregation Pipeline)
# ==========================================
async def retrieve_from_mongo(query_embedding: List[float], limit: int = 3) -> List[Dict]:
    """
    Performs a vector search on the MongoDB 'vectors' collection and
    joins the results with GridFS metadata.

    Args:
        query_embedding (List[float]): The embedding of the query.
        limit (int, optional): The maximum number of results to return. Defaults to 3.

    Returns:
        List[Dict]: A list of dictionaries, each representing a retrieved document chunk
                    with its text, filename, and other metadata.
    """
    pipeline = [
        {
            "$vectorSearch": {
                "index": "vector_index",
                "path": "embedding",
                "queryVector": query_embedding,
                "numCandidates": limit * 10,
                "limit": limit
            }
        },
        {
            "$lookup": {
                "from": "fs.files",
                "localField": "gridfs_file_id",
                "foreignField": "_id",
                "as": "file_metadata"
            }
        },
        {
            "$unwind": "$file_metadata"
        },
        {
            "$project": {
                "_id": 0,
                "score": {"$meta": "vectorSearchScore"},
                "gridfs_file_id": 1,
                "text": 1,                # PROJECT TEXT
                "filename": "$file_metadata.filename",
                "metadata": "$file_metadata.metadata"
            }
        }
    ]
    cursor = vector_collection.aggregate(pipeline)
    return await cursor.to_list(length=limit)

# ==========================================
# Global LLM and Embeddings Initialization
# ==========================================
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")

# ==========================================
# Graph Nodes Definition (Asynchronous)
# ==========================================
async def retrieve_documents(state: GraphState, config: RunnableConfig) -> Dict:
    """Node: Vector search. Strictly populates state with pointers (IDs)."""
    emit_log(config, "--- NODE: RETRIEVE DOCUMENTS ---")
    query = state["query"]
    query_embedding = await embeddings.aembed_query(query)
    docs = await retrieve_from_mongo(query_embedding, limit=10)
    
    # Stringify ObjectId for msgpack serialization compatibility
    for doc in docs:
        if "gridfs_file_id" in doc:
            doc["gridfs_file_id"] = str(doc["gridfs_file_id"])
            
    retrieved_file_ids = [doc["gridfs_file_id"] for doc in docs]
    filenames = [doc["filename"] for doc in docs]
    return {
        "file_ids": retrieved_file_ids, 
        "filenames": filenames,
        "documents": docs
    }

class Grade(BaseModel):
    binary_scores: List[str] = Field(description="A list of 'yes' or 'no' indicating the relevance of each document to the question.")

GRADE_DOCUMENTS_SYSTEM_PROMPT = """You are a semantic relevance judge. You will be provided with a user's question and a list of retrieved documents. For each document, determine if it is relevant to the question. Respond with a JSON object containing a list of 'yes' or 'no' scores, corresponding to each document in the order they were provided. If a document can help answer or has coherent keywords, return 'yes'. Otherwise, 'no'.

Example Output: {"binary_scores": ["yes", "no", "yes"]}"""

async def grade_documents(state: GraphState, config: RunnableConfig) -> Dict:
    """Node: Reflexive grader. Checks if IDs point to useful contexts."""
    emit_log(config, "--- NODE: GRADE DOCUMENTS (EVALUATOR) ---")
    query = state["query"]
    documents = state.get("documents", [])
    
    if not documents:
        emit_log(config, "  -> No documents to grade.")
        return {"file_ids": [], "filenames": [], "documents": []}

    structured_llm_grader = llm.with_structured_output(Grade)
    
    # Combine all document contents into a single string for batch grading
    combined_documents_str = ""
    for i, doc in enumerate(documents):
        doc_content = doc.get("text", "")
        filename = doc.get("filename", "Unknown")
        combined_documents_str += f"== DOCUMENT {i+1} (Source: {filename}) ==\n{doc_content}\n\n"

    
    prompt = PromptTemplate(
        template="System: {system}\n\nQuestion: {question}\n\nRetrieved Documents:\n{combined_documents}\n\nGrades (JSON):",
        input_variables=["system", "question", "combined_documents"],
    )
    grader_chain = prompt | structured_llm_grader
    
    relevant_ids = []
    relevant_filenames = []
    relevant_docs = []
    
    try:
        score: Grade = await grader_chain.ainvoke({
            "question": query, 
            "combined_documents": combined_documents_str,
            "system": GRADE_DOCUMENTS_SYSTEM_PROMPT
        })
        
        if score and score.binary_scores:
            for i, binary_score in enumerate(score.binary_scores):
                if i < len(documents):
                    doc = documents[i]
                    file_id = str(doc.get("gridfs_file_id", ""))
                    filename = doc.get("filename", "Unknown")
                    
                    if binary_score.lower() == "yes":
                        emit_log(config, f"  [+] Document {i+1} ({filename}) RELEVANT")
                        relevant_ids.append(file_id)
                        relevant_filenames.append(filename)
                        relevant_docs.append(doc)
                    else:
                        emit_log(config, f"  [-] Document {i+1} ({filename}) IRRELEVANT")
                else:
                    emit_log(config, f"  [!] Grader returned more scores than documents. Ignoring extra score {i+1}.")
        else:
            emit_log(config, "  [!] Grader returned no scores or invalid format. Assuming all irrelevant.")
            
    except Exception as e:
        emit_log(config, f"  [!] Error grading documents: {str(e)}. Assuming all irrelevant.")
        
    return {
        "file_ids": relevant_ids, 
        "filenames": relevant_filenames,
        "documents": relevant_docs
    }

def check_relevance(state: GraphState, config: RunnableConfig) -> str:
    """Conditional Edge: Routing based on the existence of relevant pointers."""
    emit_log(config, "--- ROUTING: CHECK RELEVANCE ---")
    file_ids = state.get("file_ids", [])
    rewrite_count = state.get("rewrite_count", 0)
    
    if len(file_ids) == 0:
        if rewrite_count >= 3:
            emit_log(config, "  -> Rewrite limit reached. Forcing fallback answer.")
            return "generate_answer"
        emit_log(config, "  -> No useful sources. Redirecting to REWRITE_QUERY.")
        return "rewrite_query"
    
    emit_log(config, "  -> Useful sources detected. Redirecting to GENERATE_ANSWER.")
    return "generate_answer"

async def rewrite_query(state: GraphState, config: RunnableConfig) -> Dict:
    """Node: Self-Correction Loop. Rewrites the query."""
    emit_log(config, "--- NODE: REWRITE QUERY ---")
    query = state["query"]
    
    system = "You are a semantic intent translator. The user's question did not get good results in the vector search. Rewrite it focusing on extracting the underlying concept, to get better hits in the database. Keep the query succinct."
    prompt = PromptTemplate(template="System: {system}\n\nOriginal: {question}\n\nNew Optimized Query:", input_variables=["system", "question"]))
    rewriter_chain = prompt | llm | StrOutputParser()
    new_query = await rewriter_chain.ainvoke({"question": query, "system": system})
    
    emit_log(config, f"  -> Original: '{query}'\n  -> New: '{new_query}'")
    current_count = state.get("rewrite_count", 0)
    return {"query": new_query, "rewrite_count": current_count + 1}

async def generate_answer(state: GraphState, config: RunnableConfig) -> Dict:
    """Node: Final Answer based on the buffers obtained from GridFS."""
    emit_log(config, "--- NODE: GENERATE ANSWER ---")
    query = state["query"]
    file_ids = state.get("file_ids", [])
    filenames = state.get("filenames", [])
    
    docs_contents = []
    sources_data = []
    seen_filenames = set()
    
    # Use documents from state (contains text) instead of loading from GridFS
    retrieved_docs = state.get("documents", [])

    for doc in retrieved_docs:
         content = doc.get("text", "")
         name = doc.get("filename", "Unknown Source")
         docs_contents.append(f"SOURCE: {name}\nCONTENT: {content}")
         
         if name not in seen_filenames:
             sources_data.append({"filename": name, "content": content})
             seen_filenames.add(name)
             
    context_str = "\n\n=== SOURCE CONTEXT ===\n\n".join(docs_contents)
    messages = state.get("messages", [])
    
    system = f"""You are an advanced RAG assistant (DSR-CRAG). You have access to tools and retrieved context.\
You are also a data visualization expert. You MUST generate charts (pie, bar, xychart-beta) or diagrams (flowchart) in Mermaid format whenever the answer involves quantitative data, statistics, or processes.\

### 📚 GROUNDING RULES:
1. Use the provided context to answer. 
2. **CONSOLIDATED ATTRIBUTION**:
    - **NEVER** cite every single line in a list if they come from the same source.
    - **CITE ONCE** per paragraph or distinct section.
    - **PROHIBITED STYLE**: \"Fact 1 [file.pdf]\nFact 2 [file.pdf]\" -> **INCORRECT**.
    - **REQUIRED STYLE**: \"Here is the list [file.pdf]:\n- Fact 1\n- Fact 2\" OR \"Fact 1 and Fact 2. [file.pdf]\" -> **CORRECT**.
3. **CITATIONS**: Use square brackets, e.g., [filename.pdf].
4. Only cite sources provided in the \"SOURCE CONTEXT\" section below.
5. If no relevant sources exist, do not cite and inform the user you don't have that information.

### 📊 DATA VISUALIZATION RULES:
1. **PREFER MARKDOWN TABLES** for any data involving trends, bar charts, or complex lists.
2. **QUANTITATIVE DATA**: If the user asks for counts, sums, averages, or analysis from an uploaded CSV/XLSX file, **YOU MUST** use the `query_structured_data` tool instead of relying on vector search chunks. Vector search only gives you fragments, while the tool gives you the whole picture.
3. **SIMPLE CHARTS** (Last resort):
   - **PIE**: Only for simple shares. Use double quotes for title and labels. Values MUST be integers.
     ```mermaid
     pie title \"Title\"
         \"A\" : 10
         \"B\" : 20
     ```
   - **FLOWCHART**: Use `graph TD`. Quote ALL labels: `ID[\"Label Text\"]`.
3. **CRITICAL**: No curly braces `{{ }}` or extra keywords in charts.

Provided Context:
{context_str}

Answer with excellence. If the context is insufficient, use tools or inform the user."""
    
    prompt_messages = [SystemMessage(content=system)] + messages
    human_msg = None
    
    if messages and hasattr(messages[-1], "type") and messages[-1].type == "tool":
        pass
    else:
        human_msg = HumanMessage(content=query)
        prompt_messages.append(human_msg)
        
    queue = config.get("configurable", {}).get("queue")
    
    if queue:
        # Emit final sources list (enriched with content) before streaming tokens
        try:
            queue.put_nowait({"type": "sources", "sources": sources_data})
        except:
            pass

        # Stream token by token
        response_content = ""
        tool_calls = []
        async for chunk in llm_with_tools.astream(prompt_messages):
            if chunk.content:
                response_content += chunk.content
                try:
                    queue.put_nowait({"type": "token", "content": chunk.content})
                except asyncio.QueueFull:
                    pass
            if chunk.tool_call_chunks:
                for chunk_tc in chunk.tool_call_chunks:
                    try:
                        queue.put_nowait({"type": "log", "message": f"Calling tool {chunk_tc['name']}..."})
                    except:
                        pass
        
        # We must re-invoke non-streaming to correctly capture the tool call object for langgraph state
        response = await llm_with_tools.ainvoke(prompt_messages)
    else:
        response = await llm_with_tools.ainvoke(prompt_messages)
    
    if human_msg:
        delta_messages = [human_msg, response]
    else:
        delta_messages = [response]
        
    generation_result = response.content if not response.tool_calls else None
    
    return {"messages": delta_messages, "generation": generation_result}

# ==========================================
# Tools Configuration
# ==========================================
@tool
def calculator(expression: str) -> str:
    """Useful for when you need to perform mathematical calculations. Pass the expression string (e.g.: '1500 * 2')."""
    try:
        return str(numexpr.evaluate(expression))
    except Exception as e:
        return f"Calculation error: {e}"

@tool
async def summarize_document(file_id: str) -> str:
    """Full summary of a specific document. Requires the exact 'gridfs_file_id' returned in the context."""
    try:
        content = await load_from_gridfs(file_id)
        prompt = PromptTemplate.from_template("Summarize this document in its entirety:\n{text}")
        chain = prompt | llm | StrOutputParser()
        return await chain.ainvoke({"text": content[:50000]})
    except Exception as e:
        return f"Error summarizing document: {e}"

@tool
async def query_database_stats() -> str:
    """Returns the total number of documents and chunks currently indexed in the database. Use this when asked 'how many documents do we have?'."""
    try:
        vector_count = await vector_collection.count_documents({})
        pipeline = [{"$group": {"_id": "$metadata.filename"}}, {"$count": "total"}]
        cursor = db["fs.files"].aggregate(pipeline)
        result = await cursor.to_list(1)
        pdf_count = result[0]["total"] if result else 0
        return f"We have {pdf_count} unique PDF files indexed, divided into {vector_count} vector search chunks."
    except Exception as e:
        return f"Error accessing database: {e}"

@tool
async def query_structured_data(query: str, filename: str) -> str:
    """Useful for quantitative analysis on CSV/XLSX files (counting, aggregate, filter). 
    Pass the natural language query and the filename (e.g., 'How many companies from Europe?', 'data.csv')."""
    try:
        # 1. Find the structured file in GridFS
        cursor = db["fs.files"].find({"filename": filename, "metadata.type": "structured"})
        files = await cursor.to_list(length=1)
        if not files:
             # Fallback: try finding ANY file with that name if 'structured' isn't set (for older uploads)
             cursor = db["fs.files"].find({"filename": filename})
             files = await cursor.to_list(length=1)
             if not files:
                 return f"File '{filename}' not found or not indexed as structured data."
        
        file_id = files[0]["_id"]
        content = await load_binary_from_gridfs(file_id)
        
        # 2. Load into Pandas
        try:
            if filename.endswith('.csv'):
                # Try to sniff delimiter and handle BOM
                stream = io.BytesIO(content)
                # Decode to string context for sniffing if needed, or just use pandas defaults
                df = pd.read_csv(stream, sep=None, engine='python', on_bad_lines='skip')
            else:
                df = pd.read_excel(io.BytesIO(content))
        except Exception as parse_err:
             # Fallback to UTF-8-sig (BOM handling) if direct binary read fails
             if filename.endswith('.csv'):
                 df = pd.read_csv(io.StringIO(content.decode('utf-8-sig', errors='ignore')), sep=None, engine='python')
             else:
                 raise parse_err
        
        # CLEANUP: Strip whitespace and LOWERCASE column names to avoid KeyErrors
        df.columns = [c.strip().lower() for c in df.columns]
            
        # 3. Use LLM to generate analysis code
        columns = list(df.columns)
        sample = df.head(5).to_string()
        
        analyze_prompt = f"""You are a Python data analyst. Given a DataFrame 'df' with columns {columns}.
Sample data:
{sample}

TASK: Write a SHORT, EFFICIENT, and CORRECT Python snippet to answer this question: "{query}"
The snippet MUST:
1. Use the variable 'df'.
2. Use LOWERCASE column names from the provided list.
3. Calculate the answer.
4. Assign the FINAL scalar result (string, number, or markdown table) to a variable named 'result'.
5. Do NOT use print(). 
6. Avoid complex operations unless absolutely necessary. Prioritize simple aggregations and filters.
7. Ensure the code is syntactically correct and will execute without errors.

Code:"""
        
        response = await llm.ainvoke(analyze_prompt)
        code = response.content.replace('```python', '').replace('```', '').strip()
        
        # 4. Execute (sandbox-lite)
        local_vars = {"df": df, "pd": pd}
        try:
            exec(code, {}, local_vars)
            raw_result = local_vars.get("result", "No result returned from code execution.")
            
            # FORMATTING: If result is a DataFrame or Series, convert to Markdown table
            try:
                if isinstance(raw_result, pd.DataFrame):
                    result = raw_result.to_markdown()
                elif isinstance(raw_result, pd.Series):
                    result = raw_result.to_frame().to_markdown()
                else:
                    result = str(raw_result)
            except ImportError:
                # Fallback if 'tabulate' is not installed yet
                result = str(raw_result)
                
        except Exception as exec_err:
            result = f"Code execution error: {exec_err}\n\nGenerated Code:\n{code}\nAvailable Columns: {columns}"
        
        return f"Analysis Result for '{query}' on {filename}:\n\n{result}"
        
    except Exception as e:
        return f"Error analyzing structured data: {str(e)}"

tools = [calculator, summarize_document, query_database_stats, query_structured_data]
llm_with_tools = llm.bind_tools(tools)
tool_node = ToolNode(tools)

def check_tools(state: GraphState, config: RunnableConfig) -> str:
    """
    Conditional Edge: Checks if the last message from the LLM contains tool calls.
    If tool calls are present, the graph transitions to the 'tools' node; otherwise, it ends.
    """
    messages = state.get("messages", [])
    if messages and hasattr(messages[-1], "tool_calls") and messages[-1].tool_calls:
        emit_log(config, "  -> Tool call requested by LLM.")
        return "tools"
    return END

# ==========================================
# Graph Construction and Compilation
# ==========================================
def build_dsr_rag_graph():
    """
    Constructs and compiles the Dual-State Reflexive RAG (DSR-RAG) LangGraph workflow.

    The graph defines the following nodes and edges:
    - Nodes:
        - `retrieve_documents`: Performs vector search to retrieve relevant document chunks.
        - `grade_documents`: Evaluates the relevance of retrieved documents.
        - `rewrite_query`: Rewrites the user query if no relevant documents are found.
        - `generate_answer`: Generates the final answer using retrieved context and tools.
        - `tools`: Executes any tool calls requested by the LLM.

    - Edges:
        - `START` -> `route_query` (conditional): Routes the initial query to either `retrieve_documents` or `generate_answer`.
        - `retrieve_documents` -> `grade_documents`: After retrieving documents, they are graded for relevance.
        - `grade_documents` -> `check_relevance` (conditional): Based on document relevance, either rewrites the query or generates an answer.
        - `rewrite_query` -> `retrieve_documents`: If the query is rewritten, new documents are retrieved.
        - `generate_answer` -> `check_tools` (conditional): After generating an answer, checks for tool calls.
        - `tools` -> `generate_answer`: After tool execution, the answer generation process is re-entered.
        - `check_tools` -> `END`: If no tool calls are present, the graph ends.

    Returns:
        StateGraph: The compiled LangGraph workflow.
    """
    workflow = StateGraph(GraphState)

    workflow.add_node("retrieve_documents", retrieve_documents)
    workflow.add_node("grade_documents", grade_documents)
    workflow.add_node("rewrite_query", rewrite_query)
    workflow.add_node("generate_answer", generate_answer)
    workflow.add_node("tools", tool_node)

    # Initial routing
    workflow.add_conditional_edges(
        START,
        route_query,
        {
            "vectorstore": "retrieve_documents",
            "generate": "generate_answer"
        }
    )

    workflow.add_edge("retrieve_documents", "grade_documents")

    workflow.add_conditional_edges(
        "grade_documents",
        check_relevance,
        {"generate_answer": "generate_answer", "rewrite_query": "rewrite_query"}
    )

    workflow.add_edge("rewrite_query", "retrieve_documents") 
    workflow.add_conditional_edges("generate_answer", check_tools, {"tools": "tools", END: END})
    workflow.add_edge("tools", "generate_answer")
    
    return workflow