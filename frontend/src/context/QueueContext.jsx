import React, { createContext, useContext, useState, useEffect } from 'react';

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
