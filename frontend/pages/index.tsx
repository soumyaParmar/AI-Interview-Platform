import React, { useState, useEffect } from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';
import SkillReview, { SkillMap } from '../components/SkillReview';
import { Loader2 } from 'lucide-react';
import { io, Socket } from 'socket.io-client';
import { apiUrl, SOCKET_URL } from '../lib/api';

export default function Home() {
  const [candidateName, setCandidateName] = useState('');
  const [jdText, setJdText] = useState('');
  const [companyInfo, setCompanyInfo] = useState('');
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  
  const [isExtracting, setIsExtracting] = useState(false);
  const [discoveryStatus, setDiscoveryStatus] = useState("");
  const [skillMap, setSkillMap] = useState<SkillMap | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isStarting, setIsStarting] = useState(false);
  const [socket, setSocket] = useState<Socket | null>(null);
  const router = useRouter();

  useEffect(() => {
    const newSocket = io(SOCKET_URL);
    setSocket(newSocket);

    newSocket.on('discovery_complete', (data: SkillMap) => {
      console.log("Discovery complete via socket:", data);
      setSkillMap(data);
      setIsExtracting(false);
    });

    newSocket.on('discovery_error', (data: { error: string }) => {
      console.error("Discovery error via socket:", data.error);
      setError(data.error);
      setIsExtracting(false);
    });

    return () => {
      newSocket.disconnect();
    };
  }, []);

  const handleExtract = async () => {
    if (!jdText.trim()) return;
    if (!socket?.connected) {
      setError("Not connected to server. Please wait...");
      return;
    }

    setIsExtracting(true);
    setError(null);
    setDiscoveryStatus("Sending context via Socket...");

    try {
      const data: any = {
        candidate_name: candidateName || "Candidate",
        jd_text: jdText,
        company_info: companyInfo,
      };

      if (resumeFile) {
        setDiscoveryStatus("Reading resume...");
        const reader = new FileReader();
        reader.onload = () => {
          const arrayBuffer = reader.result;
          data.resume_bytes = arrayBuffer;
          
          setDiscoveryStatus("AI is brainstorming... (Waiting for socket)");
          socket.emit('discovery_start', data);
        };
        reader.onerror = (e) => {
          console.error("FileReader error:", e);
          setError("Failed to read resume file.");
          setIsExtracting(false);
        };
        reader.readAsArrayBuffer(resumeFile);
      } else {
        setDiscoveryStatus("AI is brainstorming... (Waiting for socket)");
        socket.emit('discovery_start', data);
      }
      
      // We don't wait for a fetch response here. 
      // The result will come through the 'discovery_complete' listener in useEffect.
    } catch (err) {
      console.error("Extraction error:", err);
      setError("Extraction failed. Please check your connection and try again.");
      setIsExtracting(false);
    }
  };

  const handleStartInterview = async (finalSkills: SkillMap) => {
    if (!candidateName) {
      alert("Please enter candidate name");
      return;
    }
    setIsStarting(true);
    try {
      const formData = new FormData();
      formData.append('candidate_name', candidateName);
      formData.append('jd_text', jdText);
      formData.append('company_info', companyInfo);
      formData.append('extracted_skills', JSON.stringify(finalSkills));
      if (resumeFile) {
        formData.append('resume_file', resumeFile);
      }

      const response = await fetch(apiUrl('/sessions'), {
        method: 'POST',
        body: formData, // Multipart/form-data
      });
      
      const sessionData = await response.json();
      router.push(`/interview/${sessionData.share_url_slug}`);
    } catch (error) {
      console.error("Failed to start session:", error);
      alert("Failed to start session.");
      setIsStarting(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-900 flex flex-col items-center justify-center p-6 font-sans text-slate-200">
      <Head>
        <title>Devsko AI | Smart Interviewer</title>
      </Head>

      <main className="w-full max-w-4xl">
        <div className="text-center mb-12">
          <h1 className="text-5xl font-black bg-gradient-to-r from-blue-400 to-emerald-400 bg-clip-text text-transparent mb-2">
            AI Interview Architect
          </h1>
          <p className="text-slate-400 text-lg">Consolidated Contextual Intelligence</p>
        </div>

        {!skillMap ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <div className="space-y-6 bg-slate-800/50 p-8 rounded-2xl border border-slate-700 shadow-xl backdrop-blur-sm">
              <h2 className="text-2xl font-bold flex items-center gap-2">
                <span className="bg-blue-500/20 text-blue-400 p-2 rounded-lg text-sm">01</span>
                Interview Context
              </h2>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-slate-400 mb-1">Candidate Name</label>
                  <input
                    type="text"
                    className="w-full bg-slate-900 border border-slate-700 rounded-xl p-3 outline-none focus:ring-2 focus:ring-blue-500 transition-all"
                    placeholder="Enter full name..."
                    value={candidateName}
                    onChange={(e) => setCandidateName(e.target.value)}
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-400 mb-1">Company Info / Context</label>
                  <textarea
                    className="w-full h-32 bg-slate-900 border border-slate-700 rounded-xl p-4 outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                    placeholder="Details about your company, team, or project culture..."
                    value={companyInfo}
                    onChange={(e) => setCompanyInfo(e.target.value)}
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-400 mb-1">Resume (PDF)</label>
                  <input
                    type="file"
                    accept=".pdf"
                    className="w-full bg-slate-900 border border-slate-700 rounded-xl p-3 text-sm file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-600 file:text-white hover:file:bg-blue-700"
                    onChange={(e) => setResumeFile(e.target.files?.[0] || null)}
                  />
                </div>
              </div>
            </div>

            <div className="space-y-6 bg-slate-800/50 p-8 rounded-2xl border border-slate-700 shadow-xl backdrop-blur-sm">
              <h2 className="text-2xl font-bold flex items-center gap-2">
                <span className="bg-emerald-500/20 text-emerald-400 p-2 rounded-lg text-sm">02</span>
                Job Requirements
              </h2>
              
              <textarea
                className="w-full h-[320px] bg-slate-900 border border-slate-700 rounded-xl p-4 outline-none focus:ring-2 focus:ring-emerald-500 text-sm"
                placeholder="Paste Job Description here..."
                value={jdText}
                onChange={(e) => setJdText(e.target.value)}
              />

              <button
                onClick={handleExtract}
                disabled={isExtracting || !jdText.trim()}
                className="w-full py-4 bg-gradient-to-r from-blue-600 to-emerald-600 text-white rounded-xl font-bold hover:scale-[1.02] active:scale-[0.98] transition-all disabled:opacity-50 flex flex-col items-center justify-center gap-1 shadow-lg shadow-blue-900/20"
              >
                {isExtracting ? (
                  <>
                    <Loader2 className="animate-spin" />
                    <span className="text-xs font-normal opacity-80">{discoveryStatus}</span>
                  </>
                ) : (
                  "Analyze & Review Skills"
                )}
              </button>
            </div>
          </div>
        ) : (
          <div className="w-full relative animate-in fade-in zoom-in duration-300">
            {isStarting && (
              <div className="absolute inset-0 bg-slate-900/90 backdrop-blur-md z-50 flex flex-col items-center justify-center rounded-2xl border border-blue-500/30">
                 <Loader2 className="animate-spin text-blue-400 mb-4" size={56} />
                 <p className="font-bold text-2xl text-white">Synthesizing Architecture</p>
                 <p className="text-slate-400 mt-2">Hydrating LangGraph with consolidated context...</p>
              </div>
            )}
            <SkillReview 
              initialSkills={skillMap} 
              onStartInterview={handleStartInterview} 
            />
          </div>
        )}
        
        {error && <div className="mt-6 p-4 bg-red-500/10 border border-red-500/50 text-red-400 rounded-xl text-center">{error}</div>}
      </main>
    </div>
  );
}
