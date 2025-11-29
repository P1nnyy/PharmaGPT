import React from 'react';
import { Calculator, CheckCircle2, Lock } from 'lucide-react';
import type { ProductFormData } from '../../types/product';

interface ProductMathProps {
    formData: ProductFormData;
    onChange: (field: keyof ProductFormData, value: any) => void;
    isLocked: boolean;
}

export const ProductMath: React.FC<ProductMathProps> = ({ formData, onChange, isLocked }) => {
    return (
        <section className="bg-white/5 rounded-xl p-5 border border-white/5 relative overflow-hidden">
            <div className="absolute top-0 right-0 p-3 opacity-10">
                <Calculator size={64} />
            </div>
            <h3 className="text-sm font-semibold text-purple-400 uppercase tracking-wider mb-4 flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-purple-400"></span>
                B. Smart Inventory Model
            </h3>

            {/* Natural Language Input Sentence */}
            <div className="relative z-10 bg-black/40 rounded-lg p-6 border border-white/10">
                <div className="flex flex-wrap items-center gap-3 text-lg text-gray-300">
                    <span>I buy this in</span>

                    {/* SKU Unit Input (Pill) */}
                    <div className="relative group">
                        <input
                            type="text"
                            value={formData.skuUnit}
                            onChange={(e) => onChange('skuUnit', e.target.value)}
                            className="bg-purple-500/10 border border-purple-500/30 rounded-full px-4 py-1 text-white font-bold w-28 text-center focus:outline-none focus:border-purple-400 focus:bg-purple-500/20 transition-all placeholder-gray-500"
                            placeholder="Pack"
                        />
                        <span className="absolute -bottom-5 left-1/2 -translate-x-1/2 text-[10px] text-gray-500 opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">SKU Unit</span>
                    </div>

                    <span>containing</span>

                    {/* Conversion Input (Pill) */}
                    <div className="relative group">
                        <input
                            type="number"
                            value={formData.conversion}
                            onChange={(e) => onChange('conversion', parseFloat(e.target.value) || 0)}
                            disabled={isLocked}
                            className={`rounded-full px-3 py-1 font-bold w-20 text-center focus:outline-none transition-all ${isLocked
                                    ? 'bg-gray-800/50 border border-gray-700 text-gray-500 cursor-not-allowed'
                                    : 'bg-purple-500/10 border border-purple-500/30 text-white focus:border-purple-400 focus:bg-purple-500/20'
                                }`}
                        />
                        {isLocked && (
                            <div className="absolute -top-2 -right-2 bg-gray-800 rounded-full p-1 border border-gray-700">
                                <Lock size={10} className="text-gray-400" />
                            </div>
                        )}
                        <span className="absolute -bottom-5 left-1/2 -translate-x-1/2 text-[10px] text-gray-500 opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">Count</span>
                    </div>

                    {/* Atomic Unit Input (Pill) */}
                    <div className="relative group">
                        <input
                            type="text"
                            value={formData.atomicUnit}
                            onChange={(e) => onChange('atomicUnit', e.target.value)}
                            className="bg-purple-500/10 border border-purple-500/30 rounded-full px-4 py-1 text-white font-bold w-28 text-center focus:outline-none focus:border-purple-400 focus:bg-purple-500/20 transition-all placeholder-gray-500"
                            placeholder="Units"
                        />
                        <span className="absolute -bottom-5 left-1/2 -translate-x-1/2 text-[10px] text-gray-500 opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">Atomic Unit</span>
                    </div>
                </div>
            </div>

            {/* Visual Feedback Badge */}
            <div className="mt-4 flex items-center gap-3 bg-purple-500/10 border border-purple-500/20 rounded-lg p-3 relative z-10">
                <div className="bg-purple-500/20 p-2 rounded-full">
                    <CheckCircle2 size={16} className="text-purple-400" />
                </div>
                <div>
                    <p className="text-xs text-purple-300 font-medium">Tracking Logic</p>
                    <p className="text-sm text-white">
                        1 {formData.skuUnit || 'Pack'} = <span className="font-bold text-purple-400">{formData.conversion}</span> {formData.atomicUnit || 'Units'}
                    </p>
                </div>
            </div>
        </section>
    );
};
