import React, { useState, useEffect } from 'react';
import { FileText, Calendar, ZoomIn, ZoomOut, RotateCcw } from 'lucide-react';
import { TransformWrapper, TransformComponent } from "react-zoom-pan-pinch";

const History = () => {
    const [activityLog, setActivityLog] = useState([]);
    const [loading, setLoading] = useState(true);
    const [viewingInvoice, setViewingInvoice] = useState(null);
    const [modalLoading, setModalLoading] = useState(false);
    const [modalData, setModalData] = useState(null);

    useEffect(() => {
        fetchActivity();
    }, []);

    const fetchActivity = async () => {
        try {
            const API_BASE_URL = window.location.hostname.includes('pharmagpt.co')
                ? 'https://api.pharmagpt.co'
                : 'http://localhost:8000';

            const res = await fetch(`${API_BASE_URL}/activity-log`);
            const data = await res.json();
            if (Array.isArray(data)) {
                setActivityLog(data);
            } else {
                console.error("Activity API returned non-array:", data);
                setActivityLog([]);
            }
        } catch (err) {
            console.error("Failed to fetch activity log:", err);
        } finally {
            setLoading(false);
        }
    };

    const fetchInvoiceItems = async (invoiceNo) => {
        setViewingInvoice(invoiceNo);
        setModalLoading(true);
        setModalData(null);
        try {
            const API_BASE_URL = window.location.hostname.includes('pharmagpt.co')
                ? 'https://api.pharmagpt.co'
                : 'http://localhost:8000';

            const res = await fetch(`${API_BASE_URL}/invoices/${invoiceNo}/items`);
            if (res.ok) {
                const data = await res.json();
                setModalData(data.line_items || []);
            } else {
                console.error("Failed to fetch items");
            }
        } catch (e) {
            console.error(e);
        } finally {
            setModalLoading(false);
        }
    };

    if (loading) {
        return <div className="p-4 text-center text-slate-400">Loading Timeline...</div>;
    }

    return (
        <div className="p-4 h-[calc(100vh-80px)] overflow-y-auto pb-24 relative">
            <h2 className="text-xl font-bold text-slate-100 mb-6">Recent Activity</h2>

            {/* Modal Overlay */}
            {viewingInvoice && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
                    <div className="bg-slate-900 border border-slate-700 w-full max-w-4xl max-h-[80vh] rounded-xl flex flex-col shadow-2xl relative">
                        {/* Modal Header */}
                        <div className="p-4 border-b border-slate-700 flex justify-between items-center bg-slate-800/50 rounded-t-xl">
                            <div>
                                <h3 className="text-lg font-bold text-white">Invoice Items</h3>
                                <p className="text-xs text-slate-400 font-mono">#{viewingInvoice}</p>
                            </div>
                            <button
                                onClick={() => setViewingInvoice(null)}
                                className="p-2 hover:bg-slate-700 rounded-full transition-colors text-slate-400 hover:text-white"
                            >
                                ✕
                            </button>
                        </div>

                        {/* Modal Body */}
                        <div className="flex-1 overflow-auto p-4">
                            {modalLoading ? (
                                <div className="flex flex-col items-center justify-center h-40 text-slate-500 gap-2">
                                    <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
                                    <p className="text-sm">Loading details...</p>
                                </div>
                            ) : modalData && modalData.length > 0 ? (
                                <div className="overflow-x-auto rounded-lg border border-slate-700">
                                    <table className="w-full text-left text-sm">
                                        <thead className="bg-slate-800 text-slate-400 font-medium uppercase text-xs">
                                            <tr>
                                                <th className="p-3">Product</th>
                                                <th className="p-3 text-center">Qty</th>
                                                <th className="p-3 text-right">Rate</th>
                                                <th className="p-3 text-right">Amount</th>
                                                <th className="p-3 text-right">Batch</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-slate-700 bg-slate-900/50">
                                            {modalData.map((item, idx) => (
                                                <tr key={idx} className="hover:bg-slate-800/50 transition-colors">
                                                    <td className="p-3 font-medium text-slate-200">{item.product_name}</td>
                                                    <td className="p-3 text-center text-indigo-300 font-mono">{item.quantity}</td>
                                                    <td className="p-3 text-right text-slate-400 font-mono">₹{(item.landing_cost || 0).toFixed(2)}</td>
                                                    <td className="p-3 text-right text-emerald-400 font-mono font-bold">₹{(item.net_amount || 0).toFixed(2)}</td>
                                                    <td className="p-3 text-right text-xs text-slate-500 font-mono">{item.batch_no || "-"}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            ) : (
                                <div className="text-center py-10 text-slate-500">
                                    <p>No items found for this invoice.</p>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {/* Timeline List */}
            <div className="space-y-6">
                {activityLog.length === 0 ? (
                    <div className="text-center text-slate-500 py-10">No invoices found. Upload one to get started!</div>
                ) : (
                    activityLog.map((inv) => (
                        <div key={inv.invoice_number} className="bg-slate-800 rounded-xl overflow-hidden border border-slate-700 shadow-sm relative group">
                            <div className="flex flex-col md:flex-row">
                                {/* Image Preview Section (Left/Top) */}
                                {inv.image_path && (
                                    <div className="w-full md:w-48 h-48 md:h-auto bg-black/20 relative border-b md:border-b-0 md:border-r border-slate-700/50 flex flex-col justify-center">
                                        <TransformWrapper>
                                            {({ zoomIn, zoomOut, resetTransform }) => (
                                                <>
                                                    <TransformComponent wrapperClass="!w-full !h-full cursor-grab active:cursor-grabbing content-center">
                                                        <img
                                                            src={window.location.hostname.includes('pharmagpt.co')
                                                                ? `https://api.pharmagpt.co${inv.image_path}`
                                                                : `http://localhost:8000${inv.image_path}`}
                                                            alt="Invoice"
                                                            className="max-h-full max-w-full object-contain mx-auto"
                                                            loading="lazy"
                                                        />
                                                    </TransformComponent>
                                                    {/* Floating Controls */}
                                                    <div className="absolute bottom-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity bg-slate-900/80 rounded-lg p-1">
                                                        <button onClick={() => zoomIn()} className="p-1 hover:text-white text-slate-400"><ZoomIn className="w-3 h-3" /></button>
                                                        <button onClick={() => zoomOut()} className="p-1 hover:text-white text-slate-400"><ZoomOut className="w-3 h-3" /></button>
                                                        <button onClick={() => resetTransform()} className="p-1 hover:text-white text-slate-400"><RotateCcw className="w-3 h-3" /></button>
                                                    </div>
                                                </>
                                            )}
                                        </TransformWrapper>
                                    </div>
                                )}

                                {/* Content Section */}
                                <div className="flex-1 p-5 flex flex-col justify-between">
                                    <div>
                                        <div className="flex justify-between items-start mb-2">
                                            <div>
                                                <h3 className="font-bold text-lg text-white">{inv.supplier_name}</h3>
                                                <div className="flex items-center gap-2 text-sm text-slate-400 mt-1">
                                                    <span className="font-mono bg-slate-700/50 px-1.5 py-0.5 rounded text-slate-300">#{inv.invoice_number}</span>
                                                    <span>•</span>
                                                    <span className="flex items-center gap-1"><Calendar className="w-3 h-3" /> {inv.date}</span>
                                                </div>
                                            </div>
                                            <div className="text-right">
                                                <div className="text-xl font-bold text-emerald-400">₹{inv.total.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</div>
                                                <div className={`text-xs font-mono uppercase mt-1 px-2 py-0.5 rounded inline-block ${inv.status === 'CONFIRMED' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-yellow-500/10 text-yellow-500 border border-yellow-500/20'}`}>
                                                    {inv.status}
                                                </div>
                                            </div>
                                        </div>
                                    </div>

                                    <div className="mt-4 pt-4 border-t border-slate-700/50 flex justify-end">
                                        <button
                                            onClick={() => fetchInvoiceItems(inv.invoice_number)}
                                            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-medium transition-colors flex items-center gap-2 shadow-lg shadow-indigo-900/20"
                                        >
                                            <FileText className="w-4 h-4" /> View Line Items
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
};

export default History;
