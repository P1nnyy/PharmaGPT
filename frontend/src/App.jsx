import { useState, useEffect, lazy, Suspense } from 'react';
import { Loader2 } from 'lucide-react';
import Toast from './components/ui/Toast';
import { InvoiceProvider, useInvoice } from './context/InvoiceContext';
import { getUserProfile, setAuthToken } from './services/api';

// Static Layout Components
import Sidebar from './components/layout/Sidebar';
import MobileHeader from './components/layout/MobileHeader';
import InvoiceViewer from './components/invoice/InvoiceViewer';
import DataEditor from './components/invoice/DataEditor';
import Login from './components/Login';

// Lazy Loaded Dashboards
const InventoryView = lazy(() => import('./components/dashboard/Inventory'));
const ActivityHistory = lazy(() => import('./components/dashboard/ActivityHistory'));
const GroupedInvoices = lazy(() => import('./components/dashboard/GroupedInvoices'));
const ItemMaster = lazy(() => import('./components/items/ItemMaster'));
const AdminDashboard = lazy(() => import('./components/dashboard/AdminDashboard'));

function AppContent() {
  const [activeTab, setActiveTab] = useState('scan');
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);

  const {
    activeQueueItem,
    user,
    setUser,
    isLoadingAuth,
    setIsLoadingAuth,
    toast,
    setFileQueue,
    recentlySavedIds
  } = useInvoice();

  const invoiceData = activeQueueItem?.result?.invoice_data || null;

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // --- Auth Initialization ---
  useEffect(() => {
    const initAuth = async () => {
      const params = new URLSearchParams(window.location.search);
      const tokenFromUrl = params.get('token');

      if (tokenFromUrl) {
        setAuthToken(tokenFromUrl);
        window.history.replaceState({}, document.title, window.location.pathname);
      }

      try {
        const savedToken = localStorage.getItem('auth_token');
        if (savedToken) {
          setAuthToken(savedToken);
          const profile = await getUserProfile();
          setUser(profile);
        }
      } catch (err) {
        setAuthToken(null);
        setUser(null);
      } finally {
        setIsLoadingAuth(false);
      }
    };
    initAuth();
  }, [setUser, setIsLoadingAuth]);

  // --- SSE Integration (Replaces Polling) ---
  useEffect(() => {
    if (isLoadingAuth || !user) return;

    let eventSource;
    const connectSSE = () => {
      const token = localStorage.getItem('auth_token');
      eventSource = new EventSource(`${import.meta.env.VITE_API_BASE_URL || ''}/invoices/stream-status?token=${token}`);

      eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'update') {
          setFileQueue(prevQueue => {
            const serverItems = data.drafts
              .filter(d => !recentlySavedIds.has(d.id))
              .map(d => ({
                id: d.id,
                file: d.file,
                status: d.status === 'draft' ? (d.is_duplicate ? 'duplicate' : 'completed') : d.status,
                previewUrl: d.previewUrl,
                result: d.result,
                error: d.error,
                warning: d.duplicate_warning
              }));

            return prevQueue.filter(item => item.id.toString().startsWith('temp-')).concat(serverItems)
              .sort((a, b) => {
                const score = (s) => (s === 'completed' || s === 'duplicate' ? 3 : s === 'processing' ? 2 : 1);
                return score(b.status) - score(a.status);
              });
          });
        }
      };

      eventSource.onerror = () => {
        eventSource.close();
        setTimeout(connectSSE, 5000);
      };
    };

    connectSSE();
    return () => eventSource?.close();
  }, [isLoadingAuth, user, setFileQueue, recentlySavedIds]);

  if (isLoadingAuth) {
    return (
      <div className="h-screen bg-slate-950 flex items-center justify-center">
        <Loader2 className="w-10 h-10 text-indigo-500 animate-spin" />
      </div>
    );
  }

  if (!user) return <Login />;

  const handleTabChange = (tab) => setActiveTab(tab);

  return (
    <div className="flex bg-slate-50 h-screen font-sans selection:bg-blue-200 selection:text-blue-900 overflow-hidden">
      {isMobile && (
        <MobileHeader
          onMenuClick={() => setIsSidebarOpen(true)}
          onCameraClick={() => setActiveTab('scan')}
        />
      )}

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

      <div className={`flex-1 flex flex-col h-full overflow-hidden bg-slate-950 text-slate-200 ${isMobile ? 'pt-[60px]' : ''}`}>
        <h1 className="sr-only">PharmaGPT Dashboard - Scan Invoice</h1>

        <div className={`flex flex-col md:flex-row h-full w-full ${activeTab !== 'scan' ? 'hidden' : 'flex'}`}>
          <div className={`w-full md:w-1/2 flex flex-col relative transition-all duration-300 border-b md:border-b-0 md:border-r border-slate-800
                    ${isMobile && activeTab !== 'scan' ? 'hidden' : 'flex'}
                    ${isMobile && invoiceData ? 'h-[35%]' : 'h-full'} 
                `}>
            <InvoiceViewer isMobile={isMobile} />
          </div>

          <div className={`w-full md:w-1/2 flex flex-col bg-slate-900/50 border-l border-slate-800 overflow-y-auto
                    ${isMobile && activeTab === 'scan' && !invoiceData ? 'hidden' : 'flex'} 
                    ${isMobile && activeTab !== 'scan' ? 'flex h-full' : ''}
                    ${isMobile && activeTab === 'scan' && invoiceData ? 'h-[65%]' : 'h-full'}
                `}>
            {invoiceData && <DataEditor isMobile={isMobile} />}
            {!invoiceData && !isMobile && (
              <div className="flex-1 flex items-center justify-center text-slate-600">
                <div className="text-center">
                  <p>Upload an invoice to see details here.</p>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="flex-1 overflow-auto bg-slate-900 border-t border-slate-800 md:border-t-0 p-4">
          <Suspense fallback={
            <div className="flex items-center justify-center h-64">
              <Loader2 className="w-8 h-8 text-indigo-500 animate-spin" />
            </div>
          }>
            {activeTab === 'history' && <ActivityHistory />}
            {activeTab === 'inventory' && <InventoryView />}
            {activeTab === 'invoices' && <GroupedInvoices />}
            {activeTab === 'items' && <ItemMaster />}
            {activeTab === 'admin' && <AdminDashboard />}
          </Suspense>

          {activeTab === 'settings' && (
            <div className="p-8 text-center text-slate-500">
              <h2 className="text-xl text-slate-300 mb-2">Settings</h2>
              <p>Configure app preferences here.</p>
              <div className="mt-8 p-4 bg-slate-800 rounded-lg text-xs font-mono text-left inline-block">
                <div className="mb-2 text-indigo-400">DEBUG INFO:</div>
                <div>SSE: Connected</div>
                <div>Version: v6.0 (Optimized)</div>
              </div>
            </div>
          )}
        </div>
      </div>

      <Toast
        show={toast.show}
        message={toast.message}
        type={toast.type}
        onClose={() => {}}
      />
    </div>
  );
}

function App() {
  return (
    <InvoiceProvider>
      <AppContent />
    </InvoiceProvider>
  );
}

export default App;
