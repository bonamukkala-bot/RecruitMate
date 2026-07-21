import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  ArrowLeft, Star, CheckCircle, XCircle,
  Mail, Brain, Calendar, MessageSquare,
  ChevronDown, ChevronUp, Zap, Video, Copy,
  ShieldAlert, AlertTriangle, Ban
} from "lucide-react";
import { candidatesAPI } from "../../api/candidates";
import { pipelineAPI } from "../../api/pipeline";
import Button from "../../components/ui/Button";
import Badge from "../../components/ui/Badge";
import Modal from "../../components/ui/Modal";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import toast from "react-hot-toast";

// ── Score Ring ────────────────────────────────────────────────────────────────
function ScoreRing({ score }) {
  const color = score >= 70 ? "#1F6E58" : score >= 50 ? "#C68A1E" : "#A23B2E";
  const r     = 40;
  const circ  = 2 * Math.PI * r;
  const dash  = (score / 100) * circ;

  return (
    <div className="relative w-24 h-24 flex items-center justify-center">
      <svg className="absolute inset-0 -rotate-90" width="96" height="96">
        <circle cx="48" cy="48" r={r} fill="none" stroke="#DEE0D6" strokeWidth="8" />
        <circle
          cx="48" cy="48" r={r} fill="none"
          stroke={color} strokeWidth="8"
          strokeDasharray={`${dash} ${circ}`}
          strokeLinecap="round"
        />
      </svg>
      <div className="text-center">
        <p className="text-2xl font-bold text-ink-500 font-mono">{score}</p>
        <p className="text-xs text-stone-500">/ 100</p>
      </div>
    </div>
  );
}

// ── Integrity flag labels + icon colors, mirrors InterviewPortal.jsx's VIOLATION_LABELS ─
const INTEGRITY_LABELS = {
  tab_switch       : "Switched away from the tab",
  window_blur      : "Switched away from the window",
  fullscreen_exit  : "Exited full-screen mode",
  phone_detected   : "Phone detected on camera",
  no_face          : "No face detected on camera",
  multiple_faces   : "Multiple faces detected on camera",
  identity_mismatch: "Identity mismatch — face didn't match verified reference"
};

