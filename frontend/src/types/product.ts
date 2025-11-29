export type ProductCategory = 'Tablet' | 'Capsule' | 'Syrup' | 'Cream' | 'Injection' | 'Gel' | 'Drops' | 'Powder' | 'Other';

export interface ProductFormData {
    name: string;
    manufacturer: string;
    category: ProductCategory;

    // Math / Inventory Logic
    skuUnit: string;      // e.g., "Strip", "Box", "Bottle"
    atomicUnit: string;   // e.g., "Tablet", "Capsule", "Unit"
    conversion: number;   // e.g., 10 (1 Strip = 10 Tablets)

    // Economics
    mrp: number;
    purchaseRate: number;
    hsnCode: string;
    gst: number;
}

export interface Product extends ProductFormData {
    id?: string;
    costPerAtomicUnit?: number;
}
