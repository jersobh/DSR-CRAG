import os
import io
import asyncio
import json
import lmdb
from langgraph_checkpoint_lmdb import AsyncLMDBSaver

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pymupdf
from bson import ObjectId
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage


env = lmdb.open("./checkpoints", max_dbs=10)


from dsr_rag import (
    save_to_gridfs,
    vector_collection,
    embeddings,
    build_dsr_rag_graph,
    client
)


app = FastAPI(title="DSR-RAG API")

# Setup CORS for the React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200
)

# Initialize checkpointer and compile agent graph once
saver = AsyncLMDBSaver(env)

workflow = build_dsr_rag_graph()
agent_app = workflow.compile(checkpointer=saver)

import pandas as pd

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    filename = file.filename.lower()
    content = await file.read()
    full_text = ""
    
    try:
        if filename.endswith('.pdf'):
            # Extract text from PDF
            doc = pymupdf.open(stream=content, filetype="pdf")
            for page in doc:
                full_text += page.get_text() + "\n"
            doc.close()
            
        elif filename.endswith('.csv'):
            # Extract text from CSV
            df = pd.read_csv(io.BytesIO(content))
            full_text = df.to_string(index=False)
            
        elif filename.endswith('.xlsx') or filename.endswith('.xls'):
            # Extract text from Excel
            df = pd.read_excel(io.BytesIO(content))
            full_text = df.to_string(index=False)
            
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type. Use PDF, CSV, or XLSX.")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse file: {str(e)}")
        
    if not full_text.strip():
        raise HTTPException(status_code=400, detail="File has no extractable text")
        
    chunks = text_splitter.split_text(full_text)
    metadata = {"filename": file.filename, "source": "user_upload"}
    
    # Process chunks into MongoDB Atlas
    for i, chunk in enumerate(chunks):
        embedding = await embeddings.aembed_query(chunk)
        gridfs_file_id_str = await save_to_gridfs(chunk, file.filename, metadata)
        
        vector_doc = {
            "embedding": embedding,
            "gridfs_file_id": ObjectId(gridfs_file_id_str),
            "chunk_index": i,
            "filename": file.filename
        }
        await vector_collection.insert_one(vector_doc)
        
    return {"message": f"Document '{file.filename}' processed successfully", "chunks": len(chunks)}


@app.get("/sessions")
async def list_sessions():
    """Returns unique thread IDs from LMDB checkpointer"""
    try:
        sessions = {}
        async for checkpoint in agent_app.checkpointer.alist(None):
            thread_id = checkpoint.config["configurable"].get("thread_id")
            if not thread_id:
                continue
                
            metadata = checkpoint.metadata or {}
            # Check multiple common timestamp fields
            timestamp = metadata.get("at") or metadata.get("ts") or metadata.get("created_at") or metadata.get("at")
            
            if thread_id not in sessions:
                # Use thread_id as a fallback if no preview available
                preview = metadata.get("source", "conversation")
                sessions[thread_id] = {
                    "thread_id": thread_id,
                    "updated_at": timestamp,
                    "preview": preview
                }
        
        result = list(sessions.values())
        # Filter out sessions with no timestamp if possible, or just sort them last
        result.sort(key=lambda x: str(x["updated_at"]) if x["updated_at"] else "", reverse=True)
        return {"sessions": result}
    except Exception as e:
        print(f"[!] Error listing sessions: {e}")
        return {"sessions": []}


@app.get("/sessions/{thread_id}/history")
async def get_session_history(thread_id: str):
    """Returns the message history for a specific thread"""
    try:
        config = {"configurable": {"thread_id": thread_id}}
        state = await agent_app.aget_state(config)
        
        if not state or not state.values or "messages" not in state.values:
            return {"messages": []}
            
        messages = state.values["messages"]
        serialized_messages = []
        
        for msg in messages:
            if isinstance(msg, HumanMessage):
                role = "user"
            elif isinstance(msg, AIMessage):
                role = "assistant"
            elif isinstance(msg, SystemMessage):
                role = "system"
            else:
                role = "assistant" # Default
                
            serialized_messages.append({
                "role": role,
                "content": msg.content,
                "sources": msg.additional_kwargs.get("sources", [])
            })
            
        return {"messages": serialized_messages}
    except Exception as e:
        print(f"[!] Error fetching history for {thread_id}: {e}")
        return {"messages": []}


