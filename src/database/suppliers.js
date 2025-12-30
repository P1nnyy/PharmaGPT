
import { getDriver } from './connection.js';

/**
 * Returns a list of Suppliers, each with their invoices.
 * @returns {Promise<Array>}
 */
export async function getSupplierHistory() {
    const driver = getDriver();
    const session = driver.session();

    const query = `
    MATCH (s:Supplier)
    OPTIONAL MATCH (s)-[:ISSUED]->(i:Invoice)
    WITH s, i ORDER BY i.created_at DESC
    WITH s, collect({
        invoice_number: i.invoice_number,
        date: i.invoice_date,
        total: i.grand_total,
        status: i.status,
        image_path: i.image_path
    }) as invoices
    RETURN s.name as name, s.gst as gst, s.phone as phone, invoices
    ORDER BY name ASC
    `;

    try {
        const result = await session.run(query);
        return result.records.map(record => {
            const rawInvoices = record.get('invoices');
            const validInvoices = rawInvoices.filter(inv => inv.invoice_number);

            const totalSpend = validInvoices.reduce((sum, inv) => {
                return sum + (parseFloat(inv.total) || 0);
            }, 0);

            return {
                name: record.get('name'),
                gst: record.get('gst'),
                phone: record.get('phone'),
                total_spend: totalSpend,
                invoices: validInvoices
            };
        });
    } finally {
        await session.close();
    }
}
