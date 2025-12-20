import React from 'react';
import { Image, FileSpreadsheet } from 'lucide-react';

const MobileNavBar = ({ activeTab, onTabChange }) => {
    return (
        <div className="md:hidden fixed bottom-6 left-1/2 -translate-x-1/2 bg-gray-900/90 backdrop-blur-md border border-gray-700/50 rounded-full shadow-2xl z-50 px-2 py-1 flex items-center gap-1">
            <button
                onClick={() => onTabChange('image')}
                className={`flex items-center gap-2 px-4 py-3 rounded-full transition-all ${activeTab === 'image'
                        ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/20'
                        : 'text-gray-400 hover:text-white'
                    }`}
            >
                <Image className="w-5 h-5" />
                <span className="text-sm font-medium">Image</span>
            </button>

            <button
                onClick={() => onTabChange('editor')}
                className={`flex items-center gap-2 px-4 py-3 rounded-full transition-all ${activeTab === 'editor'
                        ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/20'
                        : 'text-gray-400 hover:text-white'
                    }`}
            >
                <FileSpreadsheet className="w-5 h-5" />
                <span className="text-sm font-medium">Data</span>
            </button>
        </div>
    );
};

export default MobileNavBar;
