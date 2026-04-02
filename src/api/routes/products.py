
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Dict, Any
from src.services.database import get_db_driver
from src.api.routes.auth import get_current_user_email
from src.domain.schemas import ProductRequest, EnrichedProductResponse
from src.services.enrichment_agent import EnrichmentAgent
from src.utils.logging_config import get_logger, tenant_id_ctx

# Global instance of EnrichmentAgent
enrichment_agent = EnrichmentAgent()

router = APIRouter(prefix="/products", tags=["products"])

@router.get("/search", response_model=List[Dict[str, Any]])
async def search_products(q: str = Query(..., min_length=2)):
    """
    Search for products by name (Global Catalog).
    Returns a list of matching products (limit 20).
    """
    driver = get_db_driver()
    if not driver:
         raise HTTPException(status_code=503, detail="Database unavailable")

    query = """
    MATCH (gp:GlobalProduct {tenant_id: $tenant_id})
    WHERE toLower(gp.name) CONTAINS toLower($q)
    RETURN gp.name as name, gp.hsn_code as hsn_code, gp.sale_price as sale_price
    LIMIT 20
    """
    
    with driver.session() as session:
        tenant_id = tenant_id_ctx.get()
        return session.execute_read(lambda tx: [dict(record) for record in tx.run(query, q=q, tenant_id=tenant_id)])

@router.get("/enrich", response_model=EnrichedProductResponse)
async def enrich_product(
    q: str = Query(..., min_length=2, description="Product Name to enrich"),
    pack_size: str = Query(None, description="Local Pack Size validation hint")
):
    """
    Enrich product data using the EnrichmentAgent (1mg + Gemini).
    """
    try:
        result = enrichment_agent.enrich_product(q, local_pack_size=pack_size)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/review-queue", response_model=List[Dict[str, Any]])
async def get_review_queue(user_email: str = Depends(get_current_user_email)):
    """
    Fetch products requiring review (needs_review=true) along with their packaging hierarchy.
    """
    driver = get_db_driver()
    if not driver:
         raise HTTPException(status_code=503, detail="Database unavailable")

    query = """
    MATCH (u:User {email: $user_email})-[:MANAGES]->(gp:GlobalProduct {tenant_id: $tenant_id})
    WHERE gp.needs_review = true
    
    // Fetch line items (Scoped to Tenant)
    MATCH (l:Line_Item {tenant_id: $tenant_id})-[:IS_VARIANT_OF]->(gp)
    WITH gp, l ORDER BY l.created_at DESC
    
    // Get Supplier Name, Date, and Saved By from the Invoice (Scoped to Tenant)
    OPTIONAL MATCH (i:Invoice {tenant_id: $tenant_id})-[:CONTAINS]->(l)
    OPTIONAL MATCH (owner:User)-[:OWNS]->(i)
    
    WITH gp, 
         head(collect(l.description)) as incoming_name, 
         head(collect(l.hsn_code)) as incoming_hsn, 
         head(collect(i.supplier_name)) as supplier_name,
         head(collect(i.invoice_date)) as last_purchase_date,
         head(collect(owner.name)) as saved_by
    
    OPTIONAL MATCH (gp)-[:HAS_VARIANT]->(pv:PackagingVariant {tenant_id: $tenant_id})
    RETURN gp.name as name, 
           incoming_name,
           supplier_name,
           last_purchase_date,
           saved_by,
           coalesce(gp.hsn_code, incoming_hsn) as hsn_code, 
           gp.sale_price as sale_price,
           gp.tax_rate as tax_rate,
           gp.item_code as item_code,
           gp.purchase_price as purchase_price,
           gp.opening_stock as opening_stock,
           gp.min_stock as min_stock,
           coalesce(gp.location, null) as location,
           gp.is_verified as is_verified,
           coalesce(gp.manufacturer, null) as manufacturer,
           coalesce(gp.salt_composition, null) as salt_composition,
           coalesce(gp.category, null) as category,
           coalesce(gp.schedule, null) as schedule,
           collect({
               unit_name: coalesce(pv.unit_name, 'Unit'),
               pack_size: pv.pack_size,
               mrp: pv.mrp,
               conversion_factor: coalesce(pv.conversion_factor, 1)
           }) as packaging_variants
    LIMIT 100
    """

    
    with driver.session() as session:
        tenant_id = tenant_id_ctx.get()
        return session.execute_read(lambda tx: [dict(record) for record in tx.run(query, user_email=user_email, tenant_id=tenant_id)])

