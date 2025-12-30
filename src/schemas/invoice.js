import { z } from 'zod';

export const SupplierMetadataSchema = z.object({
    Supplier_Name: z.string().optional().describe("Name of the supplier."),
    Address: z.string().optional().describe("Full text address of the supplier."),
    Phone_Primary: z.string().optional().describe("Primary contact number (Mobile/Landline)."),
    Phone_Secondary: z.string().optional().describe("Secondary contact number if available."),
    Email: z.string().optional().describe("Email address."),
    GSTIN: z.string().optional().describe("GST Identification Number."),
    Drug_License_20B: z.string().optional().describe("Drug License Number (Form 20B)."),
    Drug_License_21B: z.string().optional().describe("Drug License Number (Form 21B).")
});

export const RawLineItemSchema = z.object({
    Product: z.string().describe("The product description exactly as it appears on the invoice."),
    Qty: z.union([z.string(), z.number()]).optional().describe("Quantity extracted."),
    Batch: z.string().optional().nullable().describe("Batch number."),
    Section: z.string().optional().default("Main").describe("Section of invoice (e.g. 'Main', 'Sales Return')."),

    // Blind Fields
    Amount: z.union([z.string(), z.number()]).optional().describe("The neutral column value (Amount/Total)."),
    Rate: z.number().optional().describe("Unit Price."),
    MRP: z.number().optional().describe("MRP if available."),
    Expiry: z.string().optional().describe("Expiry date content."),
    HSN: z.string().optional().describe("HSN/SAC code."),

    // Computed/Filled
    Net_Line_Amount: z.number().optional(),
    Calculated_Cost_Price_Per_Unit: z.number().optional(),
    Logic_Note: z.string().optional(),

    // Snake Case
    net_amount: z.number().optional(),
    landing_cost: z.number().optional()
});

export const InvoiceExtractionSchema = z.object({
    Supplier_Name: z.string().optional().default("Unknown"),
    Invoice_No: z.string().optional().nullable(),
    Invoice_Date: z.string().optional().nullable(),
    Supplier_Phone: z.string().optional().nullable(),
    Supplier_GST: z.string().optional().nullable(),

    metadata: SupplierMetadataSchema.optional().nullable(),

    Line_Items: z.array(RawLineItemSchema).default([]),
    Stated_Grand_Total: z.union([z.string(), z.number()]).optional().nullable(),

    Global_Discount_Amount: z.union([z.string(), z.number()]).optional().nullable(),
    Freight_Charges: z.union([z.string(), z.number()]).optional().nullable(),
    SGST_Amount: z.union([z.string(), z.number()]).optional().nullable(),
    CGST_Amount: z.union([z.string(), z.number()]).optional().nullable(),
    IGST_Amount: z.union([z.string(), z.number()]).optional().nullable(),
    Round_Off: z.union([z.string(), z.number()]).optional().nullable()
});
