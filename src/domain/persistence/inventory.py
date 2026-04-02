from typing import List, Dict, Any, Optional
import re
from src.utils.logging_config import get_logger
from src.domain.normalization import parse_pack_size
from src.domain.persistence.queries import QUERY_MERGE_PRODUCT, QUERY_UPDATE_SKU, QUERY_CREATE_LINE_ITEM

logger = get_logger(__name__)

def init_db_constraints(driver):
    """
    Ensures unique constraints exist for GlobalProduct item_code.
    """
    try:
        with driver.session() as session:
            # 1. GlobalProduct Constraint
            session.execute_write(lambda tx: tx.run("CREATE CONSTRAINT item_code_unique IF NOT EXISTS FOR (p:GlobalProduct) REQUIRE p.item_code IS UNIQUE"))
            
            # 2. Invoice ID Constraint (CRITICAL for performance)
            session.execute_write(lambda tx: tx.run("CREATE CONSTRAINT invoice_id_unique IF NOT EXISTS FOR (i:Invoice) REQUIRE i.invoice_id IS UNIQUE"))
            
            # 3. Invoice Number Index
            session.execute_write(lambda tx: tx.run("CREATE INDEX invoice_number_idx IF NOT EXISTS FOR (i:Invoice) ON (i.invoice_number)"))
            
            logger.info("Database constraints and indices initialized.")
    except Exception as e:
        logger.error(f"Failed to create constraints/indices: {e}")

def _generate_sku(tx, product_name: str) -> str:
    """
    Generates a Name-Based SKU (e.g., 'DOL-001') using a transactional counter.
    Format: AAA-NNN (First 3 letters of name - Sequential Number)
    """
    if not product_name:
        return "UNK-000"
        
    # 1. Extract Prefix (First 3 uppercase letters)
    clean_name = re.sub(r'[^a-zA-Z]', '', product_name).upper()
    prefix = (clean_name[:3] if len(clean_name) >= 3 else clean_name.ljust(3, 'X'))
    
    # 2. Atomically Increment Counter for this Prefix
    query = """
    MERGE (c:SkuCounter {prefix: $prefix})
    SET c.current_count = coalesce(c.current_count, 0) + 1
    RETURN c.current_count as num
    """
    result = tx.run(query, prefix=prefix).single()
    count = result["num"]
    
    # 3. Format SKU
    return f"{prefix}-{count:03d}"

