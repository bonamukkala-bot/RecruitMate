import { useState, useEffect } from "react";
import SettingsSection from "./SettingsSection";
import { useSettings } from "../../context/SettingsContext";
import useRole from "../../hooks/useRole";
import { settingsAPI } from "../../api/settings";
import Button from "../ui/Button";
import Modal from "../ui/Modal";
import { Lock, Shield, Trash2, RotateCcw, AlertTriangle, CheckCircle2, Clock } from "lucide-react";
import toast from "react-hot-toast";

const DEFAULT_PRIVACY = {
  data_retention_days: 0,
  consent_text: (
    "I consent to the collection and processing of my interview audio, " +
    "video, and responses for the purpose of job application evaluation " +
    "by RecruitMate AI and the hiring organization."
  ),
  record_proctoring_events: true
};

const RETENTION_OPTIONS = [
  { label: "Keep Forever (No automatic purge)", value: 0 },
  { label: "30 Days (1 Month)", value: 30 },
  { label: "90 Days (3 Months)", value: 90 },
  { label: "180 Days (6 Months)", value: 180 },
  { label: "365 Days (1 Year)", value: 365 },
  { label: "730 Days (2 Years)", value: 730 },
  { label: "1095 Days (3 Years — Maximum)", value: 1095 }
];

