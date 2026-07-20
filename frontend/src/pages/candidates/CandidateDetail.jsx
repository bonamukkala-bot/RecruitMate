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
  const color = score >= 70 ? "#22c55e" : score >= 50 ? "#eab308" : "#ef4444";
  const r     = 40;
  const circ  = 2 * Math.PI * r;
  const dash  = (score / 100) * circ;

  return (
    <div className="relative w-24 h-24 flex items-center justify-center">
      <svg className="absolute inset-0 -rotate-90" width="96" height="96">
        <circle cx="48" cy="48" r={r} fill="none" stroke="#1e293b" strokeWidth="8" />
        <circle
          cx="48" cy="48" r={r} fill="none"
          stroke={color} strokeWidth="8"
          strokeDasharray={`${dash} ${circ}`}
          strokeLinecap="round"
        />
      </svg>
      <div className="text-center">
        <p className="text-2xl font-bold text-white">{score}</p>
        <p className="text-xs text-dark-400">/ 100</p>
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
      <div className="card border-green-600/20 bg-green-600/5 flex items-center gap-3">
        <CheckCircle size={20} className="text-green-400 shrink-0" />
        <div>
          <p className="text-sm font-semibold text-white">Clean interview</p>
          <p className="text-xs text-dark-400">No integrity flags were raised during this interview.</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`card space-y-4 ${terminated ? "border-red-600/30 bg-red-600/5" : "border-yellow-500/20 bg-yellow-500/5"}`}>
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-white flex items-center gap-2">
          {terminated
            ? <Ban size={16} className="text-red-400" />
            : <ShieldAlert size={16} className="text-yellow-400" />
          }
          Interview Integrity
        </h3>
        <span className={`text-xs px-2 py-0.5 rounded-md border ${
          terminated
            ? "bg-red-500/10 text-red-400 border-red-500/20"
            : "bg-yellow-500/10 text-yellow-400 border-yellow-500/20"
        }`}>
          {terminated ? "Terminated" : `${log.length} flag${log.length === 1 ? "" : "s"}`}
        </span>
      </div>

      {terminated && (
        <div className="p-3 bg-dark-800 rounded-lg border border-red-500/20">
          <p className="text-xs text-dark-400 mb-1">Termination reason</p>
          <p className="text-sm text-red-300">{candidate.termination_reason}</p>
        </div>
      )}

      {log.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-semibold text-dark-400 uppercase tracking-wider">Timeline</p>
          {log.map((flag, i) => (
            <div key={i} className="flex items-center gap-3 p-2.5 bg-dark-800 rounded-lg border border-dark-700">
              <AlertTriangle size={14} className="text-yellow-400 shrink-0" />
              <p className="text-sm text-dark-300 flex-1">
                {INTEGRITY_LABELS[flag.type] || flag.type}
              </p>
              <span className="text-xs text-dark-500 font-mono shrink-0">
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
        <p className="text-sm text-dark-400">
          Add question and answer pairs from the interview.
        </p>
        {pairs.map((pair, i) => (
          <div key={i} className="p-4 bg-dark-800 rounded-xl border border-dark-700 space-y-3">
            <p className="text-xs font-medium text-dark-400">Q&A Pair {i + 1}</p>
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
          <p className="text-sm text-green-400">
            ✓ Interview invitation emailed to the candidate.
          </p>
        ) : (
          <p className="text-sm text-red-400">
            ⚠ The link was created, but the email couldn't be sent. Please share this link with the candidate manually.
          </p>
        )}
        <p className="text-sm text-dark-400">
          You can also copy the link below as a backup.
        </p>
        <div className="p-3 bg-dark-800 rounded-lg border border-dark-700 break-all text-sm text-primary-400">
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
    <div className="p-4 bg-yellow-500/5 border border-yellow-500/20 rounded-xl space-y-3">
      <p className="text-sm font-semibold text-yellow-400">Schedule Offline Interview</p>
      <p className="text-xs text-dark-400">
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
          className="p-2 text-dark-400 hover:text-white hover:bg-dark-800 rounded-lg transition-all"
        >
          <ArrowLeft size={20} />
        </button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-white">{candidate.candidate_name}</h1>
          <p className="text-dark-400 text-sm mt-0.5">{candidate.candidate_email}</p>
        </div>
        <Badge status={candidate.status}>{candidate.status}</Badge>
      </div>

      {/* Top cards */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Score card */}
        <div className="card flex items-center gap-6">
          <ScoreRing score={candidate.match_score} />
          <div>
            <p className="text-dark-400 text-sm">Match Score</p>
            <p className="text-white font-semibold mt-1">{candidate.recommendation}</p>
            <p className="text-dark-500 text-xs mt-1 max-w-[160px] line-clamp-2">
              {candidate.reasoning}
            </p>
          </div>
        </div>

        {/* Skills */}
        <div className="card">
          <h3 className="font-semibold text-white mb-3 flex items-center gap-2">
            <CheckCircle size={16} className="text-green-400" />
            Matched Skills
          </h3>
          <div className="flex flex-wrap gap-1.5">
            {candidate.matched_skills?.map(s => (
              <span key={s} className="px-2 py-0.5 bg-green-500/10 text-green-400 border border-green-500/20 text-xs rounded-md">
                {s}
              </span>
            ))}
          </div>
          {candidate.missing_skills?.length > 0 && (
            <>
              <h3 className="font-semibold text-white mt-4 mb-3 flex items-center gap-2">
                <XCircle size={16} className="text-red-400" />
                Missing Skills
              </h3>
              <div className="flex flex-wrap gap-1.5">
                {candidate.missing_skills?.map(s => (
                  <span key={s} className="px-2 py-0.5 bg-red-500/10 text-red-400 border border-red-500/20 text-xs rounded-md">
                    {s}
                  </span>
                ))}
              </div>
            </>
          )}
        </div>

        {/* Actions */}
        <div className="card space-y-3">
          <h3 className="font-semibold text-white mb-1">Actions</h3>
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
          <h3 className="font-semibold text-white flex items-center gap-2">
            <MessageSquare size={16} className="text-primary-400" />
            Interview Questions (8)
          </h3>
          {showQs ? <ChevronUp size={18} className="text-dark-400" /> : <ChevronDown size={18} className="text-dark-400" />}
        </button>

        {showQs && (
          <div className="mt-4 space-y-4 animate-slide-down">
            {["technical", "behavioral", "gap_focused"].map((cat) => (
              <div key={cat}>
                <p className="text-xs font-semibold text-dark-400 uppercase tracking-wider mb-2">
                  {cat.replace("_", " ")}
                </p>
                <div className="space-y-2">
                  {candidate.interview_questions?.[cat]?.map((q) => (
                    <div key={q.id} className="p-3 bg-dark-800 rounded-lg border border-dark-700">
                      <p className="text-sm text-dark-300">
                        <span className="text-dark-500 mr-2">Q{q.id}.</span>
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
          <h3 className="font-semibold text-white mb-4 flex items-center gap-2">
            <Zap size={16} className="text-yellow-400" />
            Evaluation Results
          </h3>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-dark-800 rounded-xl p-4 text-center">
              <p className="text-2xl font-bold text-white">{eval_data.overall_score}</p>
              <p className="text-xs text-dark-400 mt-1">Overall Score</p>
            </div>
            <div className="bg-dark-800 rounded-xl p-4 text-center col-span-3">
              <p className="text-sm font-medium text-white">{eval_data.hiring_recommendation}</p>
              <p className="text-xs text-dark-400 mt-1">Hiring Recommendation</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <div>
              <p className="text-xs font-semibold text-green-400 uppercase tracking-wider mb-2">Strengths</p>
              <ul className="space-y-1">
                {eval_data.strengths?.map((s, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-dark-300">
                    <CheckCircle size={13} className="text-green-400 mt-0.5 shrink-0" />
                    {s}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <p className="text-xs font-semibold text-red-400 uppercase tracking-wider mb-2">Weaknesses</p>
              <ul className="space-y-1">
                {eval_data.weaknesses?.map((w, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-dark-300">
                    <XCircle size={13} className="text-red-400 mt-0.5 shrink-0" />
                    {w}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <div className="p-4 bg-dark-800 rounded-xl border border-dark-700">
            <p className="text-xs font-semibold text-dark-400 uppercase tracking-wider mb-2">Summary</p>
            <p className="text-sm text-dark-300">{eval_data.summary}</p>
          </div>

          {/* Per question scores */}
          {eval_data.per_question && (
            <div className="mt-4 space-y-3">
              <p className="text-xs font-semibold text-dark-400 uppercase tracking-wider">Per Question</p>
              {eval_data.per_question.map((q, i) => (
                <div key={i} className="p-3 bg-dark-800 rounded-xl border border-dark-700">
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-sm font-medium text-white truncate flex-1 mr-4">{q.question}</p>
                    <span className={`text-sm font-bold shrink-0 ${
                      q.score >= 70 ? "text-green-400" : q.score >= 50 ? "text-yellow-400" : "text-red-400"
                    }`}>
                      {q.score}/100
                    </span>
                  </div>
                  <p className="text-xs text-dark-400">{q.feedback}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Schedule Result */}
      {candidate.schedule && (
        <div className="card border-primary-600/30 bg-primary-600/5">
          <h3 className="font-semibold text-white mb-3 flex items-center gap-2">
            <Calendar size={16} className="text-primary-400" />
            Scheduled
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-xs text-dark-400">Next Step</p>
              <p className="text-sm font-medium text-white mt-1">{candidate.schedule.next_step}</p>
            </div>
            <div>
              <p className="text-xs text-dark-400">Decision</p>
              <Badge status={candidate.schedule.decision} className="mt-1">
                {candidate.schedule.decision}
              </Badge>
            </div>
            <div>
              <p className="text-xs text-dark-400">Scheduled Time</p>
              <p className="text-sm font-medium text-white mt-1">{candidate.schedule.scheduled_time}</p>
            </div>
            <div>
              <p className="text-xs text-dark-400">Score Used</p>
              <p className="text-sm font-medium text-white mt-1">{candidate.schedule.overall_score}/100</p>
            </div>
          </div>
        </div>
      )}

      {/* Offline interview confirmed */}
      {candidate.offline_interview && (
        <div className="card border-green-600/30 bg-green-600/5">
          <h3 className="font-semibold text-white mb-3 flex items-center gap-2">
            <Calendar size={16} className="text-green-400" />
            Offline Interview Confirmed
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <p className="text-xs text-dark-400">Date</p>
              <p className="text-sm font-medium text-white mt-1">{candidate.offline_interview.date}</p>
            </div>
            <div>
              <p className="text-xs text-dark-400">Time</p>
              <p className="text-sm font-medium text-white mt-1">{candidate.offline_interview.time}</p>
            </div>
            <div>
              <p className="text-xs text-dark-400">Location</p>
              <p className="text-sm font-medium text-white mt-1">{candidate.offline_interview.location}</p>
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