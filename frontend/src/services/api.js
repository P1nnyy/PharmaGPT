import axios from 'axios';

const API_PORT = '5001';

// If VITE_API_BASE_URL is explicitly set, use it.
// Otherwise, default to relative path '' to leverage Vite Proxy (which forwards to Backend).
// This works for:
// 1. Tunnel (dev.pharmagpt.co) -> Proxy -> Backend
// 2. LAN (192.168.x.x:5173) -> Proxy -> Backend
// 3. Localhost (localhost:5173) -> Proxy -> Backend
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

const api = axios.create({
    baseURL: API_BASE_URL,
    timeout: 300000, // 5 minutes for batch analysis
});

// --- Auth Token Management ---
let authToken = localStorage.getItem('auth_token');

export const setAuthToken = (token) => {
    authToken = token;
    if (token) {
        localStorage.setItem('auth_token', token);
    } else {
        localStorage.removeItem('auth_token');
    }
};

// Add Interceptor to inject token
api.interceptors.request.use((config) => {
    if (authToken) {
        config.headers.Authorization = `Bearer ${authToken}`;
    }
    // Bypass LocalTunnel Warning Page
    config.headers['Bypass-Tunnel-Reminder'] = 'true';
    return config;
}, (error) => Promise.reject(error));

// --- API Functions ---

export const getUserProfile = async () => {
    const response = await api.get('/auth/me');
    return response.data;
};

export const analyzeInvoice = async (files) => {
    // Legacy Wrapper for backward compatibility (if needed)
    // Or just redirect to the new batch logic if the UI keeps calling this
    return uploadBatchInvoices(files);
};

export const uploadBatchInvoices = async (files) => {
    const formData = new FormData();
    const fileList = Array.isArray(files) ? files : [files];

    fileList.forEach(file => {
        formData.append('files', file);
    });

    // Calls the async endpoint
    const response = await api.post('/invoices/batch-upload', formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
    });
    return response.data; // List of placeholders {id, status, previewUrl...}
};

export const getDrafts = async () => {
    const response = await api.get('/invoices/drafts');
    return response.data;
};

export const clearDrafts = async () => {
    const response = await api.delete('/invoices/drafts');
    return response.data;
};

export const discardInvoice = async (invoiceId) => {
    const response = await api.delete(`/invoices/${invoiceId}`);
    return response.data;
};

export const ingestInvoice = async (data) => {
    // data should match the ConfirmInvoiceRequest structure:
    // { invoice_data: {...}, normalized_items: [...] }
    const response = await api.post('/confirm-invoice', data);
    return response.data;
};

export const saveInvoice = ingestInvoice;

export const exportInvoice = async (data) => {
    const response = await api.post('/export-excel', data, {
        responseType: 'blob', // Important for binary file download
    });
    return response.data;
};

// Direct Auth URL (Bypassing Gateway for Redirects)
export const AUTH_LOGIN_URL = API_BASE_URL + "/auth/google/login";

export const getActivityLog = async () => {
    const response = await api.get('/activity-log');
    return response.data;
};

export const getInvoiceHistory = async () => {
    const response = await api.get('/history');
    return response.data;
};

export const getInvoiceDetails = async (invoiceNumber) => {
    const encodedId = encodeURIComponent(invoiceNumber);
    const response = await api.get(`/invoices/${encodedId}/items`);
    return response.data;
};

export const getInventory = async () => {
    const response = await api.get('/inventory');
    return response.data;
};

export const searchProducts = async (query) => {
    const response = await api.get(`/products/search?q=${encodeURIComponent(query)}`);
    return response.data;
};

export const getReviewQueue = async () => {
    const response = await api.get('/products/review-queue');
    return response.data;
};

export const saveProduct = async (productData) => {
    const response = await api.post('/products/', productData);
    return response.data;
};

export const renameProduct = async (oldName, newName) => {
    const response = await api.post(`/products/rename?name=${encodeURIComponent(oldName)}`, { new_name: newName });
    return response.data;
};

export const linkProductAlias = async (masterName, alias) => {
    console.log("Calling linkProductAlias", masterName, alias);
    const response = await api.post(`/products/alias?name=${encodeURIComponent(masterName)}`, { alias });
    return response.data;
};

export const getAllProducts = async () => {
    const response = await api.get('/products/all');
    return response.data;
};

export const getProductHistory = async (name) => {
    const response = await api.get(`/products/history?name=${encodeURIComponent(name)}`);
    return response.data;
};

export const submitFeedback = async (traceId, score, comment = null) => {
    const response = await api.post('/feedback', { trace_id: traceId, score, comment });
    return response.data;
};

export default {
    analyzeInvoice,
    uploadBatchInvoices,
    getDrafts,
    clearDrafts,
    discardInvoice,
    ingestInvoice,
    exportInvoice,
    getUserProfile,
    setAuthToken,
    AUTH_LOGIN_URL,
    getActivityLog,
    getInvoiceHistory,
    getInvoiceDetails,
    getInventory,
    searchProducts,
    saveProduct,
    getAllProducts,
    getProductHistory,
    getReviewQueue,
    submitFeedback
};
