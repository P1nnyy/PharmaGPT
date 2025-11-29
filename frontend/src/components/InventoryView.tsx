import React, { useState, useEffect, useMemo, useRef } from 'react';
import { Search, Filter, Package, AlertTriangle, Calendar, Activity, ChevronDown, X, Lock, Unlock, Check, Trash2 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { QuickEditModal } from './modals/QuickEditModal';

// --- Types ---

interface InventoryItem {
    product_name: string;
    dosage_form: string; // Mapped to Category
    manufacturer: string;
    batch_number: string;
    stock_display: string;
    quantity_packs: number;
    quantity_loose: number;
    total_atoms: number;
    expiry_date: string;
    mrp: number;
    purchase_rate: number;
    tax_rate: number;
}

type ExpiryFilter = 'all' | 'near_expiry' | 'expired';
type StockSort = 'none' | 'highest' | 'lowest';

interface FilterState {
    categories: string[];
    expiry: ExpiryFilter;
    sort: StockSort;
}

const CATEGORY_OPTIONS = ['Tablet', 'Capsule', 'Syrup', 'Injection', 'Softgel', 'Powder', 'Liquid', 'Cream', 'Gel', 'Drops', 'Other'];

// --- Component ---

const InventoryView: React.FC = () => {
    // Data State
    const [inventory, setInventory] = useState<InventoryItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchTerm, setSearchTerm] = useState('');

    // Filter State
    const [isFilterOpen, setIsFilterOpen] = useState(false);
    const [filters, setFilters] = useState<FilterState>({
        categories: [],
        expiry: 'all',
        sort: 'none'
    });

    // Edit Mode State
    const [isEditMode, setIsEditMode] = useState(false);
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

    const [editModal, setEditModal] = useState<{
        isOpen: boolean;
        itemIndex: number | null;
        field: 'stock' | 'mrp' | null;
        currentValue: number;
    }>({ isOpen: false, itemIndex: null, field: null, currentValue: 0 });

    const filterRef = useRef<HTMLDivElement>(null);

    // --- Effects ---

    useEffect(() => {
        fetchInventory();

        // Click outside to close filter
        const handleClickOutside = (event: MouseEvent) => {
            if (filterRef.current && !filterRef.current.contains(event.target as Node)) {
                setIsFilterOpen(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    // Reset selection when edit mode is toggled off
    useEffect(() => {
        if (!isEditMode) {
            setSelectedIds(new Set());
        }
    }, [isEditMode]);

    const fetchInventory = async () => {
        setLoading(true);
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

    // --- Logic: Filtering & Sorting ---

    const processedInventory = useMemo(() => {
        let result = [...inventory];

        // 1. Search (Text)
        if (searchTerm) {
            const term = searchTerm.toLowerCase();
            result = result.filter(item =>
                item.product_name.toLowerCase().includes(term) ||
                item.manufacturer.toLowerCase().includes(term) ||
                item.batch_number.toLowerCase().includes(term)
            );
        }

        // 2. Filter by Category (Multi-select)
        if (filters.categories.length > 0) {
            result = result.filter(item =>
                filters.categories.includes(item.dosage_form)
            );
        }

        // 3. Filter by Expiry
        const now = new Date();
        const threeMonthsFromNow = new Date();
        threeMonthsFromNow.setMonth(now.getMonth() + 3);

        if (filters.expiry === 'expired') {
            result = result.filter(item => new Date(item.expiry_date) < now);
        } else if (filters.expiry === 'near_expiry') {
            result = result.filter(item => {
                const d = new Date(item.expiry_date);
                return d >= now && d <= threeMonthsFromNow;
            });
        }

        // 4. Sort by Quantity
        if (filters.sort === 'highest') {
            result.sort((a, b) => b.quantity_packs - a.quantity_packs);
        } else if (filters.sort === 'lowest') {
            result.sort((a, b) => a.quantity_packs - b.quantity_packs);
        }

        return result;
    }, [inventory, searchTerm, filters]);

    // --- Helpers ---

    const getUniqueId = (item: InventoryItem) => `${item.product_name}-${item.batch_number}`;

    const toggleSelection = (id: string) => {
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
        const allSelected = processedInventory.length > 0 && processedInventory.every(item => selectedIds.has(getUniqueId(item)));

        if (allSelected) {
            setSelectedIds(new Set());
        } else {
            const newSet = new Set(selectedIds);
            processedInventory.forEach(item => newSet.add(getUniqueId(item)));
            setSelectedIds(newSet);
        }
    };

    // --- Handlers ---

    const toggleCategory = (category: string) => {
        setFilters(prev => {
            const exists = prev.categories.includes(category);
            return {
                ...prev,
                categories: exists
                    ? prev.categories.filter(c => c !== category)
                    : [...prev.categories, category]
            };
        });
    };

    const clearFilters = () => {
        setFilters({
            categories: [],
            expiry: 'all',
            sort: 'none'
        });
        setSearchTerm('');
    };

    const handleUpdate = (newValue: number) => {
        if (editModal.itemIndex !== null && editModal.field) {
            setInventory(prev => {
                const newInventory = [...prev];
                const item = { ...newInventory[editModal.itemIndex!] };

                if (editModal.field === 'stock') {
                    item.quantity_packs = newValue;
                } else if (editModal.field === 'mrp') {
                    item.mrp = newValue;
                }

                newInventory[editModal.itemIndex!] = item;
                return newInventory;
            });
        }
    };

    const openEditModal = (index: number, field: 'stock' | 'mrp', value: number) => {
        if (!isEditMode) return;
        setEditModal({
            isOpen: true,
            itemIndex: index,
            field,
            currentValue: value
        });
    };

    const handleDeleteSelected = async () => {
        if (!confirm(`Are you sure you want to delete ${selectedIds.size} items?`)) return;

        // Find the items to get their batch numbers
        const selectedItems = inventory.filter(item => selectedIds.has(getUniqueId(item)));
        const batchNumbers = selectedItems.map(item => item.batch_number);

        try {
            const response = await fetch('http://localhost:8000/api/inventory/delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ batch_numbers: batchNumbers })
            });

            if (response.ok) {
                setSelectedIds(new Set());
                fetchInventory(); // Refresh data
            } else {
                alert("Failed to delete items");
            }
        } catch (error) {
            console.error("Error deleting items:", error);
            alert("Error deleting items");
        }
    };

    const getExpiryStatus = (dateStr: string) => {
        const expiry = new Date(dateStr);
        const now = new Date();
        const threeMonthsFromNow = new Date();
        threeMonthsFromNow.setMonth(now.getMonth() + 3);

        if (expiry < now) return 'expired';
        if (expiry < threeMonthsFromNow) return 'near_expiry';
        return 'good';
    };

    // Grid Columns Template
    const GRID_COLS = isEditMode
        ? "grid-cols-[2.5fr_1fr_1.5fr_1.5fr_1fr_1fr_1fr_50px]"
        : "grid-cols-[2.5fr_1fr_1.5fr_1.5fr_1fr_1fr_1fr]";

    // --- Render ---

    return (
        <div className="h-full flex flex-col overflow-hidden relative">
            {/* 1. Header Section (Fixed) */}
            <div className="flex-none">
                <div className="flex justify-between items-center mb-6">
                    <div>
                        <h1 className="text-3xl font-bold mb-1">Inventory</h1>
                        <p className="text-gray-400">Advanced filtering and stock analysis.</p>
                    </div>
                    <div className="flex gap-2">
                        <button
                            onClick={() => setIsEditMode(!isEditMode)}
                            className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-all border ${isEditMode
                                ? 'bg-blue-500/20 border-blue-500 text-blue-400'
                                : 'bg-white/5 border-white/10 text-gray-300 hover:text-white hover:bg-white/10'
                                }`}
                        >
                            {isEditMode ? <Unlock size={18} /> : <Lock size={18} />}
                            {isEditMode ? 'Done Editing' : 'Edit Inventory'}
                        </button>
                    </div>
                </div>

                {/* Search & Filter Bar */}
                <div className={`flex gap-4 mb-6 relative z-50 transition-opacity duration-300 ${isEditMode ? 'opacity-50 pointer-events-none' : 'opacity-100'}`}>
                    {/* Search Input */}
                    <div className="relative flex-1">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
                        <input
                            type="text"
                            placeholder="Search inventory..."
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            className="w-full bg-white/5 border border-white/10 rounded-lg pl-10 pr-4 py-2.5 text-white focus:outline-none focus:border-blue-500 transition-colors"
                        />
                    </div>

                    {/* Filter Button & Dropdown */}
                    <div className="relative" ref={filterRef}>
                        <button
                            onClick={() => setIsFilterOpen(!isFilterOpen)}
                            className={`flex items-center gap-2 border rounded-lg px-4 py-2.5 transition-all ${isFilterOpen || filters.categories.length > 0 || filters.expiry !== 'all' || filters.sort !== 'none'
                                ? 'bg-blue-600 border-blue-500 text-white shadow-lg shadow-blue-500/20'
                                : 'bg-white/5 border-white/10 text-gray-300 hover:bg-white/10 hover:text-white'
                                }`}
                        >
                            <Filter size={18} />
                            <span className="font-medium">Filters</span>
                            {(filters.categories.length > 0 || filters.expiry !== 'all' || filters.sort !== 'none') && (
                                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-white text-blue-600 text-xs font-bold">
                                    {filters.categories.length + (filters.expiry !== 'all' ? 1 : 0) + (filters.sort !== 'none' ? 1 : 0)}
                                </span>
                            )}
                            <ChevronDown size={16} className={`transition-transform ${isFilterOpen ? 'rotate-180' : ''}`} />
                        </button>

                        {/* Dropdown Panel */}
                        <AnimatePresence>
                            {isFilterOpen && (
                                <motion.div
                                    initial={{ opacity: 0, y: 10, scale: 0.95 }}
                                    animate={{ opacity: 1, y: 0, scale: 1 }}
                                    exit={{ opacity: 0, y: 10, scale: 0.95 }}
                                    transition={{ duration: 0.1 }}
                                    className="absolute right-0 top-full mt-2 w-80 bg-[#1a1a1a] border border-white/10 rounded-xl shadow-2xl p-5 overflow-hidden backdrop-blur-xl"
                                >
                                    {/* Section A: Product Type */}
                                    <div className="mb-5">
                                        <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Category</h4>
                                        <div className="flex flex-wrap gap-2">
                                            {CATEGORY_OPTIONS.map(cat => {
                                                const isSelected = filters.categories.includes(cat);
                                                return (
                                                    <button
                                                        key={cat}
                                                        onClick={() => toggleCategory(cat)}
                                                        className={`px-3 py-1 rounded-full text-xs font-medium border transition-all ${isSelected
                                                            ? 'bg-blue-600 border-blue-500 text-white'
                                                            : 'bg-white/5 border-white/10 text-gray-400 hover:bg-white/10 hover:text-white'
                                                            }`}
                                                    >
                                                        {cat}
                                                    </button>
                                                );
                                            })}
                                        </div>
                                    </div>

                                    {/* Section B: Expiry Status */}
                                    <div className="mb-5">
                                        <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Expiry Status</h4>
                                        <div className="space-y-2">
                                            {[
                                                { id: 'all', label: 'All Items' },
                                                { id: 'near_expiry', label: 'Expiring Soon (< 3 Months)' },
                                                { id: 'expired', label: 'Already Expired' }
                                            ].map((opt) => (
                                                <label key={opt.id} className="flex items-center gap-3 cursor-pointer group">
                                                    <div className={`w-4 h-4 rounded-full border flex items-center justify-center transition-colors ${filters.expiry === opt.id ? 'border-blue-500 bg-blue-500' : 'border-gray-600 group-hover:border-gray-500'
                                                        }`}>
                                                        {filters.expiry === opt.id && <div className="w-1.5 h-1.5 rounded-full bg-white" />}
                                                    </div>
                                                    <input
                                                        type="radio"
                                                        name="expiry"
                                                        className="hidden"
                                                        checked={filters.expiry === opt.id}
                                                        onChange={() => setFilters(prev => ({ ...prev, expiry: opt.id as ExpiryFilter }))}
                                                    />
                                                    <span className={`text-sm ${filters.expiry === opt.id ? 'text-white' : 'text-gray-400 group-hover:text-gray-300'}`}>
                                                        {opt.label}
                                                    </span>
                                                </label>
                                            ))}
                                        </div>
                                    </div>

                                    {/* Section C: Stock Sorting */}
                                    <div className="mb-5">
                                        <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Sort by Quantity</h4>
                                        <div className="flex bg-white/5 rounded-lg p-1 border border-white/10">
                                            {[
                                                { id: 'none', label: 'Default' },
                                                { id: 'highest', label: 'High → Low' },
                                                { id: 'lowest', label: 'Low → High' }
                                            ].map((opt) => (
                                                <button
                                                    key={opt.id}
                                                    onClick={() => setFilters(prev => ({ ...prev, sort: opt.id as StockSort }))}
                                                    className={`flex-1 py-1.5 text-xs font-medium rounded-md transition-all ${filters.sort === opt.id
                                                        ? 'bg-blue-600 text-white shadow-sm'
                                                        : 'text-gray-400 hover:text-white'
                                                        }`}
                                                >
                                                    {opt.label}
                                                </button>
                                            ))}
                                        </div>
                                    </div>

                                    {/* Footer Actions */}
                                    <div className="pt-4 border-t border-white/10 flex justify-between items-center">
                                        <button
                                            onClick={clearFilters}
                                            className="text-xs text-gray-500 hover:text-white transition-colors flex items-center gap-1"
                                        >
                                            <X size={12} /> Clear All
                                        </button>
                                        <button
                                            onClick={() => setIsFilterOpen(false)}
                                            className="px-4 py-1.5 bg-white text-black text-xs font-bold rounded-md hover:bg-gray-200 transition-colors"
                                        >
                                            Done
                                        </button>
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>
                    </div>
                </div>

                {/* Table Header (Fixed) */}
                <div className={`grid ${GRID_COLS} gap-4 px-6 py-4 bg-white/5 border border-white/10 rounded-t-xl text-gray-400 text-sm font-medium transition-all duration-300`}>
                    <div>Product Name</div>
                    <div>Category</div>
                    <div>Batch Info</div>
                    <div>Expiry</div>
                    <div className="text-center">Stock Level</div>
                    <div className="text-right">Rate</div>
                    <div className="text-right">MRP</div>
                    {isEditMode && (
                        <div className="flex justify-center">
                            <button
                                onClick={toggleSelectAll}
                                className={`w-5 h-5 border-2 rounded flex items-center justify-center transition-colors ${processedInventory.length > 0 && processedInventory.every(item => selectedIds.has(getUniqueId(item)))
                                    ? 'bg-purple-600 border-purple-600'
                                    : 'border-slate-600 hover:border-slate-500'
                                    }`}
                            >
                                {processedInventory.length > 0 && processedInventory.every(item => selectedIds.has(getUniqueId(item))) && <Check size={14} className="text-white" />}
                            </button>
                        </div>
                    )}
                </div>
            </div>

            {/* 2. List Section (Scrollable) */}
            <div className="flex-1 overflow-y-auto pb-20 border-x border-b border-white/10 rounded-b-xl bg-white/5 backdrop-blur-sm custom-scrollbar">
                {loading ? (
                    <div className="flex items-center justify-center h-64 text-gray-400">
                        <Activity className="animate-spin mr-2" size={20} /> Loading inventory...
                    </div>
                ) : processedInventory.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-64 text-gray-400">
                        <Package size={48} className="mb-4 opacity-50" />
                        <p>No matching items found.</p>
                        <button onClick={clearFilters} className="mt-4 text-blue-400 hover:text-blue-300 text-sm">Clear Filters</button>
                    </div>
                ) : (
                    <div className="divide-y divide-white/5">
                        {processedInventory.map((item, idx) => {
                            const expiryStatus = getExpiryStatus(item.expiry_date);
                            const originalIndex = inventory.indexOf(item);
                            const uniqueId = getUniqueId(item);
                            const isSelected = selectedIds.has(uniqueId);

                            return (
                                <motion.div
                                    key={uniqueId}
                                    initial={{ opacity: 0, y: 5 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ delay: idx * 0.03 }}
                                    className={`grid ${GRID_COLS} gap-4 px-6 py-4 items-center transition-colors group ${isEditMode ? 'hover:bg-transparent' : 'hover:bg-white/5'
                                        } ${isSelected ? 'bg-purple-500/10' : ''}`}
                                >
                                    {/* Product Name */}
                                    <div className={`transition-opacity duration-300 ${isEditMode ? 'opacity-40' : 'opacity-100'}`}>
                                        <div className="font-medium text-white">{item.product_name}</div>
                                        <div className="text-xs text-gray-500">{item.manufacturer}</div>
                                    </div>

                                    {/* Category */}
                                    <div className={`transition-opacity duration-300 ${isEditMode ? 'opacity-40' : 'opacity-100'}`}>
                                        <span className="px-2 py-1 rounded-md bg-white/5 border border-white/10 text-xs text-gray-300">
                                            {item.dosage_form}
                                        </span>
                                    </div>

                                    {/* Batch */}
                                    <div className={`transition-opacity duration-300 ${isEditMode ? 'opacity-40' : 'opacity-100'}`}>
                                        <div className="text-gray-300 font-mono text-sm">{item.batch_number}</div>
                                    </div>

                                    {/* Expiry */}
                                    <div className={`transition-opacity duration-300 ${isEditMode ? 'opacity-40' : 'opacity-100'}`}>
                                        <div className={`flex items-center gap-2 text-sm ${expiryStatus === 'expired' ? 'text-red-400 font-bold' :
                                            expiryStatus === 'near_expiry' ? 'text-yellow-400' : 'text-gray-300'
                                            }`}>
                                            <Calendar size={14} />
                                            {item.expiry_date}
                                            {expiryStatus === 'expired' && <AlertTriangle size={14} />}
                                        </div>
                                    </div>

                                    {/* Stock (Editable) */}
                                    <div className="text-center">
                                        <div
                                            onClick={() => openEditModal(originalIndex, 'stock', item.quantity_packs)}
                                            className={`inline-flex flex-col items-center transition-all duration-300 rounded-lg p-2 ${isEditMode
                                                ? 'cursor-pointer border border-dashed border-blue-500/50 bg-blue-500/10 animate-pulse hover:bg-blue-500/20 hover:border-blue-400'
                                                : ''
                                                }`}
                                        >
                                            <span className={`font-bold text-lg ${isEditMode ? 'text-blue-300' :
                                                item.quantity_packs < 10 ? 'text-red-400' : 'text-white'
                                                }`}>
                                                {item.quantity_packs}
                                            </span>
                                            <span className="text-[10px] text-gray-500 uppercase tracking-wide">Packs</span>
                                        </div>
                                    </div>

                                    {/* Rate */}
                                    <div className="text-right">
                                        <div className="font-medium text-slate-400">
                                            ₹{(item.purchase_rate || 0).toFixed(2)}
                                        </div>
                                    </div>

                                    {/* MRP (Editable) */}
                                    <div className="text-right">
                                        <div
                                            onClick={() => openEditModal(originalIndex, 'mrp', item.mrp)}
                                            className={`inline-block transition-all duration-300 rounded-lg p-2 -mr-2 ${isEditMode
                                                ? 'cursor-pointer border border-dashed border-green-500/50 bg-green-500/10 animate-pulse hover:bg-green-500/20 hover:border-green-400'
                                                : ''
                                                }`}
                                        >
                                            <div className={`font-medium ${isEditMode ? 'text-green-300' : 'text-white'}`}>
                                                ₹{item.mrp.toFixed(2)}
                                            </div>
                                        </div>
                                    </div>

                                    {/* Checkbox (Edit Mode Only) */}
                                    {isEditMode && (
                                        <div className="flex justify-center">
                                            <button
                                                onClick={() => toggleSelection(uniqueId)}
                                                className={`w-5 h-5 border-2 rounded flex items-center justify-center transition-colors ${isSelected
                                                    ? 'bg-purple-600 border-purple-600'
                                                    : 'border-slate-600 hover:border-slate-500'
                                                    }`}
                                            >
                                                {isSelected && <Check size={14} className="text-white" />}
                                            </button>
                                        </div>
                                    )}
                                </motion.div>
                            );
                        })}
                    </div>
                )}
            </div>

            {/* Floating Action Bar (Selection Count) */}
            <AnimatePresence>
                {isEditMode && selectedIds.size > 0 && (
                    <motion.div
                        initial={{ opacity: 0, y: 50 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: 50 }}
                        className="absolute bottom-6 left-1/2 -translate-x-1/2 bg-[#1a1a1a] border border-white/10 shadow-2xl rounded-full px-6 py-3 flex items-center gap-4 z-50"
                    >
                        <div className="flex items-center gap-2">
                            <span className="bg-purple-600 text-white text-xs font-bold px-2 py-0.5 rounded-full">
                                {selectedIds.size}
                            </span>
                            <span className="text-sm font-medium text-gray-200">Items Selected</span>
                        </div>
                        <div className="h-4 w-px bg-white/10"></div>

                        {/* Delete Button */}
                        <button
                            onClick={handleDeleteSelected}
                            className="flex items-center gap-2 text-xs font-bold text-red-400 hover:text-red-300 transition-colors bg-red-500/10 hover:bg-red-500/20 px-3 py-1.5 rounded-lg border border-red-500/20"
                        >
                            <Trash2 size={14} />
                            Delete
                        </button>

                        <div className="h-4 w-px bg-white/10"></div>
                        <button
                            onClick={() => setSelectedIds(new Set())}
                            className="text-xs text-gray-400 hover:text-white transition-colors"
                        >
                            Clear Selection
                        </button>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Custom Scrollbar Styles */}
            <style>{`
                .custom-scrollbar::-webkit-scrollbar {
                    width: 6px;
                }
                .custom-scrollbar::-webkit-scrollbar-track {
                    background: rgba(255, 255, 255, 0.05);
                }
                .custom-scrollbar::-webkit-scrollbar-thumb {
                    background: rgba(255, 255, 255, 0.2);
                    border-radius: 10px;
                }
                .custom-scrollbar::-webkit-scrollbar-thumb:hover {
                    background: rgba(255, 255, 255, 0.3);
                }
            `}</style>

            <QuickEditModal
                isOpen={editModal.isOpen}
                onClose={() => setEditModal(prev => ({ ...prev, isOpen: false }))}
                title={editModal.field === 'stock' ? 'Update Stock Level' : 'Update MRP'}
                currentValue={editModal.currentValue}
                onSave={handleUpdate}
                unit={editModal.field === 'stock' ? 'Packs' : '₹'}
            />
        </div>
    );
};

export default InventoryView;
