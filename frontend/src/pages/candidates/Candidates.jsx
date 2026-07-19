import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Users, Search, CheckCircle, XCircle, Filter
} from "lucide-react";
import { candidatesAPI } from "../../api/candidates";
import Badge from "../../components/ui/Badge";
import Input from "../../components/ui/Input";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import toast from "react-hot-toast";

const STATUS_FILTERS = ["all", "screened", "shortlisted", "invited", "hired", "rejected"];

export default function Candidates() {
  const [candidates, setCandidates] = useState([]);
  const [filtered,   setFiltered]   = useState([]);
  const [loading,    setLoading]    = useState(true);
  const [search,     setSearch]     = useState("");
  const [status,     setStatus]     = useState("all");
  const navigate                    = useNavigate();

  useEffect(() => {
    fetchCandidates();
  }, []);

  useEffect(() => {
    let result = candidates;
    if (status !== "all") {
      result = result.filter(c => c.status === status);
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      result  = result.filter(c =>
        c.candidate_name?.toLowerCase().includes(q) ||
        c.candidate_email?.toLowerCase().includes(q) ||
        c.job_title?.toLowerCase().includes(q)
      );
    }
    setFiltered(result);
  }, [search, status, candidates]);

  const fetchCandidates = async () => {
    try {
      const res = await candidatesAPI.getAll();
      setCandidates(res.data.candidates || []);
      setFiltered(res.data.candidates  || []);
    } catch (err) {
      toast.error("Failed to load candidates");
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="h-64 flex items-center justify-center">
        <LoadingSpinner size="lg" text="Loading candidates..." />
      </div>
    );
  }

  return (
    <div className="space-y-6">

      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Candidates</h1>
        <p className="text-dark-400 text-sm mt-1">
          {candidates.length} candidate{candidates.length !== 1 ? "s" : ""} across all jobs
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="flex-1">
          <Input
            placeholder="Search by name, email or job..."
            icon={Search}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="flex items-center gap-2 overflow-x-auto pb-1">
          <Filter size={14} className="text-dark-500 shrink-0" />
          {STATUS_FILTERS.map((s) => (
            <button
              key={s}
              onClick={() => setStatus(s)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-all ${
                status === s
                  ? "bg-primary-600 text-white"
                  : "bg-dark-800 text-dark-400 hover:text-white border border-dark-700"
              }`}
            >
              {s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      {filtered.length === 0 ? (
        <div className="text-center py-20">
          <Users size={48} className="text-dark-700 mx-auto mb-4" />
          <p className="text-dark-400 font-medium">No candidates found</p>
          <p className="text-dark-600 text-sm mt-1">
            {search || status !== "all"
              ? "Try adjusting your filters"
              : "Screen your first candidate from a job posting"
            }
          </p>
        </div>
      ) : (
        <div className="card p-0 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-dark-800 text-dark-400 text-xs uppercase tracking-wider">
                <th className="text-left font-medium px-6 py-4">Candidate</th>
                <th className="text-left font-medium px-6 py-4">Job</th>
                <th className="text-center font-medium px-6 py-4">Match Score</th>
                <th className="text-center font-medium px-6 py-4">Recommendation</th>
                <th className="text-center font-medium px-6 py-4">Status</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((c) => (
                <tr
                  key={c._id}
                  onClick={() => navigate(`/candidates/${c._id}`)}
                  className="border-b border-dark-800/60 hover:bg-dark-800/40 cursor-pointer transition-all"
                >
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-full bg-primary-600/20 flex items-center justify-center text-primary-400 font-bold text-xs shrink-0">
                        {c.candidate_name?.charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <p className="font-medium text-white">{c.candidate_name}</p>
                        <p className="text-xs text-dark-400">{c.candidate_email}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-dark-300 text-sm">
                    {c.job_title || "—"}
                  </td>
                  <td className="px-6 py-4 text-center">
                    <span className={`font-bold text-base ${
                      c.match_score >= 70
                        ? "text-green-400"
                        : c.match_score >= 50
                        ? "text-yellow-400"
                        : "text-red-400"
                    }`}>
                      {c.match_score}%
                    </span>
                  </td>
                  <td className="px-6 py-4 text-center">
                    <div className="flex items-center justify-center gap-1.5">
                      {c.recommendation === "Shortlist" || c.recommendation === "Strongly Recommend"
                        ? <CheckCircle size={13} className="text-green-400" />
                        : <XCircle    size={13} className="text-red-400"   />
                      }
                      <span className="text-xs text-dark-300">{c.recommendation}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-center">
                    <Badge status={c.status}>{c.status}</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}