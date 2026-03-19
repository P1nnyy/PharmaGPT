import React, { createContext, useContext, useState, useEffect, useMemo, useCallback } from 'react';
import { analyzeInvoice, saveInvoice, getUserProfile, setAuthToken, getDrafts, clearDrafts as apiClearDrafts, discardInvoice as apiDiscardInvoice } from '../services/api';

const InvoiceContext = createContext();

export const useInvoice = () => {
    const context = useContext(InvoiceContext);
    if (!context) {
        throw new Error('useInvoice must be used within an InvoiceProvider');
    }
    return context;
};

export const InvoiceProvider = ({ children }) => {
    const [fileQueue, setFileQueue] = useState([]);
    const [selectedQueueId, setSelectedQueueId] = useState(null);
    const [recentlySavedIds, setRecentlySavedIds] = useState(new Set());
    const [isSaving, setIsSaving] = useState(false);
    const [user, setUser] = useState(null);
    const [isLoadingAuth, setIsLoadingAuth] = useState(true);
    const [toast, setToast] = useState({ show: false, message: '', type: 'success' });

    const showToast = useCallback((message, type = 'success') => {
        setToast({ show: true, message, type });
        setTimeout(() => setToast({ show: false, message: '', type: 'success' }), 3000);
    }, []);

    const isAnalyzing = useMemo(() => fileQueue.some(f => f.status === 'processing'), [fileQueue]);

    const activeQueueItem = useMemo(() => 
        fileQueue.find(item => item.id === selectedQueueId) || fileQueue[0],
    [fileQueue, selectedQueueId]);

    const runAnalysis = useCallback(async (filesToProcess) => {
        try {
            const files = filesToProcess.map(item => item.file);
            const { uploadBatchInvoices } = await import('../services/api');
            const placeholders = await uploadBatchInvoices(files);

            setFileQueue(prev => {
                return placeholders.map(p => {
                    const localItem = prev.find(item => item.file?.name === p.file?.name);
                    return {
                        ...p,
                        previewUrl: p.previewUrl || localItem?.previewUrl
                    };
                });
            });
        } catch (err) {
            console.error("Upload Failed", err);
            showToast("Batch Upload Failed", "error");
        }
    }, [showToast]);

    const handleFileChange = useCallback(async (e) => {
        const selectedFiles = e.target.files ? Array.from(e.target.files) : [];
        if (selectedFiles.length === 0) return;

        const tempQueue = selectedFiles.map(f => ({
            id: "temp-" + Math.random().toString(36),
            file: f,
            status: 'processing',
            previewUrl: URL.createObjectURL(f),
            result: null
        }));

        setFileQueue(tempQueue);
        await runAnalysis(tempQueue);
    }, [runAnalysis]);

    const handleReset = useCallback(async () => {
        try {
            await getDrafts(); // Just dummy check
            await apiClearDrafts();
            setFileQueue([]);
            setSelectedQueueId(null);
            showToast("All drafts cleared.", "success");
        } catch (error) {
            console.error("Failed to clear drafts:", error);
            showToast("Failed to clear drafts", "error");
        }
    }, [showToast]);

    const handleDiscard = useCallback(async (invoiceId) => {
        try {
            await apiDiscardInvoice(invoiceId);
            setFileQueue(prev => {
                const next = prev.filter(item => item.id !== invoiceId);
                if (selectedQueueId === invoiceId && next.length > 0) {
                    setSelectedQueueId(next[0].id);
                } else if (next.length === 0) {
                    setSelectedQueueId(null);
                }
                return next;
            });
        } catch (error) {
            console.error("Failed to discard invoice:", error);
            showToast("Failed to discard invoice", "error");
        }
    }, [selectedQueueId, showToast]);

    const handleHeaderChange = useCallback((field, value) => {
        setFileQueue(prev => prev.map(item => {
            if (item.id === selectedQueueId) {
                const newResult = { ...item.result };
                const newInvoiceData = { ...newResult.invoice_data };

                if (field.startsWith('supplier_details.')) {
                    const key = field.split('.')[1];
                    newInvoiceData.supplier_details = {
                        ...newInvoiceData.supplier_details,
                        [key]: value
                    };
                } else {
                    newInvoiceData[field] = value;
                }

                newResult.invoice_data = newInvoiceData;
                return { ...item, result: newResult };
            }
            return item;
        }));
    }, [selectedQueueId]);

    const handleLineItemChange = useCallback((index, field, value) => {
        setFileQueue(prev => prev.map(item => {
            if (item.id === selectedQueueId) {
                const newResult = { ...item.result };
                const newItems = [...newResult.normalized_items];
                newItems[index] = { ...newItems[index], [field]: value };
                newResult.normalized_items = newItems;
                return { ...item, result: newResult };
            }
            return item;
        }));
    }, [selectedQueueId]);

    const handleSaveInvoice = useCallback(async () => {
        if (!activeQueueItem?.result?.invoice_data) return;
        setIsSaving(true);

        try {
            const payload = {
                invoice_data: {
                    ...activeQueueItem.result.invoice_data,
                    id: selectedQueueId,
                },
                normalized_items: activeQueueItem.result.normalized_items,
                image_path: activeQueueItem.result.image_path
            };

            await saveInvoice(payload);
            showToast("Invoice Saved Successfully!", "success");

            setRecentlySavedIds(prev => new Set(prev).add(selectedQueueId));

            setFileQueue(prev => {
                const next = prev.filter(item => item.id !== selectedQueueId);
                if (next.length === 0) {
                    setSelectedQueueId(null);
                } else {
                    setSelectedQueueId(next[0].id);
                }
                return next;
            });
        } catch (err) {
            console.error(err);
            showToast("Failed to save invoice. " + (err.response?.data?.detail || err.message), "error");
        } finally {
            setIsSaving(false);
        }
    }, [activeQueueItem, selectedQueueId, showToast]);

    const value = {
        fileQueue,
        setFileQueue,
        selectedQueueId,
        setSelectedQueueId,
        activeQueueItem,
        isAnalyzing,
        isSaving,
        setIsSaving,
        user,
        setUser,
        isLoadingAuth,
        setIsLoadingAuth,
        toast,
        showToast,
        handleFileChange,
        handleReset,
        handleDiscard,
        handleHeaderChange,
        handleLineItemChange,
        handleSaveInvoice,
        recentlySavedIds,
        setRecentlySavedIds
    };

    return (
        <InvoiceContext.Provider value={value}>
            {children}
        </InvoiceContext.Provider>
    );
};
