import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv

# Load env before imports that might rely on it
load_dotenv()

from src.services.enrichment_agent import EnrichmentAgent

def test_enrichment():
    agent = EnrichmentAgent()
    product_name = "PANTOP 40"
    print(f"Testing enrichment for: {product_name}")
    
    result = agent.enrich_product(product_name)
    print("\nEnrichment Result:")
    print(result)

if __name__ == "__main__":
    test_enrichment()