def _ingest_line_items_batch_tx(tx, invoice_no: str, items_data: List[Dict[str, Any]], shop_id: str, tenant_id: str, invoice_id: str = None):
    """
    Creates multiple line items in a single transaction using UNWIND.
    Anchors to a Shop node instead of a User node for Multi-Tenancy.
    """
    # Use invoice_id for precise matching if available, otherwise fallback to number (legacy)
    match_clause = "MATCH (s)-[:HAS_INVOICE]->(i:Invoice {invoice_id: $invoice_id, tenant_id: $tenant_id})" if invoice_id else "MATCH (s)-[:HAS_INVOICE]->(i:Invoice {invoice_number: $invoice_no, tenant_id: $tenant_id})"
    
    batch_query = f"""
    MATCH (s:Shop {{id: $shop_id}})
    {match_clause}
    
    UNWIND $items as item
    
    // 1. Alias Lookup & Product Resolution (Scoped to Tenant)
    OPTIONAL MATCH (alias:ProductAlias {{raw_name: item.standard_item_name, tenant_id: $tenant_id}})-[:MAPS_TO]->(master:GlobalProduct {{tenant_id: $tenant_id}})
    WITH s, i, item, coalesce(master.name, item.standard_item_name) as final_product_name
    
    // 2. Merge Global Product (Enforced with tenant_id)
    MERGE (gp:GlobalProduct {{name: final_product_name, tenant_id: $tenant_id}})
    MERGE (s)-[:HAS_PRODUCT]->(gp)
    ON CREATE SET 
        gp.is_verified = false,
        gp.needs_review = true,
        gp.created_at = timestamp()
        
    // 3. Create Line Item (Specific Instance with tenant_id)
    CREATE (l:Line_Item {{tenant_id: $tenant_id}})
    SET l += item.properties
    SET l.created_at = timestamp()
    
    // 4. Connect Graph
    MERGE (i)-[:CONTAINS]->(l)
    MERGE (l)-[:IS_VARIANT_OF]->(gp)
    
    // 5. Merge HSN
    WITH s, gp, l, item
    CALL {{
        WITH l, item
        WHERE item.hsn_code IS NOT NULL
        MERGE (h:HSN {{code: item.hsn_code}})
        MERGE (l)-[:BELONGS_TO_HSN]->(h)
    }}
    
    // 6. Packaging Variant tracking (SKIP FOR RETURNS)
    WITH s, gp, l, item
    CALL {{
        WITH gp, l, item, s
        WHERE NOT item.is_return
        MERGE (pv:PackagingVariant {{pack_size: item.pack_size, product_name: gp.name, tenant_id: item.properties.tenant_id}})
        MERGE (gp)-[:HAS_VARIANT]->(pv)
        MERGE (l)-[:IS_PACKAGING_VARIANT]->(pv)
        ON CREATE SET
            pv.unit_name = item.unit_2nd,
            pv.mrp = item.mrp,
            pv.conversion_factor = item.conversion_factor,
            pv.primary_unit_name = item.primary_unit_name,
            pv.secondary_unit_name = item.secondary_unit_name,
            pv.created_at = timestamp()
        ON MATCH SET
            pv.mrp = item.mrp,
            pv.primary_unit_name = coalesce(item.primary_unit_name, pv.primary_unit_name),
            pv.secondary_unit_name = coalesce(item.secondary_unit_name, pv.secondary_unit_name),
            pv.updated_at = timestamp()
    }}
        
    // 7. Update Master Product Info (SKIP FOR RETURNS)
    WITH gp, item
    CALL {{
        WITH gp, item
        WHERE NOT item.is_return
        SET gp.sale_price = coalesce(item.mrp, gp.sale_price),
            gp.purchase_price = coalesce(item.unit_base_rate, gp.purchase_price),
            gp.tax_rate = coalesce(item.total_tax_rate, gp.tax_rate),
            gp.hsn_code = coalesce(item.hsn_code, gp.hsn_code),
            gp.category = coalesce(item.category, gp.category),
            gp.manufacturer = coalesce(item.manufacturer, gp.manufacturer),
            gp.salt_composition = coalesce(item.salt, gp.salt_composition),
            gp.base_unit = coalesce(item.base_unit, gp.base_unit),
            gp.unit_name = coalesce(item.base_unit, gp.unit_name)
    }}
    
    // 8. Rebuild Hierarchy JSON (APOC)
    WITH gp
    MATCH (gp)-[:HAS_VARIANT]->(all_v:PackagingVariant {{tenant_id: gp.tenant_id}})
    WITH gp, collect({{
        unit: all_v.unit_name, 
        pack: all_v.pack_size, 
        mrp: all_v.mrp,
        primary_unit: all_v.primary_unit_name,
        secondary_unit: all_v.secondary_unit_name
    }}) as hierarchy
    SET gp.packaging_hierarchy = apoc.convert.toJson(hierarchy)
    
    RETURN gp.name as name, gp.item_code as code
    """
    
    # Pre-process items for the batch
    prepared_items = []
    from src.domain.normalization.text import structure_packaging_hierarchy
    for item in items_data:
        pack_str = item.get("Pack_Size_Description")
        pack_data = parse_pack_size(pack_str)
        struct = structure_packaging_hierarchy(pack_str)
        
        # Tax Calculation
        total_tax_rate = float((item.get("SGST_Percent") or 0.0) + (item.get("CGST_Percent") or 0.0) + (item.get("IGST_Percent") or 0.0))
        if total_tax_rate == 0 and (item.get("GST_Percent") or 0.0) > 0:
            total_tax_rate = float(item.get("GST_Percent"))

        is_item_return = item.get("is_return", False)

        prepared_items.append({
            "standard_item_name": item.get("Standard_Item_Name"),
            "hsn_code": item.get("HSN_Code") or "UNKNOWN",
            "pack_size": pack_data.get("pack") or "1x1",
            "unit_2nd": item.get("Unit_2nd") or pack_data.get("unit"),
            "base_unit": struct.get("base_unit") if struct else "Unit",
            "primary_unit_name": struct.get("primary_unit_name") if struct else "Unit",
            "secondary_unit_name": struct.get("secondary_unit_name") if struct else "Box",
            "mrp": item.get("MRP", 0.0),
            "conversion_factor": pack_data.get("conversion_factor", 1),
            "total_tax_rate": total_tax_rate,
            "unit_base_rate": item.get("Unit_Base_Rate", 0.0),
            "category": item.get("category") or item.get("Category"),
            "manufacturer": item.get("manufacturer"),
            "salt": item.get("salt_composition"),
            "is_return": is_item_return,
            "properties": {
                "pack_size": pack_data.get("pack") or "1x1",
                "quantity": item.get("Standard_Quantity"),
                "free_quantity": item.get("Free_Quantity", 0.0),
                "net_amount": item.get("Net_Line_Amount"),
                "batch_no": item.get("Batch_No"),
                "hsn_code": item.get("HSN_Code") or "UNKNOWN",
                "mrp": item.get("MRP", 0.0),
                "expiry_date": item.get("Expiry_Date"),
                "landing_cost": item.get("Final_Unit_Cost", 0.0),
                "rate": item.get("Rate", 0.0),
                "total_tax_rate": total_tax_rate,
                "salt": item.get("salt_composition"),
                "category": item.get("category") or item.get("Category"),
                "manufacturer": item.get("manufacturer"),
                "unit_1st": item.get("Unit_1st") or pack_data.get("unit"),
                "unit_2nd": item.get("Unit_2nd") or pack_data.get("unit"),
                "sales_rate_a": item.get("Sales_Rate_A"),
                "calculated_tax_amount": item.get("Calculated_Tax_Amount", 0.0),
                "is_return": is_item_return
            }
        })

    # Execute Batch
    result = tx.run(batch_query, 
                    shop_id=shop_id, 
                    tenant_id=tenant_id,
                    invoice_no=invoice_no, 
                    invoice_id=invoice_id,
                    items=prepared_items)
    
    # Post-process SKUs for any new products created in this batch
    records = result.data()
    for rec in records:
        if not rec.get("code"):
            new_sku = _generate_sku(tx, rec["name"])
            tx.run(QUERY_UPDATE_SKU, name=rec["name"], sku=new_sku, tenant_id=tenant_id)

