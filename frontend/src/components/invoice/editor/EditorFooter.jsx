import React from 'react';
import { Download, Save, Loader2 } from 'lucide-react';

const EditorFooter = ({ invoiceData, lineItems, isSaving, onExport, onConfirm, readOnly }) => {
    if (lineItems.length === 0) return null;

    // Financial breakdown values
    const subTotal = parseFloat(invoiceData?.sub_total || 0).toFixed(2);
    const globalDiscount = parseFloat(invoiceData?.global_discount || 0).toFixed(2);
    const sgst = parseFloat(invoiceData?.total_sgst || 0).toFixed(2);
    const cgst = parseFloat(invoiceData?.total_cgst || 0).toFixed(2);
    const roundOff = parseFloat(invoiceData?.round_off || 0).toFixed(2);
    const grandTotal = parseFloat(invoiceData?.Stated_Grand_Total || 0).toFixed(2);

    return (
        <div className="p-4 bg-gray-950 border-t border-gray-800 shadow-[0_-15px_30px_rgba(0,0,0,0.6)] z-30 pb-20 md:pb-6">
            <div className="flex flex-col md:flex-row justify-between items-end gap-6">
                
                {/* Left side actions */}
                <div className="flex w-full md:w-auto gap-3 order-2 md:order-1">
                    <button
                        onClick={onExport}
                        className="flex-1 md:flex-none flex items-center justify-center gap-2 px-6 py-4 bg-gray-900 hover:bg-gray-800 text-gray-300 font-medium rounded-2xl border border-gray-800 hover:border-gray-700 transition-all shadow-lg"
                    >
                        <Download className="w-5 h-5 text-indigo-400" />
                        <span>Export Excel</span>
                    </button>

                    {!readOnly && (
                        <button
                            onClick={onConfirm}
                            disabled={isSaving}
                            className="flex-[2] md:flex-none flex items-center justify-center gap-2 px-10 py-4 bg-indigo-600 hover:bg-indigo-500 text-white font-bold rounded-2xl shadow-xl shadow-indigo-500/20 hover:shadow-indigo-500/40 transition-all disabled:opacity-50 disabled:scale-95 group"
                        >
                            {isSaving ? <Loader2 className="animate-spin w-5 h-5" /> : <Save className="w-5 h-5 group-hover:scale-110 transition-transform" />}
                            <span>Save Invoice</span>
                        </button>
                    )}
                </div>

                {/* Right side: Strict Ledger Breakdown */}
                <div className="w-full md:w-72 flex flex-col gap-1.5 text-right order-1 md:order-2 px-2">
                    <div className="flex justify-between items-center text-gray-400 text-xs font-semibold uppercase tracking-wider">
                        <span>Sub Total</span>
                        <span className="font-mono text-gray-300">₹{subTotal}</span>
                    </div>
                    {parseFloat(globalDiscount) > 0 && (
                        <div className="flex justify-between items-center text-rose-500/80 text-xs font-medium">
                            <span>Less Discount</span>
                            <span className="font-mono">-₹{globalDiscount}</span>
                        </div>
                    )}
                    <div className="flex justify-between items-center text-gray-500 text-[11px]">
                        <span>Add SGST</span>
                        <span className="font-mono">+₹{sgst}</span>
                    </div>
                    <div className="flex justify-between items-center text-gray-500 text-[11px]">
                        <span>Add CGST</span>
                        <span className="font-mono">+₹{cgst}</span>
                    </div>
                    {Math.abs(parseFloat(roundOff)) > 0.01 && (
                        <div className="flex justify-between items-center text-gray-500 text-[11px]">
                            <span>Round Off</span>
                            <span className="font-mono">₹{roundOff}</span>
                        </div>
                    )}
                    
                    <div className="h-px bg-gray-800 my-2 w-full ml-auto"></div>
                    
                    <div className="flex justify-between items-center">
                        <span className="text-gray-400 text-sm font-bold uppercase">Grand Total</span>
                        <span className="font-mono text-3xl font-black text-indigo-400 drop-shadow-[0_0_15px_rgba(99,102,241,0.3)]">
                            ₹{grandTotal}
                        </span>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default EditorFooter;
