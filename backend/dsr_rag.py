import os
import operator
from typing import TypedDict, Annotated, List, Dict, Any, Optional
from bson import ObjectId
import motor.motor_asyncio
import logging
import warnings
import asyncio

logging.getLogger("langchain_google_genai._function_utils").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.mongodb.aio import AsyncMongoDBSaver
from langgraph.prebuilt import ToolNode
from langchain_core.tools import tool
import numexpr

# ==========================================
# State Management (TypedDict)
# ==========================================
class GraphState(TypedDict):
    """
    Represents the state of the "Dual-State Reflexive RAG" (DSR-RAG) graph.
    Golden Rule: Long documents NEVER enter here. Only pointers (file_ids).
    """
    messages: Annotated[List[BaseMessage], operator.add]
    file_ids: List[str] 
    filenames: List[str]
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
async def save_to_gridfs(content: str, filename: str, metadata: Dict = None) -> str:
    file_id = await fs.upload_from_stream(
        filename,
        content.encode('utf-8'),
        metadata=metadata or {}
    )
    return str(file_id)

async def load_from_gridfs(file_id: str) -> str:
    grid_out = await fs.open_download_stream(ObjectId(file_id))
    content = await grid_out.read()
    return content.decode('utf-8')

# ==========================================
# Native Vector Search and Lookup (Aggregation Pipeline)
# ==========================================
async def retrieve_from_mongo(query_embedding: List[float], limit: int = 3) -> List[Dict]:
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
    retrieved_file_ids = [str(doc["gridfs_file_id"]) for doc in docs]
    filenames = [doc["filename"] for doc in docs]
    return {"file_ids": retrieved_file_ids, "filenames": filenames}

class Grade(BaseModel):
    binary_score: str = Field(description="Is the document relevant to the question? Answer 'yes' or 'no'")

async def grade_documents(state: GraphState, config: RunnableConfig) -> Dict:
    """Node: Reflexive grader. Checks if IDs point to useful contexts."""
    emit_log(config, "--- NODE: GRADE DOCUMENTS (EVALUATOR) ---")
    query = state["query"]
    file_ids = state.get("file_ids", [])
    filenames = state.get("filenames", [])
    
    structured_llm_grader = llm.with_structured_output(Grade)
    system = "You are a semantic relevance judge. Analyze the document to see if it has a positive correlation with the user's question. If it can help answer or has coherent keywords, return 'yes'. Otherwise, 'no'."
    
    prompt = PromptTemplate(
        template="System: {system}\n\nQuestion: {question}\n\nRetrieved Document: {document}\n",
        input_variables=["system", "question", "document"],
    )
    grader_chain = prompt | structured_llm_grader
    relevant_ids = []
    relevant_filenames = []
    
    for i, file_id in enumerate(file_ids):
        doc_content = await load_from_gridfs(file_id)
        try:
            score: Grade = await grader_chain.ainvoke({"question": query, "document": doc_content, "system": system})
            
            if score and score.binary_score.lower() == "yes":
                emit_log(config, f"  [+] Document ({file_id}) RELEVANT")
                relevant_ids.append(file_id)
                if i < len(filenames):
                    relevant_filenames.append(filenames[i])
            else:
                emit_log(config, f"  [-] Document ({file_id}) IRRELEVANT (score: {score})")
        except Exception as e:
            emit_log(config, f"  [!] Error grading document {file_id}: {str(e)}")
            # Default to irrelevant on error to be safe
            continue
            
    return {"file_ids": relevant_ids, "filenames": relevant_filenames}

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
    prompt = PromptTemplate(template="System: {system}\n\nOriginal: {question}\n\nNew Optimized Query:", input_variables=["system", "question"])
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
    for i, file_id in enumerate(file_ids):
         content = await load_from_gridfs(file_id)
         name = filenames[i] if i < len(filenames) else f"Unknown Source {i}"
         docs_contents.append(f"SOURCE: {name}\nCONTENT: {content}")
         
    context_str = "\n\n=== SOURCE CONTEXT ===\n\n".join(docs_contents)
    messages = state.get("messages", [])
    
    system = f"""You are an advanced RAG assistant (DSR-CRAG). You have access to tools and retrieved context.
You are also a data visualization expert. You MUST generate charts (pie, bar, xychart-beta) or diagrams (flowchart) in Mermaid format whenever the answer involves quantitative data, statistics, or processes.

### 📚 GROUNDING RULES:
1. Use the provided context to answer. 
2. **CITE YOUR SOURCES**: Use square brackets with the filename, e.g., [filename.pdf], to attribute information.
3. If multiple sources support a point, cite both: [file1.pdf][file2.pdf].
4. Only cite sources provided in the "SOURCE CONTEXT" section below.

### � DATA VISUALIZATION RULES:
1. **PREFER MARKDOWN TABLES** for any data involving trends, bar charts, or complex lists.
2. **SIMPLE CHARTS** (Last resort):
   - **PIE**: Only for simple shares. Use double quotes for title and labels. Values MUST be integers.
     ```mermaid
     pie title "Title"
         "A" : 10
         "B" : 20
     ```
   - **FLOWCHART**: Use `graph TD`. Quote ALL labels: `ID["Label Text"]`.
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
        # Emit final sources list before streaming tokens
        try:
            queue.put_nowait({"type": "sources", "sources": filenames})
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

tools = [calculator, summarize_document, query_database_stats]
llm_with_tools = llm.bind_tools(tools)
tool_node = ToolNode(tools)

def check_tools(state: GraphState, config: RunnableConfig) -> str:
    messages = state.get("messages", [])
    if messages and hasattr(messages[-1], "tool_calls") and messages[-1].tool_calls:
        emit_log(config, "  -> Tool call requested by LLM.")
        return "tools"
    return END

# ==========================================
# Graph Construction and Compilation
# ==========================================
def build_dsr_rag_graph():
    workflow = StateGraph(GraphState)

    workflow.add_node("retrieve_documents", retrieve_documents)
    workflow.add_node("grade_documents", grade_documents)
    workflow.add_node("rewrite_query", rewrite_query)
    workflow.add_node("generate_answer", generate_answer)
    workflow.add_node("tools", tool_node)

    workflow.add_edge(START, "retrieve_documents")
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
