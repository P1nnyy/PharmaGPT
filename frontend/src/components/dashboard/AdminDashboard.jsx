import React, { useState, useEffect } from 'react';
import { Settings, Shield, Tags, Plus, Trash2, Loader2, RefreshCw, ToggleLeft, ToggleRight, Lock, ChevronDown, ChevronRight } from 'lucide-react';
import { getCategories, createCategory, deleteCategory, updateCategoryConfig, getRoles, createRole } from '../../services/api';
import Toast from '../ui/Toast';

const AdminDashboard = () => {
    const [activeTab, setActiveTab] = useState('categories'); // 'categories' | 'roles'
    const [categories, setCategories] = useState([]);
    const [roles, setRoles] = useState([]);
    const [loading, setLoading] = useState(true);
    const [expandedCategory, setExpandedCategory] = useState(null);

    const COMMON_UNITS = ['pieces', 'ml', 'L', 'strip', 'box', 'tube', 'vial', 'ampoule', 'g', 'mg', 'kg'];

    const toggleExpand = (name) => {
        setExpandedCategory(prev => prev === name ? null : name);
    };

    // Form States
    const [newCatName, setNewCatName] = useState('');
    const [newCatDesc, setNewCatDesc] = useState('');
    const [newCatParent, setNewCatParent] = useState('');
    const [newRoleName, setNewRoleName] = useState('');
    const [newRolePerms, setNewRolePerms] = useState('');

    const [toast, setToast] = useState({ show: false, message: '', type: 'success' });

    const showToast = (msg, type = 'success') => {
        setToast({ show: true, message: msg, type });
        setTimeout(() => setToast({ show: false, message: '', type: 'success' }), 3000);
    };

    const fetchData = async () => {
        setLoading(true);
        try {
            const [cats, rls] = await Promise.all([
                getCategories(),
                getRoles()
            ]);
            setCategories(cats);
            setRoles(rls);
        } catch (error) {
            console.error("Failed to load admin data", error);
            showToast("Failed to load configuration data", "error");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
    }, []);

    const handleCreateCategory = async (e) => {
        e.preventDefault();
        if (!newCatName.trim()) return;
        try {
            // Updated to pass parent_name if it is not empty
            await createCategory(newCatName, newCatDesc, newCatParent || null);
            showToast(`Category '${newCatName}' created!`, "success");
            setNewCatName('');
            setNewCatDesc('');
            setNewCatParent('');
            fetchData();
        } catch (error) {
            showToast("Failed to create category", "error");
        }
    };

    const handleToggleAtomicSizing = async (name, currentValue) => {
        try {
            await updateCategoryConfig(name, { supports_atomic_sizing: !currentValue });
            // Optimistically update the UI
            setCategories(prev => prev.map(c =>
                c.name === name ? { ...c, supports_atomic_sizing: !currentValue } : c
            ));
            showToast(`Updated config for ${name}`, "success");
        } catch (error) {
            showToast("Failed to update component configuration", "error");
        }
    };

    const handleToggleUnit = async (cat, unit) => {
        try {
            const currentUnits = cat.units || [];
            const newUnits = currentUnits.includes(unit)
                ? currentUnits.filter(u => u !== unit)
                : [...currentUnits, unit];

            await updateCategoryConfig(cat.name, { units: newUnits });
            setCategories(prev => prev.map(c =>
                c.name === cat.name ? { ...c, units: newUnits } : c
            ));
            showToast(`Updated units for ${cat.name}`, "success");
        } catch (error) {
            showToast("Failed to update unit configuration", "error");
        }
    };

    const handleDeleteCategory = async (cat) => {
        if (cat.is_default) {
            showToast("Cannot delete a system default category", "error");
            return;
        }
        if (!window.confirm(`Are you sure you want to delete category '${cat.name}'?`)) return;
        try {
            await deleteCategory(cat.name);
            showToast(`Category '${name}' deleted!`, "success");
            fetchData();
        } catch (error) {
            showToast("Failed to delete category", "error");
        }
    };

    const handleCreateRole = async (e) => {
        e.preventDefault();
        if (!newRoleName.trim()) return;
        try {
            const permsArray = newRolePerms.split(',').map(p => p.trim()).filter(p => p);
            await createRole(newRoleName, permsArray);
            showToast(`Role '${newRoleName}' created!`, "success");
            setNewRoleName('');
            setNewRolePerms('');
            fetchData();
        } catch (error) {
            showToast("Failed to create role", "error");
        }
    };

    return (
        <div className="flex flex-col h-full bg-slate-950 p-6 overflow-hidden">
            <div className="flex items-center justify-between mb-8">
                <div className="flex items-center gap-3">
                    <div className="p-3 bg-indigo-500/20 rounded-xl">
                        <Settings className="w-6 h-6 text-indigo-400" />
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold text-white tracking-tight">System Configuration</h1>
                        <p className="text-sm text-slate-400">Manage Categories, Roles, and Application Settings</p>
                    </div>
                </div>
                <button
                    onClick={fetchData}
                    className="p-2 bg-slate-800 text-slate-300 hover:text-white rounded-lg transition-colors border border-slate-700"
                    title="Refresh Data"
                >
                    <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin text-indigo-400' : ''}`} />
                </button>
            </div>

            {/* Config Navigation */}
            <div className="flex gap-4 mb-6 border-b border-slate-800 pb-px">
                <button
                    onClick={() => setActiveTab('categories')}
                    className={`pb-3 px-4 text-sm font-medium transition-colors border-b-2 ${activeTab === 'categories'
                        ? 'border-indigo-500 text-indigo-400'
                        : 'border-transparent text-slate-400 hover:text-slate-200'
                        }`}
                >
                    <div className="flex items-center gap-2">
                        <Tags className="w-4 h-4" /> Item Categories
                    </div>
                </button>
                <button
                    onClick={() => setActiveTab('roles')}
                    className={`pb-3 px-4 text-sm font-medium transition-colors border-b-2 ${activeTab === 'roles'
                        ? 'border-emerald-500 text-emerald-400'
                        : 'border-transparent text-slate-400 hover:text-slate-200'
                        }`}
                >
                    <div className="flex items-center gap-2">
                        <Shield className="w-4 h-4" /> User Roles & Permissions
                    </div>
                </button>
            </div>

            {/* Main Content Area */}
            <div className="flex-1 overflow-y-auto pr-2 custom-scrollbar">

                {/* --- ITEM CATEGORIES TAB --- */}
                {activeTab === 'categories' && (
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

                        {/* List */}
                        <div className="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm flex flex-col h-fit max-h-[70vh]">
                            <div className="p-4 border-b border-slate-800/60 bg-slate-900/50 flex justify-between items-center">
                                <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-wider">Active Categories</h2>
                                <span className="bg-slate-800 text-slate-300 py-0.5 px-2.5 rounded-full text-xs font-medium">
                                    {categories.length} Total
                                </span>
                            </div>
                            <div className="overflow-y-auto p-4 flex-1">
                                {loading && categories.length === 0 ? (
                                    <div className="flex justify-center p-8"><Loader2 className="w-6 h-6 animate-spin text-indigo-500" /></div>
                                ) : categories.length === 0 ? (
                                    <div className="text-center p-8 text-slate-500 text-sm">No categories configured yet.</div>
                                ) : (
                                    <div className="grid gap-3">
                                        {categories.map((cat, idx) => (
                                            <div key={idx} className={`flex flex-col p-4 bg-slate-800/40 border transition-all rounded-lg group ${expandedCategory === cat.name ? 'border-indigo-500/50 ring-1 ring-indigo-500/20' : 'border-slate-800/80 hover:border-slate-700 hover:bg-slate-800/60'}`}>
                                                <div
                                                    className="flex flex-col sm:flex-row sm:items-start justify-between cursor-pointer"
                                                    onClick={() => toggleExpand(cat.name)}
                                                >
                                                    <div>
                                                        <div className="font-semibold text-slate-200 flex items-center gap-2">
                                                            {expandedCategory === cat.name ? <ChevronDown className="w-4 h-4 text-indigo-400" /> : <ChevronRight className="w-4 h-4 text-slate-500 group-hover:text-indigo-400 transition-colors" />}
                                                            <Tags className="w-3.5 h-3.5 text-indigo-400" />
                                                            {cat.name}
                                                            {cat.is_default && (
                                                                <span className="flex items-center gap-1 text-[10px] font-medium text-slate-400 ml-1 px-1.5 py-0.5 bg-slate-800 rounded-full border border-slate-700">
                                                                    <Lock className="w-3 h-3" /> System Default
                                                                </span>
                                                            )}
                                                            {cat.parent_name && (
                                                                <span className="text-[10px] font-medium text-indigo-300 ml-1 px-1.5 py-0.5 bg-indigo-500/10 rounded-full border border-indigo-500/20">
                                                                    Child of: {cat.parent_name}
                                                                </span>
                                                            )}
                                                        </div>
                                                        <div className="text-xs text-slate-500 mt-1 pl-6">{cat.description || "No description provided."}</div>

                                                        {expandedCategory !== cat.name && cat.units && cat.units.length > 0 && (
                                                            <div className="flex gap-1.5 mt-2 pl-6 flex-wrap">
                                                                {cat.units.map(u => <span key={u} className="px-1.5 py-0.5 bg-slate-700/50 text-[10px] text-slate-300 rounded border border-slate-700">{u}</span>)}
                                                            </div>
                                                        )}
                                                    </div>

                                                    <div className="mt-3 sm:mt-0 flex items-center gap-3" onClick={(e) => e.stopPropagation()}>
                                                        <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-900/50 border border-slate-800 rounded-lg">
                                                            <span className="text-xs text-slate-400 font-medium whitespace-nowrap">Atomic Sizing</span>
                                                            <button
                                                                onClick={() => handleToggleAtomicSizing(cat.name, cat.supports_atomic_sizing)}
                                                                className={`transition-colors ${cat.supports_atomic_sizing ? 'text-indigo-400' : 'text-slate-600 hover:text-slate-400'}`}
                                                                title={cat.supports_atomic_sizing ? "Enabled" : "Disabled"}
                                                            >
                                                                {cat.supports_atomic_sizing ? <ToggleRight className="w-6 h-6" /> : <ToggleLeft className="w-6 h-6" />}
                                                            </button>
                                                        </div>

                                                        {!cat.is_default && (
                                                            <button
                                                                onClick={() => handleDeleteCategory(cat)}
                                                                className="p-2 text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition-colors opacity-0 group-hover:opacity-100"
                                                                title="Delete Custom Category"
                                                            >
                                                                <Trash2 className="w-4 h-4" />
                                                            </button>
                                                        )}
                                                    </div>
                                                </div>

                                                {expandedCategory === cat.name && (
                                                    <div className="mt-4 pt-4 border-t border-slate-700/50 animate-in fade-in slide-in-from-top-2 duration-200">
                                                        <div className="mb-3 flex flex-col">
                                                            <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Configured Measurement Units</span>
                                                            <span className="text-[10px] text-slate-500 mt-0.5">Select the valid units that items in this category can be measured in.</span>
                                                        </div>
                                                        <div className="flex flex-wrap gap-2">
                                                            {COMMON_UNITS.map(unit => {
                                                                const isSelected = (cat.units || []).includes(unit);
                                                                return (
                                                                    <button
                                                                        key={unit}
                                                                        onClick={() => handleToggleUnit(cat, unit)}
                                                                        className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-all ${isSelected
                                                                            ? 'bg-indigo-500/20 text-indigo-300 border-indigo-500/50 hover:bg-indigo-500/30 shadow-sm shadow-indigo-500/10'
                                                                            : 'bg-slate-800/50 text-slate-400 border-slate-700 hover:border-slate-500 hover:text-slate-200 hover:bg-slate-800'
                                                                            }`}
                                                                    >
                                                                        {unit}
                                                                    </button>
                                                                );
                                                            })}
                                                        </div>
                                                    </div>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* Form */}
                        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 h-fit shadow-sm">
                            <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-wider mb-4 flex items-center gap-2">
                                <Plus className="w-4 h-4 text-indigo-400" /> Add New Category
                            </h2>
                            <form onSubmit={handleCreateCategory} className="space-y-4">
                                <div>
                                    <label className="block text-xs font-medium text-slate-400 mb-1.5 uppercase">Category Name</label>
                                    <input
                                        type="text"
                                        required
                                        value={newCatName}
                                        onChange={(e) => setNewCatName(e.target.value)}
                                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-2.5 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                                        placeholder="e.g. Antibiotics, Surgical"
                                    />
                                </div>
                                <div>
                                    <label className="block text-xs font-medium text-slate-400 mb-1.5 uppercase">Description</label>
                                    <textarea
                                        value={newCatDesc}
                                        onChange={(e) => setNewCatDesc(e.target.value)}
                                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-2.5 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 min-h-[80px]"
                                        placeholder="Optional details about this category..."
                                    />
                                </div>
                                <div>
                                    <label className="block text-xs font-medium text-slate-400 mb-1.5 uppercase">Parent Category (Optional)</label>
                                    <select
                                        value={newCatParent}
                                        onChange={(e) => setNewCatParent(e.target.value)}
                                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 appearance-none"
                                    >
                                        <option value="">-- None (Top Level) --</option>
                                        {categories.map((cat, idx) => (
                                            <option key={idx} value={cat.name}>{cat.name}</option>
                                        ))}
                                    </select>
                                </div>
                                <button
                                    type="submit"
                                    disabled={!newCatName.trim()}
                                    className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-semibold rounded-lg py-2.5 transition-colors shadow-lg shadow-indigo-500/20"
                                >
                                    Create Category
                                </button>
                            </form>
                        </div>
                    </div>
                )}

                {/* --- ROLES TAB --- */}
                {activeTab === 'roles' && (
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

                        {/* List */}
                        <div className="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm flex flex-col h-fit max-h-[70vh]">
                            <div className="p-4 border-b border-slate-800/60 bg-slate-900/50 flex justify-between items-center">
                                <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-wider">System Roles</h2>
                                <span className="bg-slate-800 text-slate-300 py-0.5 px-2.5 rounded-full text-xs font-medium">
                                    {roles.length} Total
                                </span>
                            </div>
                            <div className="overflow-y-auto p-4 flex-1">
                                {loading && roles.length === 0 ? (
                                    <div className="flex justify-center p-8"><Loader2 className="w-6 h-6 animate-spin text-emerald-500" /></div>
                                ) : roles.length === 0 ? (
                                    <div className="text-center p-8 text-slate-500 text-sm">No roles configured yet.</div>
                                ) : (
                                    <div className="grid gap-3">
                                        {roles.map((role, idx) => (
                                            <div key={idx} className="p-4 bg-slate-800/40 border border-slate-800/80 rounded-lg">
                                                <div className="font-semibold text-slate-200 flex items-center gap-2 mb-2">
                                                    <Shield className="w-3.5 h-3.5 text-emerald-400" />
                                                    {role.name}
                                                </div>
                                                <div className="flex flex-wrap gap-1.5 mt-2">
                                                    {role.permissions && role.permissions.length > 0 ? (
                                                        role.permissions.map((perm, pidx) => (
                                                            <span key={pidx} className="px-2 py-0.5 bg-slate-700/50 text-slate-300 text-[10px] rounded border border-slate-700">
                                                                {perm}
                                                            </span>
                                                        ))
                                                    ) : (
                                                        <span className="text-xs text-slate-500 italic">No specific permissions</span>
                                                    )}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* Form */}
                        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 h-fit shadow-sm">
                            <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-wider mb-4 flex items-center gap-2">
                                <Plus className="w-4 h-4 text-emerald-400" /> Create New Role
                            </h2>
                            <form onSubmit={handleCreateRole} className="space-y-4">
                                <div>
                                    <label className="block text-xs font-medium text-slate-400 mb-1.5 uppercase">Role Name</label>
                                    <input
                                        type="text"
                                        required
                                        value={newRoleName}
                                        onChange={(e) => setNewRoleName(e.target.value)}
                                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-2.5 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
                                        placeholder="e.g. Auditor, Manager"
                                    />
                                </div>
                                <div>
                                    <label className="block text-xs font-medium text-slate-400 mb-1.5 uppercase">Permissions (Comma separated)</label>
                                    <textarea
                                        value={newRolePerms}
                                        onChange={(e) => setNewRolePerms(e.target.value)}
                                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-2.5 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 font-mono min-h-[100px]"
                                        placeholder="e.g. read:invoices, edit:inventory, delete:users"
                                    />
                                    <p className="text-[10px] text-slate-500 mt-1.5">* Roles map to API endpoints for access control.</p>
                                </div>
                                <button
                                    type="submit"
                                    disabled={!newRoleName.trim()}
                                    className="w-full bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-semibold rounded-lg py-2.5 transition-colors shadow-lg shadow-emerald-500/20"
                                >
                                    Create Role
                                </button>
                            </form>
                        </div>
                    </div>
                )}
            </div>

            <Toast show={toast.show} message={toast.message} type={toast.type} onClose={() => setToast({ ...toast, show: false })} />
        </div>
    );
};

export default AdminDashboard;
