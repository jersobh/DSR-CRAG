import React, { useState, useEffect, useCallback } from 'react';

const FileUpload = () => {
    const [files, setFiles] = useState([]);
    const [uploadedDocs, setUploadedDocs] = useState([]);
    const [status, setStatus] = useState('idle');
    const [message, setMessage] = useState('');

    const fetchDocuments = useCallback(async () => {
        try {
            const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
            const response = await fetch(`${baseUrl}/documents`);
            const data = await response.json();
            if (response.ok) {
                setUploadedDocs(data.documents || []);
            }
        } catch (err) {
            console.error("Failed to fetch documents", err);
        }
    }, []);

    useEffect(() => {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        fetchDocuments();
    }, [fetchDocuments]);

    const handleFileChange = (e) => {
        if (e.target.files && e.target.files.length > 0) {
            setFiles(Array.from(e.target.files));
        }
    };

    const handleUpload = async () => {
        if (files.length === 0) return;

        setStatus('uploading');
        setMessage(`Uploading ${files.length} document(s)...`);

        let successCount = 0;

        for (const file of files) {
            const formData = new FormData();
            formData.append('file', file);

            try {
                const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
                const response = await fetch(`${baseUrl}/upload`, {
                    method: 'POST',
                    body: formData,
                });

                if (response.ok) {
                    successCount++;
                }
            } catch (error) {
                console.error(`Failed to upload ${file.name}`, error);
            }
        }

        if (successCount === files.length) {
            setStatus('success');
            setMessage(`Successfully ingested ${successCount} document(s).`);
            setFiles([]);
        } else {
            setStatus('error');
            setMessage(`Uploaded ${successCount}/${files.length} documents.`);
        }

        // Refresh document list
        fetchDocuments();
    };

    const handleDelete = async (filename) => {
        try {
            const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
            const response = await fetch(`${baseUrl}/documents/${encodeURIComponent(filename)}`, {
                method: 'DELETE',
            });
            if (response.ok) {
                setMessage(`Deleted ${filename}`);
                setStatus('success');
                fetchDocuments();
            }
        } catch (error) {
            console.error(`Failed to delete ${filename}`, error);
            setStatus('error');
            setMessage(`Failed to delete ${filename}`);
        }
    };

    return (
        <div className="flex flex-col gap-4 lg:h-full lg:min-h-0">
            <div className="flex items-center justify-center w-full">
                <label htmlFor="dropzone-file" className="flex flex-col items-center justify-center w-full h-36 border-2 border-slate-300 border-dashed rounded-2xl cursor-pointer bg-slate-50/50 hover:bg-slate-100 transition-all group overflow-hidden relative">
                    <div className="flex flex-col items-center justify-center pt-5 pb-6">
                        <svg className="w-10 h-10 mb-4 text-slate-400 group-hover:text-slate-600 transition-colors" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 20 16">
                            <path stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M13 13h3a3 3 0 0 0 0-6h-.025A5.56 5.56 0 0 0 16 6.5 5.5 5.5 0 0 0 5.207 5.021C5.137 5.017 5.071 5 5 5a4 4 0 0 0 0 8h2.167M10 15V6m0 0L8 8m2-2 2 2" />
                        </svg>
                        <p className="mb-2 text-sm text-slate-600">
                            <span className="font-semibold text-slate-800">Click to select files</span> or drag and drop
                        </p>
                        <p className="text-xs text-slate-500">PDF documents only</p>

                        {files.length > 0 && (
                            <div className="absolute bottom-0 left-0 right-0 bg-slate-800 text-white text-xs font-medium py-1.5 text-center">
                                {files.length} file(s) ready to upload
                            </div>
                        )}
                    </div>
                    <input id="dropzone-file" type="file" className="hidden" accept=".pdf" multiple onChange={handleFileChange} />
                </label>
            </div>

            <button
                onClick={handleUpload}
                disabled={files.length === 0 || status === 'uploading'}
                className="w-full bg-slate-900 hover:bg-slate-800 text-white font-medium py-3 px-4 rounded-xl disabled:opacity-50 transition-all disabled:cursor-not-allowed shadow-md hover:shadow-lg active:scale-[0.98] flex items-center justify-center gap-2"
            >
                {status === 'uploading' ? (
                    <>
                        <svg className="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        Ingesting...
                    </>
                ) : 'Upload Selected Documents'}
            </button>

            {message && (
                <div className={`p-3 rounded text-sm ${status === 'error' ? 'bg-red-50 text-red-700 border border-red-200' :
                    status === 'success' ? 'bg-green-50 text-green-700 border border-green-200' :
                        'bg-slate-50 text-slate-700 border border-slate-200'
                    }`}>
                    {message}
                </div>
            )}

            {/* Uploaded Documents List */}
            <div className="mt-4 border-t border-slate-200 pt-6 flex-grow lg:flex-1 flex flex-col lg:min-h-0">
                <div className="flex items-center gap-2 mb-4 text-slate-700">
                    <svg className="w-4 h-4 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" />
                    </svg>
                    <h3 className="text-sm font-medium tracking-wide">Ingested Documents in DB</h3>
                </div>
                {uploadedDocs.length === 0 ? (
                    <div className="text-center py-6 bg-slate-50 rounded-xl border border-dashed border-slate-300">
                        <p className="text-xs text-slate-500 italic">No documents available.</p>
                    </div>
                ) : (
                    <ul className="space-y-3 overflow-y-auto pr-2 flex-grow custom-scrollbar">
                        {uploadedDocs.map((docName, i) => (
                            <li key={i} className="group flex items-center justify-between text-sm bg-white hover:bg-slate-50 border border-slate-200 shadow-sm p-3 rounded-xl transition-all relative overflow-hidden">
                                <div className="absolute left-0 top-0 bottom-0 w-1 bg-slate-400 rounded-l-xl"></div>
                                <div className="flex items-center gap-3 pl-2 truncate">
                                    <svg className="w-4 h-4 text-slate-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                    </svg>
                                    <span className="truncate max-w-[180px] sm:max-w-[220px] text-slate-700 group-hover:text-slate-900 transition-colors" title={docName}>{docName}</span>
                                </div>
                                <button
                                    onClick={() => handleDelete(docName)}
                                    className="text-slate-500 hover:text-red-300 hover:bg-red-500/20 p-2 rounded-lg transition-all"
                                    title="Delete Document"
                                >
                                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                    </svg>
                                </button>
                            </li>
                        ))}
                    </ul>
                )}
            </div>
        </div>
    );
};

export default FileUpload;
