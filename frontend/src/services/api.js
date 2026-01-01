import axios from 'axios';

const API_BASE_URL = window.location.hostname === 'localhost'
    ? 'http://localhost:8000'
    : window.location.hostname.includes('pharmagpt.co')
        ? 'https://api.pharmagpt.co'
        : 'http://' + window.location.hostname + ':8000';

const api = axios.create({
    baseURL: API_BASE_URL,
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
    return config;
}, (error) => Promise.reject(error));

// --- API Functions ---

export const getUserProfile = async () => {
    const response = await api.get('/auth/me');
    return response.data;
};

export const analyzeInvoice = async (file) => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await api.post('/analyze-invoice', formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
    });
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
export const AUTH_LOGIN_URL = API_BASE_URL.replace(":8000", ":5001") + "/auth/google/login";

export const getActivityLog = async () => {
    const response = await api.get('/activity-log');
    return response.data;
};

export const getInvoiceHistory = async () => {
    const response = await api.get('/history');
    return response.data;
};

export const getInvoiceDetails = async (invoiceNumber) => {
    const response = await api.get(`/invoices/${invoiceNumber}/items`);
    return response.data;
};

export const getInventory = async () => {
    const response = await api.get('/inventory');
    return response.data;
};

export default {
    analyzeInvoice,
    ingestInvoice,
    exportInvoice,
    getUserProfile,
    setAuthToken,
    AUTH_LOGIN_URL,
    getActivityLog,
    getInvoiceHistory,
    getInvoiceDetails,
    getInventory
};
