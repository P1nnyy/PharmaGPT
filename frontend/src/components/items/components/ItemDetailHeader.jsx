import React from 'react';
import { Save, AlertCircle, CheckCircle, ArrowLeft } from 'lucide-react';

const ItemDetailHeader = ({ 
    formData, 
    activeTab, 
    setActiveTab, 
    handleSave, 
    saving, 
    setShowMobileDetail 
}) => {
    return (
        <>
            {/* Mobile Header */}
            <div className="md:hidden flex items-center gap-2 p-4 border-b border-slate-700 text-slate-400 hover:text-white cursor-pointer" onClick={() => setShowMobileDetail(false)}>
                <ArrowLeft className="w-5 h-5" />
                <span className="font-bold text-sm">Back</span>
            </div>

            {/* Detail Header */}
            <div className="px-6 py-6 flex flex-col gap-4 border-b border-slate-700 bg-slate-800 z-10">
                {/* Title Row */}
                <div className="flex justify-between items-start">
                    <div className="space-y-1 flex-1 mr-4">
                        <div className="flex items-center gap-3">
                            <h1 className="text-2xl font-bold text-white leading-tight">
                                {formData.name || 'New Product'}
                            </h1>
                            {formData.item_code && (
                                <span className="px-2 py-0.5 rounded-md bg-slate-700 text-slate-300 text-xs font-mono border border-slate-600">
                                    {formData.item_code}
                                </span>
                            )}
                        </div>
                        <div className="flex items-center gap-2 mt-1">
                            {formData.is_verified ? (
                                <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 text-[10px] font-bold border border-emerald-500/20 flex items-center gap-1">
                                    <CheckCircle className="w-3 h-3" /> VERIFIED
                                </span>
                            ) : (
                                <span className="px-2 py-0.5 rounded-full bg-orange-500/10 text-orange-400 text-[10px] font-bold border border-orange-500/20 flex items-center gap-1">
                                    <AlertCircle className="w-3 h-3" /> DRAFT
                                </span>
                            )}
                            {formData.base_unit && (
                                <span className="px-2 py-0.5 rounded-full bg-slate-700 text-slate-300 text-[10px] font-bold border border-slate-600">
                                    {formData.base_unit}
                                </span>
                            )}
                        </div>
                    </div>
                    <button
                        onClick={handleSave}
                        disabled={saving}
                        className={`flex items-center gap-2 px-6 py-2 rounded-lg font-bold shadow-lg transition-all ${saving ? 'bg-slate-600 opacity-50' : 'bg-blue-600 hover:bg-blue-500 text-white'}`}
                    >
                        <Save className="w-4 h-4" />
                        {saving ? 'Saving...' : 'Save'}
                    </button>
                </div>
            </div>
        </>
    );
};

export default ItemDetailHeader;
