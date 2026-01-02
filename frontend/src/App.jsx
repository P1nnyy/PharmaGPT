import { useState, useEffect } from 'react';
import { analyzeInvoice, saveInvoice, getUserProfile, setAuthToken } from './services/api';
import { Loader2 } from 'lucide-react';

// ... (imports remain)
import InvoiceViewer from './components/invoice/InvoiceViewer';
import DataEditor from './components/invoice/DataEditor';
import MobileNavBar from './components/layout/MobileNavBar';
import InventoryView from './components/dashboard/Inventory';
import Login from './components/Login';

import Sidebar from './components/layout/Sidebar';

import ActivityHistory from './components/dashboard/ActivityHistory';

import GroupedInvoices from './components/dashboard/GroupedInvoices';

import MobileHeader from './components/layout/MobileHeader';

function App() {
  const [activeTab, setActiveTab] = useState('scan'); // 'scan' | 'history' | 'inventory' | 'settings' | 'invoices'
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
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

  const [user, setUser] = useState(null);
  const [isLoadingAuth, setIsLoadingAuth] = useState(true);

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // --- Auth Initialization ---
  useEffect(() => {
    const initAuth = async () => {
      // 1. Check URL for Token (OAuth Callback)
      const params = new URLSearchParams(window.location.search);
      const tokenFromUrl = params.get('token');

      if (tokenFromUrl) {
        console.log("Found Token in URL, logging in...");
        setAuthToken(tokenFromUrl);
        // Clean URL
        window.history.replaceState({}, document.title, window.location.pathname);
      }

      // 2. Fetch Profile if Token exists (in memory/localstorage from setAuthToken)
      try {
        // Just checking getProfile will verify token valid
        // NOTE: setAuthToken handles localStorage read on import, but consistent here
        const savedToken = localStorage.getItem('auth_token');
        if (savedToken) {
          // Ensure it's set in axios
          setAuthToken(savedToken);
          const profile = await getUserProfile();
          setUser(profile);
        }
      } catch (err) {
        console.error("Auth Validation Failed:", err);
        // If 401, clear token
        setAuthToken(null);
        setUser(null);
      } finally {
        setIsLoadingAuth(false);
      }
    };

    initAuth();
  }, []);


  if (isLoadingAuth) {
    return (
      <div className="h-screen bg-slate-950 flex items-center justify-center">
        <Loader2 className="w-10 h-10 text-indigo-500 animate-spin" />
      </div>
    );
  }

  if (!user) {
    return <Login />;
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
    setInvoiceData(prev => {
      // Handle nested supplier_details updates
      if (field.startsWith('supplier_details.')) {
        const key = field.split('.')[1];
        return {
          ...prev,
          supplier_details: {
            ...prev.supplier_details,
            [key]: value
          }
        };
      }
      return { ...prev, [field]: value };
    });
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
    <div className="flex bg-slate-50 h-screen font-sans selection:bg-blue-200 selection:text-blue-900 overflow-hidden">

      {/* MOBILE HEADER */}
      {isMobile && (
        <MobileHeader
          onMenuClick={() => {
            console.log("MOBILE MENU CLICKED");
            setIsSidebarOpen(true);
          }}
          onCameraClick={() => setActiveTab('scan')}
        />
      )}

      {/* SIDEBAR (Desktop Fixed, Mobile Drawer) */}
      {/* DEBUG LOG */}
      {/* console.log("App Render: isMobile=", isMobile, "isSidebarOpen=", isSidebarOpen) */}
      <Sidebar
        activeTab={activeTab}
        onTabChange={handleTabChange}
        isMobile={isMobile}
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
        user={user}
        onLogout={() => {
          setAuthToken(null);
          setUser(null);
        }}
      />

      {/* MAIN CONTENT AREA */}
      <div className={`flex-1 flex flex-col h-full overflow-hidden bg-slate-950 text-slate-200 ${isMobile ? 'pt-[60px]' : ''}`}>

        {/* Only Render Split View for "Scan Invoice" Tab */}
        <div className={`flex flex-col md:flex-row h-full w-full ${activeTab !== 'scan' ? 'hidden' : 'flex'}`}>
          {/* LEFT SIDE: INVOICE & CAMERA */}
          <div className={`w-full md:w-1/2 flex flex-col relative transition-all duration-300 border-b md:border-b-0 md:border-r border-slate-800
                    ${isMobile && activeTab !== 'scan' ? 'hidden' : 'flex'}
                    ${isMobile && invoiceData ? 'h-[35%]' : 'h-full'} 
                `}>
            <InvoiceViewer
              file={file}
              previewUrl={previewUrl}
              isAnalyzing={isAnalyzing}
              onFileChange={handleFileChange}
              onReset={handleReset}
              onAnalysisComplete={handleAnalysisComplete}
              onError={handleError}
              setIsAnalyzing={setIsAnalyzing}
            />
          </div>

          {/* RIGHT SIDE: EDITOR */}
          <div className={`w-full md:w-1/2 flex flex-col bg-slate-900/50 border-l border-slate-800
                    ${isMobile && activeTab === 'scan' && !invoiceData ? 'hidden' : 'flex'} 
                    ${isMobile && activeTab !== 'scan' ? 'flex h-full' : ''}
                    ${isMobile && activeTab === 'scan' && invoiceData ? 'h-[65%]' : 'h-full'}
                `}>

            {invoiceData && (
              <DataEditor
                invoiceData={invoiceData}
                lineItems={lineItems}
                warnings={warnings}
                successMsg={successMsg}
                errorMsg={errorMsg}
                isSaving={isSaving}
                isAnalyzing={isAnalyzing}
                onHeaderChange={handleHeaderChange}
                onInputChange={handleLineItemChange}
                setLineItems={setLineItems}
                setIsSaving={setIsSaving}
                setSuccessMsg={setSuccessMsg}
                setErrorMsg={setErrorMsg}
                onConfirm={handleSaveInvoice}
              />
            )}

            {!invoiceData && !isMobile && (
              <div className="flex-1 flex items-center justify-center text-slate-600">
                <div className="text-center">
                  <p>Upload an invoice to see details here.</p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* OTHER TABS (History, Inventory, etc) - Rendered in Full Width */}
        <div className="flex-1 overflow-auto bg-slate-900 border-t border-slate-800 md:border-t-0 p-4">
          {activeTab === 'history' && <ActivityHistory />}
          {activeTab === 'inventory' && <InventoryView />}
          {activeTab === 'invoices' && <GroupedInvoices />}
          {activeTab === 'settings' && (
            <div className="p-8 text-center text-slate-500">
              <h2 className="text-xl text-slate-300 mb-2">Settings</h2>
              <p>Configure app preferences here.</p>
              <div className="mt-8 p-4 bg-slate-800 rounded-lg text-xs font-mono text-left inline-block">
                <div className="mb-2 text-indigo-400">DEBUG INFO:</div>
                <div>API: {window.location.hostname.includes('pharmagpt') ? 'Secure (Tunnel)' : 'Localhost'}</div>
                <div>Version: v5.7 (Mobile Sidebar)</div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Global Toast for Errors */}
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
