import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Mermaid } from './Mermaid';

const ChatInterface = ({ threadId }) => {
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [selectedSource, setSelectedSource] = useState(null);
    const messagesEndRef = useRef(null);
    const inputRef = useRef(null);

    // Fetch history when threadId changes
    useEffect(() => {
        const fetchHistory = async () => {
            if (!threadId) return;
            setIsLoading(true);
            try {
                const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
                const response = await fetch(`${baseUrl}/sessions/${threadId}/history`);
                const data = await response.json();
                if (response.ok) {
                    setMessages(data.messages || []);
                } else {
                    setMessages([]);
                }
            } catch (err) {
                console.error("Failed to fetch message history", err);
                setMessages([]);
            } finally {
                setIsLoading(false);
            }
        };

        fetchHistory();
    }, [threadId]);

    // Auto-focus input when loading ends or component mounts
    useEffect(() => {
        if (!isLoading) {
            const timeoutId = setTimeout(() => {
                inputRef.current?.focus();
            }, 100);
            return () => clearTimeout(timeoutId);
        }
    }, [isLoading]);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        setMessages([]);
    }, [threadId]);

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!input.trim() || isLoading) return;

        const userMessage = { role: 'user', content: input };
        setMessages((prev) => [...prev, userMessage]);
        setInput('');
        setIsLoading(true);

        try {
            const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query: userMessage.content,
                    thread_id: threadId,
                }),
            });

            if (!response.ok) {
                throw new Error(`HTTP Error: ${response.status}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder('utf-8');
            let done = false;
            let currentAssistantMessage = '';

            // Insert placeholder for streaming answer and logs
            setMessages((prev) => [...prev, { role: 'assistant', content: '', logs: [] }]);

            while (!done) {
                const { value, done: readerDone } = await reader.read();
                done = readerDone;
                if (value) {
                    const chunkStr = decoder.decode(value, { stream: true });
                    const events = chunkStr.split('\n\n');

                    for (const ev of events) {
                        if (ev.startsWith('data: ')) {
                            const dataStr = ev.substring(6);
                            if (!dataStr) continue;
                            try {
                                const data = JSON.parse(dataStr);
                                if (data.type === 'log') {
                                    setMessages((prev) => {
                                        const newMsgs = [...prev];
                                        const last = { ...newMsgs[newMsgs.length - 1] };
                                        last.logs = [...(last.logs || []), data.message];
                                        newMsgs[newMsgs.length - 1] = last;
                                        return newMsgs;
                                    });
                                } else if (data.type === 'token') {
                                    currentAssistantMessage += data.content;
                                    setMessages((prev) => {
                                        const newMsgs = [...prev];
                                        const last = { ...newMsgs[newMsgs.length - 1] };
                                        last.content = currentAssistantMessage;
                                        newMsgs[newMsgs.length - 1] = last;
                                        return newMsgs;
                                    });
                                } else if (data.type === 'sources') {
                                    setMessages((prev) => {
                                        const newMsgs = [...prev];
                                        const last = { ...newMsgs[newMsgs.length - 1] };
                                        last.sources = data.sources;
                                        newMsgs[newMsgs.length - 1] = last;
                                        return newMsgs;
                                    });
                                } else if (data.type === 'error') {
                                    setMessages((prev) => [
                                        ...prev,
                                        { role: 'system', content: `Error: ${data.message}` }
                                    ]);
                                }
                            } catch (e) {
                                console.error("Error parsing stream JSON:", e);
                            }
                        }
                    }
                }
            }
        } catch {
            setMessages((prev) => [
                ...prev,
                { role: 'system', content: 'Connection to AI failed or stream interruped.' }
            ]);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="flex flex-col h-full bg-white">
            <div className="flex-1 overflow-y-auto px-4 sm:px-6 lg:px-20 py-10 space-y-12 custom-scrollbar">
                {messages.length === 0 ? (
                    <div className="h-full flex flex-col items-center justify-center text-slate-400 space-y-4">
                        <div className="w-12 h-12 border border-slate-200 rounded-xl flex items-center justify-center text-slate-300">
                            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                            </svg>
                        </div>
                        <p className="text-sm font-medium">Start a conversation or upload a document.</p>
                    </div>
                ) : (
                    messages.map((msg, index) => (
                        <div
                            key={index}
                            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                        >
                            <div className={`w-full max-w-4xl flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} gap-4`}>
                                {msg.role !== 'user' && (
                                    <div className="w-8 h-8 rounded-full bg-slate-100 border border-slate-200 flex-shrink-0 flex items-center justify-center text-[10px] font-bold text-slate-500">
                                        AI
                                    </div>
                                )}
                                <div
                                    className={`rounded-2xl px-6 py-4 text-[15px] leading-relaxed ${msg.role === 'user'
                                        ? 'bg-slate-50 border border-slate-200 text-slate-800'
                                        : msg.role === 'system'
                                            ? 'text-red-500 text-sm italic'
                                            : 'text-slate-800'
                                        }`}
                                >
                                    {msg.role === 'user' ? (
                                        <div className="whitespace-pre-wrap">{msg.content}</div>
                                    ) : (
                                        <div className="flex flex-col w-full">
                                            {msg.logs && msg.logs.length > 0 && (
                                                <details className="mb-6 group">
                                                    <summary className="flex items-center gap-2 text-[9px] font-bold text-slate-400 uppercase tracking-widest mb-2 cursor-pointer hover:text-slate-600 transition-colors list-none">
                                                        <svg className="w-2.5 h-2.5 transition-transform group-open:rotate-90" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M9 5l7 7-7 7" />
                                                        </svg>
                                                        Process Logs
                                                    </summary>
                                                    <div className="space-y-2 p-4 bg-slate-50/50 border border-slate-100 rounded-xl text-[11px] font-mono text-slate-500 max-h-40 overflow-y-auto custom-scrollbar">
                                                        {msg.logs.map((log, ldx) => (
                                                            <div key={ldx} className="border-l border-slate-200 pl-3 py-0.5">{log}</div>
                                                        ))}
                                                    </div>
                                                </details>
                                            )}
                                            <div className="prose prose-slate max-w-none prose-p:leading-relaxed prose-pre:bg-slate-50 prose-pre:border prose-pre:border-slate-200 prose-pre:text-slate-700 prose-code:text-indigo-600 prose-headings:font-bold">
                                                <ReactMarkdown
                                                    remarkPlugins={[remarkGfm]}
                                                    components={{
                                                        code({ node, inline, className, children, ...props }) {
                                                            const match = /language-(\w+)/.exec(className || '');
                                                            if (!inline && match && match[1] === 'mermaid') {
                                                                return <Mermaid chart={String(children).replace(/\n$/, '')} />;
                                                            }
                                                            return !inline ? (
                                                                <pre className="!bg-slate-50 border border-slate-200 rounded-xl p-5 overflow-x-auto text-[13px] font-mono leading-relaxed">
                                                                    <code className={className} {...props}>
                                                                        {children}
                                                                    </code>
                                                                </pre>
                                                            ) : (
                                                                <code className="bg-slate-50 px-1 py-0.5 rounded text-indigo-600 font-mono text-xs" {...props}>
                                                                    {children}
                                                                </code>
                                                            );
                                                        }
                                                    }}
                                                >
                                                    {msg.content}
                                                </ReactMarkdown>
                                            </div>

                                            {msg.sources && msg.sources.length > 0 && (
                                                <div className="mt-8 flex gap-2 overflow-x-auto pb-2 custom-scrollbar">
                                                    {msg.sources.map((source, idx) => (
                                                        <button
                                                            key={idx}
                                                            onClick={() => setSelectedSource(source)}
                                                            className="flex-shrink-0 px-3 py-1.5 rounded-lg text-xs font-semibold bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 transition-colors flex items-center gap-2 shadow-sm"
                                                        >
                                                            <svg className="w-3 h-3 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                                                            </svg>
                                                            {source.filename || source}
                                                        </button>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    ))
                )}

                {isLoading && (
                    <div className="flex justify-start">
                        <div className="w-8 h-8 rounded-full bg-slate-50 border border-slate-200 flex items-center justify-center mr-4">
                            <div className="w-1 h-1 bg-slate-400 rounded-full animate-ping"></div>
                        </div>
                    </div>
                )}
                <div ref={messagesEndRef} />
            </div>

            <div className="p-6 sm:px-20 border-t border-slate-100 bg-white">
                <form onSubmit={handleSubmit} className="relative max-w-4xl mx-auto">
                    <input
                        ref={inputRef}
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        placeholder="Message DSR-RAG..."
                        className="w-full bg-white border border-slate-200 text-slate-800 rounded-2xl px-6 py-4 focus:outline-none focus:ring-2 focus:ring-slate-100 focus:border-slate-300 transition-all shadow-sm placeholder:text-slate-400 font-medium"
                        disabled={isLoading}
                    />
                    <button
                        type="submit"
                        disabled={isLoading || !input.trim()}
                        className="absolute right-3 top-2.5 bottom-2.5 bg-slate-900 hover:bg-black text-white rounded-xl px-5 transition-all disabled:opacity-30 disabled:grayscale flex items-center justify-center"
                    >
                        {isLoading ? (
                            <svg className="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                        ) : (
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 10l7-7m0 0l7 7m-7-7v18" />
                            </svg>
                        )}
                    </button>
                </form>
                <p className="text-center mt-4 text-[10px] text-slate-400 font-medium uppercase tracking-[0.1em]">
                    AI Assistant
                </p>
            </div>

            {/* Source Inspector Modal */}
            {selectedSource && (
                <div
                    className="fixed inset-0 z-50 flex items-center justify-center bg-white/80 backdrop-blur-sm p-4 sm:p-10"
                    onClick={() => setSelectedSource(null)}
                >
                    <div
                        className="bg-white w-full max-w-4xl h-full rounded-[2rem] border border-slate-200 shadow-2xl flex flex-col overflow-hidden animate-in fade-in zoom-in duration-200"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="flex items-center justify-between p-6 border-b border-slate-100">
                            <div className="flex items-center gap-4">
                                <span className="p-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-500">
                                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                    </svg>
                                </span>
                                <h3 className="text-lg font-bold text-slate-800 truncate">{selectedSource.filename}</h3>
                            </div>
                            <button
                                onClick={() => setSelectedSource(null)}
                                className="p-2 hover:bg-slate-100 rounded-full transition-colors"
                            >
                                <svg className="w-6 h-6 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                            </button>
                        </div>
                        <div className="flex-1 overflow-y-auto p-10 bg-slate-50/50 custom-scrollbar text-slate-700 leading-relaxed">
                            <div className="prose prose-slate max-w-none">
                                {selectedSource.content || "No content found."}
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div >
    );
};

export default ChatInterface;
