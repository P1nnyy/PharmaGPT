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
    query = "CREATE CONSTRAINT item_code_unique IF NOT EXISTS FOR (p:GlobalProduct) REQUIRE p.item_code IS UNIQUE"
    try:
        with driver.session() as session:
            session.run(query)
            logger.info("Checked/Created Unique Constraint for GlobalProduct.item_code")
    except Exception as e:
        logger.error(f"Failed to create constraint: {e}")

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

def _create_line_item_tx(tx, invoice_no: str, item: Dict[str, Any], raw_item: Any, user_email: str):
    # 1. Execute the Merge First (Resolves Product & Alias)
    result = tx.run(QUERY_MERGE_PRODUCT, 
                    user_email=user_email, 
                    invoice_no=invoice_no,
                    standard_item_name=item.get("Standard_Item_Name"))
    
    record = result.single()
    if not record:
        logger.error(f"Failed to merge product: {item.get('Standard_Item_Name')}")
        return
        
    final_name = record["name"]
    current_code = record["code"]
    
    # 2. SKU Generation Logic (Python Side)
    if not current_code:
        new_sku = _generate_sku(tx, final_name)
        logger.info(f"Generated SKU {new_sku} for new product {final_name}")
        tx.run(QUERY_UPDATE_SKU, name=final_name, sku=new_sku)
               
    # 3. Prepare Line Item Data
    logger.info(f"DEBUG_TX: Ingesting '{item.get('Standard_Item_Name')}' -> '{final_name}'")
    
    # Parse Pack Size (Moved import to top)
    pack_data = parse_pack_size(item.get("Pack_Size_Description"))
    final_pack = pack_data.get("pack") or "1x1"
    final_unit = pack_data.get("unit")
    
    # Calculate Total Tax %
    s = item.get("SGST_Percent") or 0.0
    c = item.get("CGST_Percent") or 0.0
    i = item.get("IGST_Percent") or 0.0
    g = item.get("GST_Percent") or 0.0
    
    total_tax_rate = float(s + c + i)
    if total_tax_rate == 0 and g > 0:
        total_tax_rate = float(g)
    
    # 4. Create Line Item & Connect
    tx.run(QUERY_CREATE_LINE_ITEM,
           user_email=user_email,
           invoice_no=invoice_no,
           final_product_name=final_name,
           pack_size=final_pack,
           quantity=item.get("Standard_Quantity"),
           free_quantity=item.get("Free_Quantity", 0.0),
           net_amount=item.get("Net_Line_Amount"),
           batch_no=item.get("Batch_No"),
           hsn_code=item.get("HSN_Code") or "UNKNOWN", 
           mrp=item.get("MRP", 0.0),
           rate=item.get("Rate", 0.0),
           total_tax_rate=total_tax_rate,
           expiry_date=item.get("Expiry_Date"),
           landing_cost=item.get("Final_Unit_Cost", 0.0),
           logic_note=item.get("Logic_Note", "N/A"),
           
           salt=item.get("salt_composition"), # UPDATED KEY
           category=item.get("category") or item.get("Category"),
           manufacturer=item.get("manufacturer"), # UPDATED KEY
           unit_1st=item.get("Unit_1st") or final_unit,
           unit_2nd=item.get("Unit_2nd") or final_unit,
           sales_rate_a=item.get("Sales_Rate_A"),
           sales_rate_b=item.get("Sales_Rate_B"),
           sales_rate_c=item.get("Sales_Rate_C"),
           sgst_percent=item.get("SGST_Percent"),
           cgst_percent=item.get("CGST_Percent"),
           igst_percent=item.get("IGST_Percent"),
           calculated_tax_amount=item.get("Calculated_Tax_Amount", 0.0)
    )

def link_product_alias(driver, user_email: str, master_product_name: str, raw_alias: str):
    """
    Links a raw product name (alias) to a Master GlobalProduct.
    """
    with driver.session() as session:
        session.execute_write(_link_alias_tx, user_email, master_product_name, raw_alias)

def _link_alias_tx(tx, user_email, master_product_name, raw_alias):
    query = """
    MATCH (u:User {email: $user_email})
    
    // Find Master Product (must exist and be managed by user or globally available)
    MATCH (gp:GlobalProduct {name: $master_name})
    
    // Create Alias Node
    MERGE (alias:ProductAlias {raw_name: $raw_alias})
    
    // Link Alias to Master
    MERGE (alias)-[:MAPS_TO]->(gp)
    """
    tx.run(query, user_email=user_email, master_name=master_product_name, raw_alias=raw_alias)

def rename_product_with_alias(driver, user_email: str, old_name: str, new_name: str):
    """
    Renames a GlobalProduct or Merges it if the new name already exists.
    In both cases, creates a ProductAlias for the old name pointing to the new name.
    """
    with driver.session() as session:
        session.execute_write(_rename_product_tx, user_email, old_name, new_name)

def _rename_product_tx(tx, user_email, old_name, new_name):
    # Check if target exists (Merge Case vs Rename Case)
    check_q = "MATCH (gp:GlobalProduct {name: $new_name}) RETURN count(gp) as cnt"
    target_exists = tx.run(check_q, new_name=new_name).single()["cnt"] > 0
    
    if target_exists:
        # MERGE CASE: Repoint & Delete Old
        logger.info(f"Merging '{old_name}' into existing '{new_name}'")
        query = """
        MATCH (u:User {email: $user_email})
        MATCH (old:GlobalProduct {name: $old_name})
        MATCH (new:GlobalProduct {name: $new_name})
        
        // 1. Repoint Alias links (Aliases pointing to Old now point to New)
        OPTIONAL MATCH (alias:ProductAlias)-[r1:MAPS_TO]->(old)
        DELETE r1
        MERGE (alias)-[:MAPS_TO]->(new)
        
        // 2. Repoint Line Items (History)
        OPTIONAL MATCH (li:Line_Item)-[r2:IS_VARIANT_OF]->(old)
        DELETE r2
        MERGE (li)-[:IS_VARIANT_OF]->(new)
        
        // 3. Repoint Packaging Variants
        OPTIONAL MATCH (old)-[r3:HAS_VARIANT]->(v:PackagingVariant)
        DELETE r3
        MERGE (new)-[:HAS_VARIANT]->(v)
        // Update variant product_name property
        SET v.product_name = $new_name
        
        // 4. Create Alias for the Old Name itself
        MERGE (self_alias:ProductAlias {raw_name: $old_name})
        MERGE (self_alias)-[:MAPS_TO]->(new)
        
        // 5. Delete Old Node
        DETACH DELETE old
        """
        tx.run(query, user_email=user_email, old_name=old_name, new_name=new_name)
        
    else:
        # RENAME CASE: Just update name and create alias
        logger.info(f"Renaming '{old_name}' to new '{new_name}'")
        query = """
        MATCH (u:User {email: $user_email})
        MATCH (gp:GlobalProduct {name: $old_name})
        
        // 1. Create Alias for Old Name
        MERGE (alias:ProductAlias {raw_name: $old_name})
        MERGE (alias)-[:MAPS_TO]->(gp)
        
        // 2. Update Product Name
        SET gp.name = $new_name,
            gp.updated_at = timestamp()
            
        // 3. Update related PackagingVariants' product_name property
        WITH gp
        OPTIONAL MATCH (gp)-[:HAS_VARIANT]->(pv:PackagingVariant)
        SET pv.product_name = $new_name
        """
        tx.run(query, user_email=user_email, old_name=old_name, new_name=new_name)
