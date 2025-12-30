import { GoogleGenerativeAI } from "@google/generative-ai";
import { config } from "../../config/env.js";
import logger from "../../utils/logger.js";
import fs from 'fs';

// Initialize Gemini
const genAI = new GoogleGenerativeAI(config.GOOGLE_API_KEY);
const model = genAI.getGenerativeModel({ model: "gemini-2.0-flash" });

/**
 * Reads a file as a Base64 string for Gemini.
 */
function fileToGenerativePart(path, mimeType) {
    return {
        inlineData: {
            data: fs.readFileSync(path).toString("base64"),
            mimeType
        },
    };
}

export const extractHeaderMetadata = async (state) => {
    const { image_path } = state;
    if (!image_path) {
        return { error_logs: ["HeaderAgent: Missing image path."] };
    }

    try {
        const imagePart = fileToGenerativePart(image_path, "image/jpeg"); // Assuming JPEG for now

        const prompt = `
    TASK: EXTRACT SUPPLIER METADATA & INVOICE HEADERS
    
    Target Zones: Header (Top 20%) and Footer (Bottom 20%).
    IGNORE: The central line item table.
    
    GOAL: We need to capture contact details so we can contact the supplier later.
    
    Fields to Extract:
    1. **Supplier_Name**: The main business name at the top (e.g., "KUMAR BROTHERS PHARMACEUTICALS").
    2. **Address**: The full text address. One line preferred.
    3. **Phone_Primary**: Look for "Mob", "Ph", "Call", or just 10-digit numbers. High Priority.
    4. **Phone_Secondary**: If a second number exists (landline or alternate mobile).
    5. **Email**: Look for "@".
    6. **GSTIN**: 15-character alphanumeric (e.g., "03AAGFK...").
    7. **Drug_License_20B**: Look for "D.L.", "License", "20B". Format often "20B-..." or just numbers near "20B".
    8. **Drug_License_21B**: Look for "21B".
    9. **Invoice_No**: The main invoice identifier.
    10. **Invoice_Date**: Date of the invoice (YYYY-MM-DD format preferred).
    
    CRITICAL RULES:
    - **Phone Numbers**: Remove spaces/dashes. e.g., "94173 13201" -> "9417313201".
    - **DL Handling**: If "20B/21B" are listed together (e.g. "20B/21B-12345"), assign "12345" to BOTH 20B and 21B fields.
    
    OUTPUT FORMAT (JSON ONLY):
    {
        "Supplier_Name": "string",
        "Address": "string",
        "Phone_Primary": "string",
        "Phone_Secondary": "string",
        "Email": "string",
        "GSTIN": "string",
        "Drug_License_20B": "string",
        "Drug_License_21B": "string",
        "Invoice_No": "string",
        "Invoice_Date": "string"
    }
    `;

        logger.info("HeaderAgent: Analyzing image for metadata...");

        const result = await model.generateContent([prompt, imagePart]);
        const response = await result.response;
        const text = response.text();

        // JSON Extraction
        const jsonMatch = text.match(/\{[\s\S]*\}/);
        if (jsonMatch) {
            const cleanJson = jsonMatch[0];
            const data = JSON.parse(cleanJson);

            // Filter out nulls
            const cleanedData = Object.fromEntries(
                Object.entries(data).filter(([_, v]) => v != null)
            );

            logger.info(`HeaderAgent: Success. Extracted ${cleanedData.Supplier_Name || 'Unknown'}`);
            return { header_data: cleanedData };
        } else {
            logger.warn(`HeaderAgent: Failed to parse JSON. Response: ${text.substring(0, 100)}...`);
            return { header_data: {} };
        }

    } catch (error) {
        logger.error(`HeaderAgent Error: ${error}`);
        return { error_logs: [`HeaderAgent Failed: ${error.message}`], header_data: {} };
    }
};
