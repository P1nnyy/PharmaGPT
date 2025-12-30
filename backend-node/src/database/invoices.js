import neo4j from 'neo4j-driver';
import logger from '../utils/logger.js';

export const ingestInvoice = async (driver, invoiceData, normalizedItems, imagePath = null) => {
    const session = driver.session();

    // Calculate Grand Total from line items
    const grandTotal = normalizedItems.reduce((sum, item) => sum + (item.Net_Line_Amount || 0.0), 0.0);

    try {
        // 1. Merge Invoice
        await session.executeWrite(tx => createInvoiceTx(tx, invoiceData, grandTotal, imagePath));

        // 2. Process Line Items
        for (const item of normalizedItems) {
            await session.executeWrite(tx => createLineItemTx(tx, invoiceData.Invoice_No, item));
        }
    } catch (error) {
        logger.error(`Error ingesting invoice: ${error}`);
        throw error;
    } finally {
        await session.close();
    }
};

const createInvoiceTx = (tx, invoiceData, grandTotal, imagePath) => {
    const meta = invoiceData.metadata || {};

    const query = `
    // 1. Merge Supplier (Strict Upsert)
    MERGE (s:Supplier {name: $supplier_name})
    ON CREATE SET 
        s.phone = $supplier_phone,
        s.phone_secondary = $phone_secondary,
        s.gst = $supplier_gst,
        s.address = $address,
        s.email = $email,
        s.dl_20b = $dl_20b,
        s.dl_21b = $dl_21b,
        s.created_at = timestamp()
    ON MATCH SET 
        s.phone = COALESCE($supplier_phone, s.phone),
        s.phone_secondary = COALESCE($phone_secondary, s.phone_secondary),
        s.gst = COALESCE($supplier_gst, s.gst),
        s.address = COALESCE($address, s.address),
        s.email = COALESCE($email, s.email),
        s.dl_20b = COALESCE($dl_20b, s.dl_20b),
        s.dl_21b = COALESCE($dl_21b, s.dl_21b),
        s.updated_at = timestamp()
    
    // 2. Merge Invoice
    MERGE (i:Invoice {invoice_number: $invoice_no})
    ON CREATE SET 
        i.supplier_name = $supplier_name,
        i.status = 'CONFIRMED',
        i.invoice_date = $invoice_date,
        i.grand_total = $grand_total,
        i.image_path = $image_path,
        i.created_at = timestamp()
    ON MATCH SET
        i.supplier_name = $supplier_name,
        i.status = 'CONFIRMED',
        i.invoice_date = $invoice_date,
        i.grand_total = $grand_total,
        i.image_path = $image_path,
        i.updated_at = timestamp()
        
    // 3. Link Supplier -> Invoice
    MERGE (s)-[:ISSUED]->(i)
  `;

    tx.run(query, {
        invoice_no: invoiceData.Invoice_No,
        supplier_name: invoiceData.Supplier_Name,
        supplier_phone: meta.Phone_Primary || invoiceData.Supplier_Phone,
        phone_secondary: meta.Phone_Secondary || null,
        supplier_gst: meta.GSTIN || invoiceData.Supplier_GST,
        address: meta.Address || null,
        email: meta.Email || null,
        dl_20b: meta.Drug_License_20B || null,
        dl_21b: meta.Drug_License_21B || null,
        invoice_date: invoiceData.Invoice_Date,
        grand_total: grandTotal,
        image_path: imagePath
    });
};

const createLineItemTx = (tx, invoiceNo, item) => {
    const query = `
    MATCH (i:Invoice {invoice_number: $invoice_no})
    
    MERGE (p:Product {name: $standard_item_name})
    MERGE (h:HSN {code: $hsn_code})
    
    // Find Last Price logic (omitted for brevity, can be re-added if complex price logic ported)
    // Simplified for Node MVP: Just create item
    
    CREATE (l:Line_Item {
        pack_size: $pack_size,
        quantity: $quantity,
        net_amount: $net_amount,
        batch_no: $batch_no,
        hsn_code: $hsn_code,
        mrp: $mrp,
        expiry_date: $expiry_date,
        landing_cost: $landing_cost,
        logic_note: $logic_note,
        created_at: timestamp()
    })
    
    MERGE (i)-[:CONTAINS]->(l)
    MERGE (l)-[:REFERENCES]->(p)
    MERGE (l)-[:BELONGS_TO_HSN]->(h)
  `;

    tx.run(query, {
        invoice_no: invoiceNo,
        standard_item_name: item.Standard_Item_Name,
        pack_size: item.Pack_Size_Description,
        quantity: item.Standard_Quantity,
        net_amount: item.Net_Line_Amount,
        batch_no: item.Batch_No,
        hsn_code: item.HSN_Code || "UNKNOWN",
        mrp: item.MRP || 0.0,
        expiry_date: item.Expiry_Date,
        landing_cost: item.Final_Unit_Cost || 0.0,
        logic_note: item.Logic_Note || "N/A"
    });
};

export const getRecentActivity = async (driver) => {
    const session = driver.session();
    const query = `
    MATCH (i:Invoice)
    OPTIONAL MATCH (s:Supplier)-[:ISSUED]->(i)
    RETURN 
        i.invoice_number as invoice_number,
        i.invoice_date as date,
        i.grand_total as total,
        i.status as status,
        i.image_path as image_path,
        s.name as supplier_name,
        s.phone as supplier_phone,
        s.gst as supplier_gst,
        i.created_at as created_at
    ORDER BY i.created_at DESC
    LIMIT 50
  `;

    try {
        const result = await session.run(query);
        return result.records.map(record => ({
            invoice_number: record.get("invoice_number"),
            date: record.get("date"),
            total: record.get("total"),
            status: record.get("status"),
            image_path: record.get("image_path"),
            supplier_name: record.get("supplier_name") || "Unknown",
            supplier_phone: record.get("supplier_phone"),
            supplier_gst: record.get("supplier_gst"),
            created_at: record.get("created_at")
        }));
    } catch (error) {
        logger.error(`Error fetching activity: ${error}`);
        return [];
    } finally {
        await session.close();
    }
};
