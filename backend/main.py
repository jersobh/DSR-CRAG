import os
import io
import asyncio
import json
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pymupdf
from bson import ObjectId
from langchain_text_splitters import RecursiveCharacterTextSplitter

from dsr_rag import (
    save_to_gridfs,
    vector_collection,
    embeddings,
    build_dsr_rag_graph,
    client
)
from langgraph.checkpoint.mongodb.aio import AsyncMongoDBSaver

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
checkpointer = AsyncMongoDBSaver(client)
workflow = build_dsr_rag_graph()
agent_app = workflow.compile(checkpointer=checkpointer)

@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    content = await file.read()
    
    # Extract text from PDF
    try:
        doc = pymupdf.open(stream=content, filetype="pdf")
        full_text = ""
        for page in doc:
            full_text += page.get_text() + "\n"
        doc.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse PDF: {str(e)}")
        
    if not full_text.strip():
        raise HTTPException(status_code=400, detail="PDF has no extractable text")
        
    chunks = text_splitter.split_text(full_text)
    metadata = {"filename": file.filename, "source": "user_upload"}
    
    # Process chunks into MongoDB Atlas
    for i, chunk in enumerate(chunks):
        embedding = await embeddings.aembed_query(chunk)
        
        # Save exact chunk text to GridFS (pointer target)
        gridfs_file_id_str = await save_to_gridfs(chunk, file.filename, metadata)
        
        # Save vector + reference _id
        vector_doc = {
            "embedding": embedding,
            "gridfs_file_id": ObjectId(gridfs_file_id_str),
            "chunk_index": i,
            "filename": file.filename
        }
        await vector_collection.insert_one(vector_doc)
        
    return {"message": "Document processed and stored successfully", "chunks": len(chunks)}


@app.get("/documents")
async def list_documents():
    """Returns the list of unique ingested documents (files)"""
    try:
        # Get distinct filenames
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
