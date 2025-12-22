import React, { useState, useEffect } from 'react';
import { Package, Calendar, FileText, ChevronDown, ChevronUp, Phone, MapPin } from 'lucide-react';

const History = () => {
    const [suppliers, setSuppliers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [expandedSupplier, setExpandedSupplier] = useState(null);

    useEffect(() => {
        fetchHistory();
    }, []);

    const fetchHistory = async () => {
        try {
            // In production, use the actual API URL
            const API_BASE_URL = window.location.hostname.includes('pharmagpt.co')
                ? 'https://api.pharmagpt.co'
                : 'http://localhost:8000';

            const res = await fetch(`${API_BASE_URL}/history`);
            const data = await res.json();
            if (Array.isArray(data)) {
                setSuppliers(data);
            } else {
                console.error("History API returned non-array:", data);
                setSuppliers([]); // Fallback to empty to prevent crash
            }
        } catch (err) {
            console.error("Failed to fetch history:", err);
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
        return <div className="p-4 text-center text-slate-400">Loading History...</div>;
    }

    return (
        <div className="p-4 h-[calc(100vh-80px)] overflow-y-auto pb-24">
            <h2 className="text-xl font-bold text-slate-100 mb-4">Supplier History</h2>

            <div className="space-y-3">
                {suppliers.map((supplier) => (
                    <div key={supplier.name} className="bg-slate-800 rounded-xl overflow-hidden border border-slate-700">
                        {/* Header */}
                        <div
                            onClick={() => toggleSupplier(supplier.name)}
                            className="p-4 flex items-center justify-between cursor-pointer hover:bg-slate-750 transition-colors"
                        >
                            <div>
                                <h3 className="text-lg font-semibold text-white">{supplier.name}</h3>
                                <div className="flex items-center gap-3 mt-1 text-sm text-slate-400">
                                    <span className="flex items-center gap-1">
                                        <FileText className="w-3 h-3" /> {supplier.invoices.length} Invoices
                                    </span>
                                    {supplier.phone && (
                                        <span className="flex items-center gap-1">
                                            <Phone className="w-3 h-3" /> {supplier.phone}
                                        </span>
                                    )}
                                </div>
                                {/* GST Badge */}
                                {supplier.gst && (
                                    <div className="mt-2 inline-block px-2 py-0.5 bg-slate-900 border border-slate-700 rounded text-xs text-slate-500 font-mono">
                                        GST: {supplier.gst}
                                    </div>
                                )}
                            </div>

                            {expandedSupplier === supplier.name ? <ChevronUp className="text-indigo-400" /> : <ChevronDown className="text-slate-500" />}
                        </div>

                        {/* Expanded Body */}
                        {expandedSupplier === supplier.name && (
                            <div className="bg-slate-900/50 p-3 space-y-2 border-t border-slate-700">
                                {supplier.invoices.map((inv) => (
                                    <div key={inv.invoice_number} className="bg-slate-800 p-3 rounded-lg border border-slate-700/50 flex justify-between items-center">
                                        <div>
                                            <div className="flex items-center gap-2">
                                                <span className="text-indigo-300 font-medium">{inv.invoice_number}</span>
                                                <span className={`text-[10px] px-1.5 py-0.5 rounded border ${inv.status === 'CONFIRMED' ? 'border-emerald-500/30 text-emerald-400 bg-emerald-500/10' : 'border-slate-600 text-slate-400'}`}>
                                                    {inv.status}
                                                </span>
                                            </div>
                                            <div className="text-xs text-slate-500 mt-1 flex items-center gap-2">
                                                <Calendar className="w-3 h-3" /> {inv.date || "No Date"}
                                            </div>
                                        </div>
                                        <div className="text-right">
                                            <div className="text-slate-200 font-bold">₹{inv.total?.toFixed(2)}</div>
                                        </div>
                                    </div>
                                ))}

                                {(!supplier.gst || !supplier.phone) && (
                                    <div className="hidden"></div>
                                )}
                            </div>
                        )}
                    </div>
                ))}
            </div>
        </div>
    );
};

export default History;
