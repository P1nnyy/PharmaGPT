
def reconcile_financials_fixed(item_amount, global_discount, total_subtotal, raw_gst, total_sgst, total_cgst, grand_total):
    weight_ratio = item_amount / total_subtotal
    item_discount_share = global_discount * weight_ratio
    item_taxable = item_amount - item_discount_share
    
    # NEW LOGIC
    raw_gst_pct = raw_gst
    sum_gst_pct = 2.5 + 2.5 # Mocking SGST/CGST
    
    gst_percent = raw_gst_pct if raw_gst_pct > 0 else sum_gst_pct
    
    item_tax = item_taxable * (gst_percent / 100)
    landed_cost = item_taxable + item_tax
    
    # Rounding Discovery
    calc_total_pre_round = total_subtotal - global_discount + total_sgst + total_cgst
    discovered_round = grand_total - calc_total_pre_round
    
    return landed_cost, gst_percent, discovered_round

if __name__ == "__main__":
    # Deepak Agencies Case
    landed, gst, rounding = reconcile_financials_fixed(283.20, 52.88, 928.59, 5.0, 21.90, 21.90, 920.00)
    print(f"Deepak Agencies - Landed: {landed:.2f}, GST: {gst}%, Round: {rounding:.2f}")
    
    # CM Associates Case
    landed_cm, gst_cm, rounding_cm = reconcile_financials_fixed(259.28, 78.48, 3171.08, 5.0, 52.53, 52.53, 3198.00)
    print(f"CM Associates - Landed: {landed_cm:.2f}, GST: {gst_cm}%, Round: {rounding_cm:.2f}")
