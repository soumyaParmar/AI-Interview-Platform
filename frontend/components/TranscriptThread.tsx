import React, { useEffect, useRef } from 'react';
import { Bot, User } from 'lucide-react';

interface Message {
    role: string;
    content: string;
}

interface TranscriptThreadProps {
    messages: Message[];
}

const TranscriptThread: React.FC<TranscriptThreadProps> = ({ messages }) => {
    const endOfMessagesRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        endOfMessagesRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    return (
        <div className="flex-1 overflow-y-auto p-4 space-y-6 bg-white">
            {messages.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-gray-400">
                    <Bot size={48} className="mb-4 opacity-50" />
                    <p>The interview hasn't started yet.</p>
                </div>
            ) : (
                messages.map((message, index) => {
                    const isSystem = message.role === 'system';
                    const isAgent = message.role === 'agent';
                    
                    if (isSystem) {
                        return (
                            <div key={index} className="flex justify-center my-2">
                                <span className="px-3 py-1 bg-gray-100 text-xs text-gray-500 rounded-full">
                                    {message.content}
                                </span>
                            </div>
                        );
                    }

                    return (
                        <div 
                            key={index} 
                            className={`flex gap-3 ${isAgent ? 'flex-row' : 'flex-row-reverse'}`}
                        >
                            {/* Avatar */}
                            <div className={`w-10 h-10 shrink-0 rounded-full flex items-center justify-center text-white ${isAgent ? 'bg-blue-600' : 'bg-green-600'}`}>
                                {isAgent ? <Bot size={20} /> : <User size={20} />}
                            </div>
                            
                            {/* Message Bubble */}
                            <div className={`rounded-2xl p-4 max-w-[80%] ${
                                isAgent 
                                    ? 'bg-gray-100 rounded-tl-none text-gray-800' 
                                    : 'bg-blue-600 text-white rounded-tr-none'
                            }`}>
                                <p className="leading-relaxed whitespace-pre-wrap">{message.content}</p>
                            </div>
                        </div>
                    );
                })
            )}
            <div ref={endOfMessagesRef} />
        </div>
    );
};

export default TranscriptThread;
