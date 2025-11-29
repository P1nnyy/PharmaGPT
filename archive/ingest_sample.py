from knowledge_graph import KnowledgeGraphSync

def main():
    kg = KnowledgeGraphSync()
    
    # 1. Setup Schema (Constraints)
    kg.setup_schema()
    
    # 2. Define the sample product from "SQL DB"
    sample_product = {
        "name": "Augmentin 625",
        "molecules": ["Amoxicillin", "Clavulanic Acid"]
    }
    
    # 3. Sync to Graph
    print("Ingesting sample product...")
    kg.sync_product_from_sql(sample_product)
    
    print("Ingestion complete.")
    kg.close()

if __name__ == "__main__":
    main()
