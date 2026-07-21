import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Briefcase, Users, GitBranch, TrendingUp,
  Plus, ArrowRight, CheckCircle
} from "lucide-react";
import { jobsAPI } from "../../api/jobs";
import { useAuth } from "../../context/AuthContext";
import Button from "../../components/ui/Button";
import Badge from "../../components/ui/Badge";
import LoadingSpinner from "../../components/ui/LoadingSpinner";

function StatCard({ label, value, icon: Icon, color, sub }) {
  return (
    <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-card hover:shadow-card-md transition-all duration-200">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-gray-500">{label}</p>
          <p className="text-3xl font-bold text-gray-900 mt-1">{value}</p>
          {sub && <p className="text-xs text-gray-400 mt-1 font-medium">{sub}</p>}
        </div>
        <div className={`w-11 h-11 rounded-xl flex items-center justify-center ${color}`}>
          <Icon size={20} className="text-white" />
        </div>
      </div>
    </div>
  );
}

function AgentCard({ name, description }) {
  return (
    <div className="flex items-center gap-3 p-3 rounded-xl bg-gray-50 border border-gray-100">
      <div className="w-2 h-2 rounded-full bg-emerald-500 shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-gray-800 truncate">{name}</p>
        <p className="text-xs text-gray-400 truncate">{description}</p>
      </div>
      <span className="badge-green text-xs px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 font-semibold shrink-0">
        Live
      </span>
    </div>
  );
}

const agents = [
  { name: "JD Parser",          description: "Extracts structured data from JDs"   },
  { name: "Resume Screener",    description: "Scores resumes 0-100"                },
  { name: "Question Generator", description: "Creates personalized questions"       },
  { name: "Email Sender",       description: "Sends shortlist emails"              },
  { name: "Answer Evaluator",   description: "Scores interview answers"            },
  { name: "AI Interviewer",     description: "Conducts voice interviews"           },
  { name: "Scheduler",          description: "Books next interview round"          }
];

export default function Dashboard() {
  const [jobs,    setJobs]    = useState([]);
  const [loading, setLoading] = useState(true);
  const [total,   setTotal]   = useState(0);
  const { company }           = useAuth();
  const navigate              = useNavigate();

  useEffect(() => {
    jobsAPI.getAll().then(res => {
      const j = res.data.jobs || [];
      setJobs(j);
      setTotal(j.reduce((s, jb) => s + (jb.candidates_count || 0), 0));
    }).finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="h-64 flex items-center justify-center">
      <LoadingSpinner size="lg" text="Loading dashboard..." />
    </div>
  );

  return (
    <div className="space-y-6">

      {/* Welcome */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Welcome back, {company?.company_name} 👋
          </h1>
          <p className="text-gray-500 text-sm mt-1">Your AI recruitment pipeline is ready</p>
        </div>
        <Button onClick={() => navigate("/jobs")}>
          <Plus size={16} /> Post a Job
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Total Jobs"       value={jobs.length} icon={Briefcase}  color="bg-indigo-600" sub={`${jobs.filter(j=>j.status==="active").length} active`} />
        <StatCard label="Total Candidates" value={total}       icon={Users}       color="bg-violet-600" sub="Across all jobs"   />
        <StatCard label="AI Agents"        value="7"           icon={GitBranch}   color="bg-emerald-600" sub="All systems live" />
        <StatCard label="Avg Match Score"  value="82%"         icon={TrendingUp}  color="bg-amber-500"  sub="Based on evaluations" />
      </div>

      {/* Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Recent Jobs */}
        <div className="lg:col-span-2 bg-white rounded-2xl border border-gray-200 shadow-card p-6">
          <div className="flex items-center justify-between mb-5">
            <h3 className="font-bold text-gray-900">Recent Jobs</h3>
            <button onClick={() => navigate("/jobs")} className="text-indigo-600 hover:text-indigo-700 text-sm font-semibold flex items-center gap-1">
              View all <ArrowRight size={14} />
            </button>
          </div>
          {jobs.length === 0 ? (
            <div className="text-center py-12">
              <Briefcase size={36} className="text-gray-300 mx-auto mb-3" />
              <p className="text-gray-500 font-medium">No jobs posted yet</p>
              <Button className="mt-4 mx-auto" onClick={() => navigate("/jobs")}>
                <Plus size={16} /> Post First Job
              </Button>
            </div>
          ) : (
            <div className="space-y-2">
              {jobs.slice(0, 5).map((job) => (
                <div
                  key={job._id}
                  onClick={() => navigate(`/jobs/${job._id}`)}
                  className="flex items-center justify-between p-3.5 rounded-xl bg-gray-50 hover:bg-indigo-50 border border-transparent hover:border-indigo-100 cursor-pointer transition-all"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 bg-indigo-100 rounded-lg flex items-center justify-center">
                      <Briefcase size={15} className="text-indigo-600" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-gray-900">{job.job_title}</p>
                      <p className="text-xs text-gray-400">{job.location} · {job.job_type}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-gray-400 font-medium">{job.candidates_count || 0} candidates</span>
                    <Badge status={job.status}>{job.status}</Badge>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* AI Agents */}
        <div className="bg-white rounded-2xl border border-gray-200 shadow-card p-6">
          <div className="flex items-center justify-between mb-5">
            <h3 className="font-bold text-gray-900">AI Agents</h3>
            <span className="badge-green text-xs px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 font-semibold">
              All Live
            </span>
          </div>
          <div className="space-y-2">
            {agents.map(a => <AgentCard key={a.name} {...a} />)}
          </div>
        </div>
      </div>
    </div>
  );
}