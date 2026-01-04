import React, { useState, useEffect } from 'react';
import { FileText, Clock, ChevronDown, Image } from 'lucide-react';
import { getActivityLog, getInvoiceDetails } from '../../services/api';
import AnalysisModal from '../invoice/AnalysisModal';

const ActivityHistory = () => {
    const [activityLog, setActivityLog] = useState([]);
    const [loading, setLoading] = useState(true);
    const [expandedIds, setExpandedIds] = useState(new Set());

    // Modal State
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [modalLoading, setModalLoading] = useState(false);
    const [selectedInvoiceData, setSelectedInvoiceData] = useState(null);
    const [selectedLineItems, setSelectedLineItems] = useState([]);
    const [selectedImagePath, setSelectedImagePath] = useState(null);

    const handleViewInvoice = async (e, item) => {
        e.stopPropagation();
        setModalLoading(true);
        setIsModalOpen(true);
        setSelectedInvoiceData(null);
        setSelectedLineItems([]);
        setSelectedImagePath(item.image_path); // Use path from list initially

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

            // Update image path if more accurate one returned (though list usually has it)
            if (rawInvoice.image_path) setSelectedImagePath(rawInvoice.image_path);

        } catch (err) {
            console.error("Error fetching invoice details:", err);
            // Optionally set error state or show toast
        } finally {
            setModalLoading(false);
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
        const newExpanded = new Set(expandedIds);
        if (newExpanded.has(id)) {
            newExpanded.delete(id);
        } else {
            newExpanded.add(id);
        }
        setExpandedIds(newExpanded);
    };

    if (loading) return <div className="p-8 text-center text-slate-500">Loading History...</div>;

    return (
        <div className="p-4 md:p-8 max-w-5xl mx-auto h-[calc(100vh-80px)] overflow-y-auto pb-24">
            <h2 className="text-2xl font-bold text-slate-100 mb-6 flex items-center gap-2">
                <Clock className="w-6 h-6 text-blue-500" />
                History
            </h2>

            <div className="space-y-3">
                {activityLog.length === 0 ? (
                    <div className="text-center text-slate-500 py-10">No recent activity found.</div>
                ) : (
                    activityLog.map((item, index) => {
                        const isExpanded = expandedIds.has(item.invoice_number);
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
                                                        PG
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

                                            {/* Split Circle Action Icon */}
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
