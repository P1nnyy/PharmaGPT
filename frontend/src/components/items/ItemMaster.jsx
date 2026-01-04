import React, { useState, useEffect } from 'react';
import { Package, Save, Barcode, Search, DollarSign, Warehouse, Tag } from 'lucide-react';
import { searchProducts, saveProduct } from '../../services/api';

const ItemMaster = () => {
    // State
    const [formData, setFormData] = useState({
        name: '',
        item_code: '',
        hsn_code: '',
        sale_price: 0,
        purchase_price: 0,
        tax_rate: 0,
        opening_stock: 0,
        min_stock: 0,
        location: ''
    });

    const [activeTab, setActiveTab] = useState('pricing');
    const [suggestions, setSuggestions] = useState([]);
    const [showDropdown, setShowDropdown] = useState(false);
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);

    // Autosuggest Logic
    useEffect(() => {
        const fetchSuggestions = async () => {
            // Only search if name has length > 2
            if (formData.name && formData.name.length > 2) {
                try {
                    setLoading(true);
                    const results = await searchProducts(formData.name);
                    setSuggestions(results);
                    setShowDropdown(true);
                } catch (error) {
                    console.error("Search failed", error);
                } finally {
                    setLoading(false);
                }
            } else {
                setSuggestions([]);
                setShowDropdown(false);
            }
        };

        // Debounce to prevent API spam
        const timeoutId = setTimeout(fetchSuggestions, 300);
        return () => clearTimeout(timeoutId);
    }, [formData.name]);

    const handleInputChange = (e) => {
        const { name, value } = e.target;

        // Auto-parse numbers for numeric fields
        const isNumeric = ['sale_price', 'purchase_price', 'tax_rate', 'opening_stock', 'min_stock'].includes(name);

        setFormData(prev => ({
            ...prev,
            [name]: isNumeric ? (parseFloat(value) || 0) : value
        }));
    };

    // Special handler for name to avoid number parsing/clearing weirdness
    const handleNameChange = (e) => {
        setFormData(prev => ({ ...prev, name: e.target.value }));
    };

    const handleSuggestionClick = (product) => {
        setFormData(prev => ({
            ...prev,
            name: product.name,
            hsn_code: product.hsn_code || prev.hsn_code || '',
            sale_price: product.sale_price !== undefined ? product.sale_price : prev.sale_price,
            // Preserve other fields as they might probably be specific to this batch/entry if the global product is vague
            // But if we want to fill usage:
        }));
        setShowDropdown(false);
    };

    const handleSave = async () => {
        try {
            setSaving(true);
            await saveProduct(formData);
            alert('Product Saved Successfully!');
            // Optional: Clear form or redirect
            // setFormData({ name: '', ... });
        } catch (error) {
            console.error("Save failed", error);
            alert('Failed to save product. Check console.');
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="bg-slate-900 min-h-screen text-slate-200 p-6 flex items-center justify-center">
            <div className="w-full max-w-4xl bg-slate-800 rounded-xl shadow-2xl overflow-hidden border border-slate-700">
                {/* Header */}
                <div className="p-6 border-b border-slate-700 flex items-center gap-3 bg-slate-800">
                    <div className="p-3 bg-blue-600/20 rounded-lg text-blue-400">
                        <Package className="w-6 h-6" />
                    </div>
                    <div>
                        <h2 className="text-xl font-bold text-white">Item Master</h2>
                        <p className="text-slate-400 text-sm">Create or Edit Product Inventory</p>
                    </div>
                </div>

                {/* Content */}
                <div className="p-8 space-y-8 bg-slate-800/50">
                    {/* Top Section */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        {/* Name with Autosuggest */}
                        <div className="col-span-2 relative z-20">
                            <label className="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Item Name</label>
                            <div className="relative">
                                <input
                                    type="text"
                                    name="name"
                                    value={formData.name}
                                    onChange={handleNameChange}
                                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-3 focus:outline-none focus:border-blue-500 text-white placeholder-slate-600 transition-all font-medium"
                                    placeholder="Search or Enter Item Name..."
                                    autoComplete="off"
                                />
                                {loading && <div className="absolute right-3 top-3.5 text-slate-500 text-xs animate-pulse">Searching...</div>}
                            </div>

                            {/* Dropdown */}
                            {showDropdown && suggestions.length > 0 && (
                                <div className="absolute w-full mt-2 bg-slate-800 border border-slate-600 rounded-lg shadow-2xl max-h-60 overflow-y-auto animate-in fade-in zoom-in-95 duration-200">
                                    {suggestions.map((item, idx) => (
                                        <div
                                            key={idx}
                                            onClick={() => handleSuggestionClick(item)}
                                            className="p-3 hover:bg-slate-700 cursor-pointer flex justify-between items-center border-b border-slate-700/50 last:border-0 group"
                                        >
                                            <div className="flex flex-col">
                                                <span className="text-sm font-medium text-slate-200 group-hover:text-blue-400 transition-colors">{item.name}</span>
                                                {item.hsn_code && <span className="text-[10px] text-slate-500">HSN: {item.hsn_code}</span>}
                                            </div>
                                            <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 px-2 py-1 rounded">₹{item.sale_price}</span>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>

                        {/* Codes */}
                        <div>
                            <label className="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Item Code / SKU</label>
                            <div className="relative group">
                                <Barcode className="absolute left-3 top-3 w-5 h-5 text-slate-500 group-focus-within:text-blue-400 transition-colors" />
                                <input
                                    type="text"
                                    name="item_code"
                                    value={formData.item_code}
                                    onChange={handleInputChange}
                                    className="w-full bg-slate-900 border border-slate-700 rounded-lg pl-10 pr-4 py-2.5 focus:outline-none focus:border-blue-500 text-white placeholder-slate-600 transition-all"
                                    placeholder="Auto or Manual SKU"
                                />
                            </div>
                        </div>
                        <div>
                            <label className="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">HSN / SAC Code</label>
                            <div className="relative group">
                                <Tag className="absolute left-3 top-3 w-5 h-5 text-slate-500 group-focus-within:text-blue-400 transition-colors" />
                                <input
                                    type="text"
                                    name="hsn_code"
                                    value={formData.hsn_code}
                                    onChange={handleInputChange}
                                    className="w-full bg-slate-900 border border-slate-700 rounded-lg pl-10 pr-4 py-2.5 focus:outline-none focus:border-blue-500 text-white placeholder-slate-600 transition-all"
                                    placeholder="Tax Code"
                                />
                            </div>
                        </div>
                    </div>

                    {/* Tabs */}
                    <div className="border-b border-slate-700 flex gap-8">
                        <button
                            onClick={() => setActiveTab('pricing')}
                            className={`pb-3 text-sm font-bold tracking-wide transition-all relative ${activeTab === 'pricing' ? 'text-blue-400' : 'text-slate-500 hover:text-slate-300'
                                }`}
                        >
                            Pricing & Tax
                            {activeTab === 'pricing' && <div className="absolute bottom-0 left-0 w-full h-0.5 bg-blue-500 rounded-t-full shadow-[0_0_10px_rgba(59,130,246,0.5)]" />}
                        </button>
                        <button
                            onClick={() => setActiveTab('stock')}
                            className={`pb-3 text-sm font-bold tracking-wide transition-all relative ${activeTab === 'stock' ? 'text-emerald-400' : 'text-slate-500 hover:text-slate-300'
                                }`}
                        >
                            Stock & Location
                            {activeTab === 'stock' && <div className="absolute bottom-0 left-0 w-full h-0.5 bg-emerald-500 rounded-t-full shadow-[0_0_10px_rgba(16,185,129,0.5)]" />}
                        </button>
                    </div>

                    {/* Tab Content */}
                    <div className="min-h-[180px]">
                        {activeTab === 'pricing' ? (
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 animate-in slide-in-from-left-4 fade-in duration-300">
                                <div className="group">
                                    <label className="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Sale Price (MRP)</label>
                                    <div className="relative">
                                        <DollarSign className="absolute left-3 top-3 w-5 h-5 text-emerald-500 group-focus-within:text-emerald-400 transition-colors" />
                                        <input
                                            type="number"
                                            name="sale_price"
                                            value={formData.sale_price}
                                            onChange={handleInputChange}
                                            className="w-full bg-slate-900 border border-slate-700 rounded-lg pl-10 pr-4 py-2.5 focus:outline-none focus:border-emerald-500 text-emerald-400 font-mono text-lg font-bold placeholder-slate-700 transition-all"
                                            placeholder="0.00"
                                        />
                                    </div>
                                </div>
                                <div className="group">
                                    <label className="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Purchase Price</label>
                                    <div className="relative">
                                        <DollarSign className="absolute left-3 top-3 w-5 h-5 text-slate-500 group-focus-within:text-blue-400 transition-colors" />
                                        <input
                                            type="number"
                                            name="purchase_price"
                                            value={formData.purchase_price}
                                            onChange={handleInputChange}
                                            className="w-full bg-slate-900 border border-slate-700 rounded-lg pl-10 pr-4 py-2.5 focus:outline-none focus:border-blue-500 text-white font-mono placeholder-slate-700 transition-all"
                                            placeholder="0.00"
                                        />
                                    </div>
                                </div>
                                <div>
                                    <label className="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Tax Rate (GST)</label>
                                    <div className="relative">
                                        <select
                                            name="tax_rate"
                                            value={formData.tax_rate}
                                            onChange={handleInputChange}
                                            className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 focus:outline-none focus:border-blue-500 text-white appearance-none cursor-pointer hover:bg-slate-800 transition-all"
                                        >
                                            <option value={0}>0% (Exempt)</option>
                                            <option value={5}>5%</option>
                                            <option value={12}>12%</option>
                                            <option value={18}>18%</option>
                                            <option value={28}>28%</option>
                                        </select>
                                        <div className="absolute right-4 top-3.5 pointer-events-none text-slate-500 text-[10px]">▼</div>
                                    </div>
                                </div>
                            </div>
                        ) : (
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 animate-in slide-in-from-right-4 fade-in duration-300">
                                <div>
                                    <label className="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Opening Stock</label>
                                    <input
                                        type="number"
                                        name="opening_stock"
                                        value={formData.opening_stock}
                                        onChange={handleInputChange}
                                        className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 focus:outline-none focus:border-blue-500 text-white font-mono placeholder-slate-700 transition-all"
                                        placeholder="0"
                                    />
                                </div>
                                <div>
                                    <label className="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Min Alert Stock</label>
                                    <input
                                        type="number"
                                        name="min_stock"
                                        value={formData.min_stock}
                                        onChange={handleInputChange}
                                        className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 focus:outline-none focus:border-orange-500 text-white font-mono placeholder-slate-700 transition-all"
                                        placeholder="0"
                                    />
                                </div>
                                <div className="group">
                                    <label className="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Rack / Location</label>
                                    <div className="relative">
                                        <Warehouse className="absolute left-3 top-3 w-5 h-5 text-slate-500 group-focus-within:text-blue-400 transition-colors" />
                                        <input
                                            type="text"
                                            name="location"
                                            value={formData.location}
                                            onChange={handleInputChange}
                                            className="w-full bg-slate-900 border border-slate-700 rounded-lg pl-10 pr-4 py-2.5 focus:outline-none focus:border-blue-500 text-white placeholder-slate-700 transition-all"
                                            placeholder="Row-A1"
                                        />
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                {/* Footer */}
                <div className="p-6 bg-slate-900/50 border-t border-slate-700 flex justify-end">
                    <button
                        onClick={handleSave}
                        disabled={saving}
                        className="flex items-center gap-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white px-8 py-3 rounded-lg font-bold shadow-lg transition-all transform active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
                    >
                        <Save className="w-5 h-5" />
                        {saving ? 'Saving...' : 'Save Item'}
                    </button>
                </div>
            </div>
        </div>
    );
};

export default ItemMaster;
