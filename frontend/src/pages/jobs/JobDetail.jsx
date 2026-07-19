import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  ArrowLeft, Briefcase, MapPin, Clock,
  Users, Plus, CheckCircle, XCircle,
  Star, ChevronRight, Trash2
} from "lucide-react";
import { jobsAPI } from "../../api/jobs";
import { candidatesAPI } from "../../api/candidates";
import Button from "../../components/ui/Button";
import Badge from "../../components/ui/Badge";
import Modal from "../../components/ui/Modal";
import Input from "../../components/ui/Input";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import toast from "react-hot-toast";

// ── Screen Candidate Modal ────────────────────────────────────────────────────
function ScreenCandidateModal({ isOpen, onClose, jobId, onScreened }) {
  const [form, setForm] = useState({
    candidate_name : "",
    candidate_email: "",
    resume_text    : ""
  });
  const [file,      setFile]      = useState(null);
  const [inputMode, setInputMode] = useState("text");
  const [loading,   setLoading]   = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.candidate_name.trim()) {
      toast.error("Candidate name is required");
      return;
    }
    setLoading(true);
    try {
      let res;
      if (inputMode === "file" && file) {
        res = await candidatesAPI.screenFromFile(
          jobId,
          file,
          form.candidate_name,
          form.candidate_email
        );
      } else {
        if (!form.resume_text.trim()) {
          toast.error("Resume text is required");
          setLoading(false);
          return;
        }
        res = await candidatesAPI.screen(jobId, form);
      }
      if (res.data.success) {
        toast.success(`${form.candidate_name} screened successfully!`);
        setForm({ candidate_name: "", candidate_email: "", resume_text: "" });
        setFile(null);
        onScreened(res.data.candidate);
        onClose();
      }
    } catch (err) {
      toast.error(err.response?.data?.error || "Screening failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Screen a Candidate"
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={loading} onClick={handleSubmit}>
            <Star size={16} /> Screen Candidate
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {/* Name & Email */}
        <Input
          label="Candidate Name"
          value={form.candidate_name}
          onChange={(e) => setForm({ ...form, candidate_name: e.target.value })}
          placeholder="John Doe"
          required
        />
        <Input
          label="Candidate Email"
          type="email"
          value={form.candidate_email}
          onChange={(e) => setForm({ ...form, candidate_email: e.target.value })}
          placeholder="john@email.com"
        />

        {/* Toggle */}
        <div className="flex gap-2 p-1 bg-dark-800 rounded-lg">
          <button
            onClick={() => setInputMode("text")}
            className={`flex-1 py-2 rounded-md text-sm font-medium transition-all ${
              inputMode === "text"
                ? "bg-primary-600 text-white"
                : "text-dark-400 hover:text-white"
            }`}
          >
            Paste Resume
          </button>
          <button
            onClick={() => setInputMode("file")}
            className={`flex-1 py-2 rounded-md text-sm font-medium transition-all ${
              inputMode === "file"
                ? "bg-primary-600 text-white"
                : "text-dark-400 hover:text-white"
            }`}
          >
            Upload PDF/Word
          </button>
        </div>

        {/* Text input */}
        {inputMode === "text" && (
          <div>
            <label className="text-sm font-medium text-dark-300 block mb-2">
              Resume Text
            </label>
            <p className="text-xs text-dark-500 mb-2">
              Paste the candidate's resume. AI will score it against job requirements.
            </p>
            <textarea
              value={form.resume_text}
              onChange={(e) => setForm({ ...form, resume_text: e.target.value })}
              placeholder="Name: John Doe&#10;Skills: Python, Flask, MongoDB...&#10;Experience: 3 years..."
              rows={8}
              className="input resize-none"
              required
            />
          </div>
        )}

        {/* File upload */}
        {inputMode === "file" && (
          <div>
            <label className="text-sm font-medium text-dark-300 block mb-2">
              Upload Resume File
            </label>
            <p className="text-xs text-dark-500 mb-3">
              Upload a PDF or Word (.docx) resume file.
            </p>
            <div
              className="border-2 border-dashed border-dark-700 rounded-xl p-8 text-center hover:border-primary-500 transition-all cursor-pointer"
              onClick={() => document.getElementById("resume-file-input").click()}
            >
              {file ? (
                <div className="space-y-2">
                  <p className="text-green-400 font-medium">{file.name}</p>
                  <p className="text-dark-400 text-xs">{(file.size / 1024).toFixed(1)} KB</p>
                  <button
                    onClick={(e) => { e.stopPropagation(); setFile(null); }}
                    className="text-red-400 text-xs hover:text-red-300"
                  >
                    Remove file
                  </button>
                </div>
              ) : (
                <div className="space-y-2">
                  <p className="text-dark-400">Click to upload resume</p>
                  <p className="text-dark-600 text-xs">PDF or Word (.docx) up to 10MB</p>
                </div>
              )}
            </div>
            <input
              id="resume-file-input"
              type="file"
              accept=".pdf,.docx"
              className="hidden"
              onChange={(e) => setFile(e.target.files[0])}
            />
          </div>
        )}

        {loading && (
          <div className="flex items-center gap-2 text-primary-400 text-sm">
            <LoadingSpinner size="sm" />
            <span>AI is screening the candidate...</span>
          </div>
        )}
      </div>
    </Modal>
  );
}

