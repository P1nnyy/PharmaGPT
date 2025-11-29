from neo4j import GraphDatabase
import os
from dotenv import load_dotenv
from datetime import datetime
import uuid

# Load environment variables
load_dotenv()

class PharmaShop:
    # --- v2 Features (CRM) - Deprecated for v1 "Glass" Pivot ---
    def create_customer(self, name, phone, max_limit=2000.0):
        """
        [DEPRECATED] Create a new customer with a credit limit.
        Moved to v2_features.
        """
        pass

    def get_customer(self, phone):
        """
        [DEPRECATED] Get customer details by phone.
        Moved to v2_features.
        """
        pass


    def __init__(self):
        from neo4j_utils import get_db_connection
        self.conn = get_db_connection()
        self.driver = self.conn.get_driver()

    def close(self):
        # Driver is managed by singleton, but we can close it if we want to force it.
        # Generally, we leave it open for the application lifetime.
        pass

    def find_product_fuzzy(self, search_term: str) -> list[str]:
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
    def get_readable_stock(sealed: int, loose: int) -> str:
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
        Query the graph to list all products with Sealed/Open tracking and full details.
        """
        query = """
        MATCH (p:Product)<-[:IS_BATCH_OF]-(b:InventoryBatch)
        OPTIONAL MATCH (p)-[:MANUFACTURED_BY]->(m:Manufacturer)
        OPTIONAL MATCH (p)-[:HAS_FORM]->(d:DosageForm)
        RETURN p.name as product_name, 
               b.batch_number as batch_number, 
               coalesce(b.sealed_packs, 0) as sealed,
               coalesce(b.loose_tablets, 0) as loose,
               b.expiry_date as expiry_date,
               coalesce(p.pack_size, 1) as pack_size,
               b.mrp as mrp,
               coalesce(p.tax_rate, 0.0) as tax_rate,
               m.name as manufacturer,
               d.name as dosage_form
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
                
                readable_stock = self.get_readable_stock(sealed, loose)
                total_atoms = (sealed * pack_size) + loose
                
                data.append({
                    "product_name": record['product_name'],
                    "dosage_form": record['dosage_form'] or "N/A",
                    "manufacturer": record['manufacturer'] or "N/A",
                    "batch_number": record['batch_number'],
                    "stock_display": readable_stock,
                    "quantity_packs": sealed,
                    "quantity_loose": loose,
                    "total_atoms": total_atoms,
                    "expiry_date": expiry,
                    "mrp": record['mrp'] if record['mrp'] is not None else 0.0,
                    "tax_rate": (record['tax_rate'] or 0.0) * 100,
                    "pack_size": pack_size
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

    def _normalize_string(self, s):
        return " ".join(s.lower().split()) if s else ""

    def _find_best_match(self, name, candidates, cutoff=0.85):
        import difflib
        norm_name = self._normalize_string(name)
        best_match = None
        best_ratio = 0.0
        
        for candidate in candidates:
            norm_cand = self._normalize_string(candidate)
            ratio = difflib.SequenceMatcher(None, norm_name, norm_cand).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = candidate
        
        return best_match if best_ratio >= cutoff else None

    def add_medicine_stock(self, product_name, batch_id, expiry_date, qty_packs, pack_size=10, 
                       mrp=10.0, buy_price=5.0, tax_rate=0.1, manufacturer_name="Generic Pharma Co.", dosage_form="Tablet"):
        """
        Add new stock. Stores as SEALED packs initially.
        Uses Smart Entity Resolution to merge with existing products.
        """
        # 1. Smart Entity Resolution
        existing_products = self.get_product_names()
        match = self._find_best_match(product_name, existing_products)
        
        final_product_name = match if match else product_name
        
        if match:
            print(f"🧩 Smart Merge: Mapped '{product_name}' -> Existing '{match}'")

        query = """
        // 1. Product (set properties and link to Manufacturer/DosageForm)
        MERGE (p:Product {name: $product_name})
        ON CREATE SET 
            p.created_at = datetime(), 
            p.pack_size = $pack_size,
            p.tax_rate = $tax_rate
        ON MATCH SET 
            p.pack_size = $pack_size,
            p.tax_rate = $tax_rate

        // 2. Manufacturer
        MERGE (m:Manufacturer {name: $manufacturer_name})
        MERGE (p)-[:MANUFACTURED_BY]->(m)

        // 3. Dosage Form
        MERGE (d:DosageForm {name: $dosage_form})
        MERGE (p)-[:HAS_FORM]->(d)

        // 4. Batch (set MRP and Buy Price dynamically)
        MERGE (b:InventoryBatch {batch_number: $batch_id})
        ON CREATE SET 
            b.expiry_date = date($expiry_date),
            b.sealed_packs = $qty_packs,
            b.loose_tablets = 0,
            b.mrp = $mrp,
            b.buy_price = $buy_price
        ON MATCH SET
            b.sealed_packs = coalesce(b.sealed_packs, 0) + $qty_packs
        
        MERGE (b)-[:IS_BATCH_OF]->(p)
        """
        
        with self.driver.session() as session:
            session.run(query, product_name=final_product_name, batch_id=batch_id, 
                        expiry_date=expiry_date, qty_packs=qty_packs, pack_size=pack_size,
                        mrp=mrp, buy_price=buy_price, tax_rate=tax_rate, manufacturer_name=manufacturer_name,
                        dosage_form=dosage_form)
            
        return f"✅ Added {qty_packs} Sealed Packs of {final_product_name} (Batch: {batch_id})"

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
               coalesce(p.tax_rate, 0.0) as tax_rate,
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
                
                // Explicit Locking to prevent Race Conditions
                SET c._lock = 1 REMOVE c._lock
                
                WITH c
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


    def delete_batch(self, batch_number):
        """
        Delete a batch from inventory.
        """
        query = """
        MATCH (b:InventoryBatch {batch_number: $batch_number})
        DETACH DELETE b
        """
        with self.driver.session() as session:
            session.run(query, batch_number=batch_number)
        return True

    def update_batch(self, batch_number, new_expiry, new_sealed, new_loose):
        """
        Update batch details.
        """
        query = """
        MATCH (b:InventoryBatch {batch_number: $batch_number})
        SET b.expiry_date = date($new_expiry),
            b.sealed_packs = $new_sealed,
            b.loose_tablets = $new_loose
        """
        with self.driver.session() as session:
            session.run(query, batch_number=batch_number, new_expiry=new_expiry, 
                        new_sealed=new_sealed, new_loose=new_loose)
        return True

    def get_inventory_logs(self):
        """
        Fetch a log of all items ever purchased (added to inventory).
        """
        query = """
        MATCH (b:InventoryBatch)-[:IS_BATCH_OF]->(p:Product)
        OPTIONAL MATCH (p)-[:MANUFACTURED_BY]->(m:Manufacturer)
        OPTIONAL MATCH (p)-[:HAS_FORM]->(d:DosageForm)
        RETURN p.name as product_name,
               b.batch_number as batch_number,
               b.expiry_date as expiry_date,
               b.mrp as mrp,
               coalesce(p.tax_rate, 0.0) as tax_rate,
               m.name as manufacturer,
               d.name as dosage_form,
               b.sealed_packs as initial_sealed,
               b.loose_tablets as initial_loose,
               p.created_at as date_added
        ORDER BY b.expiry_date DESC
        """
        data = []
        with self.driver.session() as session:
            result = session.run(query)
            for record in result:
                expiry = record['expiry_date']
                if hasattr(expiry, 'to_native'):
                    expiry = expiry.to_native()
                
                date_added = record['date_added']
                if hasattr(date_added, 'to_native'):
                    date_added = date_added.to_native()

                data.append({
                    "Date Added": date_added,
                    "Product": record['product_name'],
                    "Batch": record['batch_number'],
                    "Form": record['dosage_form'] or "N/A",
                    "Manufacturer": record['manufacturer'] or "N/A",
                    "MRP": record['mrp'] if record['mrp'] is not None else 0.0,
                    "Tax (%)": (record['tax_rate'] or 0.0) * 100,
                    "Initial Sealed": record['initial_sealed'],
                    "Initial Loose": record['initial_loose'],
                    "Expiry": expiry
                })
        return data


