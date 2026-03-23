import { useState } from 'react';
import { saveProduct, renameProduct } from '../../../services/api';

export const useItemForm = (initialItem = null) => {
    const defaultState = {
        original_name: '',
        name: '',
        item_code: '',
        hsn_code: '',
        sale_price: 0,
        purchase_price: 0,
        tax_rate: 0,
        opening_stock: 0,
        opening_boxes: 0,
        opening_strips: 0,
        min_stock: 0,
        rack_location: '',
        manufacturer: '',
        salt_composition: '',
        category: '',
        supplier_name: '',
        last_purchase_date: '',
        saved_by: '',
        base_unit: 'Tablet',
        is_verified: false,
        is_enriched: false,
        // Flat Packaging Fields
        pack_size_primary: 10,  // e.g. 10 tablets per strip
        pack_size_secondary: 1, // e.g. 1 strip per box (default)
        mrp_primary: 0,         // MRP per strip
        // Enrichment Fields
        hsn_description: '',
        is_tax_inferred: false,
        needs_review: false
    };

    const [formData, setFormData] = useState(initialItem || defaultState);
    const [saving, setSaving] = useState(false);
    const [errors, setErrors] = useState({});

    const handleChange = (field, value) => {
        const isNumeric = ['sale_price', 'purchase_price', 'tax_rate', 'opening_stock', 'min_stock', 'pack_size_primary', 'pack_size_secondary', 'mrp_primary'].includes(field);
        setFormData(prev => ({ 
            ...prev, 
            [field]: isNumeric ? (parseFloat(value) || 0) : value 
        }));
    };

    const handleSave = async () => {
        try {
            setSaving(true);
            const newName = (formData.name || '').trim();
            const oldName = formData.original_name;

            // If the name changed and it's not a new product, call rename API first
            if (oldName && newName && oldName !== newName) {
                await renameProduct(oldName, newName);
            }

            // Build packaging variants from flat fields
            const variants = [];
            const isTabletCapsule = ['Tablet', 'Capsule'].includes(formData.base_unit);

            if (isTabletCapsule) {
                // Primary is Strip
                variants.push({
                    unit_name: 'Strip',
                    pack_size: `${formData.pack_size_primary}'s`,
                    mrp: parseFloat(formData.mrp_primary) || 0,
                    conversion_factor: parseInt(formData.pack_size_primary) || 1
                });

                // Secondary is Box
                if (formData.pack_size_secondary > 1) {
                    const totalUnits = (parseInt(formData.pack_size_primary) || 1) * (parseInt(formData.pack_size_secondary) || 1);
                    variants.push({
                        unit_name: 'Box',
                        pack_size: `${formData.pack_size_secondary}x${formData.pack_size_primary}'s`,
                        mrp: 0,
                        conversion_factor: totalUnits
                    });
                }
            } else {
                // Primary is Unit (Bottle/Tube/Vial)
                variants.push({
                    unit_name: 'Unit',
                    pack_size: '1',
                    mrp: parseFloat(formData.mrp_primary) || parseFloat(formData.sale_price) || 0,
                    conversion_factor: 1
                });

                // Secondary is Box (e.g. Box of 10 vials)
                if (formData.pack_size_secondary > 1) {
                    variants.push({
                        unit_name: 'Box',
                        pack_size: `${formData.pack_size_secondary}x1`,
                        mrp: 0,
                        conversion_factor: parseInt(formData.pack_size_secondary) || 1
                    });
                }
            }

            const payload = {
                ...formData,
                name: newName,
                packaging_variants: variants
            };
            const response = await saveProduct(payload);
            setFormData(prev => ({
                ...prev,
                original_name: newName,
                is_verified: true,
                needs_review: false
            }));
            return { success: true, data: response };
        } catch (err) {
            setErrors({ submit: err.message });
            return { success: false, error: err.message };
        } finally {
            setSaving(false);
        }
    };

    const resetForm = (item = null) => {
        setFormData(item || defaultState);
        setErrors({});
    };

    return {
        formData,
        setFormData,
        handleChange,
        handleSave,
        saving,
        errors,
        resetForm
    };
};
