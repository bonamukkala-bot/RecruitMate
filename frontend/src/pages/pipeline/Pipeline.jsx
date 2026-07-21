import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  GitBranch, Users, CheckCircle, Clock,
  ArrowRight, Zap, Mail, Brain,
  Calendar, ChevronRight, AlertCircle
} from "lucide-react";
import { candidatesAPI } from "../../api/candidates";
import { pipelineAPI } from "../../api/pipeline";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Modal from "../../components/ui/Modal";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import toast from "react-hot-toast";

// ── Pipeline Stage Config ─────────────────────────────────────────────────────
const STAGES = [
  { key: "screened",    label: "Screened",    icon: Users,        color: "text-ledger-600",   bg: "bg-ledger-50"   },
  { key: "shortlisted", label: "Shortlisted", icon: CheckCircle,  color: "text-verified-600",  bg: "bg-verified-50" },
  { key: "invited",     label: "Invited",     icon: Mail,         color: "text-gold-600",      bg: "bg-gold-50"     },
  { key: "hired",       label: "Hired",       icon: Zap,          color: "text-ink-500",       bg: "bg-ink-50"      },
  { key: "rejected",    label: "Rejected",    icon: AlertCircle,  color: "text-brick-600",     bg: "bg-brick-50"    }
];

// ── Evaluate Modal ────────────────────────────────────────────────────────────
function EvaluateModal({ isOpen, onClose, candidate, onDone }) {
  const [pairs,   setPairs]   = useState([{ question: "", answer: "" }]);
  const [loading, setLoading] = useState(false);

  const addPair    = () => setPairs([...pairs, { question: "", answer: "" }]);
  const updatePair = (i, field, val) => {
    const updated     = [...pairs];
    updated[i][field] = val;
    setPairs(updated);
  };

  const handleSubmit = async () => {
    const valid = pairs.filter(p => p.question.trim() && p.answer.trim());
    if (valid.length === 0) {
      toast.error("Add at least one Q&A pair");
      return;
    }
    setLoading(true);
    try {
      const res = await pipelineAPI.evaluate(candidate._id, {
        answer_type: "speech",
        answers    : { qa_pairs: valid }
      });
      if (res.data.success) {
        toast.success(`Score: ${res.data.data.overall_score}/100`);
        onDone();
        onClose();
      }
    } catch (err) {
      toast.error(err.response?.data?.error || "Evaluation failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`Evaluate — ${candidate?.candidate_name}`}
      size="xl"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={loading} onClick={handleSubmit}>
            <Brain size={16} /> Evaluate
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <p className="text-sm text-stone-500">Add interview Q&A pairs to evaluate.</p>
        {pairs.map((pair, i) => (
          <div key={i} className="p-4 bg-stone-50 rounded-xl border border-stone-200 space-y-3">
            <p className="text-xs font-medium text-stone-500">Pair {i + 1}</p>
            <textarea
              value={pair.question}
              onChange={(e) => updatePair(i, "question", e.target.value)}
              placeholder="Interview question..."
              rows={2}
              className="input resize-none text-sm"
            />
            <textarea
              value={pair.answer}
              onChange={(e) => updatePair(i, "answer", e.target.value)}
              placeholder="Candidate's answer..."
              rows={3}
              className="input resize-none text-sm"
            />
          </div>
        ))}
        <Button variant="secondary" onClick={addPair} className="w-full justify-center">
          + Add Q&A Pair
        </Button>
      </div>
    </Modal>
  );
}


// ── Candidate Pipeline Card ───────────────────────────────────────────────────
function PipelineCard({ candidate, onAction, navigate }) {
  const [scheduling, setScheduling] = useState(false);
  const [emailing,   setEmailing]   = useState(false);

  const handleSchedule = async (e) => {
    e.stopPropagation();
    setScheduling(true);
    try {
      const res = await pipelineAPI.schedule(candidate._id, { role_level: "junior" });
      if (res.data.success) {
        toast.success(`Scheduled: ${res.data.data.next_step}`);
        onAction();
      }
    } catch {
      toast.error("Scheduling failed");
    } finally {
      setScheduling(false);
    }
  };

  const handleEmail = async (e) => {
    e.stopPropagation();
    if (candidate.email_sent) {
      toast("Email already sent to this candidate");
      return;
    }
    setEmailing(true);
    try {
      const res = await pipelineAPI.sendEmail(candidate._id, {});
      if (res.data.success) {
        toast.success("Shortlist email sent!");
        onAction();
      }
    } catch {
      toast.error("Email failed");
    } finally {
      setEmailing(false);
    }
  };

  const scoreColor = candidate.match_score >= 70
    ? "text-verified-600"
    : candidate.match_score >= 50
    ? "text-gold-600"
    : "text-brick-600";

  return (
    <div
      onClick={() => navigate(`/candidates/${candidate._id}`)}
      className="p-4 rounded-xl bg-white border border-stone-200 hover:border-stone-300 cursor-pointer transition-all group"
    >
      {/* Needs Interview Time flag */}
      {candidate.schedule_pending && (
        <div className="flex items-center gap-1.5 mb-3 px-2 py-1 bg-gold-50 border border-gold-200 rounded-lg w-fit">
          <Calendar size={11} className="text-gold-600" />
          <span className="text-xs font-medium text-gold-700">Needs Interview Time</span>
        </div>
      )}

      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-full bg-ledger-50 flex items-center justify-center text-ledger-600 font-bold text-sm shrink-0">
            {candidate.candidate_name?.charAt(0).toUpperCase()}
          </div>
          <div>
            <p className="font-medium text-ink-500 text-sm">{candidate.candidate_name}</p>
            <p className="text-xs text-stone-500 truncate max-w-[150px]">{candidate.job_title || "—"}</p>
          </div>
        </div>
        <span className={`text-lg font-bold font-mono ${scoreColor}`}>
          {candidate.match_score}%
        </span>
      </div>

      {/* Skills */}
      <div className="flex flex-wrap gap-1 mb-3">
        {candidate.matched_skills?.slice(0, 3).map(s => (
          <span key={s} className="px-1.5 py-0.5 bg-verified-50 text-verified-700 text-xs rounded border border-verified-200">
            {s}
          </span>
        ))}
        {candidate.missing_skills?.slice(0, 2).map(s => (
          <span key={s} className="px-1.5 py-0.5 bg-brick-50 text-brick-700 text-xs rounded border border-brick-200">
            -{s}
          </span>
        ))}
      </div>

      {/* Evaluation score if exists */}
      {candidate.evaluation && (
        <div className="flex items-center gap-2 mb-3 p-2 bg-stone-50 rounded-lg">
          <Zap size={12} className="text-gold-600" />
          <span className="text-xs text-stone-600">
            Interview Score: <span className="text-gold-600 font-bold font-mono">{candidate.evaluation.overall_score}/100</span>
          </span>
          <span className="text-xs text-stone-400">— {candidate.evaluation.hiring_recommendation}</span>
        </div>
      )}

      {/* Schedule info if exists */}
      {candidate.schedule && (
        <div className="flex items-center gap-2 mb-3 p-2 bg-ledger-50 rounded-lg border border-ledger-100">
          <Calendar size={12} className="text-ledger-600" />
          <span className="text-xs text-ledger-600 font-medium">{candidate.schedule.next_step}</span>
          <span className="text-xs text-stone-400">· {candidate.schedule.scheduled_time}</span>
        </div>
      )}

      {/* Actions */}
      <div
        className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity"
        onClick={(e) => e.stopPropagation()}
      >
        {!candidate.email_sent && (
          <Button
            variant="secondary"
            size="sm"
            loading={emailing}
            onClick={handleEmail}
            className="text-xs"
          >
            <Mail size={12} /> Email
          </Button>
        )}
        {candidate.email_sent && !candidate.evaluation && (
          <Button
            variant="secondary"
            size="sm"
            onClick={(e) => { e.stopPropagation(); onAction("evaluate", candidate); }}
            className="text-xs"
          >
            <Brain size={12} /> Evaluate
          </Button>
        )}
        {candidate.evaluation && !candidate.schedule && (
          <Button
            size="sm"
            loading={scheduling}
            onClick={handleSchedule}
            className="text-xs"
          >
            <Calendar size={12} /> Schedule
          </Button>
        )}
        <ChevronRight size={14} className="text-stone-400 ml-auto" />
      </div>
    </div>
  );
}

// ── Main Pipeline Page ────────────────────────────────────────────────────────
export default function Pipeline() {
  const [candidates,   setCandidates]   = useState([]);
  const [loading,      setLoading]      = useState(true);
  const [evalCandidate, setEvalCandidate] = useState(null);
  const navigate                         = useNavigate();

  useEffect(() => {
    fetchCandidates();
  }, []);

  const fetchCandidates = async () => {
    try {
      const res = await candidatesAPI.getAll();
      setCandidates(res.data.candidates || []);
    } catch {
      toast.error("Failed to load pipeline");
    } finally {
      setLoading(false);
    }
  };

  const handleAction = (action, candidate) => {
    if (action === "evaluate" && candidate) {
      setEvalCandidate(candidate);
    } else {
      fetchCandidates();
    }
  };

  const getCandidatesByStage = (stage) =>
    candidates.filter(c => c.status === stage);

  if (loading) {
    return (
      <div className="h-64 flex items-center justify-center">
        <LoadingSpinner size="lg" text="Loading pipeline..." />
      </div>
    );
  }

  return (
    <div className="space-y-6">

      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-ink-500 font-display">Pipeline</h1>
        <p className="text-stone-500 text-sm mt-1">
          {candidates.length} candidate{candidates.length !== 1 ? "s" : ""} across all stages
        </p>
      </div>

      {/* Flow indicator */}
      <div className="flex items-center gap-2 overflow-x-auto pb-2">
        {STAGES.map((stage, i) => (
          <div key={stage.key} className="flex items-center gap-2 shrink-0">
            <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg ${stage.bg}`}>
              <stage.icon size={14} className={stage.color} />
              <span className={`text-xs font-medium ${stage.color}`}>{stage.label}</span>
              <span className="text-xs text-stone-400 font-mono">
                ({getCandidatesByStage(stage.key).length})
              </span>
            </div>
            {i < STAGES.length - 1 && (
              <ArrowRight size={14} className="text-stone-300 shrink-0" />
            )}
          </div>
        ))}
      </div>

      {/* Kanban columns */}
      <div className="grid grid-cols-1 md:grid-cols-3 xl:grid-cols-5 gap-4">
        {STAGES.map((stage) => {
          const stageCandidates = getCandidatesByStage(stage.key);
          return (
            <div key={stage.key} className="space-y-3">
              {/* Column header */}
              <div className={`flex items-center justify-between p-3 rounded-lg ${stage.bg} border border-stone-100`}>
                <div className="flex items-center gap-2">
                  <stage.icon size={14} className={stage.color} />
                  <span className={`text-sm font-semibold ${stage.color}`}>
                    {stage.label}
                  </span>
                </div>
                <span className="text-xs text-stone-500 bg-white/60 px-2 py-0.5 rounded-full font-mono">
                  {stageCandidates.length}
                </span>
              </div>

              {/* Cards */}
              <div className="space-y-3 min-h-[100px]">
                {stageCandidates.length === 0 ? (
                  <div className="p-4 rounded-xl border border-dashed border-stone-200 text-center">
                    <p className="text-stone-400 text-xs">No candidates</p>
                  </div>
                ) : (
                  stageCandidates.map(c => (
                    <PipelineCard
                      key={c._id}
                      candidate={c}
                      onAction={handleAction}
                      navigate={navigate}
                    />
                  ))
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Evaluate Modal */}
      {evalCandidate && (
        <EvaluateModal
          isOpen={!!evalCandidate}
          onClose={() => setEvalCandidate(null)}
          candidate={evalCandidate}
          onDone={fetchCandidates}
        />
      )}
    </div>
  );
}