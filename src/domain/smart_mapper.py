from typing import Dict, Any, List, Optional
from src.services.database import get_db_driver
import logging


# Hardcoded fallback for common Pharma HSNs (Performance Optimization)
COMMON_HSN_MAP = {
    "96032100": {"desc": "Toothbrush", "tax": 18.0},
    "30049011": {"desc": "Medicaments (Allopathic)", "tax": 12.0},
    "3004": {"desc": "Medicaments", "tax": 12.0},
    "2106": {"desc": "Food Supplement", "tax": 18.0}
}

def enrich_hsn_details(hsn_code: str) -> Dict[str, any]:
    """
    Looks up HSN description and standard tax rate.
    Priority: 1. Hardcoded Map 2. Neo4j Master Graph 3. Default
    """
    clean_code = str(hsn_code).replace(" ", "").strip()
    
    # 1. Quick Lookup
    if clean_code in COMMON_HSN_MAP:
        return COMMON_HSN_MAP[clean_code]
    
    # 2. Database Lookup (If you have an HSN Master Node)
    driver = get_db_driver()
    if driver:
        query = """
        MATCH (h:HSN {code: $code})
        RETURN h.description as desc, h.gst_rate as tax
        LIMIT 1
        """
        try:
            with driver.session() as session:
                result = session.run(query, code=clean_code).single()
                if result:
                    return {"desc": result["desc"], "tax": result["tax"]}
        except Exception:
            pass # Fallback to None

    return {"desc": "Unknown Category", "tax": 0.0}

def validate_and_fix_hsn(hsn_code: str) -> str:
    """
    Fixes common OCR errors (e.g. '3004 90' -> '300490')
    """
    if not hsn_code:
        return "0000"
    
    clean = ''.join(filter(str.isdigit, str(hsn_code)))
    
    # Logic: If < 4 digits, likely garbage or partial
    if len(clean) < 4:
        return clean.ljust(4, '0') # Pad? Or mark invalid?
        
    return clean

logger = logging.getLogger(__name__)

async def enrich_line_items_from_master(line_items: List[Dict[str, Any]], user_email: str) -> List[Dict[str, Any]]:
    """
    Smart Mapper (Advanced): 
    1. Lookup each line item in Master Inventory (Name/Alias).
    2. Handle HSN Validation (Lookup official description).
    3. Handle MRP Logic (Trust Invoice if different, else Auto-fill).
    """
    driver = get_db_driver()
    if not driver:
        logger.warning("DB Driver unavailable for Smart Mapper")
        return line_items

    enriched_items = []
    
    with driver.session() as session:
        for item in line_items:
            raw_desc = item.get("Product", "").strip()
            # Clean up description for better matching? 
            # Ideally the "Product" field is what we extracted.
            
            if not raw_desc:
                enriched_items.append(item)
                continue
            
            # 1. PRODUCT LOOKUP
            # Match by Name (Exact) OR Alias (Exact) OR Variant Description
            lookup_query = """
            MATCH (u:User {email: $user_email})
            OPTIONAL MATCH (u)-[:MANAGES]->(gp:GlobalProduct)
            WHERE toLower(gp.name) = toLower($desc)
            OR EXISTS {
                MATCH (gp)<-[:ALIAS_OF]-(alias:ProductAlias)
                WHERE toLower(alias.name) = toLower($desc)
            }
            RETURN gp.name as name, gp.hsn_code as hsn, gp.tax_rate as tax, gp.sale_price as mrp
            LIMIT 1
            """
            
            # Simple fallback for standard products if not in user's managed list?
            # For now, strictly User's inventory.
            
            rec = session.run(lookup_query, user_email=user_email, desc=raw_desc).single()
            
            logic_notes = []
            if item.get("Logic_Note"):
                logic_notes.append(item["Logic_Note"])

            if rec and rec["name"]:
                logger.info(f"Smart Mapper: Matched '{raw_desc}' -> '{rec['name']}'")
                
                # A. HSN / Tax Auto-Fill (Enforce Master Consistency)
                if rec["hsn"]:
                    # Always prefer Master HSN for consistency
                    if item.get("HSN") != rec["hsn"]:
                        old_hsn = item.get("HSN", "None")
                        item["HSN"] = rec["hsn"]
                        logic_notes.append(f"[HSN Standardized: {old_hsn} -> {rec['hsn']}]")
                
                # B. MRP Logic
                invoice_mrp = item.get("MRP")
                master_mrp = rec["mrp"]
                
                if invoice_mrp and invoice_mrp > 0:
                    # Invoice has MRP. Check deviation.
                    # Use tolerance for float comparison?
                    if master_mrp and abs(invoice_mrp - master_mrp) > 0.01:
                         # Deviation found. Trust Invoice.
                         logic_notes.append(f"[Price Update: Master({master_mrp}) -> Invoice({invoice_mrp})]")
                         # TODO: Optional - Flag for Master Update?
                else:
                    # Invoice missing MRP. Use Master.
                    if master_mrp and master_mrp > 0:
                        item["MRP"] = master_mrp
                        logic_notes.append(f"[Auto-filled MRP {master_mrp}]")
            
            # 2. HSN DESCRIPTION LOOKUP (Independent of Product Match)
            # If we have an HSN Code (extracted or filled), but no Description, try to fetch official text.
            hsn_code = item.get("HSN")
            if hsn_code and not item.get("HSN_Description"):
                 # Clean HSN? remove dots/spaces? usually 4-8 digits.
                 # DB stores as string.
                 hsn_query = """
                 MATCH (h:HSN {code: $code})
                 RETURN h.description as desc
                 LIMIT 1
                 """
                 hsn_rec = session.run(hsn_query, code=hsn_code).single()
                 if hsn_rec and hsn_rec["desc"]:
                     # We don't have a field "HSN_Description" in standard LineItem schema usually?
                     # Sometimes schema uses 'Description' for product. 
                     # Let's check where to put it. 
                     # If the Product Description is empty/gibberish, maybe replace it? 
                     # No, keep Product description.
                     # Maybe added a note or a specific field if frontend supports it.
                     # For now, let's append to logic note or if the "Product" was empty (unlikely).
                     pass 
            
            item["Logic_Note"] = " ".join(logic_notes)
            enriched_items.append(item)
            
    return enriched_items
