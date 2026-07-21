import { useState, useEffect, useCallback } from "react";
import {
  Flame, Target, TrendingDown, AlertTriangle,
  CheckCircle, BarChart2, Brain, Briefcase, ChevronDown
} from "lucide-react";
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis,
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, Cell
} from "recharts";
import axios from "axios";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import toast from "react-hot-toast";

const API = process.env.REACT_APP_API_URL || "http://127.0.0.1:5000/api";

function getDifficultyColor(difficulty) {
  if (difficulty === "Hard")   return { bg: "bg-brick-50",    text: "text-brick-600",    border: "border-brick-200"    };
  if (difficulty === "Medium") return { bg: "bg-gold-50",     text: "text-gold-700",     border: "border-gold-200"     };
  return                              { bg: "bg-verified-50", text: "text-verified-600", border: "border-verified-200" };
}

function getScoreColor(score) {
  if (score >= 70) return "#1F6E58";
  if (score >= 50) return "#C68A1E";
  return "#A23B2E";
}

export default function Heatmap() {
  const [jobs,          setJobs]          = useState([]);
  const [selectedJobId, setSelectedJobId] = useState("");
  const [data,          setData]          = useState(null);
  const [jobsLoading,   setJobsLoading]   = useState(true);
  const [dataLoading,   setDataLoading]   = useState(false);

  // ── Load the list of jobs that have completed interviews ──────────────────
  useEffect(() => {
    const fetchJobs = async () => {
      try {
        const token = localStorage.getItem("token");
        const res   = await axios.get(`${API}/pipeline/heatmap/jobs`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        const jobList = res.data.jobs || [];
        setJobs(jobList);
        if (jobList.length > 0) {
          setSelectedJobId(jobList[0].job_id);
        }
      } catch (err) {
        toast.error("Failed to load jobs list");
      } finally {
        setJobsLoading(false);
      }
    };
    fetchJobs();
  }, []);

  // ── Load heatmap data whenever the selected job changes ───────────────────
  const fetchHeatmap = useCallback(async (jobId) => {
    if (!jobId) return;
    setDataLoading(true);
    try {
      const token = localStorage.getItem("token");
      const res   = await axios.get(`${API}/pipeline/heatmap`, {
        params : { job_id: jobId },
        headers: { Authorization: `Bearer ${token}` }
      });
      setData(res.data);
    } catch (err) {
      toast.error("Failed to load heatmap data");
    } finally {
      setDataLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedJobId) {
      fetchHeatmap(selectedJobId);
    }
  }, [selectedJobId, fetchHeatmap]);

  // ── Job selector dropdown (shown on every state) ──────────────────────────
  const JobSelector = () => (
    <div className="relative inline-block">
      <select
        value={selectedJobId}
        onChange={(e) => setSelectedJobId(e.target.value)}
        className="appearance-none bg-white border border-stone-200 text-ink-500 text-sm rounded-xl pl-4 pr-10 py-2.5 shadow-card focus:outline-none focus:border-ledger-400 focus:ring-2 focus:ring-ledger-50 cursor-pointer"
      >
        {jobs.map((j) => (
          <option key={j.job_id} value={j.job_id}>
            {j.job_title} ({j.interviews} interview{j.interviews !== 1 ? "s" : ""})
          </option>
        ))}
      </select>
      <ChevronDown size={16} className="absolute right-3 top-1/2 -translate-y-1/2 text-stone-400 pointer-events-none" />
    </div>
  );

  // ── Loading state: still fetching the jobs list ───────────────────────────
  if (jobsLoading) {
    return (
      <div className="h-64 flex items-center justify-center">
        <LoadingSpinner size="lg" text="Loading jobs..." />
      </div>
    );
  }

  // ── No jobs with completed interviews at all ──────────────────────────────
  if (jobs.length === 0) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-ink-500">Interview Heatmap</h1>
          <p className="text-stone-500 text-sm mt-1">Performance insights from completed interviews</p>
        </div>
        <div className="card text-center py-20">
          <Flame size={48} className="text-stone-300 mx-auto mb-4" />
          <p className="text-stone-500 font-medium">No completed interviews yet</p>
          <p className="text-stone-400 text-sm mt-1">
            Complete at least one voice interview for a job to see performance analytics
          </p>
        </div>
      </div>
    );
  }

  // ── Prepare radar chart data from question stats ──────────────────────────
  const radarData = (data?.question_stats || []).slice(0, 6).map((q, i) => ({
    subject : `Q${i + 1}`,
    score   : q.avg_score,
    fullMark: 100
  }));

  return (
    <div className="space-y-6">

      {/* Header + job selector */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-ink-500 flex items-center gap-2">
            <Flame size={24} className="text-gold-600" />
            Interview Performance Heatmap
          </h1>
          <p className="text-stone-500 text-sm mt-1 flex items-center gap-2">
            <Briefcase size={14} />
            {data ? (
              <>Viewing <span className="text-ink-500 font-medium">{data.job_title}</span> — {data.total_interviews} completed interview{data.total_interviews !== 1 ? "s" : ""}</>
            ) : (
              "Select a job to view its performance data"
            )}
          </p>
        </div>
        <JobSelector />
      </div>

      {dataLoading && (
        <div className="h-64 flex items-center justify-center">
          <LoadingSpinner size="lg" text="Analyzing interview performance..." />
        </div>
      )}

      {!dataLoading && data && data.total_interviews === 0 && (
        <div className="card text-center py-20">
          <Flame size={48} className="text-stone-300 mx-auto mb-4" />
          <p className="text-stone-500 font-medium">No completed interviews for this job yet</p>
          <p className="text-stone-400 text-sm mt-1">
            Complete at least one voice interview for this job to see performance analytics
          </p>
        </div>
      )}

      {!dataLoading && data && data.total_interviews > 0 && (
        <>
          {/* Top stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: "Interviews Done",  value: data.total_interviews,  icon: Brain,         iconBg: "bg-ledger-50",   iconColor: "text-ledger-600"   },
              { label: "Avg Score",        value: `${data.avg_score}%`,   icon: Target,        iconBg: "bg-ink-50",     iconColor: "text-ink-500"      },
              { label: "Pass Rate",        value: `${data.pass_rate}%`,   icon: CheckCircle,   iconBg: "bg-verified-50", iconColor: "text-verified-600" },
              { label: "Skill Gaps Found", value: data.skill_gaps.length, icon: AlertTriangle, iconBg: "bg-gold-50",    iconColor: "text-gold-600"     }
            ].map((s, i) => (
              <div key={i} className="card flex items-center gap-4">
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${s.iconBg}`}>
                  <s.icon size={18} className={s.iconColor} />
                </div>
                <div>
                  <p className="text-2xl font-bold font-mono text-ink-500">{s.value}</p>
                  <p className="text-stone-500 text-xs">{s.label}</p>
                </div>
              </div>
            ))}
          </div>

          {/* Charts row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

            {/* Question performance bar chart */}
            <div className="card">
              <h3 className="font-semibold text-ink-500 mb-2 flex items-center gap-2">
                <TrendingDown size={16} className="text-brick-600" />
                Weakest Questions
              </h3>
              <p className="text-stone-400 text-xs mb-4">
                Questions with lowest average scores for {data.job_title} candidates
              </p>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart
                  data={data.question_stats.slice(0, 6).map((q, i) => ({
                    name : `Q${i + 1}`,
                    score: q.avg_score,
                    full : q.question
                  }))}
                  layout="vertical"
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#DEE0D6" />
                  <XAxis type="number" domain={[0, 100]} tick={{ fill: "#8A8D7C", fontSize: 11 }} />
                  <YAxis type="category" dataKey="name" tick={{ fill: "#4F5D78", fontSize: 11 }} width={30} />
                  <Tooltip
                    content={({ active, payload }) => {
                      if (active && payload?.length) {
                        const d = payload[0].payload;
                        return (
                          <div className="bg-white border border-stone-200 rounded-xl p-3 shadow-card-md max-w-xs">
                            <p className="text-ink-500 text-xs font-medium mb-1">{d.full}</p>
                            <p className="text-gold-700 text-sm font-bold">Avg: {d.score}/100</p>
                          </div>
                        );
                      }
                      return null;
                    }}
                  />
                  <Bar dataKey="score" radius={[0, 4, 4, 0]} name="Avg Score">
                    {data.question_stats.slice(0, 6).map((q, i) => (
                      <Cell key={i} fill={getScoreColor(q.avg_score)} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Radar chart */}
            <div className="card">
              <h3 className="font-semibold text-ink-500 mb-2 flex items-center gap-2">
                <BarChart2 size={16} className="text-ledger-500" />
                Performance Radar
              </h3>
              <p className="text-stone-400 text-xs mb-4">
                Multi-dimensional view of question performance
              </p>
              <ResponsiveContainer width="100%" height={280}>
                <RadarChart data={radarData}>
                  <PolarGrid stroke="#DEE0D6" />
                  <PolarAngleAxis dataKey="subject" tick={{ fill: "#4F5D78", fontSize: 12 }} />
                  <Radar
                    name="Score"
                    dataKey="score"
                    stroke="#2A4B7C"
                    fill="#2A4B7C"
                    fillOpacity={0.3}
                  />
                  <Tooltip
                    contentStyle={{
                      background  : "#FFFFFF",
                      border      : "1px solid #DEE0D6",
                      borderRadius: "12px"
                    }}
                  />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Question breakdown table */}
          <div className="card">
            <h3 className="font-semibold text-ink-500 mb-4 flex items-center gap-2">
              <Flame size={16} className="text-gold-600" />
              Question-by-Question Breakdown
            </h3>
            <div className="space-y-3">
              {data.question_stats.map((q, i) => {
                const dc = getDifficultyColor(q.difficulty);
                return (
                  <div key={i} className="p-4 bg-stone-50 rounded-xl border border-stone-200">
                    <div className="flex items-start justify-between gap-4 mb-3">
                      <p className="text-sm text-ink-500 flex-1">{q.question}...</p>
                      <div className="flex items-center gap-2 shrink-0">
                        <span className={`text-xs px-2 py-0.5 rounded-full border ${dc.bg} ${dc.text} ${dc.border}`}>
                          {q.difficulty}
                        </span>
                        <span className="text-lg font-bold font-mono" style={{ color: getScoreColor(q.avg_score) }}>
                          {q.avg_score}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-6 text-xs text-stone-500">
                      <span>{q.attempts} attempt{q.attempts !== 1 ? "s" : ""}</span>
                      <span>Min: {q.min_score}</span>
                      <span>Max: {q.max_score}</span>
                      <span className={q.pass_rate >= 70 ? "text-verified-600" : "text-brick-600"}>
                        Pass rate: {q.pass_rate}%
                      </span>
                    </div>
                    <div className="mt-2 h-1.5 bg-stone-200 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-700"
                        style={{
                          width          : `${q.avg_score}%`,
                          backgroundColor: getScoreColor(q.avg_score)
                        }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Skill gaps */}
          {data.skill_gaps.length > 0 && (
            <div className="card">
              <h3 className="font-semibold text-ink-500 mb-2 flex items-center gap-2">
                <AlertTriangle size={16} className="text-gold-600" />
                Skill Gaps for {data.job_title} Candidates
              </h3>
              <p className="text-stone-400 text-xs mb-4">
                Skills most frequently missing among candidates for this job
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {data.skill_gaps.map((sg, i) => (
                  <div key={i} className="p-3 bg-stone-50 rounded-xl border border-stone-200">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-ink-500">{sg.skill}</span>
                      <span className={`text-sm font-bold font-mono ${
                        sg.gap_rate >= 70 ? "text-brick-600" : sg.gap_rate >= 40 ? "text-gold-700" : "text-verified-600"
                      }`}>
                        {sg.gap_rate}% gap
                      </span>
                    </div>
                    <div className="h-1.5 bg-stone-200 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full"
                        style={{
                          width          : `${sg.gap_rate}%`,
                          backgroundColor: sg.gap_rate >= 70 ? "#A23B2E" : sg.gap_rate >= 40 ? "#C68A1E" : "#1F6E58"
                        }}
                      />
                    </div>
                    <p className="text-stone-400 text-xs mt-1">
                      {sg.fail_count} of {sg.total} candidates missing this skill
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}