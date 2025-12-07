import sys
import os
import unittest
from neo4j import GraphDatabase
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.schemas import InvoiceExtraction, RawLineItem
from src.persistence import ingest_invoice
from src.normalization import normalize_line_item

# Neo4j Config
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

class TestLiveIntegration(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        try:
            cls.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
            # Verify connection
            cls.driver.verify_connectivity()
            print("Connected to Neo4j.")
        except Exception as e:
            print(f"Failed to connect to Neo4j: {e}")
            cls.driver = None

    @classmethod
    def tearDownClass(cls):
        if cls.driver:
            cls.driver.close()

    def setUp(self):
        if not self.driver:
            self.skipTest("No Neo4j connection")
        # Clean up test data
        self._clean_test_data()

    def tearDown(self):
        if self.driver:
            self._clean_test_data()

    def _clean_test_data(self):
        with self.driver.session() as session:
            session.run("MATCH (i:Invoice {invoice_number: 'LIVE-TEST-001'}) DETACH DELETE i")
            session.run("MATCH (p:Product {name: 'Live Test Product'}) DETACH DELETE p")

    def test_full_ingestion_flow(self):
        """
        Tests the full flow: Raw -> Normalization -> Ingestion -> Neo4j Verification
        """
        # 1. Create Raw Data
        raw_item = RawLineItem(
            Original_Product_Description="Live Test Product", # Will map to itself + Unit if not in mapping, or we can use mapping
            Raw_Quantity="10",
            Batch_No="L1",
            Raw_Rate_Column_1="100.00",
            Raw_Discount_Percentage="0",
            Raw_GST_Percentage="5",
            Stated_Net_Amount="1050.00"
        )
        invoice_data = InvoiceExtraction(
            Supplier_Name="Live Test Supplier",
            Invoice_No="LIVE-TEST-001",
            Invoice_Date="2024-12-07",
            Line_Items=[raw_item]
        )
        
        # 2. Normalize
        # We manually inject a mapping for this test or rely on fallback
        # Let's rely on fallback: "Live Test Product" -> "Live Test Product", "Unit"
        normalized_item = normalize_line_item(raw_item, "Live Test Supplier")
        
        # 3. Ingest
        ingest_invoice(self.driver, invoice_data, [normalized_item])
        
        # 4. Verify in Neo4j
        with self.driver.session() as session:
            # Check Invoice
            result = session.run("""
                MATCH (i:Invoice {invoice_number: 'LIVE-TEST-001'})
                RETURN i.grand_total as total, i.supplier_name as supplier
            """).single()
            
            self.assertIsNotNone(result)
            self.assertEqual(result["supplier"], "Live Test Supplier")
            self.assertEqual(result["total"], 1050.0)
            
            # Check Product
            result = session.run("""
                MATCH (p:Product {name: 'Live Test Product'})
                RETURN p
            """).single()
            self.assertIsNotNone(result)
            
            # Check Line Item & Relationships
            result = session.run("""
                MATCH (i:Invoice {invoice_number: 'LIVE-TEST-001'})
                MATCH (i)-[:CONTAINS]->(l:Line_Item)
                MATCH (l)-[:REFERENCES]->(p:Product {name: 'Live Test Product'})
                RETURN l.net_amount as net_amount, l.quantity as quantity
            """).single()
            
            self.assertIsNotNone(result)
            self.assertEqual(result["net_amount"], 1050.0)
            self.assertEqual(result["quantity"], 10.0)

if __name__ == '__main__':
    unittest.main()
