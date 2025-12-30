import React from 'react';
import { X, Loader2 } from 'lucide-react';
import InvoiceViewer from './InvoiceViewer';
import DataEditor from './DataEditor';

const AnalysisModal = ({ isOpen, onClose, isLoading, invoiceData, lineItems, imagePath }) => {
    if (!isOpen) return null;

    // Construct preview URL from imagePath
    // imagePath covers /static/invoices/...
    // If running in dev, we might need localhost logic, but usually the backend serves static.
    // The imagePath from DB is already "/static/invoices/..."
    const API_BASE_URL = window.location.hostname.includes('pharmagpt.co')
        ? 'https://api.pharmagpt.co'
        : 'http://localhost:8000';

    // If the path starts with /static, prepend API URL.
    // If it's a blob url (not likely here), leave it.
    const previewUrl = imagePath ? `${API_BASE_URL}${imagePath}` : null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
            {/* Modal Container */}
            <div className="relative w-[95vw] h-[95vh] bg-slate-950 rounded-2xl border border-slate-800 shadow-2xl overflow-hidden flex flex-col">

                {/* Header */}
                <div className="h-14 border-b border-slate-800 flex items-center justify-between px-6 bg-slate-900/50">
                    <h2 className="text-lg font-semibold text-slate-200 flex items-center gap-2">
                        Invoice Details
                        {invoiceData?.Invoice_No && (
                            <span className="text-sm font-normal text-slate-500 bg-slate-800 px-2 py-0.5 rounded-md">
                                #{invoiceData.Invoice_No}
                            </span>
                        )}
                    </h2>
                    <button
                        onClick={onClose}
                        className="p-2 hover:bg-slate-800 rounded-full text-slate-400 hover:text-white transition-colors"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-hidden relative">
                    {isLoading ? (
                        <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-400">
                            <Loader2 className="w-8 h-8 animate-spin text-indigo-500 mb-2" />
                            <p>Loading invoice data...</p>
                        </div>
                    ) : (
                        <div className="flex flex-col md:flex-row h-full w-full">
                            {/* Left: ImageViewer */}
                            <div className="w-full md:w-1/2 flex flex-col border-b md:border-b-0 md:border-r border-slate-800 h-1/2 md:h-full">
                                <InvoiceViewer
                                    previewUrl={previewUrl}
                                    isAnalyzing={false}
                                    onFileChange={() => { }} // Read-only
                                    onReset={() => { }} // Read-only
                                    file={null} // Only viewing preview
                                />
                            </div>

                            {/* Right: DataEditor (Read Only) */}
                            <div className="w-full md:w-1/2 flex flex-col bg-slate-900/50 h-1/2 md:h-full">
                                <DataEditor
                                    invoiceData={invoiceData}
                                    lineItems={lineItems}
                                    warnings={[]} // Hide warnings in history view or pass them if stored
                                    isSaving={false}
                                    isAnalyzing={false}
                                    readOnly={true} // Hides Save button
                                    onHeaderChange={() => { }}
                                    onInputChange={() => { }}
                                    onAddRow={() => { }}
                                    onConfirm={() => { }}
                                    onExport={() => { }} // Could enable export here too
                                    successMsg={null}
                                    errorMsg={null}
                                />
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default AnalysisModal;
