import { GoogleGenerativeAI } from "@google/generative-ai";
import { config } from "../../config/env.js";
import logger from "../../utils/logger.js";
import fs from 'fs';

const genAI = new GoogleGenerativeAI(config.GOOGLE_API_KEY);
const model = genAI.getGenerativeModel({ model: "gemini-2.0-flash" });

function fileToGenerativePart(path, mimeType) {
    return {
        inlineData: {
            data: fs.readFileSync(path).toString("base64"),
            mimeType
        },
    };
}

async function extractFromZone(imagePart, zone) {
    const zoneType = (zone.type || "table").toLowerCase();

    let prompt = "";
    if (zoneType.includes("table")) {
        prompt = `
        Target Zone: ${zone.description}
        TASK: EXTRACT RAW TABLE DATA (VERBATIM).
        
        Instructions:
        1. Look at the table in this image.
        2. Extract EVERY row of text you see.
        3. Format as a PIPE-SEPARATED Table (Markdown).
        4. Include headers if visible.
        5. **Do not merge rows**. Keep every single line item separate.
        6. **DUPLICATES**: If the Exact Same Item appears multiple times, LIST IT MULTIPLE TIMES.
        
        Output ONLY the markdown table string.
        `;
        try {
            const result = await model.generateContent([prompt, imagePart]);
            const text = (await result.response).text().trim();
            return { type: "raw_text", data: [text] };
        } catch (e) {
            return { type: "error", error: e.message };
        }
    } else if (zoneType.includes("footer")) {
        prompt = `
        Target Zone: ${zone.description}
        Task: Extract global financial fields.
        
        Fields:
        - Global_Discount_Amount
        - Freight_Charges
        - Round_Off
        - SGST_Amount
        - CGST_Amount
        - IGST_Amount
        - Stated_Grand_Total (ANCHOR TRUTH)
        
        Return JSON.
        `;
        try {
            const result = await model.generateContent([prompt, imagePart]);
            const text = (await result.response).text().trim();
            const jsonMatch = text.match(/\{[\s\S]*\}/);
            if (jsonMatch) {
                return { type: "modifiers", data: JSON.parse(jsonMatch[0]) };
            }
            return { type: "modifiers", data: {} };
        } catch (e) {
            return { type: "error", error: e.message };
        }
    }
    return {};
}

export const executeExtraction = async (state) => {
    const { image_path, extraction_plan } = state;
    if (!image_path) return { error_logs: ["Worker: Missing image path."] };

    try {
        const imagePart = fileToGenerativePart(image_path, "image/jpeg");
        logger.info(`Worker: Processing ${extraction_plan.length} zones...`);

        const tasks = extraction_plan.map(zone => extractFromZone(imagePart, zone));
        const results = await Promise.all(tasks);

        const raw_text_rows = [];
        const global_modifiers = {};
        const error_logs = [];

        results.forEach(res => {
            if (res.type === "raw_text") {
                raw_text_rows.push(...res.data);
            } else if (res.type === "modifiers") {
                Object.assign(global_modifiers, res.data);
            } else if (res.type === "error") {
                error_logs.push(`Zone Failed: ${res.error}`);
            }
        });

        return {
            raw_text_rows,
            global_modifiers,
            error_logs
        };

    } catch (error) {
        logger.error(`Worker Error: ${error}`);
        return { error_logs: [`Worker Failed: ${error.message}`] };
    }
};
