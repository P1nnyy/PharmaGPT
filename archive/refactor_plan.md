# Refactor Plan: PharmaGPT Hardening

## 1. Bug Hunt & Code Analysis
### Issues Identified
- **`sell_item` Silent Failures**: The current implementation prints errors (`print("Insufficient stock...")`) and returns `None`. This prevents the UI and future AI agents from knowing *why* a transaction failed.
- **`agent.py` is Empty**: The file exists but has no content.
- **Missing Fuzzy Search**: The user attempted to add `find_product_fuzzy` but it is missing from the actual file.
- **Hardcoded Credentials**: Credentials are loaded from `.env`, which is good, but error handling could be more robust.

## 2. Proposed Refactoring

### A. `shop_manager.py`
1.  **Refactor `sell_item`**:
    - **Change**: Remove `print` statements.
    - **Logic**: Raise `ValueError` for "Product not found" or "Insufficient stock".
    - **Return**: On success, return a dictionary: `{"status": "success", "tax": float, "message": str}`.
2.  **Implement `find_product_fuzzy(search_term)`**:
    - Use Neo4j Fulltext Index (to be created in Schema Upgrade).
    - Return list of matching product names.

### B. `app.py`
1.  **Update POS Logic**:
    - Wrap `sell_item` call in `try...except ValueError` block.
    - Display specific error messages from the exception in `st.error`.
2.  **Add AI Agent Tab**:
    - Re-implement the "Chat" tab the user intended.
    - Integrate with `agent.py` tools.

### C. `agent.py`
1.  **Create Tools**:
    - `check_inventory_tool`: Returns string summary of inventory.
    - `sell_item_tool`: Calls `shop.sell_item`, handles exceptions, and returns a natural language string (e.g., "Sold 2 units of Dolo. Tax: $1.50").

## 3. Execution Order
1.  Apply **Schema Upgrade** (Cypher).
2.  Refactor **`shop_manager.py`**.
3.  Populate **`agent.py`**.
4.  Update **`app.py`**.
