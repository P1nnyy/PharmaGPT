# Implementation Plan - ShopManager Backend for Neo4j

This plan outlines the steps to build the `ShopManager` backend using Python and Neo4j for pharmacy inventory management.

## User Requirements
- **Database**: Neo4j (bolt://localhost:7687)
- **Entities**: Product, InventoryBatch, Supplier, Bill
- **Core Functions**:
    - `check_inventory()`: List products, batches, stock, expiry (sorted by soonest).
    - `calculate_taxes()`: Sum `tax_amount` on `SOLD` relationships.
    - `sell_item(product_name, qty)`: FIFO logic, update stock, create Bill & SOLD relationship with tax.
- **Verification**: Show inventory, sell "Dolo 650" (2 units), verify stock drop, show tax liability.

## Proposed Files
1.  `.env`: Store database credentials (URI, User, Password).
2.  `shop_manager.py`: Main Python script containing the `PharmaShop` class and execution logic.

## Step-by-Step Plan

### Step 1: Setup
- [ ] Create/Verify virtual environment.
- [ ] Install `neo4j` Python driver.
- [ ] Create `.env` file (User to provide password).

### Step 2: Develop Application (`shop_manager.py`)
- [ ] Define `PharmaShop` class.
- [ ] Implement `__init__` to connect to Neo4j using `.env` credentials.
- [ ] Implement `close` to close the driver connection.
- [ ] Implement `check_inventory`:
    - Cypher query to match `(p:Product)<-[:BELONGS_TO]-(b:InventoryBatch)`.
    - Return product name, batch, stock, expiry.
    - Order by expiry.
- [ ] Implement `sell_item(product_name, qty)`:
    - Find batches for product, ordered by expiry (FIFO).
    - Iterate through batches to fulfill quantity.
    - For each batch used:
        - Create `(bill:Bill)`.
        - Create `(bill)-[:SOLD {tax_amount: ...}]->(b)`.
        - Update `b.current_stock`.
        - *Note*: Tax calculation logic needs `Price` and `TaxRate`. I will assume these are properties of `Product` or `InventoryBatch`. I'll check the graph or assume reasonable defaults/properties if not specified. The prompt says "Price * TaxRate", implying these exist.
- [ ] Implement `calculate_taxes`:
    - Match `(:Bill)-[r:SOLD]->(:InventoryBatch)`.
    - Return sum of `r.tax_amount`.

### Step 3: Execution & Verification
- [ ] Add `main` execution block in `shop_manager.py`.
- [ ] Print initial inventory.
- [ ] Call `sell_item("Dolo 650", 2)`.
- [ ] Print updated inventory.
- [ ] Print total tax liability.

## Verification
- Run `python shop_manager.py` and observe output.
