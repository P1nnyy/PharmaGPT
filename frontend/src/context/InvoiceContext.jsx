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
    const [fileQueue, setFileQueue] = useState(() => {
        const saved = sessionStorage.getItem('invoice_file_queue');
        return saved ? JSON.parse(saved) : [];
    });
    const [selectedQueueId, setSelectedQueueId] = useState(null);
    const [recentlySavedIds, setRecentlySavedIds] = useState(new Set());
    const [isSaving, setIsSaving] = useState(false);
    const [user, setUser] = useState(null);
    const [isLoadingAuth, setIsLoadingAuth] = useState(true);
    const [toast, setToast] = useState({ show: false, message: '', type: 'success' });
    const [lastClearedAt, setLastClearedAt] = useState(0);
    const lastClearedAtRef = React.useRef(0);
    const recentlySavedIdsRef = React.useRef(new Set());

    // Persist fileQueue to sessionStorage (excluding raw File objects)
    useEffect(() => {
        const persistQueue = fileQueue.map(({ file, ...rest }) => ({
            ...rest,
            // Ensure we keep the filename string even if 'file' object is stripped
            filename: rest.filename || file?.name
        }));
        sessionStorage.setItem('invoice_file_queue', JSON.stringify(persistQueue));
    }, [fileQueue]);

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
            const formData = new FormData();
            filesToProcess.forEach(item => {
                formData.append('files', item.file);
                // We'll pass the temp IDs as a separate field or just rely on index order
                formData.append('temp_ids', item.id);
            });
            
            const { uploadBatchInvoicesFormData } = await import('../services/api');
            const placeholders = await uploadBatchInvoicesFormData(formData);

            setFileQueue(prev => {
                // Merge placeholders with current queue by matching temp_id
                return prev.map(item => {
                    const placeholder = placeholders.find(p => p.temp_id === item.id);
                    if (placeholder) {
                        return {
                            ...item,
                            id: placeholder.id, // Update temp-id with real-id
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
    }, [showToast]);

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
    }, [runAnalysis]);

    const handleReset = useCallback(async () => {
        try {
            const now = Date.now();
            setLastClearedAt(now);
            lastClearedAtRef.current = now;
            setRecentlySavedIds(new Set());
            recentlySavedIdsRef.current = new Set();
            
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
    }, [selectedQueueId]);

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

        // --- OPTIMISTIC UPDATE ---
        // 1. Mark as recently saved to prevent SSE from re-adding it
        setRecentlySavedIds(prev => new Set(prev).add(invoiceIdToSave));
        recentlySavedIdsRef.current.add(invoiceIdToSave);

        // 2. Remove from local queue immediately
        let nextSelectedId = null;
        setFileQueue(prev => {
            const next = prev.filter(item => item.id !== invoiceIdToSave);
            if (next.length > 0) {
                nextSelectedId = next[0].id;
            }
            return next;
        });
        
        // 3. Update selected ID outside the filter loop
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
            
            // --- ROLLBACK (Optional but good) ---
            // If save fails, we should technically put it back, but the user can just re-upload or check All Invoices.
            // For now, we keep it removed to avoid confusion, but we could restore it here.
            setRecentlySavedIds(prev => {
                const next = new Set(prev);
                next.delete(invoiceIdToSave);
                return next;
            });
            recentlySavedIdsRef.current.delete(invoiceIdToSave);
        } finally {
            setIsSaving(false);
        }
    }, [activeQueueItem, selectedQueueId, showToast]);

    // --- SSE Integration (Replaces Polling) ---
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
                        // 1. Build a map of current queue by ID for quick lookup
                        const localMap = new Map(prevQueue.map(item => [item.id.toString(), item]));

                        // 2. Map server drafts to updated local items
                        const serverItems = data.drafts
                            .filter(d => {
                                // Filter out anything created before the last global clear
                                if (lastClearedAtRef.current && d.created_at < lastClearedAtRef.current) return false;
                                return !recentlySavedIdsRef.current.has(d.id.toString());
                            })
                            .map(d => {
                                const localItem = localMap.get(d.id.toString());
                                return {
                                    id: d.id,
                                    file: d.file,
                                    status: d.status === 'draft' ? (d.is_duplicate ? 'duplicate' : 'completed') : d.status,
                                    // CRITICAL: Preserve local previewUrl if server one is missing/null
                                    previewUrl: d.previewUrl || localItem?.previewUrl,
                                    result: d.result,
                                    error: d.error,
                                    warning: d.duplicate_warning
                                };
                            });

                        // 3. Keep local items that are still 'temp-' (not yet recognized by server)
                        const tempItems = prevQueue.filter(item => item.id.toString().startsWith('temp-'));
                        
                        // 4. Combine and Sort
                        const newQueue = [...tempItems];
                        serverItems.forEach(si => {
                            // Deduplicate: Compare by ID OR by filename for temp items
                            const existingIdx = newQueue.findIndex(ni => 
                                ni.id === si.id || 
                                (ni.id.toString().startsWith('temp-') && (ni.filename === si.filename || ni.file?.name === si.file?.name))
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
    }, [user]); // Removed recentlySavedIds from dependencies to prevent connection resets

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
        handleAddRow,
        handleExport,
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
