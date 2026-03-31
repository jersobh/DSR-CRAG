import React from 'react';

/**
 * A reusable confirmation modal component.
 *
 * This component displays a modal with a title, message, and customizable
 * confirm/cancel buttons. It is conditionally rendered based on the `isOpen` prop.
 *
 * @param {Object} props - The component props.
 * @param {boolean} props.isOpen - Controls the visibility of the modal.
 * @param {function} props.onClose - Callback function to close the modal.
 * @param {function} props.onConfirm - Callback function to execute when the confirm button is clicked.
 * @param {string} props.title - The title displayed in the modal.
 * @param {string} props.message - The main message content of the modal.
 * @param {string} [props.confirmText="Confirm"] - The text for the confirm button.
 * @param {string} [props.cancelText="Cancel"] - The text for the cancel button.
 * @param {string} [props.type="danger"] - The type of modal, influencing styling (e.g., "danger" for red buttons).
 */
const ConfirmationModal = ({ isOpen, onClose, onConfirm, title, message, confirmText = "Confirm", cancelText = "Cancel", type = "danger" }) => {
    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm transition-all animate-in fade-in duration-200">
            <div className="bg-white rounded-3xl shadow-2xl shadow-slate-200/50 w-full max-w-sm overflow-hidden border border-slate-100 animate-in zoom-in-95 duration-200">
                <div className="p-8">
                    <div className="flex items-center justify-center w-12 h-12 rounded-2xl mb-6 bg-red-50 text-red-500 mx-auto">
                        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                    </div>
                    
                    <h3 className="text-lg font-bold text-slate-900 text-center mb-2">{title}</h3>
                    <p className="text-sm text-slate-500 text-center leading-relaxed">
                        {message}
                    </p>
                </div>
                
                <div className="flex border-t border-slate-50 p-4 gap-3 bg-slate-50/50">
                    <button
                        onClick={onClose}
                        className="flex-1 py-3 px-4 rounded-xl text-sm font-semibold text-slate-600 hover:bg-white hover:shadow-sm transition-all active:scale-[0.98]"
                    >
                        {cancelText}
                    </button>
                    <button
                        onClick={() => {
                            onConfirm();
                            onClose();
                        }}
                        className={`flex-1 py-3 px-4 rounded-xl text-sm font-bold text-white transition-all active:scale-[0.98] shadow-lg ${
                            type === 'danger' ? 'bg-red-500 hover:bg-red-600 shadow-red-100' : 'bg-black hover:bg-slate-800 shadow-slate-200'
                        }`}
                    >
                        {confirmText}
                    </button>
                </div>
            </div>
        </div>
    );
};

export default ConfirmationModal;