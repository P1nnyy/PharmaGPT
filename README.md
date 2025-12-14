# PharmaCouncil Invoice Extraction System 🏥

## Overview
The **PharmaCouncil Invoice Extraction System** is an advanced detailed-oriented document processing pipeline designed specifically for the complex and noisy format of pharmaceutical invoices. Unlike unexpected OCR tools, this system employs a **Swarm Architecture** of specialized AI agents to ensure financial accuracy, utilizing a **Self-Correcting Feedback Loop** to reconcile line-item data against the invoice's grand total.

## Architecture: The Swarm 🐝

The system is built on a Directed Acyclic Graph (DAG) workflow (using LangGraph) where multiple specialized nodes collaborate to process a single document.

### 1. Surveyor Node
- **Role**: The Architect.
- **Function**: Scans the document to identify layout zones (Header, Footer, Main Table, Tax Breakdown). Isolate specific coordinates for downstream workers.

### 2. Worker Node (The Anchor)
- **Role**: The Extractor.
- **Function**: Executes parallel extraction tasks on identified zones.
- **Critical Logic**: Captures the **"Stated Grand Total"** as the immutable Anchor of Truth.

### 3. Auditor Node
- **Role**: The Deduplicator.
- **Function**: Merges parallel extraction fragments, filters noise (e.g., repeating sub-headers), and ensures schema compliance.

### 4. Critic Node (The Logic Engine)
- **Role**: The Judge.
- **Function**: Performs a ratio analysis: `Grand Total / Sum(Line Items)`.
    - **Verdict: APPROVE**: Exact match (< 1% variance).
    - **Verdict: APPLY_MARKUP**: Ratio > 1.0 (Implies Tax Exclusive lines or Freight addition).
    - **Verdict: APPLY_MARKDOWN**: Ratio < 1.0 (Implies Global Discount).
    - **Verdict: RETRY_OCR**: Massive mismatch (> 30%).

### 5. Solver Node (Mathematics)
- **Role**: The Fixer.
- **Function**: Applies the `correction_factor` derived by the Critic. Mathematically adjusts `Net_Line_Amount` and recalculates the `Landed_Cost_Per_Unit` to ensure the final data is 100% accurate to the penny.

---

## Technology Stack

- **Backend**: Python 3.11+, FastAPI, Uvicorn
- **AI/LLM**: Google Gemini 2.0 Flash (Vision)
- **Workflow**: LangGraph (StateGraph)
- **Database**: Neo4j (Graph Database) for inventory and tracking.
- **Frontend**: React, Vite, TailwindCSS (Dark Mode SaaS UI)

---

## Setup & Installation

### 1. Prerequisites
- Python 3.10+
- Node.js & npm
- Neo4j Database (Local or Aura)
- Google Cloud API Key (Gemini)

### 2. Environment Variables
Create a `.env` file in the root directory:
```bash
GOOGLE_API_KEY=your_gemini_key
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
```

### 3. Installation

**Backend:**
```bash
# Create Virtual Environment
python3 -m venv .venv
source .venv/bin/activate

# Install Dependencies
pip install -r requirements.txt
```

**Frontend:**
```bash
cd frontend
npm install
```

---

## Running the Application

### Start the Backend
```bash
# From project root
source .venv/bin/activate
uvicorn src.api.server:app --reload
```
API Documentation available at: `http://localhost:8000/docs`

### Start the Frontend
```bash
# From frontend directory
npm run dev
```
UI available at: `http://localhost:5173`

---

## Key Features

- **Reconciliation Engine**: Automatically detects if an invoice is "Tax Inclusive" or "Tax Exclusive" and normalizes the data.
- **Global Table Persistence**: Stores extracted `Expiry Date`, `Batch No`, `MRP`, and `Landed Cost` into the Graph for inventory valuation.
- **Draft & Staging**: Invoices can be saved as 'DRAFT' allowing for partial extraction and manual review before committing to inventory.
- **Excel Export**: Download reconciled data directly to Excel for manual ERP upload.

## License
Proprietary.
