
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

@router.post("/", response_model=Dict[str, str])
async def save_product(product: ProductRequest, user_email: str = Depends(get_current_user_email)):
    """
    Create or Update a GlobalProduct and link it to the User's inventory management.
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
        gp.updated_at = timestamp()
        
    RETURN gp.name as name
    """
    
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
            location=product.location
        )
        
    return {"status": "success", "message": f"Product '{product.name}' saved successfully."}
