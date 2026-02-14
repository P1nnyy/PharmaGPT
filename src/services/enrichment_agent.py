import re
import json
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
from typing import Dict, Any, Optional
from src.utils.logging_config import get_logger
from src.services.embeddings import API_KEY

logger = get_logger(__name__)

if API_KEY:
    genai.configure(api_key=API_KEY)

class EnrichmentAgent:
    def __init__(self):
        self.model = genai.GenerativeModel("models/gemini-2.5-flash")
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Origin': 'https://www.1mg.com',
            'Referer': 'https://www.1mg.com/'
        }

    def search_product(self, product_name: str) -> Optional[str]:
        """
        Searches for the product using 1mg's autocomplete API.
        """
        logger.info(f"Searching 1mg API for: {product_name}")
        search_url = "https://www.1mg.com/api/v1/search/autocomplete"
        params = {"name": product_name, "pageSize": 5}
        
        try:
            response = requests.get(search_url, params=params, headers=self.headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            items = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                # Try common keys
                if 'results' in data:
                    items = data['results']
                elif 'suggestions' in data:
                    items = data['suggestions']
                elif 'result' in data:
                    items = data['result']
            
            if items:
                for item in items:
                    # Check for valid url_path
                    url_path = item.get('url_path', '')
                    if url_path and (url_path.startswith('/drugs/') or url_path.startswith('/otc/')):
                        full_url = f"https://www.1mg.com{url_path}"
                        logger.info(f"Found 1mg product URL: {full_url}")
                        return full_url
            
            # Sometimes the structure might be different (e.g. nested in "result"), 
            # but the test showed a direct list of objects.
            
            logger.warning(f"No product links found on 1mg API for {product_name}")
            return None
            
        except Exception as e:
            logger.error(f"1mg API search failed: {e}")
            return None

    def scrape_page(self, url: str) -> Optional[str]:
        """
        Fetches the page content and extracts text using BeautifulSoup.
        """
        logger.info(f"Scraping URL: {url}")
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style", "header", "footer", "nav"]):
                script.decompose()
            
            # Get text
            text = soup.get_text()
            
            # Break into lines and remove leading/trailing space on each
            lines = (line.strip() for line in text.splitlines())
            # Break multi-headlines into a line each
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            # Drop blank lines
            text = '\n'.join(chunk for chunk in chunks if chunk)
            
            # Limit context window (20k chars is generous)
            return text[:20000] 
        except Exception as e:
            logger.error(f"Scraping failed for {url}: {e}")
            return None

    def extract_details(self, text: str) -> Dict[str, Any]:
        """
        Uses Gemini to parse raw text into structured JSON.
        """
        logger.info("Extracting details with Gemini...")
        prompt = """
        You are a pharmaceutical data expert. I will provide text scraped from a medicine product page.
        Extract the following details into a valid JSON object:
        - manufacturer (string): Name of the pharmaceutical company (e.g., "Sun Pharma", "Lupin").
        - salt_composition (string): The COMPLETE list of active ingredients/salts with their strengths. 
          * For combination drugs, include ALL ingredients (e.g., "Metformin (500mg) + Glimepiride (1mg)").
          * Do NOT just list one ingredient if multiple are present.
          * Ensure strengths match the product name if mentioned.
        - pack_size (string): The packaging information (e.g., "Strip of 15 tablets", "1 Vial").
        - category (string): The PHYSICAL FORM of the product (e.g., "Tablet", "Capsule", "Injection", "Vial", "Cream", "Syrup", "Gel", "Drops", "Inhaler"). 
          * Do NOT put the therapeutic class here (e.g. do NOT put "Anti-diabetic").
          * If it is a Vial or Ampoule, use "Injection".

        If a field is not found, use null.
        Do not add any markdown formatting like ```json ... ```. Just return the raw JSON string.
        
        Input Text:
        """
        
        try:
            response = self.model.generate_content(prompt + text)
            raw_json = response.text.strip()
            # Clean potential markdown
            if raw_json.startswith("```json"):
                raw_json = raw_json[7:]
            if raw_json.endswith("```"):
                raw_json = raw_json[:-3]
            
            return json.loads(raw_json)
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return {}

    def verify_pack_match(self, web_pack: str, local_pack: str) -> bool:
        """
        Uses Gemini to check if the web pack size matches the local invoice pack size.
        """
        if not web_pack or not local_pack:
            return False
            
        logger.info(f"Verifying Pack Match: Web='{web_pack}' vs Local='{local_pack}'")
        prompt = f"""
        Compare these two pharmaceutical pack sizes. determine if they represent the same quantity.
        
        Pack 1 (Web): {web_pack}
        Pack 2 (Invoice): {local_pack}
        
        Examples of Match:
        - "Strip of 15" vs "1x15" -> YES
        - "10 Tablet" vs "1x10" -> YES
        - "Bottle of 100ml" vs "100ml" -> YES
        
        Examples of Mismatch:
        - "Strip of 15" vs "1x10" -> NO
        - "10 Tablet" vs "strip of 4" -> NO

        Return ONLY JSON: {{"match": true}} or {{"match": false}}
        """
        try:
            response = self.model.generate_content(prompt)
            data = json.loads(response.text.strip().replace("```json", "").replace("```", ""))
            return data.get("match", False)
        except Exception as e:
            logger.error(f"Pack verification failed: {e}")
            return False

            logger.error(f"1mg API search failed: {e}")
            return []

    def _clean_product_name(self, name: str) -> str:
        """
        Removes common noise words to improve search matching.
        e.g. "LIVO-LUK SOLUTION 200ML" -> "LIVO-LUK"
        """
        # Remove pack sizes (e.g. 200ml, 10s, 1x15)
        name = re.sub(r'\b\d+[gm]l?\b', '', name, flags=re.IGNORECASE) # 200ml, 50g
        name = re.sub(r'\b\d+x\d+\b', '', name, flags=re.IGNORECASE)   # 1x15
        
        # Remove form factors if they might confuse search
        # strategies usually work better with just Brand Name
        banned = ['SOLUTION', 'SYRUP', 'TABLET', 'CAPSULE', 'INJECTION', 'EYE', 'EAR', 'DROPS', 'SUSPENSION']
        for word in banned:
            name = re.sub(r'\b' + word + r'\b', '', name, flags=re.IGNORECASE)
            
        # Remove extra spaces/dashes if they are isolated
        name = name.replace('-', ' ').strip()
        return " ".join(name.split())

    def search_product_multi(self, product_name: str, limit: int = 3) -> list:
        """
        Searches for the product and returns top N URLs.
        Includes Stricter relevance filtering and Retry Logic.
        """
        logger.info(f"Searching 1mg API for top {limit}: {product_name}")
        search_url = "https://www.1mg.com/api/v1/search/autocomplete"
        
        def fetch_results(query):
            try:
                params = {"name": query, "pageSize": 10}
                response = requests.get(search_url, params=params, headers=self.headers, timeout=10)
                response.raise_for_status()
                data = response.json()
                items = []
                if isinstance(data, list): items = data
                elif isinstance(data, dict):
                    if 'results' in data: items = data['results']
                    elif 'suggestions' in data: items = data['suggestions']
                    elif 'result' in data: items = data['result']
                return items
            except Exception as e:
                 logger.error(f"Search failed for '{query}': {e}")
                 return []

        # 1. Primary Search
        items = fetch_results(product_name)
        
        # 2. Fallback Search (Cleaned Name) if no results or low relevance suspected
        # We process primary results first. If none are relevant, we trigger fallback.
        
        urls = []
        from difflib import SequenceMatcher

        def process_items(candidate_items, query_str):
            # Clean the query for relevance check (remove noise like "Solution", "Tablet")
            # We want to match BRAND NAME, not form factor.
            clean_query_for_relevance = self._clean_product_name(query_str)
            if len(clean_query_for_relevance) < 3:
                clean_query_for_relevance = query_str # Fallback if cleaning stripped everything

            found_urls = []
            for item in candidate_items:
                url_path = item.get('url_path', '')
                result_name = item.get('name', '')
                
                # RELEVANCE CHECK
                # 1. Similarity on full strings (still useful for close matches)
                similarity = SequenceMatcher(None, query_str.lower(), result_name.lower()).ratio()
                
                # 2. Token Overlap on CLEANED strings
                # This prevents "Solution" matching "Salytar Solution"
                clean_result_name = self._clean_product_name(result_name)
                
                q_tokens = set(clean_query_for_relevance.lower().split())
                r_tokens = set(clean_result_name.lower().split())
                
                overlap = len(q_tokens.intersection(r_tokens))
                
                is_relevant = False
                if similarity > 0.6: is_relevant = True # Bumped threshold
                elif overlap >= 1: is_relevant = True
                
                # 3. Normalized Substring Check (Handle "Livo-Luk" vs "Livoluk")
                # Remove spaces and check if query is inside result
                norm_q = clean_query_for_relevance.lower().replace(" ", "")
                norm_r = clean_result_name.lower().replace(" ", "")
                
                if len(norm_q) > 3 and norm_q in norm_r:
                    is_relevant = True
                
                # Strict check: If query is short (brand name), ensures it's in result
                if len(query_str) < 10 and query_str.lower() not in result_name.lower():
                     # e.g. Query "Livo" should be in "Livo-Luk" (ok) but maybe not "Livogen" (ok)
                     pass

                if not is_relevant:
                    continue

                if url_path and (url_path.startswith('/drugs/') or url_path.startswith('/otc/')):
                    full_url = f"https://www.1mg.com{url_path}"
                    if full_url not in found_urls:
                        found_urls.append(full_url)
            return found_urls

        urls = process_items(items, product_name)
        
        # 3. Retry with Clean Name if results are empty
        if not urls:
            clean_name = self._clean_product_name(product_name)
            if clean_name and clean_name.lower() != product_name.lower() and len(clean_name) > 2:
                logger.info(f"Primary search failed. Retrying with cleaned name: '{clean_name}'")
                fallback_items = fetch_results(clean_name)
                # Process with cleaned name as relevance target
                urls = process_items(fallback_items, clean_name)
        
        logger.info(f"Found {len(urls)} URLs for {product_name} (final)")
        return urls[:limit]

    def extract_details_multi(self, texts: list) -> Dict[str, Any]:
        """
        Uses Gemini to synthesize details from multiple source texts.
        """
        logger.info(f"Synthesizing details from {len(texts)} sources with Gemini...")
        
        combined_text = ""
        for i, text in enumerate(texts):
            combined_text += f"\n--- SOURCE {i+1} ---\n{text[:10000]}\n"

        prompt = """
        You are a pharmaceutical data expert. I will provide text extracted from MULTIPLE different sources for the same product.
        Your job is to SYNTHESIZE the information and extract the most accurate details into a valid JSON object.
        
        Rules:
        1. Compare information across sources. If they adhere to the same product, trust the one with more detail.
        2. If sources conflict (e.g. different pack sizes), prioritize the one that seems to match the "standard" pack most often or list the most common one.
        3. EXTRACT:
           - manufacturer (string): Name of the pharmaceutical company (e.g., "Sun Pharma", "Lupin").
           - salt_composition (string): The COMPLETE list of active ingredients/salts with their strengths. 
             * For combination drugs, include ALL ingredients.
           - pack_size (string): The packaging information (e.g., "Strip of 15 tablets", "1 Vial").
           - category (string): The PHYSICAL FORM of the product (e.g., "Tablet", "Capsule", "Injection", "Vial", "Cream", "Syrup"). 
             * If it is a Vial or Ampoule, use "Injection".

        If a field is not found in ANY source, use null.
        Do not add any markdown formatting like ```json ... ```. Just return the raw JSON string.
        
        Input Text:
        """
        
        try:
            response = self.model.generate_content(prompt + combined_text)
            raw_json = response.text.strip().replace("```json", "").replace("```", "")
            return json.loads(raw_json)
        except Exception as e:
            logger.error(f"Multi-source extraction failed: {e}")
            return {}

    def enrich_product(self, product_name: str, local_pack_size: str = None) -> Dict[str, Any]:
        """
        Orchestrates the enrichment process using Multi-Search and Verification.
        """
        logger.info(f"Enriching product (Multi-Source): {product_name} (Local Pack: {local_pack_size})")
        
        # 1. Multi-Search
        urls = self.search_product_multi(product_name)
        if not urls:
            return {"error": "Product not found"}
        
        # 2. Parallel Scraping
        import concurrent.futures
        texts = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_to_url = {executor.submit(self.scrape_page, url): url for url in urls}
            for future in concurrent.futures.as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    data = future.result()
                    if data:
                        texts.append(data)
                except Exception as exc:
                    logger.error(f"{url} generated an exception: {exc}")
        
        if not texts:
            return {"error": "Failed to scrape any pages"}
        
        # 3. Synthesis
        details = self.extract_details_multi(texts)
        details['source_url'] = urls[0] # Cite primary source
        
        # 4. Verification Layer (Same as before)
        if local_pack_size and details.get('pack_size'):
            is_match = self.verify_pack_match(details['pack_size'], local_pack_size)
            
            if not is_match:
                logger.warning(f"Pack Mismatch! Web: {details['pack_size']} vs Local: {local_pack_size}. Retrying with hint...")
                
                # Retry with Pack Size Hint (Single source is fine for retry)
                retry_query = f"{product_name} {local_pack_size}"
                retry_url = self.search_product(retry_query) # Use single search for specific retry
                
                if retry_url and retry_url not in urls:
                    retry_text = self.scrape_page(retry_url)
                    if retry_text:
                        retry_details = self.extract_details(retry_text) # Single extract
                        
                        retry_match = self.verify_pack_match(retry_details.get('pack_size'), local_pack_size)
                        if retry_match:
                            logger.info("Retry search found a better match!")
                            retry_details['source_url'] = retry_url
                            return retry_details
            
        return details
