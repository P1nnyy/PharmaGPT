import React from 'react';
import { Download, Save, Loader2 } from 'lucide-react';

const EditorFooter = ({ lineItems, isSaving, onExport, onConfirm, readOnly }) => {
    if (lineItems.length === 0) return null;

    return (
        <div className="p-4 bg-gray-900 border-t border-gray-800 shadow-[0_-5px_20px_rgba(0,0,0,0.5)] z-30 pb-20 md:pb-4">
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


                    {!readOnly && (
                        <button
                            onClick={onConfirm}
                            disabled={isSaving}
                            className="flex-[2] md:flex-none flex items-center justify-center gap-2 px-8 py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-bold rounded-xl shadow-lg shadow-indigo-500/20 hover:shadow-indigo-500/40 transition-all disabled:opacity-50 disabled:scale-95"
                        >
                            {isSaving ? <Loader2 className="animate-spin w-5 h-5" /> : <Save className="w-5 h-5" />}
                            <span>Save Invoice</span>
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
};

export default EditorFooter;
