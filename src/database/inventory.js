
import { getDriver } from './connection.js';

/**
 * Returns inventory aggregated by Product Name + MRP.
 * Calculates Total Quantity (Stock).
 * @returns {Promise<Array>}
 */
export async function getInventoryAggregation() {
    const driver = getDriver();
    const session = driver.session();

    const query = `
    MATCH (l:Line_Item)-[:REFERENCES]->(p:Product)
    WITH p.name as product_name, l.mrp as mrp, sum(l.quantity) as total_qty, collect(l.batch_no) as batches
    RETURN product_name, mrp, total_qty, batches
    ORDER BY product_name ASC
    `;

    try {
        const result = await session.run(query);
        return result.records.map(record => ({
            product_name: record.get('product_name'),
            mrp: record.get('mrp'), // Neo4j integers might need conversion if they are large, but MRP usually float/int
            total_quantity: record.get('total_qty'),
            batches: [...new Set(record.get('batches'))] // unique batches
        }));
    } finally {
        await session.close();
    }
}
