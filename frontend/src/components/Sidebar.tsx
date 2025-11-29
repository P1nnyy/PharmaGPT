import React from 'react';
import { motion } from 'framer-motion';
import {
    Home,
    Box,
    FileText,
    Settings,
    User,
    Camera
} from 'lucide-react';

interface SidebarProps {
    onScanClick: () => void;
    activeTab: string;
    onNavigate: (tab: string) => void;
}

const Sidebar: React.FC<SidebarProps> = ({ onScanClick, activeTab, onNavigate }) => {
    // Mock data for recent scans
    const recentScans = [
        { id: 1, name: "Apollo Pharma #992" },
        { id: 2, name: "MediPlus Inv-2023" },
        { id: 3, name: "GSK Batch A-12" },
        { id: 4, name: "SunPharma Order" },
        { id: 5, name: "Cipla Stock #44" },
    ];

    return (
        <div className="fixed left-0 top-0 h-screen w-64 flex flex-col border-r border-white/5 bg-black/40 backdrop-blur-2xl text-white font-sans z-50">

            {/* Part A: Primary Action */}
            <div className="p-6 pb-4">
                <button
                    onClick={onScanClick}
                    className="group relative w-full flex items-center justify-center gap-2 rounded-full bg-gradient-to-r from-purple-600 to-blue-600 py-3 px-4 font-medium text-white shadow-lg transition-all hover:shadow-purple-500/25 hover:scale-[1.02] active:scale-[0.98] cursor-pointer"
                >
                    <Camera className="h-5 w-5" />
                    <span>Scan Bill</span>
                </button>
            </div>

            {/* Part B: Core Navigation */}
            <nav className="flex-none px-4 space-y-1">
                <NavItem
                    icon={<Home size={20} />}
                    label="Home"
                    id="home"
                    active={activeTab === 'home'}
                    onClick={onNavigate}
                />
                <NavItem
                    icon={<Box size={20} />}
                    label="Inventory"
                    id="inventory"
                    active={activeTab === 'inventory'}
                    onClick={onNavigate}
                />
                <NavItem
                    icon={<FileText size={20} />}
                    label="Invoices"
                    id="invoices"
                    active={activeTab === 'invoices'}
                    onClick={onNavigate}
                />
            </nav>

            {/* Part C: History Rail */}
            <div className="flex-1 overflow-y-auto py-6 px-4">
                <div className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-500">
                    Recent Scans
                </div>
                <div className="space-y-1">
                    {recentScans.map((scan, index) => (
                        <motion.div
                            key={scan.id}
                            initial={{ opacity: 0, x: -10 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: index * 0.1, duration: 0.3 }}
                            className="cursor-pointer rounded-lg px-3 py-2 text-sm text-gray-300 hover:bg-white/5 hover:text-white transition-colors"
                        >
                            {scan.name}
                        </motion.div>
                    ))}
                </div>
            </div>

            {/* Part D: Utility Footer */}
            <div className="flex-none border-t border-white/5 p-4">
                <div className="flex items-center justify-between px-2">
                    <button
                        onClick={() => onNavigate('settings')}
                        className={`rounded-lg p-2 transition-colors ${activeTab === 'settings' ? 'bg-white/10 text-white' : 'text-gray-400 hover:bg-white/5 hover:text-white'}`}
                    >
                        <Settings size={20} />
                    </button>
                    <button
                        onClick={() => onNavigate('profile')}
                        className={`rounded-full bg-gray-800 p-2 transition-colors ${activeTab === 'profile' ? 'text-white ring-2 ring-white/20' : 'text-gray-400 hover:text-white'}`}
                    >
                        <User size={20} />
                    </button>
                </div>
            </div>
        </div>
    );
};

// Helper Component for Nav Items
interface NavItemProps {
    icon: React.ReactNode;
    label: string;
    id: string;
    active?: boolean;
    onClick: (id: string) => void;
}

const NavItem: React.FC<NavItemProps> = ({ icon, label, id, active = false, onClick }) => {
    return (
        <button
            onClick={() => onClick(id)}
            className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all cursor-pointer ${active
                ? 'bg-white/10 text-white'
                : 'text-gray-400 hover:bg-white/5 hover:text-white'
                }`}
        >
            {icon}
            {label}
        </button>
    );
};

export default Sidebar;
