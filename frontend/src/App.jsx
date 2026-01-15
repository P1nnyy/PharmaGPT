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
import ItemMaster from './components/items/ItemMaster';

function App() {
  const [activeTab, setActiveTab] = useState('scan'); // 'scan' | 'history' | 'inventory' | 'settings' | 'invoices'
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  // Batch State
  const [fileQueue, setFileQueue] = useState([]); // [{ id, file, status: 'pending'|'processing'|'completed'|'error', previewUrl, result, error }]
  const [selectedQueueId, setSelectedQueueId] = useState(null);

  // Computed from Queue
  const activeQueueItem = fileQueue.find(item => item.id === selectedQueueId) || fileQueue[0];
  const file = activeQueueItem?.file || null;
  const previewUrl = activeQueueItem?.previewUrl || null;
  const invoiceData = activeQueueItem?.result?.invoice_data || null;
  const lineItems = activeQueueItem?.result?.normalized_items || [];
  const warnings = activeQueueItem?.result?.validation_flags || [];
  const imagePath = activeQueueItem?.result?.image_path || null;

  // Global Loading is true if ANY are processing
  const isAnalyzing = fileQueue.some(f => f.status === 'processing');

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

  // Polling for Updates
  useEffect(() => {
    let intervalId;

    const fetchDrafts = async () => {
      try {
        const drafts = await import('./services/api').then(m => m.getDrafts());

        // Merge Strategy: Update existing, Add new, Remove only if not in draft list?
        // Actually, getDrafts returns the source of truth for "Unsaved Work".
        // We should sync fileQueue to it.

        setFileQueue(prevQueue => {
          // Optimization: Only update if changed prevents verify flicker?
          // For now, let's just map status updates to preserve local UI state if needed (like selection)

          // Map server drafts to UI model
          // STATUS MAPPING: 
          // 'draft' + is_duplicate -> 'duplicate'
          // 'draft' -> 'completed'
          const serverItems = drafts.map(d => {
            let uiStatus = d.status;
            if (d.status === 'draft') {
              if (d.is_duplicate) {
                uiStatus = 'duplicate';
              } else {
                uiStatus = 'completed';
              }
            }

            return {
              id: d.id,
              file: d.file,
              status: uiStatus,
              previewUrl: d.previewUrl,
              result: d.result,
              error: d.error,
              warning: d.duplicate_warning // Pass warning text
            };
          });

          // SORTING: Completed/Duplicate First, then Processing
          serverItems.sort((a, b) => {
            const score = (status) => {
              if (status === 'completed') return 3;
              if (status === 'duplicate') return 3; // Same priority as completed
              if (status === 'processing') return 2;
              return 1;
            };
            return score(b.status) - score(a.status);
          });

          // Sync Logic:
          // If we just blindly replace, we might lose selection context or local-only processing items?
          // But serverItems is the source of truth for "Batch".
          // If queue is empty, just fill.
          if (prevQueue.length === 0) return serverItems;

          // If we have items, we want to update them but keep the sort order stable? 
          // Actually, if we sort serverItems, that's the desired order.
          return serverItems;
        });

      } catch (err) {
        console.error("Polling Error:", err);
      }
    };

    // 1. Initial Load (Recovery)
    fetchDrafts();

    // 2. Poll if any are Processing
    // We check state inside the effect interval or by dependency?
    // Dependency on fileQueue causes infinite loop if we update fileQueue.
    // Better: Set interval, inside check if we need to continue?
    // Or just always poll slowly (5s) if "Unsaved Work" exists?
    // Let's rely on `isAnalyzing` derived state.

    if (isAnalyzing) {
      intervalId = setInterval(fetchDrafts, 3000);
    }

    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [isAnalyzing]); // Re-evaluates when isAnalyzing changes (e.g. one finishes locally? No, local status won't change without polling)
  // Wait, if we rely on polling to change status, isAnalyzing won't change UNTIL polling runs.
  // So we need to kickstart it. 
  // ADDENDUM: We also need to poll if we *mounted* and suspect things.
  // Actually, if we just uploaded, we set status='processing'. This trips isAnalyzing=true. Effect runs. Interval starts. 
  // Polling runs. Status changes to 'draft'. isAnalyzing=false. Effect runs. Interval clears. Perfect.


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

  const runAnalysis = async (filesToProcess) => {
    // Logic moved to handleFileChange mostly, this now just handles the upload call
    // But handleFileChange builds the "Pre-Upload" queue.

    try {
      const { uploadBatchInvoices } = await import('./services/api');

      // filesToProcess is the list of { file: File } objects from the queue
      const files = filesToProcess.map(item => item.file);

      // Upload - Immediately returns placeholders with IDs
      const placeholders = await uploadBatchInvoices(files);

      // Update Queue with Server IDs and Status
      setFileQueue(prev => {
        // Replace the "temp" items with "server" placeholders
        // or just override?
        return placeholders;
        // Note: This replaces the list. If user selected 3 new ones, we show 3 new ones.
        // Existing drafts will be fetched by polling merge if we want to show combined history.
        // But `handleFileChange` creates a NEW queue currently.
      });

    } catch (err) {
      console.error("Upload Failed", err);
      setErrorMsg("Batch Upload Failed");
    }
  };

  const handleFileChange = async (e) => {
    const selectedFiles = e.target.files ? Array.from(e.target.files) : [];
    if (selectedFiles.length === 0) return;

    // Create Temporary Queue for Immediate UI Feedback
    const tempQueue = selectedFiles.map(f => ({
      id: "temp-" + Math.random().toString(36),
      file: f,
      status: 'processing',
      previewUrl: URL.createObjectURL(f),
      result: null
    }));

    setFileQueue(tempQueue);
    // runAnalysis will upload and replace these with server IDs
    await runAnalysis(tempQueue);
  };

  const handleQueueSelect = (id) => {
    setSelectedQueueId(id);
  };

  const handleReset = () => {
    setFileQueue([]);
    setSelectedQueueId(null);
    setSuccessMsg(null);
    setErrorMsg(null);
  };

  const handleAnalysisComplete = (data) => {
    // Legacy handler - likely unused now in batch mode unless called manually
    console.warn("Legacy handleAnalysisComplete called");
  };

  const handleError = (msg) => {
    setErrorMsg(msg);
    // This setIsAnalyzing is for the old single-file flow.
    // In batch mode, `isAnalyzing` is derived from `fileQueue.some(f => f.status === 'processing')`
    // so setting it here directly might conflict.
    // For now, let's assume errors are handled per-item in the queue.
    // setIsAnalyzing(false);
  };

  const handleHeaderChange = (field, value) => {
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
  };

  const handleLineItemChange = (index, field, value) => {
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

      // OPTIMISTIC REMOVAL: Remove from Queue immediately
      setFileQueue(prev => {
        const next = prev.filter(item => item.id !== selectedQueueId);
        // Auto-select next item if available
        if (next.length > 0) {
          const nextId = next[0].id;
          // Defer selection update slightly to avoid race or just set it
          setTimeout(() => setSelectedQueueId(nextId), 0);
        } else {
          setSelectedQueueId(null);
        }
        return next;
      });

      // Backend will eventually confirm status -> CONFIRMED so it won't reappear in poll

    } catch (err) {
      console.error(err);
      setErrorMsg("Failed to save invoice. " + (err.response?.data?.detail || err.message));
    } finally {
      setIsSaving(false);
    }
  };

  const handleDiscard = async (invoiceId) => {
    try {
      const { discardInvoice } = await import('./services/api');
      await discardInvoice(invoiceId);

      // Remove from local queue
      setFileQueue(prev => {
        const next = prev.filter(item => item.id !== invoiceId);
        if (selectedQueueId === invoiceId && next.length > 0) {
          setTimeout(() => setSelectedQueueId(next[0].id), 0);
        } else if (next.length === 0) {
          setTimeout(() => setSelectedQueueId(null), 0);
        }
        return next;
      });
    } catch (error) {
      console.error("Failed to discard invoice:", error);
      setErrorMsg("Failed to discard invoice");
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
              fileQueue={fileQueue}
              selectedQueueId={selectedQueueId}
              onQueueSelect={handleQueueSelect}
              previewUrl={previewUrl}
              isAnalyzing={isAnalyzing}
              onFileChange={handleFileChange}
              onReset={handleReset}
              onError={handleError}
              onDiscard={handleDiscard}
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
          {activeTab === 'items' && <ItemMaster />}
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
