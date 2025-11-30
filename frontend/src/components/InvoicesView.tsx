import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { LayoutGrid, List, Search, Calendar, Package, Trash2, Check, Lock, AlertCircle, RefreshCw, X, ListFilter } from 'lucide-react';

// --- Types ---

interface InvoiceItem {
    product_name: string;
    batch_number: string;
    expiry_date: string;
    quantity?: number;
    quantity_packs?: number;
    pack_size: number;
    mrp: number;
    rate?: number;
    buy_price?: number;
    manufacturer: string;
    dosage_form: string;
}

interface Invoice {
    id: string;
    filename: string;
    image_url: string;
    upload_date: string;
    invoice_date?: string;
    net_amount?: number;
    supplier?: string;
    items: InvoiceItem[];
}

// --- Error Boundary ---

class ModalErrorBoundary extends React.Component<{ children: React.ReactNode }, { hasError: boolean }> {
    constructor(props: any) {
        super(props);
        this.state = { hasError: false };
    }

    static getDerivedStateFromError() {
        return { hasError: true };
    }

    componentDidCatch(error: any, errorInfo: any) {
        console.error("Modal Error:", error, errorInfo);
    }

    render() {
        if (this.state.hasError) {
            return (
                <div className="flex flex-col items-center justify-center h-full text-red-400 p-8 text-center">
                    <AlertCircle size={48} className="mb-4" />
                    <h3 className="text-xl font-bold mb-2">Display Error</h3>
                    <p>Something went wrong while rendering this invoice.</p>
                </div>
            );
        }
        return this.props.children;
    }
}

// --- Helper Components ---

