from src.services.ai_client import manager
import json
import os
import asyncio
from typing import Dict, Any, List
from src.workflow.state import InvoiceState as InvoiceStateDict
from src.utils.logging_config import get_logger
from src.services.embeddings import generate_embedding
from src.utils.config_loader import load_vendor_rules
from src.domain.smart_mapper import validate_and_fix_hsn, enrich_hsn_details
from src.utils.ai_retry import ai_retry
from src.services.database import get_db_driver

logger = get_logger("mapper")

# Neo4j Config
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

from langfuse import observe

@ai_retry
@observe(name="mapper_execution")
async def execute_mapping(state: InvoiceStateDict) -> Dict[str, Any]:
    """
    Mapper Node.
    Stage 2 of Extraction.
    Takes Raw Text Rows (from Worker) and maps them to the Strict Schema.
    """
    raw_rows = state.get("raw_text_rows", [])
    
    if not raw_rows:
        logger.warning("Mapper: No raw text rows found. Skipping.")
        return {}

    logger.info(f"Mapper: Processing {len(raw_rows)} raw text fragments...")
    
    # --- 1. Load Context & Memory ---
    # A. Vendor Rules (The "Context")
    vendor_rules = load_vendor_rules()
    
    # Identify Supplier from previous steps (Surveyor/Worker)
    current_supplier = state.get("global_modifiers", {}).get("Supplier_Name", "").lower()
    
    supplier_instruction = ""
    # Check if we have specific rules for this supplier
    for vendor_name, rules in vendor_rules.get("vendors", {}).items():
        if vendor_name.lower() in current_supplier:
            logger.info(f"Mapper: Applying Vendor Rules for '{vendor_name}'")
            supplier_instruction = f"""
            *** VENDOR SPECIFIC RULES FOR: {vendor_name} ***
            {rules.get('extraction_notes', '')}
            
            Column Mapping Overrides:
            {json.dumps(rules.get('aliases', {}), indent=2)}
            """
            break

    # B. Mistake Memory (The "Lessons")
    from src.services.mistake_memory import MEMORY
    rules_list = MEMORY.get_rules()
    memory_rules = "\n    ".join([f"- {r}" for r in rules_list]) if rules_list else "- No previous mistakes recorded."
    
    # C. Model Setup (Context Handling)
    context_text = "\n".join(raw_rows)
    
    # --- D. RAG: Dynamic Few-Shotting ---
    cheat_sheet = "No similar examples found."
    
    try:
        embedding = generate_embedding(context_text)
        found_example = None
        
        driver = get_db_driver()
        if driver:
            with driver.session() as session:
                # 1. Try Vector Search (> 0.88)
                if embedding:
                    query = """
                    CALL db.index.vector.queryNodes('invoice_examples_index', 1, $embedding)
                    YIELD node, score
                    WHERE score > 0.88
                    RETURN node.raw_text as raw, node.json_payload as json, score
                    """
                    result = session.execute_read(lambda tx: tx.run(query, embedding=embedding).single())
                    
                    if result:
                        found_example = {
                            "raw": result["raw"],
                            "json": result["json"],
                            "source": f"VECTOR MATCH ({result['score']:.2f})"
                        }

                # 2. Fallback: Supplier specific example
                if not found_example and current_supplier:
                    logger.info(f"Mapper: No vector match. Checking generic example for supplier '{current_supplier}'")
                    query_fallback = """
                    MATCH (s:Supplier)-[:HAS_EXAMPLE]->(e)
                    WHERE toLower(s.name) CONTAINS $supplier_lower 
                    RETURN e.raw_text as raw, e.json_payload as json
                    LIMIT 1
                    """
                    res_fallback = session.execute_read(lambda tx: tx.run(query_fallback, supplier_lower=current_supplier).single())
                    if res_fallback:
                         found_example = {
                            "raw": res_fallback["raw"],
                            "json": res_fallback["json"],
                            "source": f"SUPPLIER FALLBACK ({current_supplier})"
                        }

        if found_example:
            logger.info(f"Mapper: Using Few-Shot Example ({found_example['source']})")
            cheat_sheet = f"""
    Here is a correct example from your history:
    [INPUT RAW]:
    {found_example['raw']}
    
    [OUTPUT JSON]:
    {found_example['json']}
    """
    except Exception as e:
        logger.warning(f"Mapper RAG Lookup Failed: {e}")
    
    prompt = f"""
    You are a DATA STRUCTURE EXPERT.
    Your input is a raw, unstructured extraction from an invoice table (OCR Text).
    
    INPUT RAW TEXT:
    \"\"\"
    {context_text}
    \"\"\"
    
    {supplier_instruction}
    
    YOUR TASK:
    Convert this text into a VALID JSON array of line items.
    
    SCHEMA RULES:
    - **Product**: Full description.
    - **Pack**: Pack Size if visible (e.g. "1x10", "10's").
    - **Qty**: Numeric (Float). Billed Quantity.
    - **Free**: Numeric (Float). Free/Bonus Quantity.
    - **Batch**: Alphanumeric Batch Number. 
    - **Expiry**: Text date (MM/YY or DD/MM/YY).
    - **HSN**: Numeric HSN code (4-8 digits).
    - **Rate**: Unit Price.
    - **Amount**: Net Total (Inclusive of Tax).
    - **MRP**: Max Retail Price.
    - **Category**: Analyze Product Name & Pack Size.
        • If 'ml', 'susp', 'syp' -> 'Syrup'.
        • If 'inj', 'vial' -> 'Injection'.
        • If 'tab', 'cap', 'strip' -> 'Tablet'.
        • Default -> 'Unit'.

    **SMART EXTRACTION RULES:**
    1. **Manufacturer**: Extract from columns labeled Mfr, Mfg, CMPNY, or Company. If the table has a specific column for this, use it. If not, check if the Product Description starts with the company name (e.g., 'Cipla Dolo').
        - Also check if it's hidden in the Batch column (prefixes like LUPIN..., CIPLA...).
    2. **Tax Logic**: If line-item tax columns are ambiguous or empty, check the Invoice Footer text (e.g. "SGST 2.5%"). Apply this rate to all items in that slab.
         - Example: "SGST 2.5% + CGST 2.5%" -> Tax Rate = 5.0%
         - EXTRACT "Raw_GST_Percentage" if you see columns like "GST%", "Tax%", or split "SGST" + "CGST". Sum them if needed.
    3. **Scheme/Free Logic**: Look for columns labeled "Free", "Scheme", "Bonus", or "Sch".
         - Example: "10+2" Scheme -> Qty = 10, Free = 2.
         - If the column contains "10+2", split it: Qty=10, Free=2.
         - If separate "Free" column exists, map it to "Free".
    
    CRITICAL:
    1. **Merges**: DO NOT merge distinct products.
    2. **DUPLICATES**: If the raw text lists the SAME product twice, CREATE TWO JSON OBJECTS.
    3. **Noise**: Ignore header rows.
    4. **MRP vs UFC**: 
        - **IGNORE "UFC" / "Unit" / "Factor" / "Case" columns** when looking for MRP.
        - **MRP is a Price**, usually > 10.0. "UFC" is usually small integer (e.g. 10, 20, 1). 
        - If you see a column "UFC", "Unit", "Pack", DO NOT map it to MRP. Map it to "Pack" if appropriate.
    
    {cheat_sheet}
    
    SYSTEM MEMORY (PREVIOUS MISTAKES TO AVOID):
    {memory_rules}
    
    Output JSON format:
    {{
        "line_items": [
            {{
                "Product": "str",
                "Pack": "str",
                "Qty": float,
                "Free": float,
                "Batch": "str",
                "Expiry": "str",
                "HSN": "str",
                "MRP": float,
                "Rate": float,
                "Amount": float,
                "Category": "str",
                "Manufacturer": "str",
                "Salt": "str",
                "Raw_GST_Percentage": float
            }}
        ]
    }}
    """
    
    try:
        response = await manager.generate_content_async(
            model="gemini-2.0-flash",
            contents=[prompt]
        )
        text = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(text)
        
        mapped_items = data.get("line_items", [])
        
        # --- SMART MAPPING POST-PROCESS ---
        driver = get_db_driver()
        if driver:
            with driver.session() as session:
                for item in mapped_items:
                    raw_product_name = item.get("Product")
                    
                    # --- HSN & TAX ENRICHMENT ---
                    raw_hsn = item.get("HSN", "")
                    clean_hsn = validate_and_fix_hsn(raw_hsn)
                    item["HSN"] = clean_hsn
                    
                    rate_extracted = item.get("Raw_GST_Percentage") or 0.0
                    
                    if rate_extracted == 0 and clean_hsn != "0000":
                        enriched = enrich_hsn_details(clean_hsn)
                        tax_rate = float(enriched.get("tax") or 0.0)
                        if tax_rate > 0:
                            item["Raw_GST_Percentage"] = tax_rate
                            item["is_tax_inferred"] = True
                            item["hsn_description"] = enriched.get("desc", "")
                            
                            current_rate = float(item.get("Rate") or 0.0)
                            if current_rate > 0:
                                # tax_rate is already defined above
                                qty = float(item.get("Qty") or 1.0)
                                amount = float(item.get("Amount") or 0.0)
                                
                                is_already_base = False
                                if amount > 0:
                                    expected_if_base = current_rate * qty * (1 + tax_rate/100)
                                    if abs(expected_if_base - amount) < (amount * 0.05 + 1.0):
                                        is_already_base = True
                                
                                if not is_already_base:
                                    base_rate = round(current_rate / (1 + (tax_rate / 100)), 2)
                                    item["Rate"] = base_rate
                                    item["Logic_Note"] = f"Tax Inferred ({tax_rate}%) & Base Rate Calc ({current_rate}->{base_rate})"
                                else:
                                    item["Logic_Note"] = f"Tax Inferred ({tax_rate}%) [Rate Preserved]"
                            
                            logger.info(f"SmartMapper: Inferred Tax {enriched['tax']}% for HSN {clean_hsn} ({enriched.get('desc')})")

                    if not raw_product_name:
                        continue
                        
                    # 1. Alias Lookup
                    alias_query = """
                    MATCH (a:ProductAlias {raw_name: $name})-[:MAPS_TO]->(gp:GlobalProduct)
                    RETURN gp.name as master_name
                    """
                    alias_res = session.execute_read(lambda tx: tx.run(alias_query, name=raw_product_name).single())
                    
                    if alias_res:
                         master_name = alias_res["master_name"]
                         logger.info(f"SmartMapper: Found Alias '{raw_product_name}' -> '{master_name}'")
                         item["Standard_Item_Name"] = master_name
                         item["Logic_Note"] = "Alias Match"
                         continue
                         
                    # 2. Vector Search
                    emb = generate_embedding(raw_product_name)
                    if emb:
                        vector_query = """
                        CALL db.index.vector.queryNodes('product_index', 1, $embedding)
                        YIELD node, score
                        WHERE score > 0.92
                        RETURN node.name as master_name, score
                        """
                        try:
                            vec_res = session.execute_read(lambda tx: tx.run(vector_query, embedding=emb).single())
                            if vec_res:
                                master_name = vec_res["master_name"]
                                score = vec_res["score"]
                                logger.info(f"SmartMapper: High-Conf Vector Match '{raw_product_name}' -> '{master_name}' ({score:.2f})")
                                item["Standard_Item_Name"] = master_name
                                item["Logic_Note"] = f"Vector Match ({score:.2f})"
                                item["needs_review"] = True
                        except Exception as e:
                            logger.warning(f"SmartMapper Vector Check Error: {e}")
                            
        logger.info(f"Mapper: Successfully mapped {len(mapped_items)} items.")
        return {"line_item_fragments": mapped_items}
        
    except Exception as e:
        logger.error(f"Mapper Error: {e}")
        return {"error_logs": [f"Mapper Failed: {e}"]}