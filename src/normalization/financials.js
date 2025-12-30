
import winston from 'winston';

const logger = winston.createLogger({
    level: 'info',
    format: winston.format.json(),
    transports: [
        new winston.transports.Console()
    ]
});

/**
 * SMART DIRECTIONAL RECONCILIATION:
 * Adjusts line items to match Grand Total based on mathematical directionality.
 * @param {Array} lineItems 
 * @param {Object} globalModifiers 
 * @param {number} grandTotal 
 * @returns {Array}
 */
export function reconcileFinancials(lineItems, globalModifiers, grandTotal) {
    if (!lineItems || lineItems.length === 0 || grandTotal <= 0) {
        return lineItems;
    }

    const currentSum = lineItems.reduce((sum, item) => sum + parseFloat(item.Net_Line_Amount || 0), 0);
    const gap = currentSum - grandTotal;

    // Threshold for "Close Enough": 0.1% or 0.5
    const threshold = Math.max(0.5, grandTotal * 0.001);

    if (Math.abs(gap) < threshold) {
        logger.info(`Reconcile: Sum ${currentSum.toFixed(2)} matches Total ${grandTotal.toFixed(2)}. No changes.`);
        return lineItems;
    }

    logger.info(`Reconcile: GAP DETECTED. Sum ${currentSum.toFixed(2)} vs Total ${grandTotal.toFixed(2)} (Gap ${gap.toFixed(2)})`);
    logger.info(`Reconcile: Input Modifiers: ${JSON.stringify(globalModifiers)}`);

    const gDisc = Math.abs(parseFloat(globalModifiers.Global_Discount_Amount || 0));

    // Sum taxes
    const gTax = Math.abs(
        parseFloat(globalModifiers.Global_Tax_Amount || 0) +
        parseFloat(globalModifiers.SGST_Amount || 0) +
        parseFloat(globalModifiers.CGST_Amount || 0) +
        parseFloat(globalModifiers.IGST_Amount || 0)
    );

    const freight = Math.abs(parseFloat(globalModifiers.Freight_Charges || 0));

    let modifierToApply = 0.0;
    let action = "NONE";

    if (gap > 0) {
        // Inflation. Reduce.
        logger.info(`Reconcile: Inflation Detected (Gap +${gap.toFixed(2)}). Looking for Reducers...`);
        if (gDisc > 0) {
            modifierToApply = -gap;
            action = "APPLY_DISCOUNT_CORRECTION";
            logger.info(`Reconcile: Found Global Discount (${gDisc}). Applying Correction of -${gap.toFixed(2)} to match Total.`);
        } else {
            const gapPercentage = grandTotal > 0 ? gap / grandTotal : 0;
            if (gapPercentage < 0.05) {
                modifierToApply = -gap;
                action = "APPLY_IMPLICIT_DISCOUNT";
                logger.info(`Reconcile: Implicit Discount Detected (${(gapPercentage * 100).toFixed(1)}%). No explicit discount found, but gap is small. Force Reconciling.`);
            } else {
                logger.warn(`Reconcile: No Discount found and gap (${(gapPercentage * 100).toFixed(1)}%) is too large for implicit correction. Doing nothing (Safe Mode).`);
            }
        }
    } else if (gap < 0) {
        // Deflation. Increase.
        logger.info(`Reconcile: Deflation Detected (Gap ${gap.toFixed(2)}). Looking for Adders...`);
        const adderSum = gTax + freight;
        if (adderSum > 0) {
            modifierToApply = -gap; // -(-gap) = +gap
            action = "APPLY_TAX_FREIGHT_CORRECTION";
            logger.info(`Reconcile: Found Tax/Freight (${adderSum}). Applying Correction of +${Math.abs(gap).toFixed(2)} to match Total.`);
        } else {
            logger.warn("Reconcile: No Tax/Freight found to increase value. Doing nothing (Safe Mode).");
        }
    }

    if (modifierToApply !== 0) {
        lineItems.forEach(item => {
            const originalNet = parseFloat(item.Net_Line_Amount || 0);
            const ratio = currentSum > 0 ? originalNet / currentSum : 0;
            const share = modifierToApply * ratio;
            const newNet = originalNet + share;

            item.Net_Line_Amount = parseFloat(newNet.toFixed(2));

            const qty = parseFloat(item.Standard_Quantity || 1);
            if (qty > 0) {
                item.Final_Unit_Cost = parseFloat((newNet / qty).toFixed(2));
            }

            item.Logic_Note = (item.Logic_Note || "") + ` [Reconcile: ${action}]`;
        });
    }

    return lineItems;
}
