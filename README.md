# Invoice Extractor 🧾

Yo! Welcome to the Invoice Extractor. 

This is a little tool I built to solve a big headache: messy pharmaceutical invoices. You know the deal — every supplier has their own weird format, column names make no sense, and "Dolo" could mean five different things.

So, I built this thing to take that chaos and turn it into clean, structured data in a Neo4j graph database.

## What it actually does

1.  **Ingests weird JSON**: Takes the raw output from an invoice OCR (like Google Document AI) and accepts it via an API.
2.  **Normalizes everything**: It uses some "Universal Pharmacy Logic" to figure out that "Augmentin 625" and "Augmentin Duo" are basically the same thing. It also handles the math (Cost Price, GST, etc.) so you don't have to.
3.  **Graphs it**: Dumps everything into Neo4j so we can track products and prices over time.
4.  **Shows you the proof**: Has a simple "Clean Invoice" report page where you can see what the code *thought* the invoice said versus the standardized version.

## How to run this bad boy

Make sure you have your `.env` file set up with your Neo4j credentials first!

```bash
# Install the goods
pip install -r requirements.txt

# Fire up the server
uvicorn src.api.server:app --reload
```

Then hit up `http://localhost:8000/docs` to play with the API, or throw some JSON at `/process-invoice`.

Happy extracting! 🚀
