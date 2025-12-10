# Invoice Extractor 🧾

Yo! Welcome to the Invoice Extractor. 

This is a little tool I built to solve a big headache: messy pharmaceutical invoices. You know the deal — every supplier has their own weird format, column names make no sense, and "Dolo" could mean five different things.

So, I built this thing to take that chaos and turn it into clean, structured data in a Neo4j graph database.

## The Secret Sauce 🌶️

1.  **Gemini 2.5 Flash**: We're using Google's latest model to read these docs. It's configured with a custom "Scan-and-Lock" prompt that finds the *real* product table and rigidly ignores summary boxes, footer noise, and promotional junk.
2.  **Smart Normalization**: It doesn't just read; it understands. It standardizes product names (e.g., mapping "Augmentin Duo" to a canonical ID), calculates costs per unit, and explicitly rounds everything to 2 decimal places so your database stays clean.
3.  **Batch & Tax Tracking**: We now track `Batch_No` and explicit `GST %` all the way from the image to the final report. No data left behind.
4.  **Graph Power**: Dumps everything into Neo4j so we can track price fluctuations and supplier history over time.
5.  **The "Clean Invoice" Report**: A simple HTML report lets you audit the extraction. It shows you the raw data next to the standardized values so you can trust (but verify).

## How to run this bad boy

### 1. Prerequisites
Make sure you have [Neo4j](https://neo4j.com/) running locally.

### 2. Configure Environment
Create a `.env` file in the project root. Don't skip this, or it won't work.

```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
GEMINI_API_KEY=your_gemini_vision_api_key
```

### 3. Install the goods
```bash
pip install -r requirements.txt
```

### 4. Fire up the server
```bash
uvicorn src.api.server:app --reload
```
Access the API docs at `http://0.0.0.0:8000/docs`.

---

## Testing the Logic 🧠

Want to see the agents in action without running the full API?

```bash
python tests/test_extraction_manual.py
```
This runs the extraction pipeline on a test image (or mock data if the image is missing) and prints the JSON output.

## API Usage

### POST /process-invoice
Upload an invoice image (JPEG/PNG) to extract data.
**Request:** `multipart/form-data` with key `file`.

**Response:** JSON object containing `status` and `normalized_data`.

### GET /report/{invoice_no}
View a human-readable HTML report of the processed invoice, complete with Batch numbers and tax breakdowns.

---

Happy extracting! 🚀
