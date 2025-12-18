
import { useState, useEffect } from 'react';
import { Upload, Check, AlertCircle, Loader2, Save, FileText, Download, Plus } from 'lucide-react';
import * as XLSX from 'xlsx';
import { analyzeInvoice, ingestInvoice } from './services/api';


function App() {
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [invoiceData, setInvoiceData] = useState(null); // Raw extracted data
  const [lineItems, setLineItems] = useState([]); // Normalized items (Editable)

  const [warnings, setWarnings] = useState([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  // Clean up object URL
  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const handleFileChange = async (e) => {
    const selectedFile = e.target.files[0];
    if (!selectedFile) return;

    setFile(selectedFile);
    setPreviewUrl(URL.createObjectURL(selectedFile));
    setSuccessMsg('');
    setErrorMsg('');
    setWarnings([]); // Clear warnings on new file
    setInvoiceData(null);
    setLineItems([]);

    // Auto-analyze on upload
    await runAnalysis(selectedFile);
  };

  const runAnalysis = async (selectedFile) => {
    setIsAnalyzing(true);
    try {
      const result = await analyzeInvoice(selectedFile);
      setInvoiceData(result.invoice_data);
      setLineItems(result.normalized_items);
      setWarnings(result.validation_flags || []);
    } catch (err) {
      console.error(err);
      setErrorMsg("Analysis failed. Please try again.");
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleInputChange = (index, field, value) => {
    const newItems = [...lineItems];
    newItems[index] = { ...newItems[index], [field]: value };
    setLineItems(newItems);
  };

  const handleHeaderChange = (field, value) => {
    setInvoiceData(prev => ({ ...prev, [field]: value }));
  };

  const handleAddRow = () => {
    setLineItems([...lineItems, {
      Standard_Item_Name: "",
      Standard_Quantity: 1,
      HSN_Code: "",
      Batch_No: "",
      Expiry_Date: "",
      Net_Line_Amount: 0,
      Landed_Cost_Per_Unit: 0,
      // Default dummy values for required fields
      Raw_Item_Name: "Manual Entry",
      MRP: 0,
      Rate: 0,
      Discount_Percentage: 0,
      Discount_Amount: 0,
      GST_Percentage: 0,
      Tax_Amount: 0,
      Total_Amount: 0
    }]);
  };

  const handleConfirm = async () => {
    setIsSaving(true);
    setErrorMsg('');
    try {
      // Construct payload for /confirm-invoice
      const payload = {
        invoice_data: invoiceData,
        normalized_items: lineItems
      };

      const response = await ingestInvoice(payload);
      setSuccessMsg(`Success! ${response.message}`);

      // Optional: Delay reset for UX
      setTimeout(() => {
        handleReset();
      }, 2000);

    } catch (err) {
      console.error(err);
      setErrorMsg(err.response?.data?.detail || "Failed to save invoice.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleReset = () => {
    setFile(null);
    setPreviewUrl(null);
    setInvoiceData(null);
    setLineItems([]);
    setWarnings([]);
    setSuccessMsg('');
    setErrorMsg('');
  };

  const handleExport = () => {
    if (!lineItems.length) return;

    // Flatten data for Excel
    const dataToExport = lineItems.map((item, index) => ({
      "Sr No": index + 1,
      "Supplier": invoiceData?.Supplier_Name || "",
      "Invoice No": invoiceData?.Invoice_No || "",
      "Date": invoiceData?.Invoice_Date || "",
      "Item Name": item.Standard_Item_Name,
      "HSN Code": item.HSN_Code,
      "Batch No": item.Batch_No,
      "Expiry": item.Expiry_Date,
      "Quantity": item.Standard_Quantity,
      "Rate": item.Rate, // EXPORT RATE
      "MRP": item.MRP,
      "Tax %": item.Raw_GST_Percentage,
      "Net Amount": item.Net_Line_Amount
    }));

    // Create Worksheet
    const ws = XLSX.utils.json_to_sheet(dataToExport);

    // Create Workbook
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "Invoice Data");

    // Generate Filename
    const filename = invoiceData?.Invoice_No ? `Invoice_${invoiceData.Invoice_No}.xlsx` : "Export.xlsx";

    // Trigger Download
    XLSX.writeFile(wb, filename);
  };



  return (
    <div className="h-screen w-screen flex bg-gray-900 text-gray-100 overflow-hidden font-sans">

      {/* LEFT PANEL: Image / Upload */}
      <div className="w-1/2 h-full border-r border-gray-700 flex flex-col bg-gray-950">
        <div className="p-4 border-b border-gray-800 flex justify-between items-center">
          <h2 className="text-xl font-bold flex items-center gap-2 text-indigo-400">
            <FileText className="w-6 h-6" /> Source Invoice
          </h2>
          {file && (
            <button onClick={handleReset} className="text-sm text-gray-400 hover:text-white underline">
              Upload New
            </button>
          )}
        </div>

        <div className="flex-1 flex items-center justify-center p-6 overflow-hidden relative">
          {previewUrl ? (
            <img
              src={previewUrl}
              alt="Invoice Preview"
              className="max-w-full max-h-full object-contain shadow-2xl rounded-lg border border-gray-700"
            />
          ) : (
            <label className="flex flex-col items-center justify-center w-full h-full border-2 border-dashed border-gray-700 rounded-lg cursor-pointer hover:bg-gray-900 transition-colors">
              <Upload className="w-12 h-12 text-gray-500 mb-4" />
              <p className="text-gray-400 font-medium">Click to upload Invoice Image</p>
              <input type="file" className="hidden" accept="image/*" onChange={handleFileChange} />
            </label>
          )}

          {isAnalyzing && (
            <div className="absolute inset-0 bg-black/60 backdrop-blur-sm flex flex-col items-center justify-center z-10">
              <Loader2 className="w-12 h-12 text-indigo-500 animate-spin mb-4" />
              <p className="text-xl font-medium animate-pulse">Analyzing with AI Agents...</p>
            </div>
          )}
        </div>
      </div>

      {/* RIGHT PANEL: Data Editor */}
      <div className="w-1/2 h-full flex flex-col bg-gray-900">

        {/* HEADER FORM */}
        <div className="p-6 bg-gray-800 border-b border-gray-700 shadow-md z-10">
          {warnings.length > 0 && (
            <div className="mb-4 p-3 bg-red-900/40 border border-red-600 rounded-md">
              <h4 className="flex items-center gap-2 text-red-400 font-bold mb-1">
                <AlertCircle className="w-4 h-4" /> Potential Missing Items
              </h4>
              <ul className="text-xs text-red-200 list-disc list-inside">
                {warnings.map((w, idx) => <li key={idx}>{w}</li>)}
              </ul>
            </div>
          )}
          <div className="flex justify-between items-start mb-4">
            <h2 className="text-2xl font-bold text-white">Review Data</h2>
            {successMsg && (
              <div className="px-4 py-2 bg-green-900/50 text-green-300 rounded-md border border-green-700 flex items-center gap-2">
                <Check className="w-4 h-4" /> {successMsg}
              </div>
            )}
            {errorMsg && (
              <div className="px-4 py-2 bg-red-900/50 text-red-300 rounded-md border border-red-700 flex items-center gap-2">
                <AlertCircle className="w-4 h-4" /> {errorMsg}
              </div>
            )}
          </div>

          {invoiceData ? (
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-xs uppercase text-gray-500 font-semibold mb-1">Supplier</label>
                <input
                  type="text"
                  value={invoiceData.Supplier_Name}
                  onChange={(e) => handleHeaderChange('Supplier_Name', e.target.value)}
                  className="w-full bg-gray-700 border-gray-600 rounded px-3 py-2 focus:ring-2 focus:ring-indigo-500 outline-none"
                />
              </div>
              <div>
                <label className="block text-xs uppercase text-gray-500 font-semibold mb-1">Invoice No</label>
                <input
                  type="text"
                  value={invoiceData.Invoice_No}
                  onChange={(e) => handleHeaderChange('Invoice_No', e.target.value)}
                  className="w-full bg-gray-700 border-gray-600 rounded px-3 py-2 font-mono"
                />
              </div>
              <div>
                <label className="block text-xs uppercase text-gray-500 font-semibold mb-1">Date</label>
                <input
                  type="text"
                  value={invoiceData.Invoice_Date}
                  onChange={(e) => handleHeaderChange('Invoice_Date', e.target.value)}
                  className="w-full bg-gray-700 border-gray-600 rounded px-3 py-2"
                />
              </div>
            </div>
          ) : (
            <div className="text-gray-500 italic text-sm py-4">Waiting for analysis...</div>
          )}
        </div>

        {/* TABLE EDITOR */}
        <div className="flex-1 overflow-auto p-0">
          {lineItems.length > 0 ? (
            <>
              {/* TABLE HEADERS - Spreadsheet Style */}
              <div className="sticky top-0 z-10 bg-gray-900 pt-2">
                <div className="grid grid-cols-12 gap-6 mb-2 text-sm font-bold text-gray-400 border-b border-gray-700 pb-2 px-2">
                  <div className="col-span-1 pl-2 text-center text-gray-500">Sr</div>
                  <div className="col-span-4 pl-2">Item Name</div>
                  <div className="col-span-2">Batch No.</div>
                  <div className="col-span-1 text-center">Expiry</div>
                  <div className="col-span-1 text-center">MRP</div>
                  <div className="col-span-1 text-center">Qty</div>
                  {/* Rate Column Removed */}
                  <div className="col-span-2 text-right pr-2">Total Cost</div>
                </div>
              </div>

              {/* TABLE ROWS */}
              <div className="divide-y divide-gray-800">
                {lineItems.map((item, idx) => {
                  return (
                    <div key={idx} className="grid grid-cols-12 gap-6 items-center py-3 hover:bg-gray-800/30 px-2 transition-colors border-b border-gray-800/50">

                      {/* 0. Sr No */}
                      <div className="col-span-1 pl-2 text-center text-gray-500 font-mono text-sm">
                        {idx + 1}
                      </div>

                      {/* 1. Item Name - Expanded Span */}
                      <div className="col-span-4 pl-2">
                        <input
                          value={item.Standard_Item_Name || ''}
                          onChange={(e) => handleInputChange(idx, 'Standard_Item_Name', e.target.value)}
                          className="w-full bg-transparent outline-none focus:text-indigo-400 font-medium text-gray-200 text-base"
                          placeholder="Item Name"
                        />
                      </div>

                      {/* 2. Batch No */}
                      <div className="col-span-2">
                        <input
                          value={item.Batch_No || ''}
                          onChange={(e) => handleInputChange(idx, 'Batch_No', e.target.value)}
                          className="w-full bg-transparent outline-none font-mono text-gray-400 focus:text-indigo-400"
                          placeholder="Batch"
                        />
                      </div>

                      {/* 3. Expiry */}
                      <div className="col-span-1 text-center">
                        <input
                          value={item.Expiry_Date || ''}
                          onChange={(e) => handleInputChange(idx, 'Expiry_Date', e.target.value)}
                          className="w-full bg-transparent outline-none font-mono text-gray-400 focus:text-indigo-400 text-xs text-center"
                          placeholder="MM/YY"
                        />
                      </div>

                      {/* 4. MRP */}
                      <div className="col-span-1 text-center">
                        <input
                          type="number"
                          value={item.MRP || 0}
                          onChange={(e) => handleInputChange(idx, 'MRP', parseFloat(e.target.value))}
                          className="w-full bg-transparent outline-none font-mono text-center text-gray-400 focus:text-indigo-400"
                        />
                      </div>

                      {/* 5. Quantity */}
                      <div className="col-span-1 text-center">
                        <input
                          type="number"
                          value={item.Standard_Quantity || 0}
                          onChange={(e) => handleInputChange(idx, 'Standard_Quantity', parseFloat(e.target.value))}
                          className="w-full bg-transparent outline-none font-mono text-center text-indigo-300 font-bold bg-gray-800/20 rounded focus:bg-gray-700 py-1"
                        />
                      </div>

                      {/* 7. Total Cost (Net Amount) */}
                      <div className="col-span-2 text-right pr-2">
                        <input
                          type="number"
                          value={item.Net_Line_Amount || 0}
                          onChange={(e) => handleInputChange(idx, 'Net_Line_Amount', parseFloat(e.target.value))}
                          className="w-full bg-transparent outline-none font-mono text-right text-green-400 font-bold focus:text-green-300 text-lg"
                        />
                      </div>

                    </div>
                  );
                })}
              </div>

              {/* Summary Section (Reconciled) */}
              <div className="mt-4 border-t border-gray-700">

                {/* Grand Total (Sum of Lines) */}
                <div className="grid grid-cols-12 gap-4 items-center py-4 px-2 bg-gray-800 border-t border-gray-600 shadow-inner">
                  <div className="col-span-10 text-right text-white font-bold text-lg">
                    Grand Total
                    <span className="block text-xs font-normal text-gray-400 font-sans mt-0.5">(Sum of Total Cost)</span>
                  </div>
                  <div className="col-span-2 text-right text-indigo-400 font-mono text-xl font-bold">
                    {(
                      lineItems.reduce((acc, item) => acc + (parseFloat(item.Net_Line_Amount) || 0), 0)
                    ).toFixed(2)}
                  </div>
                </div>
              </div>

              <button
                onClick={handleAddRow}
                className="w-full py-3 border-t border-gray-700 text-gray-400 hover:text-white hover:bg-gray-800 transition-colors flex items-center justify-center gap-2 text-sm font-medium"
              >
                <Plus className="w-4 h-4" /> Add Item
              </button>
            </>
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-gray-600">
              {!isAnalyzing && <p>No items to display</p>}
            </div>
          )}
        </div>

        {/* FOOTER ACTION */}
        {lineItems.length > 0 && (
          <div className="p-4 bg-gray-800 border-t border-gray-700 flex justify-end gap-4">
            <button
              onClick={handleExport}
              className="flex items-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-lg shadow-lg hover:shadow-xl transition-all"
            >
              <Download className="w-5 h-5" /> Download Excel
            </button>

            <div className="flex items-center gap-4 mr-auto text-xl font-bold text-white">
              <span>Total:</span>
              <span className="font-mono text-indigo-400">
                {lineItems.reduce((acc, item) => acc + (parseFloat(item.Net_Line_Amount) || 0), 0).toFixed(2)}
              </span>
            </div>

            <button
              onClick={handleConfirm}
              disabled={isSaving}
              className="flex items-center gap-2 px-6 py-3 bg-green-600 hover:bg-green-500 text-white font-semibold rounded-lg shadow-lg hover:shadow-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSaving ? <Loader2 className="animate-spin w-5 h-5" /> : <Save className="w-5 h-5" />}
              Confirm & Save Invoice
            </button>
          </div>
        )}

      </div>
    </div>
  );
}

export default App;
