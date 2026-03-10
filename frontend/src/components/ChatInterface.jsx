import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Mermaid } from './Mermaid';

const ChatInterface = ({ threadId }) => {
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const messagesEndRef = useRef(null);

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
        <div className="flex flex-col h-full">
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {messages.length === 0 ? (
                    <div className="h-full flex flex-col items-center justify-center text-slate-500 space-y-4">
                        <div className="bg-slate-50 p-4 rounded-full border border-slate-200 shadow-sm">
                            <svg className="w-10 h-10 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                            </svg>
                        </div>
                        <p className="text-sm font-medium text-slate-500">Upload a document and ask questions.</p>
                    </div>
                ) : (
                    messages.map((msg, index) => (
                        <div
                            key={index}
                            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                        >
                            <div
                                className={`max-w-[85%] rounded-2xl p-5 shadow-sm text-sm leading-relaxed ${msg.role === 'user'
                                    ? 'bg-slate-900 text-white rounded-br-sm shadow-md'
                                    : msg.role === 'system'
                                        ? 'bg-red-50 text-red-600 border border-red-200 rounded-bl-sm shadow-sm'
                                        : 'bg-white text-slate-800 border border-slate-200/60 rounded-bl-sm shadow-md'
                                    }`}
                            >
                                {msg.role === 'user' ? (
                                    <div className="whitespace-pre-wrap">{msg.content}</div>
                                ) : (
                                    <div className="flex flex-col w-full">
                                        {msg.logs && msg.logs.length > 0 && (
                                            <div className="mb-4 space-y-1.5 p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs font-mono text-slate-500 max-h-40 overflow-y-auto">
                                                <div className="text-slate-400 font-semibold mb-2 flex items-center gap-2">
                                                    <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                                                    </svg>
                                                    Agent Trace
                                                </div>
                                                {msg.logs.map((log, ldx) => (
                                                    <div key={ldx} className="break-words border-l-2 border-slate-300 pl-2 py-0.5">{log}</div>
                                                ))}
                                            </div>
                                        )}
                                        <div className="prose prose-slate prose-sm max-w-none prose-p:leading-relaxed prose-headings:text-slate-800 prose-a:text-slate-900">
                                            <ReactMarkdown
                                                remarkPlugins={[remarkGfm]}
                                                components={{
                                                    code({ node, inline, className, children, ...props }) {
                                                        const match = /language-(\w+)/.exec(className || '');
                                                        if (!inline && match && match[1] === 'mermaid') {
                                                            return <Mermaid chart={String(children).replace(/\n$/, '')} />;
                                                        }
                                                        return !inline ? (
                                                            <pre className="bg-slate-800 p-4 rounded-xl overflow-x-auto border border-slate-700 my-5 shadow-inner text-slate-100">
                                                                <code className={className} {...props}>
                                                                    {children}
                                                                </code>
                                                            </pre>
                                                        ) : (
                                                            <code className="bg-slate-100 px-1.5 py-0.5 rounded text-slate-700 font-mono text-xs border border-slate-200" {...props}>
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
                                            <div className="mt-3 pt-3 border-t border-slate-100">
                                                <div className="flex items-center gap-1.5 mb-2 text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                                                    <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                                                    </svg>
                                                    Sources
                                                </div>
                                                <div className="flex flex-wrap gap-2">
                                                    {msg.sources.map((source, idx) => (
                                                        <span key={idx} className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-slate-100 text-slate-600 border border-slate-200">
                                                            {source}
                                                        </span>
                                                    ))}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                )}
                            </div>
                        </div>
                    ))
                )}

                {isLoading && (
                    <div className="flex justify-start">
                        <div className="bg-white rounded-2xl rounded-bl-sm p-5 border border-slate-200 shadow-sm">
                            <div className="flex space-x-2 items-center h-5">
                                <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"></div>
                                <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce [animation-delay:0.2s]"></div>
                                <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce [animation-delay:0.4s]"></div>
                            </div>
                        </div>
                    </div>
                )}
                <div ref={messagesEndRef} />
            </div>

            <div className="p-4 border-t border-slate-100 bg-slate-50/50">
                <form onSubmit={handleSubmit} className="flex gap-3 relative mx-auto">
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        placeholder="Ask a question about your documents..."
                        className="flex-1 bg-white border border-slate-300 text-slate-800 rounded-xl px-5 py-4 focus:outline-none focus:ring-2 focus:ring-slate-400 focus:border-slate-500 transition-all shadow-sm placeholder:text-slate-400"
                        disabled={isLoading}
                    />
                    <button
                        type="submit"
                        disabled={isLoading || !input.trim()}
                        className="absolute right-2 top-2 bottom-2 bg-slate-900 hover:bg-slate-800 text-white rounded-lg px-6 font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center shadow-md active:scale-95"
                    >
                        {isLoading ? (
                            <svg className="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                        ) : 'Send'}
                    </button>
                </form>
            </div>
        </div >
    );
};

export default ChatInterface;
