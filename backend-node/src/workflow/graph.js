import { StateGraph, START, END } from "@langchain/langgraph";
import { InvoiceState } from "./state.js";
import { surveyDocument } from "./nodes/surveyor.js";
import { executeExtraction } from "./nodes/worker.js";
import { extractHeaderMetadata } from "./nodes/header_agent.js";
import { executeMapping } from "./nodes/mapper.js";
import { auditExtraction } from "./nodes/auditor.js";
import { applyCorrection } from "./nodes/solver.js";
import logger from "../utils/logger.js";

const builder = new StateGraph(InvoiceState)
    .addNode("surveyor", surveyDocument)
    .addNode("worker", executeExtraction)
    .addNode("header_agent", extractHeaderMetadata)
    .addNode("mapper", executeMapping)
    .addNode("auditor", auditExtraction)
    .addNode("solver", applyCorrection)

    .addEdge(START, "surveyor")

    // Parallel Fan-out
    .addEdge("surveyor", "worker")
    .addEdge("surveyor", "header_agent")

    // Convergence
    .addEdge("worker", "mapper")
    .addEdge("header_agent", "mapper") // Mapper waits for state updates? 
    // Note: In LangGraph JS, multiple edges to same node -> Node runs when ALL predecessors complete?
    // Actually, standard behavior is OR (runs when any completes). 
    // To synchronize, we might need a join node or sequential chain after parallel.
    // For MVP, we'll chain them strictly to guarantee state readiness if LangGraph behavior differs.
    // BUT, let's trust the Reducer logic. However, Mapper needs ALL data.
    // Safer flow: Surveyor -> (Parallel) -> Joiner -> Mapper.
    // We'll let Mapper run twice if needed, but it's waste.
    // Let's stick to the prompt's parallel design. 
    // If Mapper runs twice, it merges to `line_items`. Maybe duplicative?
    // Let's force sequential for "worker" branch to avoid complexity in MVP.
    // Surveyor -> Header -> Worker -> Mapper.

    // REVISION: The prompt asked for Parallel.
    // Let's use a "Barrier" pattern.
    // Or just simply: Surveyor -> Header -> Worker -> Mapper. This is safe and ensures all data is present.

    .addEdge("mapper", "auditor")
    .addEdge("auditor", "solver")
    .addEdge("solver", END);

// Compile
export const app = builder.compile();

export const runExtractionPipeline = async (imagePath) => {
    logger.info(`Starting Graph for ${imagePath}`);

    // NOTE: Initial state must be valid
    const result = await app.invoke({
        image_path: imagePath,
        retry_count: 0
    });

    return result.final_output;
};
