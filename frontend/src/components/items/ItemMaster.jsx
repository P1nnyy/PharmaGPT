import React, { useState, useEffect } from 'react';
import { Package, Save, AlertCircle, CheckCircle, ArrowLeft } from 'lucide-react';
import { saveProduct, getReviewQueue, getAllProducts, getProductHistory } from '../../services/api';

// Sub-components
import { ItemSidebar } from './ItemSidebar';
import { ItemOverview } from './tabs/ItemOverview';
import { ItemPricing } from './tabs/ItemPricing';
import { ItemInventory } from './tabs/ItemInventory';
import { ItemHistory } from './tabs/ItemHistory';

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
        rack_location: '',
        manufacturer: '',
        salt_composition: '',
        category: '',
        supplier_name: '',
        last_purchase_date: '',
        saved_by: '',
        base_unit: 'Tablet',
        is_verified: false,
        is_enriched: false,
        packaging_variants: []
    });

    const [activeTab, setActiveTab] = useState('overview'); // 'overview' | 'pricing' | 'inventory' | 'packaging' | 'history'
    const [saving, setSaving] = useState(false);

    // Sidebar Lists
    const [sidebarTab, setSidebarTab] = useState('review'); // 'review' | 'all'
    const [reviewQueue, setReviewQueue] = useState([]);
    const [allItems, setAllItems] = useState([]);
    // const [reviewLoading, setReviewLoading] = useState(true); // Unused in render, but kept logic
    // const [allLoading, setAllLoading] = useState(false); // Unused

    // History
    const [history, setHistory] = useState([]);
    const [historyLoading, setHistoryLoading] = useState(false);

    // UI State
    const [searchTerm, setSearchTerm] = useState('');
    const [showMobileDetail, setShowMobileDetail] = useState(false);

    // Data Fetching
    const fetchQueue = async () => {
        try {
            const data = await getReviewQueue();
            setReviewQueue(data);
        } catch (err) {
            console.error("Failed to fetch review queue", err);
        }
    };

    const fetchAllItems = async () => {
        try {
            const data = await getAllProducts();
            setAllItems(data);
        } catch (err) {
            console.error("Failed to fetch all items", err);
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
        // Auto-fill Product Type from Category
        let suggestedUnit = 'Tablet';
        if (product.category) {
            const cat = product.category.toLowerCase();
            if (cat.includes('syp') || cat.includes('syrup') || cat.includes('liquid') || cat.includes('susp')) suggestedUnit = 'Syrup';
            else if (cat.includes('inj') || cat.includes('vial')) suggestedUnit = 'Injection';
            else if (cat.includes('cap')) suggestedUnit = 'Capsule';
        }

        setFormData(prev => ({
            ...prev,
            name: product.name || '',
            hsn_code: product.hsn_code || '',
            sale_price: product.sale_price ? parseFloat(parseFloat(product.sale_price).toFixed(2)) : 0,
            purchase_price: product.purchase_price ? parseFloat(parseFloat(product.purchase_price).toFixed(2)) : 0,
            tax_rate: product.tax_rate ?? (product.gst_percent ?? 0),
            opening_stock: product.opening_stock ?? (!product.is_verified ? (product.quantity ?? 0) : 0),
            min_stock: product.min_stock ?? 0,
            item_code: product.item_code || '',
            rack_location: product.rack_location || product.location || '',
            is_verified: product.is_verified,
            is_enriched: product.is_enriched || false,
            manufacturer: product.manufacturer || '',
            salt_composition: product.salt_composition || '',
            category: product.category || '',
            supplier_name: product.supplier_name || '',
            last_purchase_date: product.last_purchase_date || '',
            saved_by: product.saved_by || '',
            base_unit: product.base_unit || suggestedUnit,
            packaging_variants: (product.packaging_variants || []).map(v => ({
                ...v,
                unit_name: v.unit_name || '',
                pack_size: v.pack_size || '',
                mrp: v.mrp ?? 0,
                conversion_factor: v.conversion_factor ?? 1
            })),
            needs_review: product.needs_review
        }));

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
            tax_rate: 0, opening_stock: 0, min_stock: 0, rack_location: '',
            manufacturer: '', salt_composition: '', category: '',
            is_verified: false, packaging_variants: [], base_unit: 'Tablet'
        });
        setHistory([]);
        setShowMobileDetail(true);
    };

    const handleSave = async () => {
        try {
            setSaving(true);
            await saveProduct(formData);
            if (sidebarTab === 'review') fetchQueue();
            else fetchAllItems();
        } catch (error) {
            console.error("Save failed", error);
            alert('Failed to save product.');
        } finally {
            setSaving(false);
        }
    };

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
                </div>

                {/* Main Content Split */}
                <div className="flex flex-1 overflow-hidden relative">

                    {/* LEFT SIDEBAR: List */}
                    <div className={`w-full md:w-1/4 min-w-[300px] border-r border-slate-700 flex flex-col bg-slate-900/30 absolute md:relative inset-0 z-10 transition-transform duration-300 transform md:transform-none ${showMobileDetail ? '-translate-x-full md:translate-x-0' : 'translate-x-0'}`}>
                        <ItemSidebar
                            sidebarTab={sidebarTab}
                            setSidebarTab={setSidebarTab}
                            reviewQueue={reviewQueue}
                            allItems={allItems}
                            searchTerm={searchTerm}
                            setSearchTerm={setSearchTerm}
                            handleQueueItemClick={handleQueueItemClick}
                            handleNewItem={handleNewItem}
                            formData={formData}
                        />
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
                                    <div className="flex items-center gap-3">
                                        <h1 className="text-2xl font-bold text-white leading-tight">
                                            {formData.name || 'New Product'}
                                        </h1>
                                        {formData.item_code && (
                                            <span className="px-2 py-0.5 rounded-md bg-slate-700 text-slate-300 text-xs font-mono border border-slate-600">
                                                {formData.item_code}
                                            </span>
                                        )}
                                    </div>
                                    <div className="flex items-center gap-2 mt-1">
                                        {formData.is_verified ? (
                                            <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 text-[10px] font-bold border border-emerald-500/20 flex items-center gap-1">
                                                <CheckCircle className="w-3 h-3" /> VERIFIED
                                            </span>
                                        ) : (
                                            <span className="px-2 py-0.5 rounded-full bg-orange-500/10 text-orange-400 text-[10px] font-bold border border-orange-500/20 flex items-center gap-1">
                                                <AlertCircle className="w-3 h-3" /> DRAFT
                                            </span>
                                        )}
                                        {formData.base_unit && (
                                            <span className="px-2 py-0.5 rounded-full bg-slate-700 text-slate-300 text-[10px] font-bold border border-slate-600">
                                                {formData.base_unit}
                                            </span>
                                        )}
                                    </div>
                                </div>
                                <button
                                    onClick={handleSave}
                                    disabled={saving}
                                    className={`flex items-center gap-2 px-6 py-2 rounded-lg font-bold shadow-lg transition-all ${saving ? 'bg-slate-600 opacity-50' : 'bg-blue-600 hover:bg-blue-500 text-white'}`}
                                >
                                    <Save className="w-4 h-4" />
                                    {saving ? 'Saving...' : 'Save'}
                                </button>
                            </div>

                            {/* Tabs */}
                            <div className="flex gap-6 text-sm font-medium overflow-x-auto no-scrollbar">
                                {['overview', 'pricing', 'inventory_packaging', 'history'].map(tab => (
                                    <button
                                        key={tab}
                                        onClick={() => setActiveTab(tab)}
                                        className={`pb-3 capitalize transition-colors border-b-2 whitespace-nowrap px-1 ${activeTab === tab
                                            ? 'border-blue-500 text-white'
                                            : 'border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-600'
                                            }`}
                                    >
                                        {tab === 'inventory_packaging' ? 'Packaging/ Item Management' : tab}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Scrollable Content */}
                        <div className="flex-1 overflow-y-auto p-6 custom-scrollbar">
                            <div className="max-w-4xl mx-auto space-y-8 pb-20">

                                {/* OVERVIEW TAB */}
                                {activeTab === 'overview' && (
                                    <ItemOverview formData={formData} handleInputChange={handleInputChange} />
                                )}

                                {/* PRICING TAB */}
                                {activeTab === 'pricing' && (
                                    <ItemPricing formData={formData} handleInputChange={handleInputChange} />
                                )}

                                {/* INVENTORY & PACKAGING */}
                                {activeTab === 'inventory_packaging' && (
                                    <ItemInventory formData={formData} setFormData={setFormData} handleInputChange={handleInputChange} />
                                )}

                                {/* HISTORY TAB */}
                                {activeTab === 'history' && (
                                    <ItemHistory history={history} loading={historyLoading} />
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
