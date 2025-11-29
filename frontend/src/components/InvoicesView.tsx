import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { LayoutGrid, List, Filter, Search, Calendar, Package } from 'lucide-react';

interface InvoiceItem {
    product_name: string;
    batch_number: string;
    expiry_date: string;
    quantity_packs: number;
    pack_size: number;
    mrp: number;
    rate?: number;
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
    items: InvoiceItem[];
}

const InvoicesView: React.FC = () => {
    const [invoices, setInvoices] = useState<Invoice[]>([]);
    const [viewMode, setViewMode] = useState<'list' | 'grid'>('list');
    const [searchTerm, setSearchTerm] = useState('');
    const [filterType, setFilterType] = useState<'all' | 'manufacturer' | 'medicine'>('all');
    const [selectedInvoice, setSelectedInvoice] = useState<Invoice | null>(null);

    useEffect(() => {
        fetchInvoices();
    }, []);

    const fetchInvoices = async () => {
        try {
            const response = await fetch('http://localhost:8000/api/invoices');
            const data = await response.json();
            setInvoices(data.invoices);
        } catch (error) {
            console.error("Error fetching invoices:", error);
        }
    };

    const filteredInvoices = invoices.filter(invoice => {
        if (!searchTerm) return true;
        const term = searchTerm.toLowerCase();

        // Check if any item in the invoice matches the search term
        return invoice.items.some(item => {
            if (filterType === 'manufacturer') {
                return item.manufacturer?.toLowerCase().includes(term);
            } else if (filterType === 'medicine') {
                return item.product_name?.toLowerCase().includes(term);
            } else {
                // Search everything
                return (
                    item.product_name?.toLowerCase().includes(term) ||
                    item.manufacturer?.toLowerCase().includes(term) ||
                    item.dosage_form?.toLowerCase().includes(term)
                );
            }
        });
    });

    return (
        <div className="h-full flex flex-col">
            <div className="flex justify-between items-center mb-6">
                <div>
                    <h1 className="text-3xl font-bold mb-1">Invoices</h1>
                    <p className="text-gray-400">Manage and view your bill history.</p>
                </div>

                <div className="flex items-center gap-3 bg-white/5 p-1 rounded-lg border border-white/10">
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

            {/* Filters */}
            <div className="flex gap-4 mb-6">
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

                <div className="flex items-center gap-2 bg-white/5 border border-white/10 rounded-lg px-3">
                    <Filter size={16} className="text-gray-400" />
                    <select
                        value={filterType}
                        onChange={(e) => setFilterType(e.target.value as any)}
                        className="bg-transparent border-none text-sm text-white focus:outline-none cursor-pointer"
                    >
                        <option value="all" className="bg-[#1a1a1a]">All Fields</option>
                        <option value="manufacturer" className="bg-[#1a1a1a]">Manufacturer</option>
                        <option value="medicine" className="bg-[#1a1a1a]">Medicine Name</option>
                    </select>
                </div>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto pr-2">
                {viewMode === 'list' ? (
                    <div className="space-y-3">
                        {filteredInvoices.map((invoice) => (
                            <motion.div
                                key={invoice.id}
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                onClick={() => setSelectedInvoice(invoice)}
                                className="group flex items-center gap-4 bg-white/5 border border-white/5 rounded-xl p-4 hover:bg-white/10 hover:border-white/20 transition-all cursor-pointer"
                            >
                                <div className="h-16 w-16 rounded-lg bg-gray-800 overflow-hidden flex-shrink-0 border border-white/10">
                                    <img src={invoice.image_url} alt="Bill" className="h-full w-full object-cover opacity-80 group-hover:opacity-100 transition-opacity" />
                                </div>

                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2 mb-1">
                                        <h3 className="font-semibold text-white truncate">Invoice #{invoice.id.slice(0, 8)}</h3>
                                        <span className="text-xs bg-blue-500/20 text-blue-400 px-2 py-0.5 rounded-full">
                                            {invoice.items.length} Items
                                        </span>
                                    </div>
                                    <div className="flex items-center gap-4 text-sm text-gray-400">
                                        <span className="flex items-center gap-1">
                                            <Calendar size={14} />
                                            {invoice.upload_date}
                                        </span>
                                        <span className="flex items-center gap-1">
                                            <Package size={14} />
                                            {invoice.items.reduce((acc, item) => acc + item.quantity_packs, 0)} Total Packs
                                        </span>
                                    </div>
                                </div>

                                <div className="text-right">
                                    <div className="text-lg font-bold text-white">
                                        ₹{invoice.items.reduce((acc, item) => acc + ((item.rate || item.mrp) * item.quantity_packs), 0).toFixed(2)}
                                    </div>
                                    <div className="text-xs text-gray-500">Total Value</div>
                                </div>
                            </motion.div>
                        ))}
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {filteredInvoices.map((invoice) => (
                            <motion.div
                                key={invoice.id}
                                initial={{ opacity: 0, scale: 0.95 }}
                                animate={{ opacity: 1, scale: 1 }}
                                onClick={() => setSelectedInvoice(invoice)}
                                className="group bg-white/5 border border-white/5 rounded-xl overflow-hidden hover:bg-white/10 hover:border-white/20 transition-all cursor-pointer flex flex-col"
                            >
                                <div className="h-40 bg-gray-800 overflow-hidden border-b border-white/5 relative">
                                    <img src={invoice.image_url} alt="Bill" className="h-full w-full object-cover opacity-80 group-hover:opacity-100 transition-opacity" />
                                    <div className="absolute top-2 right-2 bg-black/60 backdrop-blur-md px-2 py-1 rounded-md text-xs font-medium">
                                        {invoice.items.length} Items
                                    </div>
                                </div>

                                <div className="p-4 flex-1 flex flex-col">
                                    <div className="flex justify-between items-start mb-2">
                                        <h3 className="font-semibold text-white truncate flex-1">#{invoice.id.slice(0, 8)}</h3>
                                        <span className="text-xs text-gray-400">{invoice.upload_date.split(' ')[0]}</span>
                                    </div>

                                    <div className="mt-auto pt-3 border-t border-white/5 flex justify-between items-center">
                                        <span className="text-sm text-gray-400">Total Value</span>
                                        <span className="font-bold text-white">
                                            ₹{invoice.items.reduce((acc, item) => acc + ((item.rate || item.mrp) * item.quantity_packs), 0).toFixed(2)}
                                        </span>
                                    </div>
                                </div>
                            </motion.div>
                        ))}
                    </div>
                )}
            </div>

            {/* Invoice Details Modal */}
            {selectedInvoice && (
                <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/80 backdrop-blur-sm p-8" onClick={() => setSelectedInvoice(null)}>
                    <div className="bg-[#1a1a1a] border border-white/10 rounded-2xl w-full max-w-5xl h-[85vh] flex overflow-hidden shadow-2xl" onClick={e => e.stopPropagation()}>
                        {/* Left: Image */}
                        <div className="w-1/2 bg-black flex items-center justify-center border-r border-white/10 p-4">
                            <img src={selectedInvoice.image_url} alt="Invoice" className="max-w-full max-h-full object-contain rounded-lg" />
                        </div>

                        {/* Right: Details */}
                        <div className="w-1/2 flex flex-col">
                            <div className="p-6 border-b border-white/10 flex justify-between items-start">
                                <div>
                                    <h2 className="text-2xl font-bold mb-1">Invoice Details</h2>
                                    <p className="text-gray-400 text-sm">ID: {selectedInvoice.id}</p>
                                    <p className="text-gray-400 text-sm">Uploaded: {selectedInvoice.upload_date}</p>
                                </div>
                                <button onClick={() => setSelectedInvoice(null)} className="p-2 hover:bg-white/10 rounded-full transition-colors">
                                    <span className="text-2xl">&times;</span>
                                </button>
                            </div>

                            <div className="flex-1 overflow-y-auto p-6">
                                <h3 className="text-sm font-semibold uppercase tracking-wider text-gray-500 mb-4">Extracted Items</h3>
                                <div className="space-y-4">
                                    {selectedInvoice.items.map((item, idx) => (
                                        <div key={idx} className="bg-white/5 rounded-lg p-4 border border-white/5">
                                            <div className="flex justify-between items-start mb-2">
                                                <h4 className="font-medium text-white text-lg">{item.product_name}</h4>
                                                <div className="text-right">
                                                    <div className="font-bold text-green-400 text-lg">
                                                        ₹{((item.rate || item.mrp) * item.quantity_packs).toFixed(2)}
                                                    </div>
                                                    <div className="text-xs text-gray-400">
                                                        ₹{item.rate || item.mrp} x {item.quantity_packs}
                                                    </div>
                                                </div>
                                            </div>
                                            <div className="grid grid-cols-2 gap-2 text-sm text-gray-400">
                                                <div>Batch: <span className="text-gray-300">{item.batch_number}</span></div>
                                                <div>Expiry: <span className="text-gray-300">{item.expiry_date}</span></div>
                                                <div>Qty: <span className="text-gray-300">{item.quantity_packs}</span></div>
                                                <div>MRP: <span className="text-gray-300">₹{item.mrp}</span></div>
                                                <div className="col-span-2">Mfr: <span className="text-gray-300">{item.manufacturer}</span></div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            <div className="p-6 border-t border-white/10 bg-white/5">
                                <div className="flex flex-col gap-2">
                                    <div className="flex justify-between items-center">
                                        <span className="text-gray-400">Calculated Total (Items)</span>
                                        <span className="text-xl font-bold text-white">
                                            ₹{selectedInvoice.items.reduce((acc, item) => acc + ((item.rate || item.mrp) * item.quantity_packs), 0).toFixed(2)}
                                        </span>
                                    </div>
                                    {selectedInvoice.net_amount && (
                                        <div className="flex justify-between items-center border-t border-white/5 pt-2">
                                            <span className="text-gray-400">Net Amount (From Bill)</span>
                                            <span className="text-2xl font-bold text-white">
                                                ₹{selectedInvoice.net_amount.toFixed(2)}
                                            </span>
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default InvoicesView;
