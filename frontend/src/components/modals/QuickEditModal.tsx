import React, { useState, useEffect } from 'react';
import { X, Save } from 'lucide-react';

interface QuickEditModalProps {
    isOpen: boolean;
    onClose: () => void;
    title: string;
    currentValue: number;
    onSave: (newValue: number) => void;
    unit?: string;
}

export const QuickEditModal: React.FC<QuickEditModalProps> = ({
    isOpen,
    onClose,
    title,
    currentValue,
    onSave,
    unit
}) => {
    const [value, setValue] = useState(currentValue);

    useEffect(() => {
        setValue(currentValue);
    }, [currentValue, isOpen]);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        onSave(value);
        onClose();
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
            <div className="w-full max-w-sm bg-[#1a1a1a] border border-white/10 rounded-xl shadow-2xl p-6 animate-in fade-in zoom-in duration-200">
                <div className="flex justify-between items-center mb-6">
                    <h3 className="text-lg font-semibold text-white">{title}</h3>
                    <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors">
                        <X size={20} />
                    </button>
                </div>

                <form onSubmit={handleSubmit}>
                    <div className="mb-6">
                        <div className="relative">
                            <input
                                type="number"
                                value={value}
                                onChange={(e) => setValue(parseFloat(e.target.value) || 0)}
                                className="w-full bg-white/5 border border-white/10 rounded-lg pl-4 pr-16 py-3 text-2xl font-bold text-center text-white focus:outline-none focus:border-blue-500 transition-colors"
                                autoFocus
                                step="any"
                            />
                            {unit && (
                                <span className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-500 text-sm font-medium">
                                    {unit}
                                </span>
                            )}
                        </div>
                    </div>

                    <div className="flex gap-3">
                        <button
                            type="button"
                            onClick={onClose}
                            className="flex-1 px-4 py-2 rounded-lg text-sm font-medium text-gray-400 hover:bg-white/5 transition-colors"
                        >
                            Cancel
                        </button>
                        <button
                            type="submit"
                            className="flex-1 px-4 py-2 rounded-lg text-sm font-medium bg-blue-600 text-white hover:bg-blue-500 transition-colors flex items-center justify-center gap-2"
                        >
                            <Save size={16} />
                            Update
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};
