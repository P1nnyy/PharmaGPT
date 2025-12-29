import React from 'react';
import { Menu, Camera } from 'lucide-react';

const MobileHeader = ({ onMenuClick, onCameraClick }) => {
    return (
        <div className="h-[60px] bg-slate-900 border-b border-slate-800 flex items-center justify-between px-4 fixed top-0 left-0 right-0 z-40 shadow-md">
            {/* Left: Hamburger Menu */}
            <button
                onClick={onMenuClick}
                className="p-2 -ml-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors"
                aria-label="Open Menu"
            >
                <Menu className="w-6 h-6" />
            </button>

            {/* Center: Logo / Title */}
            <div className="flex items-center gap-2">
                <div className="w-6 h-6 bg-blue-600 rounded flex items-center justify-center text-white font-bold text-xs shadow-blue-500/20">
                    P
                </div>
                <h1 className="text-lg font-bold text-slate-100 tracking-tight">PharmaCouncil</h1>
            </div>

            {/* Right: Camera Action */}
            <button
                onClick={onCameraClick}
                className="p-2 -mr-2 text-blue-400 hover:text-blue-300 hover:bg-blue-500/10 rounded-lg transition-colors"
                aria-label="New Scan"
            >
                <Camera className="w-6 h-6" />
            </button>
        </div>
    );
};

export default MobileHeader;
