import React from 'react';
import { ScanLine, Clock, Files, Package, Settings, LogOut } from 'lucide-react';

const Sidebar = ({ activeTab, onTabChange, isMobile, isOpen, onClose }) => {
    const [isCollapsed, setIsCollapsed] = React.useState(false);

    // Initial check for mobile to prevent weird state
    const isDrawerOpen = isMobile ? isOpen : true;

    // Auto-close on mobile when tab changes
    const handleTabClick = (id) => {
        onTabChange(id);
        if (isMobile && onClose) onClose();
    };

    const menuItems = [
        { id: 'scan', label: 'Scan Invoice', icon: ScanLine },
        { id: 'history', label: 'History', icon: Clock },
        { id: 'invoices', label: 'Invoices', icon: Files },
        { id: 'inventory', label: 'Inventory', icon: Package },
    ];

    return (
        <>
            {/* Mobile Overlay */}
            {isMobile && isOpen && (
                <div
                    className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[45]"
                    onClick={onClose}
                />
            )}

            <div
                className={`flex flex-col h-full bg-slate-900 border-r border-slate-800 shadow-xl z-50 transition-all duration-300
                    ${isMobile ? 'fixed inset-y-0 left-0 w-[280px]' : 'hidden md:flex relative'}
                    ${!isMobile && isCollapsed ? 'w-20' : ''}
                    ${!isMobile && !isCollapsed ? 'w-64' : ''}
                    ${isMobile && !isOpen ? '-translate-x-full' : 'translate-x-0'}
                `}
            >
                {/* Logo Area */}
                <div className="p-4 border-b border-slate-800 flex items-center justify-between">
                    {(!isCollapsed || isMobile) && (
                        <div className="flex items-center gap-3">
                            <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center text-white font-bold text-lg shadow-blue-500/20">
                                P
                            </div>
                            <span className="font-bold text-slate-100 text-lg tracking-tight">PharmaCouncil</span>
                        </div>
                    )}
                    {!isMobile && isCollapsed && (
                        <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center text-white font-bold text-lg mx-auto">
                            P
                        </div>
                    )}

                    {/* Toggle Button (Desktop Only) */}
                    {!isMobile && (
                        <button
                            onClick={() => setIsCollapsed(!isCollapsed)}
                            className="text-slate-400 hover:text-white p-1 rounded hover:bg-slate-800 transition-colors"
                        >
                            <div className="space-y-1">
                                <div className="w-5 h-0.5 bg-current"></div>
                                <div className="w-5 h-0.5 bg-current"></div>
                                <div className="w-5 h-0.5 bg-current"></div>
                            </div>
                        </button>
                    )}
                </div>

                {/* Navigation */}
                <nav className="flex-1 p-3 space-y-2 overflow-y-auto mt-2">
                    {(!isCollapsed || isMobile) && (
                        <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2 px-3">
                            Menu
                        </div>
                    )}

                    {menuItems.map((item) => {
                        const Icon = item.icon;
                        const isActive = activeTab === item.id;

                        return (
                            <button
                                key={item.id}
                                onClick={() => handleTabClick(item.id)}
                                className={`w-full flex items-center gap-3 px-3 py-3 rounded-xl text-sm font-medium transition-all duration-200 group relative
                                    ${isActive
                                        ? 'bg-blue-600/10 text-blue-400'
                                        : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
                                    }
                                    ${!isMobile && isCollapsed ? 'justify-center' : ''}
                                `}
                                title={(!isMobile && isCollapsed) ? item.label : ''}
                            >
                                <Icon
                                    className={`w-5 h-5 transition-colors ${isActive ? 'text-blue-400' : 'text-slate-400 group-hover:text-slate-200'}`}
                                    strokeWidth={isActive ? 2.5 : 2}
                                />
                                {(!isCollapsed || isMobile) && <span>{item.label}</span>}

                                {/* Active Indicator Line */}
                                {isActive && (!isCollapsed || isMobile) && (
                                    <div className="absolute right-0 top-1/2 -translate-y-1/2 w-1 h-8 bg-blue-500 rounded-l-full"></div>
                                )}
                            </button>
                        );
                    })}
                </nav>

                {/* Bottom Actions */}
                <div className="p-3 border-t border-slate-800 mt-auto">
                    <button
                        onClick={() => handleTabClick('settings')}
                        className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 group mb-1
                            ${activeTab === 'settings'
                                ? 'bg-slate-800 text-slate-200'
                                : 'text-slate-500 hover:bg-slate-800 hover:text-slate-300'
                            }
                            ${!isMobile && isCollapsed ? 'justify-center' : ''}
                        `}
                        title="Settings"
                    >
                        <Settings className="w-5 h-5 text-slate-500 group-hover:text-slate-300" />
                        {(!isCollapsed || isMobile) && <span>Settings</span>}
                    </button>

                    {/* User Profile / Logout Placeholder */}
                    <div className={`mt-4 flex items-center gap-3 px-2 py-2 border-t border-slate-800/50 pt-4 ${!isMobile && isCollapsed ? 'justify-center' : ''}`}>
                        <div className="w-8 h-8 rounded-full bg-slate-700 flex items-center justify-center text-slate-300 text-xs font-bold border border-slate-600">
                            PG
                        </div>
                        {(!isCollapsed || isMobile) && (
                            <>
                                <div className="flex-1 min-w-0 text-left">
                                    <p className="text-xs font-medium text-slate-200 truncate">Pranav Gupta</p>
                                    <p className="text-[10px] text-slate-500 truncate">Admin</p>
                                </div>
                                <button className="text-slate-500 hover:text-rose-400 transition-colors">
                                    <LogOut className="w-4 h-4" />
                                </button>
                            </>
                        )}
                    </div>
                </div>
            </div>
        </>
    );
};

export default Sidebar;
