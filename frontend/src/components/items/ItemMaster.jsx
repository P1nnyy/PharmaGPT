import React, { useState, useEffect } from 'react';
import { Package, Save, Search, DollarSign, Warehouse, Tag, AlertCircle, CheckCircle, ArrowLeft, Plus, X, Check, FlaskConical, Stethoscope, Factory } from 'lucide-react';
import { saveProduct, getReviewQueue, getAllProducts, getProductHistory, renameProduct, linkProductAlias } from '../../services/api';

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
        location: '',

        // New Fields
        manufacturer: '',
        salt_composition: '',
        category: '',
        // schedule: '', // Removed as per request
        supplier_name: '',
        last_purchase_date: '',
        saved_by: '',

        is_verified: false,
        packaging_variants: []
    });

    const [activeTab, setActiveTab] = useState('overview'); // 'overview' | 'pricing' | 'inventory' | 'packaging' | 'history'
    const [saving, setSaving] = useState(false);

    // Sidebar Lists
    const [sidebarTab, setSidebarTab] = useState('review'); // 'review' | 'all'
    const [reviewQueue, setReviewQueue] = useState([]);
    const [reviewLoading, setReviewLoading] = useState(true);
    const [allItems, setAllItems] = useState([]);
    const [allLoading, setAllLoading] = useState(false);

    // History
    const [history, setHistory] = useState([]);
    const [historyLoading, setHistoryLoading] = useState(false);

    // Rename & Review State
    const [isRenaming, setIsRenaming] = useState(false);
    const [renameValue, setRenameValue] = useState('');
    const [showRenameInput, setShowRenameInput] = useState(false);
    const [incomingAlias, setIncomingAlias] = useState('');

    // UI State
    const [searchTerm, setSearchTerm] = useState('');
    const [showMobileDetail, setShowMobileDetail] = useState(false);

    // Data Fetching
    const fetchQueue = async () => {
        try {
            setReviewLoading(true);
            const data = await getReviewQueue();
            setReviewQueue(data);
        } catch (err) {
            console.error("Failed to fetch review queue", err);
        } finally {
            setReviewLoading(false);
        }
    };

    const fetchAllItems = async () => {
        try {
            setAllLoading(true);
            const data = await getAllProducts();
            setAllItems(data);
        } catch (err) {
            console.error("Failed to fetch all items", err);
        } finally {
            setAllLoading(false);
        }
    };

    useEffect(() => {
        fetchQueue();
    }, []);

    useEffect(() => {
        if (sidebarTab === 'all' && allItems.length === 0) {
            fetchAllItems();
        }
    }, [sidebarTab]);

    // Handlers
    const handleInputChange = (e) => {
        const { name, value } = e.target;
        const isNumeric = ['sale_price', 'purchase_price', 'tax_rate', 'opening_stock', 'min_stock'].includes(name);
        setFormData(prev => ({
            ...prev,
            [name]: isNumeric ? (parseFloat(value) || 0) : value
        }));
    };

    const handleQueueItemClick = (product) => {
        populateForm(product);
        setShowMobileDetail(true);
    };

    const populateForm = (product) => {
        setFormData(prev => ({
            ...prev,
            name: product.name || '',
            hsn_code: product.hsn_code || '',
            sale_price: product.sale_price ?? 0,
            purchase_price: product.purchase_price ?? 0,
            tax_rate: product.tax_rate ?? 0,
            opening_stock: product.opening_stock ?? 0,
            min_stock: product.min_stock ?? 0,
            item_code: product.item_code || '',
            location: product.location || '',
            is_verified: product.is_verified,

            // New Fields
            manufacturer: product.manufacturer || '',
            salt_composition: product.salt_composition || '',
            category: product.category || '',
            // schedule: product.schedule || '',
            supplier_name: product.supplier_name || '',
            last_purchase_date: product.last_purchase_date || '',
            saved_by: product.saved_by || '',

            packaging_variants: (product.packaging_variants || []).map(v => ({
                ...v,
                unit_name: v.unit_name || '',
                pack_size: v.pack_size || '',
                mrp: v.mrp ?? 0,
                conversion_factor: v.conversion_factor ?? 1
            })),
            needs_review: product.needs_review
        }));

        setIncomingAlias(product.incoming_name || '');
        setRenameValue(product.name || '');
        setShowRenameInput(false);

        // Fetch History
        if (product.name) {
            setHistoryLoading(true);
            getProductHistory(product.name).then(data => {
                setHistory(data);
                setHistoryLoading(false);
            }).catch(err => {
                console.error("Failed to fetch history", err);
                setHistoryLoading(false);
            });
        }
    };

    const handleNewItem = () => {
        setFormData({
            name: '', item_code: '', hsn_code: '', sale_price: 0, purchase_price: 0,
            tax_rate: 0, opening_stock: 0, min_stock: 0, location: '',
            manufacturer: '', salt_composition: '', category: '', schedule: '',
            is_verified: false, packaging_variants: []
        });
        setHistory([]);
        setShowMobileDetail(true);
    };

    const handleSave = async () => {
        try {
            setSaving(true);
            await saveProduct(formData);

            // Refresh logic
            if (sidebarTab === 'review') fetchQueue();
            else fetchAllItems();

            // Show toast or alert (Using alert for now)
            // alert('Product Saved Successfully!'); 
        } catch (error) {
            console.error("Save failed", error);
            alert('Failed to save product.');
        } finally {
            setSaving(false);
        }
    };

    // --- Render Helpers ---

    const renderInput = (label, name, type = 'text', icon = null, placeholder = '') => (
        <div className="space-y-1">
            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1">
                {icon} {label}
            </label>
            <input
                type={type}
                name={name}
                value={formData[name]}
                onChange={handleInputChange}
                placeholder={placeholder}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none transition-colors"
            />
        </div>
    );

    return (
        <div className="bg-slate-900 h-full text-slate-200">
            <div className="w-full h-full bg-slate-800 rounded-xl shadow-2xl overflow-hidden border border-slate-700 flex flex-col">

                {/* Header */}
                <div className="p-4 border-b border-slate-700 flex items-center justify-between bg-slate-800 shrink-0">
                    <div className="flex items-center gap-3">
                        <div className="p-2 bg-blue-600/20 rounded-lg text-blue-400">
                            <Package className="w-5 h-5" />
                        </div>
                        <div>
                            <h2 className="text-lg font-bold text-white leading-tight">Item Master</h2>
                            <p className="text-slate-400 text-xs">Pharma Inventory Management</p>
                        </div>
                    </div>
                    {/* Global Actions */}
                </div>

                {/* Main Content Split */}
                <div className="flex flex-1 overflow-hidden relative">

                    {/* LEFT SIDEBAR: List */}
                    <div className={`w-full md:w-1/4 min-w-[300px] border-r border-slate-700 flex flex-col bg-slate-900/30 absolute md:relative inset-0 z-10 transition-transform duration-300 transform md:transform-none ${showMobileDetail ? '-translate-x-full md:translate-x-0' : 'translate-x-0'}`}>
                        {/* Sidebar Tabs */}
                        <div className="p-3 pb-0">
                            <div className="flex rounded-lg bg-slate-900 p-1 mb-3 border border-slate-700">
                                <button
                                    onClick={() => setSidebarTab('review')}
                                    className={`flex-1 py-1.5 text-xs font-bold rounded-md transition-all ${sidebarTab === 'review' ? 'bg-slate-700 text-white shadow' : 'text-slate-500 hover:text-slate-300'}`}
                                >
                                    Review {reviewQueue.length > 0 && `(${reviewQueue.length})`}
                                </button>
                                <button
                                    onClick={() => setSidebarTab('all')}
                                    className={`flex-1 py-1.5 text-xs font-bold rounded-md transition-all ${sidebarTab === 'all' ? 'bg-slate-700 text-white shadow' : 'text-slate-500 hover:text-slate-300'}`}
                                >
                                    All Items
                                </button>
                                <button
                                    onClick={handleNewItem}
                                    className="ml-1 px-2 py-1.5 rounded-md bg-emerald-600/20 text-emerald-400 border border-emerald-600/50 hover:bg-emerald-600/30"
                                >
                                    <Plus className="w-4 h-4" />
                                </button>
                            </div>

                            {/* Search */}
                            <div className="relative mb-2">
                                <input
                                    type="text"
                                    placeholder="Filter..."
                                    value={searchTerm}
                                    onChange={(e) => setSearchTerm(e.target.value)}
                                    className="w-full bg-slate-900 border border-slate-700 rounded-lg pl-8 pr-3 py-2 text-xs text-slate-300 focus:border-blue-500 focus:outline-none"
                                />
                                <Search className="absolute left-2.5 top-2.5 w-3.5 h-3.5 text-slate-500" />
                            </div>
                        </div>

                        {/* List Area */}
                        <div className="flex-1 overflow-y-auto p-2 space-y-2 custom-scrollbar">
                            {(sidebarTab === 'review' ? reviewQueue : allItems)
                                .filter(item => item.name.toLowerCase().includes(searchTerm.toLowerCase()))
                                .map((item, idx) => (
                                    <div
                                        key={idx}
                                        onClick={() => handleQueueItemClick(item)}
                                        className={`p-3 rounded-lg border cursor-pointer transition-all hover:bg-slate-800 ${formData.name === item.name ? 'border-blue-500/50 bg-blue-500/10 ring-1 ring-blue-500/20' : 'border-slate-800 bg-slate-900/40'}`}
                                    >
                                        <div className="font-semibold text-sm text-slate-200 truncate">{item.name}</div>
                                        <div className="flex justify-between items-center mt-1">
                                            <span className="text-[10px] text-slate-500 flex items-center gap-1">
                                                {item.hsn_code || 'No HSN'}
                                            </span>
                                            <span className="text-[10px] font-mono text-emerald-400">₹{item.sale_price}</span>
                                        </div>
                                    </div>
                                ))
                            }
                            {((sidebarTab === 'review' ? reviewQueue : allItems).length === 0) && (
                                <div className="text-center py-8 text-slate-500 text-xs">No items found</div>
                            )}
                        </div>
                    </div>

                    {/* RIGHT PANEL: Details Form */}
                    <div className={`flex-1 flex flex-col bg-slate-800 absolute md:relative inset-0 z-20 transition-transform duration-300 ${showMobileDetail ? 'translate-x-0' : 'translate-x-full md:translate-x-0'}`}>

                        {/* Mobile Header */}
                        <div className="md:hidden flex items-center gap-2 p-4 border-b border-slate-700 text-slate-400 hover:text-white cursor-pointer" onClick={() => setShowMobileDetail(false)}>
                            <ArrowLeft className="w-5 h-5" />
                            <span className="font-bold text-sm">Back</span>
                        </div>

                        {/* Detail Header & Tabs */}
                        <div className="px-6 pt-6 pb-0 flex flex-col gap-4 border-b border-slate-700 bg-slate-800 z-10">
                            {/* Title Row */}
                            <div className="flex justify-between items-start">
                                <div className="space-y-1 flex-1 mr-4">
                                    <h1 className="text-2xl font-bold text-white leading-tight">
                                        {formData.name || 'New Product'}
                                    </h1>
                                    <div className="flex items-center gap-2">
                                        {formData.is_verified ? (
                                            <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 text-[10px] font-bold border border-emerald-500/20 flex items-center gap-1">
                                                <CheckCircle className="w-3 h-3" /> VERIFIED
                                            </span>
                                        ) : (
                                            <span className="px-2 py-0.5 rounded-full bg-orange-500/10 text-orange-400 text-[10px] font-bold border border-orange-500/20 flex items-center gap-1">
                                                <AlertCircle className="w-3 h-3" /> DRAFT
                                            </span>
                                        )}
                                        {formData.category && (
                                            <span className="px-2 py-0.5 rounded-full bg-slate-700 text-slate-300 text-[10px] font-bold border border-slate-600">
                                                {formData.category}
                                            </span>
                                        )}
                                    </div>
                                </div>
                                <button
                                    onClick={handleSave}
                                    disabled={saving}
                                    className={`flex items-center gap-2 px-6 py-2 rounded-lg font-bold shadow-lg transition-all ${saving ? 'bg-slate-600 opacity-50' : 'bg-blue-600 hover:bg-blue-500 text-white'
                                        }`}
                                >
                                    <Save className="w-4 h-4" />
                                    {saving ? 'Saving...' : 'Save'}
                                </button>
                            </div>

                            {/* Tabs */}
                            <div className="flex gap-6 text-sm font-medium overflow-x-auto no-scrollbar">
                                {['overview', 'pricing', 'inventory', 'packaging', 'history'].map(tab => (
                                    <button
                                        key={tab}
                                        onClick={() => setActiveTab(tab)}
                                        className={`pb-3 capitalize transition-colors border-b-2 whitespace-nowrap px-1 ${activeTab === tab
                                            ? 'border-blue-500 text-white'
                                            : 'border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-600'
                                            }`}
                                    >
                                        {tab}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Scrollable Content */}
                        <div className="flex-1 overflow-y-auto p-6 custom-scrollbar">
                            <div className="max-w-4xl mx-auto space-y-8 pb-20">

                                {/* OVERVIEW TAB */}
                                {activeTab === 'overview' && (
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
                                        <div className="col-span-2">
                                            {renderInput('Product Name', 'name', 'text', <Tag className="w-3 h-3" />, 'Enter product name')}
                                        </div>


                                        {renderInput('Manufacturer', 'manufacturer', 'text', <Factory className="w-3 h-3" />, 'Cipla, Sun Pharma...')}
                                        {renderInput('Salt Composition', 'salt_composition', 'text', <FlaskConical className="w-3 h-3" />, 'Paracetamol 500mg...')}

                                        {renderInput('Category', 'category', 'text', <Package className="w-3 h-3" />, 'Tablet, Syrup, Injection')}


                                        {/* Source Information (Read Only) */}
                                        <div className="col-span-2 grid grid-cols-1 md:grid-cols-3 gap-6 p-4 bg-slate-900/50 rounded-xl border border-dashed border-slate-700">
                                            {renderInput('Supplier Name', 'supplier_name', 'text', <Warehouse className="w-3 h-3 text-slate-500" />, 'Read Only')}
                                            {renderInput('Purchase Date', 'last_purchase_date', 'text', <Tag className="w-3 h-3 text-slate-500" />, 'Read Only')}
                                            {renderInput('Saved By', 'saved_by', 'text', <Tag className="w-3 h-3 text-slate-500" />, 'System')}
                                        </div>

                                        {renderInput('Item Code / SKU', 'item_code', 'text', <Search className="w-3 h-3" />, 'Internal SKU')}
                                    </div>
                                )}

                                {/* PRICING TAB (ERP REDESIGN) */}
                                {activeTab === 'pricing' && (
                                    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">

                                        {/* 1. Metric Cards (Real-time Analysis) */}
                                        <div className="grid grid-cols-3 gap-4">
                                            {/* Landing Cost */}
                                            <div className="bg-slate-900/50 p-4 rounded-xl border border-slate-700">
                                                <div className="text-slate-500 text-[10px] font-bold uppercase tracking-wider mb-1">Effective Landing Cost</div>
                                                <div className="text-2xl font-mono font-bold text-white">
                                                    ₹{((formData.purchase_price || 0) * (1 + (formData.tax_rate || 0) / 100)).toFixed(2)}
                                                </div>
                                                <div className="text-[10px] text-slate-400 mt-1">Base + {formData.tax_rate}% GST</div>
                                            </div>

                                            {/* Tax Amount */}
                                            <div className="bg-slate-900/50 p-4 rounded-xl border border-slate-700">
                                                <div className="text-slate-500 text-[10px] font-bold uppercase tracking-wider mb-1">Tax Amount</div>
                                                <div className="text-2xl font-mono font-bold text-blue-400">
                                                    ₹{((formData.purchase_price || 0) * ((formData.tax_rate || 0) / 100)).toFixed(2)}
                                                </div>
                                                <div className="text-[10px] text-slate-400 mt-1">Input Credit Available</div>
                                            </div>

                                            {/* Margin Analysis */}
                                            {(() => {
                                                const landing = (formData.purchase_price || 0) * (1 + (formData.tax_rate || 0) / 100);
                                                const margin = (formData.sale_price || 0) - landing;
                                                const marginPercent = formData.sale_price > 0 ? (margin / formData.sale_price) * 100 : 0;
                                                const isHigh = marginPercent > 25;
                                                const isLow = marginPercent < 15;

                                                return (
                                                    <div className={`p-4 rounded-xl border ${isHigh ? 'bg-emerald-500/10 border-emerald-500/30' : isLow ? 'bg-red-500/10 border-red-500/30' : 'bg-amber-500/10 border-amber-500/30'}`}>
                                                        <div className={`text-[10px] font-bold uppercase tracking-wider mb-1 ${isHigh ? 'text-emerald-400' : isLow ? 'text-red-400' : 'text-amber-400'}`}>Net Margin</div>
                                                        <div className="flex items-end gap-2">
                                                            <div className={`text-2xl font-mono font-bold ${isHigh ? 'text-emerald-300' : isLow ? 'text-red-300' : 'text-amber-300'}`}>
                                                                {marginPercent.toFixed(1)}%
                                                            </div>
                                                            <div className="text-sm font-medium opacity-80 mb-1">
                                                                (₹{margin.toFixed(2)})
                                                            </div>
                                                        </div>
                                                        <div className="text-[10px] mt-1 opacity-70">Profit per Unit</div>
                                                    </div>
                                                );
                                            })()}
                                        </div>

                                        {/* 2. Detailed Input Grid */}
                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">

                                            {/* Cost Side */}
                                            <div className="space-y-4">
                                                <h3 className="text-xs font-bold text-slate-500 uppercase border-b border-slate-700 pb-2 mb-4">Cost Structure</h3>
                                                {renderInput('Purchase Price (Base Rate)', 'purchase_price', 'number', <DollarSign className="w-3 h-3 text-slate-400" />)}
                                                {renderInput('Tax Rate (GST %)', 'tax_rate', 'number', <span className="text-xs font-bold">%</span>)}
                                                {renderInput('HSN / SAC Code', 'hsn_code', 'text', <Search className="w-3 h-3" />)}
                                            </div>

                                            {/* Revenue Side */}
                                            <div className="space-y-4">
                                                <h3 className="text-xs font-bold text-slate-500 uppercase border-b border-slate-700 pb-2 mb-4">Revenue & Pricing</h3>

                                                <div className="p-1 bg-emerald-500/5 rounded-xl border border-emerald-500/20">
                                                    {renderInput('Sale Price (MRP)', 'sale_price', 'number', <DollarSign className="w-3 h-3 text-emerald-400" />)}
                                                </div>

                                                <div className="p-3 bg-slate-900 rounded-lg border border-slate-800 mt-4">
                                                    <div className="flex justify-between items-center text-xs mb-2">
                                                        <span className="text-slate-400">Trade Discount (Scheme)</span>
                                                        <span className="text-slate-500 italic">Coming Soon</span>
                                                    </div>
                                                    <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
                                                        <div className="h-full bg-slate-700 w-0"></div>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                )}

                                {/* INVENTORY TAB */}
                                {activeTab === 'inventory' && (
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
                                        {renderInput('Opening Stock', 'opening_stock', 'number', <Warehouse className="w-3 h-3" />)}
                                        {renderInput('Minimum Stock Alert', 'min_stock', 'number', <AlertCircle className="w-3 h-3" />)}
                                        <div className="col-span-2">
                                            {renderInput('Rack Location', 'location', 'text', <Tag className="w-3 h-3" />, 'A-12-04')}
                                        </div>
                                    </div>
                                )}

                                {/* PACKAGING TAB */}
                                {activeTab === 'packaging' && (
                                    <div className="animate-in fade-in slide-in-from-bottom-2 duration-300">
                                        <div className="bg-slate-900/50 rounded-xl border border-slate-700 p-4">
                                            <div className="flex justify-between items-center mb-4">
                                                <h3 className="text-sm font-bold text-slate-300 uppercase">Packaging Hierarchy</h3>
                                                <button onClick={() => setFormData(p => ({ ...p, packaging_variants: [...p.packaging_variants, { unit_name: 'Box', pack_size: '1x10', mrp: 0, conversion_factor: 10 }] }))} className="text-xs bg-slate-800 hover:bg-slate-700 px-3 py-1.5 rounded transition-colors text-blue-400 border border-slate-600">
                                                    + Add Level
                                                </button>
                                            </div>
                                            <div className="space-y-3">
                                                {formData.packaging_variants.length === 0 && (
                                                    <div className="text-center py-6 text-slate-500 text-sm italic">No packaging defined. Add a variant like "Strip" or "Box".</div>
                                                )}
                                                {formData.packaging_variants.map((variant, idx) => (
                                                    <div key={idx} className="grid grid-cols-12 gap-2 bg-slate-800 p-3 rounded-lg border border-slate-700 items-start">
                                                        <div className="col-span-3 space-y-1">
                                                            <label className="text-[9px] text-slate-500 uppercase">Unit Name</label>
                                                            <input type="text" value={variant.unit_name} onChange={e => { const v = [...formData.packaging_variants]; v[idx].unit_name = e.target.value; setFormData(p => ({ ...p, packaging_variants: v })) }} className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs" />
                                                        </div>
                                                        <div className="col-span-3 space-y-1">
                                                            <label className="text-[9px] text-slate-500 uppercase">Pack Size</label>
                                                            <input type="text" value={variant.pack_size} onChange={e => { const v = [...formData.packaging_variants]; v[idx].pack_size = e.target.value; setFormData(p => ({ ...p, packaging_variants: v })) }} className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs" />
                                                        </div>
                                                        <div className="col-span-2 space-y-1">
                                                            <label className="text-[9px] text-slate-500 uppercase">MRP</label>
                                                            <input type="number" value={variant.mrp} onChange={e => { const v = [...formData.packaging_variants]; v[idx].mrp = parseFloat(e.target.value); setFormData(p => ({ ...p, packaging_variants: v })) }} className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs text-right" />
                                                        </div>
                                                        <div className="col-span-3 space-y-1">
                                                            <label className="text-[9px] text-slate-500 uppercase">Base Units</label>
                                                            <input type="number" value={variant.conversion_factor} onChange={e => { const v = [...formData.packaging_variants]; v[idx].conversion_factor = parseFloat(e.target.value); setFormData(p => ({ ...p, packaging_variants: v })) }} className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs text-center" />
                                                        </div>
                                                        <div className="col-span-1 flex justify-end pt-4">
                                                            <button onClick={() => { const v = formData.packaging_variants.filter((_, i) => i !== idx); setFormData(p => ({ ...p, packaging_variants: v })) }} className="text-slate-500 hover:text-red-400">
                                                                <X className="w-4 h-4" />
                                                            </button>
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    </div>
                                )}

                                {/* HISTORY TAB */}
                                {activeTab === 'history' && (
                                    <div className="animate-in fade-in slide-in-from-bottom-2 duration-300">
                                        <div className="bg-slate-900/50 rounded-xl border border-slate-700 overflow-hidden">
                                            <table className="w-full text-left text-xs text-slate-300">
                                                <thead className="bg-slate-800 text-slate-500 font-bold uppercase">
                                                    <tr>
                                                        <th className="px-4 py-3">Date</th>
                                                        <th className="px-4 py-3">Supplier</th>
                                                        <th className="px-4 py-3 text-right">Qty</th>
                                                        <th className="px-4 py-3 text-right">Rate</th>
                                                    </tr>
                                                </thead>
                                                <tbody className="divide-y divide-slate-700/50">
                                                    {historyLoading ? (<tr><td colSpan="4" className="p-4 text-center text-slate-500">Loading...</td></tr>)
                                                        : history.length === 0 ? (<tr><td colSpan="4" className="p-4 text-center text-slate-500">No Purchase History</td></tr>)
                                                            : history.map((h, i) => (
                                                                <tr key={i} className="hover:bg-slate-800/50">
                                                                    <td className="px-4 py-2">{h.date}</td>
                                                                    <td className="px-4 py-2">{h.supplier}</td>
                                                                    <td className="px-4 py-2 text-right">{h.quantity}</td>
                                                                    <td className="px-4 py-2 text-right text-emerald-400">₹{h.amount}</td>
                                                                </tr>
                                                            ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    </div>
                                )}

                            </div>
                        </div>

                    </div>
                </div>
            </div>
        </div>
    );
};

export default ItemMaster;
