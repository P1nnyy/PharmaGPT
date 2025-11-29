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

## 📝 Recent Changes (Refactor v2.1)
- **Product Definition Module**: Added a comprehensive "Product Master" form with Glassmorphic UI.
- **Universal Pharmacy Logic**: Implemented dynamic inventory modeling:
    - **Mode A (Divisible)**: Tablets/Capsules with variable conversion (e.g., 1 Strip = 10 Tabs).
    - **Mode B (Whole)**: Syrups/Creams/Powders with fixed conversion (1 Unit).
    - **Mode C (Hybrid)**: Injections with variable conversion (e.g., 1 Box = 5 Vials).
- **Auto-Learn UI**: Integrated "New Product" detection in the bill scanning workflow.
- **Catalog View**: Added a dedicated Catalog management tab in the sidebar.
- **Feature Pruning**: Removed legacy CRM and complex sales tabs to focus on core inventory speed.
- **UI Overhaul**: Implemented `glass_styles.css` and a new React frontend.
- **Schema Upgrade**: Enhanced Neo4j schema for better product-molecule relationships.
