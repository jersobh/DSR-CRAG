import React, { useState } from 'react';
import FileUpload from './components/FileUpload';
import ChatInterface from './components/ChatInterface';

function App() {
  const [threadId, setThreadId] = useState(
    () => `thread_${Math.random().toString(36).substring(2, 9)}`
  );

  return (
    <div className="min-h-screen bg-transparent w-full text-slate-800 flex flex-col py-8 px-6 sm:px-10">
      <header className="mb-10 w-full mx-auto flex flex-col sm:flex-row justify-between items-start sm:items-center border-b border-slate-200 pb-6">
        <div>
          <h1 className="text-3xl sm:text-4xl font-extrabold text-slate-900 tracking-tight mb-2">
            Langgraph + MongoDB/GridFS RAG
          </h1>
          <p className="text-slate-600 text-sm">
            Dual-State Reflexive Corrective Retrieval-Augmented Generation
          </p>
        </div>
        <button
          onClick={() => setThreadId(`thread_${Math.random().toString(36).substring(2, 9)}`)}
          className="mt-4 sm:mt-0 bg-white hover:bg-slate-100 text-slate-700 text-sm py-2 px-4 rounded-full border border-slate-300 shadow-sm transition-all flex items-center gap-2 group"
        >
          <svg className="w-4 h-4 text-slate-500 group-hover:text-slate-800" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          New Session
        </button>
      </header>

      <main className="w-full mx-auto grid grid-cols-1 lg:grid-cols-12 gap-8 flex-grow">
        <div className="lg:col-span-4 space-y-6 flex flex-col">
          <div className="bg-white rounded-2xl p-6 shadow-md border border-slate-200 flex-grow">
            <div className="flex items-center gap-3 mb-6">
              <div className="bg-slate-100 p-2 rounded-lg border border-slate-200">
                <svg className="w-5 h-5 text-slate-700" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                </svg>
              </div>
              <h2 className="text-xl font-semibold text-slate-800">Knowledge Base</h2>
            </div>
            <FileUpload />
          </div>

          <div className="bg-slate-50 rounded-2xl p-5 border border-slate-200 shadow-sm">
            <h2 className="text-sm font-semibold text-slate-500 tracking-wider uppercase mb-3">Session Info</h2>
            <div className="flex items-center gap-3 text-xs font-mono bg-white p-3 rounded-lg text-slate-600 break-all border border-slate-200 shadow-[inset_0_1px_4px_rgba(0,0,0,0.02)]">
              <span className="text-slate-700 font-bold bg-slate-100 px-2 py-1 rounded">ID</span>
              {threadId}
            </div>
            <p className="text-xs text-slate-500 mt-3 leading-relaxed">
              Context is maintained within this thread. Use the 'New Session' button above to reset.
            </p>
          </div>
        </div>

        <div className="lg:col-span-8 flex flex-col">
          <div className="bg-white rounded-2xl shadow-md border border-slate-200 h-[75vh] min-h-[600px] flex flex-col overflow-hidden">
            <div className="p-5 border-b border-slate-100 bg-slate-50/50 flex items-center gap-3">
              <div className="bg-slate-100 p-2 rounded-lg border border-slate-200">
                <svg className="w-5 h-5 text-slate-700" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                </svg>
              </div>
              <h2 className="text-xl font-semibold text-slate-800">Agent Chat</h2>
            </div>
            <ChatInterface threadId={threadId} />
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
