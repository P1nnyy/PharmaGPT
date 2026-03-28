import React from 'react';
import { Download, Save, Loader2 } from 'lucide-react';

const EditorFooter = ({ lineItems, invoiceData, isSaving, onExport, onConfirm, readOnly }) => {
    // --- Safe Fallbacks (Defensive Coding) ---
    const subTotal = Number(invoiceData?.sub_total) || 0;
    const globalDiscount = Number(invoiceData?.global_discount) || 0;
    const sgst = Number(invoiceData?.total_sgst) || 0;
    const cgst = Number(invoiceData?.total_cgst) || 0;
    const creditNote = Number(invoiceData?.credit_note_amount) || 0;
    const extraCharges = Number(invoiceData?.extra_charges) || 0;
    const roundOff = Number(invoiceData?.round_off) || 0;
    const grandTotal = Number(invoiceData?.Stated_Grand_Total) || Number(invoiceData?.grand_total) || 0;

    if (!lineItems || lineItems.length === 0) return null;

    return (
        <div className="p-4 bg-gray-950 border-t border-gray-800 shadow-[0_-15px_30px_rgba(0,0,0,0.6)] z-30 pb-20 md:pb-6">
            <div className="flex flex-col md:flex-row justify-between items-end gap-6 max-w-7xl mx-auto">
                
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

                {/* Right side: Ledger Summary */}
                <div className="w-full md:w-80 flex flex-col gap-2 text-right order-1 md:order-2 bg-gray-900/40 p-5 rounded-2xl border border-gray-800/50 backdrop-blur-sm">
                    <div className="flex justify-between items-center text-slate-400 text-xs font-semibold uppercase tracking-wider">
                        <span>Sub Total</span>
                        <span className="font-mono text-slate-200">₹{subTotal.toFixed(2)}</span>
                    </div>

                    <div className={`flex justify-between items-center text-xs font-medium ${globalDiscount > 0 ? 'text-rose-400' : 'text-slate-500'}`}>
                        <span>Discount</span>
                        <span className="font-mono">
                            {globalDiscount > 0 ? `-₹${globalDiscount.toFixed(2)}` : `₹0.00`}
                        </span>
                    </div>

                    <div className="flex justify-between items-center text-slate-500 text-xs">
                        <span>SGST</span>
                        <span className="font-mono">+₹{sgst.toFixed(2)}</span>
                    </div>

                    <div className="flex justify-between items-center text-slate-500 text-xs">
                        <span>CGST</span>
                        <span className="font-mono">+₹{cgst.toFixed(2)}</span>
                    </div>

                    {Math.abs(creditNote) > 0.001 && (
                        <div className="flex justify-between items-center text-rose-400 text-xs font-medium">
                            <span>Credit Note</span>
                            <span className="font-mono">-₹{creditNote.toFixed(2)}</span>
                        </div>
                    )}

                    {Math.abs(extraCharges) > 0.001 && (
                        <div className="flex justify-between items-center text-blue-400 text-xs font-medium">
                            <span>Extra Charges</span>
                            <span className="font-mono">+₹{extraCharges.toFixed(2)}</span>
                        </div>
                    )}

                    {Math.abs(roundOff) > 0.001 && (
                        <div className="flex justify-between items-center text-slate-500 text-xs">
                            <span>Round Off</span>
                            <span className="font-mono">{roundOff > 0 ? '+' : '-'}₹{Math.abs(roundOff).toFixed(2)}</span>
                        </div>
                    )}
                    
                    <div className="border-t border-slate-700 my-1 pt-2">
                        <div className="flex justify-between items-baseline">
                            <span className="text-slate-400 text-sm font-bold uppercase tracking-tight">Grand Total</span>
                            <span className="font-mono text-3xl font-black text-white tracking-tighter drop-shadow-[0_0_20px_rgba(255,255,255,0.15)]">
                                ₹{grandTotal.toFixed(2)}
                            </span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default EditorFooter;
