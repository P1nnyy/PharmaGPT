import React from 'react';
import { Warehouse, Package, AlertCircle, Tag, Plus, X } from 'lucide-react';
import { InputField } from '../InputField';

export const ItemInventory = ({ formData, setFormData, handleInputChange }) => {
    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">

            {/* 1. Inventory Control */}
            <div className="bg-slate-900/40 rounded-xl border border-slate-700/50 p-5">
                <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-5 flex items-center gap-2">
                    <Warehouse className="w-4 h-4" /> Inventory Control
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className="col-span-2 md:col-span-1">
                        <label className="block text-xs font-bold text-slate-500 uppercase mb-1.5 ml-1">Product Type</label>
                        <div className="relative">
                            <select
                                value={formData.base_unit || 'Tablet'}
                                onChange={(e) => setFormData({ ...formData, base_unit: e.target.value })}
                                className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-2.5 text-sm font-semibold text-slate-200 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all outline-none appearance-none"
                            >
                                <option value="Tablet">Tablet</option>
                                <option value="Capsule">Capsule</option>
                                <option value="Syrup">Syrup</option>
                                <option value="Injection">Injection</option>
                                <option value="Softgel">Softgel</option>
                                <option value="Powder">Powder</option>
                                <option value="Liquid">Liquid</option>
                                <option value="Cream">Cream</option>
                                <option value="Gel">Gel</option>
                                <option value="Drops">Drops</option>
                                <option value="Spray">Spray</option>
                            </select>
                            <div className="absolute right-4 top-3 pointer-events-none text-slate-500">
                                <Package className="w-4 h-4" />
                            </div>
                        </div>
                    </div>
                    <div className="group relative">
                        <InputField
                            label={`Opening Stock (in ${formData.base_unit || 'Strip'}s)`}
                            name="opening_stock"
                            type="number"
                            value={formData.opening_stock}
                            onChange={handleInputChange}
                            icon={<Warehouse className="w-3 h-3" />}
                        />
                        {(!formData.is_verified && formData.opening_stock > 0) && (
                            <div className="absolute -top-8 left-0 hidden group-hover:block bg-slate-800 text-xs text-blue-300 px-2 py-1 rounded border border-blue-500/30 whitespace-nowrap z-50">
                                Auto-filled from Invoice Qty
                            </div>
                        )}
                    </div>
                    <InputField
                        label="Minimum Stock Alert"
                        name="min_stock"
                        type="number"
                        value={formData.min_stock}
                        onChange={handleInputChange}
                        icon={<AlertCircle className="w-3 h-3" />}
                    />
                    <div className="col-span-2">
                        <InputField
                            label="Rack Location"
                            name="rack_location"
                            value={formData.rack_location}
                            onChange={handleInputChange}
                            icon={<Tag className="w-3 h-3" />}
                            placeholder="A-12-04"
                        />
                    </div>
                </div>
            </div>

            {/* 2. Packaging Hierarchy */}
            <div className="bg-slate-900/40 rounded-xl border border-slate-700/50 p-5">
                <div className="flex justify-between items-center mb-5">
                    <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider flex items-center gap-2">
                        <Package className="w-4 h-4" /> Packaging Hierarchy
                    </h3>
                    <button onClick={() => setFormData(p => ({ ...p, packaging_variants: [...p.packaging_variants, { unit_name: 'Box', pack_size: '1x10', mrp: 0, conversion_factor: 10 }] }))} className="text-xs bg-slate-800 hover:bg-slate-700 px-3 py-1.5 rounded transition-colors text-blue-400 border border-slate-600 flex items-center gap-1">
                        <Plus className="w-3 h-3" /> Add Level
                    </button>
                </div>

                <div className="space-y-3">
                    {formData.packaging_variants.length === 0 ? (
                        <div className="text-center py-8 border border-dashed border-slate-800 rounded-lg text-slate-500 text-xs italic">
                            No alternative packaging defined (e.g. Boxes, Cartons).
                        </div>
                    ) : (
                        formData.packaging_variants.map((v, i) => (
                            <div key={i} className="grid grid-cols-12 gap-3 p-3 bg-slate-900 rounded-lg border border-slate-800 items-center">
                                <div className="col-span-3">
                                    <label className="text-[9px] text-slate-500 uppercase mb-1 block">Unit</label>
                                    <input placeholder="Box" value={v.unit_name} onChange={e => {
                                        const newV = [...formData.packaging_variants];
                                        newV[i].unit_name = e.target.value;
                                        setFormData({ ...formData, packaging_variants: newV });
                                    }} className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-xs text-white focus:ring-1 focus:ring-blue-500" />
                                </div>
                                <div className="col-span-3">
                                    <label className="text-[9px] text-slate-500 uppercase mb-1 block">Pack</label>
                                    <input placeholder="10x10" value={v.pack_size} onChange={e => {
                                        const newV = [...formData.packaging_variants];
                                        newV[i].pack_size = e.target.value;
                                        setFormData({ ...formData, packaging_variants: newV });
                                    }} className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-xs text-white focus:ring-1 focus:ring-blue-500" />
                                </div>
                                <div className="col-span-2">
                                    <label className="text-[9px] text-slate-500 uppercase mb-1 block">MRP</label>
                                    <input type="number" placeholder="0" value={v.mrp} onChange={e => {
                                        const newV = [...formData.packaging_variants];
                                        newV[i].mrp = parseFloat(e.target.value);
                                        setFormData({ ...formData, packaging_variants: newV });
                                    }} className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-xs text-white focus:ring-1 focus:ring-blue-500 text-right" />
                                </div>
                                <div className="col-span-3">
                                    <label className="text-[9px] text-slate-500 uppercase mb-1 block">Units</label>
                                    <input type="number" placeholder="10" value={v.conversion_factor} onChange={e => {
                                        const newV = [...formData.packaging_variants];
                                        newV[i].conversion_factor = parseFloat(e.target.value);
                                        setFormData({ ...formData, packaging_variants: newV });
                                    }} className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-xs text-white focus:ring-1 focus:ring-blue-500 text-center" />
                                </div>
                                <div className="col-span-1 text-right pt-4">
                                    <button onClick={() => {
                                        const newV = [...formData.packaging_variants];
                                        newV.splice(i, 1);
                                        setFormData({ ...formData, packaging_variants: newV });
                                    }} className="text-slate-600 hover:text-red-400 transition-colors">
                                        <X className="w-4 h-4" />
                                    </button>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </div>
        </div>
    );
};
