import sys
import os
import json
from dotenv import load_dotenv

# Setup Path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
load_dotenv()

from src.normalization import normalize_line_item, parse_float
from src.schemas import InvoiceExtraction
from src.workflow.graph import run_extraction_pipeline

def test_specific_invoice(image_path):
    print(f"\n--- TESTING: {os.path.basename(image_path)} ---")
    
    if not os.path.exists(image_path):
        print(f"File not found: {image_path}")
        return

    # 1. Run Extractor
    print("Running Extractor (Graph Pipeline)...")
    # raw_data = extract_invoice_data(image_path) 
    import asyncio
    raw_data = asyncio.run(run_extraction_pipeline(image_path))
    if not raw_data:
        print("Extraction Failed.")
        return

    print(f"Extraction Complete. Found {len(raw_data.get('Line_Items', []))} items.")
    print(f"Supplier: {raw_data.get('Supplier_Name')}")
    print(f"Extracted Grand Total: {raw_data.get('Stated_Grand_Total')}")
    print(f"Extracted Global Discount: {raw_data.get('Global_Discount_Amount')}")
    # print(json.dumps(raw_data, indent=2)) # Too verbose, but good for local debugging
    
    # 2. Run Normalization & Check Math
    print(f"{'Item':<30} | {'Qty':<5} | {'Rate':<8} | {'Taxable':<10} | {'Stated Net':<10} | {'Calc Net':<10} | {'Status'}")
    print("-" * 100)
    
    # Quick hydration to pass pydantic checks -> actually raw_data is dict, we need list of RawLineItem objects or dicts
    # The normalize_line_item expects a RawLineItem object
    
    try:
        inv_obj = InvoiceExtraction(**raw_data)
        normalized_items = []
        
        for raw_item in inv_obj.Line_Items:
            norm = normalize_line_item(raw_item, raw_data['Supplier_Name'])
            normalized_items.append(norm)

        # Apply Proration (Phase 3 Logic)
        global_discount = parse_float(raw_data.get("Global_Discount_Amount", 0.0))
        freight = parse_float(raw_data.get("Freight_Charges", 0.0))
        
        if global_discount > 0 or freight > 0:
            from src.normalization import distribute_global_modifiers
            normalized_items = distribute_global_modifiers(normalized_items, global_discount, freight)

        # Print Results
        for i, norm in enumerate(normalized_items):
            raw_item = inv_obj.Line_Items[i]
            
            # Status Check
            calc_net = norm['Net_Line_Amount']
            stated = float(raw_item.Stated_Net_Amount)
            diff = abs(calc_net - stated)
            status = "✅ MATCH" if diff < 5.0 else "❌ MISMATCH"
            
            print(f"{raw_item.Original_Product_Description[:30]:<30} | "
                  f"{norm['Standard_Quantity']:<5} | "
                  f"{norm['Calculated_Cost_Price_Per_Unit']:<8} | "
                  f"{norm['Calculated_Taxable_Value']:<10} | "
                  f"{stated:<10} | "
                  f"{calc_net:<10} | "
                  f"{status}")

        # Validate Grand Total (Phase 3 Success Criteria)
        calc_total = sum(item['Net_Line_Amount'] for item in normalized_items)
        stated_grand = parse_float(raw_data.get("Stated_Grand_Total", 0.0))
        
        print("-" * 100)
        print(f"Calculated Total (Sum of Line Nets): {calc_total}")
        print(f"Stated Grand Total: {stated_grand}")
        
        if stated_grand > 0:
            diff = abs(calc_total - stated_grand)
            if diff <= 5.0:
                 print(f"✅ GRAND TOTAL MATCH (Diff: {diff:.2f})")
            else:
                 print(f"❌ GRAND TOTAL MISMATCH (Diff: {diff:.2f})")

        print("-" * 100)
                  
    except Exception as e:
        print(f"Processing Error: {data}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Add your specific problematic images here
    # test_specific_invoice("cm_debug_2.png")
    test_specific_invoice("c_m_associates.jpg")

