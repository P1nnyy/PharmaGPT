import React, { useState } from 'react';
import { Lock, User, ArrowRight } from 'lucide-react';

const Login = ({ onLogin }) => {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');

    const handleSubmit = (e) => {
        e.preventDefault();
        // Hardcoded credentials as requested
        // Interpreting "1234pranav" as the username. 
        // Setting a default password '1234' for simplicity since not specified, 
        // or allowing the username itself as password.

        const validUsers = ['1234pranav', '1234ranjhan'];

        if (validUsers.includes(username)) {
            // Check password - asking user provided just "user name", implying maybe simplistic check?
            // Let's assume password is '1234' based on the prefix of the username
            if (password === '1234') {
                onLogin(username);
            } else {
                setError('Invalid Password (Try 1234)');
            }
        } else {
            setError('Invalid Username');
        }
    };

    return (
        <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4 text-slate-200">
            <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl p-8">
                <div className="text-center mb-8">
                    <div className="w-16 h-16 bg-indigo-500/10 rounded-full flex items-center justify-center mx-auto mb-4 border border-indigo-500/20">
                        <Lock className="w-8 h-8 text-indigo-400" />
                    </div>
                    <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-indigo-400 to-cyan-400">
                        PharmaGPT Access
                    </h1>
                    <p className="text-slate-500 text-sm mt-2">Please log in to continue</p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-6">
                    <div className="space-y-2">
                        <label className="text-xs font-semibold uppercase tracking-wider text-slate-500 ml-1">Username</label>
                        <div className="relative">
                            <User className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-600" />
                            <input
                                type="text"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                className="w-full bg-slate-950 border border-slate-800 rounded-xl py-3 pl-10 pr-4 focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 outline-none transition-all placeholder-slate-700"
                                placeholder="Enter ID"
                            />
                        </div>
                    </div>

                    <div className="space-y-2">
                        <label className="text-xs font-semibold uppercase tracking-wider text-slate-500 ml-1">Password</label>
                        <div className="relative">
                            <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-600" />
                            <input
                                type="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                className="w-full bg-slate-950 border border-slate-800 rounded-xl py-3 pl-10 pr-4 focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 outline-none transition-all placeholder-slate-700"
                                placeholder="••••"
                            />
                        </div>
                    </div>

                    {error && (
                        <div className="text-rose-400 text-sm text-center bg-rose-500/10 py-2 rounded-lg border border-rose-500/20">
                            {error}
                        </div>
                    )}

                    <button
                        type="submit"
                        className="w-full bg-gradient-to-r from-indigo-600 to-blue-600 hover:from-indigo-500 hover:to-blue-500 text-white font-bold py-3.5 rounded-xl shadow-lg shadow-indigo-900/20 transition-all active:scale-[0.98] flex items-center justify-center gap-2"
                    >
                        <span>Access Dashboard</span>
                        <ArrowRight className="w-4 h-4" />
                    </button>
                </form>
            </div>
        </div>
    );
};

export default Login;
