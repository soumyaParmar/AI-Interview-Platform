import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Mic, MicOff, Send, Loader2 } from 'lucide-react';

interface VoiceControllerProps {
    onSpeechResult: (text: string) => void;
    isMuted: boolean;
    onToggleMute: () => void;
    status: string;
    lastAgentMessage?: string;
}

const VoiceController: React.FC<VoiceControllerProps> = ({ 
    onSpeechResult, 
    isMuted, 
    onToggleMute, 
    status,
    lastAgentMessage 
}) => {
    const [isListening, setIsListening] = useState(false);
    const [transcript, setTranscript] = useState('');
    const recognitionRef = useRef<any>(null);

    // Setup Speech Recognition
    useEffect(() => {
        if (typeof window !== 'undefined') {
            const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
            
            if (SpeechRecognition) {
                const recognition = new SpeechRecognition();
                recognition.continuous = true;
                recognition.interimResults = true;
                recognition.lang = 'en-US';

                recognition.onresult = (event: any) => {
                    let currentTranscript = '';
                    for (let i = event.resultIndex; i < event.results.length; ++i) {
                        currentTranscript += event.results[i][0].transcript;
                    }
                    setTranscript(currentTranscript);
                };

                recognition.onend = () => {
                    if (isListening && !isMuted) {
                        try {
                            // Resume listening if we didn't explicitly stop it
                            recognition.start();
                        } catch (e) {
                            console.error("Speech recognition restart failed", e);
                        }
                    } else {
                        setIsListening(false);
                    }
                };

                recognitionRef.current = recognition;
            }
        }

        return () => {
            if (recognitionRef.current) {
                recognitionRef.current.stop();
            }
        };
    }, []);

    // Text-to-Speech (TTS) for agent messages
    useEffect(() => {
        if (lastAgentMessage && !isMuted && typeof window !== 'undefined' && window.speechSynthesis) {
            // Cancel any ongoing speech
            window.speechSynthesis.cancel();
            
            const utterance = new SpeechSynthesisUtterance(lastAgentMessage);
            // Optionally set voice preferences here
            window.speechSynthesis.speak(utterance);
        }
    }, [lastAgentMessage, isMuted]);

    // Handle Mic Toggle
    useEffect(() => {
        if (!recognitionRef.current) return;

        if (isMuted || status !== 'Listening') {
            recognitionRef.current.stop();
            setIsListening(false);
        } else if (!isListening) {
            try {
                recognitionRef.current.start();
                setIsListening(true);
            } catch (e) {
                console.error("Could not start recognition:", e);
            }
        }
    }, [isMuted, status]);

    const handleSend = useCallback(() => {
        if (transcript.trim()) {
            onSpeechResult(transcript.trim());
            setTranscript('');
        }
    }, [transcript, onSpeechResult]);

    // Send on Enter
    const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key === 'Enter') {
            handleSend();
        }
    };

    const isSystemProcessing = status !== 'Listening' && status !== 'Initializing' && status !== 'Disconnected' && !status.startsWith('Error');

    return (
        <div className="flex flex-col gap-3">
             {/* Status indicator */}
             {isSystemProcessing && (
                <div className="flex items-center gap-2 text-blue-600 text-sm animate-pulse px-2">
                    <Loader2 size={16} className="animate-spin" />
                    <span>Devsko is {status.toLowerCase()}...</span>
                </div>
            )}

            <div className="flex items-end gap-2">
                <button
                    onClick={onToggleMute}
                    className={`p-3 rounded-full flex shrink-0 items-center justify-center transition-colors shadow-sm ${
                        isMuted 
                            ? 'bg-red-100 text-red-600 hover:bg-red-200' 
                            : 'bg-green-100 text-green-600 hover:bg-green-200'
                    }`}
                    title={isMuted ? "Unmute Microphone" : "Mute Microphone"}
                >
                    {isMuted ? <MicOff size={24} /> : <Mic size={24} />}
                </button>
                
                <div className="flex-1 bg-white border rounded-3xl flex items-center shadow-sm overflow-hidden focus-within:ring-2 focus-within:ring-blue-500">
                    <input 
                        type="text" 
                        value={transcript}
                        onChange={(e) => setTranscript(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder={isMuted ? "Microphone muted. Type your answer..." : "Listening... or type your answer"}
                        className="w-full bg-transparent px-5 py-3 outline-none text-gray-700"
                        disabled={isSystemProcessing}
                    />
                    <button 
                        onClick={handleSend}
                        disabled={!transcript.trim() || isSystemProcessing}
                        className="p-3 text-blue-600 hover:bg-blue-50 disabled:opacity-50 disabled:hover:bg-transparent transition-colors"
                    >
                        <Send size={20} />
                    </button>
                </div>
            </div>
            
            {!isMuted && status === 'Listening' && (
                <div className="text-xs text-gray-500 px-2 flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse"></span>
                    Microphone is active
                </div>
            )}
        </div>
    );
};

export default VoiceController;
