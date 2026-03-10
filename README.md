# DSR-CRAG (Dual-State Reflexive Corrective RAG)

DSR-CRAG is a full-stack, AI-powered application designed for intelligent document ingestion and retrieval. It implements a sophisticated **Dual-State Reflexive Retrieval-Augmented Generation (RAG)** architecture using LangGraph and MongoDB, paired with a modern React frontend.

## 🏗 System Architecture

The project consists of three main components:
1. **Frontend**: A React SPA built with Vite and TailwindCSS.
2. **Backend**: A FastAPI server handling file uploads, document management, and agentic workflows.
3. **Database**: MongoDB serving dual purposes: GridFS for robust document blob storage and Vector Search for efficient semantic retrieval.

### Backend (FastAPI + LangGraph)
The backend is the core of the intelligence layer. It uses **FastAPI** to expose RESTful endpoints and integrates with **Google Generative AI (Gemini 2.5 Flash)** for both LLM capabilities and embeddings.

**Key Technical Features:**
- **Dual-State LangGraph Architecture**: The system utilizes a LangGraph state machine (`dsr_rag.py`) to orchestrate complex RAG queries. It implements "Just-In-Time" (JIT) data materialization: the StateGraph strictly circulates lightweight database pointers (ObjectIds) rather than bloated document contents.
- **Reflexive Self-Correction**: The workflow contains a self-correction loop (`check_relevance`). Retrieved documents are graded for relevance using an LLM evaluator. If no relevant sources are found, an LLM query-rewriter automatically refines the search parameters to try again.
- **Tools Integrations**: The LLM agent has access to specific tools including a math calculator (`numexpr`), full document summarization, and database statistics querying.
- **Agentic State Persistence**: Queries are routed through specific threads (`thread_id`), with the conversation history check-pointed and persistent in MongoDB via `AsyncMongoDBSaver`.
- **Vector Search & GridFS**: Document ingestion splits text into chunks. Chunk texts are offloaded to **GridFS**, while vector embeddings are stored in a standard collection, allowing fast `$vectorSearch` operations that `$lookup` back to the GridFS chunks.

### Frontend (React + Vite)
The frontend provides a sleek, modern UI interacting seamlessly with the backend.

**Key Technical Features:**
- **React 19 & Vite**: Optimized frontend build and development toolkit.
- **Tailwind CSS**: Utility-first CSS framework for responsive design.
- **Rich Content Support**: The chat interface utilizes `react-markdown`, `remark-gfm`, and `react-syntax-highlighter` to format complex LLM responses correctly.
- **Mermaid JS Generation**: Configured to render complex diagrams (`mermaid`) when the LLM responds with quantitative data interpretations or flowcharts.

## 🚀 Getting Started

The easiest way to run the application is via Docker Compose.

### Prerequisites
- Docker & Docker Compose
- Environment variables configured `.env` (MongoDB URI, Google API Key)

### Environment Setup
Create a `.env` file at the root of the project with the following variables:
```env
MONGODB_URI=mongodb+srv://<user>:<password>@cluster.mongodb.net/?retryWrites=true&w=majority
GOOGLE_API_KEY=your_gemini_api_key
```

### Running the Project
Use Docker Compose to build and start both frontend and backend:
```bash
docker-compose up --build
```

- **Frontend App**: `http://localhost:5173`
- **Backend API**: `http://localhost:8000`

## 📡 API Endpoints 

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/upload` | POST | Ingests a PDF document, extracting chunks to Vector DB and GridFS. |
| `/documents` | GET | Returns a list of all ingested unique document filenames. |
| `/documents/{filename}` | DELETE | Cascades deletion of a specific document from all Vector and GridFS records. |
| `/chat` | POST | Main endpoint. Receives `{query, thread_id}` and streams LLM state chunks. |
