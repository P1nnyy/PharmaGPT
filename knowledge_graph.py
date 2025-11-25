from neo4j_utils import get_db_connection

class KnowledgeGraphSync:
    def __init__(self):
        self.conn = get_db_connection()

    def setup_schema(self):
        """
        Create constraints to ensure uniqueness for Products and Molecules.
        """
        queries = [
            "CREATE CONSTRAINT product_name_unique IF NOT EXISTS FOR (p:Product) REQUIRE p.name IS UNIQUE",
            "CREATE CONSTRAINT molecule_name_unique IF NOT EXISTS FOR (m:Molecule) REQUIRE m.name IS UNIQUE"
        ]
        
        for q in queries:
            self.conn.query(q)
        print("Schema constraints set up.")

    def sync_product_from_sql(self, product_data):
        """
        Syncs a product and its molecules to the Knowledge Graph.
        
        Args:
            product_data (dict): A dictionary containing product details.
                                 Expected format:
                                 {
                                     "name": "Product Name",
                                     "molecules": [{"name": "Molecule1", "strength": "500mg"}, ...]
                                 }
        """
        product_name = product_data.get("name")
        molecules = product_data.get("molecules", [])

        if not product_name:
            print("Error: Product name is required.")
            return

        query = """
        MERGE (p:Product {name: $product_name})
        WITH p
        UNWIND $molecules as mol_data
        MERGE (m:Molecule {name: mol_data.name})
        MERGE (p)-[r:CONTAINS]->(m)
        SET r.strength = mol_data.strength
        """
        
        self.conn.query(query, {"product_name": product_name, "molecules": molecules})
        print(f"Synced product: {product_name} with molecules: {molecules}")

    def close(self):
        self.conn.close()
