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

const setAuthToken = (token) => {
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

const getUserProfile = async () => {
    const response = await api.get('/auth/me');
    return response.data;
};

const analyzeInvoice = async (files) => {
    // Legacy Wrapper for backward compatibility (if needed)
    // Or just redirect to the new batch logic if the UI keeps calling this
    return uploadBatchInvoices(files);
};

const uploadBatchInvoicesFormData = async (formData) => {
    const response = await api.post('/invoices/batch-upload', formData);
    return response.data; // List of placeholders {id, temp_id, status, previewUrl...}
};

const getDrafts = async () => {
    const response = await api.get('/invoices/drafts');
    return response.data;
};

const clearDrafts = async () => {
    const response = await api.delete('/invoices/drafts');
    return response.data;
};

const discardInvoice = async (invoiceId, wipe = false) => {
    const url = `/invoices/${invoiceId}${wipe ? '?wipe=true' : ''}`;
    const response = await api.delete(url);
    return response.data;
};

const ingestInvoice = async (data) => {
    // data should match the ConfirmInvoiceRequest structure:
    // { invoice_data: {...}, normalized_items: [...] }
    // normalizes items: [...] }
    const response = await api.post('/invoices/confirm', data);
    return response.data;
};

const saveInvoice = ingestInvoice;

const exportInvoice = async (data) => {
    const response = await api.post('/export-excel', data, {
        responseType: 'blob', // Important for binary file download
    });
    return response.data;
};

// Direct Auth URL (Bypassing Gateway for Redirects)
const AUTH_LOGIN_URL = API_BASE_URL + "/auth/google/login";

const getActivityLog = async () => {
    const response = await api.get('/activity-log');
    return response.data;
};

const getInvoiceHistory = async () => {
    const response = await api.get('/history');
    return response.data;
};

const getInvoiceDetails = async (invoiceNumber) => {
    const encodedId = encodeURIComponent(invoiceNumber);
    const response = await api.get(`/invoices/${encodedId}/items`);
    return response.data;
};

const getInventory = async () => {
    const response = await api.get('/inventory');
    return response.data;
};

const searchProducts = async (query) => {
    const response = await api.get(`/products/search?q=${encodeURIComponent(query)}`);
    return response.data;
};

const getReviewQueue = async () => {
    const response = await api.get('/products/review-queue');
    return response.data;
};

const saveProduct = async (productData) => {
    const response = await api.post('/products/', productData);
    return response.data;
};

const renameProduct = async (oldName, newName) => {
    const response = await api.post(`/products/rename?name=${encodeURIComponent(oldName)}`, { new_name: newName });
    return response.data;
};

const linkProductAlias = async (masterName, alias) => {
    console.log("Calling linkProductAlias", masterName, alias);
    const response = await api.post(`/products/alias?name=${encodeURIComponent(masterName)}`, { alias });
    return response.data;
};

const getAllProducts = async () => {
    const response = await api.get('/products/all');
    return response.data;
};

const getProductHistory = async (name) => {
    const response = await api.get(`/products/history?name=${encodeURIComponent(name)}`);
    return response.data;
};

const submitFeedback = async (traceId, score, comment = null) => {
    const response = await api.post('/feedback', { trace_id: traceId, score, comment });
    return response.data;
};

const enrichProduct = async (productName, packSize = null) => {
    let url = `/products/enrich?q=${encodeURIComponent(productName)}`;
    if (packSize) {
        url += `&pack_size=${encodeURIComponent(packSize)}`;
    }
    const response = await api.get(url);
    return response.data;
};

// --- Config / Admin API ---
const getCategories = async () => {
    const response = await api.get('/config/categories');
    return response.data;
}

const updateCategoryConfig = async (name, configUpdates) => {
    const response = await api.put(`/config/categories/${encodeURIComponent(name)}/config`, configUpdates);
    return response.data;
}

const createCategory = async (name, base_unit, supports_atomic = false, description = '') => {
    const response = await api.post('/config/categories', { name, base_unit, supports_atomic, description });
    return response.data;
}

const deleteCategory = async (name) => {
    const response = await api.delete(`/config/categories/${encodeURIComponent(name)}`);
    return response.data;
}

const getRoles = async () => {
    const response = await api.get('/config/roles');
    return response.data;
}

const createRole = async (name, permissions = []) => {
    const response = await api.post('/config/roles', { name, permissions });
    return response.data;
}

const assignRole = async (email, roleName) => {
    const response = await api.post('/config/users/assign-role', { email, role_name: roleName });
    return response.data;
}

// --- Invitations API ---
const getInvitations = async () => {
    const response = await api.get('/invitations/me');
    return response.data;
};

const createInvitation = async (email, role_name) => {
    const response = await api.post('/invitations/', { email, role_name });
    return response.data;
};

const acceptInvitation = async (invitationId) => {
    const response = await api.post(`/invitations/${invitationId}/accept`);
    return response.data;
};

export {
    getUserProfile,
    setAuthToken,
    analyzeInvoice,
    uploadBatchInvoicesFormData,
    getDrafts,
    clearDrafts,
    discardInvoice,
    ingestInvoice,
    saveInvoice,
    exportInvoice,
    AUTH_LOGIN_URL,
    getActivityLog,
    getInvoiceHistory,
    getInvoiceDetails,
    getInventory,
    searchProducts,
    getReviewQueue,
    saveProduct,
    renameProduct,
    linkProductAlias,
    getAllProducts,
    getProductHistory,
    submitFeedback,
    enrichProduct,
    getCategories,
    updateCategoryConfig,
    createCategory,
    deleteCategory,
    getRoles,
    createRole,
    assignRole,
    getInvitations,
    createInvitation,
    acceptInvitation
};

