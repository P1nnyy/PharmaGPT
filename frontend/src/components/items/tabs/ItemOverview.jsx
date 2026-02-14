import React from 'react';
import { Tag, Factory, FlaskConical, Warehouse, Search, Globe } from 'lucide-react';
import { InputField } from '../InputField';

export const ItemOverview = ({ formData, handleInputChange }) => {

    // Enrichment Indicator
    const enrichmentBadge = formData.is_enriched ? (
        <span title="Data fetched from internet - Please Verify" className="text-blue-400 ml-2 animate-pulse cursor-help">
            <Globe className="w-3 h-3 inline" />
        </span>
    ) : null;

    return (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
            <div className="col-span-2">
                <InputField
                    label="Product Name"
                    name="name"
                    value={formData.name}
                    onChange={handleInputChange}
                    icon={<Tag className="w-3 h-3" />}
                    placeholder="Enter product name"
                />
            </div>

            <InputField
                label={<span className="flex items-center">Manufacturer {enrichmentBadge}</span>}
                name="manufacturer"
                value={formData.manufacturer}
                onChange={handleInputChange}
                icon={<Factory className="w-3 h-3" />}
                placeholder="Enter manufacturer..."
            />

            <InputField
                label={<span className="flex items-center">Salt Composition {enrichmentBadge}</span>}
                name="salt_composition"
                value={formData.salt_composition}
                onChange={handleInputChange}
                icon={<FlaskConical className="w-3 h-3" />}
                placeholder="Enter salt composition..."
            />

            {/* Source Information (Read Only) */}
            <div className="col-span-2 grid grid-cols-1 md:grid-cols-3 gap-6 p-4 bg-slate-900/50 rounded-xl border border-dashed border-slate-700">
                <InputField
                    label="Supplier Name"
                    name="supplier_name"
                    value={formData.supplier_name}
                    onChange={handleInputChange}
                    icon={<Warehouse className="w-3 h-3 text-slate-500" />}
                    placeholder="Read Only"
                    readOnly={true}
                />
                <InputField
                    label="Purchase Date"
                    name="last_purchase_date"
                    value={formData.last_purchase_date}
                    onChange={handleInputChange}
                    icon={<Tag className="w-3 h-3 text-slate-500" />}
                    placeholder="Read Only"
                    readOnly={true}
                />
                <InputField
                    label="Saved By"
                    name="saved_by"
                    value={formData.saved_by}
                    onChange={handleInputChange}
                    icon={<Tag className="w-3 h-3 text-slate-500" />}
                    placeholder="System"
                    readOnly={true}
                />
            </div>

            <InputField
                label="Item Code / SKU"
                name="item_code"
                value={formData.item_code}
                onChange={handleInputChange}
                icon={<Search className="w-3 h-3" />}
                placeholder="Internal SKU"
            />
        </div>
    );
};
