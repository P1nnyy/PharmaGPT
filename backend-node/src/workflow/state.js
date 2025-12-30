import { Annotation } from "@langchain/langgraph";

// Reducer for merging dictionaries (objects)
const mergeObjects = (left, right) => {
    if (!left) return right || {};
    if (!right) return left || {};
    return { ...left, ...right };
};

// Reducer for appending arrays
const concatArrays = (left, right) => {
    if (!left) return right || [];
    if (!right) return left || [];
    return [...left, ...right];
};

/**
 * InvoiceState Annotation for LangGraph JS.
 * Mirrors the Python TypedDict structure.
 */
export const InvoiceState = Annotation.Root({
    image_path: Annotation(),

    // Plan
    extraction_plan: Annotation(),

    // Parallel Outputs (Reducers applied)
    line_item_fragments: Annotation({
        reducer: concatArrays,
        default: () => [],
    }),

    header_data: Annotation({
        reducer: mergeObjects,
        default: () => ({}),
    }),

    raw_text_rows: Annotation({
        reducer: concatArrays,
        default: () => [],
    }),

    // Final Outputs
    line_items: Annotation(),
    global_modifiers: Annotation({
        reducer: mergeObjects,
        default: () => ({}),
    }),

    final_output: Annotation(),

    // Logs
    error_logs: Annotation({
        reducer: concatArrays,
        default: () => [],
    }),

    feedback_logs: Annotation({
        reducer: concatArrays,
        default: () => [],
    }),

    // Counters
    retry_count: Annotation({
        default: () => 0,
    }),
    critic_verdict: Annotation(),
    correction_factor: Annotation(),
});
