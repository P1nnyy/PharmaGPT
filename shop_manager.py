from neo4j import GraphDatabase
import os
from dotenv import load_dotenv
from datetime import datetime
import uuid

# Load environment variables
load_dotenv()

class PharmaShop:
    def __init__(self):
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD")
        
        if not password:
            # Fallback or error if password is missing. 
            # The user might have put it in .env manually or we might need to ask.
            # For now, we raise an error to prompt the user if it fails.
            pass 
            
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def check_inventory(self):
        """
        Query the graph to list all products, their batch numbers, current stock, 
        and expiry dates. Sort by expiry (soonest first).
        Returns a list of dictionaries.
        """
        query = """
        MATCH (p:Product)<-[:IS_BATCH_OF]-(b:InventoryBatch)
        RETURN p.name as product_name, b.batch_number as batch_number, 
               b.current_stock as current_stock, b.expiry_date as expiry_date
        ORDER BY b.expiry_date ASC
        """
        data = []
        with self.driver.session() as session:
            result = session.run(query)
            for record in result:
                # Convert neo4j Date to python date or string
                expiry = record['expiry_date']
                if hasattr(expiry, 'to_native'):
                    expiry = expiry.to_native()
                
                data.append({
                    "Product": record['product_name'],
                    "Batch": record['batch_number'],
                    "Stock": record['current_stock'],
                    "Expiry": expiry
                })
        return data

    def get_product_names(self):
        """
        Fetch all unique product names.
        """
        query = "MATCH (p:Product) RETURN DISTINCT p.name as name ORDER BY name"
        with self.driver.session() as session:
            return [record["name"] for record in session.run(query)]

    def calculate_taxes(self):
        """
        Calculate the total tax liability by summing the tax_amount property 
        on all SOLD relationships between Bill and InventoryBatch nodes.
        """
        query = """
        MATCH (:Bill)-[r:SOLD]->(:InventoryBatch)
        RETURN sum(r.tax_amount) as total_tax
        """
        with self.driver.session() as session:
            result = session.run(query)
            record = result.single()
            total_tax = record["total_tax"] if record and record["total_tax"] is not None else 0.0
            return total_tax

    def sell_item(self, product_name, qty):
        """
        Sell item using FIFO logic.
        Returns the total tax amount for the transaction, or None if failed.
        """
        # 1. Find batches for the product, ordered by expiry (FIFO)
        # Schema: (InventoryBatch)-[:IS_BATCH_OF]->(Product)
        # Price is 'mrp' on Batch, Tax Rate is 'tax_rate' on Product.
        
        check_stock_query = """
        MATCH (p:Product {name: $product_name})<-[:IS_BATCH_OF]-(b:InventoryBatch)
        WHERE b.current_stock > 0
        RETURN b.batch_number as batch, b.current_stock as stock, b.expiry_date as expiry, 
               b.mrp as price, p.tax_rate as tax_rate
        ORDER BY b.expiry_date ASC
        """
        
        total_transaction_tax = 0.0
        
        with self.driver.session() as session:
            batches = list(session.run(check_stock_query, product_name=product_name))
            
            if not batches:
                print(f"No stock found for {product_name}")
                return None

            total_stock = sum(b['stock'] for b in batches)
            if total_stock < qty:
                print(f"Insufficient stock for {product_name}. Requested: {qty}, Available: {total_stock}")
                return None

            remaining_qty = qty
            
            # Create a single Bill node for this transaction
            bill_id = str(uuid.uuid4())
            create_bill_query = """
            CREATE (bill:Bill {id: $bill_id, date: datetime(), product: $product_name, total_qty: $qty})
            RETURN elementId(bill) as id
            """
            session.run(create_bill_query, bill_id=bill_id, product_name=product_name, qty=qty)
            
            for batch in batches:
                if remaining_qty <= 0:
                    break
                
                batch_no = batch['batch']
                current_stock = batch['stock']
                price = batch['price']
                tax_rate = batch['tax_rate']
                
                if price is None or tax_rate is None:
                    print(f"Error: Price or Tax Rate missing for batch {batch_no} of {product_name}. Skipping.")
                    continue

                take_qty = min(remaining_qty, current_stock)
                
                # Tax Amount = (Price * TaxRate) * Quantity Sold
                tax_amount = (price * tax_rate) * take_qty
                total_transaction_tax += tax_amount
                
                sell_query = """
                MATCH (b:InventoryBatch {batch_number: $batch_number})
                MATCH (bill:Bill {id: $bill_id})
                CREATE (bill)-[:SOLD {tax_amount: $tax_amount, qty: $qty_sold}]->(b)
                SET b.current_stock = b.current_stock - $qty_sold
                """
                
                session.run(sell_query, batch_number=batch_no, bill_id=bill_id, 
                            tax_amount=tax_amount, qty_sold=take_qty)
                
                remaining_qty -= take_qty
                print(f"Sold {take_qty} from Batch {batch_no}. Tax: {tax_amount}")
                
        return total_transaction_tax

if __name__ == "__main__":
    try:
        shop = PharmaShop()
        
        print("--- Initial Inventory ---")
        inventory = shop.check_inventory()
        print(f"{'Product':<20} | {'Batch':<10} | {'Stock':<5} | {'Expiry':<12}")
        print("-" * 55)
        for item in inventory:
            print(f"{item['Product']:<20} | {item['Batch']:<10} | "
                  f"{item['Stock']:<5} | {str(item['Expiry']):<12}")
        print("-" * 55)
        
        print("\n--- Selling 2 units of Dolo 650 ---")
        tax = shop.sell_item("Dolo 650", 2)
        if tax is not None:
             print(f"Transaction completed. Total Tax: {tax}")
        
        print("\n--- Updated Inventory ---")
        inventory = shop.check_inventory()
        for item in inventory:
            print(f"{item['Product']:<20} | {item['Batch']:<10} | {item['Stock']:<5}")
        
        print("\n--- Tax Liability ---")
        tax = shop.calculate_taxes()
        print(f"Total Tax Liability: {tax}")
        
        shop.close()
    except Exception as e:
        print(f"An error occurred: {e}")
