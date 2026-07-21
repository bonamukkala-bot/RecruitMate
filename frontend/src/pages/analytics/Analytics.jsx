import { useState, useEffect } from "react";
import {
  Briefcase, Users, TrendingUp, Award,
  BarChart2, PieChart, Target, Zap
} from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, PieChart as RPieChart, Pie, Cell,
  FunnelChart, Funnel, LabelList, AreaChart, Area
} from "recharts";
import { jobsAPI } from "../../api/jobs";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import toast from "react-hot-toast";

const COLORS = ["#2A4B7C", "#1F6E58", "#C68A1E", "#A23B2E", "#4F5D78", "#8A8D7C"];

// ── Stat Card ────────────────────────────────────────────────────────────────
function StatCard({ label, value, icon: Icon, iconBg, iconColor, sub, trend }) {
  return (
    <div className="card hover:border-ledger-200 transition-all duration-200">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-stone-500 text-sm">{label}</p>
          <p className="text-3xl font-bold font-mono text-ink-500 mt-1">{value}</p>
          {sub && <p className="text-stone-400 text-xs mt-1">{sub}</p>}
          {trend && (
            <p className="text-verified-600 text-xs mt-1 flex items-center gap-1">
              <TrendingUp size={12} /> {trend}
            </p>
          )}
        </div>
        <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${iconBg}`}>
          <Icon size={22} className={iconColor} />
        </div>
      </div>
    </div>
  );
}

// ── Custom Tooltip ────────────────────────────────────────────────────────────
function CustomTooltip({ active, payload, label }) {
  if (active && payload && payload.length) {
    return (
      <div className="bg-white border border-stone-200 rounded-xl p-3 shadow-card-md">
        <p className="text-stone-500 text-xs mb-1">{label}</p>
        {payload.map((p, i) => (
          <p key={i} className="text-ink-500 text-sm font-medium">
            {p.name}: <span style={{ color: p.color }}>{p.value}</span>
          </p>
        ))}
      </div>
    );
  }
  return null;
}

export default function Analytics() {
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAnalytics();
  }, []);

  const fetchAnalytics = async () => {
    try {
      const res = await jobsAPI.getAnalytics();
      setData(res.data);
    } catch (err) {
      toast.error("Failed to load analytics");
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="h-64 flex items-center justify-center">
        <LoadingSpinner size="lg" text="Loading analytics..." />
      </div>
    );
  }

  if (!data) return null;

  // Prepare chart data
  const funnelData = [
    { name: "Screened",    value: data.funnel.screened,    fill: "#2A4B7C" },
    { name: "Shortlisted", value: data.funnel.shortlisted, fill: "#1F6E58" },
    { name: "Invited",     value: data.funnel.invited,     fill: "#C68A1E" },
    { name: "Advanced",    value: data.funnel.advance,     fill: "#6E96C0" },
    { name: "Hired",       value: data.funnel.hired,       fill: "#12203A" }
  ].filter(d => d.value > 0);

  const scoreDistData = Object.entries(data.score_dist).map(([range, count]) => ({
    range, count
  }));

  const skillsData = data.top_skills.map(([skill, count]) => ({ skill, count }));

  const jobStatsData = data.job_stats.map(j => ({
    name     : j.job_title.length > 20 ? j.job_title.slice(0, 20) + "..." : j.job_title,
    candidates: j.total_candidates,
    avg_score : j.avg_score,
    shortlisted: j.shortlisted
  }));

  return (
    <div className="space-y-6">

      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-ink-500">Analytics</h1>
        <p className="text-stone-500 text-sm mt-1">
          Real-time insights into your recruitment pipeline
        </p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Total Jobs"
          value={data.total_jobs}
          icon={Briefcase}
          iconBg="bg-ledger-50"
          iconColor="text-ledger-600"
          sub={`${data.active_jobs} active`}
        />
        <StatCard
          label="Total Candidates"
          value={data.total_candidates}
          icon={Users}
          iconBg="bg-gold-50"
          iconColor="text-gold-600"
          sub="Across all jobs"
        />
        <StatCard
          label="Avg Match Score"
          value={`${data.avg_score}%`}
          icon={Target}
          iconBg="bg-verified-50"
          iconColor="text-verified-600"
          sub="AI screening score"
        />
        <StatCard
          label="Pass Rate"
          value={`${data.pass_rate}%`}
          icon={Award}
          iconBg="bg-ink-50"
          iconColor="text-ink-500"
          sub="Advanced to next round"
        />
      </div>

      {/* Charts row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* Pipeline Funnel */}
        <div className="card">
          <h3 className="font-semibold text-ink-500 mb-6 flex items-center gap-2">
            <BarChart2 size={16} className="text-ledger-500" />
            Recruitment Funnel
          </h3>
          {funnelData.length === 0 ? (
            <div className="h-48 flex items-center justify-center text-stone-400 text-sm">
              No pipeline data yet
            </div>
          ) : (
            <div className="space-y-3">
              {funnelData.map((item, i) => (
                <div key={i} className="space-y-1">
                  <div className="flex justify-between text-sm">
                    <span className="text-stone-600">{item.name}</span>
                    <span className="text-ink-500 font-medium font-mono">{item.value}</span>
                  </div>
                  <div className="h-2 bg-stone-100 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-700"
                      style={{
                        width: `${(item.value / (funnelData[0]?.value || 1)) * 100}%`,
                        backgroundColor: item.fill
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Score Distribution */}
        <div className="card">
          <h3 className="font-semibold text-ink-500 mb-6 flex items-center gap-2">
            <PieChart size={16} className="text-gold-600" />
            Score Distribution
          </h3>
          {data.total_candidates === 0 ? (
            <div className="h-48 flex items-center justify-center text-stone-400 text-sm">
              No candidates yet
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <RPieChart>
                <Pie
                  data={scoreDistData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={90}
                  dataKey="count"
                  nameKey="range"
                  paddingAngle={3}
                >
                  {scoreDistData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    background  : "#FFFFFF",
                    border      : "1px solid #DEE0D6",
                    borderRadius: "12px"
                  }}
                  formatter={(val, name) => [val, name]}
                />
              </RPieChart>
            </ResponsiveContainer>
          )}
          <div className="flex flex-wrap gap-3 mt-2 justify-center">
            {scoreDistData.map((d, i) => (
              <div key={i} className="flex items-center gap-1.5 text-xs text-stone-600">
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
                {d.range}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Charts row 2 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* Top skills in demand */}
        <div className="card">
          <h3 className="font-semibold text-ink-500 mb-6 flex items-center gap-2">
            <Zap size={16} className="text-gold-600" />
            Top Skills in Demand
          </h3>
          {skillsData.length === 0 ? (
            <div className="h-48 flex items-center justify-center text-stone-400 text-sm">
              No jobs posted yet
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={skillsData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#DEE0D6" />
                <XAxis type="number" tick={{ fill: "#8A8D7C", fontSize: 11 }} />
                <YAxis
                  type="category"
                  dataKey="skill"
                  tick={{ fill: "#4F5D78", fontSize: 11 }}
                  width={80}
                />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="count" fill="#2A4B7C" radius={[0, 4, 4, 0]} name="Jobs" />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Per job performance */}
        <div className="card">
          <h3 className="font-semibold text-ink-500 mb-6 flex items-center gap-2">
            <TrendingUp size={16} className="text-verified-600" />
            Performance by Job
          </h3>
          {jobStatsData.length === 0 ? (
            <div className="h-48 flex items-center justify-center text-stone-400 text-sm">
              No jobs posted yet
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={jobStatsData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#DEE0D6" />
                <XAxis dataKey="name" tick={{ fill: "#8A8D7C", fontSize: 10 }} />
                <YAxis tick={{ fill: "#8A8D7C", fontSize: 11 }} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="candidates"  fill="#2A4B7C" radius={[4,4,0,0]} name="Candidates" />
                <Bar dataKey="shortlisted" fill="#1F6E58" radius={[4,4,0,0]} name="Shortlisted" />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Interview stats */}
      <div className="card">
        <h3 className="font-semibold text-ink-500 mb-4 flex items-center gap-2">
          <Zap size={16} className="text-ledger-500" />
          AI Pipeline Performance
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: "Interviews Completed", value: data.interviewed,     color: "text-ledger-600"   },
            { label: "Advanced to L2",       value: data.funnel.advance,  color: "text-verified-600"  },
            { label: "Rejected",             value: data.funnel.rejected, color: "text-brick-600"     },
            { label: "Avg Score",            value: `${data.avg_score}%`, color: "text-gold-600"      }
          ].map((item, i) => (
            <div key={i} className="bg-stone-50 rounded-xl p-4 text-center border border-stone-200">
              <p className={`text-2xl font-bold font-mono ${item.color}`}>{item.value}</p>
              <p className="text-stone-500 text-xs mt-1">{item.label}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}