@app.delete("/sessions/{thread_id}")
async def delete_session(thread_id: str):
    """Deletes all checkpoints and writes for a specific thread_id"""
    try:
        saver = agent_app.checkpointer._saver
        env = saver.env
        prefix = f"{thread_id}\x00".encode()
        
        with saver.lock:
            with env.begin(write=True) as txn:
                # 1. Delete checkpoints
                cursor = txn.cursor(db=saver._db)
                if cursor.set_range(prefix):
                    for k, _ in cursor:
                        if not k.startswith(prefix):
                            break
                        txn.delete(k, db=saver._db)
                
                # 2. Delete writes
                w_cursor = txn.cursor(db=saver._writes_db)
                if w_cursor.set_range(prefix):
                    for k, _ in w_cursor:
                        if not k.startswith(prefix):
                            break
                        txn.delete(k, db=saver._writes_db)
                        
        return {"message": f"Session {thread_id} deleted"}
    except Exception as e:
        print(f"[!] Error deleting thread {thread_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/sessions/clear")
async def clear_sessions():
    """Clears all conversation checkpoints from LMDB safely"""
    try:
        saver = agent_app.checkpointer._saver
        env = saver.env
        
        # Use the internal lock to prevent race conditions during drop
        with saver.lock:
            with env.begin(write=True) as txn:
                # drop(db, delete=False) empties the DB but keeps the handle valid
                txn.drop(saver._db, delete=False)
                txn.drop(saver._writes_db, delete=False)
                
        return {"message": "All session history cleared successfully"}
    except Exception as e:
        print(f"[!] Critical Error clearing LMDB: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear sessions: {str(e)}")


@app.get("/documents")
async def list_documents():
    """Returns the list of unique ingested documents (files)"""
    try:
        filenames = await vector_collection.distinct("filename")
        return {"documents": filenames}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/documents/{filename}")
async def delete_document(filename: str):
    """Deletes a document and all its vector chunks"""
    try:
        # 1. Find all GridFS IDs associated with this filename in the vector db
        cursor = vector_collection.find({"filename": filename}, {"gridfs_file_id": 1, "_id": 0})
        gridfs_ids = {doc["gridfs_file_id"] for doc in await cursor.to_list(length=None)}
        
        from dsr_rag import fs
        
        # 2. Delete from GridFS
        deleted_gridfs = 0
        for f_id in gridfs_ids:
            try:
                 await fs.delete(f_id)
                 deleted_gridfs += 1
            except Exception as grid_err:
                 print(f"Error deleting from GridFS {f_id}: {grid_err}")
                 # Proceeding as it might have been deleted already
                 
        # 3. Delete from Vector Store
        result = await vector_collection.delete_many({"filename": filename})
        
        return {
            "message": f"Document '{filename}' deleted", 
            "chunks_removed": result.deleted_count,
            "gridfs_files_removed": deleted_gridfs
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



class ChatRequest(BaseModel):
    query: str
    thread_id: str

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    async def event_generator():
        # Setup communication queue between the LangGraph execution task and the SSE stream
        queue = asyncio.Queue()
        config = {"configurable": {"thread_id": request.thread_id, "queue": queue}}
        inputs = {"query": request.query}
        
        async def run_graph():
            try:
                async for output in agent_app.astream(inputs, config=config, stream_mode="updates"):
                    # We just consume the stream, real-time outputs go to queue via emit_log
                    pass 
                await queue.put({"type": "done"})
            except Exception as e:
                await queue.put({"type": "error", "message": str(e)})
                
        # Fire off graph execution in background
        task = asyncio.create_task(run_graph())
        
        while True:
            event = await queue.get()
            yield f"data: {json.dumps(event)}\n\n"
            
            if event["type"] in ("done", "error"):
                break
                
    return StreamingResponse(event_generator(), media_type="text/event-stream")
