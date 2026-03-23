import React from 'react';

const ItemCard = ({ item, isSelected, onClick }) => {
    return (
        <div
            onClick={onClick}
            className={`p-3 rounded-lg border cursor-pointer transition-all hover:bg-slate-800 ${isSelected ? 'border-blue-500/50 bg-blue-500/10 ring-1 ring-blue-500/20' : 'border-slate-800 bg-slate-900/40'}`}
        >
            <div className="font-semibold text-sm text-slate-200 truncate flex items-center gap-2">
                <span className="truncate">{item?.name || 'Unknown Item'}</span>
                {item?.item_code && (
                    <span className="shrink-0 px-1.5 py-0.5 rounded bg-slate-700 text-slate-300 text-[10px] font-mono border border-slate-600">
                        {item.item_code}
                    </span>
                )}
            </div>
            <div className="flex justify-between items-center mt-1">
                <span className="text-[10px] text-slate-500 flex items-center gap-1">
                    {item?.hsn_code || item?.HSN || 'No HSN'}
                </span>
                <span className="text-[10px] font-mono text-emerald-400">₹{item?.sale_price || 0}</span>
            </div>
        </div>
    );
};

export default ItemCard;
