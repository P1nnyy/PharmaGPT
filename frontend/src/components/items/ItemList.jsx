import React from 'react';
import { Search, Plus, Loader2 } from 'lucide-react';
import ItemCard from './components/ItemCard';

const ItemList = ({ 
    reviewQueue, 
    allItems, 
    sidebarTab, 
    setSidebarTab, 
    searchTerm, 
    onSearchChange, 
    onSelect, 
    onNewItem, 
    loading,
    selectedName,
    showMobileDetail
}) => {
    const items = sidebarTab === 'review' ? reviewQueue : allItems;
    const filtered = items.filter(item =>
        item && (
            (item.name || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
            (item.item_code && item.item_code.toLowerCase().includes(searchTerm.toLowerCase()))
        )
    );

    return (
        <div className={`w-full md:w-1/4 h-full min-w-[300px] border-r border-slate-700 flex flex-col bg-slate-900/30 absolute md:relative inset-0 z-10 transition-transform duration-300 transform md:transform-none ${showMobileDetail ? '-translate-x-full md:translate-x-0' : 'translate-x-0'}`}>
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
                        onClick={onNewItem}
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
                        onChange={(e) => onSearchChange(e.target.value)}
                        className="w-full bg-slate-900 border border-slate-700 rounded-lg pl-8 pr-3 py-2 text-xs text-slate-300 focus:border-blue-500 focus:outline-none"
                    />
                    <Search className="absolute left-2.5 top-2.5 w-3.5 h-3.5 text-slate-500" />
                </div>
            </div>

            {/* List Area */}
            <div className="flex-1 overflow-y-auto p-2 space-y-2 custom-scrollbar">
                {loading && (
                    <div className="flex items-center justify-center p-8">
                        <Loader2 className="w-5 h-5 animate-spin text-slate-500" />
                    </div>
                )}
                
                {!loading && filtered.map((item, idx) => (
                    <ItemCard
                        key={idx}
                        item={item}
                        isSelected={selectedName === item?.name}
                        onClick={() => onSelect(item)}
                    />
                ))}
                
                {!loading && filtered.length === 0 && (
                    <div className="text-center py-8 text-slate-500 text-xs">No items found</div>
                )}
            </div>
        </div>
    );
};

export default ItemList;
