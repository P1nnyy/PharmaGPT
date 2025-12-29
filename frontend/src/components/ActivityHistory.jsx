import React, { useState, useEffect } from 'react';
import { FileText, ArrowUpRight } from 'lucide-react';

const ActivityHistory = () => {
    const [logs, setLogs] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchActivity();
    }, []);

    const fetchActivity = async () => {
        try {
            const API_BASE_URL = window.location.hostname.includes('pharmagpt.co')
                ? 'https://api.pharmagpt.co'
                : 'http://localhost:8000';

            const res = await fetch(`${API_BASE_URL}/activity-log`);
            const data = await res.json();
            if (Array.isArray(data)) {
                setLogs(data);
            } else {
                setLogs([]);
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    if (loading) {
        return <div className="p-8 text-center text-slate-500">Loading activity...</div>;
    }

    return (
        <div className="p-8 max-w-6xl mx-auto">
            <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-bold text-slate-100">Activity Log</h2>
                <div className="text-sm text-slate-400">
                    Showing last {logs.length} entries
                </div>
            </div>

            <div className="bg-slate-900/50 rounded-xl shadow-xl border border-slate-800 overflow-hidden backdrop-blur-sm">
                <table className="w-full text-left text-sm">
                    <thead>
                        <tr className="bg-slate-900 text-slate-400 font-medium border-b border-slate-800">
                            <th className="px-6 py-4 w-32">Status</th>
                            <th className="px-6 py-4">Invoice #</th>
                            <th className="px-6 py-4">Supplier</th>
                            <th className="px-6 py-4">Date Uploaded</th>
                            <th className="px-6 py-4 text-right">Amount</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/50">
                        {logs.length === 0 ? (
                            <tr>
                                <td colSpan="5" className="px-6 py-12 text-center text-slate-500">
                                    No activity found.
                                </td>
                            </tr>
                        ) : (
                            logs.map((log, idx) => (
                                <tr key={idx} className="hover:bg-slate-800/30 transition-colors group">
                                    <td className="px-6 py-4">
                                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border
                                            ${log.status === 'CONFIRMED'
                                                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                                                : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                                            }`}>
                                            {log.status === 'CONFIRMED' ? 'Confirmed' : 'Review'}
                                        </span>
                                    </td>
                                    <td className="px-6 py-4 font-mono text-slate-300">
                                        {log.invoice_number}
                                    </td>
                                    <td className="px-6 py-4 font-medium text-slate-200">
                                        {log.supplier_name}
                                    </td>
                                    <td className="px-6 py-4 text-slate-400">
                                        {/* Format timestamp if available, else date string */}
                                        {log.created_at
                                            ? new Date(log.created_at).toLocaleDateString('en-IN', {
                                                day: 'numeric', month: 'short', year: 'numeric',
                                                hour: '2-digit', minute: '2-digit'
                                            })
                                            : log.date}
                                    </td>
                                    <td className="px-6 py-4 text-right font-medium text-slate-100">
                                        ₹{log.total?.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                                    </td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export default ActivityHistory;
