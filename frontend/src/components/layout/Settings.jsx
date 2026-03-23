import React, { useState } from 'react';
import { Settings as SettingsIcon, LogOut, Store, Shield, User, Info, AlertTriangle, Loader2 } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import axios from 'axios';

const Settings = () => {
    const { user, setUser } = useAuth();
    const { showToast } = useToast();
    const [isLeaving, setIsLeaving] = useState(false);

    const handleLeaveShop = async () => {
        if (!window.confirm(`Are you sure you want to leave ${user?.shop_name}? You will lose access to this shop's data until re-invited.`)) {
            return;
        }

        setIsLeaving(true);
        try {
            const token = localStorage.getItem('auth_token');
            await axios.post(`${import.meta.env.VITE_API_BASE_URL || ''}/auth/leave-shop`, {}, {
                headers: { Authorization: `Bearer ${token}` }
            });
            
            showToast("Successfully left the shop.", "success");
            
            // Refresh profile to update UI state (Back to Personal Workspace)
            const { getUserProfile } = await import('../../services/api');
            const profile = await getUserProfile();
            setUser(profile);
        } catch (err) {
            console.error(err);
            showToast(err.response?.data?.detail || "Failed to leave shop", "error");
        } finally {
            setIsLeaving(false);
        }
    };

    const isPersonal = user?.shop_id === 'personal' || !user?.shop_id;

    return (
        <div className="max-w-4xl mx-auto py-8 px-4">
            <div className="flex items-center gap-4 mb-8">
                <div className="p-3 bg-indigo-500/10 rounded-2xl border border-indigo-500/20">
                    <SettingsIcon className="w-8 h-8 text-indigo-400" />
                </div>
                <div>
                    <h1 className="text-3xl font-bold text-white">Settings</h1>
                    <p className="text-slate-400">Manage your account and workspace preferences.</p>
                </div>
            </div>

            <div className="grid gap-6">
                {/* Account Section */}
                <section className="bg-slate-900/50 border border-slate-800 rounded-2xl overflow-hidden shadow-sm">
                    <div className="p-6 border-b border-slate-800 flex items-center gap-3">
                        <User className="w-5 h-5 text-slate-400" />
                        <h2 className="text-lg font-semibold text-white">Account Profile</h2>
                    </div>
                    <div className="p-6 flex flex-col md:flex-row items-center gap-6">
                        <div className="relative">
                            {user?.picture ? (
                                <img src={user.picture} alt="Avatar" className="w-20 h-20 rounded-full border-2 border-indigo-500/30 p-1" />
                            ) : (
                                <div className="w-20 h-20 rounded-full bg-slate-800 flex items-center justify-center text-2xl font-bold text-slate-400 border-2 border-slate-700">
                                    {user?.name?.charAt(0) || 'U'}
                                </div>
                            )}
                        </div>
                        <div className="flex-1 text-center md:text-left">
                            <h3 className="text-xl font-bold text-white">{user?.name}</h3>
                            <p className="text-slate-400 text-sm mb-1">{user?.email}</p>
                            <div className="flex flex-wrap justify-center md:justify-start gap-2 mt-2">
                                <span className="px-3 py-1 bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 rounded-full text-[10px] font-bold uppercase tracking-wider">
                                    {user?.role || 'Member'}
                                </span>
                            </div>
                        </div>
                    </div>
                </section>

                {/* Workspace Section */}
                <section className="bg-slate-900/50 border border-slate-800 rounded-2xl overflow-hidden shadow-sm">
                    <div className="p-6 border-b border-slate-800 flex items-center gap-3">
                        <Store className="w-5 h-5 text-slate-400" />
                        <h2 className="text-lg font-semibold text-white">Workspace</h2>
                    </div>
                    <div className="p-6">
                        <div className="flex flex-col md:flex-row justify-between items-center gap-6">
                            <div className="flex-1">
                                <div className="flex items-center gap-2 mb-1">
                                    <h3 className="font-bold text-white">{user?.shop_name || "Personal Workspace"}</h3>
                                    {isPersonal && (
                                        <span className="px-2 py-0.5 bg-slate-800 text-slate-400 rounded text-[9px] font-bold uppercase">Solo</span>
                                    )}
                                </div>
                                <p className="text-slate-400 text-sm">
                                    {isPersonal 
                                        ? "You are currently in a personal workspace. Join a shop to collaborate." 
                                        : `You are currently a ${user?.role} at ${user?.shop_name}.`
                                    }
                                </p>
                            </div>

                            {!isPersonal && (
                                <button
                                    onClick={handleLeaveShop}
                                    disabled={isLeaving}
                                    className="px-6 py-2.5 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 rounded-xl transition-all font-semibold flex items-center gap-2 text-sm disabled:opacity-50"
                                >
                                    {isLeaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <LogOut className="w-4 h-4" />}
                                    Leave Shop
                                </button>
                            )}
                        </div>

                        {isPersonal && (
                            <div className="mt-6 p-4 bg-indigo-500/5 border border-indigo-500/10 rounded-xl flex gap-4">
                                <Info className="w-5 h-5 text-indigo-400 shrink-0 mt-0.5" />
                                <div className="text-xs text-slate-400 leading-relaxed">
                                    <p className="font-semibold text-indigo-300 mb-1">Personal Workspace Mode</p>
                                    As you are not linked to any shop, you have full view access to manage your own Item Master and Inventory. 
                                    Once you accept an invitation to join a professional shop, your view will adjust to your assigned role.
                                </div>
                            </div>
                        )}
                    </div>
                </section>

                {/* System Info Section */}
                <section className="bg-slate-900/10 border border-slate-800/50 rounded-2xl p-6 flex flex-col md:flex-row justify-between items-center gap-4">
                    <div className="flex items-center gap-3 text-slate-500 text-xs font-mono">
                        <Shield className="w-4 h-4" />
                        <span>Security: SSE Encrypted</span>
                        <span className="text-slate-700 mx-1">|</span>
                        <span>Version: v6.1 (Ledger Build)</span>
                    </div>
                    <div className="text-[10px] text-slate-600 font-mono italic">
                        Node ID: {user?.shop_id || 'personal'}
                    </div>
                </section>
            </div>
        </div>
    );
};

export default Settings;
