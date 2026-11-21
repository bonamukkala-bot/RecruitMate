import { useState, useEffect } from "react";
import SettingsSection from "./SettingsSection";
import { useSettings } from "../../context/SettingsContext";
import Input from "../ui/Input";
import { Mic, Clock, ShieldCheck } from "lucide-react";
import toast from "react-hot-toast";

const DEFAULT_INTERVIEW = {
  duration_minutes: 30,
  question_count: 8,
  difficulty: "medium",
  question_types: "mixed",
  proctoring: {
    enabled: true,
    face_detection: true,
    fullscreen_required: true,
    tab_switch_violations_allowed: 1,
    no_face_grace_seconds: 10,
    terminate_on_violation: true
  }
};

export default function InterviewSettings() {
  const { settings, loading, updateSection, resetSection } = useSettings();
  const [formData, setFormData] = useState(DEFAULT_INTERVIEW);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (settings?.interview) {
      setFormData({
        duration_minutes: settings.interview.duration_minutes ?? 30,
        question_count: settings.interview.question_count ?? 8,
        difficulty: settings.interview.difficulty ?? "medium",
        question_types: settings.interview.question_types ?? "mixed",
        proctoring: {
          enabled: settings.interview.proctoring?.enabled ?? true,
          face_detection: settings.interview.proctoring?.face_detection ?? true,
          fullscreen_required: settings.interview.proctoring?.fullscreen_required ?? true,
          tab_switch_violations_allowed: settings.interview.proctoring?.tab_switch_violations_allowed ?? 1,
          no_face_grace_seconds: settings.interview.proctoring?.no_face_grace_seconds ?? 10,
          terminate_on_violation: settings.interview.proctoring?.terminate_on_violation ?? true
        }
      });
    }
  }, [settings]);

  const handleChange = (field, value) => {
    setFormData((prev) => ({
      ...prev,
      [field]: value
    }));
  };

  const handleProctoringChange = (field, value) => {
    setFormData((prev) => ({
      ...prev,
      proctoring: {
        ...prev.proctoring,
        [field]: value
      }
    }));
  };

  const estSecondsPerQ = Math.max(
    30,
    Math.floor((formData.duration_minutes * 60) / Math.max(1, formData.question_count))
  );

  // Compute dirty state
  const originalInterview = settings?.interview || DEFAULT_INTERVIEW;
  const isDirty = JSON.stringify(formData) !== JSON.stringify(originalInterview);

  const handleSave = async () => {
    if (formData.duration_minutes < 5 || formData.duration_minutes > 120) {
      toast.error("Duration must be between 5 and 120 minutes");
      return;
    }
    if (formData.question_count < 3 || formData.question_count > 20) {
      toast.error("Question count must be between 3 and 20");
      return;
    }

    setSaving(true);
    try {
      const res = await updateSection("interview", formData);
      if (res.success) {
        toast.success("Interview settings saved successfully");
      }
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    setSaving(true);
    try {
      const res = await resetSection("interview");
      if (res.success) {
        setFormData(DEFAULT_INTERVIEW);
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <SettingsSection
      title="AI Voice Interview & Proctoring"
      description="Configure interview duration, question quota, difficulty, and automated proctoring integrity rules."
      isDirty={isDirty}
      loading={saving || loading}
      onSave={handleSave}
      onReset={handleReset}
    >
      <div className="space-y-8">
        {/* Section 1: Duration & Quotas */}
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <Clock size={18} className="text-ledger-600" />
            <h3 className="text-sm font-bold text-ink-500 uppercase tracking-wider font-display">
              Interview Duration & Question Quota
            </h3>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 bg-stone-50/70 rounded-xl border border-stone-200 space-y-2">
              <label className="text-xs font-semibold text-stone-600 block">
                Total Interview Duration (minutes)
              </label>
              <div className="flex items-center gap-3">
                <Input
                  type="number"
                  min="5"
                  max="120"
                  value={formData.duration_minutes}
                  onChange={(e) => {
                    const val = Math.max(5, Math.min(120, parseInt(e.target.value, 10) || 5));
                    handleChange("duration_minutes", val);
                  }}
                  className="font-mono text-sm font-bold"
                />
                <span className="text-xs text-stone-500 whitespace-nowrap">
                  5 - 120 mins
                </span>
              </div>
              <p className="text-[11px] text-stone-400">
                Paces each question to ~{Math.floor(estSecondsPerQ / 60)}m {estSecondsPerQ % 60}s answering time.
              </p>
            </div>

            <div className="p-4 bg-stone-50/70 rounded-xl border border-stone-200 space-y-2">
              <label className="text-xs font-semibold text-stone-600 block">
                Question Count per Interview
              </label>
              <div className="flex items-center gap-3">
                <Input
                  type="number"
                  min="3"
                  max="20"
                  value={formData.question_count}
                  onChange={(e) => {
                    const val = Math.max(3, Math.min(20, parseInt(e.target.value, 10) || 3));
                    handleChange("question_count", val);
                  }}
                  className="font-mono text-sm font-bold"
                />
                <span className="text-xs text-stone-500 whitespace-nowrap">
                  3 - 20 questions
                </span>
              </div>
              <p className="text-[11px] text-stone-400">
                Personalized questions generated for each candidate profile.
              </p>
            </div>
          </div>
        </div>

        {/* Section 2: Difficulty & Question Types */}
        <div className="space-y-4 pt-4 border-t border-stone-100">
          <div className="flex items-center gap-2">
            <Mic size={18} className="text-ledger-600" />
            <h3 className="text-sm font-bold text-ink-500 uppercase tracking-wider font-display">
              Difficulty & Question Types
            </h3>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 bg-stone-50/70 rounded-xl border border-stone-200 space-y-2">
              <label className="text-xs font-semibold text-stone-600 block">
                Default Difficulty
              </label>
              <select
                value={formData.difficulty}
                onChange={(e) => handleChange("difficulty", e.target.value)}
                className="input py-2 text-sm font-medium"
              >
                <option value="easy">Easy — Basic terminology and fundamental concepts</option>
                <option value="medium">Medium — Real-world problem solving and core skills</option>
                <option value="hard">Hard — Complex system design, edge cases, deep architecture</option>
                <option value="adaptive">Adaptive — Dynamically adjusts to candidate response strength</option>
              </select>
            </div>

            <div className="p-4 bg-stone-50/70 rounded-xl border border-stone-200 space-y-2">
              <label className="text-xs font-semibold text-stone-600 block">
                Question Types Focus
              </label>
              <select
                value={formData.question_types}
                onChange={(e) => handleChange("question_types", e.target.value)}
                className="input py-2 text-sm font-medium"
              >
                <option value="mixed">Mixed — Balanced blend of technical, behavioral, and gap-focused</option>
                <option value="technical">Technical Only — Focused exclusively on matched technical skills</option>
                <option value="behavioral">Behavioral Only — Focused on culture, leadership, and soft skills</option>
              </select>
            </div>
          </div>
        </div>

        {/* Section 3: Proctoring & Integrity */}
        <div className="space-y-4 pt-4 border-t border-stone-100">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ShieldCheck size={18} className="text-ledger-600" />
              <h3 className="text-sm font-bold text-ink-500 uppercase tracking-wider font-display">
                Automated Proctoring & Integrity Rules
              </h3>
            </div>
            <label className="flex items-center gap-2 cursor-pointer text-xs font-semibold text-ink-500">
              <input
                type="checkbox"
                checked={formData.proctoring.enabled}
                onChange={(e) => handleProctoringChange("enabled", e.target.checked)}
                className="w-4 h-4 rounded border-stone-300 text-ledger-600 focus:ring-ledger-200 cursor-pointer"
              />
              <span>Proctoring Enabled</span>
            </label>
          </div>

          <div className={`space-y-4 transition-opacity ${formData.proctoring.enabled ? "opacity-100" : "opacity-40 pointer-events-none"}`}>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-4 bg-stone-50/70 rounded-xl border border-stone-200 space-y-2">
                <label className="flex items-center gap-2 cursor-pointer text-sm font-semibold text-ink-500">
                  <input
                    type="checkbox"
                    checked={formData.proctoring.face_detection}
                    onChange={(e) => handleProctoringChange("face_detection", e.target.checked)}
                    className="w-4 h-4 rounded border-stone-300 text-ledger-600 focus:ring-ledger-200 cursor-pointer"
                  />
                  <span>Face Detection</span>
                </label>
                <p className="text-xs text-stone-500">
                  Monitors candidate camera for missing faces, multiple individuals, or cell phone presence.
                </p>
              </div>

              <div className="p-4 bg-stone-50/70 rounded-xl border border-stone-200 space-y-2">
                <label className="flex items-center gap-2 cursor-pointer text-sm font-semibold text-ink-500">
                  <input
                    type="checkbox"
                    checked={formData.proctoring.fullscreen_required}
                    onChange={(e) => handleProctoringChange("fullscreen_required", e.target.checked)}
                    className="w-4 h-4 rounded border-stone-300 text-ledger-600 focus:ring-ledger-200 cursor-pointer"
                  />
                  <span>Require Fullscreen</span>
                </label>
                <p className="text-xs text-stone-500">
                  Requires candidates to stay in fullscreen mode and registers strikes on fullscreen exit.
                </p>
              </div>

              <div className="p-4 bg-stone-50/70 rounded-xl border border-stone-200 space-y-2">
                <label className="flex items-center gap-2 cursor-pointer text-sm font-semibold text-ink-500">
                  <input
                    type="checkbox"
                    checked={formData.proctoring.terminate_on_violation}
                    onChange={(e) => handleProctoringChange("terminate_on_violation", e.target.checked)}
                    className="w-4 h-4 rounded border-stone-300 text-ledger-600 focus:ring-ledger-200 cursor-pointer"
                  />
                  <span>Terminate on Violations</span>
                </label>
                <p className="text-xs text-stone-500">
                  Automatically terminates the session when strikes exceed the allowed threshold.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
              <div className="p-4 bg-stone-50/70 rounded-xl border border-stone-200 space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-stone-600">
                    Tab Switch Violations Allowed
                  </label>
                  <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-stone-100 text-stone-700">
                    {formData.proctoring.tab_switch_violations_allowed} warning{formData.proctoring.tab_switch_violations_allowed !== 1 ? "s" : ""}
                  </span>
                </div>
                <Input
                  type="number"
                  min="0"
                  max="5"
                  value={formData.proctoring.tab_switch_violations_allowed}
                  onChange={(e) => {
                    const val = Math.max(0, Math.min(5, parseInt(e.target.value, 10) || 0));
                    handleProctoringChange("tab_switch_violations_allowed", val);
                  }}
                  className="font-mono text-sm font-bold"
                />
                <p className="text-[11px] text-stone-400">
                  {formData.proctoring.tab_switch_violations_allowed === 0
                    ? "Zero tolerance: First tab switch or window blur terminates the session immediately."
                    : `Allows ${formData.proctoring.tab_switch_violations_allowed} warning before session termination.`}
                </p>
              </div>

              <div className="p-4 bg-stone-50/70 rounded-xl border border-stone-200 space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-stone-600">
                    No-Face Grace Period (seconds)
                  </label>
                  <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-stone-100 text-stone-700">
                    {formData.proctoring.no_face_grace_seconds}s
                  </span>
                </div>
                <Input
                  type="number"
                  min="0"
                  max="60"
                  value={formData.proctoring.no_face_grace_seconds}
                  onChange={(e) => {
                    const val = Math.max(0, Math.min(60, parseInt(e.target.value, 10) || 0));
                    handleProctoringChange("no_face_grace_seconds", val);
                  }}
                  className="font-mono text-sm font-bold"
                />
                <p className="text-[11px] text-stone-400">
                  Grace period allowed before an integrity flag is recorded when candidate's face is momentarily not detected.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </SettingsSection>
  );
}
