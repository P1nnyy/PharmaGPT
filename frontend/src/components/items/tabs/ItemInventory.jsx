import React, { useEffect, useState } from 'react';
import { Warehouse, Package, AlertCircle, Tag, Layers, Box, Calculator, Plus, Trash2 } from 'lucide-react';
import { InputField } from '../InputField';

export const ItemInventory = ({ formData, setFormData, handleInputChange }) => {

    // Defaults
    const baseUnit = formData.base_unit || 'Tablet';
    const conversionFactor = parseFloat(formData.pack_size_primary) || 10;
    const outerPackSize = parseFloat(formData.pack_size_secondary) || 1;

    // Derived visual labels
    const isTabletLike = ['Tablet', 'Capsule'].includes(baseUnit);
    const primaryUnitLabel = isTabletLike ? 'Strip' : 'Unit';
    const secondaryUnitLabel = 'Box';

    // Lazy Loading State: Show Secondary Packing only if it exists (>1)
    const [showSecondary, setShowSecondary] = useState(false);

    // Initialize showSecondary based on incoming data
    useEffect(() => {
        if (formData.pack_size_secondary > 1) {
            setShowSecondary(true);
        }
    }, [formData.pack_size_secondary]);

    // Unity Rule: Force pack_size_primary to 1 if not tablet/capsule
    useEffect(() => {
        if (!isTabletLike && formData.pack_size_primary !== 1) {
            handleStockCalculation({ pack_size_primary: 1 });
        }
    }, [baseUnit]);

    // Calculate total stock whenever inputs change
    useEffect(() => {
        if (formData.opening_boxes === undefined) {
            setFormData(prev => ({ ...prev, opening_boxes: 0 }));
        }
        if (formData.opening_strips === undefined) {
            setFormData(prev => ({ ...prev, opening_strips: 0 }));
        }
    }, []);

    const handleStockCalculation = (updates) => {
        const newData = { ...formData, ...updates };
        const boxes = parseFloat(newData.opening_boxes) || 0;
        const strips = parseFloat(newData.opening_strips) || 0;
        const cf = parseFloat(newData.pack_size_primary) || 10;

        // If hidden, treat secondary pack size as 1 (or ignore boxes)
        // Note: The UI hides the box input, so boxes *should* be 0 conceptually if hidden.
        // We'll use the actual pack size from data, but if !showSecondary, we technically shouldn't have boxes.
        const ops = parseFloat(newData.pack_size_secondary) || 1;

        // Formula: (Boxes * Strips/Box * Tabs/Strip) + (Loose_Strips * Tabs/Strip)
        const totalStock = (boxes * ops * cf) + (strips * cf);

        setFormData({
            ...newData,
            opening_stock: totalStock
        });
    };

    const handleAddBoxLayer = () => {
        setShowSecondary(true);
        handleStockCalculation({ pack_size_secondary: 10 }); // Default assumption
    };

    const handleRemoveBoxLayer = () => {
        setShowSecondary(false);
        handleStockCalculation({
            pack_size_secondary: 1,
            opening_boxes: 0
        });
    };

    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">

            {/* Section 1: Base Definition */}
            <div className="bg-slate-900/40 rounded-xl border border-slate-700/50 p-5">
                <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-4 flex items-center gap-2">
                    <Tag className="w-4 h-4" /> 1. Base Definition
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                        <label className="block text-xs font-bold text-slate-500 uppercase mb-1.5 ml-1">Base Unit</label>
                        <div className="relative">
                            <select
                                value={formData.base_unit || 'Tablet'}
                                onChange={(e) => setFormData({ ...formData, base_unit: e.target.value })}
                                className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-2.5 text-sm font-semibold text-slate-200 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all outline-none appearance-none"
                            >
                                <option value="Tablet">Tablet</option>
                                <option value="Capsule">Capsule</option>
                                <option value="Bottle">Bottle</option>
                                <option value="Vial">Vial</option>
                                <option value="Injection">Injection</option>
                                <option value="Tube">Tube</option>
                                <option value="Sachet">Sachet</option>
                            </select>
                            <div className="absolute right-4 top-3 pointer-events-none text-slate-500">
                                <Package className="w-4 h-4" />
                            </div>
                        </div>
                        <p className="text-[10px] text-slate-500 mt-2 ml-1">
                            This is the unit used for billing patients (e.g., 1 Tablet).
                        </p>
                    </div>
                </div>
            </div>

            {/* Section 2: Primary Packing */}
            <div className="bg-slate-900/40 rounded-xl border border-slate-700/50 p-5 relative overflow-hidden">
                <div className="absolute top-0 right-0 p-4 opacity-5">
                    <Layers className="w-24 h-24" />
                </div>
                <h3 className="text-sm font-bold text-blue-400 uppercase tracking-wider mb-4 flex items-center gap-2">
                    <Layers className="w-4 h-4" /> 2. Primary Packing (Sellable Unit)
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 relative z-10">
                    <InputField
                        label={`Units per ${primaryUnitLabel}`}
                        name="pack_size_primary"
                        type="number"
                        value={formData.pack_size_primary}
                        onChange={(e) => handleStockCalculation({ pack_size_primary: e.target.value })}
                        icon={<Calculator className="w-3 h-3" />}
                        placeholder={isTabletLike ? "10" : "1"}
                        disabled={!isTabletLike}
                        className={!isTabletLike ? 'opacity-50 cursor-not-allowed bg-slate-800' : ''}
                    />
                </div>
                <div className="mt-4 bg-blue-900/20 border border-blue-500/20 rounded-lg p-3 text-center">
                    <p className="text-xs text-blue-300 font-mono">
                        {isTabletLike ? (
                            <>1 {primaryUnitLabel} = <span className="font-bold text-white">{conversionFactor}</span> {baseUnit}s</>
                        ) : (
                            <>Sold as Single Units (1x1)</>
                        )}
                    </p>
                </div>
            </div>

            {/* Section 3: Secondary Packing (Lazy Loaded) */}
            {showSecondary ? (
                <div className="bg-slate-900/40 rounded-xl border border-slate-700/50 p-5 relative overflow-hidden animate-in fade-in zoom-in-95 duration-200">
                    <div className="absolute top-0 right-0 p-4 opacity-5">
                        <Box className="w-24 h-24" />
                    </div>
                    <div className="flex justify-between items-center mb-4">
                        <h3 className="text-sm font-bold text-emerald-400 uppercase tracking-wider flex items-center gap-2">
                            <Box className="w-4 h-4" /> 3. Secondary Packing (Purchase Unit)
                        </h3>
                        <button
                            onClick={handleRemoveBoxLayer}
                            className="text-slate-500 hover:text-red-400 transition-colors p-1"
                            title="Remove Box Details"
                        >
                            <Trash2 className="w-4 h-4" />
                        </button>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 relative z-10">
                        <InputField
                            label={`${primaryUnitLabel}s per ${secondaryUnitLabel}`}
                            name="pack_size_secondary"
                            type="number"
                            value={formData.pack_size_secondary}
                            onChange={(e) => handleStockCalculation({ pack_size_secondary: e.target.value })}
                            icon={<Package className="w-3 h-3" />}
                            placeholder="1"
                        />
                    </div>
                    <div className="mt-4 bg-emerald-900/20 border border-emerald-500/20 rounded-lg p-3 text-center">
                        <p className="text-xs text-emerald-300 font-mono">
                            1 {secondaryUnitLabel} = <span className="font-bold text-white">{outerPackSize}</span> {primaryUnitLabel}s = <span className="font-bold text-white">{outerPackSize * conversionFactor}</span> Total {baseUnit}s
                        </p>
                    </div>
                </div>
            ) : (
                <div className="flex justify-center">
                    <button
                        onClick={handleAddBoxLayer}
                        className="flex items-center gap-2 text-xs font-bold text-slate-500 hover:text-blue-400 bg-slate-900/50 hover:bg-slate-900 border border-dashed border-slate-700 hover:border-blue-500/50 rounded-xl px-6 py-3 transition-all group"
                    >
                        <Plus className="w-4 h-4 group-hover:scale-110 transition-transform" />
                        Add Box/Carton Details
                    </button>
                </div>
            )}

            {/* Total Stock Calculation */}
            <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-5">
                <h3 className="text-sm font-bold text-slate-300 uppercase tracking-wider mb-4 flex items-center gap-2">
                    <Warehouse className="w-4 h-4" /> Opening Stock Calculator
                </h3>
                <div className="grid grid-cols-12 gap-4 items-end">
                    {showSecondary && (
                        <div className="col-span-5 animate-in fade-in slide-in-from-left-2">
                            <InputField
                                label={`Opening ${secondaryUnitLabel}s`}
                                name="opening_boxes"
                                type="number"
                                value={formData.opening_boxes || ''}
                                onChange={(e) => handleStockCalculation({ opening_boxes: e.target.value })}
                                placeholder="0"
                            />
                        </div>
                    )}
                    <div className={showSecondary ? "col-span-5" : "col-span-10"}>
                        <InputField
                            label={`Loose ${primaryUnitLabel}s`}
                            name="opening_strips"
                            type="number"
                            value={formData.opening_strips || ''}
                            onChange={(e) => handleStockCalculation({ opening_strips: e.target.value })}
                            placeholder="0"
                        />
                    </div>
                    <div className="col-span-2 pb-1">
                        <div className="text-right">
                            <label className="block text-[10px] text-slate-500 uppercase mb-1">Total {baseUnit}s</label>
                            <div className="text-xl font-bold text-white font-mono">
                                {formData.opening_stock || 0}
                            </div>
                        </div>
                    </div>
                </div>
                <div className="mt-4 pt-4 border-t border-slate-700/50 flex justify-between items-center text-xs text-slate-500">
                    <span>
                        Inventory Location
                    </span>
                    <div className="w-48">
                        <InputField
                            name="rack_location"
                            value={formData.rack_location}
                            onChange={handleInputChange}
                            placeholder="Rack / Shelf"
                            className="bg-slate-900 md:text-xs"
                        />
                    </div>
                </div>
            </div>

        </div>
    );
};
