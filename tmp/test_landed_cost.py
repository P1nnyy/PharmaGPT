
def simulate_calculation(item_amount, global_discount, total_subtotal, raw_gst):
    # Current Logic (Buggy)
    weight_ratio = item_amount / total_subtotal
    item_discount_share = global_discount * weight_ratio
    item_taxable = item_amount - item_discount_share
    
    # Bug: Summing SGST + CGST + Raw_GST
    sgst_pct = raw_gst / 2
    cgst_pct = raw_gst / 2
    gst_percent = sgst_pct + cgst_pct + raw_gst # Doubled!
    
    item_tax = item_taxable * (gst_percent / 100)
    landed_cost = item_taxable + item_tax
    
    print(f"--- CURRENT LOGIC (BUGGY) ---")
    print(f"Item Amount: {item_amount}")
    print(f"Discount Share: {item_discount_share:.2f}")
    print(f"Taxable: {item_taxable:.2f}")
    print(f"GST Percent used: {gst_percent}%")
    print(f"Tax Amount: {item_tax:.2f}")
    print(f"Landed Cost: {landed_cost:.2f}")
    print(f"Unit Cost (Qty 2): {landed_cost/2:.2f}")

    # Proposed Logic (Fixed)
    fixed_gst_percent = raw_gst # Don't sum if Raw_GST exists
    fixed_item_tax = item_taxable * (fixed_gst_percent / 100)
    fixed_landed_cost = item_taxable + fixed_item_tax
    
    print(f"\n--- PROPOSED LOGIC (FIXED) ---")
    print(f"GST Percent used: {fixed_gst_percent}%")
    print(f"Tax Amount: {fixed_item_tax:.2f}")
    print(f"Landed Cost: {fixed_landed_cost:.2f}")
    print(f"Unit Cost (Qty 2): {fixed_landed_cost/2:.2f}")

if __name__ == "__main__":
    # Deepak Agencies Case
    simulate_calculation(283.20, 52.88, 928.59, 5.0)
