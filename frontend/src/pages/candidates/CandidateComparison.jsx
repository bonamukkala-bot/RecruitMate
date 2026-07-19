import { useState, useEffect } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Trophy, CheckCircle2, XCircle, Sparkles } from "lucide-react";
import { candidatesAPI } from "../../api/candidates";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import Badge from "../../components/ui/Badge";
import toast from "react-hot-toast";

export default function CandidateComparison() {
  const [searchParams] = useSearchParams();
  const navigate        = useNavigate();
  const [loading, setLoading] = useState(true);
  const [result,  setResult]  = useState(null);
  const [error,   setError]   = useState("");

  const ids = (searchParams.get("ids") || "").split(",").filter(Boolean);

  useEffect(() => {
    if (ids.length < 2) {
      setError("Select at least 2 candidates from the Candidates page to compare.");
      setLoading(false);
      return;
    }
    fetchComparison();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchComparison = async () => {
    try {
      const res = await candidatesAPI.compare(ids);
      setResult(res.data);
    } catch (err) {
      const msg = err.response?.data?.error || "Failed to compare candidates";
      setError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="h-64 flex items-center justify-center">
        <LoadingSpinner size="lg" text="Comparing candidates..." />
      </div>
    );
  }

  if (error || !result) {
    return (
      <div className="space-y-6">
        <button
          onClick={() => navigate("/candidates")}
          className="flex items-center gap-1.5 text-sm text-dark-400 hover:text-white"
        >
          <ArrowLeft size={14} />
          Back to Candidates
        </button>
        <div className="text-center py-20">
          <p className="text-dark-400 font-medium">{error}</p>
        </div>
      </div>
    );
  }

  const { candidates, comparison, job_title } = result;
  const recommendedId = comparison.recommended_candidate_id;
  const sharedSkills   = comparison.skill_overlap?.shared_by_all || [];
  const uniqueSkills   = comparison.skill_overlap?.unique || {};

  const verdictFor = (candidateId) => {
    const v = comparison.other_candidates?.find((o) => o.candidate_id === candidateId);
    return v?.verdict;
  };

  return (
    <div className="space-y-6">
      <button
        onClick={() => navigate("/candidates")}
        className="flex items-center gap-1.5 text-sm text-dark-400 hover:text-white"
      >
        <ArrowLeft size={14} />
        Back to Candidates
      </button>

      <div>
        <h1 className="text-2xl font-bold text-white">Candidate Comparison</h1>
        <p className="text-dark-400 text-sm mt-1">{job_title || "Comparing candidates"}</p>
      </div>

      {/* AI Recommendation banner */}
      <div className="card bg-gradient-to-br from-primary-600/10 to-transparent border-primary-600/30 p-5">
        <div className="flex items-start gap-3">
          <div className="w-9 h-9 rounded-lg bg-primary-600/20 flex items-center justify-center shrink-0">
            <Sparkles size={16} className="text-primary-400" />
          </div>
          <div>
            <p className="text-xs uppercase tracking-wider text-primary-400 font-medium mb-1">
              AI Recommendation
            </p>
            <p className="text-white font-semibold mb-1">
              {candidates.find((c) => c._id === recommendedId)?.candidate_name || "—"}
            </p>
            <p className="text-dark-300 text-sm leading-relaxed">
              {comparison.recommendation_reasoning}
            </p>
          </div>
        </div>
      </div>

      {/* Side-by-side cards */}
      <div className={`grid grid-cols-1 ${
        candidates.length === 2 ? "md:grid-cols-2" : "md:grid-cols-3"
      } gap-4`}>
        {candidates.map((c) => {
          const isRecommended = c._id === recommendedId;
          return (
            <div
              key={c._id}
              className={`card p-5 relative ${
                isRecommended ? "border-primary-600 ring-1 ring-primary-600/40" : ""
              }`}
            >
              {isRecommended && (
                <div className="absolute -top-3 left-5 flex items-center gap-1 bg-primary-600 text-white text-xs font-medium px-2.5 py-1 rounded-full">
                  <Trophy size={11} />
                  Top Pick
                </div>
              )}

              <div className="flex items-center gap-3 mb-4 mt-1">
                <div className="w-10 h-10 rounded-full bg-primary-600/20 flex items-center justify-center text-primary-400 font-bold text-sm shrink-0">
                  {c.candidate_name?.charAt(0).toUpperCase()}
                </div>
                <div className="min-w-0">
                  <p className="font-medium text-white truncate">{c.candidate_name}</p>
                  <p className="text-xs text-dark-400 truncate">{c.candidate_email}</p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 mb-4">
                <div className="bg-dark-800/60 rounded-lg p-3">
                  <p className="text-xs text-dark-400 mb-1">Match Score</p>
                  <p className={`text-lg font-bold ${
                    c.match_score >= 70 ? "text-green-400" : c.match_score >= 50 ? "text-yellow-400" : "text-red-400"
                  }`}>
                    {c.match_score}%
                  </p>
                </div>
                <div className="bg-dark-800/60 rounded-lg p-3">
                  <p className="text-xs text-dark-400 mb-1">Interview Score</p>
                  <p className="text-lg font-bold text-white">
                    {c.interview_score != null ? `${c.interview_score}%` : "—"}
                  </p>
                </div>
              </div>

              <div className="mb-3">
                <p className="text-xs text-dark-400 mb-2">Status</p>
                <Badge status={c.status}>{c.status}</Badge>
              </div>

              <div className="mb-3">
                <p className="text-xs text-dark-400 mb-2">Matched Skills</p>
                <div className="flex flex-wrap gap-1.5">
                  {c.matched_skills?.length ? c.matched_skills.map((s) => (
                    <span key={s} className="text-xs px-2 py-0.5 rounded-md bg-green-500/10 text-green-400 border border-green-500/20">
                      {s}
                    </span>
                  )) : <span className="text-xs text-dark-500">None</span>}
                </div>
              </div>

              <div className="mb-4">
                <p className="text-xs text-dark-400 mb-2">Missing Skills</p>
                <div className="flex flex-wrap gap-1.5">
                  {c.missing_skills?.length ? c.missing_skills.map((s) => (
                    <span key={s} className="text-xs px-2 py-0.5 rounded-md bg-red-500/10 text-red-400 border border-red-500/20">
                      {s}
                    </span>
                  )) : <span className="text-xs text-dark-500">None</span>}
                </div>
              </div>

              {!isRecommended && verdictFor(c._id) && (
                <div className="flex items-start gap-2 pt-3 border-t border-dark-800">
                  <XCircle size={13} className="text-dark-500 mt-0.5 shrink-0" />
                  <p className="text-xs text-dark-400 leading-relaxed">{verdictFor(c._id)}</p>
                </div>
              )}
              {isRecommended && (
                <div className="flex items-start gap-2 pt-3 border-t border-dark-800">
                  <CheckCircle2 size={13} className="text-primary-400 mt-0.5 shrink-0" />
                  <p className="text-xs text-primary-300 leading-relaxed">Recommended candidate for this role</p>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Skill overlap visualization */}
      <div className="card p-5">
        <h3 className="text-sm font-semibold text-white mb-4">Skill Overlap</h3>

        <div className="mb-4">
          <p className="text-xs text-dark-400 mb-2">Shared by all candidates</p>
          <div className="flex flex-wrap gap-1.5">
            {sharedSkills.length ? sharedSkills.map((s) => (
              <span key={s} className="text-xs px-2.5 py-1 rounded-md bg-primary-600/15 text-primary-300 border border-primary-600/30">
                {s}
              </span>
            )) : <span className="text-xs text-dark-500">No skills shared by every candidate</span>}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {candidates.map((c) => (
            <div key={c._id}>
              <p className="text-xs text-dark-400 mb-2">Unique to {c.candidate_name?.split(" ")[0]}</p>
              <div className="flex flex-wrap gap-1.5">
                {(uniqueSkills[c._id] || []).length ? uniqueSkills[c._id].map((s) => (
                  <span key={s} className="text-xs px-2 py-0.5 rounded-md bg-dark-800 text-dark-300 border border-dark-700">
                    {s}
                  </span>
                )) : <span className="text-xs text-dark-600">None</span>}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}