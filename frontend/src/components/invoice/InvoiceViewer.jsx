import React, { useState, useEffect, useRef } from 'react';
import { FileText, Upload, Loader2, RefreshCw, MoreVertical, Trash2 } from 'lucide-react';
import { TransformWrapper, TransformComponent } from "react-zoom-pan-pinch";

const InvoiceViewer = ({
    fileQueue = [],
    selectedQueueId,
    onQueueSelect,
    onFileChange,
    onReset,
    onDiscard
}) => {
    // Derived active state
    const activeItem = fileQueue.find(item => item.id === selectedQueueId) || fileQueue[0];
    const previewUrl = activeItem?.previewUrl;
    const isAnalyzing = fileQueue.some(f => f.status === 'processing');

    const [menuOpenId, setMenuOpenId] = useState(null);
    const menuRef = useRef(null);

    // Close menu when clicking outside
    useEffect(() => {
        const handleClickOutside = (event) => {
            if (menuRef.current && !menuRef.current.contains(event.target)) {
                setMenuOpenId(null);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    return (
        <div className="flex flex-row h-full bg-gray-950 border-r border-gray-800">

            {/* LEFT SIDEBAR: BATCH LIST (Only if queue exists) */}
            {fileQueue.length > 0 && (
                <div className="w-16 md:w-64 border-r border-gray-800 flex flex-col bg-gray-900/30 overflow-y-auto">
                    <div className="p-3 text-xs font-bold text-gray-500 uppercase tracking-widest sticky top-0 bg-gray-950/90 backdrop-blur-sm z-10">
                        Queue ({fileQueue.length})
                    </div>

                    <div className="flex-1 space-y-1 p-2">
                        {fileQueue.map((item) => (
                            <button
                                key={item.id}
                                onClick={() => onQueueSelect && onQueueSelect(item.id)}
                                className={`w-full text-left p-2 rounded-lg flex items-center gap-3 transition-all relative overflow-hidden group
                                    ${item.id === selectedQueueId ? 'bg-indigo-500/20 ring-1 ring-indigo-500/50' : 'hover:bg-gray-800'}
                                `}
                            >
                                {/* Thumbnail */}
                                <div className="w-8 h-8 md:w-10 md:h-10 rounded bg-gray-800 flex-shrink-0 bg-cover bg-center border border-gray-700"
                                    style={{ backgroundImage: `url(${item.previewUrl})` }}>
                                </div>

                                {/* Info (Desktop) */}
                                <div className="hidden md:block flex-1 min-w-0">
                                    <div className={`text-sm font-medium truncate ${item.id === selectedQueueId ? 'text-indigo-300' : 'text-gray-300'}`}>
                                        {item.file.name}
                                    </div>
                                    <div className="text-[10px] text-gray-500 flex items-center gap-1">
                                        {item.status === 'processing' && <span className="text-yellow-500">Processing...</span>}
                                        {item.status === 'completed' && <span className="text-green-500">Done</span>}
                                        {item.status === 'duplicate' && <span className="text-amber-500 font-bold">Duplicate</span>}
                                        {item.status === 'error' && <span className="text-red-500">Failed</span>}
                                    </div>
                                </div>

                                {/* STATUS ICON ANCHORED RIGHT */}
                                <div className="absolute right-2 md:static">
                                    {item.status === 'processing' && <Loader2 className="w-4 h-4 text-indigo-400 animate-spin" />}
                                    {item.status === 'completed' && (
                                        <div className="bg-green-500/20 p-1 rounded-full">
                                            <svg className="w-4 h-4 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                                            </svg>
                                        </div>
                                    )}
                                    {item.status === 'duplicate' && (
                                        <div className="bg-amber-500/20 p-1 rounded-full group mx-1 relative">
                                            {/* Icon */}
                                            <svg className="w-4 h-4 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                                            </svg>

                                            {/* Tooltip for Duplicate Message */}
                                            <div className="absolute right-0 top-6 w-48 bg-gray-900 text-amber-400 text-[10px] p-2 rounded shadow-xl border border-gray-700 opacity-0 group-hover:opacity-100 transition-opacity z-50 pointer-events-none">
                                                {item.warning || "Duplicate Invoice Detected"}
                                            </div>
                                        </div>
                                    )}
                                    {item.status === 'error' && (
                                        <div className="bg-red-500/20 p-1 rounded-full">
                                            <svg className="w-4 h-4 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                            </svg>
                                        </div>
                                    )}

                                    {/* 3-DOTS MENU */}
                                    <div className="relative ml-2" ref={menuOpenId === item.id ? menuRef : null}>
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                setMenuOpenId(menuOpenId === item.id ? null : item.id);
                                            }}
                                            className="p-1 hover:bg-gray-700 rounded-full text-gray-400 hover:text-white transition-colors"
                                        >
                                            <MoreVertical className="w-4 h-4" />
                                        </button>

                                        {/* Dropdown */}
                                        {menuOpenId === item.id && (
                                            <div className="absolute right-0 top-6 w-32 bg-gray-900 border border-gray-700 rounded-lg shadow-xl z-50 overflow-hidden">
                                                <button
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        onDiscard(item.id);
                                                        setMenuOpenId(null);
                                                    }}
                                                    className="w-full text-left px-3 py-2 text-xs font-medium text-red-400 hover:bg-gray-800 flex items-center gap-2"
                                                >
                                                    <Trash2 className="w-3 h-3" />
                                                    Discard
                                                </button>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </button>
                        ))}
                    </div>

                    {/* Add More Button */}
                    <div className="p-2 border-t border-gray-800">
                        <label className="flex items-center justify-center gap-2 w-full p-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-400 text-xs cursor-pointer transition-colors">
                            <Upload className="w-3 h-3" />
                            <span className="hidden md:inline">Add More</span>
                            <input type="file" multiple className="hidden" accept="image/*" onChange={onFileChange} />
                        </label>
                    </div>
                </div>
            )}

            {/* MAIN PREVIEW AREA */}
            <div className="flex-1 flex flex-col relative">
                {/* Header */}
                <div className="p-3 md:p-4 border-b border-gray-800 flex justify-between items-center bg-gray-900/50 backdrop-blur-sm sticky top-0 z-10 w-full">
                    <h2 className="text-sm md:text-xl font-bold flex items-center gap-2 text-indigo-400">
                        <FileText className="w-4 h-4 md:w-6 md:h-6" />
                        <span className="hidden sm:inline">Source Invoice</span>
                        <span className="sm:hidden">Invoice</span>
                    </h2>
                    {fileQueue.length > 0 && (
                        <button
                            onClick={onReset}
                            className="flex items-center gap-1 text-[10px] md:text-sm text-gray-400 hover:text-white transition-colors bg-gray-800 px-2 py-1 md:px-3 md:py-1.5 rounded-full"
                        >
                            <RefreshCw className="w-3 h-3" /> Clear All
                        </button>
                    )}
                </div>

                {/* Content */}
                <div className="flex-1 flex items-center justify-center overflow-hidden relative bg-black/20">
                    {previewUrl ? (
                        <div className="relative w-full h-full flex items-center justify-center p-4">
                            <TransformWrapper
                                initialScale={1}
                                minScale={0.5}
                                maxScale={4}
                                centerOnInit={true}
                                wheel={{ step: 0.2 }} // Faster zoom on mouse wheel
                            >
                                <TransformComponent wrapperClass="w-full h-full" contentClass="w-full h-full flex items-center justify-center">
                                    <img
                                        src={previewUrl}
                                        alt="Invoice Preview"
                                        className="max-w-full max-h-full object-contain shadow-2xl"
                                        onError={(e) => {
                                            e.target.onerror = null;
                                            e.target.src = "https://placehold.co/600x800?text=Image+Not+Found";
                                        }}
                                    />
                                </TransformComponent>
                            </TransformWrapper>
                        </div>
                    ) : (
                        <label className="flex flex-col items-center justify-center w-full h-full border-2 border-dashed border-gray-800 rounded-xl cursor-pointer hover:bg-gray-900/50 hover:border-indigo-500/50 transition-all group m-4">
                            <div className="bg-gray-900 p-4 rounded-full mb-4 group-hover:scale-110 transition-transform shadow-lg">
                                <Upload className="w-8 h-8 md:w-12 md:h-12 text-indigo-500" />
                            </div>
                            <p className="text-gray-400 font-medium text-sm md:text-base text-center px-4">
                                Tap to upload Invoices (Batch Supported)
                            </p>
                            <span className="text-xs text-gray-600 mt-2">Supports JPG, PNG (Select Multiple)</span>
                            <input type="file" multiple className="hidden" accept="image/*" onChange={onFileChange} />
                        </label>
                    )}

                    {/* Global Loading Overlay (Only if current item is processing?) 
                        Actually, backend is sequential, so the whole batch processes. 
                        Let's show overlay IF the current active item is processing OR just show global status in Sidebar?
                        User asked for "Green Tick" so viewing the list is important.
                        Let's remove the FULL SCREEN blocking loader so user can browse list while processing.
                    */}
                    {/* 
                    {isAnalyzing && (
                        <div className="absolute inset-0 bg-black/80 backdrop-blur-sm flex flex-col items-center justify-center z-20">
                           ...
                        </div>
                    )}
                    */}
                </div>
            </div>
        </div>
    );
};

export default InvoiceViewer;