function formatElapsed(seconds) {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

// ── Integrity Panel ───────────────────────────────────────────────────────────
function IntegrityPanel({ candidate }) {
  const log        = candidate.integrity_log || [];
  const terminated = candidate.terminated;

  if (!terminated && log.length === 0) {
    return (
      <div className="card border-verified-200 bg-verified-50 flex items-center gap-3">
        <CheckCircle size={20} className="text-verified-600 shrink-0" />
        <div>
          <p className="text-sm font-semibold text-ink-500">Clean interview</p>
          <p className="text-xs text-stone-500">No integrity flags were raised during this interview.</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`card space-y-4 ${terminated ? "border-brick-200 bg-brick-50" : "border-gold-200 bg-gold-50"}`}>
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-ink-500 flex items-center gap-2">
          {terminated
            ? <Ban size={16} className="text-brick-600" />
            : <ShieldAlert size={16} className="text-gold-600" />
          }
          Interview Integrity
        </h3>
        <span className={terminated ? "stamp text-brick-600" : "stamp text-gold-700"}
              style={{ background: terminated ? "rgba(162,59,46,0.07)" : "rgba(198,138,30,0.08)" }}>
          {terminated ? "Terminated" : `${log.length} flag${log.length === 1 ? "" : "s"}`}
        </span>
      </div>

      {terminated && (
        <div className="p-3 bg-white rounded-lg border border-brick-200">
          <p className="text-xs text-stone-500 mb-1">Termination reason</p>
          <p className="text-sm text-brick-700">{candidate.termination_reason}</p>
        </div>
      )}

      {log.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-semibold text-stone-500 uppercase tracking-wider">Timeline</p>
          {log.map((flag, i) => (
            <div key={i} className="flex items-center gap-3 p-2.5 bg-white rounded-lg border border-stone-200">
              <AlertTriangle size={14} className="text-gold-600 shrink-0" />
              <p className="text-sm text-ink-400 flex-1">
                {INTEGRITY_LABELS[flag.type] || flag.type}
              </p>
              <span className="text-xs text-stone-500 font-mono shrink-0">
                {formatElapsed(flag.at_seconds)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Evaluate Modal ────────────────────────────────────────────────────────────
function EvaluateModal({ isOpen, onClose, candidateId, onEvaluated }) {
  const [pairs,   setPairs]   = useState([{ question: "", answer: "" }]);
  const [loading, setLoading] = useState(false);

  const addPair = () => setPairs([...pairs, { question: "", answer: "" }]);

  const updatePair = (i, field, val) => {
    const updated    = [...pairs];
    updated[i][field] = val;
    setPairs(updated);
  };

  const handleSubmit = async () => {
    const valid = pairs.filter(p => p.question && p.answer);
    if (valid.length === 0) {
      toast.error("Add at least one Q&A pair");
      return;
    }
    setLoading(true);
    try {
      const res = await pipelineAPI.evaluate(candidateId, {
        answer_type: "speech",
        answers    : { qa_pairs: valid }
      });
      if (res.data.success) {
        toast.success(`Evaluation complete! Score: ${res.data.data.overall_score}/100`);
        onEvaluated(res.data.data);
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
      title="Evaluate Interview Answers"
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
        <p className="text-sm text-stone-500">
          Add question and answer pairs from the interview.
        </p>
        {pairs.map((pair, i) => (
          <div key={i} className="p-4 bg-stone-50 rounded-xl border border-stone-200 space-y-3">
            <p className="text-xs font-medium text-stone-500">Q&A Pair {i + 1}</p>
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
          + Add Another Q&A
        </Button>
      </div>
    </Modal>
  );
}

// ── Interview Link Modal ──────────────────────────────────────────────────────
function InterviewLinkModal({ isOpen, onClose, link, emailSent }) {
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(link);
      toast.success("Link copied to clipboard");
    } catch {
      toast.error("Couldn't copy — please copy manually");
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Interview Invitation"
      size="md"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Close</Button>
          <Button onClick={handleCopy}>
            <Copy size={16} /> Copy Link
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        {emailSent ? (
          <p className="text-sm text-verified-600">
            ✓ Interview invitation emailed to the candidate.
          </p>
        ) : (
          <p className="text-sm text-brick-600">
            ⚠ The link was created, but the email couldn't be sent. Please share this link with the candidate manually.
          </p>
        )}
        <p className="text-sm text-stone-500">
          You can also copy the link below as a backup.
        </p>
        <div className="p-3 bg-stone-50 rounded-lg border border-stone-200 break-all text-sm text-ledger-600">
          {link}
        </div>
      </div>
    </Modal>
  );
}

// ── Schedule Offline Interview Form ───────────────────────────────────────────
function ScheduleOfflineForm({ candidateId, onScheduled }) {
  const [date, setDate]       = useState("");
  const [time, setTime]       = useState("");
  const [loading, setLoading] = useState(false);

  const handleConfirm = async () => {
    if (!date || !time) {
      toast.error("Please pick both a date and a time");
      return;
    }
    setLoading(true);
    try {
      const res = await pipelineAPI.scheduleOffline(candidateId, {
        interview_date: date,
        interview_time: time
      });
      if (res.data.success) {
        if (res.data.email_sent) {
          toast.success("Candidate notified of offline interview");
        } else {
          toast.error("Scheduled, but email failed to send");
        }
        onScheduled();
      }
    } catch (err) {
      toast.error(err.response?.data?.error || "Failed to schedule");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-4 bg-gold-50 border border-gold-200 rounded-xl space-y-3">
      <p className="text-sm font-semibold text-gold-700">Schedule Offline Interview</p>
      <p className="text-xs text-stone-500">
        Set the date and time for the in-person interview at Charan Solutions Office, Hyderabad.
      </p>
      <div className="grid grid-cols-2 gap-2">
        <input
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          className="input text-sm"
        />
        <input
          type="time"
          value={time}
          onChange={(e) => setTime(e.target.value)}
          className="input text-sm"
        />
      </div>
      <Button
        className="w-full justify-center"
        loading={loading}
        onClick={handleConfirm}
      >
        <Calendar size={16} /> Confirm & Send Invitation
      </Button>
    </div>
  );
}

// ── Main CandidateDetail ──────────────────────────────────────────────────────
export default function CandidateDetail() {
  const { id }                        = useParams();
  const navigate                      = useNavigate();
  const [candidate, setCandidate]     = useState(null);
  const [loading,   setLoading]       = useState(true);
  const [showEval,  setShowEval]      = useState(false);
  const [showQs,    setShowQs]        = useState(false);
  const [scheduling, setScheduling]   = useState(false);
  const [creatingLink, setCreatingLink] = useState(false);
  const [interviewLink, setInterviewLink] = useState(null);
  const [emailSent, setEmailSent] = useState(false);

  useEffect(() => {
    fetchCandidate();
  }, [id]);

  const fetchCandidate = async () => {
    try {
      const res = await candidatesAPI.getOne(id);
      setCandidate(res.data.candidate);
    } catch {
      toast.error("Candidate not found");
      navigate(-1);
    } finally {
      setLoading(false);
    }
  };

  const handleStatusUpdate = async (status) => {
    try {
      await candidatesAPI.updateStatus(id, status);
      setCandidate(prev => ({ ...prev, status }));
      toast.success(`Status updated to ${status}`);
    } catch {
      toast.error("Failed to update status");
    }
  };

  const handleEvaluated = (evalData) => {
    setCandidate(prev => ({ ...prev, evaluation: evalData }));
  };

  const handleSchedule = async () => {
    setScheduling(true);
    try {
      const res = await pipelineAPI.schedule(id, { role_level: "junior" });
      if (res.data.success) {
        toast.success(`Scheduled: ${res.data.data.next_step}`);
        setCandidate(prev => ({ ...prev, schedule: res.data.data }));
      }
    } catch {
      toast.error("Scheduling failed");
    } finally {
      setScheduling(false);
    }
  };

  const handleStartInterview = async () => {
    setCreatingLink(true);
    try {
      const res = await pipelineAPI.createInterviewLink(id);
      if (res.data.success) {
        setInterviewLink(res.data.interview_url);
        setEmailSent(res.data.email_sent);
        if (res.data.email_sent) {
          toast.success("Interview invitation sent to candidate");
        } else {
          toast.error("Link created, but email failed to send");
        }
      }
    } catch (err) {
      toast.error(err.response?.data?.error || "Failed to create interview link");
    } finally {
      setCreatingLink(false);
    }
  };

  if (loading) {
    return (
      <div className="h-64 flex items-center justify-center">
        <LoadingSpinner size="lg" text="Loading candidate..." />
      </div>
    );
  }

  if (!candidate) return null;

  const eval_data = candidate.evaluation;
  const hasInterviewData = candidate.interview_status === "completed";

  return (
    <div className="space-y-6">

      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => navigate(-1)}
          className="p-2 text-stone-500 hover:text-ink-500 hover:bg-stone-100 rounded-lg transition-all"
        >
          <ArrowLeft size={20} />
        </button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-ink-500 font-display">{candidate.candidate_name}</h1>
          <p className="text-stone-500 text-sm mt-0.5">{candidate.candidate_email}</p>
        </div>
        <Badge status={candidate.status}>{candidate.status}</Badge>
      </div>

      {/* Top cards */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Score card */}
        <div className="card flex items-center gap-6">
          <ScoreRing score={candidate.match_score} />
          <div>
            <p className="text-stone-500 text-sm">Match Score</p>
            <p className="text-ink-500 font-semibold mt-1">{candidate.recommendation}</p>
            <p className="text-stone-500 text-xs mt-1 max-w-[160px] line-clamp-2">
              {candidate.reasoning}
            </p>
          </div>
        </div>

        {/* Skills */}
        <div className="card">
          <h3 className="font-semibold text-ink-500 mb-3 flex items-center gap-2">
            <CheckCircle size={16} className="text-verified-600" />
            Matched Skills
          </h3>
          <div className="flex flex-wrap gap-1.5">
            {candidate.matched_skills?.map(s => (
              <span key={s} className="px-2 py-0.5 bg-verified-50 text-verified-700 border border-verified-200 text-xs rounded-md">
                {s}
              </span>
            ))}
          </div>
          {candidate.missing_skills?.length > 0 && (
            <>
              <h3 className="font-semibold text-ink-500 mt-4 mb-3 flex items-center gap-2">
                <XCircle size={16} className="text-brick-600" />
                Missing Skills
              </h3>
              <div className="flex flex-wrap gap-1.5">
                {candidate.missing_skills?.map(s => (
                  <span key={s} className="px-2 py-0.5 bg-brick-50 text-brick-700 border border-brick-200 text-xs rounded-md">
                    {s}
                  </span>
                ))}
              </div>
            </>
          )}
        </div>

        {/* Actions */}
        <div className="card space-y-3">
          <h3 className="font-semibold text-ink-500 mb-1">Actions</h3>
          <Button
            className="w-full justify-center"
            onClick={() => setShowEval(true)}
          >
            <Brain size={16} /> Evaluate Answers
          </Button>
          <Button
            variant="secondary"
            className="w-full justify-center"
            loading={creatingLink}
            onClick={handleStartInterview}
          >
            <Video size={16} /> Start Interview
          </Button>
          <Button
            variant="secondary"
            className="w-full justify-center"
            loading={scheduling}
            onClick={handleSchedule}
          >
            <Calendar size={16} /> Schedule Next Round
          </Button>
          <div className="grid grid-cols-2 gap-2">
            <Button
              variant="secondary"
              className="justify-center text-xs"
              onClick={() => handleStatusUpdate("shortlisted")}
            >
              Shortlist
            </Button>
            <Button
              variant="danger"
              className="justify-center text-xs"
              onClick={() => handleStatusUpdate("rejected")}
            >
              Reject
            </Button>
          </div>
        </div>
      </div>

      {/* Integrity panel — only shown once the voice interview has actually run */}
      {hasInterviewData && <IntegrityPanel candidate={candidate} />}

      {/* Needs offline scheduling */}
      {candidate.schedule_pending && (
        <ScheduleOfflineForm candidateId={id} onScheduled={fetchCandidate} />
      )}

      {/* Interview Questions */}
      <div className="card">
        <button
          onClick={() => setShowQs(!showQs)}
          className="w-full flex items-center justify-between"
        >
          <h3 className="font-semibold text-ink-500 flex items-center gap-2">
            <MessageSquare size={16} className="text-ledger-500" />
            Interview Questions (8)
          </h3>
          {showQs ? <ChevronUp size={18} className="text-stone-500" /> : <ChevronDown size={18} className="text-stone-500" />}
        </button>

        {showQs && (
          <div className="mt-4 space-y-4 animate-slide-down">
            {["technical", "behavioral", "gap_focused"].map((cat) => (
              <div key={cat}>
                <p className="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-2">
                  {cat.replace("_", " ")}
                </p>
                <div className="space-y-2">
                  {candidate.interview_questions?.[cat]?.map((q) => (
                    <div key={q.id} className="p-3 bg-stone-50 rounded-lg border border-stone-200">
                      <p className="text-sm text-ink-400">
                        <span className="text-stone-500 mr-2 font-mono">Q{q.id}.</span>
                        {q.question}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Evaluation Results */}
      {eval_data && (
        <div className="card">
          <h3 className="font-semibold text-ink-500 mb-4 flex items-center gap-2">
            <Zap size={16} className="text-gold-600" />
            Evaluation Results
          </h3>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-stone-50 rounded-xl p-4 text-center">
              <p className="text-2xl font-bold text-ink-500 font-mono">{eval_data.overall_score}</p>
              <p className="text-xs text-stone-500 mt-1">Overall Score</p>
            </div>
            <div className="bg-stone-50 rounded-xl p-4 text-center col-span-3">
              <p className="text-sm font-medium text-ink-500">{eval_data.hiring_recommendation}</p>
              <p className="text-xs text-stone-500 mt-1">Hiring Recommendation</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <div>
              <p className="text-xs font-semibold text-verified-600 uppercase tracking-wider mb-2">Strengths</p>
              <ul className="space-y-1">
                {eval_data.strengths?.map((s, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-ink-400">
                    <CheckCircle size={13} className="text-verified-600 mt-0.5 shrink-0" />
                    {s}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <p className="text-xs font-semibold text-brick-600 uppercase tracking-wider mb-2">Weaknesses</p>
              <ul className="space-y-1">
                {eval_data.weaknesses?.map((w, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-ink-400">
                    <XCircle size={13} className="text-brick-600 mt-0.5 shrink-0" />
                    {w}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <div className="p-4 bg-stone-50 rounded-xl border border-stone-200">
            <p className="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-2">Summary</p>
            <p className="text-sm text-ink-400">{eval_data.summary}</p>
          </div>

          {/* Per question scores */}
          {eval_data.per_question && (
            <div className="mt-4 space-y-3">
              <p className="text-xs font-semibold text-stone-500 uppercase tracking-wider">Per Question</p>
              {eval_data.per_question.map((q, i) => (
                <div key={i} className="p-3 bg-stone-50 rounded-xl border border-stone-200">
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-sm font-medium text-ink-500 truncate flex-1 mr-4">{q.question}</p>
                    <span className={`text-sm font-bold font-mono shrink-0 ${
                      q.score >= 70 ? "text-verified-600" : q.score >= 50 ? "text-gold-600" : "text-brick-600"
                    }`}>
                      {q.score}/100
                    </span>
                  </div>
                  <p className="text-xs text-stone-500">{q.feedback}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Schedule Result */}
      {candidate.schedule && (
        <div className="card border-ledger-200 bg-ledger-50">
          <h3 className="font-semibold text-ink-500 mb-3 flex items-center gap-2">
            <Calendar size={16} className="text-ledger-600" />
            Scheduled
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-xs text-stone-500">Next Step</p>
              <p className="text-sm font-medium text-ink-500 mt-1">{candidate.schedule.next_step}</p>
            </div>
            <div>
              <p className="text-xs text-stone-500">Decision</p>
              <Badge status={candidate.schedule.decision} className="mt-1">
                {candidate.schedule.decision}
              </Badge>
            </div>
            <div>
              <p className="text-xs text-stone-500">Scheduled Time</p>
              <p className="text-sm font-medium text-ink-500 mt-1">{candidate.schedule.scheduled_time}</p>
            </div>
            <div>
              <p className="text-xs text-stone-500">Score Used</p>
              <p className="text-sm font-medium text-ink-500 mt-1 font-mono">{candidate.schedule.overall_score}/100</p>
            </div>
          </div>
        </div>
      )}

      {/* Offline interview confirmed */}
      {candidate.offline_interview && (
        <div className="card border-verified-200 bg-verified-50">
          <h3 className="font-semibold text-ink-500 mb-3 flex items-center gap-2">
            <Calendar size={16} className="text-verified-600" />
            Offline Interview Confirmed
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <p className="text-xs text-stone-500">Date</p>
              <p className="text-sm font-medium text-ink-500 mt-1">{candidate.offline_interview.date}</p>
            </div>
            <div>
              <p className="text-xs text-stone-500">Time</p>
              <p className="text-sm font-medium text-ink-500 mt-1">{candidate.offline_interview.time}</p>
            </div>
            <div>
              <p className="text-xs text-stone-500">Location</p>
              <p className="text-sm font-medium text-ink-500 mt-1">{candidate.offline_interview.location}</p>
            </div>
          </div>
        </div>
      )}

      {/* Evaluate Modal */}
      <EvaluateModal
        isOpen={showEval}
        onClose={() => setShowEval(false)}
        candidateId={id}
        onEvaluated={handleEvaluated}
      />

      {/* Interview Link Modal */}
      <InterviewLinkModal
        isOpen={!!interviewLink}
        onClose={() => setInterviewLink(null)}
        link={interviewLink}
        emailSent={emailSent}
      />
    </div>
  );
}