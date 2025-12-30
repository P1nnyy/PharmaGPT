import express from 'express';
import cors from 'cors';
import { config } from './config/env.js';
import { initDriver } from './database/connection.js';
import invoiceRoutes from './routes/invoices.js';
import logger from './utils/logger.js';

const app = express();

// Middleware
app.use(cors());
app.use(express.json());

// Routes
app.use('/invoices', invoiceRoutes); // Legacy path might be /api/v1... check frontend?
// Frontend calls `${API_BASE_URL}/analyze-invoice` typically.
// Let's check python `server.py`. Python maps `@app.post("/analyze-invoice")`.
// My route is `/invoices/analyze`.
// To match Python API exactly for Frontend compatibility:
const exactCompatRouter = express.Router();

import multer from 'multer';
import { runExtractionPipeline } from './workflow/graph.js';
import { ingestInvoice } from './database/invoices.js';
import { getDriver } from './database/connection.js';
import path from 'path';

const upload = multer({ dest: 'uploads/' });

// Direct Route for compatibility with Frontend
exactCompatRouter.post('/analyze-invoice', upload.single('file'), async (req, res) => {
    console.log("Analyzing...");
    if (!req.file) return res.status(400).json({ error: 'No file uploaded' });
    try {
        const imagePath = path.resolve(req.file.path);
        const result = await runExtractionPipeline(imagePath);

        // Wrap output in { invoice, line_items } if that's what frontend expects?
        // Python returns `final_output` directly (which has Line_Items).

        // Ingestion
        await ingestInvoice(getDriver(), { ...result, Invoice_No: result.Invoice_No || "Unknown" }, result.Line_Items, imagePath);

        res.json(result);
    } catch (e) {
        logger.error(e);
        res.status(500).json({ error: e.message });
    }
});
exactCompatRouter.get('/activity-log', async (req, res) => {
    const logs = await import('./database/invoices.js').then(m => m.getRecentActivity(getDriver()));
    res.json(logs);
});

// App Config
app.use('/', exactCompatRouter); // Root Level for "/analyze-invoice" compatibility

// Start
const start = async () => {
    await initDriver();
    app.listen(config.PORT, () => {
        logger.info(`Node.js Server running on port ${config.PORT}`);
    });
};

start();
