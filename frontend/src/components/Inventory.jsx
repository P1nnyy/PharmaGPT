import React, { useState, useEffect } from 'react';
import { Package, Search, Filter } from 'lucide-react';

const Inventory = () => {
    const [items, setItems] = useState([]);
    const [filteredItems, setFilteredItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState("");

    useEffect(() => {
        fetchInventory();
    }, []);

    useEffect(() => {
        if (!search) {
            setFilteredItems(items);
        } else {
            const lower = search.toLowerCase();
            setFilteredItems(items.filter(i => i.product_name.toLowerCase().includes(lower)));
        }
    }, [search, items]);

    const fetchInventory = async () => {
        try {
            const API_BASE_URL = window.location.hostname.includes('pharmagpt.co')
                ? 'https://api.pharmagpt.co'
                : 'http://localhost:8000';

            const res = await fetch(`${API_BASE_URL}/inventory`);
            const data = await res.json();
            if (Array.isArray(data)) {
                setItems(data);
                setFilteredItems(data);
            } else {
                console.error("Inventory API returned non-array:", data);
                setItems([]);
                setFilteredItems([]);
            }
        } catch (err) {
            console.error("Failed to fetch inventory:", err);
        } finally {
            setLoading(false);
        }
    };

    if (loading) {
        return <div className="p-4 text-center text-slate-400">Loading Inventory...</div>;
    }

    return (
        <div className="p-4 h-[calc(100vh-80px)] overflow-y-auto pb-24">
            <h2 className="text-xl font-bold text-slate-100 mb-4 flex items-center gap-2">
                <Package className="w-6 h-6 text-emerald-400" /> Inventory
            </h2>

            {/* Search Bar */}
            <div className="relative mb-4">
                <Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-500" />
                <input
                    type="text"
                    placeholder="Search medicines..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg pl-10 pr-4 py-2 text-slate-200 focus:outline-none focus:border-indigo-500 transition-colors"
                />
            </div>

            <div className="space-y-2">
                {filteredItems.map((item, idx) => (
                    <div key={idx} className="bg-slate-800 p-3 rounded-lg border border-slate-700/50 flex justify-between items-center">
                        <div>
                            <div className="text-slate-200 font-medium">{item.product_name}</div>
                            <div className="text-xs text-slate-500 mt-1">
                                MRP: <span className="text-slate-400">₹{item.mrp}</span>
                            </div>
                        </div>
                        <div className="text-right">
                            <div className="text-2xl font-bold text-emerald-400">{item.total_quantity}</div>
                            <div className="text-[10px] text-slate-500 uppercase tracking-wider">Stock</div>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default Inventory;