export default function PrivacySettings() {
  const { settings, loading, updateSection, resetSection } = useSettings();
  const { isAdmin, isOwner } = useRole();
  const [formData, setFormData] = useState(DEFAULT_PRIVACY);
  const [savedPrivacy, setSavedPrivacy] = useState(DEFAULT_PRIVACY);
  const [saving, setSaving] = useState(false);

  // ── Purge Modal State ──────────────────────────────────────────────────────
  const [purgeModalOpen, setPurgeModalOpen] = useState(false);
  const [checkingPurge, setCheckingPurge] = useState(false);
  const [purging, setPurging] = useState(false);
  const [purgePreview, setPurgePreview] = useState(null);

  useEffect(() => {
    if (settings?.privacy) {
      const initial = {
        data_retention_days: settings.privacy.data_retention_days ?? 0,
        consent_text: settings.privacy.consent_text || DEFAULT_PRIVACY.consent_text,
        record_proctoring_events: settings.privacy.record_proctoring_events ?? true
      };
      setFormData(initial);
      setSavedPrivacy(initial);
    }
  }, [settings]);

  const isDirty = JSON.stringify(formData) !== JSON.stringify(savedPrivacy);

  const handleChange = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleSave = async (e) => {
    e.preventDefault();
    if (!isAdmin) {
      toast.error("Only administrators can update privacy policies");
      return;
    }
    setSaving(true);
    try {
      const res = await updateSection("privacy", formData);
      if (res.success) {
        toast.success("Privacy settings updated successfully");
      } else {
        toast.error(res.error || "Failed to update privacy settings");
      }
    } catch (err) {
      toast.error(err.response?.data?.error || "Failed to update privacy settings");
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    if (!isAdmin) {
      toast.error("Only administrators can reset settings");
      return;
    }
    setSaving(true);
    try {
      const res = await resetSection("privacy");
      if (res.success) {
        toast.success("Privacy settings reset to defaults");
      }
    } catch (err) {
      toast.error("Failed to reset settings");
    } finally {
      setSaving(false);
    }
  };

  // ── Manual Retention Purge Flow ────────────────────────────────────────────
  const openPurgeModal = async () => {
    setPurgeModalOpen(true);
    setCheckingPurge(true);
    setPurgePreview(null);
    try {
      // Run dry-run check
      const res = await settingsAPI.purgeExpired(false);
      if (res.data?.success) {
        setPurgePreview(res.data);
      } else {
        toast.error(res.data?.error || "Could not check expired candidates");
      }
    } catch (err) {
      toast.error(err.response?.data?.error || "Could not check expired candidates");
    } finally {
      setCheckingPurge(false);
    }
  };

  const handleExecutePurge = async () => {
    setPurging(true);
    try {
      const res = await settingsAPI.purgeExpired(true);
      if (res.data?.success) {
        toast.success(`Purged ${res.data.candidates_purged} expired candidate(s)`);
        setPurgeModalOpen(false);
      } else {
        toast.error(res.data?.error || "Failed to purge candidates");
      }
    } catch (err) {
      toast.error(err.response?.data?.error || "Failed to purge candidates");
    } finally {
      setPurging(false);
    }
  };

  return (
    <form onSubmit={handleSave}>
      <SettingsSection
        title="Privacy, Consent & Data Retention"
        description="Configure automated candidate data retention windows, customize candidate interview consent agreements, and manage proctoring event storage."
        isDirty={isDirty}
        onSave={handleSave}
        onReset={handleReset}
        saving={saving}
        loading={loading}
      >
        <div className="space-y-8 max-w-2xl">
          {/* Data Retention */}
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-ink-500 uppercase tracking-wider flex items-center gap-2">
              <Clock size={16} className="text-ledger-500" />
              Automated Data Retention
            </h3>
            <p className="text-xs text-stone-500">
              Set the lifespan for candidate records. Once past this threshold, candidate data (including resumes,
              evaluations, audio responses, and pipeline logs) will be eligible for automated purging.
            </p>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-ink-500">
                Retention Window
              </label>
              <select
                value={formData.data_retention_days}
                onChange={(e) => handleChange("data_retention_days", parseInt(e.target.value, 10))}
                disabled={!isAdmin}
                className="w-full px-3 py-2 text-sm bg-stone-50 border border-stone-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                {RETENTION_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            {isOwner && formData.data_retention_days > 0 && (
              <div className="p-4 bg-amber-50/70 border border-amber-200 rounded-xl flex items-center justify-between">
                <div>
                  <h4 className="text-xs font-bold text-amber-900">
                    Manual Retention Cleanup
                  </h4>
                  <p className="text-[11px] text-amber-700 mt-0.5">
                    Preview and remove candidates older than {formData.data_retention_days} days.
                  </p>
                </div>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={openPurgeModal}
                  className="shrink-0"
                >
                  <Trash2 size={13} className="mr-1.5 text-amber-700" />
                  Review Purge
                </Button>
              </div>
            )}
          </div>

          <hr className="border-stone-200" />

          {/* Candidate Consent Agreement */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-ink-500 uppercase tracking-wider flex items-center gap-2">
                <Lock size={16} className="text-ledger-500" />
                Candidate Interview Consent
              </h3>
              {isAdmin && (
                <button
                  type="button"
                  onClick={() => handleChange("consent_text", DEFAULT_PRIVACY.consent_text)}
                  className="text-xs text-stone-500 hover:text-ink-600 flex items-center gap-1 font-medium"
                >
                  <RotateCcw size={12} />
                  <span>Restore Default</span>
                </button>
              )}
            </div>
            <p className="text-xs text-stone-500">
              Candidates are presented with this legal notice before commencing their voice interview.
              Acceptance via a required checkbox is recorded with a timestamp.
            </p>

            <div className="space-y-1">
              <textarea
                rows={4}
                value={formData.consent_text}
                onChange={(e) => handleChange("consent_text", e.target.value)}
                disabled={!isAdmin}
                maxLength={5000}
                placeholder="Enter mandatory interview consent wording..."
                className="w-full px-3 py-2 text-sm bg-stone-50 border border-stone-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 font-sans leading-relaxed"
              />
              <div className="flex justify-between text-[11px] text-stone-400">
                <span>Required for all AI voice interviews</span>
                <span>{formData.consent_text.length} / 5000 characters</span>
              </div>
            </div>
          </div>

          <hr className="border-stone-200" />

          {/* Proctoring Event Storage */}
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-ink-500 uppercase tracking-wider flex items-center gap-2">
              <Shield size={16} className="text-ledger-500" />
              Proctoring Integrity Event Recording
            </h3>

            <div className="flex items-start gap-3 p-4 bg-stone-50 border border-stone-200 rounded-xl">
              <input
                type="checkbox"
                id="record_proctoring_events"
                checked={formData.record_proctoring_events}
                onChange={(e) => handleChange("record_proctoring_events", e.target.checked)}
                disabled={!isAdmin}
                className="mt-1 w-4 h-4 text-indigo-600 rounded border-stone-300 focus:ring-indigo-500"
              />
              <label htmlFor="record_proctoring_events" className="text-xs cursor-pointer space-y-1">
                <span className="font-semibold text-ink-600 block">
                  Store individual proctoring integrity events (tab switches, webcam detections)
                </span>
                <span className="text-stone-500 block leading-relaxed">
                  When unchecked, integrity rules (such as session termination on repeated violations) remain strictly
                  enforced in real-time, but detailed timestamped violation event logs are not retained on candidate profiles.
                </span>
              </label>
            </div>
          </div>
        </div>
      </SettingsSection>

      {/* ── RETENTION PURGE MODAL ─────────────────────────────────────────── */}
      <Modal
        isOpen={purgeModalOpen}
        onClose={() => setPurgeModalOpen(false)}
        title="Review Expired Candidate Data"
        size="md"
        footer={
          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="secondary"
              onClick={() => setPurgeModalOpen(false)}
              disabled={purging}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="danger"
              disabled={checkingPurge || !purgePreview || purgePreview.candidates_found === 0}
              loading={purging}
              onClick={handleExecutePurge}
            >
              Permanently Delete ({purgePreview?.candidates_found || 0})
            </Button>
          </div>
        }
      >
        <div className="space-y-4">
          {checkingPurge ? (
            <div className="py-8 text-center text-sm text-stone-500">
              Scanning database for candidates past retention window...
            </div>
          ) : purgePreview ? (
            <div className="space-y-3">
              <div className="p-3 bg-stone-50 border border-stone-200 rounded-xl text-xs space-y-1">
                <div className="flex justify-between">
                  <span className="text-stone-500">Configured Retention Period:</span>
                  <span className="font-bold text-ink-600">{formData.data_retention_days} Days</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-stone-500">Expired Candidates Found:</span>
                  <span className="font-bold text-ink-600">{purgePreview.candidates_found}</span>
                </div>
              </div>

              {purgePreview.candidates_found > 0 ? (
                <div className="p-3 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl text-xs flex items-start gap-2.5">
                  <AlertTriangle size={18} className="shrink-0 text-rose-600 mt-0.5" />
                  <div>
                    <p className="font-semibold">Irreversible Operation</p>
                    <p className="mt-0.5 text-rose-700 leading-relaxed">
                      Executing this will permanently delete {purgePreview.candidates_found} candidate record(s), resumes,
                      interview transcripts, and pipeline logs. A privacy-safe audit record containing only hashed identifiers will be retained.
                    </p>
                  </div>
                </div>
              ) : (
                <div className="p-4 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl text-xs flex items-center gap-2">
                  <CheckCircle2 size={16} className="text-emerald-600 shrink-0" />
                  <span>No candidates exceed the {formData.data_retention_days}-day retention window at this time.</span>
                </div>
              )}
            </div>
          ) : null}
        </div>
      </Modal>
    </form>
  );
}
