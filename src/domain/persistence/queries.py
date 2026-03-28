
# --- Cypher Queries ---

QUERY_MERGE_PRODUCT = """
    MATCH (u:User {email: $user_email})
    MATCH (u)-[:OWNS]->(i:Invoice {invoice_id: $invoice_id, tenant_id: $tenant_id})
    
    // 1. Alias Lookup & Product Resolution (Scoped to Tenant)
    OPTIONAL MATCH (alias:ProductAlias {raw_name: $standard_item_name, tenant_id: $tenant_id})-[:MAPS_TO]->(master:GlobalProduct {tenant_id: $tenant_id})
    
    // Determine final name: Use Master if alias found, else use incoming name
    WITH coalesce(master.name, $standard_item_name) as final_product_name, u, i
    
    // 2. Merge Global Product (Scoped to Tenant)
    MERGE (gp:GlobalProduct {name: final_product_name, tenant_id: $tenant_id})
    
    // Ensure User manages this product
    MERGE (u)-[:MANAGES]->(gp)
    
    ON CREATE SET 
        gp.is_verified = false,
        gp.needs_review = true,
        gp.created_at = timestamp()
        
    // RETURN info needed for SKU check
    RETURN gp.name as name, gp.item_code as code
"""

QUERY_UPDATE_SKU = "MATCH (p:GlobalProduct {name: $name, tenant_id: $tenant_id}) SET p.item_code = $sku"

QUERY_CREATE_LINE_ITEM = """
    MATCH (u:User {email: $user_email})
    MATCH (u)-[:OWNS]->(i:Invoice {invoice_id: $invoice_id, tenant_id: $tenant_id})
    MATCH (gp:GlobalProduct {name: $final_product_name, tenant_id: $tenant_id})
    
    // 2. Merge HSN Node (Global - No tenant_id)
    MERGE (h:HSN {code: $hsn_code})
    
    // 3. Create Line Item (Specific Variant / Instance with tenant_id)
    CREATE (l:Line_Item {
        tenant_id: $tenant_id,
        pack_size: $pack_size,
        quantity: $quantity,
        free_quantity: $free_quantity,
        net_amount: $net_amount,
        batch_no: $batch_no,
        hsn_code: $hsn_code,
        mrp: $mrp,
        expiry_date: $expiry_date,
        landing_cost: $landing_cost,
        logic_note: $logic_note,
        
        // Pharma Fields
        salt: $salt,
        category: $category,
        manufacturer: $manufacturer,
        unit_1st: $unit_1st,
        unit_2nd: $unit_2nd,
        sales_rate_a: $sales_rate_a,
        sales_rate_b: $sales_rate_b,
        sales_rate_c: $sales_rate_c,

        sgst_percent: $sgst_percent,
        cgst_percent: $cgst_percent,
        igst_percent: $igst_percent,
        calculated_tax_amount: $calculated_tax_amount
    })
    
    // 4. Connect Graph
    MERGE (i)-[:CONTAINS]->(l)
    MERGE (l)-[:IS_VARIANT_OF]->(gp)
    MERGE (l)-[:BELONGS_TO_HSN]->(h)
    
    // 5. Packaging Variant Tracking (Scoped to Tenant)
    MERGE (pv:PackagingVariant {pack_size: $pack_size, product_name: $final_product_name, tenant_id: $tenant_id})
    MERGE (gp)-[:HAS_VARIANT]->(pv)
    MERGE (l)-[:IS_PACKAGING_VARIANT]->(pv)
    
    ON CREATE SET
        pv.unit_name = $unit_2nd,
        pv.mrp = $mrp,
        pv.conversion_factor = $conversion_factor,
        pv.created_at = timestamp(),
        gp.needs_review = true
        
    ON MATCH SET
        pv.mrp = $mrp,
        pv.updated_at = timestamp()
        
    // 6. UPDATE MASTER DATA (GlobalProduct) with latest pricing & metadata
    SET gp.sale_price = coalesce($mrp, gp.sale_price),
        // Calculate Effective Base Rate from Landing Cost (Tax Inclusive) to support correct UI Margin Calc
        gp.purchase_price = CASE 
            WHEN $landing_cost > 0 THEN $landing_cost / (1 + coalesce($total_tax_rate, 0) / 100.0)
            ELSE coalesce($rate, gp.purchase_price)
        END,
        gp.tax_rate = coalesce($total_tax_rate, gp.tax_rate),
        gp.hsn_code = coalesce($hsn_code, gp.hsn_code),
        
        // Update New Metadata if present
        gp.category = coalesce($category, gp.category),
        gp.manufacturer = coalesce($manufacturer, gp.manufacturer),
        gp.salt_composition = coalesce($salt, gp.salt_composition)

    // 7. DYNAMIC PACKAGING HIERARCHY UPDATE
    WITH gp, pv, $tenant_id as tid
    MATCH (gp)-[:HAS_VARIANT]->(all_v:PackagingVariant {tenant_id: tid})
    WITH gp, collect({unit: all_v.unit_name, pack: all_v.pack_size, mrp: all_v.mrp}) as hierarchy
    SET gp.packaging_hierarchy = apoc.convert.toJson(hierarchy)
"""
