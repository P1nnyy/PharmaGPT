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

export const surveyDocument = async (state) => {
    const { image_path } = state;
    if (!image_path) return { error_logs: ["Surveyor: Missing image path."] };

    try {
        const imagePart = fileToGenerativePart(image_path, "image/jpeg");

        const prompt = `
    Role: Document Surveyor
    Task: Analyze this invoice Layout.
    Identify the distinct 'Zones' containing data tables.
    
    Output JSON:
    [
      { "type": "table", "description": "Main product table with columns..." },
      { "type": "footer", "description": "Totals and taxes section..." }
    ]
    `; // Simplified for Node MVP

        logger.info("Surveyor: Analyzing document layout...");
        const result = await model.generateContent([prompt, imagePart]);
        const response = await result.response;
        const text = response.text();

        // Mock parsing for now or basic JSON extract
        // For MVP, we'll force a standard single-table plan if parsing fails
        let plan = [];
        try {
            const jsonMatch = text.match(/\[[\s\S]*\]/);
            if (jsonMatch) plan = JSON.parse(jsonMatch[0]);
        } catch (e) { }

        // Fallback Plan if LLM fail
        if (!plan || plan.length === 0) {
            plan = [
                { type: "header", description: "Top Header Check" },
                { type: "table", description: "Main Table" },
                { type: "footer", description: "Footer Totals" }
            ];
        }

        return { extraction_plan: plan };
    } catch (error) {
        logger.error(`Surveyor Error: ${error}`);
        // Return a default plan on error so pipeline continues
        return {
            extraction_plan: [{ type: "table", description: "Fallback Main Table" }],
            error_logs: [`Surveyor Failed: ${error.message}`]
        };
    }
};
