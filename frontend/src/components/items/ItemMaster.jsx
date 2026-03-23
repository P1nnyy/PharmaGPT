import React, { useState, useEffect } from 'react';
import { Package } from 'lucide-react';
import { useItemData } from './hooks/useItemData';
import { useItemForm } from './hooks/useItemForm';
import ItemList from './ItemList';
import ItemDetails from './ItemDetails';
import ItemForm from './ItemForm';
import { inferProductForm } from './utils/itemUtils';

const ItemMaster = () => {
    // Shared Data Hook
    const { reviewQueue, allItems, categories, loading, refreshData } = useItemData();
    
    // UI State
    const [sidebarTab, setSidebarTab] = useState('review'); // 'review' | 'all'
    const [searchTerm, setSearchTerm] = useState('');
    const [activeTab, setActiveTab] = useState('overview');
    const [showMobileDetail, setShowMobileDetail] = useState(false);
    
    // Item Selection & Editing
    const { formData, setFormData, handleChange, handleSave, saving, resetForm } = useItemForm();
    const [isEditingInModal, setIsEditingInModal] = useState(false);

    // Initial Selection (Auto-select first item in review queue if available)
    useEffect(() => {
        if (reviewQueue.length > 0 && !formData.name && !formData.original_name) {
            handleSelect(reviewQueue[0]);
        }
    }, [reviewQueue]);

    const handleSelect = (product) => {
        const inferred = inferProductForm(product);
        setFormData(inferred);
        setShowMobileDetail(true);
    };

    const handleNewItem = () => {
        resetForm();
        setIsEditingInModal(true);
    };

    const onSaveComplete = async () => {
        await refreshData();
        // Product state in formData is already updated by handleSave in the hook
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

                <div className="flex flex-1 overflow-hidden relative">
                    <ItemList
                        reviewQueue={reviewQueue}
                        allItems={allItems}
                        sidebarTab={sidebarTab}
                        setSidebarTab={setSidebarTab}
                        searchTerm={searchTerm}
                        onSearchChange={setSearchTerm}
                        onSelect={handleSelect}
                        onNewItem={handleNewItem}
                        loading={loading}
                        selectedName={formData.name || formData.original_name}
                        showMobileDetail={showMobileDetail}
                    />

                    {formData.name || formData.original_name ? (
                        <ItemDetails
                            formData={formData}
                            setFormData={setFormData}
                            activeTab={activeTab}
                            setActiveTab={setActiveTab}
                            onSave={async () => {
                                const res = await handleSave();
                                if (res.success) await onSaveComplete();
                            }}
                            saving={saving}
                            setShowMobileDetail={setShowMobileDetail}
                            onInputChange={(e) => handleChange(e.target.name, e.target.value)}
                            categories={categories}
                            showMobileDetail={showMobileDetail}
                        />
                    ) : (
                        <div className="flex-1 h-full flex flex-col items-center justify-center text-slate-500 bg-slate-800">
                             <Package className="w-16 h-16 mb-4 opacity-20" />
                             <p className="text-lg font-medium">No Item Selected</p>
                             <p className="text-sm opacity-60">Pick an item from the sidebar to manage it.</p>
                        </div>
                    )}

                    {isEditingInModal && (
                        <ItemForm
                            item={formData}
                            onClose={() => setIsEditingInModal(false)}
                            onSave={async () => {
                                await onSaveComplete();
                                setIsEditingInModal(false);
                            }}
                        />
                    )}
                </div>
            </div>
        </div>
    );
};

export default ItemMaster;
