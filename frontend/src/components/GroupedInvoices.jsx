import React, { useState, useEffect } from 'react';
import { ChevronDown, ChevronRight, Folder, FileText, Image, X } from 'lucide-react';
import { TransformWrapper, TransformComponent } from "react-zoom-pan-pinch";

const GroupedInvoices = () => {
    const [suppliers, setSuppliers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [expandedSupplier, setExpandedSupplier] = useState(null);
    const [viewingImage, setViewingImage] = useState(null); // Image URL for modal

    useEffect(() => {
        fetchHistory();
    }, []);

    const fetchHistory = async () => {
        try {
            const API_BASE_URL = window.location.hostname.includes('pharmagpt.co')
                ? 'https://api.pharmagpt.co'
                : 'http://localhost:8000';

            const res = await fetch(`${API_BASE_URL}/history`);
            const data = await res.json();
            if (Array.isArray(data)) {
                setSuppliers(data);
            } else {
                setSuppliers([]);
            }
        } catch (err) {
            console.error("Failed to fetch grouped history:", err);
        } finally {
            setLoading(false);
        }
    };

    const toggleSupplier = (name) => {
        if (expandedSupplier === name) {
            setExpandedSupplier(null);
        } else {
            setExpandedSupplier(name);
        }
    };

    if (loading) {
        return <div className="p-8 text-center text-slate-500">Loading Folders...</div>;
    }

    return (
        <div className="p-8 max-w-5xl mx-auto h-full overflow-y-auto">
            <h2 className="text-2xl font-bold text-slate-100 mb-6 flex items-center gap-2">
                <Folder className="w-6 h-6 text-blue-500" />
                Invoices by Supplier
            </h2>

            {/* Image Modal */}
            {viewingImage && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/90 backdrop-blur-sm animate-in fade-in duration-200" onClick={() => setViewingImage(null)}>
                    <button
                        onClick={() => setViewingImage(null)}
                        className="absolute top-4 right-4 p-2 bg-slate-800 rounded-full text-white hover:bg-slate-700 transition-colors z-50"
                    >
                        <X className="w-6 h-6" />
                    </button>
                    <div className="w-full max-w-5xl max-h-[90vh] flex items-center justify-center" onClick={(e) => e.stopPropagation()}>
                        <TransformWrapper>
                            {({ zoomIn, zoomOut, resetTransform }) => (
                                <div className="relative w-full h-full">
                                    <TransformComponent wrapperClass="w-full h-full flex items-center justify-center">
                                        <img
                                            src={window.location.hostname.includes('pharmagpt.co')
                                                ? `https://api.pharmagpt.co${viewingImage}`
                                                : `http://localhost:8000${viewingImage}`}
                                            alt="Invoice Preview"
                                            className="max-h-[85vh] w-auto rounded shadow-2xl"
                                        />
                                    </TransformComponent>
                                </div>
                            )}
                        </TransformWrapper>
                    </div>
                </div>
            )}

            <div className="space-y-4">
                {suppliers.length === 0 ? (
                    <div className="text-center text-slate-500 py-12">No invoices found.</div>
                ) : (
                    suppliers.map((supplier) => (
                        <div key={supplier.name} className="bg-slate-900/50 rounded-lg border border-slate-800 overflow-hidden shadow-sm hover:border-slate-700 transition-colors">
                            {/* Parent Row (Supplier) */}
                            <div
                                onClick={() => toggleSupplier(supplier.name)}
                                className="flex items-center justify-between p-4 cursor-pointer hover:bg-slate-800/50 transition-colors"
                            >
                                <div className="flex items-center gap-3">
                                    <div className={`p-2 rounded-full transition-colors ${expandedSupplier === supplier.name ? 'bg-blue-600/20 text-blue-400' : 'bg-slate-800 text-slate-500'}`}>
                                        {expandedSupplier === supplier.name ? <ChevronDown className="w-5 h-5" /> : <ChevronRight className="w-5 h-5" />}
                                    </div>
                                    <div>
                                        <h3 className="font-semibold text-slate-200 text-lg">{supplier.name}</h3>
                                        <p className="text-sm text-slate-500 flex items-center gap-1">
                                            <FileText className="w-3 h-3" /> {supplier.invoices.length} Invoices
                                        </p>
                                    </div>
                                </div>
                                <div className="text-right">
                                    <div className="text-sm font-medium text-slate-200">
                                        Total: <span className="text-emerald-400">₹{supplier.total_spend?.toLocaleString('en-IN', { minimumFractionDigits: 2 }) || '0.00'}</span>
                                    </div>
                                </div>
                            </div>

                            {/* Child Rows (Invoices) */}
                            {expandedSupplier === supplier.name && (
                                <div className="bg-slate-950/50 border-t border-slate-800 animate-in slide-in-from-top-2 duration-200">
                                    {/* Header Row */}
                                    <div className="grid grid-cols-12 gap-4 px-6 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-wider border-b border-slate-800/50">
                                        <div className="col-span-1">#</div>
                                        <div className="col-span-3">Invoice No</div>
                                        <div className="col-span-2">Date</div>
                                        <div className="col-span-3">Saved By</div>
                                        <div className="col-span-3 text-right">Amount</div>
                                    </div>

                                    {/* Invoice Rows */}
                                    {supplier.invoices.map((inv, index) => (
                                        <div key={inv.invoice_number} className="grid grid-cols-12 gap-4 px-6 py-3 border-b border-slate-800 last:border-0 hover:bg-slate-900/50 transition-colors items-center group">
                                            <div className="col-span-1 text-slate-600 text-sm font-mono">
                                                {supplier.invoices.length > 1 ? String(index + 1).padStart(2, '0') : ''}
                                            </div>

                                            <div className="col-span-3">
                                                <div className="font-mono text-slate-300 text-sm truncate" title={inv.invoice_number}>
                                                    {inv.invoice_number}
                                                </div>
                                            </div>

                                            <div className="col-span-2 text-slate-400 text-sm">
                                                {inv.date || '-'}
                                            </div>

                                            <div className="col-span-3">
                                                <div className="flex items-center gap-2">
                                                    <div className="w-5 h-5 rounded-full bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 flex items-center justify-center text-[9px] font-bold">
                                                        PG
                                                    </div>
                                                    <span className="text-sm text-slate-400">Pranav Gupta</span>
                                                </div>
                                            </div>

                                            <div className="col-span-3 flex items-center justify-end gap-4">
                                                <span className="font-medium text-slate-300 font-mono">
                                                    ₹{inv.total?.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                                                </span>

                                                {inv.image_path ? (
                                                    <button
                                                        onClick={(e) => { e.stopPropagation(); setViewingImage(inv.image_path); }}
                                                        className="p-1.5 text-slate-400 hover:text-blue-400 hover:bg-blue-500/10 rounded-lg transition-all opacity-100 sm:opacity-0 sm:group-hover:opacity-100"
                                                        title="View Original Invoice"
                                                    >
                                                        <Image className="w-4 h-4" />
                                                    </button>
                                                ) : (
                                                    <div className="w-7"></div>
                                                )}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    ))
                )}
            </div>
        </div>
    );
};

export default GroupedInvoices;
