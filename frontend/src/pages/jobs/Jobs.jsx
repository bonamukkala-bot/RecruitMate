import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Plus, Briefcase, MapPin, Clock,
  Users, Trash2, Eye, Search
} from "lucide-react";
import { jobsAPI } from "../../api/jobs";
import Button from "../../components/ui/Button";
import Badge from "../../components/ui/Badge";
import Modal from "../../components/ui/Modal";
import Input from "../../components/ui/Input";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import toast from "react-hot-toast";

function CreateJobModal({ isOpen, onClose, onCreated }) {
  const [jdText,    setJdText]    = useState("");
  const [brief,     setBrief]     = useState("");
  const [file,      setFile]      = useState(null);
  const [inputMode, setInputMode] = useState("ai"); // "ai", "text", "file"
  const [loading,   setLoading]   = useState(false);
  const [generating, setGenerating] = useState(false);

  const handleGenerate = async () => {
    if (!brief.trim()) {
      toast.error("Please enter a brief description");
      return;
    }
    setGenerating(true);
    try {
      const res = await jobsAPI.generateJD(brief);
      if (res.data.success) {
        setJdText(res.data.jd_text);
        toast.success("JD generated! Review and edit if needed.");
      }
    } catch (err) {
      toast.error(err.response?.data?.error || "Generation failed");
    } finally {
      setGenerating(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      let res;
      if (inputMode === "file" && file) {
        res = await jobsAPI.createFromFile(file);
      } else {
        if (!jdText.trim()) {
          toast.error("Please enter or generate a job description");
          setLoading(false);
          return;
        }
        res = await jobsAPI.create({ jd_text: jdText });
      }
      if (res.data.success) {
        toast.success("Job created successfully!");
        setJdText("");
        setBrief("");
        setFile(null);
        onCreated(res.data.job);
        onClose();
      }
    } catch (err) {
      toast.error(err.response?.data?.error || "Failed to create job");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Post a New Job"
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={loading} onClick={handleSubmit}>
            <Plus size={16} /> Create Job
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {/* Mode toggle */}
        <div className="flex gap-1 p-1 bg-stone-100 rounded-lg">
          {[
            { key: "ai",   label: "AI Generate" },
            { key: "text", label: "Paste Text"     },
            { key: "file", label: "Upload File"    }
          ].map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setInputMode(key)}
              className={`flex-1 py-2 rounded-md text-sm font-medium transition-all ${
                inputMode === key
                  ? "bg-ledger-500 text-white"
                  : "text-stone-500 hover:text-ink-500"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {/* AI Generate mode */}
        {inputMode === "ai" && (
          <div className="space-y-3">
            <div>
              <label className="text-sm font-medium text-ink-400 block mb-2">
                Describe the role in one line
              </label>
              <p className="text-xs text-stone-500 mb-3">
                e.g. "Senior Python developer for our fintech startup in Hyderabad"
              </p>
              <div className="flex gap-2">
                <input
                  value={brief}
                  onChange={(e) => setBrief(e.target.value)}
                  placeholder="I need a Python developer with Flask and MongoDB..."
                  className="input flex-1"
                  onKeyDown={(e) => e.key === "Enter" && handleGenerate()}
                />
                <Button
                  loading={generating}
                  onClick={handleGenerate}
                  className="shrink-0"
                >
                  {generating ? "Generating..." : "Generate"}
                </Button>
              </div>
            </div>

            {jdText && (
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-sm font-medium text-ink-400">
                    Generated JD — Review & Edit
                  </label>
                  <span className="stamp text-verified-600" style={{ background: "rgba(31,110,88,0.07)" }}>Ready</span>
                </div>
                <textarea
                  value={jdText}
                  onChange={(e) => setJdText(e.target.value)}
                  rows={12}
                  className="input resize-none text-sm"
                />
              </div>
            )}

            {!jdText && (
              <div className="border-2 border-dashed border-stone-200 rounded-xl p-8 text-center">
                <p className="text-stone-500 text-sm">
                  Enter a brief description above and click Generate
                </p>
                <p className="text-stone-400 text-xs mt-1">
                  AI will write a complete professional JD in seconds
                </p>
              </div>
            )}
          </div>
        )}

        {/* Text mode */}
        {inputMode === "text" && (
          <div>
            <label className="text-sm font-medium text-ink-400 block mb-2">
              Job Description
            </label>
            <textarea
              value={jdText}
              onChange={(e) => setJdText(e.target.value)}
              placeholder="We are hiring a Senior Python Developer..."
              rows={12}
              className="input resize-none"
            />
          </div>
        )}

        {/* File upload mode */}
        {inputMode === "file" && (
          <div>
            <label className="text-sm font-medium text-ink-400 block mb-2">
              Upload JD File
            </label>
            <div
              className="border-2 border-dashed border-stone-200 rounded-xl p-8 text-center hover:border-ledger-400 transition-all cursor-pointer"
              onClick={() => document.getElementById("jd-file-input").click()}
            >
              {file ? (
                <div className="space-y-2">
                  <p className="text-verified-600 font-medium">{file.name}</p>
                  <p className="text-stone-500 text-xs">{(file.size / 1024).toFixed(1)} KB</p>
                  <button
                    onClick={(e) => { e.stopPropagation(); setFile(null); }}
                    className="text-brick-600 text-xs hover:text-brick-700"
                  >
                    Remove file
                  </button>
                </div>
              ) : (
                <div className="space-y-2">
                  <p className="text-stone-500">Click to upload PDF or Word file</p>
                  <p className="text-stone-400 text-xs">AI will extract the JD automatically</p>
                </div>
              )}
            </div>
            <input
              id="jd-file-input"
              type="file"
              accept=".pdf,.docx"
              className="hidden"
              onChange={(e) => setFile(e.target.files[0])}
            />
          </div>
        )}

        {loading && (
          <div className="flex items-center gap-2 text-ledger-600 text-sm">
            <LoadingSpinner size="sm" />
            <span>AI is parsing your job description...</span>
          </div>
        )}
      </div>
    </Modal>
  );
}

// ── Job Card ──────────────────────────────────────────────────────────────────
function JobCard({ job, onDelete, onClick }) {
  const [deleting, setDeleting] = useState(false);

  const handleDelete = async (e) => {
    e.stopPropagation();
    if (!window.confirm("Delete this job?")) return;
    setDeleting(true);
    try {
      await jobsAPI.delete(job._id);
      toast.success("Job deleted");
      onDelete(job._id);
    } catch {
      toast.error("Failed to delete job");
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div
      onClick={onClick}
      className="card card-notch hover:border-ledger-200 cursor-pointer transition-all duration-200 group"
    >
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-ledger-50 rounded-xl flex items-center justify-center">
            <Briefcase size={18} className="text-ledger-600" />
          </div>
          <div>
            <h3 className="font-semibold text-ink-500 group-hover:text-ledger-600 transition-colors">
              {job.job_title}
            </h3>
            <p className="text-xs text-stone-500">{job.experience_required} experience</p>
          </div>
        </div>
        <Badge status={job.status}>{job.status}</Badge>
      </div>

      {/* Skills */}
      <div className="flex flex-wrap gap-1.5 mb-4">
        {job.required_skills?.slice(0, 4).map((skill) => (
          <span
            key={skill}
            className="px-2 py-0.5 bg-stone-50 text-stone-600 text-xs rounded-md border border-stone-200"
          >
            {skill}
          </span>
        ))}
        {job.required_skills?.length > 4 && (
          <span className="px-2 py-0.5 bg-stone-50 text-stone-500 text-xs rounded-md border border-stone-200">
            +{job.required_skills.length - 4} more
          </span>
        )}
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between pt-3 border-t border-stone-200">
        <div className="flex items-center gap-4 text-xs text-stone-500">
          <span className="flex items-center gap-1">
            <MapPin size={12} /> {job.location}
          </span>
          <span className="flex items-center gap-1">
            <Clock size={12} /> {job.job_type}
          </span>
          <span className="flex items-center gap-1 font-mono">
            <Users size={12} /> {job.candidates_count || 0} candidates
          </span>
        </div>
        <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            onClick={(e) => { e.stopPropagation(); }}
            className="p-1.5 text-stone-500 hover:text-ink-500 hover:bg-stone-100 rounded-lg transition-all"
          >
            <Eye size={14} />
          </button>
          <button
            onClick={handleDelete}
            disabled={deleting}
            className="p-1.5 text-stone-500 hover:text-brick-600 hover:bg-brick-50 rounded-lg transition-all"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main Jobs Page ────────────────────────────────────────────────────────────
export default function Jobs() {
  const [jobs,      setJobs]      = useState([]);
  const [filtered,  setFiltered]  = useState([]);
  const [loading,   setLoading]   = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [search,    setSearch]    = useState("");
  const navigate                  = useNavigate();

  useEffect(() => {
    fetchJobs();
  }, []);

  useEffect(() => {
    if (!search.trim()) {
      setFiltered(jobs);
    } else {
      setFiltered(jobs.filter(j =>
        j.job_title.toLowerCase().includes(search.toLowerCase()) ||
        j.location?.toLowerCase().includes(search.toLowerCase())
      ));
    }
  }, [search, jobs]);

  const fetchJobs = async () => {
    try {
      const res = await jobsAPI.getAll();
      setJobs(res.data.jobs || []);
      setFiltered(res.data.jobs || []);
    } catch {
      toast.error("Failed to load jobs");
    } finally {
      setLoading(false);
    }
  };

  const handleCreated = (job) => {
    setJobs(prev => [job, ...prev]);
  };

  const handleDelete = (id) => {
    setJobs(prev => prev.filter(j => j._id !== id));
  };

  if (loading) {
    return (
      <div className="h-64 flex items-center justify-center">
        <LoadingSpinner size="lg" text="Loading jobs..." />
      </div>
    );
  }

  return (
    <div className="space-y-6">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-ink-500 font-display">Jobs</h1>
          <p className="text-stone-500 text-sm mt-1">
            {jobs.length} job{jobs.length !== 1 ? "s" : ""} posted
          </p>
        </div>
        <Button onClick={() => setShowModal(true)}>
          <Plus size={16} /> Post Job
        </Button>
      </div>

      {/* Search */}
      <Input
        placeholder="Search jobs by title or location..."
        icon={Search}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />

      {/* Jobs Grid */}
      {filtered.length === 0 ? (
        <div className="text-center py-20">
          <Briefcase size={48} className="text-stone-300 mx-auto mb-4" />
          <p className="text-stone-500 font-medium">No jobs found</p>
          <p className="text-stone-400 text-sm mt-1">
            {search ? "Try a different search" : "Post your first job to get started"}
          </p>
          {!search && (
            <Button className="mt-4 mx-auto" onClick={() => setShowModal(true)}>
              <Plus size={16} /> Post First Job
            </Button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map((job) => (
            <JobCard
              key={job._id}
              job={job}
              onDelete={handleDelete}
              onClick={() => navigate(`/jobs/${job._id}`)}
            />
          ))}
        </div>
      )}

      {/* Create Job Modal */}
      <CreateJobModal
        isOpen={showModal}
        onClose={() => setShowModal(false)}
        onCreated={handleCreated}
      />
    </div>
  );
}