def link_product_alias(driver, shop_id: str, tenant_id: str, master_product_name: str, raw_alias: str):
    """
    Links a raw product name (alias) to a Master GlobalProduct.
    """
    with driver.session() as session:
        session.execute_write(_link_alias_tx, shop_id, tenant_id, master_product_name, raw_alias)

def _link_alias_tx(tx, shop_id, tenant_id, master_product_name, raw_alias):
    query = """
    MATCH (s:Shop {id: $shop_id})
    
    // Find Master Product (scoped to Shop)
    MATCH (s)-[:HAS_PRODUCT]->(gp:GlobalProduct {name: $master_name, tenant_id: $tenant_id})
    
    // Create Alias Node (Scoped to Tenant)
    MERGE (alias:ProductAlias {raw_name: $raw_alias, tenant_id: $tenant_id})
    
    // Link Alias to Master
    MERGE (alias)-[:MAPS_TO]->(gp)
    """
    tx.run(query, shop_id=shop_id, tenant_id=tenant_id, master_name=master_product_name, raw_alias=raw_alias)

def rename_product_with_alias(driver, shop_id: str, tenant_id: str, old_name: str, new_name: str):
    """
    Renames a GlobalProduct or Merges it if the new name already exists.
    Anchored to Shop.
    """
    with driver.session() as session:
        session.execute_write(_rename_product_tx, shop_id, tenant_id, old_name, new_name)

