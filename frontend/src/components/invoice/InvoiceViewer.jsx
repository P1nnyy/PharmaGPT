import React, { useState, useEffect, useRef } from 'react';
import { FileText, Upload, Loader2, RefreshCw, MoreVertical, Trash2 } from 'lucide-react';
import { TransformWrapper, TransformComponent } from "react-zoom-pan-pinch";

const InvoiceViewer = ({
    fileQueue = [],
    selectedQueueId,
    onQueueSelect,
    onFileChange,
    onReset,
    onDiscard,
    isMobile,
    previewUrl: directPreviewUrl // Accept optional direct URL
}) => {
    // Derived active state
    const activeItem = fileQueue.find(item => item.id === selectedQueueId) || fileQueue[0];
    const previewUrl = directPreviewUrl || activeItem?.previewUrl; // Prioritize direct prop
    const isAnalyzing = fileQueue.some(f => f.status === 'processing');

    const [menuOpenId, setMenuOpenId] = useState(null);
    const [isListOpen, setIsListOpen] = useState(false);
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

    const handleQueueItemClick = (id) => {
        if (onQueueSelect) onQueueSelect(id);
        if (isMobile) setIsListOpen(false); // Auto-close on mobile selection
    };

    return (
        <div className="flex flex-row h-full bg-gray-950 border-r border-gray-800 relative">

            {/* LEFT SIDEBAR: BATCH LIST */}
            {fileQueue.length > 0 && (
                <div className={`
                    border-r border-gray-800 flex flex-col bg-gray-900/95 backdrop-blur-sm overflow-y-auto transition-all z-20
                    ${isMobile ? 'absolute inset-0 w-full' : 'w-16 md:w-64 relative'}
                    ${isMobile && !isListOpen ? 'hidden' : 'flex'}
                `}>
                    <div className="p-3 text-xs font-bold text-gray-500 uppercase tracking-widest sticky top-0 bg-gray-950/90 backdrop-blur-sm z-10 flex justify-between items-center">
                        <span>Queue ({fileQueue.length})</span>
                        {isMobile && (
                            <button onClick={() => setIsListOpen(false)} className="p-1 hover:bg-gray-800 rounded">
                                <span className="sr-only">Close</span>
                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                            </button>
                        )}
                    </div>

                    <div className="flex-1 space-y-1 p-2">
                        {fileQueue.map((item) => (
                            <div
                                key={item.id}
                                onClick={() => handleQueueItemClick(item.id)}
                                className={`w-full text-left p-2 rounded-lg flex items-center gap-3 transition-all relative overflow-hidden group cursor-pointer
                                    ${item.id === selectedQueueId ? 'bg-indigo-500/20 ring-1 ring-indigo-500/50' : 'hover:bg-gray-800'}
                                `}
                            >
                                {/* Thumbnail */}
                                <div className="w-8 h-8 md:w-10 md:h-10 rounded bg-gray-800 flex-shrink-0 bg-cover bg-center border border-gray-700"
                                    style={{ backgroundImage: `url(${item.previewUrl})` }}>
                                </div>

                                {/* Info (Desktop or Mobile List Mode) */}
                                <div className={`${isMobile ? 'block' : 'hidden md:block'} flex-1 min-w-0`}>
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

                                {/* STATUS ICON */}
                                <div className="absolute right-2 top-2 md:static md:right-auto md:top-auto flex flex-col items-end gap-2 md:block">
                                    {item.status === 'processing' && (
                                        <div className="bg-black/60 p-1.5 rounded-full backdrop-blur-sm shadow-md">
                                            <Loader2 className="w-4 h-4 text-indigo-400 animate-spin" />
                                        </div>
                                    )}
                                    {item.status === 'completed' && (
                                        <div className="bg-green-500/20 md:bg-transparent p-1 rounded-full drop-shadow-md">
                                            <div className="bg-green-500 p-1 rounded-full shadow-lg">
                                                <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                                                </svg>
                                            </div>
                                        </div>
                                    )}
                                    {item.status === 'duplicate' && (
                                        <div className="bg-black/70 p-1.5 rounded-full group mx-1 relative backdrop-blur-md shadow-lg border border-amber-500/50">
                                            <svg className="w-4 h-4 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                                            </svg>
                                        </div>
                                    )}
                                    {item.status === 'error' && (
                                        <div className="bg-red-500/20 p-1 rounded-full backdrop-blur-sm">
                                            <div className="bg-red-500 p-1 rounded-full shadow-lg">
                                                <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                                </svg>
                                            </div>
                                        </div>
                                    )}

                                    {/* 3-DOTS MENU */}
                                    <div className="relative mt-1" ref={menuOpenId === item.id ? menuRef : null}>
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                setMenuOpenId(menuOpenId === item.id ? null : item.id);
                                            }}
                                            className="p-1.5 bg-black/60 hover:bg-black/90 rounded-full text-white shadow-lg backdrop-blur-sm border border-white/10 transition-all"
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
                            </div>
                        ))}
                    </div>

                    {/* Add More Button */}
                    <div className="p-2 border-t border-gray-800">
                        <label className="flex items-center justify-center gap-2 w-full p-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-400 text-xs cursor-pointer transition-colors">
                            <Upload className="w-3 h-3" />
                            <span className={`${isMobile ? 'inline' : 'hidden md:inline'}`}>Add More</span>
                            <input type="file" multiple className="hidden" accept="image/*" onChange={onFileChange} />
                        </label>
                    </div>
                </div>
            )}

            {/* MAIN PREVIEW AREA */}
            <div className="flex-1 flex flex-col relative">
                {/* Header */}
                <div className="p-3 md:p-4 border-b border-gray-800 flex justify-between items-center bg-gray-900/50 backdrop-blur-sm sticky top-0 z-10 w-full">
                    <div className="flex items-center gap-3">
                        {isMobile && fileQueue.length > 0 && (
                            <button
                                onClick={() => setIsListOpen(true)}
                                className="p-1.5 bg-gray-800 rounded-lg text-gray-300 hover:bg-gray-700 relative"
                            >
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" /></svg>
                                <span className="absolute -top-1 -right-1 w-4 h-4 bg-indigo-500 rounded-full text-[9px] flex items-center justify-center text-white font-bold">{fileQueue.length}</span>
                            </button>
                        )}
                        <h2 className="text-sm md:text-xl font-bold flex items-center gap-2 text-indigo-400">
                            <FileText className="w-4 h-4 md:w-6 md:h-6" />
                            {!isMobile && <span>Source Invoice</span>}
                        </h2>
                    </div>

                    {fileQueue.length > 0 && (
                        <button
                            onClick={onReset}
                            className="flex items-center gap-1 text-[10px] md:text-sm text-gray-400 hover:text-white transition-colors bg-gray-800 px-3 py-1.5 rounded-full border border-gray-700 shadow-sm active:bg-gray-700"
                        >
                            <RefreshCw className="w-3 h-3" />
                            <span>Clear All</span>
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
                                wheel={{ step: 0.2 }}
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
                                Tap to upload Invoices
                            </p>
                            <input type="file" multiple className="hidden" accept="image/*" onChange={onFileChange} />
                        </label>
                    )}
                </div>
            </div>
        </div>
    );
};

export default InvoiceViewer;


