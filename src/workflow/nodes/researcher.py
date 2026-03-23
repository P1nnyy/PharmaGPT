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

async def enrich_line_items(state: InvoiceStateDict) -> Dict[str, Any]:
    """
    Researcher Node.
    Uses DuckDuckGo + LLM to enrich missing pharma details (Manufacturer, Salt Mapping).
    """
    normalized_items = state.get("normalized_items") or state.get("line_items", [])
    
    if not normalized_items:
        logger.warning("Researcher: No items to enrich (checked 'normalized_items' and 'line_items').")
        return {}

    logger.info(f"Researcher: checking {len(normalized_items)} items for enrichment needs...")
    
    ddgs = DDGS()
    enriched_count = 0
    updated_items = []

    for item in normalized_items:
        # Check condition: Manufacturer is Unknown OR Salt is missing
        mfr = item.get("Manufacturer", "Unknown")
        salt = item.get("salt_composition")  # Assuming lowercase from new schema
        
        # Also check legacy 'Salt' just in case
        if not salt: 
            salt = item.get("Salt")

        needs_enrichment = (not mfr or mfr.lower() == "unknown") or (not salt)
        
        if needs_enrichment:
            product_name = item.get("Standard_Item_Name") or item.get("Product") or "Unknown Product"
            if product_name.lower() == "unknown product":
                updated_items.append(item)
                continue
                
            try:
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
                        # ddgs.text is synchronous, running in an async node is okay as long as it's not too slow.
                        res = ddgs.text(query, max_results=2)
                        if res:
                            all_snippets.extend([f"- {r.get('title', '')}: {r.get('body', '')}" for r in res])
                    except Exception as e:
                        logger.warning(f"Search Query failed: {e}")
                
                if all_snippets:
                    search_results = "\n".join(all_snippets)
                
                # 2. LLM Analysis (Updated prompt for FMCG/OMC items)
                prompt = f"""
                Analyze these search results for the item "{product_name}".
                
                SEARCH SNIPPETS:
                {search_results}
                
                TASK:
                Extract official details for this product. 
                If it's a medicine, find active salts. 
                If it's an OMC/Personal Care item (like toothpaste, shampoo), find the main ingredients.
                
                EXPANSION HINTS: {", ".join(expanded_names)}
                
                OUTPUT FIELDS:
                1. manufacturer: Company Name (e.g. Colgate Palmolive, Sun Pharma)
                2. salt_composition: Leading active ingredients or salts.
                3. packaging_size: Best guess for pack size (e.g. 70g, 10 tablets).
                
                RULES:
                - Use the most credible source.
                - Return strictly valid JSON.
                
                OUTPUT FORMAT:
                {{
                    "manufacturer": "string or null",
                    "salt_composition": "string or null",
                    "packaging_size": "string or null"
                }}
                """
                
                response = await manager.generate_content_async(
                    model="gemini-2.0-flash",
                    contents=[prompt]
                )
                text = response.text.replace("```json", "").replace("```", "").strip()
                data = json.loads(text)
                
                found_mfr = data.get("manufacturer")
                found_salt = data.get("salt_composition")
                found_pack = data.get("packaging_size")
                
                # 3. Update Item
                did_update = False
                if found_mfr:
                    item["Manufacturer"] = found_mfr # Update Legacy
                    item["manufacturer"] = found_mfr # Update New
                    did_update = True
                
                if found_salt:
                    item["Salt"] = found_salt # Update Legacy
                    item["salt_composition"] = found_salt # Update New
                    did_update = True

                if found_pack:
                     item["Pack_Size_Description"] = found_pack
                     item["pack_size_description"] = found_pack
                     did_update = True
                    
                if did_update:
                    item["is_enriched"] = True
                    item["Logic_Note"] = (item.get("Logic_Note", "") + " [Enriched via Web]").strip()
                    enriched_count += 1
                    
            except Exception as e:
                logger.error(f"Researcher Error for {product_name}: {e}")
                
        updated_items.append(item)

    logger.info(f"Researcher: Completed. Enriched {enriched_count} items.")
    
    return {
        "normalized_items": updated_items,
        "line_items": updated_items # CRITICAL FIX: Ensure Critic/Graph sees the updates
    }
