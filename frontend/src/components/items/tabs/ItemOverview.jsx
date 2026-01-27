import React from 'react';
import { Tag, Factory, FlaskConical, Warehouse, Search } from 'lucide-react';
import { InputField } from '../InputField';

export const ItemOverview = ({ formData, handleInputChange }) => {
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
                label="Manufacturer"
                name="manufacturer"
                value={formData.manufacturer}
                onChange={handleInputChange}
                icon={<Factory className="w-3 h-3" />}
                placeholder="Cipla, Sun Pharma..."
            />

            <InputField
                label="Salt Composition"
                name="salt_composition"
                value={formData.salt_composition}
                onChange={handleInputChange}
                icon={<FlaskConical className="w-3 h-3" />}
                placeholder="Paracetamol 500mg..."
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
                />
                <InputField
                    label="Purchase Date"
                    name="last_purchase_date"
                    value={formData.last_purchase_date}
                    onChange={handleInputChange}
                    icon={<Tag className="w-3 h-3 text-slate-500" />}
                    placeholder="Read Only"
                />
                <InputField
                    label="Saved By"
                    name="saved_by"
                    value={formData.saved_by}
                    onChange={handleInputChange}
                    icon={<Tag className="w-3 h-3 text-slate-500" />}
                    placeholder="System"
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
