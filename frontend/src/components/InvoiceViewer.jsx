import React from 'react';
import { FileText, Upload, Loader2, RefreshCw } from 'lucide-react';

const InvoiceViewer = ({ file, previewUrl, isAnalyzing, onFileChange, onReset }) => {
    return (
        <div className="flex flex-col h-full bg-gray-950 border-r border-gray-800">
            {/* Header */}
            <div className="p-3 md:p-4 border-b border-gray-800 flex justify-between items-center bg-gray-900/50 backdrop-blur-sm sticky top-0 z-10">
                <h2 className="text-sm md:text-xl font-bold flex items-center gap-2 text-indigo-400">
                    <FileText className="w-4 h-4 md:w-6 md:h-6" />
                    <span className="hidden sm:inline">Source Invoice</span>
                    <span className="sm:hidden">Invoice</span>
                </h2>
                {file && (
                    <button
                        onClick={onReset}
                        className="flex items-center gap-1 text-[10px] md:text-sm text-gray-400 hover:text-white transition-colors bg-gray-800 px-2 py-1 md:px-3 md:py-1.5 rounded-full"
                    >
                        <RefreshCw className="w-3 h-3" /> New
                    </button>
                )}
            </div>

            {/* Content */}
            <div className="flex-1 flex items-center justify-center p-2 md:p-6 overflow-hidden relative">
                {previewUrl ? (
                    <div className="relative w-full h-full flex items-center justify-center group">
                        {/* Image Container with Zoom hint could go here later */}
                        <img
                            src={previewUrl}
                            alt="Invoice Preview"
                            className="max-w-full max-h-full object-contain shadow-2xl rounded-lg border border-gray-800 transition-transform duration-300"
                        />
                    </div>
                ) : (
                    <label className="flex flex-col items-center justify-center w-full h-full border-2 border-dashed border-gray-800 rounded-xl cursor-pointer hover:bg-gray-900/50 hover:border-indigo-500/50 transition-all group">
                        <div className="bg-gray-900 p-4 rounded-full mb-4 group-hover:scale-110 transition-transform shadow-lg">
                            <Upload className="w-8 h-8 md:w-12 md:h-12 text-indigo-500" />
                        </div>
                        <p className="text-gray-400 font-medium text-sm md:text-base text-center px-4">
                            Tap to upload Invoice
                        </p>
                        <span className="text-xs text-gray-600 mt-2">Supports JPG, PNG</span>
                        <input type="file" className="hidden" accept="image/*" onChange={onFileChange} />
                    </label>
                )}

                {/* Loading Overlay */}
                {isAnalyzing && (
                    <div className="absolute inset-0 bg-black/80 backdrop-blur-sm flex flex-col items-center justify-center z-20">
                        <div className="relative">
                            <div className="absolute inset-0 bg-indigo-500/20 blur-xl rounded-full"></div>
                            <Loader2 className="relative w-16 h-16 text-indigo-500 animate-spin mb-4" />
                        </div>
                        <p className="text-lg md:text-xl font-medium text-white animate-pulse">Extracting Data...</p>
                        <p className="text-sm text-indigo-400 mt-2">AI Agents are reading the invoice</p>
                    </div>
                )}
            </div>
        </div>
    );
};

export default InvoiceViewer;
