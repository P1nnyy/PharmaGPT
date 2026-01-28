import React from 'react';
import { CheckCircle2, XCircle, AlertCircle } from 'lucide-react';

const Toast = ({ show, message, type, onClose }) => {
    if (!show) return null;

    const bgColors = {
        success: 'bg-green-500/10 border-green-500/20 text-green-400',
        error: 'bg-red-500/10 border-red-500/20 text-red-400',
        warning: 'bg-yellow-500/10 border-yellow-500/20 text-yellow-400'
    };

    const icons = {
        success: <CheckCircle2 className="w-5 h-5 text-green-400" />,
        error: <XCircle className="w-5 h-5 text-red-400" />,
        warning: <AlertCircle className="w-5 h-5 text-yellow-400" />
    };

    return (
        <div className="fixed bottom-6 right-6 z-50 animate-in slide-in-from-bottom-5 fade-in duration-300">
            <div className={`flex items-center gap-3 px-4 py-3 rounded-xl border backdrop-blur-md shadow-2xl ${bgColors[type] || bgColors.success}`}>
                {icons[type] || icons.success}
                <span className="font-medium text-sm">{message}</span>
            </div>
        </div>
    );
};

export default Toast;
