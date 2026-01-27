import React from 'react';

export const ItemHistory = ({ history, loading }) => {
    return (
        <div className="animate-in fade-in slide-in-from-bottom-2 duration-300">
            <div className="bg-slate-900/50 rounded-xl border border-slate-700 overflow-hidden">
                <table className="w-full text-left text-xs text-slate-300">
                    <thead className="bg-slate-800 text-slate-500 font-bold uppercase">
                        <tr>
                            <th className="px-4 py-3">Date</th>
                            <th className="px-4 py-3">Supplier</th>
                            <th className="px-4 py-3 text-right">Qty</th>
                            <th className="px-4 py-3 text-right">Rate</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-700/50">
                        {loading ? (
                            <tr><td colSpan="4" className="p-4 text-center text-slate-500">Loading...</td></tr>
                        ) : history.length === 0 ? (
                            <tr><td colSpan="4" className="p-4 text-center text-slate-500">No Purchase History</td></tr>
                        ) : (
                            history.map((h, i) => (
                                <tr key={i} className="hover:bg-slate-800/50">
                                    <td className="px-4 py-2">{h.date}</td>
                                    <td className="px-4 py-2">{h.supplier}</td>
                                    <td className="px-4 py-2 text-right">{h.quantity}</td>
                                    <td className="px-4 py-2 text-right text-emerald-400">₹{h.amount}</td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
};
