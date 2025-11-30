# PharmaGPT v2: AI-Powered Pharmacy Agent

PharmaGPT is a high-speed, "Apple Glass" style AI Agent designed for modern pharmacies. It pivots from a generic ERP to a focused tool for **Bill Scanning (Ingestion)** and **Inventory Search (Retrieval)**.

## 🚀 Key Features

### 1. 💎 "Apple Glass" UI
- **Aesthetics**: Deep, organic dark mode with glassmorphism effects (translucent cards, blur filters).
- **Experience**: Minimalist interface focused on a central "Spotlight-style" search bar for the AI agent.

### 2. 🧠 Agentic Ingestion Pipeline
- **Vision Agent**: Powered by Gemini Vision to extract structured data from bill images (PDF/PNG).
- **Workflow**: Upload Bill -> Extract JSON -> Verify in Grid -> Commit to Neo4j.
- **Atomic Sizing**: Inventory is managed at the atomic level (Total Atoms = Packs * PackSize + Loose) for precise tracking.

### 3. 🔍 Intelligent Retrieval
- **Graph Search**: Robust inventory lookup using Neo4j graph traversals.
- **Natural Language Querying**: Ask the agent questions about stock, location, and substitutes.

## 🛠️ Tech Stack

- **Frontend**: React, Vite, TailwindCSS (Glassmorphism styles)
- **Backend**: Python (Flask/FastAPI), Neo4j (Graph Database)
- **AI/ML**: Gemini Pro Vision (Bill Extraction), LLM Agents
- **State Management**: Atomic inventory states (Sealed vs. Open packs)

## 📂 Project Structure

- `frontend/`: React/Vite application source code.
- `backend_server.py`: Main backend server entry point.
- `shop_manager.py`: Core business logic and Neo4j interactions.
- `agent.py`: AI Agent logic for handling user queries.
- `vision_agent.py`: Vision model integration for bill scanning.
- `glass_styles.css`: Core CSS definitions for the glassmorphism design.

## 🏁 Getting Started

1.  **Backend**:
    ```bash
    source venv/bin/activate
    python backend_server.py
    ```

2.  **Frontend**:
    ```bash
    cd frontend
    npm install
    npm run dev
    ```

## 📝 Recent Changes (Refactor v2.2 - Smart Ingestion)
- **Smart Ingestion**:
    - **Duplicate Detection**: Automatically detects if a bill has already been uploaded (based on Supplier + Invoice No).
    - **Merge Workflow**: Interactive UI to review and merge duplicate bills into existing inventory without double-counting.
- **Golden Record Identity**:
    - Products are now uniquely identified by **Name + Pack Size** (e.g., "Dolo 650" 1x15 is distinct from "Dolo 650" 1x10).
    - Prevents inventory corruption from different pack sizes of the same medicine.
- **Enhanced Vision Agent**:
    - **Batch & Pack Extraction**: Improved heuristics to extract Batch Numbers (including "PCode" fallbacks) and Pack Sizes (from product names) when columns are missing.
    - **Data Normalization**: Automatic normalization of unit types (e.g., "Tabs" -> "Tablet", "Syp" -> "Syrup").
- **Universal Pharmacy Logic**:
    - **Mode A (Divisible)**: Tablets/Capsules with variable conversion.
    - **Mode B (Whole)**: Syrups/Creams with fixed conversion.
    - **Mode C (Hybrid)**: Injections with variable conversion.
- **UI Overhaul**:
    - **Glassmorphism**: Deep dark mode with translucent cards.
    - **Inventory Grid**: Improved readability and sorting.
