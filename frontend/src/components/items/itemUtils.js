/**
 * Logic to infer base units, packaging sizes, and MRPs from product data and variants.
 */
export const inferProductForm = (product) => {
    // 1. Category Detection & Base Unit
    let suggestedUnit = 'Unit'; // Default
    const cat = (product.category || '').toLowerCase();

    if (cat.includes('tab') || cat.includes('tablet')) suggestedUnit = 'Tablet';
    else if (cat.includes('cap') || cat.includes('capsule')) suggestedUnit = 'Capsule';
    else if (cat.includes('syp') || cat.includes('syrup') || cat.includes('liq') || cat.includes('susp')) suggestedUnit = 'Bottle';
    else if (cat.includes('inj') || cat.includes('vial') || cat.includes('amp')) suggestedUnit = 'Vial';
    else if (cat.includes('cream') || cat.includes('gel') || cat.includes('oint') || cat.includes('tube')) suggestedUnit = 'Tube';

    // 2. Smart Packing Extraction
    let primaryPack = 1;
    let secondaryPack = 1;
    let primaryMrp = 0;

    // Defaults if no variants
    if (!['Tablet', 'Capsule'].includes(suggestedUnit)) {
        primaryMrp = product.sale_price ? parseFloat(parseFloat(product.sale_price).toFixed(2)) : 0;
    }

    const variants = Array.isArray(product.packaging_variants) ? product.packaging_variants : [];

    // Strategy: First pass to find Primary Unit (Strip/Pack)
    if (['Tablet', 'Capsule'].includes(suggestedUnit)) {
        const stripVar = variants.find(v => {
            const cf = parseFloat(v.conversion_factor);
            return cf > 1 && cf <= 50;
        });

        if (stripVar) {
            primaryPack = parseFloat(stripVar.conversion_factor);
            primaryMrp = parseFloat(stripVar.mrp || 0);
        } else {
            const name = product.name || '';
            const qtyMatch = name.match(/(\d+)\s*(?:tabs|tablets|caps|capsules|'s|s|pcs|units|nos|ml|gm)\b/i) || 
                             name.match(/(?:pack|bottle|box)\s*(?:of|size)?\s*(\d+)/i);
            
            if (qtyMatch) {
                const extractedQty = parseInt(qtyMatch[1] || qtyMatch[2]);
                if (extractedQty > 0) {
                    primaryPack = extractedQty;
                    if (extractedQty >= 30 && !name.toLowerCase().includes('strip')) {
                        suggestedUnit = 'Bottle';
                    }
                } else {
                    primaryPack = 10;
                }
            } else {
                primaryPack = 10;
            }
        }
    } else {
        primaryPack = 1;
        const unitVar = variants.find(v => parseFloat(v.conversion_factor) === 1);
        if (unitVar && unitVar.mrp) {
            primaryMrp = parseFloat(unitVar.mrp);
        }
    }

    // Secondary Unit (Box/Outer)
    const boxVar = variants.find(v => {
        const name = (v.unit_name || '').toLowerCase();
        const cf = parseFloat(v.conversion_factor);
        return name.includes('box') || name.includes('outer') || (cf > primaryPack && cf > 1);
    });

    if (boxVar) {
        const totalUnits = parseFloat(boxVar.conversion_factor);
        const calculatedSec = totalUnits / primaryPack;
        if (calculatedSec >= 1) {
            secondaryPack = Math.floor(calculatedSec);
        }
    }

    return {
        original_name: product.name || '',
        name: product.name || '',
        hsn_code: product.hsn_code || (product.HSN || ''),
        purchase_price: product.purchase_price ? parseFloat(parseFloat(product.purchase_price).toFixed(2)) : 0,
        sale_price: product.sale_price ? parseFloat(parseFloat(product.sale_price).toFixed(2)) : 0,
        tax_rate: product.Raw_GST_Percentage ?? (product.tax_rate ?? (product.gst_percent ?? 0)),
        opening_stock: product.opening_stock ?? (!product.is_verified ? (product.quantity ?? 0) : 0),
        opening_boxes: 0,
        opening_strips: 0,
        min_stock: product.min_stock ?? 0,
        item_code: product.item_code || '',
        rack_location: product.rack_location || product.location || '',
        is_verified: product.is_verified,
        is_enriched: product.is_enriched || false,
        manufacturer: product.manufacturer || '',
        salt_composition: product.salt_composition || '',
        category: product.category || '',
        supplier_name: product.supplier_name || '',
        last_purchase_date: product.last_purchase_date || '',
        saved_by: product.saved_by || '',
        base_unit: product.base_unit || suggestedUnit,
        pack_size_primary: primaryPack,
        pack_size_secondary: secondaryPack,
        mrp_primary: primaryMrp,
        needs_review: product.needs_review,
        hsn_description: product.hsn_description || '',
        is_tax_inferred: product.is_tax_inferred || false
    };
};
