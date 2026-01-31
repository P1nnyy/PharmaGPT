import React from 'react';
import { IndianRupee, Search } from 'lucide-react';
import { InputField } from '../InputField';

export const ItemPricing = ({ formData, handleInputChange }) => {
    // Derived values
    const landing = (formData.purchase_price || 0) * (1 + (formData.tax_rate || 0) / 100);
    const margin = (formData.sale_price || 0) - landing;
    const marginPercent = formData.sale_price > 0 ? (margin / formData.sale_price) * 100 : 0;
    const isHigh = marginPercent > 25;
    const isLow = marginPercent < 15;
    // Unit Analysis (Per Tablet/Capsule)
    const packSize = parseFloat(formData.pack_size_primary) || 1;
    const showUnitAnalysis = packSize > 1;

    const unitLanding = landing / packSize;
    const unitMrp = (formData.sale_price || 0) / packSize;
    const unitMargin = margin / packSize;


    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">

            {/* 1. Metric Cards (Real-time Analysis) */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Landing Cost */}
                <div className="bg-slate-900/50 p-4 rounded-xl border border-slate-700">
                    <div className="text-slate-500 text-[10px] font-bold uppercase tracking-wider mb-1">Effective Landing Cost</div>
                    <div className="text-2xl font-mono font-bold text-white">
                        ₹{landing.toFixed(2)}
                    </div>
                    <div className="text-[10px] text-slate-400 mt-1">Base + {formData.tax_rate}% GST</div>
                </div>

                {/* Tax Amount */}
                <div className="bg-slate-900/50 p-4 rounded-xl border border-slate-700">
                    <div className="text-slate-500 text-[10px] font-bold uppercase tracking-wider mb-1">Tax Amount</div>
                    <div className="text-2xl font-mono font-bold text-blue-400">
                        ₹{((formData.purchase_price || 0) * ((formData.tax_rate || 0) / 100)).toFixed(2)}
                    </div>
                    <div className="text-[10px] text-slate-400 mt-1">Input Credit Available</div>
                </div>

                {/* Margin Analysis */}
                <div className={`p-4 rounded-xl border ${isHigh ? 'bg-emerald-500/10 border-emerald-500/30' : isLow ? 'bg-red-500/10 border-red-500/30' : 'bg-amber-500/10 border-amber-500/30'}`}>
                    <div className={`text-[10px] font-bold uppercase tracking-wider mb-1 ${isHigh ? 'text-emerald-400' : isLow ? 'text-red-400' : 'text-amber-400'}`}>Net Margin</div>
                    <div className="flex items-end gap-2">
                        <div className={`text-2xl font-mono font-bold ${isHigh ? 'text-emerald-300' : isLow ? 'text-red-300' : 'text-amber-300'}`}>
                            {marginPercent.toFixed(1)}%
                        </div>
                        <div className="text-sm font-medium opacity-80 mb-1">
                            (₹{margin.toFixed(2)})
                        </div>
                    </div>
                    <div className="text-[10px] mt-1 opacity-70">Profit per Pack</div>
                </div>
            </div>

            {/* 2. Unit Level Analysis (Dynamic) */}
            {showUnitAnalysis && (
                <div className="bg-slate-800/50 p-4 rounded-xl border border-dashed border-slate-600">
                    <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                        <span className="bg-slate-700 text-white px-1.5 py-0.5 rounded text-[10px]">{packSize}x</span> Unit Breakdown
                    </h3>
                    <div className="grid grid-cols-3 gap-4">
                        <div>
                            <div className="text-[10px] text-slate-500 uppercase">Cost / Unit</div>
                            <div className="font-mono font-bold text-slate-300">₹{unitLanding.toFixed(2)}</div>
                        </div>
                        <div>
                            <div className="text-[10px] text-slate-500 uppercase">MRP / Unit</div>
                            <div className="font-mono font-bold text-slate-300">₹{unitMrp.toFixed(2)}</div>
                        </div>
                        <div>
                            <div className="text-[10px] text-slate-500 uppercase">Profit / Unit</div>
                            <div className={`font-mono font-bold ${unitMargin > 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                                ₹{unitMargin.toFixed(2)}
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* 3. Detailed Input Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">

                {/* Cost Side */}
                <div className="space-y-4">
                    <h3 className="text-xs font-bold text-slate-500 uppercase border-b border-slate-700 pb-2 mb-4">Cost Structure</h3>
                    <InputField
                        label="Purchase Price (Base Rate)"
                        name="purchase_price"
                        type="number"
                        value={formData.purchase_price}
                        onChange={handleInputChange}
                        icon={<IndianRupee className="w-3 h-3 text-slate-400" />}
                    />
                    <InputField
                        label="Tax Rate (GST %)"
                        name="tax_rate"
                        type="number"
                        value={formData.tax_rate}
                        onChange={handleInputChange}
                        icon={<span className="text-xs font-bold">%</span>}
                    />
                    <InputField
                        label="HSN / SAC Code"
                        name="hsn_code"
                        value={formData.hsn_code}
                        onChange={handleInputChange}
                        icon={<Search className="w-3 h-3" />}
                    />
                </div>

                {/* Revenue Side */}
                <div className="space-y-4">
                    <h3 className="text-xs font-bold text-slate-500 uppercase border-b border-slate-700 pb-2 mb-4">Revenue & Pricing</h3>

                    <div className="p-1 bg-emerald-500/5 rounded-xl border border-emerald-500/20">
                        <InputField
                            label="Sale Price (MRP)"
                            name="sale_price"
                            type="number"
                            value={formData.sale_price}
                            onChange={handleInputChange}
                            icon={<IndianRupee className="w-3 h-3 text-emerald-400" />}
                        />
                    </div>

                    <div className="p-3 bg-slate-900 rounded-lg border border-slate-800 mt-4">
                        <div className="flex justify-between items-center text-xs mb-2">
                            <span className="text-slate-400">Trade Discount (Scheme)</span>
                            <span className="text-slate-500 italic">Coming Soon</span>
                        </div>
                        <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
                            <div className="h-full bg-slate-700 w-0"></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};
