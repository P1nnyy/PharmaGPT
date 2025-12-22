import React from 'react';
import { AlertCircle, Check, Calendar } from 'lucide-react';

const EditorHeader = ({
    invoiceData,
    lineItems,
    warnings,
    successMsg,
    errorMsg,
    onHeaderChange
}) => {
    const [isHeaderExpanded, setIsHeaderExpanded] = React.useState(false);

    return (
        <div className="p-3 md:p-6 bg-gray-800/50 backdrop-blur-sm border-b border-gray-700 shadow-md sticky top-0 z-20">
            {/* Notifications */}
            {warnings.length > 0 && (
                <div className="mb-2 p-2 bg-red-900/20 border border-red-500/30 rounded-lg animate-in fade-in slide-in-from-top-2">
                    <h4 className="flex items-center gap-2 text-red-400 font-bold mb-1 text-xs md:text-sm">
                        <AlertCircle className="w-3 h-3 md:w-4 md:h-4" /> Missing Items
                    </h4>
                    <ul className="text-[10px] md:text-xs text-red-200/70 list-disc list-inside space-y-0.5 pl-1">
                        {warnings.map((w, idx) => <li key={idx}>{w}</li>)}
                    </ul>
                </div>
            )}

            <div className="flex flex-col gap-2 md:gap-4">
                {/* Title & Status */}
                <div className="flex justify-between items-center">
                    <div className="flex items-center gap-2" onClick={() => setIsHeaderExpanded(!isHeaderExpanded)}>
                        <h2 className="text-lg md:text-2xl font-bold text-white flex items-center gap-2 cursor-pointer select-none">
                            Review Data
                            <span className="text-[10px] md:text-xs font-normal px-2 py-0.5 bg-indigo-500/20 text-indigo-300 rounded-full border border-indigo-500/30">
                                {lineItems.length}
                            </span>
                        </h2>
                        <span className={`text-gray-500 transition-transform duration-200 ${isHeaderExpanded ? 'rotate-180' : ''}`}>▼</span>
                    </div>

                    <div className="flex gap-2">
                        {successMsg && (
                            <div className="px-2 py-1 bg-green-500/20 text-green-300 rounded-full border border-green-500/30 flex items-center gap-1 text-[10px] md:text-sm animate-in fade-in">
                                <Check className="w-3 h-3" /> <span className="hidden md:inline">{successMsg}</span>
                            </div>
                        )}
                        {errorMsg && (
                            <div className="px-2 py-1 bg-red-500/20 text-red-300 rounded-full border border-red-500/30 flex items-center gap-1 text-[10px] md:text-sm animate-in fade-in">
                                <AlertCircle className="w-3 h-3" /> <span className="hidden md:inline">{errorMsg}</span>
                            </div>
                        )}
                    </div>
                </div>

                {/* Collapsible Area */}
                <div className={`transition-all duration-300 overflow-hidden ${isHeaderExpanded ? 'max-h-96 opacity-100' : 'max-h-0 opacity-0 md:max-h-96 md:opacity-100'}`}>
                    {invoiceData ? (
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-2">
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
                                <label className="text-[10px] uppercase tracking-wider text-gray-500 font-bold ml-1">Phone / Invoice #</label>
                                <input
                                    type="text"
                                    value={invoiceData.Supplier_Phone || ''}
                                    onChange={(e) => onHeaderChange('Supplier_Phone', e.target.value)}
                                    className="w-full bg-gray-900/50 border border-gray-700 rounded-lg px-3 py-2 text-sm font-mono focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 outline-none transition-all placeholder-gray-600"
                                    placeholder={invoiceData.Invoice_No || "Phone Number"}
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
                        <div className="animate-pulse flex gap-4 pt-2">
                            <div className="h-10 bg-gray-800 rounded w-1/3"></div>
                            <div className="h-10 bg-gray-800 rounded w-1/3"></div>
                            <div className="h-10 bg-gray-800 rounded w-1/3"></div>
                        </div>
                    )}
                </div>

                {!isHeaderExpanded && invoiceData && (
                    <div className="md:hidden flex items-center gap-2 text-xs text-gray-400 -mt-2 truncate" onClick={() => setIsHeaderExpanded(true)}>
                        <span className="font-semibold text-gray-300 truncate max-w-[40%]">{invoiceData.Supplier_Name || 'Unknown Supplier'}</span>
                        <span>•</span>
                        <span className="font-mono">{invoiceData.Invoice_No || 'No #'}</span>
                        <span>•</span>
                        <span>{invoiceData.Invoice_Date || 'No Date'}</span>
                    </div>
                )}
            </div>
        </div>
    );
};

export default EditorHeader;
