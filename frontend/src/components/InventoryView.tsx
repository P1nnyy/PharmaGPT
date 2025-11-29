import React, { useState, useEffect } from 'react';
import { Search, Filter, Package, AlertTriangle, Calendar, Activity } from 'lucide-react';
import { motion } from 'framer-motion';

interface InventoryItem {
    product_name: string;
    dosage_form: string;
    manufacturer: string;
    batch_number: string;
    stock_display: string;
    quantity_packs: number;
    quantity_loose: number;
    total_atoms: number;
    expiry_date: string;
    mrp: number;
    tax_rate: number;
}

const InventoryView: React.FC = () => {
    const [inventory, setInventory] = useState<InventoryItem[]>([]);
    const [searchTerm, setSearchTerm] = useState('');
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchInventory();
    }, []);

    const fetchInventory = async () => {
        try {
            const response = await fetch('http://localhost:8000/api/inventory');
            const data = await response.json();
            setInventory(data.inventory);
        } catch (error) {
            console.error("Error fetching inventory:", error);
        } finally {
            setLoading(false);
        }
    };

    const filteredInventory = inventory.filter(item => {
        const term = searchTerm.toLowerCase();
        return (
            item.product_name.toLowerCase().includes(term) ||
            item.manufacturer.toLowerCase().includes(term) ||
            item.batch_number.toLowerCase().includes(term)
        );
    });

    // Helper to check if expired or near expiry (within 3 months)
    const getExpiryStatus = (dateStr: string) => {
        const expiry = new Date(dateStr);
        const now = new Date();
        const threeMonthsFromNow = new Date();
        threeMonthsFromNow.setMonth(now.getMonth() + 3);

        if (expiry < now) return 'expired';
        if (expiry < threeMonthsFromNow) return 'near_expiry';
        return 'good';
    };

    return (
        <div className="h-full flex flex-col">
            <div className="flex justify-between items-center mb-6">
                <div>
                    <h1 className="text-3xl font-bold mb-1">Inventory</h1>
                    <p className="text-gray-400">Real-time stock tracking and management.</p>
                </div>
                <div className="flex gap-2">
                    <button onClick={fetchInventory} className="p-2 bg-white/5 hover:bg-white/10 rounded-lg transition-colors text-gray-300 hover:text-white">
                        <Activity size={20} />
                    </button>
                </div>
            </div>

            {/* Search and Filter Bar */}
            <div className="flex gap-4 mb-6">
                <div className="relative flex-1">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
                    <input
                        type="text"
                        placeholder="Search by medicine, batch, or manufacturer..."
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        className="w-full bg-white/5 border border-white/10 rounded-lg pl-10 pr-4 py-2.5 text-white focus:outline-none focus:border-blue-500 transition-colors"
                    />
                </div>
                <div className="flex items-center gap-2 bg-white/5 border border-white/10 rounded-lg px-3 text-gray-400">
                    <Filter size={16} />
                    <span className="text-sm">Filter</span>
                </div>
            </div>

            {/* Inventory Table */}
            <div className="flex-1 overflow-y-auto rounded-xl border border-white/10 bg-white/5 backdrop-blur-sm">
                {loading ? (
                    <div className="flex items-center justify-center h-64 text-gray-400">
                        Loading inventory...
                    </div>
                ) : filteredInventory.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-64 text-gray-400">
                        <Package size={48} className="mb-4 opacity-50" />
                        <p>No inventory items found.</p>
                    </div>
                ) : (
                    <table className="w-full text-left border-collapse">
                        <thead className="bg-white/5 sticky top-0 backdrop-blur-md z-10">
                            <tr className="text-gray-400 text-sm font-medium">
                                <th className="p-4 border-b border-white/10">Product Name</th>
                                <th className="p-4 border-b border-white/10">Batch Info</th>
                                <th className="p-4 border-b border-white/10">Stock Level</th>
                                <th className="p-4 border-b border-white/10">Expiry</th>
                                <th className="p-4 border-b border-white/10 text-right">MRP</th>
                            </tr>
                        </thead>
                        <tbody>
                            {filteredInventory.map((item, idx) => {
                                const expiryStatus = getExpiryStatus(item.expiry_date);
                                return (
                                    <motion.tr
                                        key={idx}
                                        initial={{ opacity: 0, y: 5 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        transition={{ delay: idx * 0.05 }}
                                        className="border-b border-white/5 hover:bg-white/5 transition-colors group"
                                    >
                                        <td className="p-4">
                                            <div className="font-medium text-white">{item.product_name}</div>
                                            <div className="text-xs text-gray-500 flex gap-2 mt-1">
                                                <span>{item.manufacturer}</span>
                                                <span className="w-1 h-1 rounded-full bg-gray-600 self-center"></span>
                                                <span>{item.dosage_form}</span>
                                            </div>
                                        </td>
                                        <td className="p-4">
                                            <div className="text-gray-300 font-mono text-sm">{item.batch_number}</div>
                                        </td>
                                        <td className="p-4">
                                            <div className="flex flex-col">
                                                <span className="text-white font-medium">{item.quantity_packs} Packs</span>
                                                {item.quantity_loose > 0 && (
                                                    <span className="text-xs text-gray-400">{item.quantity_loose} Loose</span>
                                                )}
                                                {item.quantity_packs === 0 && item.quantity_loose === 0 && (
                                                    <span className="text-xs text-red-400 font-medium">Out of Stock</span>
                                                )}
                                            </div>
                                        </td>
                                        <td className="p-4">
                                            <div className={`flex items-center gap-2 text-sm ${expiryStatus === 'expired' ? 'text-red-400 font-bold' :
                                                    expiryStatus === 'near_expiry' ? 'text-yellow-400' : 'text-gray-300'
                                                }`}>
                                                <Calendar size={14} />
                                                {item.expiry_date}
                                                {expiryStatus === 'expired' && <AlertTriangle size={14} />}
                                            </div>
                                        </td>
                                        <td className="p-4 text-right">
                                            <div className="font-medium text-white">₹{item.mrp.toFixed(2)}</div>
                                            <div className="text-xs text-gray-500">per pack</div>
                                        </td>
                                    </motion.tr>
                                );
                            })}
                        </tbody>
                    </table>
                )}
            </div>
        </div>
    );
};

export default InventoryView;
