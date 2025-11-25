from shop_manager import PharmaShop
from knowledge_graph import KnowledgeGraphSync
from datetime import date

def setup_test_data():
    shop = PharmaShop()
    kg = KnowledgeGraphSync()
    
    # 1. Add "Augmentin 625" stock (if not already there)
    # We already ingested it into KG, but maybe not stock?
    # Let's add stock for Augmentin 625
    print("Adding stock for Augmentin 625...")
    shop.add_medicine_stock("Augmentin 625", "BATCH001", "2025-12-31", 10, 10)
    
    # 2. Add a substitute: "Moxikind-CV 625"
    # It has same molecules: Amoxicillin, Clavulanic Acid
    print("Adding stock for Moxikind-CV 625...")
    shop.add_medicine_stock("Moxikind-CV 625", "BATCH002", "2026-01-31", 5, 10)
    
    # Sync Moxikind to KG
    print("Syncing Moxikind-CV 625 to KG...")
    kg.sync_product_from_sql({
        "name": "Moxikind-CV 625",
        "molecules": ["Amoxicillin", "Clavulanic Acid"]
    })
    
    # 3. Add a non-substitute: "Dolo 650" (Paracetamol)
    print("Adding stock for Dolo 650...")
    shop.add_medicine_stock("Dolo 650", "BATCH003", "2025-11-30", 20, 15)
    kg.sync_product_from_sql({
        "name": "Dolo 650",
        "molecules": ["Paracetamol"]
    })
    
    shop.close()
    kg.close()

def test_substitution():
    shop = PharmaShop()
    
    print("\n--- Testing Substitution for Augmentin 625 ---")
    substitutes = shop.get_substitutes("Augmentin 625")
    
    if substitutes:
        print(f"Found {len(substitutes)} substitutes:")
        for sub in substitutes:
            print(f"- {sub['product']} (Price: {sub['price']}, Stock: {sub['stock']})")
    else:
        print("No substitutes found.")
        
    shop.close()

if __name__ == "__main__":
    setup_test_data()
    test_substitution()
