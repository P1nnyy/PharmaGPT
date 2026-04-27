from src.services.ai_client import manager
from typing import Dict, Any, List
import os
import json
import asyncio
from duckduckgo_search import DDGS
from src.workflow.state import InvoiceState as InvoiceStateDict
from src.utils.logging_config import get_logger
from src.services.product_catalog import ProductCatalog

logger = get_logger("researcher")

# Still use a semaphore but now it governs chunks/batches if needed,
# although we batch everything into 1-2 calls natively.
RESEARCH_SEMAPHORE = asyncio.Semaphore(2)

async def expand_abbreviations_batch(product_names: List[str]) -> Dict[str, List[str]]:
    """
    Uses LLM to guess full names from a LIST of abbreviations in a single batch call.
    """
    if not product_names:
        return {}
        
    payload = {str(i): name for i, name in enumerate(product_names)}
    
    prompt = f"""
    You are a Pharmacy/FMCG abstraction resolution engine.
    Here is a dictionary of Product Names mapped by an ID:
    {json.dumps(payload, indent=2)}
    
    For each product:
    If it looks like an abbreviation or shortened name, provide 1-2 possible full product names (e.g. "Colgate Sensitive" for "CS").
    If it's already a full name, just return the name as is.
    
    Return strictly JSON mapping the ID to an array of string expansions:
    {{
        "0": ["name1", "name2"],
        "1": ["name1"]
    }}
    """
    try:
        response = await manager.generate_content_async(model="gemini-2.0-flash", contents=[prompt])
        data = json.loads(response.text.replace("```json", "").replace("```", "").strip())
        
        # Map back from ID to original name
        results = {}
        for i_str, expansions in data.items():
            try:
                original_name = payload[i_str]
                results[original_name] = expansions if isinstance(expansions, list) else [expansions]
            except KeyError:
                pass
        return results
    except Exception as e:
        logger.warning(f"Researcher batch abbreviation expansion failed: {e}")
        return {name: [name] for name in product_names}

async def _fetch_search_snippets(product_name: str, expansions: List[str], max_queries=2) -> str:
    """Helper to fetch DDGS search snippets without LLM intervention."""
    ddgs = DDGS()
    queries = []
    for name in expansions:
         queries.append(f"{name} manufacturer composition India")
         queries.append(f"{name} brand active ingredients")
    
    queries = list(dict.fromkeys(queries))[:max_queries]
    all_snippets = []
    
    for query in queries:
        try:
            res = await asyncio.to_thread(ddgs.text, query, max_results=1)
            if res:
                all_snippets.extend([f"- {r.get('title', '')}: {r.get('body', '')}" for r in res])
        except Exception:
            pass
            
    return "\n".join(all_snippets) if all_snippets else "No results."

async def analyze_snippets_batch(items_with_snippets: List[Dict]) -> Dict[str, Dict]:
    """
    Single LLM call to analyze search snippets for multiple items and extract normalized data.
    Input format: [{"id": "...", "name": "...", "snippets": "...", "local_mrp": 0.0}, ...]
    """
    if not items_with_snippets:
        return {}
        
    prompt = f"""
    Analyze these search results for multiple pharmacy/FMCG products.
    
    INPUT DATA:
    {json.dumps(items_with_snippets, indent=2)}
    
    TASK:
    Extract official details for EACH product by its "id".
    
    CATEGORIZATION:
    - Medicine: Prescription or OTC drugs (e.g. Paracetamol, Atorvastatin). Requires active salts.
    - FMCG/Personal Care: Diapers, Soaps, Shampoos (e.g. Pampers, Tide). 
      *CRITICAL*: For FMCG, leave 'salt_composition' as null unless medicated.
    
    OUTPUT FORMAT:
    Return strictly JSON mapping the "id" to the extracted parameters:
    {{
        "id_here": {{
            "product_type": "string",
            "manufacturer": "string or null",
            "salt_composition": "string or null",
            "packaging_size": "string or null",
            "mrp": "float or null"
        }}
    }}
    """
    try:
         response = await manager.generate_content_async(model="gemini-2.0-flash", contents=[prompt])
         text = response.text.replace("```json", "").replace("```", "").strip()
         return json.loads(text)
    except Exception as e:
         logger.warning(f"Batch analysis failed: {e}")
         return {}

