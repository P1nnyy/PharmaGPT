# Data Structure Standardization Plan

## Objective
Ensure consistency between the **Bill Ingestion Data** (from Vision Agent) and the **Inventory Data** (in Neo4j). Currently, there are mismatches in field names and formats (e.g., "Qty" vs "Sealed", "PackSize" vs "Pack Size", "DosageForm" vs "Form").

## 1. Unified Data Model (The "Golden Record")
We will define a single dictionary structure for a "Medicine Item" that is used across the entire app.

```python
{
    "product_name": str,       # "Dolo 650"
    "batch_number": str,       # "B123"
    "expiry_date": str,        # "YYYY-MM-DD"
    "manufacturer": str,       # "Micro Labs"
    "dosage_form": str,        # "Tablet"
    "pack_size": int,          # 15
    "mrp": float,              # 30.0
    "tax_rate": float,         # 0.12 (12%)
    "quantity_packs": int,     # 5 (Sealed Packs)
    "quantity_loose": int      # 0 (Loose Units)
}
```

## 2. Changes Required

### A. `vision_agent.py`
-   Ensure the JSON output keys match the "Golden Record" keys (or map them immediately).
-   Current: `Product`, `Batch`, `Expiry`, `Qty`, `PackSize`, `MRP`, `Manufacturer`, `DosageForm`.
-   Target: `product_name`, `batch_number`, `expiry_date`, `quantity_packs`, `pack_size`, `mrp`, `manufacturer`, `dosage_form`.

### B. `shop_manager.py` (`check_inventory`)
-   Update the returned dictionary keys to match the "Golden Record" for display consistency.
-   Current: `Product`, `Batch`, `Stock`, `Sealed`, `Loose`, `Expiry`, `Form`, `Manufacturer`, `MRP`, `Tax (%)`.
-   Target: Standardize to the same keys or ensure the UI maps them correctly.

### C. `app.py`
-   Update the `st.data_editor` to use the standardized keys.
-   Update the `add_medicine_stock` call to use the standardized keys.

## 3. Implementation Steps
1.  **Update `vision_agent.py`**: Modify the prompt to output the standardized keys.
2.  **Update `app.py`**:
    -   When receiving data from `vision_agent`, ensure it matches the DataFrame columns we want to show.
    -   Rename columns in `check_inventory` display to match the Ingestion table for visual consistency.
