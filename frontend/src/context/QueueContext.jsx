import React, { createContext, useContext, useState, useEffect } from 'react';

export const getQueueItemDisplayName = (item) => {
    // 1. Check for valid extraction result
    const invoiceData = item.result?.invoice_data;
    const isDone = item.status === 'completed' || !!invoiceData;

    if (isDone) {
        if (invoiceData?.Supplier_Name) {
            const supplier = invoiceData.Supplier_Name;
            const invNo = invoiceData.Invoice_No || 'N/A';
            return `${supplier} • Inv #${invNo}`;
        }
        return 'Unknown Supplier';
    }

    // 2. Check for processing state
    if (item.status === 'processing') {
        return `Scanning: ${item.file?.name || item.filename || 'Document'}`;
    }

    // 3. Fallback to filename
    return item.file?.name || item.filename || 'Unnamed File';
};

/*
### 5. Deep Fix: Data Integrity & Heading-Up (CM ASSOCIATES)
Resolved severe extraction and rotation failures found in "CM ASSOCIATES" style invoices:
- **Grid-Line Resistant Rotation**: Implemented a new orientation heuristic in `image_processing.py` that ignores table grid lines and prioritizes "Heading-Up" view.
- **"Un-clubbing" Engine**: Updated `auditor.py` and `worker.py` to prevent and recover merged "Batch/Description" columns.
- **Strict Verification**: Hardened `mathematics.py` to flag financial gaps as `CRITICAL_FAILURE` if extraction is suspected to be corrupted.
- **Detailed Diagnostics**: Created a comprehensive [Agent Diagnostics Report](file:///Users/pranavgupta/.gemini/antigravity/brain/f4309550-ee18-46cf-bbac-fa15f7142535/agent_diagnostics.md) explaining internal states.

## Verification Results

### Backend Log Audit
Confirmed orientation scoring now prioritizes text blobs over grid lines. Verified un-clubbing logic correctly splits trailed batch numbers.

### Manual Verification (User)
- [ ] CM ASSOCIATES Invoice 1: Upright orientation, separate Batch column.
- [ ] CM ASSOCIATES Invoice 2: 180° inversion corrected (Heading Up).
- [ ] Financial calculations reconciled or flagged with clear warnings.
*/

const QueueContext = createContext();

export const useQueue = () => {
    const context = useContext(QueueContext);
    if (!context) {
        throw new Error('useQueue must be used within QueueProvider');
    }
    return context;
};

export const QueueProvider = ({ children }) => {
    const [fileQueue, setFileQueue] = useState(() => {
        const saved = sessionStorage.getItem('invoice_file_queue');
        return saved ? JSON.parse(saved) : [];
    });
    const [selectedQueueId, setSelectedQueueId] = useState(null);
    const [recentlySavedIds, setRecentlySavedIds] = useState(new Set());
    const [isSaving, setIsSaving] = useState(false);

    // Persist fileQueue
    useEffect(() => {
        const persistQueue = fileQueue.map((item) => {
            const { file, ...rest } = item;
            return {
                ...rest,
                filename: item.filename || file?.name || 'Unnamed File'
            };
        });
        sessionStorage.setItem('invoice_file_queue', JSON.stringify(persistQueue));
    }, [fileQueue]);

    const value = {
        fileQueue,
        setFileQueue,
        selectedQueueId,
        setSelectedQueueId,
        recentlySavedIds,
        setRecentlySavedIds,
        isSaving,
        setIsSaving
    };

    return (
        <QueueContext.Provider value={value}>
            {children}
        </QueueContext.Provider>
    );
};
