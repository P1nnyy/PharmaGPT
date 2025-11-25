from neo4j import GraphDatabase
import os
from dotenv import load_dotenv
from datetime import datetime
import uuid

# Load environment variables
load_dotenv()

class PharmaShop:
    def create_customer(self, name, phone, max_limit=2000.0):
        """
        Create a new customer with a credit limit.
        """
        customer_id = str(uuid.uuid4())
        query = """
        MERGE (c:Customer {phone: $phone})
        ON CREATE SET 
            c.id = $id,
            c.name = $name,
            c.current_credit_balance = 0.0,
            c.max_credit_limit = $max_limit,
            c.created_at = datetime()
        RETURN c.id as id
        """
        with self.driver.session() as session:
            result = session.run(query, id=customer_id, name=name, phone=phone, max_limit=max_limit)
            record = result.single()
            return record["id"] if record else None

    def get_customer(self, phone):
        """
        Get customer details by phone.
        """
        query = """
        MATCH (c:Customer {phone: $phone})
        RETURN c.id as id, c.name as name, c.current_credit_balance as balance, c.max_credit_limit as limit
        """
        with self.driver.session() as session:
            result = session.run(query, phone=phone)
            record = result.single()
            return dict(record) if record else None

    def find_product_fuzzy(self, search_term):
        query = """
        CALL db.index.fulltext.queryNodes("productNames", $term + "~") YIELD node, score
        RETURN node.name as name, score
        ORDER BY score DESC LIMIT 1
        """
        # ... execute and return the closest match name ...
    def __init__(self):
        from neo4j_utils import get_db_connection
        self.conn = get_db_connection()
        self.driver = self.conn.get_driver()

    def close(self):
        # Driver is managed by singleton, but we can close it if we want to force it.
        # Generally, we leave it open for the application lifetime.
        pass

    def find_product_fuzzy(self, search_term):
        """
        Find products using fuzzy search on the fulltext index.
        Returns a list of matching product names.
        """
        query = """
        CALL db.index.fulltext.queryNodes("productNames", $term + "~") YIELD node, score
        RETURN node.name as name, score
        ORDER BY score DESC LIMIT 5
        """
        with self.driver.session() as session:
            result = session.run(query, term=search_term)
            return [record["name"] for record in result]

    @staticmethod
    def get_readable_stock(sealed, loose):
        """
        Convert sealed/loose count to human-readable format.
        """
        parts = []
        if sealed > 0:
            parts.append(f"{sealed} Sealed Packs")
        if loose > 0:
            parts.append(f"{loose} Loose Units")
        
        return ", ".join(parts) if parts else "Out of Stock"

    def check_inventory(self):
        """
        Query the graph to list all products with Sealed/Open tracking.
        """
        query = """
        MATCH (p:Product)<-[:IS_BATCH_OF]-(b:InventoryBatch)
        RETURN p.name as product_name, 
               b.batch_number as batch_number, 
               coalesce(b.sealed_packs, 0) as sealed,
               coalesce(b.loose_tablets, 0) as loose,
               b.expiry_date as expiry_date,
               coalesce(p.pack_size, 1) as pack_size
        ORDER BY b.expiry_date ASC
        """
        data = []
        with self.driver.session() as session:
            result = session.run(query)
            for record in result:
                expiry = record['expiry_date']
                if hasattr(expiry, 'to_native'):
                    expiry = expiry.to_native()
                
                sealed = record['sealed']
                loose = record['loose']
                pack_size = record['pack_size']
                
                # Fallback for old data that might still have 'current_stock'
                # We can't easily access 'current_stock' if we didn't query it, 
                # but for this refactor we assume new schema or migration.
                # To be safe, let's assume 0 if null.
                
                readable_stock = self.get_readable_stock(sealed, loose)
                total_atoms = (sealed * pack_size) + loose
                
                data.append({
                    "Product": record['product_name'],
                    "Batch": record['batch_number'],
                    "Stock": readable_stock,
                    "Stock_Raw": total_atoms,
                    "Expiry": expiry
                })
        return data

    def open_pack(self, batch_number, pack_size):
        """
        Moves 1 pack from Sealed to Loose.
        """
        query = """
        MATCH (b:InventoryBatch {batch_number: $batch_number})
        WHERE b.sealed_packs > 0
        SET b.sealed_packs = b.sealed_packs - 1,
            b.loose_tablets = coalesce(b.loose_tablets, 0) + $pack_size
        RETURN b.sealed_packs as sealed, b.loose_tablets as loose
        """
        with self.driver.session() as session:
            result = session.run(query, batch_number=batch_number, pack_size=pack_size)
            record = result.single()
            if record:
                print(f"Opened pack for batch {batch_number}. New state: {record['sealed']} Sealed, {record['loose']} Loose")
                return True
            return False

    def add_medicine_stock(self, product_name, batch_id, expiry_date, qty_packs, pack_size=10):
        """
        Add new stock. Stores as SEALED packs initially.
        """
        query = """
        MERGE (p:Product {name: $product_name})
        ON CREATE SET p.created_at = datetime(), p.pack_size = $pack_size
        ON MATCH SET p.pack_size = $pack_size
        
        MERGE (b:InventoryBatch {batch_number: $batch_id})
        ON CREATE SET 
            b.expiry_date = date($expiry_date),
            b.sealed_packs = $qty_packs,
            b.loose_tablets = 0,
            b.mrp = 10.0,
            b.buy_price = 5.0
        ON MATCH SET
            b.sealed_packs = coalesce(b.sealed_packs, 0) + $qty_packs
        
        MERGE (b)-[:IS_BATCH_OF]->(p)
        """
        
        with self.driver.session() as session:
            session.run(query, product_name=product_name, batch_id=batch_id, 
                        expiry_date=expiry_date, qty_packs=qty_packs, pack_size=pack_size)
            
        return f"✅ Added {qty_packs} Sealed Packs of {product_name} (Batch: {batch_id})"

    def sell_item(self, product_name, qty, payment_method="CASH", customer_phone=None):
        """
        Sell item using FIFO logic with Sealed/Open state machine.
        Supports Payment Methods: CASH, CREDIT.
        Optimized to reduce DB roundtrips and ensure Atomic Credit Validation.
        """
        if payment_method == "CREDIT" and not customer_phone:
            raise ValueError("Customer phone number is required for Credit payments.")

        # 1. Check Stock
        check_stock_query = """
        MATCH (p:Product {name: $product_name})<-[:IS_BATCH_OF]-(b:InventoryBatch)
        WHERE (coalesce(b.sealed_packs, 0) * coalesce(p.pack_size, 1)) + coalesce(b.loose_tablets, 0) > 0
        RETURN b.batch_number as batch, 
               coalesce(b.sealed_packs, 0) as sealed, 
               coalesce(b.loose_tablets, 0) as loose,
               b.expiry_date as expiry, 
               b.mrp as price, 
               p.tax_rate as tax_rate,
               coalesce(p.pack_size, 1) as pack_size
        ORDER BY b.expiry_date ASC
        """
        
        with self.driver.session() as session:
            batches = list(session.run(check_stock_query, product_name=product_name))
            
            if not batches:
                raise ValueError(f"Product '{product_name}' not found or out of stock.")

            total_available = sum((b['sealed'] * b['pack_size']) + b['loose'] for b in batches)
            if total_available < qty:
                raise ValueError(f"Insufficient stock for {product_name}. Requested: {qty}, Available: {total_available}")

            # --- CALCULATE SPLITS & COST ---
            temp_qty = qty
            calculated_total_cost = 0.0
            total_transaction_tax = 0.0
            batch_updates = []
            sold_details = []
            
            for batch in batches:
                if temp_qty <= 0: break
                
                batch_no = batch['batch']
                sealed = batch['sealed']
                loose = batch['loose']
                pack_size = batch['pack_size']
                mrp_per_pack = batch['price']
                tax_rate = batch['tax_rate']
                
                unit_price = mrp_per_pack / pack_size if pack_size > 0 else mrp_per_pack
                
                batch_total_atoms = (sealed * pack_size) + loose
                take_from_batch = min(temp_qty, batch_total_atoms)
                
                # Calculate how many packs we need to open
                needed_from_sealed = max(0, take_from_batch - loose)
                packs_to_open = (needed_from_sealed + pack_size - 1) // pack_size if pack_size > 0 else 0
                
                # Calculate Tax & Cost
                batch_cost = (unit_price * take_from_batch)
                batch_tax = (unit_price * tax_rate) * take_from_batch
                
                calculated_total_cost += (batch_cost + batch_tax)
                total_transaction_tax += batch_tax
                
                # New Inventory State
                new_sealed = sealed - packs_to_open
                new_loose = loose + (packs_to_open * pack_size) - take_from_batch
                
                batch_updates.append({
                    "batch_number": batch_no,
                    "tax_amount": batch_tax,
                    "qty_sold": take_from_batch,
                    "new_sealed": new_sealed,
                    "new_loose": new_loose
                })
                
                sold_details.append(f"{take_from_batch} units from {batch_no}")
                temp_qty -= take_from_batch
            
            # --- PREPARE TRANSACTION ---
            bill_id = str(uuid.uuid4())
            tx_id = str(uuid.uuid4())
            customer_id = None
            
            if payment_method == "CREDIT":
                # Fetch customer ID first (needed for the query)
                customer = self.get_customer(customer_phone)
                if not customer:
                    raise ValueError(f"Customer with phone {customer_phone} not found.")
                customer_id = customer['id']
                
                # ATOMIC QUERY: Check Balance -> Update Balance -> Create Bill -> Update Inventory
                query = """
                MATCH (c:Customer {id: $customer_id})
                WHERE c.current_credit_balance + $total_amount <= c.max_credit_limit
                
                // Update Customer
                SET c.current_credit_balance = c.current_credit_balance + $total_amount
                
                // Create Transaction Record
                CREATE (tx:CreditTransaction {
                    id: $tx_id,
                    amount: $total_amount,
                    type: 'DEBIT',
                    timestamp: datetime()
                })
                CREATE (c)-[:HAS_TRANSACTION]->(tx)
                
                // Create Bill
                CREATE (bill:Bill {id: $bill_id, date: datetime(), product: $product_name, total_qty: $qty, total_amount: $total_amount, payment_method: $method})
                CREATE (bill)-[:BILLED_TO]->(c)
                
                // Update Inventory
                WITH bill
                UNWIND $batch_updates as update
                MATCH (b:InventoryBatch {batch_number: update.batch_number})
                CREATE (bill)-[:SOLD {tax_amount: update.tax_amount, qty: update.qty_sold}]->(b)
                SET b.sealed_packs = update.new_sealed,
                    b.loose_tablets = update.new_loose
                
                RETURN elementId(bill) as id
                """
                
                result = session.run(query, customer_id=customer_id, total_amount=calculated_total_cost,
                                     tx_id=tx_id, bill_id=bill_id, product_name=product_name, qty=qty,
                                     method=payment_method, batch_updates=batch_updates)
                
                record = result.single()
                if not record:
                    # The query returned nothing, meaning the WHERE clause failed (Credit Limit Exceeded)
                    # Fetch current balance to show in error
                    curr = self.get_customer(customer_phone)
                    raise ValueError(f"Credit Limit Exceeded. Current Balance: {curr['balance']:.2f}, Limit: {curr['limit']:.2f}, Attempted Bill: {calculated_total_cost:.2f}")

            else:
                # CASH Transaction (No Customer Check)
                query = """
                CREATE (bill:Bill {id: $bill_id, date: datetime(), product: $product_name, total_qty: $qty, total_amount: $total_amount, payment_method: $method})
                
                WITH bill
                UNWIND $batch_updates as update
                MATCH (b:InventoryBatch {batch_number: update.batch_number})
                CREATE (bill)-[:SOLD {tax_amount: update.tax_amount, qty: update.qty_sold}]->(b)
                SET b.sealed_packs = update.new_sealed,
                    b.loose_tablets = update.new_loose
                
                RETURN elementId(bill) as id
                """
                session.run(query, bill_id=bill_id, product_name=product_name, qty=qty, 
                            total_amount=calculated_total_cost, method=payment_method, 
                            batch_updates=batch_updates)
                
        return {
            "status": "success",
            "product": product_name,
            "qty": qty,
            "tax": total_transaction_tax,
            "total_amount": calculated_total_cost,
            "details": ", ".join(sold_details)
        }

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

    def get_substitutes(self, product_name):
        """
        Find substitutes for a given product.
        Criteria:
        1. Share the same molecule(s) AND Strength.
        2. In stock (atomic_quantity > 0).
        3. Sorted by Price (Low to High).
        """
        query = """
        MATCH (p:Product {name: $product_name})-[r1:CONTAINS]->(m:Molecule)
        WITH p, collect({node: m, strength: r1.strength}) as source_components
        
        MATCH (other:Product)-[r2:CONTAINS]->(m:Molecule)
        WHERE other.name <> p.name
        
        WITH p, source_components, other, collect({node: m, strength: r2.strength}) as other_components
        
        // Check if there is any overlap in (Molecule, Strength)
        WHERE any(sc IN source_components WHERE any(oc IN other_components WHERE sc.node = oc.node AND sc.strength = oc.strength))
        
        // Ensure we only look at products with stock
        MATCH (other)<-[:IS_BATCH_OF]-(b:InventoryBatch)
        WITH other, b
        
        // Calculate total stock and find best price
        WITH other, 
             sum((coalesce(b.sealed_packs, 0) * coalesce(other.pack_size, 1)) + coalesce(b.loose_tablets, 0)) as total_stock,
             min(b.mrp) as min_price
             
        WHERE total_stock > 0
        RETURN other.name as product, min_price as price, total_stock as stock
        ORDER BY price ASC
        """
        
        with self.driver.session() as session:
            result = session.run(query, product_name=product_name)
            substitutes = [
                {"product": record["product"], "price": record["price"], "stock": record["stock"]}
                for record in result
            ]
            
        return substitutes


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
