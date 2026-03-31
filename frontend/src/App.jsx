import React, { useState } from 'react';
import FileUpload from './components/FileUpload';
import ChatInterface from './components/ChatInterface';
import SessionsList from './components/SessionsList';

/**
 * The main application component for the DSR-CRAG frontend.
 *
 * This component orchestrates the layout and functionality of the application,
 * including document upload, chat interface, and session management.
 * It manages the active conversation thread ID and passes it to child components.
 */
function App() {
  const [threadId, setThreadId] = useState(
    () => `thread_${Math.random().toString(36).substring(2, 9)}`
  );

  return (
    <div className="h-screen w-full flex overflow-hidden bg-white text-slate-900 selection:bg-indigo-100">
      {/* Navigation / Sidebar */}
      <aside className="hidden lg:flex flex-col w-80 border-r border-slate-100 bg-slate-50/50">
        <div className="p-6 border-b border-slate-100 flex items-center gap-3">
          <div className="w-8 h-8 bg-black rounded-lg flex items-center justify-center text-white font-bold text-xl">
            D
          </div>
          <h1 className="font-bold text-lg tracking-tight">DSR-RAG</h1>
        </div>

        <div className="flex-1 overflow-y-auto p-6 custom-scrollbar">
          <div className="mb-8">
            <h2 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-4">Knowledge Assets</h2>
            <FileUpload />
          </div>

          <SessionsList
            currentThreadId={threadId}
            onSelectSession={(id) => setThreadId(id)}
          />
        </div>

        <div className="p-6 border-t border-slate-100 bg-white">
          <button
            onClick={() => setThreadId(`thread_${Math.random().toString(36).substring(2, 9)}`)}
            className="w-full py-2.5 px-4 bg-black hover:bg-slate-800 rounded-xl text-xs font-bold text-white transition-all flex items-center justify-center gap-2 shadow-lg shadow-slate-200"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            New Conversation
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col min-w-0 bg-white">
        <header className="lg:hidden p-4 border-b border-slate-100 flex items-center justify-between">
          <h1 className="font-bold text-lg">DSR-RAG</h1>
          <button
            onClick={() => setThreadId(`thread_${Math.random().toString(36).substring(2, 9)}`)}
            className="p-2 hover:bg-slate-100 rounded-lg"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
        </header>

        <div className="flex-1 flex flex-col overflow-hidden relative">
          <ChatInterface threadId={threadId} />
        </div>
      </main>
    </div>
  );
}

export default App;