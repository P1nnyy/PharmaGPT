
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Dict, Any
from src.services.database import get_db_driver
from src.api.routes.auth import get_current_user_email
from src.domain.schemas import ProductRequest

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
    MATCH (gp:GlobalProduct)
    WHERE toLower(gp.name) CONTAINS toLower($q)
    RETURN gp.name as name, gp.hsn_code as hsn_code, gp.sale_price as sale_price
    LIMIT 20
    """
    
    with driver.session() as session:
        result = session.run(query, q=q)
        return [dict(record) for record in result]

@router.get("/review-queue", response_model=List[Dict[str, Any]])
async def get_review_queue(user_email: str = Depends(get_current_user_email)):
    """
    Fetch products requiring review (needs_review=true) along with their packaging hierarchy.
    """
    driver = get_db_driver()
    if not driver:
         raise HTTPException(status_code=503, detail="Database unavailable")

    query = """
    MATCH (u:User {email: $user_email})-[:MANAGES]->(gp:GlobalProduct)
    WHERE gp.needs_review = true
    
    // Fetch latest line item to show "Incoming" name and HSN
    OPTIONAL MATCH (l:Line_Item)-[:IS_VARIANT_OF]->(gp)
    WITH gp, l ORDER BY l.created_at DESC
    
    // Get Supplier Name, Date, and Saved By from the Invoice containing this line item
    OPTIONAL MATCH (i:Invoice)-[:CONTAINS]->(l)
    OPTIONAL MATCH (owner:User)-[:OWNS]->(i)
    
    WITH gp, 
         head(collect(l.description)) as incoming_name, 
         head(collect(l.hsn_code)) as incoming_hsn, 
         head(collect(i.supplier_name)) as supplier_name,
         head(collect(i.invoice_date)) as last_purchase_date,
         head(collect(owner.name)) as saved_by
    
    OPTIONAL MATCH (gp)-[:HAS_VARIANT]->(pv:PackagingVariant)
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
           gp.location as location,
           gp.is_verified as is_verified,
           gp.manufacturer as manufacturer,
           gp.salt_composition as salt_composition,
           gp.category as category,
           gp.schedule as schedule,
           collect({
               unit_name: coalesce(pv.unit_name, 'Unit'),
               pack_size: pv.pack_size,
               mrp: pv.mrp,
               conversion_factor: coalesce(pv.conversion_factor, 1)
           }) as packaging_variants
    LIMIT 100
    """

    
    with driver.session() as session:
        result = session.run(query, user_email=user_email)
        return [dict(record) for record in result]

@router.get("/all", response_model=List[Dict[str, Any]])
async def get_all_products(user_email: str = Depends(get_current_user_email)):
    """
    Fetch ALL products managed by the user, including packaging hierarchy.
    """
    driver = get_db_driver()
    if not driver:
         raise HTTPException(status_code=503, detail="Database unavailable")

    query = """
    MATCH (u:User {email: $user_email})-[:MANAGES]->(gp:GlobalProduct)
    OPTIONAL MATCH (gp)-[:HAS_VARIANT]->(pv:PackagingVariant)
    RETURN gp.name as name, 
           gp.hsn_code as hsn_code, 
           gp.sale_price as sale_price,
           gp.tax_rate as tax_rate,
           gp.item_code as item_code,
           gp.purchase_price as purchase_price,
           gp.opening_stock as opening_stock,
           gp.min_stock as min_stock,
           gp.location as location,
           gp.is_verified as is_verified,
           gp.manufacturer as manufacturer,
           gp.salt_composition as salt_composition,
           gp.category as category,
           gp.schedule as schedule,
           gp.needs_review as needs_review,
           collect({
               unit_name: coalesce(pv.unit_name, 'Unit'),
               pack_size: pv.pack_size,
               mrp: pv.mrp,
               conversion_factor: coalesce(pv.conversion_factor, 1)
           }) as packaging_variants
    ORDER BY gp.name
    LIMIT 200
    """
    
    with driver.session() as session:
        result = session.run(query, user_email=user_email)
        return [dict(record) for record in result]

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
    MATCH (u:User {email: $user_email})
    MERGE (gp:GlobalProduct {name: $name})
    
    // Ensure User manages this product (ownership/access)
    MERGE (u)-[:MANAGES]->(gp)
    
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
    
    // Process Packaging Variants
    WITH gp, $packaging_variants as variants
    // Clear old variants to allow clean save (pseudo-overwrite)
    OPTIONAL MATCH (gp)-[r:HAS_VARIANT]->()
    DELETE r
    
    WITH gp, variants
    FOREACH (v IN variants |
        MERGE (pv:PackagingVariant {pack_size: v.pack_size, product_name: gp.name})
        ON CREATE SET pv.id = randomUUID()
        MERGE (gp)-[:HAS_VARIANT]->(pv)
        SET pv.unit_name = v.unit_name,
            pv.mrp = v.mrp,
            pv.conversion_factor = v.conversion_factor,
            pv.updated_at = timestamp()
    )
        
    RETURN gp.name as name
    """
    
    # Serialize variants list of models to dicts
    variants_data = [v.dict() for v in product.packaging_variants]
    
    with driver.session() as session:
        session.run(query, 
            user_email=user_email,
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
        )
        
    return {"status": "success", "message": f"Product '{product.name}' saved successfully."}

@router.post("/{name}/rename", response_model=Dict[str, str])
async def rename_product(name: str, payload: Dict[str, str], user_email: str = Depends(get_current_user_email)):
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
        rename_product_with_alias(driver, user_email, name, new_name)
        return {"status": "success", "message": f"Renamed '{name}' to '{new_name}'"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{name}/alias", response_model=Dict[str, str])
async def add_alias(name: str, payload: Dict[str, str], user_email: str = Depends(get_current_user_email)):
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
        link_product_alias(driver, user_email, name, raw_alias)
        # Also assume review is done, so unflag 'needs_review'? 
        # For now, let frontend call save to clear flag or we do it here.
        # Let's do it here for convenience.
        with driver.session() as session:
            session.run("MATCH (gp:GlobalProduct {name: $name}) SET gp.needs_review = false", name=name)
            
        return {"status": "success", "message": f"Linked alias '{raw_alias}' to '{name}'"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{name}/history", response_model=List[Dict[str, Any]])
async def get_product_history(name: str, user_email: str = Depends(get_current_user_email)):
    """
    Fetch purchase history for a specific product name.
    """
    driver = get_db_driver()
    if not driver:
         raise HTTPException(status_code=503, detail="Database unavailable")

    query = """
    MATCH (u:User {email: $user_email})-[:MANAGES]->(gp:GlobalProduct {name: $name})
    MATCH (l:Line_Item)-[:IS_VARIANT_OF]->(gp)
    MATCH (i:Invoice)-[:CONTAINS]->(l)
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
        result = session.run(query, user_email=user_email, name=name)
        return [dict(record) for record in result]
