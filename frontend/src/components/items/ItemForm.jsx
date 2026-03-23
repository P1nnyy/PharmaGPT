import React from 'react';
import { Loader2, X } from 'lucide-react';
import { useItemForm } from './hooks/useItemForm';

const ItemForm = ({ item, onClose, onSave }) => {
    const { formData, handleChange, handleSave, saving, errors } = useItemForm(item);

    const onSubmit = async () => {
        const result = await handleSave();
        if (result.success) {
            onSave(result.data);
            onClose();
        }
    };

    return (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-[100] p-4">
            <div className="bg-slate-900 border border-slate-700 rounded-2xl p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto shadow-2xl">
                <div className="flex justify-between items-center mb-6">
                    <h2 className="text-2xl font-bold text-white">
                        {item.original_name ? 'Edit Item' : 'Add New Item'}
                    </h2>
                    <button onClick={onClose} className="text-slate-400 hover:text-white transition-colors">
                        <X className="w-6 h-6" />
                    </button>
                </div>

                <div className="space-y-6">
                    {/* Basic Info */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="md:col-span-2">
                            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                                Item Name
                            </label>
                            <input
                                type="text"
                                value={formData.name}
                                onChange={(e) => handleChange('name', e.target.value)}
                                className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:border-indigo-500 focus:outline-none transition-colors"
                                placeholder="Enter product name..."
                            />
                        </div>
                        <div>
                            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                                HSN Code
                            </label>
                            <input
                                type="text"
                                value={formData.hsn_code}
                                onChange={(e) => handleChange('hsn_code', e.target.value)}
                                className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:border-indigo-500 focus:outline-none transition-colors"
                            />
                        </div>
                        <div>
                            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                                Category
                            </label>
                            <input
                                type="text"
                                value={formData.category}
                                onChange={(e) => handleChange('category', e.target.value)}
                                className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:border-indigo-500 focus:outline-none transition-colors"
                            />
                        </div>
                    </div>

                    {/* Pricing */}
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-4 p-4 bg-slate-800/50 rounded-xl border border-slate-700/50">
                        <div>
                            <label className="block text-xs font-semibold text-slate-500 uppercase mb-2">MRP</label>
                            <input
                                type="number"
                                value={formData.mrp_primary}
                                onChange={(e) => handleChange('mrp_primary', e.target.value)}
                                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-white focus:border-emerald-500 outline-none"
                            />
                        </div>
                         <div>
                            <label className="block text-xs font-semibold text-slate-500 uppercase mb-2">Sale Price</label>
                            <input
                                type="number"
                                value={formData.sale_price}
                                onChange={(e) => handleChange('sale_price', e.target.value)}
                                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-white focus:border-emerald-500 outline-none"
                            />
                        </div>
                        <div>
                            <label className="block text-xs font-semibold text-slate-500 uppercase mb-2">GST %</label>
                            <input
                                type="number"
                                value={formData.tax_rate}
                                onChange={(e) => handleChange('tax_rate', e.target.value)}
                                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-white focus:border-emerald-500 outline-none"
                            />
                        </div>
                    </div>

                    {errors.submit && (
                        <div className="p-3 bg-red-900/20 border border-red-500/30 rounded-lg text-red-400 text-sm">
                            {errors.submit}
                        </div>
                    )}

                    <div className="flex gap-4 pt-4">
                        <button
                            onClick={onSubmit}
                            disabled={saving}
                            className="flex-1 bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-700 text-white font-bold py-3 rounded-xl flex items-center justify-center gap-2 transition-all shadow-lg shadow-indigo-600/20"
                        >
                            {saving ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Save Product Changes'}
                        </button>
                        <button
                            onClick={onClose}
                            className="px-6 bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold py-3 rounded-xl transition-colors"
                        >
                            Cancel
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ItemForm;
