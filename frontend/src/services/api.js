import axios from 'axios';

const API_BASE_URL = window.location.hostname === 'localhost' ? 'http://localhost:8000' : 'http://' + window.location.hostname + ':8000';

const api = axios.create({
    baseURL: API_BASE_URL,
});

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

export const exportInvoice = async (data) => {
    const response = await api.post('/export-excel', data, {
        responseType: 'blob', // Important for binary file download
    });
    return response.data;
};

export default {
    analyzeInvoice,
    ingestInvoice,
    exportInvoice,
};
