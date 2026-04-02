from src.services.ai_client import manager
from typing import Dict, Any, List
import os
import json
import asyncio
from duckduckgo_search import DDGS
from src.workflow.state import InvoiceState as InvoiceStateDict
from src.utils.logging_config import get_logger

logger = get_logger("researcher")

async def expand_abbreviations(product_name: str) -> List[str]:
    """
    Uses LLM to guess full names from abbreviations (e.g., CS -> Colgate Sensitive).
    """
    prompt = f"""
    Given the product name from a pharmacy/FMCG invoice: "{product_name}"
    
    If it looks like an abbreviation or a shortened name, provide 1-2 possible full product names (e.g. "Colgate Sensitive" for "CS").
    If it's already a full name, just return the name as is.
    
    Return strictly JSON: {{"expansions": ["name1", "name2"]}}
    """
    try:
        response = await manager.generate_content_async(model="gemini-2.0-flash", contents=[prompt])
        data = json.loads(response.text.replace("```json", "").replace("```", "").strip())
        return data.get("expansions", [product_name])
    except Exception as e:
        logger.warning(f"Researcher abbreviation expansion failed: {e}")
        return [product_name]

async def process_single_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Worker function to enrich a single line item.
    """
    mfr = item.get("Manufacturer", "Unknown")
    salt = item.get("salt_composition") or item.get("Salt")
    
    needs_enrichment = (not mfr or mfr.lower() == "unknown") or (not salt)
    
    if not needs_enrichment:
        return item
    
    product_name = item.get("Standard_Item_Name") or item.get("Product") or "Unknown Product"
    if product_name.lower() == "unknown product":
        return item
        
    # --- LOCAL-FIRST CACHING ---
    from src.services.product_catalog import ProductCatalog
    catalog = ProductCatalog()
    match = catalog.find_match(product_name)
    
    if match:
        logger.info(f"Researcher: Local Match found for '{product_name}' -> '{match['known_name']}'. Skipping web search.")
        item["Standard_Item_Name"] = match.get("known_name")
        item["Pack_Size_Description"] = match.get("standard_pack")
        item["pack_size_description"] = match.get("standard_pack")
        item["is_enriched"] = True
        item["Logic_Note"] = (item.get("Logic_Note", "") + " [Enriched via Local Catalog]").strip()
        return item
    # ---------------------------

    try:
        ddgs = DDGS() # Initialize here, only if we actually need web search
        
        # 1. Broaden Search Strategy
        search_results = "No results found."
        search_queries = []
        
        # Step A: Expand name (e.g. CS -> Colgate Sensitive)
        expanded_names = await expand_abbreviations(product_name)
        for name in expanded_names:
            search_queries.append(f"{name} manufacturer composition India")
            search_queries.append(f"{name} brand owner active ingredients")
        
        # Remove duplicates and limit
        search_queries = list(dict.fromkeys(search_queries))[:3]
        
        all_snippets = []
        for query in search_queries:
            logger.info(f"Researcher: Searching for '{query}'...")
            try:
                # ddgs.text is synchronous, offload to thread
                res = await asyncio.to_thread(ddgs.text, query, max_results=2)
                if res:
                    all_snippets.extend([f"- {r.get('title', '')}: {r.get('body', '')}" for r in res])
            except Exception as e:
                logger.warning(f"Search Query failed: {e}")
        
        if all_snippets:
            search_results = "\n".join(all_snippets)
        
        # 2. LLM Analysis
        prompt = f"""
        Analyze these search results for the item "{product_name}".
        
        SEARCH SNIPPETS:
        {search_results}
        
        TASK:
        Extract official details for this product. 
        
        CATEGORIZATION:
        - Medicine: Prescription or OTC drugs (e.g. Paracetamol, Atorvastatin). Requires active salts.
        - FMCG/Personal Care: Diapers, Soaps, Shampoos, House-hold items (e.g. Pampers, Tide). 
          *CRITICAL*: For FMCG, leave 'salt_composition' as null unless it is a medicated product (e.g. Ketoconazole shampoo).
          Do NOT extract generic ingredients like 'Aloe vera', 'Moisturizer', 'Vitamin E' as salts for FMCG.
        
        EXPANSION HINTS: {", ".join(expanded_names)}
        
        OUTPUT FIELDS:
        1. product_type: String ("Medicine" or "FMCG")
        2. manufacturer: Official Company Name (e.g. P&G, Sun Pharma)
        3. salt_composition: Leading ACTIVE PHARMACEUTICAL INGREDIENTS (APIs) or salts. 
           Null for most FMCG.
        4. packaging_size: Best guess for pack size (e.g. Strip of 15 tablets, 70g tube).
        5. mrp: RAW numeric Maximum Retail Price (e.g. 150.0). No currency symbols.
        
        RULES:
        - Use the most credible source.
        - Important: Return strictly valid JSON.
        
        OUTPUT FORMAT:
        {{
            "product_type": "string",
            "manufacturer": "string or null",
            "salt_composition": "string or null",
            "packaging_size": "string or null",
            "mrp": "float or null"
        }}
        """
        
        response = await manager.generate_content_async(
            model="gemini-2.0-flash",
            contents=[prompt]
        )
        text = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(text)
        
        found_type = data.get("product_type", "Medicine")
        found_mfr = data.get("manufacturer")
        found_salt = data.get("salt_composition")
        
        # --- POST-PROCESSING HEURISTIC ---
        # Suppression of non-medicinal "filler" salts
        filler_salts = {"aloe vera", "moisturizer", "fragrance", "vitamin e", "green tea", "charcoal"}
        if found_type == "FMCG" and found_salt:
            if found_salt.lower() in filler_salts or len(found_salt.split(',')) > 5:
                # If it's a long list of ingredients for a diaper, or a common filler -> hide it.
                found_salt = None
        # ---------------------------------
        found_pack = data.get("packaging_size")
        web_mrp = data.get("mrp")
        
        # --- PHASE 2: MRP GUARDRAIL VALIDATION ---
        local_mrp = item.get("MRP")
        needs_review = False
        
        if web_mrp and local_mrp:
            try:
                # Sanitize web_mrp (it might be a string due to LLM variance)
                import re
                s_web = str(web_mrp).replace(',', '')
                match = re.search(r'(\d+(?:\.\d+)?)', s_web)
                web_mrp_f = float(match.group(1)) if match else 0.0
                local_mrp_f = float(local_mrp)
                
                if web_mrp_f > 0 and local_mrp_f > 0:
                    # PROMPT 2 GUARDRAIL: 20% THRESHOLD
                    difference_pct = abs(web_mrp_f - local_mrp_f) / local_mrp_f
                    
                    if difference_pct > 0.20:
                        logger.warning(f"MRP Guardrail: Large Discrepancy ({difference_pct*100:.1f}%) for {product_name}")
                        needs_review = True
                        item["Suggested_Web_MRP"] = web_mrp_f
                        item["Logic_Note"] = (item.get("Logic_Note", "") + 
                            f" [MRP Guardrail: Web suggests {web_mrp_f}, Invoice says {local_mrp_f}]").strip()
            except Exception as e:
                logger.warning(f"MRP Guardrail check failed: {e}")
        
        item["needs_review"] = needs_review or item.get("needs_review", False)
        # ------------------------------------------
        
        # 3. Update Item
        if found_mfr:
            item["Manufacturer"] = found_mfr
            item["manufacturer"] = found_mfr
        
        if found_salt:
            item["Salt"] = found_salt
            item["salt_composition"] = found_salt

        if found_pack:
             item["Pack_Size_Description"] = found_pack
             item["pack_size_description"] = found_pack
            
        if found_mfr or found_salt or (found_pack and not needs_review):
            item["is_enriched"] = True
            item["Logic_Note"] = (item.get("Logic_Note", "") + " [Enriched via Web]").strip()
        elif needs_review:
            item["is_enriched"] = True
            item["Logic_Note"] = (item.get("Logic_Note", "") + " [Enriched - Mismatch Detected]").strip()
            
    except Exception as e:
        logger.error(f"Researcher Error for {product_name}: {e}")
        
    return item

async def enrich_line_items(state: InvoiceStateDict) -> Dict[str, Any]:
    """
    Researcher Node. Parallelized for high speed.
    """
    normalized_items = state.get("normalized_items") or state.get("line_items", [])
    
    if not normalized_items:
        return {}

    logger.info(f"Researcher: Starting parallel enrichment for {len(normalized_items)} items...")
    
    # Process all items in parallel
    tasks = [process_single_item(item) for item in normalized_items]
    updated_items = await asyncio.gather(*tasks)

    enriched_count = sum(1 for item in updated_items if item.get("is_enriched"))
    logger.info(f"Researcher: Completed. Enriched {enriched_count} items.")
    
    return {
        "normalized_items": updated_items,
        "line_items": updated_items 
    }
