import React, { useState, useEffect } from 'react';
import { FileText, Clock, ChevronDown, Image, Trash2, AlertTriangle, Loader2, X } from 'lucide-react';
import { getActivityLog, getInvoiceDetails, discardInvoice } from '../../services/api';
import { getImageUrl } from '../../utils/urlHelper';
import AnalysisModal from '../invoice/AnalysisModal';
import { useInvoice } from '../../context/InvoiceContext';

const ActivityHistory = () => {
    const { user } = useInvoice();
    const [activityLog, setActivityLog] = useState([]);
    const [loading, setLoading] = useState(true);
    const [expandedId, setExpandedId] = useState(null);

    // Modal State
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [modalLoading, setModalLoading] = useState(false);
    const [selectedInvoiceData, setSelectedInvoiceData] = useState(null);
    const [selectedLineItems, setSelectedLineItems] = useState(null);
    const [selectedImagePath, setSelectedImagePath] = useState(null);

    // Delete State
    const [confirmDelete, setConfirmDelete] = useState(null); // {id, number, supplier}
    const [isDeleting, setIsDeleting] = useState(false);

    const handleViewInvoice = async (e, item) => {
        e.stopPropagation();
        setModalLoading(true);
        setIsModalOpen(true);
        setSelectedInvoiceData(null);
        setSelectedLineItems([]);

        // Use helper to resolve full URL immediately
        setSelectedImagePath(getImageUrl(item.image_path));

        try {
            const data = await getInvoiceDetails(item.invoice_number);

            // MAP BACKEND (snake_case) -> FRONTEND (PascalCase)
            const rawInvoice = data.invoice || {};
            const mappedInvoice = {
                ...rawInvoice,
                Invoice_No: rawInvoice.invoice_number,
                Invoice_Date: rawInvoice.invoice_date,
                Supplier_Name: rawInvoice.supplier_name,
                Supplier_Phone: rawInvoice.supplier_phone,
                Invoice_Amount: rawInvoice.grand_total,

                // Reconstruct supplier_details for DataEditor
                supplier_details: {
                    Supplier_Name: rawInvoice.supplier_name,
                    GSTIN: rawInvoice.supplier_gst,
                    Address: rawInvoice.supplier_address,
                    DL_No: rawInvoice.supplier_dl,
                    Phone_Number: rawInvoice.supplier_phone,
                    Email: rawInvoice.supplier_email
                },

                // Keep originals just in case
                invoice_number: rawInvoice.invoice_number
            };

            const mappedItems = (data.line_items || []).map(item => ({
                ...item,
                Standard_Item_Name: item.product_name || item.raw_product_name,
                Standard_Quantity: item.quantity,
                Net_Line_Amount: item.net_amount || item.stated_net_amount,
                Batch_No: item.batch_no,
                Expiry_Date: item.expiry_date,
                MRP: item.mrp,
                HSN_Code: item.hsn_code,
                // Pass through boolean flags
                is_price_hike: item.is_price_hike
            }));

            setSelectedInvoiceData(mappedInvoice);
            setSelectedLineItems(mappedItems);

            // Update image path if more accurate one returned
            if (rawInvoice.image_path) {
                setSelectedImagePath(getImageUrl(rawInvoice.image_path));
            }

        } catch (err) {
            console.error("Error fetching invoice details:", err);
            // Optionally set error state or show toast
        } finally {
            setModalLoading(false);
        }
    };

    const handleDelete = async (invoiceId, wipe = true) => {
        setIsDeleting(true);
        try {
            await discardInvoice(invoiceId, wipe);
            // Refresh list
            await fetchActivity();
            setConfirmDelete(null);
        } catch (err) {
            console.error("Failed to delete invoice:", err);
            alert("Failed to delete invoice. Please try again.");
        } finally {
            setIsDeleting(false);
        }
    };

    const formatTimestamp = (timestamp, isExpanded = false) => {
        if (!timestamp) return 'N/A';
        const date = new Date(timestamp);
        const now = new Date();
        const isToday = date.toDateString() === now.toDateString();

        const timeStr = date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
        const dateStr = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

        if (isExpanded) {
            return `${dateStr}, ${timeStr}`;
        }
        return isToday ? timeStr : dateStr;
    };

    useEffect(() => {
        fetchActivity();
    }, []);

    const fetchActivity = async () => {
        try {
            const data = await getActivityLog();

            if (Array.isArray(data)) {
                setActivityLog(data);
            } else {
                setActivityLog([]);
            }
        } catch (err) {
            console.error("Failed to fetch activity log:", err);
        } finally {
            setLoading(false);
        }
    };

    const toggleExpand = (id) => {
        if (expandedId === id) {
            setExpandedId(null);
        } else {
            setExpandedId(id);
        }
    };

    if (loading) return <div className="p-8 text-center text-slate-500">Loading History...</div>;

    const getInitials = (name) => {
        if (!name || name === 'Unknown' || name === 'User') return '??';
        return name.split(' ').map(n => n ? n[0] : '').join('').substring(0, 2).toUpperCase();
    };

    const isAdmin = user?.role === 'Admin';

    return (
        <div className="p-4 md:p-8 max-w-5xl mx-auto h-[calc(100vh-80px)] overflow-y-auto pb-24">
            <h2 className="text-2xl font-bold text-slate-100 mb-6 flex items-center gap-2">
                <Clock className="w-6 h-6 text-blue-500" />
                History
            </h2>

            {/* Delete Confirmation Modal */}
            {confirmDelete && (
                <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
                    <div className="bg-slate-900 border border-red-500/30 rounded-2xl p-6 max-w-md w-full shadow-2xl animate-in zoom-in-95 duration-200">
                        <div className="flex items-center gap-4 mb-4 text-red-500">
                            <div className="p-3 bg-red-500/10 rounded-full">
                                <AlertTriangle className="w-6 h-6" />
                            </div>
                            <h3 className="text-xl font-bold text-slate-100">Deep Wipe Invoice?</h3>
                        </div>
                        
                        <p className="text-slate-400 mb-6 leading-relaxed">
                            This will permanently delete invoice <span className="text-slate-200 font-mono">#{confirmDelete.number}</span> from <span className="text-slate-200 font-semibold">{confirmDelete.supplier}</span>.
                            <br /><br />
                            <span className="text-red-400 font-medium italic">Safety Warning:</span> This also wipes all associated line items and extracted data from your database. This action <b>cannot</b> be undone.
                        </p>

                        <div className="flex gap-3">
                            <button
                                disabled={isDeleting}
                                onClick={() => setConfirmDelete(null)}
                                className="flex-1 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg transition-colors font-medium disabled:opacity-50"
                            >
                                Cancel
                            </button>
                            <button
                                disabled={isDeleting}
                                onClick={() => handleDelete(confirmDelete.id, true)}
                                className="flex-1 px-4 py-2 bg-red-600 hover:bg-red-500 text-white rounded-lg transition-colors font-bold flex items-center justify-center gap-2 disabled:opacity-50"
                            >
                                {isDeleting ? (
                                    <>
                                        <Loader2 className="w-4 h-4 animate-spin" />
                                        Wiping...
                                    </>
                                ) : (
                                    <>
                                        <Trash2 className="w-4 h-4" />
                                        Confirm Wipe
                                    </>
                                )}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            <div className="space-y-3">
                {activityLog.length === 0 ? (
                    <div className="text-center text-slate-500 py-10">No recent activity found.</div>
                ) : (
                    activityLog.map((item, index) => {
                        const isExpanded = expandedId === item.invoice_number;
                        const contactInfo = item.supplier_phone || item.supplier_gst || 'N/A';

                        return (
                            <div key={item.invoice_number} className="bg-slate-900/50 rounded-xl border border-slate-800 overflow-hidden transition-all duration-200 hover:border-slate-700">
                                {/* Main Row */}
                                <div
                                    onClick={() => toggleExpand(item.invoice_number)}
                                    className="flex items-center p-4 cursor-pointer gap-4"
                                >
                                    {/* Sr No */}
                                    <div className="text-slate-500 font-mono text-sm w-6">
                                        {String(index + 1).padStart(2, '0')}
                                    </div>

                                    {/* Supplier Name & Contact */}
                                    <div className="flex-1 min-w-0 flex flex-col justify-center gap-1 pl-2">
                                        <div className="font-semibold text-slate-200 truncate text-base leading-tight">
                                            {item.supplier_name}
                                        </div>

                                        {/* Contact Info - Explicitly on new line, aligned left */}
                                        <div className="flex flex-col items-start gap-1">
                                            {/* Priority: Phone > DL > GST */}
                                            {(() => {
                                                if (item.supplier_phone) {
                                                    return (
                                                        <div className="text-slate-500 text-xs flex items-center gap-1.5">
                                                            <span className="text-slate-600 font-medium">Ph:</span>
                                                            <span className="font-mono text-slate-400">{item.supplier_phone}</span>
                                                        </div>
                                                    );
                                                } else if (item.supplier_dl) {
                                                    return (
                                                        <div className="text-slate-500 text-xs flex items-center gap-1.5">
                                                            <span className="text-slate-600 font-medium">DL:</span>
                                                            <span className="font-mono text-slate-400">{item.supplier_dl}</span>
                                                        </div>
                                                    );
                                                } else if (item.supplier_gst) {
                                                    return (
                                                        <div className="text-slate-500 text-xs flex items-center gap-1.5">
                                                            <span className="text-slate-600 font-medium">GST:</span>
                                                            <span className="font-mono text-slate-400">{item.supplier_gst}</span>
                                                        </div>
                                                    );
                                                }
                                                return null;
                                            })()}
                                        </div>
                                    </div>

                                    {/* Date/Time Display */}
                                    <div className="text-slate-400 text-xs md:text-sm font-medium whitespace-nowrap mr-2">
                                        {formatTimestamp(item.created_at)}
                                    </div>

                                    {/* Expand Icon */}
                                    <div className={`text-slate-500 transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}>
                                        <ChevronDown className="w-5 h-5" />
                                    </div>
                                </div>

                                {/* Expanded Section */}
                                {isExpanded && (
                                    <div className="bg-slate-950/30 border-t border-slate-800 p-4 animate-in slide-in-from-top-2">
                                        <div className="flex flex-wrap items-center justify-between gap-6">

                                            {/* Date */}
                                            <div className="flex flex-col">
                                                <span className="text-[10px] uppercase text-slate-500 font-bold tracking-wider mb-1">Uploaded</span>
                                                <span className="text-slate-300 text-sm font-medium">
                                                    {formatTimestamp(item.created_at, true)}
                                                </span>
                                            </div>

                                            {/* Supplier Details (Expanded) */}
                                            {(item.supplier_dl || item.supplier_address) && (
                                                <div className="flex flex-col max-w-[200px]">
                                                    <span className="text-[10px] uppercase text-slate-500 font-bold tracking-wider mb-1">Supplier Info</span>
                                                    <div className="flex flex-col gap-0.5">
                                                        {item.supplier_dl && (
                                                            <div className="text-[10px] text-slate-400">
                                                                <span className="text-slate-500">DL:</span> {item.supplier_dl}
                                                            </div>
                                                        )}
                                                        {item.supplier_address && (
                                                            <div className="text-[10px] text-slate-400 leading-tight line-clamp-2" title={item.supplier_address}>
                                                                {item.supplier_address}
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>
                                            )}

                                            {/* Saved By */}
                                            <div className="flex flex-col">
                                                <span className="text-[10px] uppercase text-slate-500 font-bold tracking-wider">Saved By</span>
                                                <div className="flex items-center gap-2 mt-0.5">
                                                    <div className="w-5 h-5 rounded-full bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 flex items-center justify-center text-[9px] font-bold">
                                                        {getInitials(item.saved_by)}
                                                    </div>
                                                    <span className="text-slate-300 text-sm font-medium">{item.saved_by || 'Unknown'}</span>
                                                </div>
                                            </div>

                                            {/* Amount */}
                                            <div className="flex flex-col text-right ml-auto mr-4">
                                                <span className="text-[10px] uppercase text-slate-500 font-bold tracking-wider">Amount</span>
                                                <span className="text-emerald-400 font-mono font-medium">
                                                    ₹{item.total?.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                                                </span>
                                            </div>

                                            {/* Actions */}
                                            <div className="flex items-center gap-3 shrink-0">
                                                {/* Delete Button (Admin Only) */}
                                                {isAdmin && (
                                                    <button
                                                        className="w-12 h-12 rounded-full bg-red-600/10 border border-red-600/20 flex items-center justify-center text-red-500 hover:bg-red-600 hover:text-white transition-all shadow-lg shadow-red-900/10 group"
                                                        onClick={(e) => { e.stopPropagation(); setConfirmDelete({ id: item.id, number: item.invoice_number, supplier: item.supplier_name }); }}
                                                        title="Delete Invoice"
                                                    >
                                                        <Trash2 className="w-5 h-5 group-hover:scale-110 transition-transform" />
                                                    </button>
                                                )}

                                                {/* Split Circle Action Icon (View) */}
                                                <button
                                                    className="relative w-12 h-12 rounded-full overflow-hidden shadow-lg hover:scale-105 transition-transform group shrink-0"
                                                    onClick={(e) => handleViewInvoice(e, item)}
                                                    title="View Details"
                                                >
                                                    {/* Left Half - Image Icon */}
                                                    <div className="absolute inset-y-0 left-0 w-1/2 bg-blue-600 flex items-center justify-center text-white">
                                                        <Image className="w-4 h-4" />
                                                    </div>

                                                    {/* Right Half - Bar/Content Icon */}
                                                    <div className="absolute inset-y-0 right-0 w-1/2 bg-indigo-600 flex items-center justify-center text-white">
                                                        <FileText className="w-4 h-4" />
                                                    </div>

                                                    {/* Divisive Line */}
                                                    <div className="absolute inset-y-0 left-1/2 w-px bg-white/20"></div>

                                                    {/* Shine Effect */}
                                                    <div className="absolute inset-0 bg-white/10 opacity-0 group-hover:opacity-100 transition-opacity" />
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        );
                    })
                )}
            </div>

            <AnalysisModal
                isOpen={isModalOpen}
                onClose={() => setIsModalOpen(false)}
                isLoading={modalLoading}
                invoiceData={selectedInvoiceData}
                lineItems={selectedLineItems}
                imagePath={selectedImagePath}
            />
        </div>
    );
};

export default ActivityHistory;
