import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Briefcase, Users, GitBranch,
  TrendingUp, Plus, ArrowRight,
  CheckCircle, Clock, XCircle
} from "lucide-react";
import { jobsAPI } from "../../api/jobs";
import { candidatesAPI } from "../../api/candidates";
import { useAuth } from "../../context/AuthContext";
import Button from "../../components/ui/Button";
import Badge from "../../components/ui/Badge";
import LoadingSpinner from "../../components/ui/LoadingSpinner";

// ── Stat Card ────────────────────────────────────────────────────────────────
function StatCard({ label, value, icon: Icon, color, sub }) {
  return (
    <div className="card hover:border-dark-700 transition-all duration-200">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-dark-400 text-sm">{label}</p>
          <p className="text-3xl font-bold text-white mt-1">{value}</p>
          {sub && <p className="text-dark-500 text-xs mt-1">{sub}</p>}
        </div>
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${color}`}>
          <Icon size={20} className="text-white" />
        </div>
      </div>
    </div>
  );
}

// ── Agent Status Card ─────────────────────────────────────────────────────────
function AgentCard({ name, description, status }) {
  return (
    <div className="flex items-center gap-3 p-3 rounded-lg bg-dark-800/50 border border-dark-800">
      <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse-slow" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-white truncate">{name}</p>
        <p className="text-xs text-dark-400 truncate">{description}</p>
      </div>
      <Badge variant="green">{status}</Badge>
    </div>
  );
}

const agents = [
  { name: "JD Parser",          description: "Extracts structured data from JDs",       status: "Live" },
  { name: "Resume Screener",    description: "Scores resumes 0-100",                    status: "Live" },
  { name: "Question Generator", description: "Creates personalized questions",           status: "Live" },
  { name: "Email Sender",       description: "Sends shortlist emails",                  status: "Live" },
  { name: "Answer Evaluator",   description: "Scores interview answers",                status: "Live" },
  { name: "AI Interviewer",     description: "Conducts voice interviews",               status: "Live" },
  { name: "Scheduler",          description: "Books next interview round",              status: "Live" }
];

export default function Dashboard() {
  const [jobs,       setJobs]       = useState([]);
  const [loading,    setLoading]    = useState(true);
  const [totalCands, setTotalCands] = useState(0);
  const { company }                 = useAuth();
  const navigate                    = useNavigate();

  useEffect(() => {
    const fetchData = async () => {
      try {
        const jobsRes = await jobsAPI.getAll();
        const jobs    = jobsRes.data.jobs || [];
        setJobs(jobs);
        const total = jobs.reduce((sum, j) => sum + (j.candidates_count || 0), 0);
        setTotalCands(total);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="h-64 flex items-center justify-center">
        <LoadingSpinner size="lg" text="Loading dashboard..." />
      </div>
    );
  }

  const activeJobs = jobs.filter(j => j.status === "active").length;

  return (
    <div className="space-y-6">

      {/* Welcome */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">
            Welcome back, {company?.company_name} 👋
          </h1>
          <p className="text-dark-400 text-sm mt-1">
            Your AI recruitment pipeline is ready
          </p>
        </div>
        <Button onClick={() => navigate("/jobs")}>
          <Plus size={16} />
          Post a Job
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Total Jobs"
          value={jobs.length}
          icon={Briefcase}
          color="bg-primary-600"
          sub={`${activeJobs} active`}
        />
        <StatCard
          label="Total Candidates"
          value={totalCands}
          icon={Users}
          color="bg-purple-600"
          sub="Across all jobs"
        />
        <StatCard
          label="AI Agents"
          value="7"
          icon={GitBranch}
          color="bg-green-600"
          sub="All systems live"
        />
        <StatCard
          label="Avg Match Score"
          value="82%"
          icon={TrendingUp}
          color="bg-orange-600"
          sub="Based on evaluations"
        />
      </div>

      {/* Main grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Recent Jobs */}
        <div className="lg:col-span-2 card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-white">Recent Jobs</h3>
            <button
              onClick={() => navigate("/jobs")}
              className="text-primary-400 hover:text-primary-300 text-sm flex items-center gap-1"
            >
              View all <ArrowRight size={14} />
            </button>
          </div>

          {jobs.length === 0 ? (
            <div className="text-center py-12">
              <Briefcase size={40} className="text-dark-600 mx-auto mb-3" />
              <p className="text-dark-400">No jobs posted yet</p>
              <Button
                className="mt-4 mx-auto"
                onClick={() => navigate("/jobs")}
              >
                <Plus size={16} /> Post First Job
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              {jobs.slice(0, 5).map((job) => (
                <div
                  key={job._id}
                  onClick={() => navigate(`/jobs/${job._id}`)}
                  className="flex items-center justify-between p-3 rounded-lg bg-dark-800/50 border border-dark-800 hover:border-dark-700 cursor-pointer transition-all"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 bg-primary-600/20 rounded-lg flex items-center justify-center">
                      <Briefcase size={16} className="text-primary-400" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-white">{job.job_title}</p>
                      <p className="text-xs text-dark-400">{job.location} · {job.job_type}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-dark-400">
                      {job.candidates_count || 0} candidates
                    </span>
                    <Badge status={job.status}>{job.status}</Badge>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* AI Agents Status */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-white">AI Agents</h3>
            <Badge variant="green">All Live</Badge>
          </div>
          <div className="space-y-2">
            {agents.map((agent) => (
              <AgentCard key={agent.name} {...agent} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}