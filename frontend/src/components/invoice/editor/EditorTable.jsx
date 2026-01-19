import React from 'react';
import { Plus, Calculator } from 'lucide-react';

const EditorTable = ({ lineItems, onInputChange, onAddRow, readOnly = false }) => {
    return (
        <div className="flex-1 overflow-y-auto overflow-x-hidden p-2 md:p-0 pb-32 md:pb-0">
            {/* Added bottom padding on mobile for floating bar */}

            {/* --- DESKTOP VIEW (Table) --- */}
            <div className="hidden md:block">
                {lineItems.length > 0 ? (
                    <>
                        <div className="sticky top-0 z-10 bg-gray-900 pt-2 border-b border-gray-800">
                            <div className="grid grid-cols-12 gap-4 mb-2 text-xs font-bold text-gray-500 uppercase tracking-wider px-4">
                                <div className="col-span-1 text-center">#</div>
                                <div className="col-span-4">Item Name</div>
                                <div className="col-span-2">Batch / Expiry</div>
                                <div className="col-span-1 text-center">MRP</div>
                                <div className="col-span-1 text-center">Qty</div>
                                <div className="col-span-3 text-right">Net Amount</div>
                            </div>
                        </div>

                        <div className="divide-y divide-gray-800/50">
                            {lineItems.map((item, idx) => (
                                <div
                                    key={idx}
                                    className={`grid grid-cols-12 gap-4 items-center py-3 px-4 transition-colors group ${item.is_price_hike ? 'bg-red-900/10 hover:bg-red-900/20 border-l-2 border-red-500' : 'hover:bg-gray-800/30 border-l-2 border-transparent hover:border-gray-700'
                                        }`}
                                >
                                    {/* Index */}
                                    <div className="col-span-1 text-center text-gray-600 font-mono text-xs">{idx + 1}</div>

                                    {/* Name */}
                                    <div className="col-span-4">
                                        <input
                                            value={item.Standard_Item_Name || ''}
                                            onChange={(e) => onInputChange(idx, 'Standard_Item_Name', e.target.value)}
                                            className="w-full bg-transparent outline-none text-gray-300 focus:text-white placeholder-gray-600 font-medium text-sm border-b border-transparent focus:border-indigo-500 transition-colors py-1 disabled:opacity-75 disabled:cursor-not-allowed"
                                            placeholder="Item Description"
                                            disabled={readOnly}
                                        />
                                    </div>

                                    {/* Batch/Expiry Combined */}
                                    <div className="col-span-2 flex flex-col gap-1">
                                        <input
                                            value={item.Batch_No || ''}
                                            onChange={(e) => onInputChange(idx, 'Batch_No', e.target.value)}
                                            className="w-full bg-transparent outline-none text-xs font-mono text-gray-400 focus:text-indigo-300 placeholder-gray-700 disabled:opacity-75"
                                            placeholder="BATCH"
                                            disabled={readOnly}
                                        />
                                        <input
                                            value={item.Expiry_Date || ''}
                                            onChange={(e) => onInputChange(idx, 'Expiry_Date', e.target.value)}
                                            className="w-full bg-transparent outline-none text-xs font-mono text-gray-500 focus:text-indigo-300 placeholder-gray-700 disabled:opacity-75"
                                            placeholder="EXPIRY"
                                            disabled={readOnly}
                                        />
                                    </div>

                                    {/* MRP */}
                                    <div className="col-span-1">
                                        <input
                                            type="number"
                                            value={item.MRP || 0}
                                            onChange={(e) => onInputChange(idx, 'MRP', parseFloat(e.target.value))}
                                            className="w-full bg-transparent outline-none text-center font-mono text-sm text-gray-400 focus:text-white disabled:opacity-75"
                                            disabled={readOnly}
                                        />
                                    </div>

                                    {/* Qty */}
                                    <div className="col-span-1 flex justify-center">
                                        <input
                                            type="number"
                                            value={item.Standard_Quantity || 0}
                                            onChange={(e) => onInputChange(idx, 'Standard_Quantity', parseFloat(e.target.value))}
                                            className="w-16 bg-gray-800/50 rounded text-center font-mono text-sm text-indigo-300 font-bold focus:bg-gray-700 outline-none py-1 border border-transparent focus:border-indigo-500/50 transition-all disabled:opacity-75 disabled:bg-transparent"
                                            disabled={readOnly}
                                        />
                                    </div>

                                    {/* Net Amount & Alert */}
                                    <div className="col-span-3 text-right flex items-center justify-end gap-3">
                                        {/* Price Hike Warning */}
                                        {item.is_price_hike && (
                                            <div className="group/alert relative flex items-center justify-center w-8 h-8 bg-red-500/10 rounded-full animate-pulse">
                                                <span className="text-sm">⚠️</span>
                                                <span className="absolute bottom-full right-0 mb-2 w-32 bg-gray-950 text-white text-xs p-2 rounded border border-red-900 shadow-xl hidden group-hover/alert:block z-50">
                                                    Possible Price Hike detected
                                                </span>
                                            </div>
                                        )}

                                        {/* Global Reconcile Calc Indicator */}
                                        {item.Is_Calculated && (
                                            <div className="group/calc relative flex items-center justify-center w-8 h-8 bg-amber-500/10 rounded-full">
                                                <Calculator className="w-4 h-4 text-amber-400" />
                                                <span className="absolute bottom-full right-0 mb-2 w-48 bg-gray-900 text-amber-300 text-[10px] p-2 rounded border border-amber-900 shadow-xl hidden group-hover/calc:block z-50 pointer-events-none">
                                                    {item.Logic_Note || "Auto-Corrected to match Invoice Total"}
                                                </span>
                                            </div>
                                        )}

                                        <input
                                            type="number"
                                            value={item.Net_Line_Amount || 0}
                                            onChange={(e) => onInputChange(idx, 'Net_Line_Amount', parseFloat(e.target.value))}
                                            className={`w-24 bg-transparent outline-none font-mono text-right font-bold text-base disabled:text-green-500/80
                                                ${item.Is_Calculated
                                                    ? 'text-amber-400 focus:text-amber-300 bg-amber-900/20 rounded px-1'
                                                    : 'text-green-400 focus:text-green-300'
                                                }
                                            `}
                                            disabled={readOnly}
                                        />
                                    </div>
                                </div>
                            ))}
                        </div>
                    </>
                ) : null}
            </div>

            {/* --- MOBILE VIEW (Compact Cards) --- */}
            <div className="md:hidden flex flex-col gap-1">
                {lineItems.map((item, idx) => (
                    <div
                        key={idx}
                        className={`bg-gray-800/40 rounded-lg p-2 border transition-all relative overflow-hidden ${item.is_price_hike ? 'border-red-500/50 shadow-[0_0_15px_-3px_rgba(239,68,68,0.2)]' : 'border-gray-700/50 shadow-sm'
                            }`}
                    >
                        {/* Card Header: Name & Amount */}
                        <div className="flex justify-between items-start mb-1 gap-2">
                            <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-1 mb-0.5">
                                    <span className="text-[9px] bg-gray-700/50 text-gray-500 px-1 py-0.5 rounded font-mono">#{idx + 1}</span>
                                    {item.is_price_hike && <span className="text-[10px] bg-red-500/20 text-red-300 px-1 py-0.5 rounded border border-red-500/30">Hike ⚠️</span>}
                                </div>
                                <input
                                    value={item.Standard_Item_Name || ''}
                                    onChange={(e) => onInputChange(idx, 'Standard_Item_Name', e.target.value)}
                                    className="w-full bg-transparent outline-none text-sm font-semibold text-gray-100 placeholder-gray-600 focus:text-indigo-300 truncate disabled:opacity-100"
                                    placeholder="Item Name"
                                    disabled={readOnly}
                                />
                            </div>
                            <div className="flex flex-col items-end shrink-0">
                                <div className="relative flex items-center gap-1">
                                    {item.Is_Calculated && (
                                        <Calculator className="w-3 h-3 text-amber-400" />
                                    )}
                                    <span className="absolute left-0 top-1/2 -translate-y-1/2 text-gray-500 text-[10px]">₹</span>
                                    <input
                                        type="number"
                                        value={item.Net_Line_Amount || 0}
                                        onChange={(e) => onInputChange(idx, 'Net_Line_Amount', parseFloat(e.target.value))}
                                        className={`w-16 bg-transparent outline-none font-mono text-right text-base font-bold pl-2 disabled:text-green-500
                                             ${item.Is_Calculated
                                                ? 'text-amber-400 focus:text-amber-300 bg-amber-900/20 rounded'
                                                : 'text-green-400 focus:text-green-300'
                                            }
                                        `}
                                        disabled={readOnly}
                                    />
                                </div>
                            </div>
                        </div>

                        {/* Card Body: Compact Grid Inputs */}
                        <div className="grid grid-cols-4 gap-1 bg-gray-900/30 p-1.5 rounded border border-gray-800/50">
                            {/* QTY */}
                            <div className="col-span-1">
                                <label className="text-[9px] text-gray-500 uppercase block mb-0.5">Qty</label>
                                <input
                                    type="number"
                                    value={item.Standard_Quantity || 0}
                                    onChange={(e) => onInputChange(idx, 'Standard_Quantity', parseFloat(e.target.value))}
                                    className="w-full bg-gray-800 rounded px-1 py-1 text-center font-mono text-xs text-white border border-gray-700/50 focus:border-indigo-500/50 outline-none disabled:bg-gray-800/50"
                                    disabled={readOnly}
                                />
                            </div>

                            {/* MRP */}
                            <div className="col-span-1">
                                <label className="text-[9px] text-gray-500 uppercase block mb-0.5">MRP</label>
                                <input
                                    type="number"
                                    value={item.MRP || 0}
                                    onChange={(e) => onInputChange(idx, 'MRP', parseFloat(e.target.value))}
                                    className="w-full bg-transparent border-b border-gray-700 text-center font-mono text-xs text-gray-300 py-1 outline-none focus:border-indigo-500 disabled:border-transparent"
                                    disabled={readOnly}
                                />
                            </div>

                            {/* BATCH */}
                            <div className="col-span-1">
                                <label className="text-[9px] text-gray-500 uppercase block mb-0.5">Batch</label>
                                <input
                                    value={item.Batch_No || ''}
                                    onChange={(e) => onInputChange(idx, 'Batch_No', e.target.value)}
                                    className="w-full bg-transparent border-b border-gray-700 text-xs py-1 outline-none focus:border-indigo-500 font-mono text-gray-400 disabled:border-transparent"
                                    placeholder="BATCH"
                                    disabled={readOnly}
                                />
                            </div>

                            {/* EXPIRY */}
                            <div className="col-span-1">
                                <label className="text-[9px] text-gray-500 uppercase block mb-0.5">Exp</label>
                                <input
                                    value={item.Expiry_Date || ''}
                                    onChange={(e) => onInputChange(idx, 'Expiry_Date', e.target.value)}
                                    className="w-full bg-transparent border-b border-gray-700 text-xs py-1 outline-none focus:border-indigo-500 font-mono text-gray-400 disabled:border-transparent"
                                    placeholder="MY"
                                    disabled={readOnly}
                                />
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            {/* Add Row Button - Hide if readOnly */}
            {!readOnly && (
                <div className="mt-4 px-2 md:px-6">
                    <button
                        onClick={onAddRow}
                        className="w-full py-3 md:py-4 rounded-xl border-2 border-dashed border-gray-700 text-gray-500 hover:text-indigo-400 hover:border-indigo-500/50 hover:bg-gray-800/30 transition-all flex items-center justify-center gap-2 text-sm font-bold uppercase tracking-wide"
                    >
                        <Plus className="w-5 h-5" /> Add New Item
                    </button>
                </div>
            )}

        </div>
    );
};

export default EditorTable;
