import React, { useState, useEffect } from 'react';
import { useSocket } from '../hooks/useSocket';
import TranscriptThread from './TranscriptThread';
import VoiceController from './VoiceController';
import { Power, Loader2, Award } from 'lucide-react';
import { useRouter } from 'next/router';
import { apiUrl } from '../lib/api';

interface InterviewRoomProps {
    sessionSlug: string;
}

const InterviewRoom: React.FC<InterviewRoomProps> = ({ sessionSlug }) => {
    const [sessionStatus, setSessionStatus] = useState<string>('ANALYZING');
    const [statusError, setStatusError] = useState<string | null>(null);
    
    const { isConnected, messages, status, report, sendAnswer, terminateInterview } = useSocket(
        sessionSlug, 
        sessionStatus === 'READY'
    );
    
    const [isMuted, setIsMuted] = useState(false);
    const [isTerminating, setIsTerminating] = useState(false);
    const router = useRouter();

    useEffect(() => {
        let intervalId: NodeJS.Timeout;

        const checkStatus = async () => {
            try {
                const response = await fetch(apiUrl(`/sessions/${sessionSlug}/status`));
                if (!response.ok) throw new Error("Failed to fetch status");
                const data = await response.json();
                
                if (data.status === 'READY') {
                    setSessionStatus('READY');
                } else if (data.status === 'FAILED') {
                    setSessionStatus('FAILED');
                    setStatusError(data.error_message || "Analysis failed");
                }
            } catch (error) {
                console.error("Polling error:", error);
            }
        };

        if (sessionStatus === 'ANALYZING') {
            checkStatus();
            intervalId = setInterval(checkStatus, 3000);
        }

        return () => {
            if (intervalId) clearInterval(intervalId);
        };
    }, [sessionSlug, sessionStatus]);

    useEffect(() => {
        if (report) {
            // Give 2 seconds to show the "Success" state before redirecting
            const timer = setTimeout(() => {
                router.push(`/report/${sessionSlug}`);
            }, 2000);
            return () => clearTimeout(timer);
        }
    }, [report, router, sessionSlug]);

    const handleTerminate = () => {
        console.log("Terminate clicked!");
        setIsTerminating(true);
        terminateInterview();
    };

    return (
        <div className="flex flex-col h-screen bg-gray-50 font-sans text-gray-800">
            {/* Header */}
            <header className="flex items-center justify-between p-4 bg-white shadow-sm border-b">
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white font-bold">
                        AI
                    </div>
                    <div>
                        <h1 className="text-lg font-semibold">Devsko Interviewer</h1>
                        <p className="text-sm text-gray-500">Session: {sessionSlug}</p>
                    </div>
                </div>

                <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2">
                        <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`}></div>
                        <span className="text-sm font-medium text-gray-600">
                            {isConnected ? 'Connected' : 'Disconnected'}
                        </span>
                        <div className="ml-4 px-3 py-1 bg-blue-100 text-blue-700 text-xs font-semibold rounded-full uppercase tracking-wider">
                            {status}
                        </div>
                    </div>

                    <button
                        onClick={handleTerminate}
                        disabled={!isConnected || isTerminating}
                        className="flex items-center gap-2 px-4 py-2 bg-red-50 text-red-600 hover:bg-red-600 hover:text-white transition-all rounded-lg font-bold text-sm border border-red-100 disabled:opacity-50"
                    >
                        <Power size={18} />
                        Terminate
                    </button>
                </div>
            </header>

            {/* Main Content Area */}
            <main className="flex-1 overflow-hidden flex flex-col max-w-4xl w-full mx-auto shadow-sm bg-white border-x relative">
                {sessionStatus === 'ANALYZING' && (
                    <div className="absolute inset-0 z-50 bg-white/90 backdrop-blur-md flex flex-col items-center justify-center p-8 text-center transition-all animate-in fade-in">
                        <Loader2 className="w-16 h-16 text-blue-600 animate-spin mb-6" />
                        <h2 className="text-3xl font-black text-gray-900 mb-2">Analyzing Context</h2>
                        <p className="text-gray-500 text-lg">AI is brainstorming the perfect interview flow based on the JD and your resume...</p>
                        <div className="mt-8 flex gap-2">
                             {[0, 1, 2].map(i => (
                                 <div key={i} className="w-2 h-2 rounded-full bg-blue-500 animate-bounce" style={{ animationDelay: `${i * 0.1}s` }}></div>
                             ))}
                        </div>
                    </div>
                )}

                {sessionStatus === 'FAILED' && (
                    <div className="absolute inset-0 z-50 bg-white/95 backdrop-blur-md flex flex-col items-center justify-center p-8 text-center">
                        <div className="w-20 h-20 bg-red-100 text-red-600 rounded-full flex items-center justify-center mb-6">
                            <Power size={48} />
                        </div>
                        <h2 className="text-3xl font-black text-gray-900 mb-2">Analysis Failed</h2>
                        <p className="text-red-500 text-lg mb-6">{statusError}</p>
                        <button 
                            onClick={() => router.push('/')}
                            className="px-6 py-3 bg-gray-900 text-white rounded-xl font-bold hover:bg-gray-800 transition-all"
                        >
                            Return to Setup
                        </button>
                    </div>
                )}

                {(isTerminating || report) && (
                    <div className="absolute inset-0 z-50 bg-white/90 backdrop-blur-md flex flex-col items-center justify-center p-8 text-center">
                        {report ? (
                            <>
                                <div className="w-20 h-20 bg-green-100 text-green-600 rounded-full flex items-center justify-center mb-6">
                                    <Award size={48} />
                                </div>
                                <h2 className="text-3xl font-black text-gray-900 mb-2">Interview Complete!</h2>
                                <p className="text-gray-500 text-lg">Your report is ready. Redirecting now...</p>
                            </>
                        ) : (
                            <>
                                <Loader2 className="w-16 h-16 text-blue-600 animate-spin mb-6" />
                                <h2 className="text-3xl font-black text-gray-900 mb-2">Generating Report</h2>
                                <p className="text-gray-500 text-lg">AI is analyzing your performance. This might take a minute...</p>
                            </>
                        )}
                    </div>
                )}

                <TranscriptThread messages={messages} />
                
                {/* Voice Controller Footer */}
                <div className="p-4 border-t bg-gray-50">
                    <VoiceController 
                        onSpeechResult={sendAnswer} 
                        isMuted={isMuted}
                        onToggleMute={() => setIsMuted(!isMuted)}
                        status={status}
                        lastAgentMessage={messages.filter(m => m.role === 'agent').pop()?.content}
                    />
                </div>
            </main>
        </div>
    );
};

export default InterviewRoom;
