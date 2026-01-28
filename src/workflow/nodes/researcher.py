from typing import Dict, Any, List
import os
import json
import logging
import google.generativeai as genai
# from langchain_community.tools import DuckDuckGoSearchRun # REMOVED: Broken dependency
from duckduckgo_search import DDGS
from src.workflow.state import InvoiceState as InvoiceStateDict
from src.utils.logging_config import get_logger

logger = get_logger("researcher")

# Initialize Gemini
API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=API_KEY)

def enrich_line_items(state: InvoiceStateDict) -> Dict[str, Any]:
    """
    Researcher Node.
    Uses DuckDuckGo + LLM to enrich missing pharma details (Manufacturer, Salt Mapping).
    """
    normalized_items = state.get("normalized_items") or state.get("line_items", [])
    
    if not normalized_items:
        logger.warning("Researcher: No items to enrich (checked 'normalized_items' and 'line_items').")
        return {}

    logger.info(f"Researcher: checking {len(normalized_items)} items for enrichment needs...")
    
    # Initialize Search Tool
    # search_tool = DuckDuckGoSearchRun() # REMOVED
    ddgs = DDGS()
    model = genai.GenerativeModel("gemini-2.0-flash")

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
                
            query = f"{product_name} medicine manufacturer salt composition India"
            logger.info(f"Researcher: Searching web for '{product_name}'...")
            
            try:
                # 1. Search
                # search_results = search_tool.run(query)
                results = ddgs.text(query, max_results=3)
                if not results:
                     search_results = "No results found."
                else:
                     search_results = "\n".join([f"- {r.get('title', '')}: {r.get('body', '')}" for r in results])
                
                # 2. LLM Analysis
                prompt = f"""
                Analyze these search results for the medicine "{product_name}".
                
                SEARCH SNIPPETS:
                {search_results}
                
                TASK:
                Extract the following details:
                1. Manufacturer (Company Name)
                2. Salt Composition (Generic Name / Active Ingredients)
                3. Packaging Size (e.g. 10 Tablets, 1 Strip, 100ml Bottle)
                
                RULES:
                - If conflicting, use the most credible source or return null.
                - Do NOT hallucinate. If not found, return null.
                - Return strictly valid JSON.
                
                OUTPUT FORMAT:
                {{
                    "manufacturer": "string or null",
                    "salt_composition": "string or null",
                    "packaging_size": "string or null"
                }}
                """
                
                response = model.generate_content(prompt)
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