def _rename_product_tx(tx, shop_id, tenant_id, old_name, new_name):
    # Check if target exists (Merge Case vs Rename Case)
    check_q = """
    MATCH (s:Shop {id: $shop_id})-[:HAS_PRODUCT]->(gp:GlobalProduct {name: $new_name, tenant_id: $tenant_id})
    RETURN count(gp) as cnt
    """
    target_exists = tx.run(check_q, shop_id=shop_id, tenant_id=tenant_id, new_name=new_name).single()["cnt"] > 0
    
    if target_exists:
        # MERGE CASE: Repoint & Delete Old
        logger.info(f"Merging '{old_name}' into existing '{new_name}'")
        query = """
        MATCH (s:Shop {id: $shop_id})
        MATCH (s)-[:HAS_PRODUCT]->(old:GlobalProduct {name: $old_name, tenant_id: $tenant_id})
        MATCH (s)-[:HAS_PRODUCT]->(new:GlobalProduct {name: $new_name, tenant_id: $tenant_id})
        
        // 1. Repoint Alias links
        OPTIONAL MATCH (alias:ProductAlias {tenant_id: $tenant_id})-[r1:MAPS_TO]->(old)
        DELETE r1
        MERGE (alias)-[:MAPS_TO]->(new)
        
        // 2. Repoint Line Items (History)
        OPTIONAL MATCH (li:Line_Item {tenant_id: $tenant_id})-[r2:IS_VARIANT_OF]->(old)
        DELETE r2
        MERGE (li)-[:IS_VARIANT_OF]->(new)
        
        // 3. Repoint Packaging Variants
        OPTIONAL MATCH (old)-[r3:HAS_VARIANT]->(v:PackagingVariant {tenant_id: $tenant_id})
        DELETE r3
        MERGE (new)-[:HAS_VARIANT]->(v)
        SET v.product_name = $new_name
        
        // 4. Create Alias for the Old Name itself
        MERGE (self_alias:ProductAlias {raw_name: $old_name, tenant_id: $tenant_id})
        MERGE (self_alias)-[:MAPS_TO]->(new)
        
        // 5. Delete Old Node
        DETACH DELETE old
        """
        tx.run(query, shop_id=shop_id, tenant_id=tenant_id, old_name=old_name, new_name=new_name)
        
    else:
        # RENAME CASE: Just update name and create alias
        logger.info(f"Renaming '{old_name}' to new '{new_name}'")
        query = """
        MATCH (s:Shop {id: $shop_id})
        MATCH (s)-[:HAS_PRODUCT]->(gp:GlobalProduct {name: $old_name, tenant_id: $tenant_id})
        
        // 1. Create Alias for Old Name
        MERGE (alias:ProductAlias {raw_name: $old_name, tenant_id: $tenant_id})
        MERGE (alias)-[:MAPS_TO]->(gp)
        
        // 2. Update Product Name
        SET gp.name = $new_name,
            gp.updated_at = timestamp()
            
        // 3. Update related PackagingVariants' product_name property
        WITH gp
        OPTIONAL MATCH (gp)-[:HAS_VARIANT]->(pv:PackagingVariant {tenant_id: $tenant_id})
        SET pv.product_name = $new_name
        """
        tx.run(query, shop_id=shop_id, tenant_id=tenant_id, old_name=old_name, new_name=new_name)
