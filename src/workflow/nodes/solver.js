import logger from "../../utils/logger.js";
import { reconcileFinancials } from "../../normalization/financials.js";

export const applyCorrection = async (state) => {
    logger.info("Solver: Starting Final Reconciliation...");
    const { line_items, header_data, global_modifiers } = state;

    // 1. Initial Mapping to Standard Schema
    let normalizedLines = line_items.map(item => {
        const net = parseFloat(item.Amount || 0);
        const qty = parseFloat(item.Qty || 0);
        const mrp = parseFloat(item.MRP || 0);
        const rate = parseFloat(item.Rate || 0);

        return {
            ...item,
            Net_Line_Amount: net,
            Standard_Quantity: qty,
            MRP: mrp,
            Rate: rate,
            Standard_Item_Name: item.Product || item.Description,
            Pack_Size_Description: item.Pack,
            Batch_No: item.Batch,
            Expiry_Date: item.Expiry,
            HSN_Code: item.HSN,
            Logic_Note: "" // Initialize for usage in reconcile
        };
    });

    // 2. Apply Financial Reconciliation (The "Perfect Match" Engine)
    // We need logic to extract Grand Total from global_modifiers or header_data
    // Typically it's in header_data as Invoice_Total or Grand_Total
    const grandTotal = parseFloat(global_modifiers.Grand_Total || global_modifiers.Invoice_Total || 0);

    // Call the ported logic
    normalizedLines = reconcileFinancials(normalizedLines, global_modifiers, grandTotal);

    // 3. Final Pass: Calculate Derived Metrics (Margins, Landing Cost)
    normalizedLines = normalizedLines.map(item => {
        const net = item.Net_Line_Amount;
        const qty = item.Standard_Quantity;

        let landing = 0;
        if (qty > 0) {
            landing = parseFloat((net / qty).toFixed(2));
        }

        let margin = 0;
        if (item.MRP > 0 && landing > 0) {
            margin = ((item.MRP - landing) / item.MRP) * 100;
        }

        return {
            ...item,
            Final_Unit_Cost: landing,
            Margin_Percentage: parseFloat(margin.toFixed(2))
        };
    });

    // Construct Final Output
    const finalOutput = {
        ...global_modifiers,
        metadata: header_data,
        Line_Items: normalizedLines
    };

    logger.info("Solver: Final Output Constructed.");
    return { final_output: finalOutput };
};
