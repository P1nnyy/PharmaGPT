import { useState, useEffect } from 'react';
import { analyzeInvoice, saveInvoice } from './services/api';

// ... (imports remain)
import InvoiceViewer from './components/InvoiceViewer';
import DataEditor from './components/DataEditor';
import MobileNavBar from './components/MobileNavBar';
import HistoryView from './components/History';
import InventoryView from './components/Inventory';
import Login from './components/Login';

function App() {
  const [activeTab, setActiveTab] = useState('invoice'); // 'invoice' | 'history' | 'inventory' | 'settings'
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [invoiceData, setInvoiceData] = useState(null);
  const [imagePath, setImagePath] = useState(null);
  const [lineItems, setLineItems] = useState([]);
  const [warnings, setWarnings] = useState([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [successMsg, setSuccessMsg] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);

  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);

  const [username, setAuthenticatedUser] = useState(null);

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  if (!username) {
    return <Login onLogin={setAuthenticatedUser} />;
  }

  const handleTabChange = (tab) => {
    setActiveTab(tab);
  };

  const runAnalysis = async (selectedFile) => {
    setIsAnalyzing(true);
    try {
      // Assuming analyzeInvoice returns { invoice_data, normalized_items, validation_flags }
      const data = await analyzeInvoice(selectedFile);
      handleAnalysisComplete(data);
    } catch (err) {
      console.error(err);
      setErrorMsg(err.response?.data?.detail || "Analysis failed. Please try again.");
      setIsAnalyzing(false);
    }
  };

  const handleFileChange = async (e) => {
    const selectedFile = e.target.files ? e.target.files[0] : null;
    if (!selectedFile) return;

    setFile(selectedFile);
    setPreviewUrl(URL.createObjectURL(selectedFile));
    setInvoiceData(null);
    setImagePath(null);
    setLineItems([]);
    setWarnings([]);
    setSuccessMsg(null);
    setErrorMsg(null);

    // Trigger Analysis
    await runAnalysis(selectedFile);
  };

  const handleReset = () => {
    setFile(null);
    setPreviewUrl(null);
    setInvoiceData(null);
    setImagePath(null);
    setLineItems([]);
    setWarnings([]);
    setSuccessMsg(null);
    setErrorMsg(null);
  };

  const handleAnalysisComplete = (data) => {
    setInvoiceData(data.invoice_data);
    setLineItems(data.normalized_items);
    setImagePath(data.image_path);
    setWarnings(data.validation_flags || []);
    setIsAnalyzing(false);
  };

  const handleError = (msg) => {
    setErrorMsg(msg);
    setIsAnalyzing(false);
  };

  const handleHeaderChange = (field, value) => {
    setInvoiceData(prev => ({ ...prev, [field]: value }));
  };

  const handleLineItemChange = (index, field, value) => {
    const updated = [...lineItems];
    updated[index] = { ...updated[index], [field]: value };
    setLineItems(updated);
  };

  const handleSaveInvoice = async () => {
    if (!invoiceData) return;
    setIsSaving(true);
    setSuccessMsg(null);
    setErrorMsg(null);

    try {
      // Construct payload matching backend expectation
      const payload = {
        invoice_data: invoiceData,
        normalized_items: lineItems,
        image_path: imagePath
      };

      await saveInvoice(payload);
      setSuccessMsg("Invoice Saved Successfully!");
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err) {
      console.error(err);
      setErrorMsg("Failed to save invoice. " + (err.response?.data?.detail || err.message));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 font-sans selection:bg-indigo-500/30">

      <div className="flex flex-col md:flex-row h-screen overflow-hidden">

        {/* LEFT SIDE: INVOICE & CAMERA */}
        <div className={`w-full md:w-1/2 flex flex-col relative transition-all duration-300 border-b md:border-b-0 md:border-r border-slate-800
                ${isMobile && activeTab !== 'invoice' ? 'hidden' : 'flex'}
                ${isMobile && invoiceData ? 'h-[35%]' : 'h-full'} 
            `}>
          <InvoiceViewer
            file={file}
            previewUrl={previewUrl}
            isAnalyzing={isAnalyzing}
            onFileChange={handleFileChange}
            onReset={handleReset}
            onAnalysisComplete={handleAnalysisComplete} // Pass callback
            onError={handleError}
            setIsAnalyzing={setIsAnalyzing}
          />
        </div>

        {/* RIGHT SIDE: CONTENT AREA (Editor, History, Inventory) */}
        <div className={`w-full md:w-1/2 flex flex-col bg-slate-900/50 border-l border-slate-800
                ${isMobile && activeTab === 'invoice' && !invoiceData ? 'hidden' : 'flex'} 
                ${isMobile && activeTab !== 'invoice' ? 'flex h-full' : ''}
                ${isMobile && activeTab === 'invoice' && invoiceData ? 'h-[65%]' : 'h-full'}
            `}>
          {/* Note: On mobile, if we are in 'invoice' tab but have data, we might want to show editor?
                    Actually, let's keep it simple:
                    'invoice' tab = Split View equivalent.
                    If no data, show Viewer.
                    If data, show Editor (scrolled down).
                    
                    Better approach for Mobile 'Invoice' Tab:
                    - Show Viewer at top.
                    - Show Editor below it?
                    - Or toggle? 
                    
                    Let's stick to the prompt's request: "Don't mess up logic".
                    I'll implement the Tab Switching logic cleanly.
                */}

          {activeTab === 'invoice' && invoiceData && (
            <DataEditor
              invoiceData={invoiceData}
              lineItems={lineItems}
              warnings={warnings}
              successMsg={successMsg}
              errorMsg={errorMsg}
              isSaving={isSaving}
              isAnalyzing={isAnalyzing}
              onHeaderChange={handleHeaderChange}
              onLineItemChange={handleLineItemChange}
              setLineItems={setLineItems}
              setIsSaving={setIsSaving}
              setSuccessMsg={setSuccessMsg}
              setErrorMsg={setErrorMsg}
              onConfirm={handleSaveInvoice}
            />
          )}

          {/* On Desktop, if no data, we might show a placeholder or just empty */}
          {activeTab === 'invoice' && !invoiceData && !isMobile && (
            <div className="flex-1 flex items-center justify-center text-slate-600">
              <div className="text-center">
                <p>Upload an invoice to see details here.</p>
              </div>
            </div>
          )}

          {activeTab === 'history' && <HistoryView />}

          {activeTab === 'inventory' && <InventoryView />}

          {activeTab === 'settings' && (
            <div className="p-8 text-center text-slate-500">
              <h2 className="text-xl text-slate-300 mb-2">Settings</h2>
              <p>Configure app preferences here.</p>
              <div className="mt-8 p-4 bg-slate-800 rounded-lg text-xs font-mono text-left">
                <div className="mb-2 text-indigo-400">DEBUG INFO:</div>
                <div>API: {window.location.hostname.includes('pharmagpt') ? 'Secure (Tunnel)' : 'Localhost'}</div>
                <div>Version: v5.2 (History Enabled)</div>
              </div>
            </div>
          )}
        </div>

      </div>

      {/* Mobile Navigation Bar */}
      {isMobile && (
        <MobileNavBar
          activeTab={activeTab}
          onTabChange={handleTabChange}
          onCameraClick={() => {
            setActiveTab('invoice');
            // Logic to trigger camera input if supported (ref passed to viewer?)
            // For now, just switching tab is enough to show the viewer which has the upload button.
          }}
        />
      )}

      {/* Global Toast for Errors (Visible even if Analysis Fails) */}
      {errorMsg && !invoiceData && (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 bg-rose-500/90 text-white px-6 py-3 rounded-full shadow-2xl backdrop-blur-md z-[100] animate-in slide-in-from-top-4 fade-in">
          <span className="font-medium mr-2">Error:</span> {errorMsg}
          <button onClick={() => setErrorMsg(null)} className="ml-4 hover:bg-white/20 rounded-full p-1">✕</button>
        </div>
      )}
    </div>
  );
}

export default App;
