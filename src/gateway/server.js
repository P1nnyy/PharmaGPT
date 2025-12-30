const express = require('express');
const multer = require('multer');
const axios = require('axios');
const path = require('path');
const cors = require('cors');
const fs = require('fs');
require('dotenv').config({ path: path.join(__dirname, '../../.env') });

const app = express();
const PORT = process.env.PORT || 8000;
const PYTHON_SERVICE_URL = process.env.PYTHON_SERVICE_URL || 'http://127.0.0.1:5000';

// --- Middleware ---
app.use(cors({ origin: '*' })); // Allow all origins for dev
app.use(express.json());

// --- File Upload Setup ---
// Configure Multer to save to 'uploads/' directly (sharing volume with Python)
const uploadDir = path.join(__dirname, '../../uploads/invoices');
if (!fs.existsSync(uploadDir)) {
    fs.mkdirSync(uploadDir, { recursive: true });
}

const storage = multer.diskStorage({
    destination: (req, file, cb) => {
        cb(null, uploadDir);
    },
    filename: (req, file, cb) => {
        // Keep original extension, add UUID-like prefix if needed, but for now 
        // we'll rely on the existing logic or simple timestamp
        const uniqueSuffix = Date.now() + '-' + Math.round(Math.random() * 1E9);
        const ext = path.extname(file.originalname);
        cb(null, uniqueSuffix + ext);
    }
});

const upload = multer({ storage: storage });

// --- Static Files ---
// Serve 'uploads' directory at /static to match previous Python behavior
app.use('/static', express.static(path.join(__dirname, '../../uploads')));

// --- Routes ---

/**
 * Health Check
 */
app.get('/', (req, res) => {
    res.json({ status: 'ok', service: 'Node.js Gateway' });
});

/**
 * Endpoint: /analyze-invoice
 * Receives file from Frontend -> Saves to Disk -> Calls Python Service
 */
app.post('/analyze-invoice', upload.single('file'), async (req, res) => {
    try {
        if (!req.file) {
            return res.status(400).json({ error: 'No file uploaded' });
        }

        const filePath = req.file.path; // Absolute path on disk
        console.log(`[Node] Received File: ${filePath}`);

        // Call Python Service
        // We act as a proxy. Since Python expects a file upload, we can re-stream it
        // Or, since they share the disk, we can just send the PATH.
        // However, the existing Python /analyze-invoice expects multipart/form-data.
        // To minimize Python changes, let's re-stream the file.

        const formData = new FormData();
        const fileStream = fs.createReadStream(filePath);

        // Note: In Node, FormData requires special handling or us of 'form-data' package
        // But since we are using 'axios', we can just pass the stream if we import 'form-data'
        // Let's use the 'form-data' library which usually comes with axios or needs install. 
        // Wait, 'axios' can handle streams but needs 'form-data' lib for multipart.

        // Simpler approach for Hybrid: Modify Python to accept a file PATH?
        // Or just install 'form-data'. 
        // Let's try to pass the file stream.

        // Actually, to avoid "form-data" dependency valid issues, let's try just piping the request?
        // No, 'multer' already consumed the stream. We have the file on disk.

        // Let's use 'form-data' package logic (we might need to install it if axios doesn't bundle it, usually better to install).
        // Since I didn't install 'form-data' explicitly (only express multer axios), I'll try to rely on 'axios' auto handling or fallback to installing it.
        // Actually, let's just make the Python endpoint accept a 'file_path' text field OR a file.
        // BUT, for minimal friction, I will execute a direct POST using 'form-data' package which is standard.
        // I'll assume I need to install 'form-data' -> I should do that.

        // TEMPORARY: I'll try to just install 'form-data' now to be safe.
        // For now, I'll write this file assuming I have it.

        const FormData = require('form-data');
        const form = new FormData();
        form.append('file', fs.createReadStream(filePath));

        const pythonResponse = await axios.post(`${PYTHON_SERVICE_URL}/analyze-invoice`, form, {
            headers: {
                ...form.getHeaders()
            },
            maxBodyLength: Infinity,
            maxContentLength: Infinity
        });

        // Return Python's response to Frontend
        res.json(pythonResponse.data);

    } catch (error) {
        console.error('[Node] Error communicating with Python:', error.message);
        if (error.response) {
            return res.status(error.response.status).json(error.response.data);
        }
        res.status(500).json({ error: 'Internal Gateway Error', details: error.message });
    }
});

/**
 * Proxy All Other Requests (Activity Log, Confirm, Reports)
 * We can catch-all and forward.
 */
app.use(async (req, res) => {
    // Skip static/uploads which are handled above
    if (req.path.startsWith('/static')) return;

    try {
        const url = `${PYTHON_SERVICE_URL}${req.originalUrl}`;
        console.log(`[Node] Proxying ${req.method} ${url}`);

        const config = {
            method: req.method,
            url: url,
            headers: { ...req.headers, host: 'localhost:5000' }, // Reset host
            data: req.body
        };

        // Remove content-length/type if strictly proxying (axios handles it)
        // But for getting JSON bodies, express.json() consumed it.
        // If it's a GET, data is underfined.

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
