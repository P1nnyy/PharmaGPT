import React, { useState, useEffect } from 'react';
import ItemDetailHeader from './components/ItemDetailHeader';
import ItemTabs from './ItemTabs';
import { getProductHistory } from '../../services/api';

const ItemDetails = ({ 
    formData, 
    setFormData,
    activeTab, 
    setActiveTab, 
    onSave, 
    saving, 
    setShowMobileDetail, 
    onInputChange, 
    categories,
    showMobileDetail
}) => {
    const [history, setHistory] = useState([]);
    const [historyLoading, setHistoryLoading] = useState(false);

    useEffect(() => {
        if (formData.original_name) {
            setHistoryLoading(true);
            getProductHistory(formData.original_name).then(data => {
                setHistory(data);
                setHistoryLoading(false);
            }).catch(err => {
                console.error("Failed to fetch product history", err);
                setHistoryLoading(false);
            });
        }
    }, [formData.original_name]);

    return (
        <div className={`flex-1 h-full flex flex-col bg-slate-800 absolute md:relative inset-0 z-20 transition-transform duration-300 ${showMobileDetail ? 'translate-x-0' : 'translate-x-full md:translate-x-0'}`}>
            <ItemDetailHeader 
                formData={formData}
                activeTab={activeTab}
                setActiveTab={setActiveTab}
                handleSave={onSave}
                saving={saving}
                setShowMobileDetail={setShowMobileDetail}
            />

            <ItemTabs
                item={formData}
                activeTab={activeTab}
                onTabChange={setActiveTab}
                onInputChange={onInputChange}
                onFormDataChange={setFormData}
                categories={categories}
                history={history}
                historyLoading={historyLoading}
            />
        </div>
    );
};

export default ItemDetails;
