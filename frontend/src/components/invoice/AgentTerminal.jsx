import React, { useState, useEffect } from 'react';
import { Terminal } from 'lucide-react';

const TypewriterText = ({ text, speed = 40 }) => {
    const [displayedText, setDisplayedText] = useState('');
    
    useEffect(() => {
        setDisplayedText('');
        let i = 0;
        const timer = setInterval(() => {
            if (i < text.length) {
                setDisplayedText(prev => prev + text.charAt(i));
                i++;
            } else {
                clearInterval(timer);
            }
        }, speed);
        return () => clearInterval(timer);
    }, [text, speed]);

    return <span>{displayedText}</span>;
};

const AgentTerminal = ({ status, message }) => {
    if (status !== 'processing' || !message) return null;

    return (
        <div className="absolute bottom-6 right-6 z-30 max-w-sm w-full animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="bg-black/80 backdrop-blur-xl border border-indigo-500/30 rounded-lg shadow-2xl overflow-hidden font-mono">
                {/* Terminal Header */}
                <div className="bg-gray-900/50 px-3 py-1.5 border-b border-white/5 flex items-center justify-between text-[10px] text-gray-400">
                    <div className="flex items-center gap-2">
                        <Terminal className="w-3 h-3 text-indigo-400" />
                        <span>AGENT_INTELLIGENCE_STREAM</span>
                    </div>
                    <div className="flex gap-1">
                        <div className="w-1.5 h-1.5 rounded-full bg-red-500/50" />
                        <div className="w-1.5 h-1.5 rounded-full bg-yellow-500/50" />
                        <div className="w-1.5 h-1.5 rounded-full bg-green-500/50" />
                    </div>
                </div>
                
                {/* Terminal Body */}
                <div className="p-4 space-y-2">
                    <div className="flex gap-2 text-xs">
                        <span className="text-indigo-400 shrink-0">tenant@pharmagpt:~$</span>
                        <span className="text-gray-300">
                            <TypewriterText text={message} />
                            <span className="inline-block w-1.5 h-3.5 bg-indigo-500 ml-1 animate-pulse align-middle" />
                        </span>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default AgentTerminal;
