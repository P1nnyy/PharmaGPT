from shop_manager import PharmaShop
import uuid

def test_khata():
    shop = PharmaShop()
    
    # 1. Create Customer
    print("Creating Customer 'Rahul'...")
    phone = f"98765{str(uuid.uuid4())[:5]}" # Randomize phone to avoid unique constraint issues if re-run
    customer_id = shop.create_customer("Rahul", phone, max_limit=100.0)
    print(f"Customer Created: {customer_id}, Phone: {phone}, Limit: 100.0")
    
    # 2. Add Stock (Expensive Item)
    print("Adding Stock...")
    shop.add_medicine_stock("ExpensiveMeds", "BATCH999", "2025-12-31", 10, 1) # 10 packs, size 1
    # Note: MRP defaults to 10.0 in add_medicine_stock, Tax Rate defaults? 
    # Wait, add_medicine_stock sets MRP=10.0. 
    # Tax rate is on Product node. If not set, it might be null.
    # Let's ensure tax rate is set or handle it. 
    # In add_medicine_stock: MERGE (p:Product)... ON CREATE SET ...
    # It doesn't set tax_rate. It might be null.
    # sell_item handles null tax_rate? 
    # "tax_amount = (unit_price * tax_rate) * take_from_batch" -> if tax_rate is None, this fails.
    # I should fix add_medicine_stock or update the product manually.
    
    # Let's update the product tax rate to be safe
    with shop.driver.session() as session:
        session.run("MERGE (p:Product {name: 'ExpensiveMeds'}) SET p.tax_rate = 0.1")

    # 3. Attempt Credit Sale (Within Limit)
    # Price = 10.0, Tax = 1.0 -> Total 11.0 per unit.
    # Buy 5 units -> 55.0. Should succeed.
    print("\n--- Attempting Credit Sale (5 units) ---")
    try:
        result = shop.sell_item("ExpensiveMeds", 5, payment_method="CREDIT", customer_phone=phone)
        print("Sale Successful!")
        print(f"Total Amount: {result['total_amount']}")
    except Exception as e:
        print(f"Sale Failed: {e}")

    # 4. Check Balance
    cust = shop.get_customer(phone)
    print(f"Customer Balance: {cust['balance']}")

    # 5. Attempt Credit Sale (Exceed Limit)
    # Current Balance ~55. Limit 100. Remaining ~45.
    # Buy 5 units -> 55.0. Should fail.
    print("\n--- Attempting Credit Sale (5 units) - Should Fail ---")
    try:
        result = shop.sell_item("ExpensiveMeds", 5, payment_method="CREDIT", customer_phone=phone)
        print("Sale Successful (Unexpected)!")
    except Exception as e:
        print(f"Sale Failed (Expected): {e}")

    shop.close()

if __name__ == "__main__":
    test_khata()
