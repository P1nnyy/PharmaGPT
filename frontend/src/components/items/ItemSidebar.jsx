import React from 'react';
import { Search, Plus } from 'lucide-react';

export const ItemSidebar = ({ sidebarTab, setSidebarTab, reviewQueue, allItems, searchTerm, setSearchTerm, handleQueueItemClick, handleNewItem, formData }) => {
    return (
        <div className="w-full md:w-1/4 min-w-[300px] border-r border-slate-700 flex flex-col bg-slate-900/30 absolute md:relative inset-0 z-10">
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
                    .filter(item =>
                        (item.name || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
                        (item.item_code && item.item_code.toLowerCase().includes(searchTerm.toLowerCase()))
                    )
                    .map((item, idx) => (
                        <div
                            key={idx}
                            onClick={() => handleQueueItemClick(item)}
                            className={`p-3 rounded-lg border cursor-pointer transition-all hover:bg-slate-800 ${formData.name === item.name ? 'border-blue-500/50 bg-blue-500/10 ring-1 ring-blue-500/20' : 'border-slate-800 bg-slate-900/40'}`}
                        >
                            <div className="font-semibold text-sm text-slate-200 truncate flex items-center gap-2">
                                <span className="truncate">{item.name}</span>
                                {item.item_code && (
                                    <span className="shrink-0 px-1.5 py-0.5 rounded bg-slate-700 text-slate-300 text-[10px] font-mono border border-slate-600">
                                        {item.item_code}
                                    </span>
                                )}
                            </div>
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
    );
};
