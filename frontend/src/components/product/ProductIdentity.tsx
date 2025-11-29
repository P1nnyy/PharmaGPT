import React from 'react';
import type { ProductFormData, ProductCategory } from '../../types/product';
import { PRODUCT_CATEGORIES } from '../../constants/product';

interface ProductIdentityProps {
    formData: ProductFormData;
    onChange: (field: keyof ProductFormData, value: any) => void;
}

export const ProductIdentity: React.FC<ProductIdentityProps> = ({ formData, onChange }) => {
    return (
        <section>
            <h3 className="text-sm font-semibold text-blue-400 uppercase tracking-wider mb-4 flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-400"></span>
                A. Identity
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                <div className="col-span-2">
                    <label className="block text-xs font-medium text-gray-400 mb-1.5">Product Name</label>
                    <input
                        type="text"
                        value={formData.name}
                        onChange={(e) => onChange('name', e.target.value)}
                        placeholder="e.g. Dolo 650"
                        className="w-full bg-black/20 border border-white/10 rounded-lg px-4 py-2.5 text-white placeholder-gray-600 focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/50 transition-all"
                    />
                </div>
                <div>
                    <label className="block text-xs font-medium text-gray-400 mb-1.5">Manufacturer</label>
                    <input
                        type="text"
                        value={formData.manufacturer}
                        onChange={(e) => onChange('manufacturer', e.target.value)}
                        placeholder="e.g. GSK"
                        className="w-full bg-black/20 border border-white/10 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-blue-500/50 transition-all"
                    />
                </div>
                <div>
                    <label className="block text-xs font-medium text-gray-400 mb-1.5">Category</label>
                    <select
                        value={formData.category}
                        onChange={(e) => onChange('category', e.target.value as ProductCategory)}
                        className="w-full bg-black/20 border border-white/10 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-blue-500/50 transition-all appearance-none cursor-pointer hover:bg-white/5"
                    >
                        {PRODUCT_CATEGORIES.map(cat => (
                            <option key={cat} value={cat} className="bg-gray-900">{cat}</option>
                        ))}
                    </select>
                </div>
            </div>
        </section>
    );
};
