import React from 'react';
import { Lock } from 'lucide-react';
import { AUTH_LOGIN_URL } from '../services/api';

const Login = () => {

    const handleGoogleLogin = () => {
        window.location.href = AUTH_LOGIN_URL;
    };

    return (
        <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4 text-slate-200">
            <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl p-8">
                <div className="text-center mb-10">
                    <div className="w-20 h-20 bg-indigo-500/10 rounded-full flex items-center justify-center mx-auto mb-6 border border-indigo-500/20 ring-4 ring-slate-900 shadow-xl">
                        <Lock className="w-10 h-10 text-indigo-400" />
                    </div>
                    <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-indigo-400 to-cyan-400 mb-2">
                        PharmaGPT
                    </h1>
                    <p className="text-slate-500">Secure Workspace Access</p>
                </div>

                {window.location.hostname.match(/\d+\.\d+\.\d+\.\d+/) && (
                    <div className="bg-amber-500/10 border border-amber-500/50 text-amber-200 p-4 rounded-xl mb-6 text-sm text-center">
                        <p className="font-bold mb-1">⚠️ Incorrect Access URL</p>
                        Google Login requires HTTPS. Please use:
                        <br />
                        <a href="https://dev.pharmagpt.co" className="underline font-bold text-amber-400 block mt-2 p-2 bg-amber-500/10 rounded-lg hover:bg-amber-500/20 transition-colors">
                            https://dev.pharmagpt.co
                        </a>
                    </div>
                )}

                <div className="space-y-6">
                    <button
                        onClick={handleGoogleLogin}
                        className="w-full bg-white hover:bg-slate-50 text-slate-900 font-bold py-4 rounded-xl shadow-lg transition-all active:scale-[0.98] flex items-center justify-center gap-3 border border-slate-200"
                    >
                        <img
                            src="https://www.google.com/favicon.ico"
                            alt="Google"
                            className="w-6 h-6"
                        />
                        <span className="text-lg">Sign in with Google</span>
                    </button>

                    <div className="text-center pt-4 border-t border-slate-800">
                        <p className="text-xs text-slate-600">
                            By continuing, you agree to the Terms of Service.
                            <br />Only authorized personnel permitted.
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Login;
