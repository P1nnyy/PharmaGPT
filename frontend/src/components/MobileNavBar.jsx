import React from 'react';
import { LayoutGrid, Camera, Settings, History, Package } from 'lucide-react';

const NavButton = ({ icon: Icon, label, active, onClick }) => (
    <button
        onClick={onClick}
        className={`flex flex-col items-center gap-1 p-2 transition-colors ${active ? 'text-indigo-400' : 'text-slate-500 hover:text-slate-300'
            }`}
    >
        <Icon className={`w-6 h-6 ${active ? 'fill-current/10' : ''}`} />
        <span className="text-[10px] font-medium">{label}</span>
    </button>
);

const MobileNavBar = ({ activeTab, onTabChange, onCameraClick }) => {
    return (
        <div className="h-[60px] bg-slate-900 border-t border-slate-800 flex justify-around items-center px-2 z-[999] fixed bottom-0 left-0 right-0 shadow-2xl">

            <NavButton
                icon={LayoutGrid}
                label="Invoice"
                active={activeTab === 'invoice'}
                onClick={() => onTabChange('invoice')}
            />

            <NavButton
                icon={History}
                label="History"
                active={activeTab === 'history'}
                onClick={() => onTabChange('history')}
            />

            <div className="relative -top-5">
                <button
                    onClick={onCameraClick}
                    className="bg-indigo-500 hover:bg-indigo-600 text-white p-4 rounded-full shadow-lg shadow-indigo-500/20 transition-all active:scale-95"
                >
                    <Camera className="w-6 h-6" />
                </button>
            </div>

            <NavButton
                icon={Package}
                label="Inventory"
                active={activeTab === 'inventory'}
                onClick={() => onTabChange('inventory')}
            />

            <NavButton
                icon={Settings}
                label="More"
                active={activeTab === 'settings'}
                onClick={() => onTabChange('settings')}
            />
        </div>
    );
};

export default MobileNavBar;
