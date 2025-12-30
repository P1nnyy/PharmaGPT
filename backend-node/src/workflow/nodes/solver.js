import logger from "../../utils/logger.js";

export const applyCorrection = async (state) => {
    const { line_items, header_data, global_modifiers } = state;

    // Construct Final Output object
    // Merging Headers (Supplier Info) + Footer (modifiers) + Lines

    const finalOutput = {
        ...global_modifiers,
        metadata: header_data,
        Line_Items: line_items.map(item => {
            // Calculate Landing Cost
            // Logic: Net_Amount / Qty
            const net = parseFloat(item.Amount || 0);
            const qty = parseFloat(item.Qty || 0);
            const landing = qty > 0 ? net / qty : 0;

            return {
                ...item,
                Net_Line_Amount: net,
                Final_Unit_Cost: landing,
                Standard_Item_Name: item.Product,
                Standard_Quantity: qty,
                Pack_Size_Description: item.Pack,
                Batch_No: item.Batch,
                Expiry_Date: item.Expiry,
                HSN_Code: item.HSN
            };
        })
    };

    logger.info("Solver: Final Output Constructed.");
    return { final_output: finalOutput };
};
