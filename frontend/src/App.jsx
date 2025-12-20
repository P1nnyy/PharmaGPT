import { useState, useEffect } from 'react';
import { analyzeInvoice, ingestInvoice, exportInvoice } from './services/api';

// Components
import InvoiceViewer from './components/InvoiceViewer';
import DataEditor from './components/DataEditor';
import MobileNavBar from './components/MobileNavBar';

function App() {
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);

  // Data State
  const [invoiceData, setInvoiceData] = useState(null);
  const [lineItems, setLineItems] = useState([]);
  const [warnings, setWarnings] = useState([]);

  // UI State
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  // Layout State (For Mobile)
  const [activeTab, setActiveTab] = useState('image'); // 'image' or 'editor'

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
    setWarnings([]);
    setInvoiceData(null);
    setLineItems([]);

    // Auto-switch to editor view on mobile after brief delay or keep on image until done
    // For now, let's keep user on image until analysis starts

    await runAnalysis(selectedFile);
  };

  const runAnalysis = async (selectedFile) => {
    setIsAnalyzing(true);
    try {
      const result = await analyzeInvoice(selectedFile);
      setInvoiceData(result.invoice_data);
      setLineItems(result.normalized_items);
      setWarnings(result.validation_flags || []);

      // On success, switch mobile view to Editor to show results
      setActiveTab('editor');

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
      Raw_Item_Name: "Manual Entry",
      MRP: 0,
    }]);
  };

  const handleConfirm = async () => {
    setIsSaving(true);
    setErrorMsg('');
    try {
      const payload = {
        invoice_data: invoiceData,
        normalized_items: lineItems
      };

      const response = await ingestInvoice(payload);
      setSuccessMsg(`Success! ${response.message}`);

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
    setActiveTab('image'); // Reset to start
  };

  const handleExport = async () => {
    if (!invoiceData || lineItems.length === 0) {
      setErrorMsg("Nothing to export!");
      return;
    }

    try {
      setSuccessMsg("Generating Excel...");
      const blob = await exportInvoice({
        invoice_data: invoiceData,
        normalized_items: lineItems
      });

      const url = window.URL.createObjectURL(new Blob([blob]));
      const link = document.createElement('a');
      link.href = url;
      const filename = invoiceData?.Invoice_No ? `Invoice_${invoiceData.Invoice_No}.xlsx` : "Export.xlsx";
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.parentNode.removeChild(link);
      setSuccessMsg("Export Complete!");
      setTimeout(() => setSuccessMsg(null), 3000);

    } catch (e) {
      console.error(e);
      setErrorMsg("Export Failed.");
    }
  };

  return (
    <div className="h-screen w-screen bg-gray-950 text-gray-100 overflow-hidden font-sans relative">

      <div className="flex flex-col md:flex-row h-full">

        {/* PANEL 1: IMAGE VIEWER */}
        {/* Hidden on mobile if activeTab is 'editor' */}
        <div className={`md:w-1/2 h-full ${activeTab === 'image' ? 'block' : 'hidden md:block'}`}>
          <InvoiceViewer
            file={file}
            previewUrl={previewUrl}
            isAnalyzing={isAnalyzing}
            onFileChange={handleFileChange}
            onReset={handleReset}
          />
        </div>

        {/* PANEL 2: DATA EDITOR */}
        {/* Hidden on mobile if activeTab is 'image' */}
        <div className={`md:w-1/2 h-full ${activeTab === 'editor' ? 'block' : 'hidden md:block'}`}>
          <DataEditor
            invoiceData={invoiceData}
            lineItems={lineItems}
            warnings={warnings}
            successMsg={successMsg}
            errorMsg={errorMsg}
            isSaving={isSaving}
            isAnalyzing={isAnalyzing}
            onHeaderChange={handleHeaderChange}
            onInputChange={handleInputChange}
            onAddRow={handleAddRow}
            onConfirm={handleConfirm}
            onExport={handleExport}
          />
        </div>
      </div>

      {/* MOBILE NAVIGATION Bar */}
      {/* Only shows if file is loaded to allow switching contexts */}
      {file && <MobileNavBar activeTab={activeTab} onTabChange={setActiveTab} />}

    </div>
  );
}

export default App;
