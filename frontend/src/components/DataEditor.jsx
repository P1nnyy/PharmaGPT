import React from 'react';
import { LayoutGrid } from 'lucide-react';
import EditorHeader from './editor/EditorHeader';
import EditorTable from './editor/EditorTable';
import EditorFooter from './editor/EditorFooter';

const DataEditor = ({
    invoiceData,
    lineItems,
    warnings,
    successMsg,
    errorMsg,
    isSaving,
    isAnalyzing,
    onHeaderChange,
    onInputChange,
    onAddRow,
    onConfirm,
    onExport
}) => {

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
        <div className="flex flex-col h-full bg-gray-900 relative">
            <EditorHeader
                invoiceData={invoiceData}
                lineItems={lineItems}
                warnings={warnings}
                successMsg={successMsg}
                errorMsg={errorMsg}
                onHeaderChange={onHeaderChange}
            />

            <EditorTable
                lineItems={lineItems}
                onInputChange={onInputChange}
                onAddRow={onAddRow}
            />

            <EditorFooter
                lineItems={lineItems}
                isSaving={isSaving}
                onExport={onExport}
                onConfirm={onConfirm}
            />
        </div>
    );
};

export default DataEditor;
