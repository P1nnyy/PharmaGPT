import { useState, useEffect, useMemo } from 'react';
import type { ProductFormData, Product, ProductCategory } from '../types/product';
import { DEFAULT_UNITS, VARIABLE_CONVERSION_CATEGORIES } from '../constants/product';

const INITIAL_STATE: ProductFormData = {
    name: '',
    manufacturer: '',
    category: 'Tablet',
    skuUnit: 'Strip',
    atomicUnit: 'Tablet',
    conversion: 10,
    mrp: 0,
    purchaseRate: 0,
    hsnCode: '',
    gst: 12
};

export const useProductForm = (initialData?: Partial<Product>) => {
    const [formData, setFormData] = useState<ProductFormData>(INITIAL_STATE);

    // Load initial data
    useEffect(() => {
        if (initialData) {
            setFormData(prev => ({
                ...prev,
                ...initialData,
                // Ensure defaults if missing
                category: (initialData.category as ProductCategory) || 'Tablet',
            }));
        } else {
            setFormData(INITIAL_STATE);
        }
    }, [initialData]);

    // Derived State: Cost Per Atomic Unit
    const costPerAtomicUnit = useMemo(() => {
        if (!formData.purchaseRate || !formData.conversion) return 0;
        return formData.purchaseRate / formData.conversion;
    }, [formData.purchaseRate, formData.conversion]);

    // Handler
    const handleChange = (field: keyof ProductFormData, value: any) => {
        setFormData(prev => {
            const updates: Partial<ProductFormData> = { [field]: value };

            // Smart Logic: Category Change triggers Unit updates
            if (field === 'category') {
                const category = value as ProductCategory;
                const defaults = DEFAULT_UNITS[category];

                updates.skuUnit = defaults.sku;
                updates.atomicUnit = defaults.atomic;
                updates.conversion = defaults.defaultConversion;
            }

            return { ...prev, ...updates };
        });
    };

    const isConversionLocked = !VARIABLE_CONVERSION_CATEGORIES.includes(formData.category);

    return {
        formData,
        handleChange,
        costPerAtomicUnit,
        isConversionLocked
    };
};
