import logger from "../../utils/logger.js";

export const auditExtraction = async (state) => {
    const { line_items } = state;

    if (!line_items || line_items.length === 0) return {};

    logger.info("Auditor: Verifying items...");

    // Logic: Simple Deduplication (Based on Batch + Qty + Amount)
    // Complex python logic (fuzzy matching) replaced with exact match for MVP speed
    // Can be enhanced later with 'string-similarity' package

    const uniqueItems = [];
    const seen = new Set();

    for (const item of line_items) {
        // Normalization
        const p = (item.Product || "").trim().toLowerCase().replace(/\s+/g, '');
        const b = (item.Batch || "nb").trim().toLowerCase();
        const q = parseFloat(item.Qty || 0);
        const a = parseFloat(item.Amount || 0);

        const key = `${p}|${b}|${q}|${a}`;

        if (seen.has(key)) {
            logger.info(`Auditor: Dropping duplicate ${key}`);
            continue;
        }

        seen.add(key);

        // Sanity Check: Qty vs MRP Swap
        const mrp = parseFloat(item.MRP || 0);
        if (mrp > 0 && q > 1.5 && Math.abs(mrp - a) < 1.0) {
            // MRP is suspiciously close to Amount -> Logic Error in Mapper
            logger.warn("Auditor: MRP equals Amount. Suspected column swap.");
            // Keep item but log warning (or fix logic here)
            item.Logic_Note = "Auditor Warning: MRP=Amount";
        }

        uniqueItems.push(item);
    }

    logger.info(`Auditor: Reduced ${line_items.length} to ${uniqueItems.length} items.`);

    // Check Global Modifiers (Sanitize)
    // We treat 'state.global_modifiers' as read-only source here, 
    // but we can return updates to it.

    return { line_items: uniqueItems };
};