@router.get("/all", response_model=List[Dict[str, Any]])
async def get_all_products(user_email: str = Depends(get_current_user_email)):
    """
    Fetch ALL products managed by the user, including packaging hierarchy.
    """
    driver = get_db_driver()
    if not driver:
         raise HTTPException(status_code=503, detail="Database unavailable")

    query = """
    MATCH (u:User {email: $user_email})-[:MANAGES]->(gp:GlobalProduct {tenant_id: $tenant_id})
    WHERE gp.is_verified = true
    OPTIONAL MATCH (gp)-[:HAS_VARIANT]->(pv:PackagingVariant {tenant_id: $tenant_id})
    RETURN gp.name as name, 
           gp.hsn_code as hsn_code, 
           gp.sale_price as sale_price,
           gp.tax_rate as tax_rate,
           gp.item_code as item_code,
           gp.purchase_price as purchase_price,
           gp.opening_stock as opening_stock,
           gp.min_stock as min_stock,
           coalesce(gp.location, null) as location,
           gp.is_verified as is_verified,
           coalesce(gp.manufacturer, null) as manufacturer,
           coalesce(gp.salt_composition, null) as salt_composition,
           coalesce(gp.category, null) as category,
           coalesce(gp.schedule, null) as schedule,
           gp.needs_review as needs_review,
           collect({
               unit_name: coalesce(pv.unit_name, 'Unit'),
               pack_size: pv.pack_size,
               mrp: pv.mrp,
               conversion_factor: coalesce(pv.conversion_factor, 1)
           }) as packaging_variants
    ORDER BY gp.name
    LIMIT 1000
    """
    
    with driver.session() as session:
        tenant_id = tenant_id_ctx.get()
        return session.execute_read(lambda tx: [dict(record) for record in tx.run(query, user_email=user_email, tenant_id=tenant_id)])

@router.post("/", response_model=Dict[str, str])
async def save_product(product: ProductRequest, user_email: str = Depends(get_current_user_email)):
    """
    Create or Update a GlobalProduct and link it to the User's inventory management.
    Also updates Packaging Variants.
    """
    driver = get_db_driver()
    if not driver:
         raise HTTPException(status_code=503, detail="Database unavailable")

    query = """
    MATCH (s:Shop {id: $shop_id})
    MERGE (gp:GlobalProduct {name: $name, tenant_id: $tenant_id})
    
    // Link to Shop
    MERGE (s)-[:HAS_PRODUCT]->(gp)
    
    SET gp.hsn_code = $hsn_code,
        gp.item_code = $item_code,
        gp.sale_price = $sale_price,
        gp.purchase_price = $purchase_price,
        gp.tax_rate = $tax_rate,
        gp.opening_stock = $opening_stock,
        gp.min_stock = $min_stock,
        gp.location = $location,
        gp.updated_at = timestamp(),
        gp.is_verified = true,
        gp.needs_review = false,
        
        // New Fields
        gp.manufacturer = $manufacturer,
        gp.salt_composition = $salt_composition,
        gp.category = $category,
        gp.schedule = $schedule
    
    // Process Packaging Variants (Scoped to Tenant)
    WITH gp, $packaging_variants as variants, $tenant_id as tid
    // Clear old variants using DETACH DELETE to handle historical LineItem relationships
    OPTIONAL MATCH (gp)-[:HAS_VARIANT]->(old_v:PackagingVariant {tenant_id: tid})
    DETACH DELETE old_v
    
    WITH gp, variants, tid
    FOREACH (v IN variants |
        MERGE (pv:PackagingVariant {pack_size: v.pack_size, product_name: gp.name, tenant_id: tid})
        ON CREATE SET pv.id = randomUUID()
        MERGE (gp)-[:HAS_VARIANT]->(pv)
        SET pv.unit_name = v.unit_name,
            pv.mrp = v.mrp,
            pv.conversion_factor = v.conversion_factor,
            pv.primary_unit_name = v.primary_unit_name,
            pv.secondary_unit_name = v.secondary_unit_name,
            pv.updated_at = timestamp()
    )
    
    // Update base units from first variant
    WITH gp, variants
    WHERE size(variants) > 0
    WITH gp, variants[0] as first_v
    SET gp.base_unit = coalesce(first_v.primary_unit_name, gp.base_unit),
        gp.unit_name = coalesce(first_v.primary_unit_name, gp.unit_name)
        
    RETURN gp.name as name
    """
    
    # Serialize variants list of models to dicts
    variants_data = [v.dict() for v in product.packaging_variants]
    
    with driver.session() as session:
        shop_id = tenant_id_ctx.get()
        session.execute_write(lambda tx: tx.run(query, 
            shop_id=shop_id,
            tenant_id=shop_id,
            name=product.name,
            hsn_code=product.hsn_code,
            item_code=product.item_code,
            sale_price=product.sale_price,
            purchase_price=product.purchase_price,
            tax_rate=product.tax_rate,
            opening_stock=product.opening_stock,
            min_stock=product.min_stock,
            location=product.location,
            packaging_variants=variants_data,
            manufacturer=product.manufacturer,
            salt_composition=product.salt_composition,
            category=product.category,
            schedule=product.schedule
        ))
        
    return {"status": "success", "message": f"Product '{product.name}' saved successfully."}

