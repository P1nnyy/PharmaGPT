import React from 'react';
import { X, Save } from 'lucide-react';
import { useProductForm } from '../hooks/useProductForm';
import { ProductIdentity } from './product/ProductIdentity';
import { ProductMath } from './product/ProductMath';
import { ProductEconomics } from './product/ProductEconomics';
import type { Product } from '../types/product';

interface ProductFormProps {
    isOpen: boolean;
    onClose: () => void;
    initialData?: Partial<Product>;
    onSubmit: (data: Product) => void;
}

const ProductForm: React.FC<ProductFormProps> = ({ isOpen, onClose, initialData, onSubmit }) => {
    const { formData, handleChange, costPerAtomicUnit, isConversionLocked } = useProductForm(initialData);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        // Pass the full product object including derived cost
        onSubmit({
            ...formData,
            costPerAtomicUnit
        });
        onClose();
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
            <div className="w-full max-w-2xl rounded-2xl bg-[#1a1a1a]/80 backdrop-blur-xl border border-white/10 shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">

                {/* Header */}
                <div className="flex items-center justify-between p-6 border-b border-white/10 bg-white/5">
                    <div>
                        <h2 className="text-xl font-bold text-white flex items-center gap-2">
                            {initialData ? 'Modify Product' : 'New Product Master'}
                        </h2>
                        <p className="text-xs text-gray-400 mt-1">Define the atomic structure and economics.</p>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-2 rounded-full hover:bg-white/10 text-gray-400 hover:text-white transition-colors"
                    >
                        <X size={20} />
                    </button>
                </div>

                {/* Body */}
                <div className="flex-1 overflow-y-auto p-6 space-y-8">
                    <ProductIdentity
                        formData={formData}
                        onChange={handleChange}
                    />

                    <ProductMath
                        formData={formData}
                        onChange={handleChange}
                        isLocked={isConversionLocked}
                    />

                    <ProductEconomics
                        formData={formData}
                        onChange={handleChange}
                        costPerAtomicUnit={costPerAtomicUnit}
                    />
                </div>

                {/* Footer */}
                <div className="p-6 border-t border-white/10 bg-black/20 flex justify-end gap-3">
                    <button
                        onClick={onClose}
                        className="px-6 py-2.5 rounded-lg text-sm font-medium text-gray-400 hover:text-white hover:bg-white/5 transition-colors"
                    >
                        Cancel
                    </button>
                    <button
                        onClick={handleSubmit}
                        className="px-6 py-2.5 rounded-lg text-sm font-medium bg-gradient-to-r from-blue-600 to-purple-600 text-white hover:shadow-lg hover:shadow-blue-500/25 transition-all flex items-center gap-2"
                    >
                        <Save size={18} />
                        Save Product
                    </button>
                </div>

            </div>
        </div>
    );
};

export default ProductForm;
