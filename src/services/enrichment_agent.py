from src.services.ai_client import manager
import re
import json
import requests
import asyncio
from bs4 import BeautifulSoup
from typing import Dict, Any, Optional
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

class EnrichmentAgent:
    def __init__(self):
        # Using gemini-2.0-flash
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
                if 'results' in data:
                    items = data['results']
                elif 'suggestions' in data:
                    items = data['suggestions']
                elif 'result' in data:
                    items = data['result']
            
            if items:
                for item in items:
                    url_path = item.get('url_path', '')
                    if url_path and (url_path.startswith('/drugs/') or url_path.startswith('/otc/')):
                        full_url = f"https://www.1mg.com{url_path}"
                        logger.info(f"Found 1mg product URL: {full_url}")
                        return full_url
            
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
            for script in soup(["script", "style", "header", "footer", "nav"]):
                script.decompose()
            
            text = soup.get_text()
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)
            return text[:20000] 
        except Exception as e:
            logger.error(f"Scraping failed for {url}: {e}")
            return None

    async def extract_details(self, text: str) -> Dict[str, Any]:
        """
        Uses Gemini to parse raw text into structured JSON.
        """
        logger.info("Extracting details with Gemini...")
        prompt = """
        You are a pharmaceutical data expert. I will provide text scraped from a medicine product page.
        Extract the following details into a valid JSON object:
        - manufacturer (string): Name of the pharmaceutical company (e.g., "Sun Pharma", "Lupin").
        - salt_composition (string): The COMPLETE list of active ingredients/salts with their strengths. 
        - pack_size (string): The packaging information (e.g., "Strip of 15 tablets", "1 Vial").
        - category (string): The PHYSICAL FORM (Tablet, Capsule, Injection, etc). 

        If a field is not found, use null.
        Return raw JSON only.
        
        Input Text:
        """
        
        try:
            response = await manager.generate_content_async(
                model='gemini-2.0-flash',
                contents=[prompt + text]
            )
            raw_json = response.text.strip().replace("```json", "").replace("```", "")
            return json.loads(raw_json)
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return {}

    async def verify_pack_match(self, web_pack: str, local_pack: str) -> bool:
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
        Return ONLY JSON: {{"match": true}} or {{"match": false}}
        """
        try:
            response = await manager.generate_content_async(
                model='gemini-2.0-flash',
                contents=[prompt]
            )
            data = json.loads(response.text.strip().replace("```json", "").replace("```", ""))
            return data.get("match", False)
        except Exception as e:
            logger.error(f"Pack verification failed: {e}")
            return False

    def _clean_product_name(self, name: str) -> str:
        name = re.sub(r'\b\d+[gm]l?\b', '', name, flags=re.IGNORECASE) 
        name = re.sub(r'\b\d+x\d+\b', '', name, flags=re.IGNORECASE)   
        banned = ['SOLUTION', 'SYRUP', 'TABLET', 'CAPSULE', 'INJECTION', 'EYE', 'EAR', 'DROPS', 'SUSPENSION']
        for word in banned:
            name = re.sub(r'\b' + word + r'\b', '', name, flags=re.IGNORECASE)
        name = name.replace('-', ' ').strip()
        return " ".join(name.split())

    def search_product_multi(self, product_name: str, limit: int = 3) -> list:
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

        items = fetch_results(product_name)
        urls = []
        from difflib import SequenceMatcher

        def process_items(candidate_items, query_str):
            clean_query_for_relevance = self._clean_product_name(query_str)
            if len(clean_query_for_relevance) < 3: clean_query_for_relevance = query_str 

            found_urls = []
            for item in candidate_items:
                url_path = item.get('url_path', '')
                result_name = item.get('name', '')
                similarity = SequenceMatcher(None, query_str.lower(), result_name.lower()).ratio()
                clean_result_name = self._clean_product_name(result_name)
                q_tokens = set(clean_query_for_relevance.lower().split())
                r_tokens = set(clean_result_name.lower().split())
                overlap = len(q_tokens.intersection(r_tokens))
                
                is_relevant = False
                if similarity > 0.6: is_relevant = True 
                elif overlap >= 1: is_relevant = True
                
                norm_q = clean_query_for_relevance.lower().replace(" ", "")
                norm_r = clean_result_name.lower().replace(" ", "")
                if len(norm_q) > 3 and norm_q in norm_r: is_relevant = True
                
                if not is_relevant: continue
                if url_path and (url_path.startswith('/drugs/') or url_path.startswith('/otc/')):
                    full_url = f"https://www.1mg.com{url_path}"
                    if full_url not in found_urls: found_urls.append(full_url)
            return found_urls

        urls = process_items(items, product_name)
        
        if not urls:
            potential_queries = set()
            if 'z' in product_name.lower(): potential_queries.add(product_name.lower().replace('z', 's'))
            elif 's' in product_name.lower(): potential_queries.add(product_name.lower().replace('s', 'z'))
            if 'aa' in product_name.lower(): potential_queries.add(product_name.lower().replace('aa', 'a'))
            
            for alt_query in potential_queries:
                if alt_query == product_name.lower(): continue
                logger.info(f"Trying phonetic fallback: '{alt_query}'")
                alt_items = fetch_results(alt_query)
                alt_urls = process_items(alt_items, alt_query)
                if alt_urls:
                    urls.extend(alt_urls)
                    break 
        
        if not urls:
            clean_name = self._clean_product_name(product_name)
            if clean_name and clean_name.lower() != product_name.lower() and len(clean_name) > 2:
                logger.info(f"Primary search failed. Retrying with cleaned name: '{clean_name}'")
                fallback_items = fetch_results(clean_name)
                urls = process_items(fallback_items, clean_name)
        
        logger.info(f"Found {len(urls)} URLs for {product_name} (final)")
        return urls[:limit]

    async def extract_details_multi(self, texts: list, product_name: str = "") -> Dict[str, Any]:
        """
        Uses Gemini to synthesize details from multiple source texts.
        """
        logger.info(f"Synthesizing details from {len(texts)} sources with Gemini...")
        combined_text = ""
        for i, text in enumerate(texts):
            combined_text += f"\n--- SOURCE {i+1} ---\n{text[:10000]}\n"

        prompt = f"""
        You are a pharmaceutical data expert. I will provide text extracted from MULTIPLE different sources for the same product.
        Your job is to SYNTHESIZE the information and extract the most accurate details into a valid JSON object.
        Target Product from Invoice: "{product_name}"
        Fields: manufacturer, salt_composition, pack_size, category.
        Return ONLY valid JSON.
        """
        
        try:
            response = await manager.generate_content_async(
                model='gemini-2.0-flash',
                contents=[prompt + combined_text]
            )
            raw_json = response.text.strip().replace("```json", "").replace("```", "")
            return json.loads(raw_json)
        except Exception as e:
            logger.error(f"Multi-source extraction failed: {e}")
            return {}

    async def enrich_product(self, product_name: str, local_pack_size: str = None) -> Dict[str, Any]:
        """
        Orchestrates the enrichment process using Multi-Search and Verification.
        """
        logger.info(f"Enriching product (Multi-Source): {product_name} (Local Pack: {local_pack_size})")
        
        urls = self.search_product_multi(product_name)
        if not urls: return {"error": "Product not found"}
        
        texts = []
        for url in urls:
            data = self.scrape_page(url)
            if data: texts.append(data)
        
        if not texts: return {"error": "Failed to scrape any pages"}
        
        details = await self.extract_details_multi(texts, product_name=product_name)
        details['source_url'] = urls[0] 
        
        if local_pack_size and details.get('pack_size'):
            is_match = await self.verify_pack_match(details['pack_size'], local_pack_size)
            if not is_match:
                logger.warning(f"Pack Mismatch! Web: {details['pack_size']} vs Local: {local_pack_size}")
                retry_query = f"{product_name} {local_pack_size}"
                retry_url = self.search_product(retry_query) 
                if retry_url and retry_url not in urls:
                    retry_text = self.scrape_page(retry_url)
                    if retry_text:
                        retry_details = await self.extract_details(retry_text)
                        retry_match = await self.verify_pack_match(retry_details.get('pack_size'), local_pack_size)
                        if retry_match:
                            retry_details['source_url'] = retry_url
                            return retry_details
            
        return details
