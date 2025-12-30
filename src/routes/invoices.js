import express from 'express';
import multer from 'multer';
import path from 'path';
import { runExtractionPipeline } from '../workflow/graph.js';
import { ingestInvoice, getRecentActivity } from '../database/invoices.js';
import { getDriver } from '../database/connection.js';
import logger from '../utils/logger.js';

const router = express.Router();
const upload = multer({ dest: 'uploads/' });

// POST /invoices/analyze
router.post('/analyze', upload.single('file'), async (req, res) => {
    if (!req.file) return res.status(400).json({ error: 'No file uploaded' });

    try {
        const imagePath = path.resolve(req.file.path);
        logger.info(`Received analysis request for ${imagePath}`);

        // 1. Run Extraction Graph
        const result = await runExtractionPipeline(imagePath);

        if (!result) {
            return res.status(500).json({ error: 'Extraction failed to produce output.' });
        }

        // 2. Ingest to DB (Fire and Forget or Await?)
        // Let's await to confirm save
        try {
            await ingestInvoice(getDriver(), result.metadata ? { ...result, metadata: result.metadata } : result, result.Line_Items, imagePath);
        } catch (dbErr) {
            logger.error(`DB Ingestion failed: ${dbErr}`);
            // Return result anyway, but warn
        }

        res.json(result);

    } catch (error) {
        logger.error(`Analysis Route Error: ${error}`);
        res.status(500).json({ error: error.message });
    }
});

// GET /invoices/activity-log
router.get('/activity-log', async (req, res) => {
    try {
        const logs = await getRecentActivity(getDriver());
        res.json(logs);
    } catch (e) {
        res.status(500).json({ error: e.message });
    }
});

export default router;
