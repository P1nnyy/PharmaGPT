import React from 'react';
import type { ProductFormData } from '../../types/product';
import { GST_RATES } from '../../constants/product';

interface ProductEconomicsProps {
    formData: ProductFormData;
    onChange: (field: keyof ProductFormData, value: any) => void;
    costPerAtomicUnit: number;
}

export const ProductEconomics: React.FC<ProductEconomicsProps> = ({ formData, onChange, costPerAtomicUnit }) => {
    return (
        <section>
            <h3 className="text-sm font-semibold text-green-400 uppercase tracking-wider mb-4 flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-green-400"></span>
                C. Economics
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                    <label className="block text-xs font-medium text-gray-400 mb-1.5">MRP (per {formData.skuUnit})</label>
                    <div className="relative">
                        <span className="absolute left-3 top-2.5 text-gray-500">₹</span>
                        <input
                            type="number"
                            value={formData.mrp}
                            onChange={(e) => onChange('mrp', parseFloat(e.target.value) || 0)}
                            className="w-full bg-black/20 border border-white/10 rounded-lg pl-7 pr-4 py-2.5 text-white focus:outline-none focus:border-green-500/50 transition-all"
                        />
                    </div>
                </div>
                <div>
                    <label className="block text-xs font-medium text-gray-400 mb-1.5">Purchase Rate</label>
                    <div className="relative">
                        <span className="absolute left-3 top-2.5 text-gray-500">₹</span>
                        <input
                            type="number"
                            value={formData.purchaseRate}
                            onChange={(e) => onChange('purchaseRate', parseFloat(e.target.value) || 0)}
                            className="w-full bg-black/20 border border-white/10 rounded-lg pl-7 pr-4 py-2.5 text-white focus:outline-none focus:border-green-500/50 transition-all"
                        />
                    </div>
                </div>
                <div>
                    <label className="block text-xs font-medium text-gray-400 mb-1.5">HSN Code</label>
                    <input
                        type="text"
                        value={formData.hsnCode}
                        onChange={(e) => onChange('hsnCode', e.target.value)}
                        className="w-full bg-black/20 border border-white/10 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-green-500/50 transition-all"
                    />
                </div>
                <div>
                    <label className="block text-xs font-medium text-gray-400 mb-1.5">GST %</label>
                    <select
                        value={formData.gst}
                        onChange={(e) => onChange('gst', parseFloat(e.target.value))}
                        className="w-full bg-black/20 border border-white/10 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-green-500/50 transition-all appearance-none cursor-pointer hover:bg-white/5"
                    >
                        {GST_RATES.map(rate => (
                            <option key={rate} value={rate} className="bg-gray-900">{rate}%</option>
                        ))}
                    </select>
                </div>
            </div>

            {/* Auto-Math Cost Display */}
            <div className="mt-4 p-3 bg-green-500/10 border border-green-500/20 rounded-lg flex justify-between items-center">
                <span className="text-sm text-green-300">Effective Cost per {formData.atomicUnit}</span>
                <span className="text-lg font-bold text-white">
                    ₹{costPerAtomicUnit.toFixed(2)}
                </span>
            </div>
        </section>
    );
};
