import React, { createContext, useContext, useState, useEffect, useMemo, useCallback } from 'react';
import { analyzeInvoice, saveInvoice, getDrafts, clearDrafts as apiClearDrafts, discardInvoice as apiDiscardInvoice } from '../services/api';
import { useAuth } from './AuthContext';
import { useQueue } from './QueueContext';
import { useToast } from './ToastContext';

const InvoiceContext = createContext();

export const useInvoice = () => {
    const context = useContext(InvoiceContext);
    if (!context) {
        throw new Error('useInvoice must be used within an InvoiceProvider');
    }
    return context;
};

export const InvoiceProvider = ({ children }) => {
    const { user } = useAuth();
    const { 
        fileQueue, setFileQueue, 
        selectedQueueId, setSelectedQueueId, 
        recentlySavedIds, setRecentlySavedIds,
        isSaving, setIsSaving 
    } = useQueue();
    const { showToast } = useToast();

    const [lastClearedAt, setLastClearedAt] = useState(0);
    const lastClearedAtRef = React.useRef(0);
    const recentlySavedIdsRef = React.useRef(new Set());

    // Keep recentlySavedIdsRef in sync with context state for SSE
    useEffect(() => {
        recentlySavedIdsRef.current = recentlySavedIds;
    }, [recentlySavedIds]);

    const isAnalyzing = useMemo(() => fileQueue.some(f => f.status === 'processing'), [fileQueue]);

    const activeQueueItem = useMemo(() => 
        fileQueue.find(item => item.id === selectedQueueId) || fileQueue[0],
    [fileQueue, selectedQueueId]);

    const runAnalysis = useCallback(async (filesToProcess) => {
        try {
            const formData = new FormData();
            filesToProcess.forEach(item => {
                formData.append('files', item.file);
                formData.append('temp_ids', item.id);
            });
            
            const { uploadBatchInvoicesFormData } = await import('../services/api');
            const placeholders = await uploadBatchInvoicesFormData(formData);

            setFileQueue(prev => {
                return prev.map(item => {
                    const placeholder = placeholders.find(p => p.temp_id === item.id);
                    if (placeholder) {
                        return {
                            ...item,
                            id: placeholder.id,
                            status: placeholder.status,
                            previewUrl: placeholder.previewUrl || item.previewUrl
                        };
                    }
                    return item;
                });
            });
        } catch (err) {
            console.error("Upload Failed", err);
            showToast("Batch Upload Failed", "error");
        }
    }, [setFileQueue, showToast]);

    const handleFileChange = useCallback(async (e) => {
        const selectedFiles = e.target.files ? Array.from(e.target.files) : [];
        if (selectedFiles.length === 0) return;

        const tempQueue = selectedFiles.map(f => ({
            id: "temp-" + Math.random().toString(36),
            filename: f.name,
            file: f,
            status: 'processing',
            previewUrl: URL.createObjectURL(f),
            result: null
        }));

        setFileQueue(prev => [...prev, ...tempQueue]);
        await runAnalysis(tempQueue);
    }, [runAnalysis, setFileQueue]);

    const handleReset = useCallback(async () => {
        try {
            // Optimistic UI clear
            setFileQueue([]);
            setSelectedQueueId(null);
            setRecentlySavedIds(new Set());
            
            const now = Date.now();
            setLastClearedAt(now);
            lastClearedAtRef.current = now;
            
            // Server-side clear
            await apiClearDrafts();
            showToast("All drafts cleared.", "success");
        } catch (error) {
            console.error("Failed to clear drafts:", error);
            showToast("Failed to clear drafts", "error");
        }
    }, [setFileQueue, setSelectedQueueId, setRecentlySavedIds, showToast]);

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
    }, [selectedQueueId, setFileQueue, setSelectedQueueId, showToast]);

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
    }, [selectedQueueId, setFileQueue]);

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
    }, [selectedQueueId, setFileQueue]);

    const handleAddRow = useCallback(() => {
        setFileQueue(prev => prev.map(item => {
            if (item.id === selectedQueueId) {
                const newResult = { ...item.result };
                const newItems = [...(newResult.normalized_items || [])];
                newItems.push({
                    Standard_Item_Name: '',
                    Batch_No: '',
                    Expiry_Date: '',
                    MRP: 0,
                    Standard_Quantity: 1,
                    Net_Line_Amount: 0,
                    Is_Calculated: false
                });
                newResult.normalized_items = newItems;
                return { ...item, result: newResult };
            }
            return item;
        }));
    }, [selectedQueueId, setFileQueue]);

    const handleExport = useCallback(async () => {
        if (!activeQueueItem?.result?.normalized_items) return;
        try {
            const { exportToExcel } = await import('../utils/exportUtils');
            exportToExcel(activeQueueItem.result.normalized_items, `Invoice_${selectedQueueId}.xlsx`);
            showToast("Exporting to Excel...", "success");
        } catch (err) {
            console.error("Export failed", err);
            showToast("Export failed", "error");
        }
    }, [activeQueueItem, selectedQueueId, showToast]);

    const handleSaveInvoice = useCallback(async () => {
        if (!activeQueueItem?.result?.invoice_data) return;
        
        const invoiceIdToSave = selectedQueueId;
        setIsSaving(true);

        setRecentlySavedIds(prev => new Set(prev).add(invoiceIdToSave));

        let nextSelectedId = null;
        setFileQueue(prev => {
            const next = prev.filter(item => item.id !== invoiceIdToSave);
            if (next.length > 0) {
                nextSelectedId = next[0].id;
            }
            return next;
        });
        
        if (selectedQueueId === invoiceIdToSave) {
            setSelectedQueueId(nextSelectedId);
        }

        try {
            const payload = {
                invoice_data: {
                    ...activeQueueItem.result.invoice_data,
                    id: invoiceIdToSave,
                },
                normalized_items: activeQueueItem.result.normalized_items,
                image_path: activeQueueItem.result.image_path
            };

            await saveInvoice(payload);
            showToast("Invoice Saved Successfully!", "success");
        } catch (err) {
            console.error(err);
            showToast("Failed to save invoice. " + (err.response?.data?.detail || err.message), "error");
            
            setRecentlySavedIds(prev => {
                const next = new Set(prev);
                next.delete(invoiceIdToSave);
                return next;
            });
        } finally {
            setIsSaving(false);
        }
    }, [activeQueueItem, selectedQueueId, setFileQueue, setSelectedQueueId, setRecentlySavedIds, setIsSaving, showToast]);

    // SSE Integration
    useEffect(() => {
        if (!user) return;

        let eventSource;
        const connectSSE = () => {
            const token = localStorage.getItem('auth_token');
            if (!token) return;

            eventSource = new EventSource(`${import.meta.env.VITE_API_BASE_URL || ''}/invoices/stream-status?token=${token}`);

            eventSource.onmessage = (event) => {
                const data = JSON.parse(event.data);
                if (data.type === 'update') {
                    setFileQueue(prevQueue => {
                        const localMap = new Map(prevQueue.map(item => [item.id.toString(), item]));

                        const serverItems = data.drafts
                            .filter(d => {
                                if (lastClearedAtRef.current && d.created_at < lastClearedAtRef.current) return false;
                                return !recentlySavedIdsRef.current.has(d.id.toString());
                            })
                            .map(d => {
                                const localItem = localMap.get(d.id.toString());
                                return {
                                    id: d.id,
                                    status: d.status === 'draft' ? (d.is_duplicate ? 'duplicate' : 'completed') : d.status,
                                    previewUrl: d.previewUrl || localItem?.previewUrl,
                                    result: d.result,
                                    error: d.error,
                                    warning: d.duplicate_warning,
                                    filename: d.filename || d.file?.name || localItem?.filename,
                                    file: d.file || localItem?.file
                                };
                            });

                        const tempItems = prevQueue.filter(item => item.id.toString().startsWith('temp-'));
                        
                        const newQueue = [...tempItems];
                        serverItems.forEach(si => {
                            const existingIdx = newQueue.findIndex(ni => 
                                ni.id === si.id || 
                                (ni.id.toString().startsWith('temp-') && (ni.filename === si.filename))
                            );
                            
                            if (existingIdx > -1) {
                                newQueue[existingIdx] = { ...newQueue[existingIdx], ...si, previewUrl: si.previewUrl || newQueue[existingIdx].previewUrl };
                            } else {
                                newQueue.push(si);
                            }
                        });

                        return newQueue.sort((a, b) => {
                            const score = (s) => (s === 'completed' || s === 'duplicate' ? 3 : s === 'processing' ? 2 : 1);
                            return score(b.status) - score(a.status);
                        });
                    });
                }
            };

            eventSource.onerror = () => {
                eventSource.close();
                setTimeout(connectSSE, 5000);
            };
        };

        connectSSE();
        return () => eventSource?.close();
    }, [user, setFileQueue]); 

    const value = {
        activeQueueItem,
        isAnalyzing,
        handleFileChange,
        handleReset,
        handleDiscard,
        handleHeaderChange,
        handleLineItemChange,
        handleAddRow,
        handleExport,
        handleSaveInvoice
    };

    return (
        <InvoiceContext.Provider value={value}>
            {children}
        </InvoiceContext.Provider>
    );
};
