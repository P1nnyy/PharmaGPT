import { GoogleGenerativeAI } from "@google/generative-ai";
import { config } from "../../config/env.js";
import logger from "../../utils/logger.js";

const genAI = new GoogleGenerativeAI(config.GOOGLE_API_KEY);
const model = genAI.getGenerativeModel({ model: "gemini-2.0-flash" });

export const executeMapping = async (state) => {
    const { raw_text_rows } = state;

    if (!raw_text_rows || raw_text_rows.length === 0) {
        logger.warn("Mapper: No raw text rows found.");
        return {};
    }

    logger.info(`Mapper: Processing ${raw_text_rows.length} raw fragments...`);
    const contextText = raw_text_rows.join("\n");

    const prompt = `
    You are a DATA STRUCTURE EXPERT.
    Input Raw OCR Text:
    """
    ${contextText}
    """
    
    TASK: Convert to VALID JSON array of line items.
    
    SCHEMA:
    - Product: string
    - Pack: string (Pack Size)
    - Qty: float (Total Quantity)
    - Batch: string (Batch No)
    - Expiry: string
    - HSN: string
    - Rate: float (Unit Price)
    - Amount: float (Net Amount)
    - MRP: float
    
    CRITICAL:
    - Do not merge distinct products.
    - Keep Duplicates if they are separate line items.
    - Ignore headers.
    
    Output JSON format:
    {
        "line_items": [
            { "Product": "...", "Qty": 10, ... }
        ]
    }
    `;

    try {
        const result = await model.generateContent(prompt);
        const text = (await result.response).text().trim();
        const jsonMatch = text.match(/\{[\s\S]*\}/);

        if (jsonMatch) {
            const data = JSON.parse(jsonMatch[0]);
            const items = data.line_items || [];
            logger.info(`Mapper: Mapped ${items.length} items.`);
            // Return to line_items channel
            return { line_items: items };
        } else {
            return { error_logs: ["Mapper: Invalid JSON output."] };
        }

    } catch (e) {
        logger.error(`Mapper Error: ${e}`);
        return { error_logs: [`Mapper Failed: ${e.message}`] };
    }
};
