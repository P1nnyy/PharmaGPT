import React from 'react';
import { LayoutGrid } from 'lucide-react';
import EditorHeader from './editor/EditorHeader';
import EditorTable from './editor/EditorTable';
import EditorFooter from './editor/EditorFooter';
import { useInvoice } from '../../context/InvoiceContext';
import { useQueue } from '../../context/QueueContext';

const DataEditor = ({
    readOnly = false
}) => {
    const {
        activeQueueItem,
        isAnalyzing,
        handleHeaderChange,
        handleLineItemChange,
        handleAddRow,
        handleExport,
        handleSaveInvoice,
    } = useInvoice();

    const { isSaving } = useQueue();

    const invoiceData = activeQueueItem?.result?.invoice_data || null;
    const lineItems = activeQueueItem?.result?.normalized_items || [];
    const warnings = activeQueueItem?.result?.validation_flags || [];

    const onHeaderChange = handleHeaderChange;
    const onInputChange = handleLineItemChange;
    const onAddRow = handleAddRow;
    const onExport = handleExport;
    const onConfirm = handleSaveInvoice;

    if (!invoiceData && !isAnalyzing) {
        return (
            <div className="h-full flex flex-col items-center justify-center text-gray-500 p-8 text-center">
                <div className="w-16 h-16 bg-gray-800 rounded-full flex items-center justify-center mb-4">
                    <LayoutGrid className="w-8 h-8 text-gray-600" />
                </div>
                <h3 className="text-lg font-medium text-gray-400">No Data Yet</h3>
                <p className="text-sm text-gray-600 mt-2">Upload an invoice to see extracted data here.</p>
            </div>
        );
    }

    return (
        <div className="flex flex-col min-h-full bg-gray-900 relative">
            <EditorHeader
                invoiceData={invoiceData}
                lineItems={lineItems}
                warnings={warnings}
                onHeaderChange={onHeaderChange}
                readOnly={readOnly}
            />

            <EditorTable
                lineItems={lineItems}
                onInputChange={onInputChange}
                onAddRow={onAddRow}
                readOnly={readOnly}
            />

            <EditorFooter
                invoiceData={invoiceData}
                lineItems={lineItems}
                isSaving={isSaving}
                onExport={onExport}
                onConfirm={onConfirm}
                readOnly={readOnly}
            />
        </div>
    );
};

export default DataEditor;
