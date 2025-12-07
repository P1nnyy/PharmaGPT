# Invoice Extractor 🧾

Yo! Welcome to the Invoice Extractor. 

This is a little tool I built to solve a big headache: messy pharmaceutical invoices. You know the deal — every supplier has their own weird format, column names make no sense, and "Dolo" could mean five different things.

So, I built this thing to take that chaos and turn it into clean, structured data in a Neo4j graph database.

## What it actually does

1.  **Ingests weird JSON**: Takes the raw output from an invoice OCR (like Google Document AI) and accepts it via an API.
2.  **Normalizes everything**: It uses some "Universal Pharmacy Logic" to figure out that "Augmentin 625" and "Augmentin Duo" are basically the same thing. It also handles the math (Cost Price, GST, etc.) so you don't have to.
3.  **Council of Agents Extraction**: Uses a multi-agent system (Supplier Identifier, Quantity/Description, Rate/Amount, Percentage) to vote on what the messy invoice text actually means.
4.  **Graphs it**: Dumps everything into Neo4j so we can track products and prices over time.
5.  **Shows you the proof**: Has a simple "Clean Invoice" report page where you can see what the code *thought* the invoice said versus the standardized version.

## How to run this bad boy

### 1. The Full Stack (Extraction + API)
Make sure you have your### 3. Configure Environment
Create a `.env` file in the project root:
```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
GEMINI_API_KEY=your_gemini_vision_api_key
```
(*Note: Without `GEMINI_API_KEY`, the system falls back to mock data.*)

### 4.To run the full backend:
```bash
python src/api/server.py
```
The extraction logic is sophisticated:
1.  **Contextual Financial Identification**: Distinguishes "Rate/Doz" from simple Unit Rate.
2.  **Net Amount Localization**: Spatially aware of the far-right column for totals.
3.  **Strict Quantity/Dosage Separation**: Avoids confusing "650" (mg) with 650 (qty).
4.  **GST Extraction**: Explicitly parsing tax percentages.
5.  **Multi-Agent Redundancy**: If Gemini misses a field, Heuristic Agents (e.g., regex-based) fill the gaps.

Access the API at `http://0.0.0.0:8000/docs`.

## API Usage

### POST /process-invoice
Upload an invoice image (JPEG/PNG) to extract data.
**Request:** `multipart/form-data` with key `file`.

**Response:** JSON object containing `status` and `normalized_data`.

### GET /report/{invoice_no}
View a human-readable HTML report of the processed invoice.
`.env` file set up with your Neo4j credentials first!

```bash
# Install the goods
pip install -r requirements.txt

# Fire up the server
uvicorn src.api.server:app --reload
```

### 2. Testing the Extraction Logic 🧠
You can run the extraction logic standalone to see the agents in action:

```bash
# Run the integration script
python tests/test_extraction_to_api.py
```

Make sure you have your `.env` file set up with your Neo4j credentials first!

```bash
# Install the goods
pip install -r requirements.txt

# Fire up the server
uvicorn src.api.server:app --reload
```

Then hit up `http://localhost:8000/docs` to play with the API, or throw some JSON at `/process-invoice`.

Happy extracting! 🚀