@router.post("/rename", response_model=Dict[str, str])
async def rename_product(payload: Dict[str, str], name: str = Query(..., description="Current product name"), user_email: str = Depends(get_current_user_email)):
    """
    Rename a product. If new name exists, merges them. 
    Creates an alias for the old name.
    Payload: {"new_name": "New Name"}
    """
    new_name = payload.get("new_name")
    if not new_name:
        raise HTTPException(status_code=400, detail="New name is required")
        
    driver = get_db_driver()
    if not driver:
        raise HTTPException(status_code=503, detail="Database unavailable")
        
    from src.domain.persistence import rename_product_with_alias
    
    try:
        tenant_id = tenant_id_ctx.get()
        rename_product_with_alias(driver, user_email, tenant_id, name, new_name)
        return {"status": "success", "message": f"Renamed '{name}' to '{new_name}'"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/alias", response_model=Dict[str, str])
async def add_alias(payload: Dict[str, str], name: str = Query(..., description="Master product name"), user_email: str = Depends(get_current_user_email)):
    """
    Manually add an alias to a Master Product.
    Used for Review Queue confirmation.
    Payload: {"alias": "Raw Name"}
    """
    raw_alias = payload.get("alias")
    if not raw_alias:
         raise HTTPException(status_code=400, detail="Alias is required")

    driver = get_db_driver()
    if not driver:
         raise HTTPException(status_code=503, detail="Database unavailable")

    from src.domain.persistence import link_product_alias
    
    try:
        tenant_id = tenant_id_ctx.get()
        link_product_alias(driver, user_email, tenant_id, name, raw_alias)
        # Also assume review is done, so unflag 'needs_review'? 
        # For now, let frontend call save to clear flag or we do it here.
        # Let's do it here for convenience.
        with driver.session() as session:
            session.execute_write(lambda tx: tx.run("MATCH (gp:GlobalProduct {name: $name, tenant_id: $tenant_id}) SET gp.needs_review = false", name=name, tenant_id=tenant_id))
            
        return {"status": "success", "message": f"Linked alias '{raw_alias}' to '{name}'"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history", response_model=List[Dict[str, Any]])
async def get_product_history(name: str = Query(..., description="Product name"), user_email: str = Depends(get_current_user_email)):
    """
    Fetch purchase history for a specific product name.
    """
    driver = get_db_driver()
    if not driver:
         raise HTTPException(status_code=503, detail="Database unavailable")

    query = """
    MATCH (u:User {email: $user_email})-[:MANAGES]->(gp:GlobalProduct {name: $name, tenant_id: $tenant_id})
    MATCH (l:Line_Item {tenant_id: $tenant_id})-[:IS_VARIANT_OF]->(gp)
    MATCH (i:Invoice {tenant_id: $tenant_id})-[:CONTAINS]->(l)
    MATCH (u)-[:OWNS]->(i)
    RETURN i.invoice_date as date,
           i.supplier_name as supplier,
           i.invoice_number as invoice_no,
           l.quantity as quantity,
           l.net_amount as amount,
           l.mrp as mrp,
           l.batch_no as batch_no,
           l.expiry_date as expiry,
           l.pack_size as pack_size
    ORDER BY date DESC
    LIMIT 50
    """
    
    with driver.session() as session:
        tenant_id = tenant_id_ctx.get()
        return session.execute_read(lambda tx: [dict(record) for record in tx.run(query, user_email=user_email, tenant_id=tenant_id, name=name)])
