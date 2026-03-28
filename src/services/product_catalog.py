
import yaml
import os
from difflib import SequenceMatcher
from typing import Dict, Any, Optional, List
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

class ProductCatalog:
    _instance = None
    _catalog = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ProductCatalog, cls).__new__(cls)
            cls._instance._load_catalog()
        return cls._instance

    def _load_catalog(self):
        catalog_path = os.path.join(os.getcwd(), "config", "product_catalog.yaml")
        if not os.path.exists(catalog_path):
            logger.warning(f"Product catalog not found at {catalog_path}")
            self._catalog = {"products": []}
            return

        try:
            with open(catalog_path, "r") as f:
                self._catalog = yaml.safe_load(f) or {"products": []}
                logger.info(f"Loaded {len(self._catalog.get('products', []))} products from catalog.")
        except Exception as e:
            logger.error(f"Failed to load product catalog: {e}")
            self._catalog = {"products": []}

    def _get_similarity(self, a: str, b: str) -> float:
        return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()

    def find_match(self, product_name: str, threshold: float = 0.8) -> Optional[Dict[str, Any]]:
        """
        Fuzzy matches the product name against known_name and synonyms.
        Returns the first match that exceeds the threshold.
        """
        if not product_name or product_name.lower() == "unknown product":
            return None

        products = self._catalog.get("products", [])
        
        # 1. Exact match first
        for p in products:
            known_name = p.get("known_name", "")
            if known_name.lower() == product_name.lower():
                logger.info(f"Exact match found in catalog: {known_name}")
                return p
            
            for syn in p.get("synonyms", []):
                if syn.lower() == product_name.lower():
                    logger.info(f"Exact synonym match found in catalog: {syn} -> {known_name}")
                    return p

        # 2. Fuzzy match
        best_match = None
        highest_score = 0.0

        for p in products:
            known_name = p.get("known_name", "")
            score = self._get_similarity(product_name, known_name)
            
            # Check synonyms too
            for syn in p.get("synonyms", []):
                syn_score = self._get_similarity(product_name, syn)
                if syn_score > score:
                    score = syn_score

            if score > highest_score and score >= threshold:
                highest_score = score
                best_match = p

        if best_match:
            logger.info(f"Fuzzy match found in catalog: {product_name} -> {best_match.get('known_name')} (Score: {highest_score:.2f})")
            return best_match

        return None
