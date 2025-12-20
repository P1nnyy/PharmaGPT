import React from 'react';
import { AlertCircle, Check, Plus, Download, Save, Loader2, Calendar, LayoutGrid, Package } from 'lucide-react';

const DataEditor = ({
    invoiceData,
    lineItems,
    warnings,
    successMsg,
    errorMsg,
    isSaving,
    isAnalyzing,
    onHeaderChange,
    onInputChange,
    onAddRow,
    onConfirm,
    onExport
}) => {

    if (!invoiceData && !isAnalyzing) {
        return (
            <div className="h-full flex flex-col items-center justify-center text-gray-500 p-8 text-center">
                <div className="w-16 h-16 bg-gray-800 rounded-full flex items-center justify-center mb-4">
                    <LayoutGrid className="w-8 h-8 text-gray-600" />
                </div>
                <h3 className="text-lg font-medium text-gray-400">No Data Yet</h3>
                <p className="text-sm text-gray-600 mt-2">Upload an invoice to see extracted data here.</p>
            </div>
        );
    }

    // Header Section Component (Shared)
    const InvoiceHeader = () => (
        <div className="p-4 md:p-6 bg-gray-800/50 backdrop-blur-sm border-b border-gray-700 shadow-md sticky top-0 z-20">
            {/* Notifications */}
            {warnings.length > 0 && (
                <div className="mb-4 p-3 bg-red-900/20 border border-red-500/30 rounded-lg animate-in fade-in slide-in-from-top-2">
                    <h4 className="flex items-center gap-2 text-red-400 font-bold mb-1 text-sm">
                        <AlertCircle className="w-4 h-4" /> Missing Items
                    </h4>
                    <ul className="text-xs text-red-200/70 list-disc list-inside space-y-0.5 pl-1">
                        {warnings.map((w, idx) => <li key={idx}>{w}</li>)}
                    </ul>
                </div>
            )}

            <div className="flex flex-col gap-4">
                {/* Title & Status */}
                <div className="flex justify-between items-start">
                    <h2 className="text-xl md:text-2xl font-bold text-white flex items-center gap-2">
                        Review Data
                        <span className="text-xs font-normal px-2 py-0.5 bg-indigo-500/20 text-indigo-300 rounded-full border border-indigo-500/30">
                            {lineItems.length} Items
                        </span>
                    </h2>

                    {successMsg && (
                        <div className="px-3 py-1.5 bg-green-500/20 text-green-300 rounded-full border border-green-500/30 flex items-center gap-2 text-xs md:text-sm animate-in fade-in">
                            <Check className="w-3 h-3 md:w-4 md:h-4" /> {successMsg}
                        </div>
                    )}
                    {errorMsg && (
                        <div className="px-3 py-1.5 bg-red-500/20 text-red-300 rounded-full border border-red-500/30 flex items-center gap-2 text-xs md:text-sm animate-in fade-in">
                            <AlertCircle className="w-3 h-3 md:w-4 md:h-4" /> {errorMsg}
                        </div>
                    )}
                </div>

                {/* Invoice Meta Fields */}
                {invoiceData ? (
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                        <div className="space-y-1">
                            <label className="text-[10px] uppercase tracking-wider text-gray-500 font-bold ml-1">Supplier</label>
                            <input
                                type="text"
                                value={invoiceData.Supplier_Name}
                                onChange={(e) => onHeaderChange('Supplier_Name', e.target.value)}
                                className="w-full bg-gray-900/50 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 outline-none transition-all placeholder-gray-600"
                                placeholder="Supplier Name"
                            />
                        </div>
                        <div className="space-y-1">
                            <label className="text-[10px] uppercase tracking-wider text-gray-500 font-bold ml-1">Invoice No</label>
                            <input
                                type="text"
                                value={invoiceData.Invoice_No}
                                onChange={(e) => onHeaderChange('Invoice_No', e.target.value)}
                                className="w-full bg-gray-900/50 border border-gray-700 rounded-lg px-3 py-2 text-sm font-mono focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 outline-none transition-all placeholder-gray-600"
                                placeholder="INV-000"
                            />
                        </div>
                        <div className="space-y-1">
                            <label className="text-[10px] uppercase tracking-wider text-gray-500 font-bold ml-1">Date</label>
                            <div className="relative">
                                <input
                                    type="text"
                                    value={invoiceData.Invoice_Date}
                                    onChange={(e) => onHeaderChange('Invoice_Date', e.target.value)}
                                    className="w-full bg-gray-900/50 border border-gray-700 rounded-lg pl-9 pr-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 outline-none transition-all placeholder-gray-600"
                                    placeholder="DD/MM/YYYY"
                                />
                                <Calendar className="w-4 h-4 text-gray-500 absolute left-3 top-1/2 -translate-y-1/2" />
                            </div>
                        </div>
                    </div>
                ) : (
                    // Skeleton Loader for Header
                    <div className="animate-pulse flex gap-4">
                        <div className="h-10 bg-gray-800 rounded w-1/3"></div>
                        <div className="h-10 bg-gray-800 rounded w-1/3"></div>
                        <div className="h-10 bg-gray-800 rounded w-1/3"></div>
                    </div>
                )}
            </div>
        </div>
    );

    return (
        <div className="flex flex-col h-full bg-gray-900 relative">
            <InvoiceHeader />

            {/* SCROLLABLE CONTENT AREA */}
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
                                                className="w-full bg-transparent outline-none text-gray-300 focus:text-white placeholder-gray-600 font-medium text-sm border-b border-transparent focus:border-indigo-500 transition-colors py-1"
                                                placeholder="Item Description"
                                            />
                                        </div>

                                        {/* Batch/Expiry Combined */}
                                        <div className="col-span-2 flex flex-col gap-1">
                                            <input
                                                value={item.Batch_No || ''}
                                                onChange={(e) => onInputChange(idx, 'Batch_No', e.target.value)}
                                                className="w-full bg-transparent outline-none text-xs font-mono text-gray-400 focus:text-indigo-300 placeholder-gray-700"
                                                placeholder="BATCH"
                                            />
                                            <input
                                                value={item.Expiry_Date || ''}
                                                onChange={(e) => onInputChange(idx, 'Expiry_Date', e.target.value)}
                                                className="w-full bg-transparent outline-none text-xs font-mono text-gray-500 focus:text-indigo-300 placeholder-gray-700"
                                                placeholder="EXPIRY"
                                            />
                                        </div>

                                        {/* MRP */}
                                        <div className="col-span-1">
                                            <input
                                                type="number"
                                                value={item.MRP || 0}
                                                onChange={(e) => onInputChange(idx, 'MRP', parseFloat(e.target.value))}
                                                className="w-full bg-transparent outline-none text-center font-mono text-sm text-gray-400 focus:text-white"
                                            />
                                        </div>

                                        {/* Qty */}
                                        <div className="col-span-1 flex justify-center">
                                            <input
                                                type="number"
                                                value={item.Standard_Quantity || 0}
                                                onChange={(e) => onInputChange(idx, 'Standard_Quantity', parseFloat(e.target.value))}
                                                className="w-16 bg-gray-800/50 rounded text-center font-mono text-sm text-indigo-300 font-bold focus:bg-gray-700 outline-none py-1 border border-transparent focus:border-indigo-500/50 transition-all"
                                            />
                                        </div>

                                        {/* Net Amount & Alert */}
                                        <div className="col-span-3 text-right flex items-center justify-end gap-3">
                                            {item.is_price_hike && (
                                                <div className="group/alert relative flex items-center justify-center w-8 h-8 bg-red-500/10 rounded-full animate-pulse">
                                                    <span className="text-sm">⚠️</span>
                                                    <span className="absolute bottom-full right-0 mb-2 w-32 bg-gray-950 text-white text-xs p-2 rounded border border-red-900 shadow-xl hidden group-hover/alert:block z-50">
                                                        Possible Price Hike detected
                                                    </span>
                                                </div>
                                            )}
                                            <input
                                                type="number"
                                                value={item.Net_Line_Amount || 0}
                                                onChange={(e) => onInputChange(idx, 'Net_Line_Amount', parseFloat(e.target.value))}
                                                className="w-24 bg-transparent outline-none font-mono text-right text-green-400 font-bold focus:text-green-300 text-base"
                                            />
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </>
                    ) : null}
                </div>

                {/* --- MOBILE VIEW (Cards) --- */}
                <div className="md:hidden flex flex-col gap-3">
                    {lineItems.map((item, idx) => (
                        <div
                            key={idx}
                            className={`bg-gray-800/40 rounded-xl p-4 border transition-all relative overflow-hidden ${item.is_price_hike ? 'border-red-500/50 shadow-[0_0_15px_-3px_rgba(239,68,68,0.2)]' : 'border-gray-700/50 shadow-sm'
                                }`}
                        >
                            {/* Card Header: Name & Amount */}
                            <div className="flex justify-between items-start mb-3 gap-2">
                                <div className="flex-1">
                                    <div className="flex items-center gap-2 mb-1">
                                        <span className="text-[10px] bg-gray-700/50 text-gray-500 px-1.5 py-0.5 rounded font-mono">#{idx + 1}</span>
                                        {item.is_price_hike && <span className="text-xs bg-red-500/20 text-red-300 px-1.5 py-0.5 rounded border border-red-500/30">Hike ⚠️</span>}
                                    </div>
                                    <input
                                        value={item.Standard_Item_Name || ''}
                                        onChange={(e) => onInputChange(idx, 'Standard_Item_Name', e.target.value)}
                                        className="w-full bg-transparent outline-none text-base font-semibold text-gray-100 placeholder-gray-600 focus:text-indigo-300"
                                        placeholder="Item Name"
                                    />
                                </div>
                                <div className="flex flex-col items-end">
                                    <span className="text-[10px] text-gray-500 uppercase">Net</span>
                                    <div className="relative">
                                        <span className="absolute left-0 top-1/2 -translate-y-1/2 text-gray-500 text-xs">₹</span>
                                        <input
                                            type="number"
                                            value={item.Net_Line_Amount || 0}
                                            onChange={(e) => onInputChange(idx, 'Net_Line_Amount', parseFloat(e.target.value))}
                                            className="w-20 bg-transparent outline-none font-mono text-right text-lg font-bold text-green-400 focus:text-green-300 pl-3"
                                        />
                                    </div>
                                </div>
                            </div>

                            {/* Card Body: Grid Inputs */}
                            <div className="grid grid-cols-2 gap-3 bg-gray-900/30 p-3 rounded-lg border border-gray-800/50">
                                {/* QTY */}
                                <div>
                                    <label className="text-[10px] text-gray-500 uppercase tracking-wide block mb-1">Qty</label>
                                    <div className="flex items-center gap-2 bg-gray-800 rounded px-2 py-1.5 border border-gray-700/50 focus-within:border-indigo-500/50 focus-within:ring-1 focus-within:ring-indigo-500/50">
                                        <Package className="w-3 h-3 text-indigo-400" />
                                        <input
                                            type="number"
                                            value={item.Standard_Quantity || 0}
                                            onChange={(e) => onInputChange(idx, 'Standard_Quantity', parseFloat(e.target.value))}
                                            className="w-full bg-transparent outline-none text-sm font-mono text-white text-center"
                                        />
                                    </div>
                                </div>

                                {/* MRP */}
                                <div>
                                    <label className="text-[10px] text-gray-500 uppercase tracking-wide block mb-1">MRP</label>
                                    <div className="flex items-center gap-2 bg-gray-800 rounded px-2 py-1.5 border border-gray-700/50">
                                        <span className="text-xs text-gray-500 font-sans">₹</span>
                                        <input
                                            type="number"
                                            value={item.MRP || 0}
                                            onChange={(e) => onInputChange(idx, 'MRP', parseFloat(e.target.value))}
                                            className="w-full bg-transparent outline-none text-sm font-mono text-gray-300 text-center"
                                        />
                                    </div>
                                </div>

                                {/* BATCH */}
                                <div>
                                    <label className="text-[10px] text-gray-500 uppercase tracking-wide block mb-1">Batch</label>
                                    <input
                                        value={item.Batch_No || ''}
                                        onChange={(e) => onInputChange(idx, 'Batch_No', e.target.value)}
                                        className="w-full bg-transparent border-b border-gray-700 text-xs py-1 outline-none focus:border-indigo-500 font-mono text-gray-400"
                                        placeholder="BATCH"
                                    />
                                </div>

                                {/* EXPIRY */}
                                <div>
                                    <label className="text-[10px] text-gray-500 uppercase tracking-wide block mb-1">Expiry</label>
                                    <input
                                        value={item.Expiry_Date || ''}
                                        onChange={(e) => onInputChange(idx, 'Expiry_Date', e.target.value)}
                                        className="w-full bg-transparent border-b border-gray-700 text-xs py-1 outline-none focus:border-indigo-500 font-mono text-gray-400"
                                        placeholder="MM/YY"
                                    />
                                </div>
                            </div>
                        </div>
                    ))}
                </div>

                {/* Add Row Button */}
                <div className="mt-4 px-2 md:px-6">
                    <button
                        onClick={onAddRow}
                        className="w-full py-3 md:py-4 rounded-xl border-2 border-dashed border-gray-700 text-gray-500 hover:text-indigo-400 hover:border-indigo-500/50 hover:bg-gray-800/30 transition-all flex items-center justify-center gap-2 text-sm font-bold uppercase tracking-wide"
                    >
                        <Plus className="w-5 h-5" /> Add New Item
                    </button>
                </div>

            </div>

            {/* --- FOOTER ACTIONS --- */}
            {lineItems.length > 0 && (
                <div className="p-4 bg-gray-900 border-t border-gray-800 shadow-[0_-5px_20px_rgba(0,0,0,0.5)] z-30">
                    <div className="flex flex-col md:flex-row justify-end gap-3 md:gap-4 items-center">

                        {/* Total Display */}
                        <div className="w-full md:w-auto flex justify-between md:justify-start items-center gap-4 bg-gray-800/50 px-4 py-2 rounded-lg border border-gray-700 mb-2 md:mb-0">
                            <span className="text-gray-400 text-sm font-medium">Grand Total</span>
                            <span className="font-mono text-xl md:text-2xl font-bold text-indigo-400">
                                ₹{lineItems.reduce((acc, item) => acc + (parseFloat(item.Net_Line_Amount) || 0), 0).toFixed(2)}
                            </span>
                        </div>

                        <div className="flex w-full md:w-auto gap-3">
                            <button
                                onClick={onExport}
                                className="flex-1 md:flex-none flex items-center justify-center gap-2 px-6 py-3 bg-gray-800 hover:bg-gray-700 text-white font-medium rounded-xl border border-gray-700 hover:border-gray-600 transition-all shadow-lg"
                            >
                                <Download className="w-5 h-5" />
                                <span className="hidden md:inline">Export Excel</span>
                                <span className="md:hidden">Excel</span>
                            </button>

                            <button
                                onClick={onConfirm}
                                disabled={isSaving}
                                className="flex-[2] md:flex-none flex items-center justify-center gap-2 px-8 py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-bold rounded-xl shadow-lg shadow-indigo-500/20 hover:shadow-indigo-500/40 transition-all disabled:opacity-50 disabled:scale-95"
                            >
                                {isSaving ? <Loader2 className="animate-spin w-5 h-5" /> : <Save className="w-5 h-5" />}
                                <span>Save Invoice</span>
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default DataEditor;
