import { useState, useEffect, lazy, Suspense } from 'react';
import { Loader2, Mail, Check, X } from 'lucide-react';
import Toast from './components/ui/Toast';
import { InvoiceProvider, useInvoice } from './context/InvoiceContext';
import { getUserProfile, setAuthToken, getInvitations, acceptInvitation } from './services/api';

// Static Layout Components
import Sidebar from './components/layout/Sidebar';
import MobileHeader from './components/layout/MobileHeader';
import MobileNavBar from './components/layout/MobileNavBar';
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
  const [invitations, setInvitations] = useState([]);

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

  // --- UI Bouncer: Role Protection ---
  useEffect(() => {
    const adminTabs = ['admin', 'items', 'inventory'];
    if (user && user.role !== 'Admin' && adminTabs.includes(activeTab)) {
      console.warn(`Unauthorized access attempt to ${activeTab}. Redirecting...`);
      setActiveTab('scan');
    }
  }, [activeTab, user]);

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
          
          // Fetch invitations if user exists
          const pending = await getInvitations();
          setInvitations(pending);
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

  const handleAcceptInvite = async (inviteId) => {
    try {
      await acceptInvitation(inviteId);
      setInvitations(prev => prev.filter(inv => inv.id !== inviteId));
      // Refresh profile to get new role
      const profile = await getUserProfile();
      setUser(profile);
    } catch (err) {
      console.error("Failed to accept invitation", err);
    }
  };

  // --- SSE Integration is now handled in InvoiceContext ---

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

      {isMobile && (
        <MobileNavBar 
          activeTab={activeTab} 
          onTabChange={setActiveTab} 
          onCameraClick={() => setActiveTab('scan')}
          user={user}
        />
      )}

      {/* Invitations Overlay */}
      {invitations && invitations.length > 0 && invitations[0] && invitations[0].id && (
        <div className="fixed inset-0 z-[100] bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 max-w-md w-full shadow-2xl animate-in fade-in zoom-in duration-300">
            <div className="w-12 h-12 bg-blue-500/10 border border-blue-500/20 rounded-full flex items-center justify-center mb-4">
              <Mail className="w-6 h-6 text-blue-400" />
            </div>
            <h2 className="text-xl font-bold text-white mb-2">Join Organization</h2>
            <p className="text-slate-400 text-sm mb-6">
              You have been invited to join <strong>PharmaGPT</strong> with the role of <strong>{invitations[0].role || 'Member'}</strong>.
            </p>
            <div className="flex flex-col gap-3">
              <button
                onClick={() => handleAcceptInvite(invitations[0].id)}
                className="w-full bg-blue-600 hover:bg-blue-500 text-white font-semibold py-3 rounded-xl transition-all flex items-center justify-center gap-2"
              >
                <Check className="w-5 h-5" /> Accept Invitation
              </button>
              <button
                onClick={() => setInvitations([])}
                className="w-full bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold py-3 rounded-xl transition-all flex items-center justify-center gap-2"
              >
                <X className="w-5 h-5" /> Later
              </button>
            </div>
            <p className="text-[10px] text-slate-500 mt-4 text-center">
              Invited by: {invitations[0].inviter_name || invitations[0].inviter_email || 'System'}
            </p>
          </div>
        </div>
      )}
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
