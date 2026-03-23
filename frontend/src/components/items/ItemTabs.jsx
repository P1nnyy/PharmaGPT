import React from 'react';
import ItemEditor from './components/ItemEditor';
import ItemPricingTab from './components/ItemPricingTab';
import ItemInventoryTab from './components/ItemInventoryTab';
import ItemHistoryTab from './components/ItemHistoryTab';

const ItemTabs = ({ item, activeTab, onTabChange, onInputChange, onFormDataChange, categories, history, historyLoading }) => {
    const tabs = [
        { id: 'overview', label: 'Overview' },
        { id: 'inventory_packaging', label: 'Inventory & Packaging' },
        { id: 'pricing', label: 'Pricing' },
        { id: 'history', label: 'Purchase History' }
    ];

    return (
        <div className="flex flex-col h-full">
            {/* Tab Navigation */}
            <div className="flex border-b border-slate-700 bg-slate-900/50 px-4">
                {tabs.map(tab => (
                    <button
                        key={tab.id}
                        onClick={() => onTabChange(tab.id)}
                        className={`px-4 py-3 text-sm font-medium border-b-2 transition-all ${
                            activeTab === tab.id
                                ? 'border-blue-500 text-blue-400 bg-blue-500/5'
                                : 'border-transparent text-slate-500 hover:text-slate-300 hover:bg-slate-800/50'
                        }`}
                    >
                        {tab.label}
                    </button>
                ))}
            </div>

            {/* Tab Content */}
            <div className="flex-1 overflow-y-auto p-6 custom-scrollbar">
                <div className="max-w-4xl mx-auto space-y-8 pb-20">
                    {activeTab === 'overview' && (
                        <ItemEditor formData={item} handleInputChange={onInputChange} />
                    )}

                    {activeTab === 'inventory_packaging' && (
                        <ItemInventoryTab 
                            formData={item} 
                            setFormData={onFormDataChange} 
                            handleInputChange={onInputChange} 
                            categories={categories}
                        />
                    )}

                    {activeTab === 'pricing' && (
                        <ItemPricingTab formData={item} handleInputChange={onInputChange} />
                    )}

                    {activeTab === 'history' && (
                        <ItemHistoryTab history={history} loading={historyLoading} />
                    )}
                </div>
            </div>
        </div>
    );
};

export default ItemTabs;
