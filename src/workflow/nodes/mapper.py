import google.generativeai as genai
import json
import os
from typing import Dict, Any, List
from src.workflow.state import InvoiceState as InvoiceStateDict
from src.utils.logging_config import get_logger
from src.services.embeddings import generate_embedding
from src.utils.config_loader import load_vendor_rules
from neo4j import GraphDatabase

logger = get_logger("mapper")

# Neo4j Config (Ad-hoc connection for Mapper RAG)
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

# Initialize Gemini
API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=API_KEY)

from langfuse import observe

@observe(name="mapper_execution")
def execute_mapping(state: InvoiceStateDict) -> Dict[str, Any]:
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
    # We check global modifiers for a hint, or just pass 'Unknown'
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
    
    # C. Model Setup
    model = genai.GenerativeModel("gemini-2.0-flash")
    context_text = "\n".join(raw_rows)
    
    # --- D. RAG: Dynamic Few-Shotting ---
    cheat_sheet = "No similar examples found."
    
    try:
        embedding = generate_embedding(context_text)
        found_example = None
        
        with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
            with driver.session() as session:
                # 1. Try Vector Search (> 0.88)
                if embedding:
                    query = """
                    CALL db.index.vector.queryNodes('invoice_examples_index', 1, $embedding)
                    YIELD node, score
                    WHERE score > 0.88
                    RETURN node.raw_text as raw, node.json_payload as json, score
                    """
                    result = session.run(query, embedding=embedding).single()
                    
                    if result:
                        found_example = {
                            "raw": result["raw"],
                            "json": result["json"],
                            "source": f"VECTOR MATCH ({result['score']:.2f})"
                        }

                # 2. Fallback: Supplier specific example
                if not found_example and current_supplier:
                    logger.info(f"Mapper: No vector match. Checking generic example for supplier '{current_supplier}'")
                    # Note: We rely on the Supplier Name being accurate from Surveyor/Global Modifiers
                    query_fallback = """
                    MATCH (s:Supplier)-[:HAS_EXAMPLE]->(e)
                    WHERE toLower(s.name) CONTAINS $supplier_lower 
                    RETURN e.raw_text as raw, e.json_payload as json
                    LIMIT 1
                    """
                    res_fallback = session.run(query_fallback, supplier_lower=current_supplier).single()
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
    
    
    # --- E. SMART MAPPER LOGIC (Alias & Vector Pre-Check) ---
    # Goal: Try to resolve Product Names via DB before asking LLM.
    # We iterate over raw_rows to find potential matches.
    
    # 1. Prepare Pre-Filled Context
    # We can't easily "inject" per-row logic into a single bulk-prompt without complex rewriting.
    # Strategy: We will ask the LLM to map as usual, BUT we provide a "Known Mappings" hint list.
    # OR better: We post-process the LLM output? 
    # USER REQUEST says: "Prioritize Alias Lookups... force the Standard_Item_Name".
    # Since the Mapper output is the source of truth for the next step, we can:
    # A. Parse raw rows locally (hard with unstructured text).
    # B. Use LLM to get preliminary JSON, THEN post-process with Alias Lookup against the 'Product' field the LLM extracted.
    # C. Pass "Known Aliases" to LLM?
    
    # DECISION: Post-Process the LLM Output.
    # Why? We need the LLM to extract the "Raw Name" first (e.g. from "Acitrom 2mg 10s" -> "Acitrom 2mg").
    # Once we have the "Product" field from JSON, we check if THAT is an alias.
    
    # Wait, the prompt says: "Before running the LLM... MATCH (a:ProductAlias {raw_name: $raw_ocr_text})"
    # This implies $raw_ocr_text is the full row or a specific column? 
    # If raw_rows are full generic text lines, matching "raw_name" is tricky unless exact match.
    # Let's assume we do POST-PROCESSING for robustness, OR we try to match substrings.
    # Let's stick to the prompt's spirit: "Teach the Mapper node to look for these aliases".
    
    # Let's Prompt, Get JSON, THEN Re-Map Names based on DB.
    # This is safer than trying to regex matches in raw text.
    
    # However, to support "Force Standard_Item_Name", we can do it after `data = json.loads(text)`.
    
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
    
    CRITICAL:
    1. **Merges**: DO NOT merge distinct products.
    2. **DUPLICATES**: If the raw text lists the SAME product twice, CREATE TWO JSON OBJECTS.
    3. **Noise**: Ignore header rows.
    
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
                "Amount": float
            }}
        ]
    }}
    """
    
    try:
        response = model.generate_content(prompt)
        text = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(text)
        
        mapped_items = data.get("line_items", [])
        
        # --- SMART MAPPING POST-PROCESS ---
        # Now that we have the "Product" (which is essentially the extracted raw name),
        # We query Neo4j to see if this name is an Alias or needs Auto-Correction via Vector.
        
        with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
            with driver.session() as session:
                for item in mapped_items:
                    raw_product_name = item.get("Product")
                    if not raw_product_name:
                        continue
                        
                    # 1. Alias Lookup (Exact Match)
                    # "Match (a:ProductAlias {raw_name: raw_product_name})..."
                    alias_query = """
                    MATCH (a:ProductAlias {raw_name: $name})-[:MAPS_TO]->(gp:GlobalProduct)
                    RETURN gp.name as master_name
                    """
                    alias_res = session.run(alias_query, name=raw_product_name).single()
                    
                    if alias_res:
                         master_name = alias_res["master_name"]
                         logger.info(f"SmartMapper: Found Alias '{raw_product_name}' -> '{master_name}'")
                         # FORCE OVERWRITE
                         item["Standard_Item_Name"] = master_name
                         item["Logic_Note"] = "Alias Match"
                         continue # Skip Vector Search
                         
                    # 2. Vector Search (High Confidence Fallback)
                    # If no alias, check if we have a very strong vector match for this product name
                    emb = generate_embedding(raw_product_name)
                    if emb:
                        vector_query = """
                        CALL db.index.vector.queryNodes('product_index', 1, $embedding)
                        YIELD node, score
                        WHERE score > 0.92
                        RETURN node.name as master_name, score
                        """
                        # Assuming we have a 'product_index' on GlobalProduct(name_embedding) or similar.
                        # If not, this step might fail or return nothing. 
                        # We use 'invoice_examples_index' usually, but here we want PRODUCT names.
                        # Let's assume GlobalProduct has an index. If not, we skip safety.
                        try:
                            vec_res = session.run(vector_query, embedding=emb).single()
                            if vec_res:
                                master_name = vec_res["master_name"]
                                score = vec_res["score"]
                                logger.info(f"SmartMapper: High-Conf Vector Match '{raw_product_name}' -> '{master_name}' ({score:.2f})")
                                
                                # Use Master Name but Flag for Review
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