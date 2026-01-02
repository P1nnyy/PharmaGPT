import express from 'express';
import multer from 'multer';
import axios from 'axios';
import path from 'path';
import cors from 'cors';
import fs from 'fs';
import { fileURLToPath } from 'url';
import FormData from 'form-data';
import dotenv from 'dotenv'; // need to import dotenv

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Load env vars
dotenv.config({ path: path.join(__dirname, '../../.env') });

const app = express();
const PORT = process.env.PORT || 8000;
// We will use 5001 if 5000 is taken (waiting for lsof result, but safer to assume 5001)
const PYTHON_SERVICE_URL = process.env.PYTHON_SERVICE_URL || 'http://127.0.0.1:5001';

// --- Middleware ---
app.use(cors({ origin: '*' }));
app.use(express.json());

// --- File Upload Setup ---
const uploadDir = path.join(__dirname, '../../uploads/invoices');
if (!fs.existsSync(uploadDir)) {
    fs.mkdirSync(uploadDir, { recursive: true });
}

const storage = multer.diskStorage({
    destination: (req, file, cb) => {
        cb(null, uploadDir);
    },
    filename: (req, file, cb) => {
        const uniqueSuffix = Date.now() + '-' + Math.round(Math.random() * 1E9);
        const ext = path.extname(file.originalname);
        cb(null, uniqueSuffix + ext);
    }
});

const upload = multer({ storage: storage });

// --- Static Files ---
app.use('/static', express.static(path.join(__dirname, '../../uploads')));

// --- Routes ---
app.get('/', (req, res) => {
    res.json({ status: 'ok', service: 'Node.js Gateway' });
});

app.post('/analyze-invoice', upload.single('file'), async (req, res) => {
    try {
        if (!req.file) {
            return res.status(400).json({ error: 'No file uploaded' });
        }

        const filePath = req.file.path;
        console.log(`[Node] Received File: ${filePath}`);

        const form = new FormData();
        form.append('file', fs.createReadStream(filePath));

        const pythonResponse = await axios.post(`${PYTHON_SERVICE_URL}/analyze-invoice`, form, {
            headers: {
                ...form.getHeaders(),
                Authorization: req.headers.authorization // Forward Auth Token
            },
            maxBodyLength: Infinity,
            maxContentLength: Infinity
        });

        res.json(pythonResponse.data);

    } catch (error) {
        console.error('[Node] Error communicating with Python:', error.message);
        if (error.response) {
            return res.status(error.response.status).json(error.response.data);
        }
        res.status(500).json({ error: 'Internal Gateway Error', details: error.message });
    }
});

// Proxy Catch-All
app.use(async (req, res) => {
    if (req.path.startsWith('/static')) return;

    try {
        const url = `${PYTHON_SERVICE_URL}${req.originalUrl}`;
        console.log(`[Node] Proxying ${req.method} ${url}`);

        const config = {
            method: req.method,
            url: url,
            headers: { ...req.headers, host: `localhost:5001` }, // Update host check
            data: req.body
        };

        const response = await axios(config);
        res.status(response.status).json(response.data);
    } catch (error) {
        if (error.response) {
            res.status(error.response.status).json(error.response.data);
        } else {
            console.error(`[Node] Proxy Error: ${error.message}`);
            res.status(502).json({ error: 'Bad Gateway - Python Service Unavailable' });
        }
    }
});

app.listen(PORT, () => {
    console.log(`Gateway running on port ${PORT}`);
    console.log(`Proxying to Python Service at ${PYTHON_SERVICE_URL}`);
});
