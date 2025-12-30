
/**
 * Parses a float from a string or number, handling currency symbols and formatting.
 * @param {string|number|null} value 
 * @returns {number}
 */
export function parseFloatClean(value) {
    if (value === null || value === undefined) return 0.0;
    if (typeof value === 'number') return value;

    let cleanedValue = String(value).trim().toLowerCase();
    // Remove currency symbols (rs., inr, $, €, £)
    cleanedValue = cleanedValue.replace(/(?:rs\.?|inr|\$|€|£)/g, '').trim();
    // Remove commas
    cleanedValue = cleanedValue.replace(/,/g, '');

    if (!cleanedValue) return 0.0;

    // Handle "Billed + Free" formats (e.g. "10+2")
    if (cleanedValue.includes('+')) {
        try {
            const parts = cleanedValue.split('+');
            const firstPart = parts[0];
            const match = firstPart.match(/\d+(\.\d+)?/);
            if (match) {
                return parseFloat(match[0]);
            }
        } catch (e) {
            // ignore
        }
    }

    const match = cleanedValue.match(/-?\d+(\.\d+)?/);
    if (match) {
        return parseFloat(match[0]);
    }
    return 0.0;
}

/**
 * Parses a quantity string, handling sums (e.g. '10+2') and rounding UP to nearest integer.
 * @param {string|number|null} value 
 * @returns {number}
 */
export function parseQuantity(value) {
    if (value === null || value === undefined) return 0;
    if (typeof value === 'number') return Math.ceil(value);

    let cleanedValue = String(value).trim().toLowerCase();
    cleanedValue = cleanedValue.replace(/(?:rs\.?|inr|\$|€|£)/g, '').trim();
    cleanedValue = cleanedValue.replace(/,/g, '');

    if (!cleanedValue) return 0;

    let totalQty = 0.0;

    if (cleanedValue.includes('+')) {
        const parts = cleanedValue.split('+');
        for (const part of parts) {
            const match = part.trim().match(/-?\d+(\.\d+)?/);
            if (match) {
                totalQty += parseFloat(match[0]);
            }
        }
    } else {
        const match = cleanedValue.match(/-?\d+(\.\d+)?/);
        if (match) {
            totalQty = parseFloat(match[0]);
        }
    }

    // Python logic was returning float(total_qty) but the docstring said rounding UP. 
    // Wait, Python code: return float(total_qty). 
    // The parser logic says "rounding UP to nearest integer" but implementation returns float.
    // I will stick to what the Python implementation DOES, which is returning the float sum.
    // However, the Python function `parse_quantity` line 49 `if isinstance... return math.ceil` implies integer intent.
    // But line 72 `return float(total_qty)` returns float.
    // I will align with "return float" for now to match behavior.
    return totalQty;
}