async def enrich_line_items(state: InvoiceStateDict) -> Dict[str, Any]:
    """
    Batch-Optimized Researcher Node.
    """
    normalized_items = state.get("normalized_items") or state.get("line_items", [])
    if not normalized_items:
        return {}

    catalog = ProductCatalog()
    
    # 1. Triage Items
    items_to_web_search = []
    
    for idx, item in enumerate(normalized_items):
        mfr = item.get("Manufacturer", "Unknown")
        salt = item.get("salt_composition") or item.get("Salt")
        product_name = item.get("Standard_Item_Name") or item.get("Product") or "Unknown Product"
        
        needs_enrichment = (not mfr or mfr.lower() == "unknown") or (not salt)
        if not needs_enrichment or product_name.lower() == "unknown product":
            continue
            
        # Try Local Catalog first
        match = catalog.find_match(product_name)
        if match:
            item["Standard_Item_Name"] = match.get("known_name")
            item["Pack_Size_Description"] = match.get("standard_pack")
            item["pack_size_description"] = match.get("standard_pack")
            item["is_enriched"] = True
            item["Logic_Note"] = (item.get("Logic_Note", "") + " [Enriched via Local Catalog]").strip()
            continue
            
        # Queue for Web Research
        items_to_web_search.append({
            "idx": idx,
            "product_name": product_name,
            "local_mrp": item.get("MRP", 0.0),
            "ref_item": item
        })

    if not items_to_web_search:
        logger.info("Researcher: All items enriched via local cache or skipped.")
        return {
            "normalized_items": normalized_items,
            "line_items": normalized_items 
        }

    logger.info(f"Researcher: {len(items_to_web_search)} items require web enrichment. Batching LLM calls...")
    
    # 2. Batch Abbreviation Expansion (O(1) LLM Call)
    names_to_expand = [x["product_name"] for x in items_to_web_search]
    expansions_map = await expand_abbreviations_batch(names_to_expand)
    
    # 3. Concurrent Search (DuckDuckGo only - lightweight IO)
    async def _search_worker(x):
        exps = expansions_map.get(x["product_name"], [x["product_name"]])
        snippets = await _fetch_search_snippets(x["product_name"], exps)
        return {
            "id": str(x["idx"]),
            "name": x["product_name"],
            "snippets": snippets,
            "local_mrp": x["local_mrp"],
            "expansions": exps
        }
        
    search_tasks = [_search_worker(x) for x in items_to_web_search]
    search_results = await asyncio.gather(*search_tasks)
    
    # 4. Batch Analysis (O(1) LLM Call)
    analysis_results = await analyze_snippets_batch(search_results)
    
    # 5. Apply Results
    enriched_count = 0
    filler_salts = {"aloe vera", "moisturizer", "fragrance", "vitamin e", "green tea", "charcoal"}
    
    for x in items_to_web_search:
        idx_str = str(x["idx"])
        item = x["ref_item"]
        data = analysis_results.get(idx_str)
        
        if not data:
            continue
            
        found_type = data.get("product_type", "Medicine")
        found_mfr = data.get("manufacturer")
        found_salt = data.get("salt_composition")
        found_pack = data.get("packaging_size")
        web_mrp = data.get("mrp")
        
        # Post-Processing
        if found_type == "FMCG" and found_salt:
             if found_salt.lower() in filler_salts or len(found_salt.split(',')) > 5:
                  found_salt = None
                  
        local_mrp = x["local_mrp"]
        needs_review = False
        
        if web_mrp and local_mrp:
            try:
                import re
                s_web = str(web_mrp).replace(',', '')
                match = re.search(r'(\d+(?:\.\d+)?)', s_web)
                web_mrp_f = float(match.group(1)) if match else 0.0
                local_mrp_f = float(local_mrp)
                
                if web_mrp_f > 0 and local_mrp_f > 0:
                    difference_pct = abs(web_mrp_f - local_mrp_f) / local_mrp_f
                    if difference_pct > 0.20:
                        needs_review = True
                        item["Suggested_Web_MRP"] = web_mrp_f
                        item["Logic_Note"] = (item.get("Logic_Note", "") + 
                            f" [MRP Guardrail: Web suggests {web_mrp_f}, Invoice says {local_mrp_f}]").strip()
            except Exception:
                pass
        
        item["needs_review"] = needs_review or item.get("needs_review", False)
        
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
            item["Logic_Note"] = (item.get("Logic_Note", "") + " [Enriched via Web Batch]").strip()
            enriched_count += 1
        elif needs_review:
            item["is_enriched"] = True
            item["Logic_Note"] = (item.get("Logic_Note", "") + " [Enriched - Mismatch Detected]").strip()

    logger.info(f"Researcher: Completed Batch Enrichment. Affected {enriched_count} items.")
    
    return {
        "normalized_items": normalized_items,
        "line_items": normalized_items 
    }
