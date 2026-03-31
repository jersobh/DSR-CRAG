# DSR-CRAG Frontend

This is the frontend application for the Dual-State Reflexive Corrective RAG (DSR-CRAG) project. It's a modern, interactive React Single Page Application (SPA) built with Vite and styled using Tailwind CSS.

## Overview

The frontend provides a user-friendly interface for interacting with the DSR-CRAG backend. Key functionalities include:

- **Document Upload**: Users can upload PDF, CSV, or XLSX documents for ingestion into the RAG system.
- **Chat Interface**: A real-time chat interface where users can ask questions and receive answers streamed from the DSR-CRAG agent.
- **Session Management**: Users can view and manage their conversation sessions, including retrieving historical chats and deleting sessions.
- **Document Management**: Users can view a list of ingested documents and delete them from the system.
- **Rich Content Display**: The chat interface supports rendering Markdown, code blocks, and Mermaid diagrams for enhanced readability of LLM responses.

## Technologies Used

- **React 19**: A JavaScript library for building user interfaces.
- **Vite**: A fast frontend build tool that provides a lightning-fast development experience.
- **Tailwind CSS**: A utility-first CSS framework for rapidly building custom designs.
- **react-markdown**: A React component to render Markdown.
- **remark-gfm**: A remark plugin to support GitHub Flavored Markdown.
- **react-syntax-highlighter**: Syntax highlighting for React.
- **Mermaid JS**: For rendering diagrams and flowcharts.

## Project Structure

The main application logic resides in the `src` directory:

- `src/App.jsx`: The main application component.
- `src/components/`: Contains reusable React components (e.g., chat window, document list, upload form).
- `src/hooks/`: Custom React hooks for managing state and side effects.
- `src/services/`: Functions for interacting with the DSR-CRAG backend API.
- `src/utils/`: Utility functions.

## Getting Started

To run the frontend application locally:

1.  **Navigate to the frontend directory**:
    ```bash
    cd frontend
    ```
2.  **Install dependencies**:
    ```bash
    npm install
    ```
3.  **Start the development server**:
    ```bash
    npm run dev
    ```
    The application will typically be available at `http://localhost:5173`.

Ensure the backend is running and accessible as configured in the frontend's API service (usually `http://localhost:8000`).

## Interaction with Backend

The frontend communicates with the DSR-CRAG backend (FastAPI) via RESTful API endpoints. Key interactions include:

-   `POST /upload`: For uploading documents.
-   `GET /documents`: To list ingested documents.
-   `DELETE /documents/{filename}`: To delete a specific document.
-   `POST /chat`: For sending user queries and receiving streamed LLM responses.
-   `GET /sessions`: To list active chat sessions.
-   `GET /sessions/{thread_id}/history`: To retrieve the message history of a specific session.
-   `DELETE /sessions/{thread_id}`: To delete a specific chat session.
-   `DELETE /sessions/clear`: To clear all chat sessions.

For more details on the backend API, refer to the main `README.md` in the project root and the backend's API documentation.