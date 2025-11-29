import type { ProductCategory } from '../types/product';

export const PRODUCT_CATEGORIES: ProductCategory[] = [
    'Tablet',
    'Capsule',
    'Syrup',
    'Cream',
    'Injection',
    'Gel',
    'Drops',
    'Powder',
    'Other'
];

export const GST_RATES = [0, 5, 12, 18, 28];

// Mode A: Divisible (Variable Conversion)
// Mode B: Whole (Fixed Conversion = 1)
// Mode C: Hybrid (Variable Conversion)

// Categories where conversion is editable (Mode A & C)
export const VARIABLE_CONVERSION_CATEGORIES: ProductCategory[] = ['Tablet', 'Capsule', 'Injection', 'Other'];

export const DEFAULT_UNITS: Record<ProductCategory, { sku: string; atomic: string; defaultConversion: number }> = {
    // Mode A: Divisible
    'Tablet': { sku: 'Strip', atomic: 'Tablet', defaultConversion: 10 },
    'Capsule': { sku: 'Strip', atomic: 'Capsule', defaultConversion: 10 },

    // Mode B: Whole Items (Syrups, Powders, Creams, Drops) -> Conversion locked to 1
    'Syrup': { sku: 'Bottle', atomic: 'Unit', defaultConversion: 1 },
    'Cream': { sku: 'Tube', atomic: 'Unit', defaultConversion: 1 },
    'Gel': { sku: 'Tube', atomic: 'Unit', defaultConversion: 1 },
    'Drops': { sku: 'Bottle', atomic: 'Unit', defaultConversion: 1 },
    'Powder': { sku: 'Jar', atomic: 'Unit', defaultConversion: 1 },

    // Mode C: Hybrid
    'Injection': { sku: 'Box', atomic: 'Vial', defaultConversion: 5 },

    'Other': { sku: 'Pack', atomic: 'Unit', defaultConversion: 1 }
};
