import React, { useState, useEffect, useCallback } from 'react';
import ConfirmationModal from './ConfirmationModal';

const SessionsList = ({ currentThreadId, onSelectSession }) => {
    const [sessions, setSessions] = useState([]);
    const [isLoading, setIsLoading] = useState(false);
    const [modalConfig, setModalConfig] = useState({ isOpen: false, type: 'clearAll', targetId: null });

    const fetchSessions = useCallback(async () => {
        setIsLoading(true);
        try {
            const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
            const response = await fetch(`${baseUrl}/sessions`);
            const data = await response.json();
            if (response.ok) {
                setSessions(data.sessions || []);
            }
        } catch (err) {
            console.error("Failed to fetch sessions", err);
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchSessions();
        // Refresh every 10 seconds or when thread changes externally
        const interval = setInterval(fetchSessions, 10000);
        return () => clearInterval(interval);
    }, [fetchSessions]);

    const handleClearAll = async () => {
        try {
            const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
            await fetch(`${baseUrl}/sessions/clear`, { method: 'DELETE' });
            fetchSessions();
            onSelectSession(`thread_${Math.random().toString(36).substring(2, 9)}`);
        } catch (err) {
            console.error("Failed to clear sessions", err);
        }
    };

    const handleDeleteSession = async (thread_id) => {
        try {
            const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
            await fetch(`${baseUrl}/sessions/${thread_id}`, { method: 'DELETE' });
            fetchSessions();
            if (currentThreadId === thread_id) {
                onSelectSession(`thread_${Math.random().toString(36).substring(2, 9)}`);
            }
        } catch (err) {
            console.error("Failed to delete session", err);
        }
    };

    return (
        <div className="flex flex-col gap-4 mt-8">
            <div className="flex items-center justify-between mb-2">
                <h2 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">History</h2>
                <button 
                    onClick={() => setModalConfig({ isOpen: true, type: 'clearAll', targetId: null })}
                    className="text-[9px] font-bold text-red-400 hover:text-red-600 uppercase tracking-tighter transition-colors"
                >
                    Clear All
                </button>
            </div>
            
            <ConfirmationModal 
                isOpen={modalConfig.isOpen}
                onClose={() => setModalConfig({ ...modalConfig, isOpen: false })}
                onConfirm={modalConfig.type === 'clearAll' ? handleClearAll : () => handleDeleteSession(modalConfig.targetId)}
                title={modalConfig.type === 'clearAll' ? "Clear All History" : "Delete Conversation"}
                message={modalConfig.type === 'clearAll' 
                    ? "This will permanently remove all conversation checkpoints from your local database. This action cannot be undone." 
                    : "Are you sure you want to delete this specific conversation thread? Its memory will be lost forever."}
                confirmText={modalConfig.type === 'clearAll' ? "Yes, Clear All" : "Delete"}
            />

            {isLoading && sessions.length === 0 ? (
                <div className="animate-pulse flex space-x-2 p-3">
                    <div className="flex-1 space-y-2 py-1">
                        <div className="h-2 bg-slate-200 rounded"></div>
                    </div>
                </div>
            ) : sessions.length === 0 ? (
                <div className="p-4 bg-slate-50 rounded-xl border border-dashed border-slate-200 text-center">
                    <p className="text-[10px] text-slate-400 italic">No previous sessions found.</p>
                </div>
            ) : (
                <div className="space-y-2 max-h-[300px] overflow-y-auto pr-2 custom-scrollbar">
                    {sessions.map((session) => (
                        <div
                            key={session.thread_id}
                            onClick={() => onSelectSession(session.thread_id)}
                            className={`group w-full relative cursor-pointer p-3 rounded-xl border transition-all flex flex-col gap-1 overflow-hidden h-14 ${
                                currentThreadId === session.thread_id
                                    ? 'bg-white border-slate-300 shadow-sm ring-2 ring-slate-100'
                                    : 'bg-transparent border-transparent hover:bg-slate-100 text-slate-500 hover:text-slate-900 border-transparent hover:border-slate-200'
                            }`}
                        >
                            {currentThreadId === session.thread_id && (
                                <div className="absolute left-0 top-0 bottom-0 w-1 bg-black"></div>
                            )}
                            <div className="flex items-center justify-between">
                                <div className="text-[11px] font-mono truncate max-w-[140px]">
                                    {session.thread_id}
                                </div>
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        setModalConfig({ isOpen: true, type: 'delete', targetId: session.thread_id });
                                    }}
                                    className="opacity-0 group-hover:opacity-100 p-1 text-slate-400 hover:text-red-500 transition-all"
                                    title="Delete conversation"
                                >
                                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                    </svg>
                                </button>
                            </div>
                            <div className="text-[10px] opacity-60 flex items-center gap-1.5 mt-auto">
                                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                                </svg>
                                {session.updated_at ? new Date(session.updated_at).toLocaleTimeString() : 'Recent'}
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};

export default SessionsList;
