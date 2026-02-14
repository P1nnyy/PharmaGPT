import React from 'react';

export const InputField = ({ label, name, type = 'text', icon = null, placeholder = '', value, onChange, className = '', inputClassName = '' }) => (
    <div className={`space-y-1 ${className}`}>
        <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1">
            {icon} {label}
        </label>
        <input
            type={type}
            name={name}
            value={value}
            onChange={onChange}
            placeholder={placeholder}
            className={`w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none transition-colors ${inputClassName}`}
        />
    </div>
);
