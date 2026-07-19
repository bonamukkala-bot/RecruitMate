import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Users, Search, CheckCircle, XCircle, Filter, SlidersHorizontal, Download, X, GitCompare
} from "lucide-react";
import { candidatesAPI } from "../../api/candidates";
import Badge from "../../components/ui/Badge";
import Input from "../../components/ui/Input";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import toast from "react-hot-toast";

const STATUS_FILTERS = ["all", "screened", "shortlisted", "invited", "hired", "rejected"];
const MAX_COMPARE = 3;

export default function Candidates() {
  const [candidates, setCandidates] = useState([]);
  const [filtered,   setFiltered]   = useState([]);
  const [loading,    setLoading]    = useState(true);
  const [search,     setSearch]     = useState("");
  const [status,     setStatus]     = useState("all");
  const [selected,   setSelected]   = useState([]);
  const navigate                    = useNavigate();

  // ── Advanced filters (skill / score range / date range) ────────────────────
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [skill,        setSkill]        = useState("");
  const [minScore,     setMinScore]     = useState("");
  const [maxScore,     setMaxScore]     = useState("");
  const [dateFrom,     setDateFrom]     = useState("");
  const [dateTo,       setDateTo]       = useState("");
  const [exporting,    setExporting]    = useState(false);

  const advancedActive = Boolean(skill || minScore || maxScore || dateFrom || dateTo);

  useEffect(() => {
    fetchCandidates();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Re-fetch from backend whenever advanced filters change (debounced)
  useEffect(() => {
    const timer = setTimeout(() => {
      fetchCandidates();
    }, 400);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [skill, minScore, maxScore, dateFrom, dateTo]);

  // Local text search + status tab filtering on top of whatever set is loaded
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

  const buildParams = () => {
    const params = {};
    if (skill)     params.skill      = skill;
    if (minScore)  params.min_score  = minScore;
    if (maxScore)  params.max_score  = maxScore;
    if (dateFrom)  params.date_from  = dateFrom;
    if (dateTo)    params.date_to    = dateTo;
    return params;
  };

  const fetchCandidates = async () => {
    try {
      setLoading((prev) => (candidates.length === 0 ? true : prev));
      const res = advancedActive
        ? await candidatesAPI.search(buildParams())
        : await candidatesAPI.getAll();
      setCandidates(res.data.candidates || []);
    } catch (err) {
      toast.error("Failed to load candidates");
    } finally {
      setLoading(false);
    }
  };

  const clearAdvanced = () => {
    setSkill("");
    setMinScore("");
    setMaxScore("");
    setDateFrom("");
    setDateTo("");
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      const res = await candidatesAPI.exportCSV(advancedActive ? buildParams() : {});
      const url  = window.URL.createObjectURL(new Blob([res.data], { type: "text/csv" }));
      const link = document.createElement("a");
      link.href  = url;
      link.setAttribute("download", "candidates_export.csv");
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      toast.success("Export downloaded");
    } catch (err) {
      toast.error("Export failed");
    } finally {
      setExporting(false);
    }
  };

  const toggleSelect = (candidateId) => {
    setSelected((prev) => {
      if (prev.includes(candidateId)) {
        return prev.filter((id) => id !== candidateId);
      }
      if (prev.length >= MAX_COMPARE) {
        toast.error(`You can compare up to ${MAX_COMPARE} candidates at a time`);
        return prev;
      }
      return [...prev, candidateId];
    });
  };

  const handleCompare = () => {
    if (selected.length < 2) {
      toast.error("Select at least 2 candidates to compare");
      return;
    }
    const selectedCandidates = candidates.filter((c) => selected.includes(c._id));
    const jobIds = new Set(selectedCandidates.map((c) => c.job_id));
    if (jobIds.size > 1) {
      toast.error("You can only compare candidates applying to the same job");
      return;
    }
    navigate(`/candidates/compare?ids=${selected.join(",")}`);
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
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white">Candidates</h1>
          <p className="text-dark-400 text-sm mt-1">
            {candidates.length} candidate{candidates.length !== 1 ? "s" : ""}
            {advancedActive ? " matching filters" : " across all jobs"}
          </p>
        </div>
        <button
          onClick={handleExport}
          disabled={exporting}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-dark-800 text-dark-200 border border-dark-700 hover:text-white hover:border-dark-600 transition-all disabled:opacity-50"
        >
          <Download size={14} />
          {exporting ? "Exporting..." : "Export CSV"}
        </button>
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
        <button
          onClick={() => setShowAdvanced((v) => !v)}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap border transition-all ${
            showAdvanced || advancedActive
              ? "bg-primary-600/20 text-primary-400 border-primary-600/40"
              : "bg-dark-800 text-dark-400 border-dark-700 hover:text-white"
          }`}
        >
          <SlidersHorizontal size={14} />
          Advanced
          {advancedActive && (
            <span className="w-1.5 h-1.5 rounded-full bg-primary-400" />
          )}
        </button>
      </div>

      {/* Advanced filter panel */}
      {showAdvanced && (
        <div className="card p-4 flex flex-col gap-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
            <div>
              <label className="text-xs text-dark-400 mb-1 block">Skill</label>
              <Input
                placeholder="e.g. Python"
                value={skill}
                onChange={(e) => setSkill(e.target.value)}
              />
            </div>
            <div>
              <label className="text-xs text-dark-400 mb-1 block">Min score</label>
              <Input
                type="number"
                min="0"
                max="100"
                placeholder="0"
                value={minScore}
                onChange={(e) => setMinScore(e.target.value)}
              />
            </div>
            <div>
              <label className="text-xs text-dark-400 mb-1 block">Max score</label>
              <Input
                type="number"
                min="0"
                max="100"
                placeholder="100"
                value={maxScore}
                onChange={(e) => setMaxScore(e.target.value)}
              />
            </div>
            <div>
              <label className="text-xs text-dark-400 mb-1 block">Date from</label>
              <Input
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
              />
            </div>
            <div>
              <label className="text-xs text-dark-400 mb-1 block">Date to</label>
              <Input
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
              />
            </div>
          </div>
          {advancedActive && (
            <button
              onClick={clearAdvanced}
              className="flex items-center gap-1.5 text-xs text-dark-400 hover:text-white w-fit"
            >
              <X size={13} />
              Clear advanced filters
            </button>
          )}
        </div>
      )}

      {/* Table */}
      {filtered.length === 0 ? (
        <div className="text-center py-20">
          <Users size={48} className="text-dark-700 mx-auto mb-4" />
          <p className="text-dark-400 font-medium">No candidates found</p>
          <p className="text-dark-600 text-sm mt-1">
            {search || status !== "all" || advancedActive
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
                <th className="text-left font-medium px-4 py-4 w-10"></th>
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
                  <td className="px-4 py-4" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={selected.includes(c._id)}
                      onChange={() => toggleSelect(c._id)}
                      className="w-4 h-4 rounded border-dark-600 bg-dark-800 text-primary-600 focus:ring-primary-600 cursor-pointer"
                    />
                  </td>
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

      {/* Floating compare bar */}
      {selected.length >= 2 && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 bg-dark-800 border border-dark-700 rounded-xl shadow-2xl px-5 py-3 flex items-center gap-4">
          <span className="text-sm text-dark-200">
            {selected.length} candidate{selected.length !== 1 ? "s" : ""} selected
          </span>
          <button
            onClick={handleCompare}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-primary-600 text-white hover:bg-primary-700 transition-all"
          >
            <GitCompare size={14} />
            Compare
          </button>
          <button
            onClick={() => setSelected([])}
            className="text-dark-400 hover:text-white text-sm"
          >
            Clear
          </button>
        </div>
      )}
    </div>
  );
}