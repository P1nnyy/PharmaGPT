import React, { useState, useEffect } from 'react';
import { ChevronDown, ChevronRight, Folder, FileText, Image, X, Trash2, AlertTriangle, Loader2 } from 'lucide-react';
import { TransformWrapper, TransformComponent } from "react-zoom-pan-pinch";
import { getInvoiceHistory, discardInvoice } from '../../services/api';
import { getImageUrl } from '../../utils/urlHelper';
import { useAuth } from '../../context/AuthContext';

const GroupedInvoices = () => {
    const { user } = useAuth();
    const [suppliers, setSuppliers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [expandedSupplier, setExpandedSupplier] = useState(null);
    const [viewingImage, setViewingImage] = useState(null); // Image URL for modal
    const [confirmDelete, setConfirmDelete] = useState(null); // {id, number, supplier}
    const [isDeleting, setIsDeleting] = useState(false);

    useEffect(() => {
        fetchHistory();
    }, []);

    const fetchHistory = async () => {
        try {
            const data = await getInvoiceHistory();
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

    const handleDelete = async (invoiceId, wipe = true) => {
        setIsDeleting(true);
        try {
            await discardInvoice(invoiceId, wipe);
            // Refresh list
            await fetchHistory();
            setConfirmDelete(null);
        } catch (err) {
            console.error("Failed to delete invoice:", err);
            alert("Failed to delete invoice. Please try again.");
        } finally {
            setIsDeleting(false);
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

    const getInitials = (name) => {
        if (!name || name === 'Unknown' || name === 'User') return '??';
        return name.split(' ').map(n => n ? n[0] : '').join('').substring(0, 2).toUpperCase();
    };

    const isAdmin = user?.role === 'Admin' || user?.shop_id === 'personal' || !user?.shop_id;

    return (
        <div className="p-8 max-w-5xl mx-auto h-full overflow-y-auto">
            <h2 className="text-2xl font-bold text-slate-100 mb-6 flex items-center gap-2">
                <Folder className="w-6 h-6 text-blue-500" />
                Invoices by Supplier
            </h2>

            {/* Delete Confirmation Modal */}
            {confirmDelete && (
                <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
                    <div className="bg-slate-900 border border-red-500/30 rounded-2xl p-6 max-w-md w-full shadow-2xl animate-in zoom-in-95 duration-200">
                        <div className="flex items-center gap-4 mb-4 text-red-500">
                            <div className="p-3 bg-red-500/10 rounded-full">
                                <AlertTriangle className="w-6 h-6" />
                            </div>
                            <h3 className="text-xl font-bold text-slate-100">Deep Wipe Invoice?</h3>
                        </div>
                        
                        <p className="text-slate-400 mb-6 leading-relaxed">
                            This will permanently delete invoice <span className="text-slate-200 font-mono">#{confirmDelete.number}</span> from <span className="text-slate-200 font-semibold">{confirmDelete.supplier}</span>.
                            <br /><br />
                            <span className="text-red-400 font-medium italic">Safety Warning:</span> This also wipes all associated line items and extracted data from your database. This action <b>cannot</b> be undone.
                        </p>

                        <div className="flex gap-3">
                            <button
                                disabled={isDeleting}
                                onClick={() => setConfirmDelete(null)}
                                className="flex-1 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg transition-colors font-medium disabled:opacity-50"
                            >
                                Cancel
                            </button>
                            <button
                                disabled={isDeleting}
                                onClick={() => handleDelete(confirmDelete.id, true)}
                                className="flex-1 px-4 py-2 bg-red-600 hover:bg-red-500 text-white rounded-lg transition-colors font-bold flex items-center justify-center gap-2 disabled:opacity-50"
                            >
                                {isDeleting ? (
                                    <>
                                        <Loader2 className="w-4 h-4 animate-spin" />
                                        Wiping...
                                    </>
                                ) : (
                                    <>
                                        <Trash2 className="w-4 h-4" />
                                        Confirm Wipe
                                    </>
                                )}
                            </button>
                        </div>
                    </div>
                </div>
            )}

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
                                            src={getImageUrl(viewingImage)}
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
                {suppliers && suppliers.length === 0 ? (
                    <div className="text-center text-slate-500 py-12">No invoices found.</div>
                ) : (
                    suppliers && suppliers.map((supplier) => supplier && (
                        <div key={supplier.name || Math.random()} className="bg-slate-900/50 rounded-lg border border-slate-800 overflow-hidden shadow-sm hover:border-slate-700 transition-colors">
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
                                            <FileText className="w-3 h-3" /> {supplier.invoices?.length || 0} Invoices
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
                                    {/* Mobile View (Card Layout) */}
                                    <div className="md:hidden">
                                        {supplier.invoices && supplier.invoices.map((inv, index) => inv && inv.id && (
                                            <div key={inv.invoice_number} className="p-4 border-b border-slate-800 last:border-0 hover:bg-slate-900/50 transition-colors">
                                                <div className="flex justify-between items-start mb-2">
                                                    <div className="flex flex-col">
                                                        <span className="text-xs text-slate-500 font-mono mb-1">
                                                            #{inv.invoice_number}
                                                        </span>
                                                        <span className="text-sm text-slate-300">
                                                            {inv.date || '-'}
                                                        </span>
                                                    </div>
                                                    <div className="flex flex-col items-end">
                                                        <span className="font-medium text-emerald-400 font-mono text-base">
                                                            ₹{inv.total?.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                                                        </span>
                                                    </div>
                                                </div>

                                                <div className="flex justify-between items-center mt-3 pt-3 border-t border-slate-800/50">
                                                    <div className="flex items-center gap-2">
                                                        <div className="w-5 h-5 rounded-full bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 flex items-center justify-center text-[9px] font-bold">
                                                            {getInitials(inv?.saved_by)}
                                                        </div>
                                                        <span className="text-xs text-slate-400">{inv?.saved_by || 'Unknown'}</span>
                                                    </div>

                                                    <div className="flex items-center gap-2">
                                                        {inv.image_path && (
                                                            <button
                                                                onClick={(e) => { e.stopPropagation(); setViewingImage(inv.image_path); }}
                                                                className="flex items-center gap-1.5 px-2 py-1 bg-slate-800 hover:bg-slate-700 rounded text-xs text-blue-400 transition-colors"
                                                            >
                                                                <Image className="w-3 h-3" /> View Source
                                                            </button>
                                                        )}
                                                        {isAdmin && (
                                                            <button
                                                                onClick={(e) => { e.stopPropagation(); setConfirmDelete({ id: inv.id, number: inv.invoice_number, supplier: supplier.name }); }}
                                                                className="p-1 px-2 bg-red-500/10 hover:bg-red-500/20 text-red-400 rounded transition-colors"
                                                            >
                                                                <Trash2 className="w-3.5 h-3.5" />
                                                            </button>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>
                                        ))}
                                    </div>

                                    {/* Desktop View (Grid Layout) */}
                                    <div className="hidden md:grid grid-cols-12 gap-4 px-6 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-wider border-b border-slate-800/50">
                                        <div className="col-span-1">#</div>
                                        <div className="col-span-3">Invoice No</div>
                                        <div className="col-span-2">Date</div>
                                        <div className="col-span-2">Saved By</div>
                                        <div className="col-span-4 text-right">Amount / Actions</div>
                                    </div>

                                    <div className="hidden md:block">
                                        {supplier.invoices && supplier.invoices.map((inv, index) => inv && inv.id && (
                                            <div key={inv.invoice_number} className="grid grid-cols-12 gap-4 px-6 py-3 border-b border-slate-800 last:border-0 hover:bg-slate-900/50 transition-colors items-center group">
                                                <div className="col-span-1 text-slate-600 text-sm font-mono">
                                                    {supplier.invoices?.length > 1 ? String(index + 1).padStart(2, '0') : ''}
                                                </div>

                                                <div className="col-span-3">
                                                    <div className="font-mono text-slate-300 text-sm truncate" title={inv.invoice_number}>
                                                        {inv.invoice_number}
                                                    </div>
                                                </div>

                                                <div className="col-span-2 text-slate-400 text-sm">
                                                    {inv.date || '-'}
                                                </div>

                                                <div className="col-span-2">
                                                    <div className="flex items-center gap-2">
                                                        <div className="w-5 h-5 rounded-full bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 flex items-center justify-center text-[9px] font-bold">
                                                            {getInitials(inv?.saved_by)}
                                                        </div>
                                                        <span className="text-sm text-slate-400 truncate">{inv?.saved_by || 'Unknown'}</span>
                                                    </div>
                                                </div>

                                                <div className="col-span-4 flex items-center justify-end gap-3 text-right">
                                                    <span className="font-medium text-slate-300 font-mono">
                                                        ₹{inv.total?.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                                                    </span>

                                                    <div className="flex items-center gap-1 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity">
                                                        {inv.image_path && (
                                                            <button
                                                                onClick={(e) => { e.stopPropagation(); setViewingImage(inv.image_path); }}
                                                                className="p-1.5 text-slate-400 hover:text-blue-400 hover:bg-blue-500/10 rounded-lg transition-all"
                                                                title="View Original Invoice"
                                                            >
                                                                <Image className="w-4 h-4" />
                                                            </button>
                                                        )}
                                                        {isAdmin && (
                                                            <button
                                                                onClick={(e) => { e.stopPropagation(); setConfirmDelete({ id: inv.id, number: inv.invoice_number, supplier: supplier.name }); }}
                                                                className="p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-500/10 rounded-lg transition-all"
                                                                title="Permanently Wipe Invoice"
                                                            >
                                                                <Trash2 className="w-4 h-4" />
                                                            </button>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
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