const InvoiceDetailModal: React.FC<{ invoice: Invoice; onClose: () => void }> = ({ invoice, onClose }) => {
    // Defensive Data Preparation
    const safeItems = (invoice.items || []).map((item, idx) => {
        if (!item) return null;

        // Safely extract numbers
        const qty = Number(item.quantity) || Number(item.quantity_packs) || 0;
        const mrp = Number(item.mrp) || 0;
        const rate = Number(item.rate) || Number(item.buy_price) || mrp; // Fallback to MRP if rate/buy_price missing

        return {
            id: idx,
            productName: String(item.product_name || "Unknown Product"),
            batch: String(item.batch_number || "N/A"),
            expiry: String(item.expiry_date || "N/A"),
            mfr: String(item.manufacturer || "N/A"),
            qty,
            mrp,
            rate,
            total: qty * rate
        };
    }).filter((item): item is NonNullable<typeof item> => item !== null);

    const calculatedTotal = safeItems.reduce((acc, item) => acc + item.total, 0);
    const netAmount = invoice.net_amount !== undefined && invoice.net_amount !== null ? Number(invoice.net_amount) : null;
    const uploadDate = invoice.upload_date ? String(invoice.upload_date) : "N/A";
    const invoiceId = invoice.id ? String(invoice.id) : "Unknown ID";

    return (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 md:p-8" onClick={onClose}>
            <div
                className="bg-[#1a1a1a] border border-white/10 rounded-2xl w-full max-w-6xl h-[90vh] flex flex-col md:flex-row overflow-hidden shadow-2xl"
                onClick={e => e.stopPropagation()}
            >
                <ModalErrorBoundary>
                    {/* Left: Image Section */}
                    <div className="w-full md:w-1/2 bg-black flex items-center justify-center border-b md:border-b-0 md:border-r border-white/10 p-4 relative group">
                        {invoice.image_url ? (
                            <img
                                src={invoice.image_url}
                                alt="Invoice"
                                className="max-w-full max-h-full object-contain"
                                onError={(e) => {
                                    (e.target as HTMLImageElement).style.display = 'none';
                                    (e.target as HTMLImageElement).parentElement!.innerHTML = '<div class="text-gray-500">Image Load Failed</div>';
                                }}
                            />
                        ) : (
                            <div className="text-gray-500">No Image Available</div>
                        )}
                        <div className="absolute top-4 left-4 bg-black/60 backdrop-blur px-3 py-1 rounded-full text-xs text-white">
                            {safeItems.length} Items Extracted
                        </div>
                    </div>

                    {/* Right: Details Section */}
                    <div className="w-full md:w-1/2 flex flex-col h-full bg-[#1a1a1a]">
                        {/* Header */}
                        <div className="p-6 border-b border-white/10 flex justify-between items-start bg-[#222]">
                            <div>
                                <h2 className="text-2xl font-bold text-white mb-1">Invoice Details</h2>
                                <div className="flex flex-col gap-1 text-sm text-gray-400">
                                    <span>ID: <span className="font-mono text-gray-300">{invoiceId}</span></span>
                                    <span>Uploaded: <span className="text-gray-300">{uploadDate}</span></span>
                                </div>
                            </div>
                            <button
                                onClick={onClose}
                                className="p-2 hover:bg-white/10 rounded-full transition-colors text-gray-400 hover:text-white"
                            >
                                <X size={24} />
                            </button>
                        </div>

                        {/* Scrollable Items List */}
                        <div className="flex-1 overflow-y-auto p-6 custom-scrollbar">
                            <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-4 sticky top-0 bg-[#1a1a1a] py-2 z-10">
                                Extracted Line Items
                            </h3>
                            <div className="space-y-3">
                                {safeItems.length === 0 ? (
                                    <div className="text-center py-10 text-gray-500 border border-dashed border-white/10 rounded-lg">
                                        No items extracted from this invoice.
                                    </div>
                                ) : (
                                    safeItems.map((item) => (
                                        <div key={item.id} className="bg-white/5 rounded-lg p-4 border border-white/5 hover:border-white/10 transition-colors">
                                            <div className="flex justify-between items-start mb-3">
                                                <h4 className="font-medium text-white text-lg leading-tight">{item.productName}</h4>
                                                <div className="text-right ml-4 flex-shrink-0">
                                                    <div className="font-bold text-green-400 text-lg">
                                                        ₹{item.total.toFixed(2)}
                                                    </div>
                                                    <div className="text-xs text-gray-500">
                                                        ₹{item.rate.toFixed(2)} × {item.qty}
                                                    </div>
                                                </div>
                                            </div>

                                            <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                                                <div className="flex justify-between">
                                                    <span className="text-gray-500">Batch</span>
                                                    <span className="text-gray-300 font-mono">{item.batch}</span>
                                                </div>
                                                <div className="flex justify-between">
                                                    <span className="text-gray-500">Expiry</span>
                                                    <span className="text-gray-300">{item.expiry}</span>
                                                </div>
                                                <div className="flex justify-between">
                                                    <span className="text-gray-500">MRP</span>
                                                    <span className="text-gray-300">₹{item.mrp.toFixed(2)}</span>
                                                </div>
                                                <div className="flex justify-between">
                                                    <span className="text-gray-500">Mfr</span>
                                                    <span className="text-gray-300 truncate max-w-[100px]" title={item.mfr}>{item.mfr}</span>
                                                </div>
                                            </div>
                                        </div>
                                    ))
                                )}
                            </div>
                        </div>

                        {/* Footer Totals */}
                        <div className="p-6 border-t border-white/10 bg-[#222]">
                            <div className="space-y-3">
                                <div className="flex justify-between items-center">
                                    <span className="text-gray-400">Calculated Total</span>
                                    <span className="text-xl font-bold text-white">
                                        ₹{calculatedTotal.toFixed(2)}
                                    </span>
                                </div>
                                {netAmount !== null && (
                                    <div className="flex justify-between items-center pt-3 border-t border-white/5">
                                        <span className="text-gray-400">Net Amount (Extracted)</span>
                                        <span className="text-2xl font-bold text-green-400">
                                            ₹{netAmount.toFixed(2)}
                                        </span>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                </ModalErrorBoundary>
            </div>
        </div>
    );
};

const InvoiceCard: React.FC<{
    invoice: Invoice;
    isSelected: boolean;
    isEditMode: boolean;
    onClick: () => void;
}> = ({ invoice, isSelected, isEditMode, onClick }) => {
    if (!invoice) return null;

    // Defensive calculations
    const items = Array.isArray(invoice.items) ? invoice.items : [];
    const itemCount = items.length;
    const totalValue = items.reduce((acc, item) => {
        if (!item) return acc;
        const qty = Number(item.quantity) || Number(item.quantity_packs) || 0;
        const rate = Number(item.rate) || Number(item.buy_price) || Number(item.mrp) || 0;
        return acc + (qty * rate);
    }, 0);

    const invoiceId = invoice.id ? String(invoice.id) : 'Unknown';
    const displayId = invoiceId.length > 8 ? invoiceId.slice(0, 8) : invoiceId;
    const uploadDate = invoice.upload_date ? String(invoice.upload_date).split(' ')[0] : 'N/A';
    const supplierName = invoice.supplier || "Unknown Supplier";

    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            onClick={onClick}
            className={`group border rounded-xl overflow-hidden transition-all cursor-pointer flex flex-col relative ${isSelected
                ? 'bg-purple-500/10 border-purple-500/50'
                : 'bg-white/5 border-white/5 hover:bg-white/10 hover:border-white/20'
                }`}
        >
            {isEditMode && (
                <div className="absolute top-2 right-2 z-20">
                    <div className={`w-6 h-6 border-2 rounded-md flex items-center justify-center transition-colors shadow-lg ${isSelected
                        ? 'bg-purple-600 border-purple-600'
                        : 'bg-black/50 border-white/50 hover:border-white'
                        }`}>
                        {isSelected && <Check size={16} className="text-white" />}
                    </div>
                </div>
            )}

            <div className="h-40 bg-gray-800 overflow-hidden border-b border-white/5 relative">
                {invoice.image_url ? (
                    <img
                        src={invoice.image_url}
                        alt="Bill"
                        className="h-full w-full object-cover opacity-80 group-hover:opacity-100 transition-opacity"
                        onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                    />
                ) : (
                    <div className="h-full w-full flex items-center justify-center text-gray-500">No Image</div>
                )}

                {!isEditMode && (
                    <div className="absolute top-2 right-2 bg-black/60 backdrop-blur-md px-2 py-1 rounded-md text-xs font-medium">
                        {itemCount} Items
                    </div>
                )}
            </div>

            <div className="p-4 flex-1 flex flex-col">
                <div className="flex justify-between items-start mb-2">
                    <h3 className="font-semibold text-white truncate flex-1">#{displayId}</h3>
                    <span className="text-xs text-gray-400">{supplierName} • {uploadDate}</span>
                </div>

                <div className="mt-auto pt-3 border-t border-white/5 flex justify-between items-center">
                    <span className="text-sm text-gray-400">Total Value</span>
                    <span className="font-bold text-white">
                        ₹{totalValue.toFixed(2)}
                    </span>
                </div>
            </div>
        </motion.div>
    );
};

const InvoiceRow: React.FC<{
    invoice: Invoice;
    isSelected: boolean;
    isEditMode: boolean;
    onClick: () => void;
}> = ({ invoice, isSelected, isEditMode, onClick }) => {
    if (!invoice) return null;

    const items = Array.isArray(invoice.items) ? invoice.items : [];
    const itemCount = items.length;
    const totalPacks = items.reduce((acc, item) => {
        if (!item) return acc;
        return acc + (Number(item.quantity) || Number(item.quantity_packs) || 0);
    }, 0);

    const totalValue = items.reduce((acc, item) => {
        if (!item) return acc;
        const qty = Number(item.quantity) || Number(item.quantity_packs) || 0;
        const rate = Number(item.rate) || Number(item.buy_price) || Number(item.mrp) || 0;
        return acc + (qty * rate);
    }, 0);

    const invoiceId = invoice.id ? String(invoice.id) : 'Unknown';
    const displayId = invoiceId.length > 8 ? invoiceId.slice(0, 8) : invoiceId;
    const uploadDate = invoice.upload_date || 'N/A';
    const supplierName = invoice.supplier || "Unknown Supplier";

    return (
        <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            onClick={onClick}
            className={`group flex items-center gap-4 border rounded-xl p-4 transition-all cursor-pointer ${isSelected
                ? 'bg-purple-500/10 border-purple-500/50'
                : 'bg-white/5 border-white/5 hover:bg-white/10 hover:border-white/20'
                }`}
        >
            <div className="h-16 w-16 rounded-lg bg-gray-800 overflow-hidden flex-shrink-0 border border-white/10">
                {invoice.image_url ? (
                    <img
                        src={invoice.image_url}
                        alt="Bill"
                        className="h-full w-full object-cover opacity-80 group-hover:opacity-100 transition-opacity"
                        onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                    />
                ) : (
                    <div className="h-full w-full flex items-center justify-center text-xs text-gray-500">No Img</div>
                )}
            </div>

            <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                    <h3 className="font-semibold text-white truncate">Invoice #{displayId}</h3>
                    <span className="text-xs bg-blue-500/20 text-blue-400 px-2 py-0.5 rounded-full">
                        {itemCount} Items
                    </span>
                </div>
                <div className="flex items-center gap-4 text-sm text-gray-400">
                    <span className="flex items-center gap-1">
                        <Calendar size={14} />
                        {supplierName} • {uploadDate}
                    </span>
                    <span className="flex items-center gap-1">
                        <Package size={14} />
                        {totalPacks} Total Packs
                    </span>
                </div>
            </div>

            <div className="text-right">
                <div className="text-lg font-bold text-white">
                    ₹{totalValue.toFixed(2)}
                </div>
                <div className="text-xs text-gray-500">Total Value</div>
            </div>

            {isEditMode && (
                <div className="pl-4 border-l border-white/10 ml-2">
                    <div className={`w-6 h-6 border-2 rounded-md flex items-center justify-center transition-colors ${isSelected
                        ? 'bg-purple-600 border-purple-600'
                        : 'border-slate-600 hover:border-slate-500'
                        }`}>
                        {isSelected && <Check size={16} className="text-white" />}
                    </div>
                </div>
            )}
        </motion.div>
    );
};

// --- Main Component ---

const InvoicesView: React.FC = () => {
    const [invoices, setInvoices] = useState<Invoice[]>([]);
    const [viewMode, setViewMode] = useState<'list' | 'grid'>('list');
    const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
    const [showFilterMenu, setShowFilterMenu] = useState(false);
    const [searchTerm, setSearchTerm] = useState('');
    const [selectedInvoice, setSelectedInvoice] = useState<Invoice | null>(null);
    const [error, setError] = useState<string | null>(null);

    // Edit Mode State
    const [isEditMode, setIsEditMode] = useState(false);
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

    useEffect(() => {
        fetchInvoices();
    }, []);

    useEffect(() => {
        if (!isEditMode) {
            setSelectedIds(new Set());
        }
    }, [isEditMode]);

    const fetchInvoices = async () => {
        setError(null);
        try {
            const response = await fetch('http://localhost:8000/api/invoices');
            if (!response.ok) throw new Error("Failed to fetch invoices");

            const data = await response.json();
            if (Array.isArray(data.invoices)) {
                const validInvoices = data.invoices.filter((inv: any) => inv && typeof inv === 'object');
                setInvoices(validInvoices);
            } else {
                console.error("Invalid invoices data format:", data);
                setInvoices([]);
                setError("Received invalid data format from server.");
            }
        } catch (error) {
            console.error("Error fetching invoices:", error);
            setInvoices([]);
            setError("Failed to load invoices. Check backend connection.");
        }
    };

    const filteredInvoices = invoices.filter(invoice => {
        if (!invoice) return false;
        if (!searchTerm) return true;
        const term = searchTerm.toLowerCase();

        const items = Array.isArray(invoice.items) ? invoice.items : [];
        const matchesItems = items.some(item => {
            if (!item) return false;
            return (
                (item.product_name || "").toLowerCase().includes(term) ||
                (item.manufacturer || "").toLowerCase().includes(term) ||
                (item.dosage_form || "").toLowerCase().includes(term)
            );
        });

        const matchesInvoice = (invoice.supplier || "").toLowerCase().includes(term) ||
            (invoice.id || "").toLowerCase().includes(term);

        return matchesItems || matchesInvoice;
    }).sort((a, b) => {
        const dateA = new Date(a.upload_date || 0).getTime();
        const dateB = new Date(b.upload_date || 0).getTime();
        return sortOrder === 'asc' ? dateA - dateB : dateB - dateA;
    });

    const toggleSelection = (id: string) => {
        if (!id) return;
        setSelectedIds(prev => {
            const newSet = new Set(prev);
            if (newSet.has(id)) {
                newSet.delete(id);
            } else {
                newSet.add(id);
            }
            return newSet;
        });
    };

    const toggleSelectAll = () => {
        const allSelected = filteredInvoices.length > 0 && filteredInvoices.every(inv => inv.id && selectedIds.has(inv.id));

        if (allSelected) {
            setSelectedIds(new Set());
        } else {
            const newSet = new Set(selectedIds);
            filteredInvoices.forEach(inv => {
                if (inv.id) newSet.add(inv.id);
            });
            setSelectedIds(newSet);
        }
    };

    const handleDeleteSelected = async () => {
        if (!confirm(`Are you sure you want to delete ${selectedIds.size} invoices?`)) return;

        try {
            const response = await fetch('http://localhost:8000/api/invoices/delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ invoice_ids: Array.from(selectedIds) })
            });

            if (response.ok) {
                setSelectedIds(new Set());
                fetchInvoices();
            } else {
                alert("Failed to delete invoices");
            }
        } catch (error) {
            console.error("Error deleting invoices:", error);
            alert("Error deleting invoices");
        }
    };

    return (
        <div className="h-full flex flex-col">
            <div className="flex justify-between items-center mb-6">
                <div>
                    <h1 className="text-3xl font-bold mb-1">Invoices</h1>
                    <p className="text-gray-400">Manage and view your bill history.</p>
                </div>

                <div className="flex items-center gap-3">
                    {error && (
                        <div className="flex items-center gap-2 text-red-400 bg-red-500/10 px-3 py-1.5 rounded-lg border border-red-500/20 text-sm">
                            <AlertCircle size={16} />
                            {error}
                            <button onClick={fetchInvoices} className="ml-2 hover:text-white"><RefreshCw size={14} /></button>
                        </div>
                    )}

                    <AnimatePresence>
                        {isEditMode && selectedIds.size > 0 && (
                            <motion.button
                                initial={{ opacity: 0, scale: 0.9 }}
                                animate={{ opacity: 1, scale: 1 }}
                                exit={{ opacity: 0, scale: 0.9 }}
                                onClick={handleDeleteSelected}
                                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/20 hover:text-red-300 transition-colors font-medium"
                            >
                                <Trash2 size={18} />
                                Delete ({selectedIds.size})
                            </motion.button>
                        )}
                    </AnimatePresence>



                    <button
                        onClick={() => setIsEditMode(!isEditMode)}
                        className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-all border ${isEditMode
                            ? 'bg-blue-500/20 border-blue-500 text-blue-400'
                            : 'bg-white/5 border-white/10 text-gray-300 hover:text-white hover:bg-white/10'
                            }`}
                    >
                        {isEditMode ? <Check size={18} /> : <Lock size={18} />}
                        {isEditMode ? 'Done' : 'Edit'}
                    </button>

                    <div className="h-8 w-px bg-white/10 mx-1"></div>

                    <div className="flex items-center gap-1 bg-white/5 p-1 rounded-lg border border-white/10">
                        <button
                            onClick={() => setViewMode('list')}
                            className={`p-2 rounded-md transition-colors ${viewMode === 'list' ? 'bg-white/10 text-white' : 'text-gray-400 hover:text-white'}`}
                        >
                            <List size={20} />
                        </button>
                        <button
                            onClick={() => setViewMode('grid')}
                            className={`p-2 rounded-md transition-colors ${viewMode === 'grid' ? 'bg-white/10 text-white' : 'text-gray-400 hover:text-white'}`}
                        >
                            <LayoutGrid size={20} />
                        </button>
                    </div>
                </div>
            </div>

            <div className={`flex gap-4 mb-6 transition-opacity duration-300 ${isEditMode ? 'opacity-50 pointer-events-none' : 'opacity-100'}`}>
                <div className="relative flex-1">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
                    <input
                        type="text"
                        placeholder="Search invoices..."
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        className="w-full bg-white/5 border border-white/10 rounded-lg pl-10 pr-4 py-2.5 text-white focus:outline-none focus:border-blue-500 transition-colors"
                    />
                </div>

                <div className="relative">
                    <button
                        onClick={() => setShowFilterMenu(!showFilterMenu)}
                        className="flex items-center gap-2 px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-sm text-gray-300 hover:text-white transition-colors"
                    >
                        <ListFilter size={16} />
                        <span>Filter</span>
                    </button>

                    {/* Dropdown Menu */}
                    {showFilterMenu && (
                        <div className="absolute right-0 mt-2 w-48 bg-[#1a1a1a] border border-white/10 rounded-lg shadow-xl z-50 overflow-hidden">
                            <button
                                onClick={() => { setSortOrder('desc'); setShowFilterMenu(false); }}
                                className={`w-full text-left px-4 py-2 text-sm ${sortOrder === 'desc' ? 'text-blue-400 bg-white/5' : 'text-gray-300 hover:bg-white/5'}`}
                            >
                                Newest to Oldest (Default)
                            </button>
                            <button
                                onClick={() => { setSortOrder('asc'); setShowFilterMenu(false); }}
                                className={`w-full text-left px-4 py-2 text-sm ${sortOrder === 'asc' ? 'text-blue-400 bg-white/5' : 'text-gray-300 hover:bg-white/5'}`}
                            >
                                Oldest to Newest
                            </button>
                        </div>
                    )}
                </div>
            </div>

            {isEditMode && (
                <div className="mb-4 flex items-center gap-3 px-4 py-2 bg-white/5 border border-white/10 rounded-lg">
                    <button
                        onClick={toggleSelectAll}
                        className={`w-5 h-5 border-2 rounded flex items-center justify-center transition-colors ${filteredInvoices.length > 0 && filteredInvoices.every(inv => inv.id && selectedIds.has(inv.id))
                            ? 'bg-purple-600 border-purple-600'
                            : 'border-slate-600 hover:border-slate-500'
                            }`}
                    >
                        {filteredInvoices.length > 0 && filteredInvoices.every(inv => inv.id && selectedIds.has(inv.id)) && <Check size={14} className="text-white" />}
                    </button>
                    <span className="text-sm text-gray-300">Select All {filteredInvoices.length} Invoices</span>
                </div>
            )}

            <div className="flex-1 overflow-y-auto pr-2">
                {filteredInvoices.length === 0 && !error ? (
                    <div className="text-center text-gray-500 mt-20">
                        <p>No invoices found.</p>
                    </div>
                ) : null}

                {viewMode === 'list' ? (
                    <div className="space-y-3">
                        {filteredInvoices.map((invoice, idx) => {
                            if (!invoice) return null;
                            const id = invoice.id || `temp-${idx}`;
                            return (
                                <InvoiceRow
                                    key={id}
                                    invoice={invoice}
                                    isSelected={selectedIds.has(id)}
                                    isEditMode={isEditMode}
                                    onClick={() => isEditMode ? toggleSelection(id) : setSelectedInvoice(invoice)}
                                />
                            );
                        })}
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {filteredInvoices.map((invoice, idx) => {
                            if (!invoice) return null;
                            const id = invoice.id || `temp-${idx}`;
                            return (
                                <InvoiceCard
                                    key={id}
                                    invoice={invoice}
                                    isSelected={selectedIds.has(id)}
                                    isEditMode={isEditMode}
                                    onClick={() => isEditMode ? toggleSelection(id) : setSelectedInvoice(invoice)}
                                />
                            );
                        })}
                    </div>
                )}
            </div>

            {selectedInvoice && (
                <InvoiceDetailModal
                    invoice={selectedInvoice}
                    onClose={() => setSelectedInvoice(null)}
                />
            )}
        </div>
    );
};

export default InvoicesView;
