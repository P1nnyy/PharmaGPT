# PharmaGPT v2: "Apple Glass" Refactoring Plan

## 1. ✂️ Feature Pruning (The "Later" Pile)
We will streamline the application to focus strictly on **Ingestion (Enter Stock)** and **Retrieval (Find Stock)**.

-   **Deprecate/Move to v2**:
    -   `create_customer`, `get_customer` (CRM logic) in `shop_manager.py`.
    -   "Cashier (POS)" tab in `app.py` (Temporarily hide or simplify to a "Quick Deduct" command via Agent).
    -   "Manager Portal" manual form (Replaced by Bill Ingestion).
-   **Keep**:
    -   `check_inventory` (Retrieval).
    -   `add_medicine_stock` (Core Ingestion logic).
    -   `sell_item` (Core Inventory update logic, kept for backend utility).

## 2. 💎 The "Apple Glass" UI (Glassmorphism)
We will transform the Streamlit interface using custom CSS.

-   **Visual Style**:
    -   **Background**: Deep, organic gradient (Dark Blue/Purple/Black).
    -   **Cards**: Translucent white/black with `backdrop-filter: blur(10px)`.
    -   **Typography**: Inter/San Francisco style (System fonts).
    -   **Layout**:
        -   **Central Hub**: A large, "Spotlight-style" search bar for the Agent.
        -   **Floating Action Button (FAB)**: For "Scan Bill" (Ingestion).
        -   **Hidden Sidebar**: Remove standard navigation.

## 3. 🧠 The "Atomic" Backend Logic
-   **Atomic Sizing**: The current `InventoryBatch` model already supports `sealed_packs` and `loose_tablets`. We will enforce that all ingestion calculates `Total Atoms = (Packs * PackSize) + Loose`.
-   **Search**:
    -   Current: Cypher `CONTAINS` / Fulltext.
    -   **Upgrade**: We will prepare the code for Vector Search by ensuring product descriptions/metadata are ready for embedding. For now, we stick to the robust Graph traversal which is highly accurate for structured inventory.

## 4. 📸 The Ingestion Pipeline (Agentic)
-   **Flow**:
    1.  **Upload**: User drops a Bill Image (PDF/PNG).
    2.  **Process**: (Mocked for now, ready for Gemini Vision) Extract JSON.
    3.  **Verify**: Display data in `st.data_editor` (AG Grid style).
    4.  **Commit**: Button to write to Neo4j.

---

## Execution Steps
1.  **Refactor `shop_manager.py`**: Mark CRM methods as `@deprecated`.
2.  **Create `glass_styles.css`**: Define the Glassmorphism variables and classes.
3.  **Rewrite `app.py`**:
    -   Inject CSS.
    -   Implement the "Spotlight" Agent interface.
    -   Implement the "Bill Ingestion" modal/overlay.