// ── Candidate Row ─────────────────────────────────────────────────────────────
function CandidateRow({ candidate, onDelete, onClick }) {
  const [deleting, setDeleting] = useState(false);

  const scoreColor = candidate.match_score >= 70
    ? "text-green-400"
    : candidate.match_score >= 50
    ? "text-yellow-400"
    : "text-red-400";

  const handleDelete = async (e) => {
    e.stopPropagation();
    if (!window.confirm("Delete this candidate?")) return;
    setDeleting(true);
    try {
      await candidatesAPI.delete(candidate._id);
      toast.success("Candidate deleted");
      onDelete(candidate._id);
    } catch {
      toast.error("Failed to delete");
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div
      onClick={onClick}
      className="flex items-center justify-between p-4 rounded-xl bg-dark-800/50 border border-dark-800 hover:border-dark-700 cursor-pointer transition-all group"
    >
      <div className="flex items-center gap-4">
        {/* Avatar */}
        <div className="w-10 h-10 rounded-full bg-primary-600/20 flex items-center justify-center text-primary-400 font-bold text-sm">
          {candidate.candidate_name?.charAt(0).toUpperCase()}
        </div>

        {/* Info */}
        <div>
          <p className="font-medium text-white text-sm">{candidate.candidate_name}</p>
          <p className="text-xs text-dark-400">{candidate.candidate_email}</p>
        </div>
      </div>

      <div className="flex items-center gap-6">
        {/* Score */}
        <div className="text-center">
          <p className={`text-lg font-bold ${scoreColor}`}>
            {candidate.match_score}%
          </p>
          <p className="text-xs text-dark-500">Match</p>
        </div>

        {/* Recommendation */}
        <div className="hidden md:flex items-center gap-1.5">
          {candidate.recommendation === "Shortlist"
            ? <CheckCircle size={14} className="text-green-400" />
            : <XCircle size={14} className="text-red-400" />
          }
          <span className={`text-xs font-medium ${
            candidate.recommendation === "Shortlist"
              ? "text-green-400"
              : "text-red-400"
          }`}>
            {candidate.recommendation}
          </span>
        </div>

        {/* Status */}
        <Badge status={candidate.status}>{candidate.status}</Badge>

        {/* Actions */}
        <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            onClick={handleDelete}
            disabled={deleting}
            className="p-1.5 text-dark-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-all"
          >
            <Trash2 size={14} />
          </button>
          <ChevronRight size={16} className="text-dark-500" />
        </div>
      </div>
    </div>
  );
}

// ── Main JobDetail Page ───────────────────────────────────────────────────────
export default function JobDetail() {
  const { id }                    = useParams();
  const navigate                  = useNavigate();
  const [job,        setJob]       = useState(null);
  const [candidates, setCandidates]= useState([]);
  const [loading,    setLoading]   = useState(true);
  const [showModal,  setShowModal] = useState(false);

  useEffect(() => {
    fetchData();
  }, [id]);

  const fetchData = async () => {
    try {
      const [jobRes, candsRes] = await Promise.all([
        jobsAPI.getOne(id),
        candidatesAPI.getAll(id)
      ]);
      setJob(jobRes.data.job);
      setCandidates(candsRes.data.candidates || []);
    } catch {
      toast.error("Failed to load job details");
      navigate("/jobs");
    } finally {
      setLoading(false);
    }
  };

  const handleScreened = (candidate) => {
    setCandidates(prev => [candidate, ...prev]);
  };

  const handleDelete = (id) => {
    setCandidates(prev => prev.filter(c => c._id !== id));
  };

  if (loading) {
    return (
      <div className="h-64 flex items-center justify-center">
        <LoadingSpinner size="lg" text="Loading job details..." />
      </div>
    );
  }

  if (!job) return null;

  const avgScore = candidates.length
    ? Math.round(candidates.reduce((sum, c) => sum + c.match_score, 0) / candidates.length)
    : 0;

  return (
    <div className="space-y-6">

      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => navigate("/jobs")}
          className="p-2 text-dark-400 hover:text-white hover:bg-dark-800 rounded-lg transition-all"
        >
          <ArrowLeft size={20} />
        </button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-white">{job.job_title}</h1>
          <div className="flex items-center gap-4 mt-1 text-dark-400 text-sm">
            <span className="flex items-center gap-1">
              <MapPin size={13} /> {job.location}
            </span>
            <span className="flex items-center gap-1">
              <Clock size={13} /> {job.job_type}
            </span>
            <span className="flex items-center gap-1">
              <Briefcase size={13} /> {job.experience_required}
            </span>
          </div>
        </div>
        <Badge status={job.status}>{job.status}</Badge>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-4">
        <div className="card text-center">
          <p className="text-2xl font-bold text-white">{candidates.length}</p>
          <p className="text-dark-400 text-sm">Total Candidates</p>
        </div>
        <div className="card text-center">
          <p className="text-2xl font-bold text-green-400">
            {candidates.filter(c => c.recommendation === "Shortlist").length}
          </p>
          <p className="text-dark-400 text-sm">Shortlisted</p>
        </div>
        <div className="card text-center">
          <p className="text-2xl font-bold text-primary-400">{avgScore}%</p>
          <p className="text-dark-400 text-sm">Avg Match Score</p>
        </div>
      </div>

      {/* Content grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Candidates list */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-white">
              Candidates ({candidates.length})
            </h2>
            <Button onClick={() => setShowModal(true)}>
              <Plus size={16} /> Screen Candidate
            </Button>
          </div>

          {candidates.length === 0 ? (
            <div className="card text-center py-12">
              <Users size={40} className="text-dark-600 mx-auto mb-3" />
              <p className="text-dark-400">No candidates screened yet</p>
              <Button
                className="mt-4 mx-auto"
                onClick={() => setShowModal(true)}
              >
                <Plus size={16} /> Screen First Candidate
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              {candidates.map((c) => (
                <CandidateRow
                  key={c._id}
                  candidate={c}
                  onDelete={handleDelete}
                  onClick={() => navigate(`/candidates/${c._id}`)}
                />
              ))}
            </div>
          )}
        </div>

        {/* Job Details sidebar */}
        <div className="space-y-4">
          <div className="card">
            <h3 className="font-semibold text-white mb-3">Required Skills</h3>
            <div className="flex flex-wrap gap-2">
              {job.required_skills?.map((skill) => (
                <span
                  key={skill}
                  className="px-2.5 py-1 bg-primary-600/10 text-primary-400 border border-primary-600/20 text-xs rounded-lg font-medium"
                >
                  {skill}
                </span>
              ))}
            </div>
          </div>

          <div className="card">
            <h3 className="font-semibold text-white mb-3">Responsibilities</h3>
            <ul className="space-y-2">
              {job.responsibilities?.map((r, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-dark-300">
                  <CheckCircle size={14} className="text-green-400 mt-0.5 shrink-0" />
                  {r}
                </li>
              ))}
            </ul>
          </div>

          {job.qualifications?.length > 0 && (
            <div className="card">
              <h3 className="font-semibold text-white mb-3">Qualifications</h3>
              <ul className="space-y-2">
                {job.qualifications?.map((q, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-dark-300">
                    <CheckCircle size={14} className="text-primary-400 mt-0.5 shrink-0" />
                    {q}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>

      {/* Screen Candidate Modal */}
      <ScreenCandidateModal
        isOpen={showModal}
        onClose={() => setShowModal(false)}
        jobId={id}
        onScreened={handleScreened}
      />
    </div>
  );
}