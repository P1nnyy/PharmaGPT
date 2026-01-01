import google.generativeai as genai
import json
import os
from typing import Dict, Any, List
from src.workflow.state import InvoiceState as InvoiceStateDict
from src.utils.logging_config import get_logger
from src.services.embeddings import generate_embedding
from neo4j import GraphDatabase
import os

logger = get_logger("mapper")

# Neo4j Config (Ad-hoc connection for Mapper RAG)
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

# Initialize Gemini
API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=API_KEY)

def execute_mapping(state: InvoiceStateDict) -> Dict[str, Any]:
    """
    Mapper Node.
    Stage 2 of Extraction.
    Takes Raw Text Rows (from Worker) and maps them to the Strict Schema.
    """
    raw_rows = state.get("raw_text_rows", [])
    
    if not raw_rows:
        logger.warning("Mapper: No raw text rows found. Skipping.")
        return {}

    logger.info(f"Mapper: Processing {len(raw_rows)} raw text fragments...")
    
    # Model Setup
    model = genai.GenerativeModel("gemini-2.0-flash")
    
    # Construct Context from all rows
    # Each row is likely a string "Product | Qty | Rate"
    context_text = "\n".join(raw_rows)
    
    # Load Memory
    from src.services.mistake_memory import MEMORY
    rules = MEMORY.get_rules()
    memory_rules = "\n    ".join([f"- {r}" for r in rules]) if rules else "- No previous mistakes recorded."
    
    # --- RAG: Vector Search for Similar Invoice ---
    cheat_sheet = "No similar examples found."
    try:
        embedding = generate_embedding(context_text)
        if embedding:
            # Connect Ad-Hoc (Short-lived)
            with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
                with driver.session() as session:
                    # Query for nearest neighbor (> 0.88 similarity)
                    # Note: You must have created the vector index 'invoice_examples_index'
                    query = """
                    CALL db.index.vector.queryNodes('invoice_examples_index', 1, $embedding)
                    YIELD node, score
                    WHERE score > 0.88
                    RETURN node.raw_text as raw, node.json_payload as json, score
                    """
                    result = session.run(query, embedding=embedding).single()
                    
                    if result:
                        example_raw = result["raw"]
                        example_json = result["json"]
                        score = result["score"]
                        logger.info(f"Mapper: Found similar invoice example! Score: {score:.4f}")
                        
                        cheat_sheet = f"""
    ### REFERENCE EXAMPLE (HIGH SIMILARITY MATCH: {score:.2f})
    Build your output based on how we mapped this similar invoice:
    
    [EXAMPLE INPUT]:
    {example_raw[:300]}... (truncated)
    
    [EXAMPLE OUTPUT MAP]:
    {example_json}
    
    **INSTRUCTION**: Follow the logic of the Example Output EXACTLY for handling columns, packs, and formatting.
                        """
                    else:
                        logger.info("Mapper: No similar invoice found above threshold.")
    except Exception as e:
        logger.warning(f"Mapper RAG Lookup Failed: {e}")
    
    prompt = f"""
    You are a DATA STRUCTURE EXPERT.
    Your input is a raw, unstructured extraction from an invoice table (OCR Text).
    
    INPUT RAW TEXT:
    \"\"\"
    {context_text}
    \"\"\"
    
    YOUR TASK:
    Convert this text into a VALID JSON array of line items.
    
    SCHEMA RULES:
    - **Product**: Full description.
    - **Pack**: Pack Size if visible (e.g. "1x10", "10's", "10T").
    - **Qty**: Numeric (Float). Billed Quantity.
      - **Aliases**: Look for "Billed", "Sales Qty", "Strips", "Tabs", "Packs", "Quantity".
      - **Split**: If column is "10+2", use 10.
      - **Multi-Column**: If text is "0 0 2" or "0 2", extract the NON-ZERO number (e.g. 2).
      - **Fractional**: If you see "1.84" or "0.92", ROUND IT to the nearest integer/whole pack (e.g. 1.84 -> 2, 0.92 -> 1).
    - **Batch**: Alphanumeric Batch Number. 
      - **Look for aliases**: "Pcode", "Code", "Lot". 
      - **Extraction**: If a column has "Pcode: 808..." extract that as Batch.
    - **Expiry**: Text date (MM/YY or DD/MM/YY).
      - **CRITICAL**: Do NOT put a 4-8 digit HSN code (e.g. 3004, 30049099) here.
      - If you see an integer like "3004" or "30043110", put it in HSN, NOT Expiry.
    - **HSN**: Numeric HSN code (4-8 digits).
    - **Rate**: Unit Price.
    - **Rate**: Unit Price.
      - **CRITICAL**: Watch for faint decimal points. "16000" is likely "160.00".
      - "12345" is likely "123.45".
    - **Amount**: Net Total (Inclusive of Tax).
      - **CRITICAL**: Watch for faint decimal points.
      - **Consistency**: Ideally `Qty * Rate` ~= `Amount`. If `Amount` is wildly different, check if you missed a decimal in Rate or Amount.
      - **Selection**: If "Total" and "Amount" both exist, prefer "Amount" (usually strict final). Avoid "Total" if it looks like Gross/MRP-based.
    - **MRP**: Max Retail Price.
    
    CRITICAL:
    1. **Merges**: DO NOT merge distinct products. "Vaporub 5gm" and "Vaporub 10gm" are DIFFERENT.
    2. **DUPLICATES**: If the raw text lists the SAME product twice (e.g. "Dolo 650" appears on two lines), CREATE TWO JSON OBJECTS. Do NOT merge them into one. Keep them separate.
    3. **Noise**: Ignore header rows (e.g. "Description | Qty").
    4. **Schemes**: Keep "Offer" / "Free" rows if they are separate line items.
    

    {cheat_sheet}
    
    SYSTEM MEMORY (PREVIOUS MISTAKES TO AVOID):
    {memory_rules}
    
    Output JSON format:
    {{
        "line_items": [
            {{
                "Product": "str",
                "Pack": "str",
                "Qty": float,
                "Batch": "str",
                "Expiry": "str",
                "HSN": "str",
                "MRP": float,
                "Rate": float,
                "Amount": float
            }}
        ]
    }}
    """
    
    try:
        response = model.generate_content(prompt)
        text = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(text)
        
        mapped_items = data.get("line_items", [])
        logger.info(f"Mapper: Successfully mapped {len(mapped_items)} items.")
        
        return {"line_item_fragments": mapped_items}
        
    except Exception as e:
        logger.error(f"Mapper Error: {e}")
        return {"error_logs": [f"Mapper Failed: {e}"]}
