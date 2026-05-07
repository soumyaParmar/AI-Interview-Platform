import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import Head from 'next/head';
import { CheckCircle, AlertCircle, BarChart3, ArrowLeft, Download } from 'lucide-react';
import { apiUrl } from '../../lib/api';

interface QuestionThread {
  question_type: string;
  question_text: string;
  candidate_response: string;
  evaluation: {
    score: number;
    clarity: string;
    accuracy: string;
    individual_feedback: string;
  };
}

interface TopicAnalysis {
  topic_name: string;
  topic_overall_score: number;
  demonstrated_depth: 'L1' | 'L2' | 'L3';
  topic_feedback: string;
  improvement_areas: string[];
  question_threads: QuestionThread[];
}

interface Report {
  report_summary: {
    overall_score: number;
    hiring_verdict: string;
    pass_fail_status: string;
    executive_summary: string;
    honesty_score: number;
    professional_experience_notes: string;
  };
  skill_topic_analysis: TopicAnalysis[];
  soft_skills: {
    problem_solving: number;
    communication: number;
    adaptability: number;
  };
}

export default function ReportPage() {
  const router = useRouter();
  const { id } = router.query;
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;

    const fetchReport = async () => {
      try {
        const response = await fetch(apiUrl(`/sessions/${id}/report`));
        if (!response.ok) {
          throw new Error('Report not found or not yet generated.');
        }
        const data = await response.json();
        setReport(data);
      } catch (err: unknown) {
        if (err instanceof Error) {
          setError(err.message);
        } else {
          setError('An unknown error occurred.');
        }
      } finally {
        setLoading(false);
      }
    };

    fetchReport();
  }, [id]);

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-gray-50">
        <div className="w-16 h-16 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mb-4"></div>
        <p className="text-gray-600 font-medium">Loading your evaluation...</p>
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-gray-50 p-4 text-center">
        <AlertCircle className="text-red-500 mb-4" size={64} />
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Evaluation Not Ready</h1>
        <p className="text-gray-600 mb-6 max-w-sm">
          We couldn&apos;t find the report for this session. It might still be generating or the session ID is invalid.
        </p>
        <button 
          onClick={() => router.push('/')}
          className="px-6 py-2 bg-blue-600 text-white rounded-lg font-bold hover:bg-blue-700 transition-colors"
        >
          Back to Home
        </button>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 font-sans text-gray-800 pb-20">
      <Head>
        <title>Interview Report | Devsko AI</title>
      </Head>

      <nav className="bg-white border-b sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center text-white font-bold">D</div>
            <span className="font-bold text-xl tracking-tight text-gray-900">Devsko <span className="text-blue-600">Report</span></span>
          </div>
          <button 
            onClick={() => window.print()}
            className="flex items-center gap-2 px-4 py-2 text-sm font-semibold text-gray-600 hover:bg-gray-100 rounded-lg transition-colors border"
          >
            <Download size={16} />
            Export PDF
          </button>
        </div>
      </nav>

      <main className="max-w-4xl mx-auto px-4 mt-8">
        {/* Hero Section */}
        <div className="bg-white rounded-2xl p-8 shadow-sm border mb-8 flex flex-col md:flex-row items-center gap-8">
          <div className="relative">
            <svg className="w-40 h-40 transform -rotate-90">
              <circle
                cx="80"
                cy="80"
                r="70"
                stroke="currentColor"
                strokeWidth="12"
                fill="transparent"
                className="text-gray-100"
              />
              <circle
                cx="80"
                cy="80"
                r="70"
                stroke="currentColor"
                strokeWidth="12"
                fill="transparent"
                strokeDasharray={440}
                strokeDashoffset={440 - (440 * report.report_summary.overall_score) / 100}
                className={`${report.report_summary.overall_score >= 70 ? 'text-green-500' : 'text-blue-600'} transition-all duration-1000 ease-out`}
                strokeLinecap="round"
              />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-4xl font-black text-gray-900">{report.report_summary.overall_score}</span>
              <span className="text-xs font-bold text-gray-400 uppercase tracking-widest">Score</span>
            </div>
          </div>
          
          <div className="flex-1 text-center md:text-left">
            <div className="flex flex-col md:flex-row md:items-center gap-2 mb-2">
              <h1 className="text-3xl font-extrabold text-gray-900">Analyst Audit Result</h1>
              <span className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider w-fit mx-auto md:mx-0 ${
                report.report_summary.hiring_verdict === 'Strong Hire' ? 'bg-green-100 text-green-700' : 
                report.report_summary.hiring_verdict === 'Hire' ? 'bg-blue-100 text-blue-700' : 'bg-red-100 text-red-700'
              }`}>
                {report.report_summary.hiring_verdict}
              </span>
            </div>
            <p className="text-gray-500 mb-4 font-medium uppercase tracking-wide text-sm flex items-center justify-center md:justify-start gap-2">
              <BarChart3 size={16} className="text-blue-500" />
              High-Fidelity Evaluation
            </p>
            <div className="p-4 bg-gray-50 rounded-xl border border-gray-100 text-gray-700 leading-relaxed italic">
              &quot;{report.report_summary.executive_summary}&quot;
            </div>

            <div className="mt-4 flex items-center gap-6">
                <div>
                   <p className="text-[10px] uppercase font-bold text-gray-400 mb-1">Honesty Score</p>
                   <div className="flex items-center gap-2">
                      <div className="h-1.5 w-24 bg-gray-200 rounded-full overflow-hidden">
                         <div className="h-full bg-orange-500" style={{ width: `${report.report_summary.honesty_score * 10}%` }}></div>
                      </div>
                      <span className="text-xs font-bold">{report.report_summary.honesty_score}/10</span>
                   </div>
                </div>
                <div className="border-l pl-6">
                   <p className="text-[10px] uppercase font-bold text-gray-400 mb-1">Pass Status</p>
                   <span className={`text-sm font-bold ${report.report_summary.pass_fail_status === 'Pass' ? 'text-green-600' : 'text-red-600'}`}>
                      {report.report_summary.pass_fail_status}
                   </span>
                </div>
            </div>
          </div>
        </div>

        {/* Professional Experience Notes */}
        <div className="bg-amber-50 border border-amber-100 rounded-xl p-4 mb-8 flex items-start gap-3">
           <AlertCircle className="text-amber-500 mt-0.5" size={20} />
           <div>
              <p className="text-sm font-bold text-amber-900">Professional Audit Note</p>
              <p className="text-xs text-amber-800 mt-0.5">{report.report_summary.professional_experience_notes}</p>
           </div>
        </div>

        {/* Skill Breakdown */}
        <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
          <CheckCircle className="text-green-500" size={24} />
          Technical Depth Analysis
        </h2>
        
        <div className="grid grid-cols-1 gap-6">
          {report.skill_topic_analysis.map((topic, idx) => (
            <div key={idx} className="bg-white rounded-xl shadow-sm border overflow-hidden">
              <div className="p-6 bg-white border-b flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-bold text-gray-900">{topic.topic_name}</h3>
                  <div className="flex items-center gap-2 mt-1">
                     <span className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase ${
                        topic.demonstrated_depth === 'L3' ? 'bg-purple-100 text-purple-700' :
                        topic.demonstrated_depth === 'L2' ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-700'
                     }`}>Depth {topic.demonstrated_depth}</span>
                     <span className="text-xs text-gray-400">Score: {topic.topic_overall_score}/10</span>
                  </div>
                </div>
                <div className="h-2 w-24 bg-gray-100 rounded-full overflow-hidden">
                  <div className="h-full bg-blue-600" style={{ width: `${topic.topic_overall_score * 10}%` }}></div>
                </div>
              </div>
              
              <div className="p-6">
                 <p className="text-sm text-gray-600 mb-4">{topic.topic_feedback}</p>
                 
                 {topic.improvement_areas.length > 0 && (
                    <div className="mb-4">
                       <p className="text-xs font-bold text-gray-400 uppercase mb-2">Improvement Areas</p>
                       <div className="flex flex-wrap gap-2">
                          {topic.improvement_areas.map((area, i) => (
                             <span key={i} className="px-2 py-1 bg-red-50 text-red-600 text-xs rounded-lg border border-red-100">{area}</span>
                          ))}
                       </div>
                    </div>
                 )}

                 <div className="space-y-4 pt-4 border-t">
                    <p className="text-xs font-bold text-gray-400 uppercase">Question Threads (Sample)</p>
                    {topic.question_threads.slice(0, 2).map((thread, i) => (
                       <div key={i} className="bg-gray-50 rounded-lg p-3 text-xs">
                          <p className="font-bold text-gray-700 mb-1">Q: {thread.question_text}</p>
                          <p className="text-gray-600 italic mb-2">&quot;{thread.candidate_response}&quot;</p>
                          <div className="flex items-center gap-2 text-blue-600 font-medium">
                             <span>Acc: {thread.evaluation.accuracy}</span>
                             <span>•</span>
                             <span>Score: {thread.evaluation.score}/10</span>
                          </div>
                       </div>
                    ))}
                 </div>
              </div>
            </div>
          ))}
        </div>

        {/* Soft Skills */}
        <div className="mt-12 grid grid-cols-1 md:grid-cols-3 gap-4">
           {Object.entries(report.soft_skills).map(([skill, score]) => (
              <div key={skill} className="bg-white p-4 rounded-xl border shadow-sm text-center">
                 <p className="text-xs font-bold text-gray-400 uppercase mb-2">{skill.replace('_', ' ')}</p>
                 <span className="text-2xl font-black text-gray-900">{score}<span className="text-xs text-gray-400">/10</span></span>
                 <div className="h-1 w-full bg-gray-100 rounded-full mt-3 overflow-hidden">
                    <div className="h-full bg-indigo-500" style={{ width: `${Number(score) * 10}%` }}></div>
                 </div>
              </div>
           ))}
        </div>

        <div className="mt-12 text-center">
           <button 
             onClick={() => router.push('/')}
             className="inline-flex items-center gap-2 text-blue-600 font-bold hover:underline"
           >
             <ArrowLeft size={18} />
             Start Another Interview
           </button>
        </div>
      </main>
    </div>
  );
}
