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

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchCandidates();
    }, 400);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [skill, minScore, maxScore, dateFrom, dateTo]);

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
          <h1 className="text-2xl font-bold text-ink-500 font-display">Candidates</h1>
          <p className="text-stone-500 text-sm mt-1">
            {candidates.length} candidate{candidates.length !== 1 ? "s" : ""}
            {advancedActive ? " matching filters" : " across all jobs"}
          </p>
        </div>
        <button
          onClick={handleExport}
          disabled={exporting}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-white text-ink-400 border border-stone-200 hover:text-ink-500 hover:border-stone-300 transition-all disabled:opacity-50"
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
          <Filter size={14} className="text-stone-400 shrink-0" />
          {STATUS_FILTERS.map((s) => (
            <button
              key={s}
              onClick={() => setStatus(s)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-all ${
                status === s
                  ? "bg-ledger-500 text-white"
                  : "bg-white text-stone-500 hover:text-ink-500 border border-stone-200"
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
              ? "bg-ledger-50 text-ledger-600 border-ledger-200"
              : "bg-white text-stone-500 border-stone-200 hover:text-ink-500"
          }`}
        >
          <SlidersHorizontal size={14} />
          Advanced
          {advancedActive && (
            <span className="w-1.5 h-1.5 rounded-full bg-ledger-500" />
          )}
        </button>
      </div>

      {/* Advanced filter panel */}
      {showAdvanced && (
        <div className="card p-4 flex flex-col gap-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
            <div>
              <label className="text-xs text-stone-500 mb-1 block">Skill</label>
              <Input
                placeholder="e.g. Python"
                value={skill}
                onChange={(e) => setSkill(e.target.value)}
              />
            </div>
            <div>
              <label className="text-xs text-stone-500 mb-1 block">Min score</label>
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
              <label className="text-xs text-stone-500 mb-1 block">Max score</label>
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
              <label className="text-xs text-stone-500 mb-1 block">Date from</label>
              <Input
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
              />
            </div>
            <div>
              <label className="text-xs text-stone-500 mb-1 block">Date to</label>
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
              className="flex items-center gap-1.5 text-xs text-stone-500 hover:text-ink-500 w-fit"
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
          <Users size={48} className="text-stone-300 mx-auto mb-4" />
          <p className="text-stone-500 font-medium">No candidates found</p>
          <p className="text-stone-400 text-sm mt-1">
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
              <tr className="border-b border-stone-200 text-stone-500 text-xs uppercase tracking-wider">
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
                  className="border-b border-stone-100 hover:bg-stone-50 cursor-pointer transition-all"
                >
                  <td className="px-4 py-4" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={selected.includes(c._id)}
                      onChange={() => toggleSelect(c._id)}
                      className="w-4 h-4 rounded border-stone-300 bg-white text-ledger-500 focus:ring-ledger-200 cursor-pointer"
                    />
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-full bg-ledger-50 flex items-center justify-center text-ledger-600 font-bold text-xs shrink-0">
                        {c.candidate_name?.charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <p className="font-medium text-ink-500">{c.candidate_name}</p>
                        <p className="text-xs text-stone-500">{c.candidate_email}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-stone-600 text-sm">
                    {c.job_title || "—"}
                  </td>
                  <td className="px-6 py-4 text-center">
                    <span className={`font-bold text-base font-mono ${
                      c.match_score >= 70
                        ? "text-verified-600"
                        : c.match_score >= 50
                        ? "text-gold-600"
                        : "text-brick-600"
                    }`}>
                      {c.match_score}%
                    </span>
                  </td>
                  <td className="px-6 py-4 text-center">
                    <div className="flex items-center justify-center gap-1.5">
                      {c.recommendation === "Shortlist" || c.recommendation === "Strongly Recommend"
                        ? <CheckCircle size={13} className="text-verified-600" />
                        : <XCircle    size={13} className="text-brick-600"   />
                      }
                      <span className="text-xs text-stone-600">{c.recommendation}</span>
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
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 bg-ink-500 border border-ink-600 rounded-xl shadow-card-lg px-5 py-3 flex items-center gap-4">
          <span className="text-sm text-ink-100">
            {selected.length} candidate{selected.length !== 1 ? "s" : ""} selected
          </span>
          <button
            onClick={handleCompare}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-gold-500 text-ink-700 hover:bg-gold-400 transition-all"
          >
            <GitCompare size={14} />
            Compare
          </button>
          <button
            onClick={() => setSelected([])}
            className="text-ink-200 hover:text-white text-sm"
          >
            Clear
          </button>
        </div>
      )}
    </div>
  );
}