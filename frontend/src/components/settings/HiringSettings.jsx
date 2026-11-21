import { useState, useEffect } from "react";
import SettingsSection from "./SettingsSection";
import { useSettings } from "../../context/SettingsContext";
import Input from "../ui/Input";
import { CheckCircle2, AlertTriangle, Briefcase, Sliders, ShieldAlert } from "lucide-react";
import toast from "react-hot-toast";

const DEFAULT_HIRING = {
  thresholds: {
    senior: { advance_score: 75, l2_score: 75, hr_score: 55 },
    mid:    { advance_score: 70, l2_score: 70, hr_score: 50 },
    junior: { advance_score: 65, l2_score: 65, hr_score: 45 }
  },
  scoring_weights: {
    skills: 40,
    experience: 30,
    education: 15,
    projects: 15
  },
  approval_mode: {
    auto_reject_requires_approval: false
  }
};

export default function HiringSettings() {
  const { settings, loading, updateSection, resetSection } = useSettings();
  const [formData, setFormData] = useState(DEFAULT_HIRING);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (settings?.hiring) {
      setFormData({
        thresholds: {
          senior: {
            advance_score: settings.hiring.thresholds?.senior?.advance_score ?? 75,
            l2_score: settings.hiring.thresholds?.senior?.l2_score ?? 75,
            hr_score: settings.hiring.thresholds?.senior?.hr_score ?? 55
          },
          mid: {
            advance_score: settings.hiring.thresholds?.mid?.advance_score ?? 70,
            l2_score: settings.hiring.thresholds?.mid?.l2_score ?? 70,
            hr_score: settings.hiring.thresholds?.mid?.hr_score ?? 50
          },
          junior: {
            advance_score: settings.hiring.thresholds?.junior?.advance_score ?? 65,
            l2_score: settings.hiring.thresholds?.junior?.l2_score ?? 65,
            hr_score: settings.hiring.thresholds?.junior?.hr_score ?? 45
          }
        },
        scoring_weights: {
          skills: settings.hiring.scoring_weights?.skills ?? 40,
          experience: settings.hiring.scoring_weights?.experience ?? 30,
          education: settings.hiring.scoring_weights?.education ?? 15,
          projects: settings.hiring.scoring_weights?.projects ?? 15
        },
        approval_mode: {
          auto_reject_requires_approval: Boolean(
            settings.hiring.approval_mode?.auto_reject_requires_approval
          )
        }
      });
    }
  }, [settings]);

  // Handle threshold change
  const handleThresholdChange = (level, key, value) => {
    const num = Math.max(0, Math.min(100, parseInt(value, 10) || 0));
    setFormData((prev) => {
      const updatedLevel = {
        ...prev.thresholds[level],
        [key]: num
      };
      // Keep advance_score and l2_score in sync
      if (key === "l2_score") {
        updatedLevel.advance_score = num;
      }
      return {
        ...prev,
        thresholds: {
          ...prev.thresholds,
          [level]: updatedLevel
        }
      };
    });
  };

  // Handle weight change
  const handleWeightChange = (key, value) => {
    const num = Math.max(0, Math.min(100, parseInt(value, 10) || 0));
    setFormData((prev) => ({
      ...prev,
      scoring_weights: {
        ...prev.scoring_weights,
        [key]: num
      }
    }));
  };

  // Handle approval mode toggle
  const handleApprovalToggle = (checked) => {
    setFormData((prev) => ({
      ...prev,
      approval_mode: {
        ...prev.approval_mode,
        auto_reject_requires_approval: checked
      }
    }));
  };

  // Calculations & Validations
  const totalWeight =
    (formData.scoring_weights.skills || 0) +
    (formData.scoring_weights.experience || 0) +
    (formData.scoring_weights.education || 0) +
    (formData.scoring_weights.projects || 0);

  const isWeightValid = totalWeight === 100;

  const thresholdErrors = [];
  ["senior", "mid", "junior"].forEach((lvl) => {
    const l2 = formData.thresholds[lvl]?.l2_score;
    const hr = formData.thresholds[lvl]?.hr_score;
    if (l2 < hr) {
      thresholdErrors.push(
        `${lvl.charAt(0).toUpperCase() + lvl.slice(1)} role: L2 score (${l2}) cannot be lower than HR score (${hr})`
      );
    }
  });

  const isThresholdValid = thresholdErrors.length === 0;

  // Compute dirty state
  const originalHiring = settings?.hiring || DEFAULT_HIRING;
  const isDirty = JSON.stringify(formData) !== JSON.stringify(originalHiring);

  const handleSave = async () => {
    if (!isWeightValid) {
      toast.error(`Scoring weights must sum to 100% (currently ${totalWeight}%)`);
      return;
    }
    if (!isThresholdValid) {
      toast.error(thresholdErrors[0]);
      return;
    }

    setSaving(true);
    try {
      const res = await updateSection("hiring", formData);
      if (res.success) {
        toast.success("Hiring rules updated successfully");
      }
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    setSaving(true);
    try {
      const res = await resetSection("hiring");
      if (res.success) {
        setFormData(DEFAULT_HIRING);
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <SettingsSection
      title="Hiring Rules & Decision Engine"
      description="Configure interview score thresholds, resume scoring weights, and rejection review workflows."
      isDirty={isDirty}
      loading={saving || loading}
      onSave={handleSave}
      onReset={handleReset}
    >
      <div className="space-y-8">
        {/* Section 1: Role Thresholds */}
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <Sliders size={18} className="text-ledger-600" />
            <h3 className="text-sm font-bold text-ink-500 uppercase tracking-wider font-display">
              Interview Passing Thresholds
            </h3>
          </div>
          <p className="text-xs text-stone-500">
            Candidates scoring at or above the L2 threshold advance to the technical round.
            Candidates scoring at or above the HR threshold advance to the HR round.
            L2 threshold must be greater than or equal to the HR threshold.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[
              { key: "senior", label: "Senior Roles", desc: "5+ years experience" },
              { key: "mid",    label: "Mid-Level Roles", desc: "2-5 years experience" },
              { key: "junior", label: "Junior Roles", desc: "0-2 years experience" }
            ].map(({ key, label, desc }) => {
              const lvl = formData.thresholds[key] || {};
              const hasOrderError = lvl.l2_score < lvl.hr_score;
              return (
                <div
                  key={key}
                  className={`p-4 rounded-xl border transition-all ${
                    hasOrderError
                      ? "border-brick-300 bg-brick-50/50"
                      : "border-stone-200 bg-stone-50/60"
                  }`}
                >
                  <div className="mb-3">
                    <p className="font-semibold text-sm text-ink-500">{label}</p>
                    <p className="text-xs text-stone-400">{desc}</p>
                  </div>

                  <div className="space-y-3">
                    <div>
                      <label className="text-xs font-medium text-stone-600 block mb-1">
                        L2 Technical Round (min score)
                      </label>
                      <Input
                        type="number"
                        min="0"
                        max="100"
                        value={lvl.l2_score}
                        onChange={(e) => handleThresholdChange(key, "l2_score", e.target.value)}
                        className="text-sm font-mono font-bold"
                      />
                    </div>

                    <div>
                      <label className="text-xs font-medium text-stone-600 block mb-1">
                        HR Round (min score)
                      </label>
                      <Input
                        type="number"
                        min="0"
                        max="100"
                        value={lvl.hr_score}
                        onChange={(e) => handleThresholdChange(key, "hr_score", e.target.value)}
                        className="text-sm font-mono font-bold"
                      />
                    </div>

                    {hasOrderError && (
                      <p className="text-xs text-brick-600 font-medium">
                        L2 score ({lvl.l2_score}) must be ≥ HR score ({lvl.hr_score})
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Section 2: Resume Screener Scoring Weights */}
        <div className="space-y-4 pt-4 border-t border-stone-100">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-2">
              <Briefcase size={18} className="text-ledger-600" />
              <h3 className="text-sm font-bold text-ink-500 uppercase tracking-wider font-display">
                Resume Screening Weights
              </h3>
            </div>

            <div
              className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold ${
                isWeightValid
                  ? "bg-verified-50 text-verified-700 border border-verified-200"
                  : "bg-brick-50 text-brick-700 border border-brick-200"
              }`}
            >
              {isWeightValid ? (
                <>
                  <CheckCircle2 size={13} />
                  <span>Total: 100% / 100%</span>
                </>
              ) : (
                <>
                  <AlertTriangle size={13} />
                  <span>Total: {totalWeight}% / 100% (Must equal 100%)</span>
                </>
              )}
            </div>
          </div>
          <p className="text-xs text-stone-500">
            Define how the AI resume screener weighs different dimensions when calculating candidate match scores. Individual weights must sum to 100%.
          </p>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { key: "skills",     label: "Skills Match" },
              { key: "experience", label: "Experience" },
              { key: "education",  label: "Education" },
              { key: "projects",   label: "Projects & Portfolio" }
            ].map(({ key, label }) => (
              <div key={key} className="p-4 bg-stone-50/60 rounded-xl border border-stone-200">
                <label className="text-xs font-semibold text-stone-600 block mb-1">
                  {label}
                </label>
                <div className="relative">
                  <Input
                    type="number"
                    min="0"
                    max="100"
                    value={formData.scoring_weights[key]}
                    onChange={(e) => handleWeightChange(key, e.target.value)}
                    className="font-mono text-sm font-bold pr-8"
                  />
                  <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs font-bold text-stone-400">
                    %
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Section 3: Approval Mode */}
        <div className="space-y-4 pt-4 border-t border-stone-100">
          <div className="flex items-center gap-2">
            <ShieldAlert size={18} className="text-ledger-600" />
            <h3 className="text-sm font-bold text-ink-500 uppercase tracking-wider font-display">
              Rejection Approval Mode
            </h3>
          </div>

          <div className="p-4 bg-stone-50/70 rounded-xl border border-stone-200 flex items-start gap-4">
            <input
              id="auto_reject_approval"
              type="checkbox"
              checked={formData.approval_mode.auto_reject_requires_approval}
              onChange={(e) => handleApprovalToggle(e.target.checked)}
              className="mt-1 w-4 h-4 rounded border-stone-300 text-ledger-600 focus:ring-ledger-200 cursor-pointer"
            />
            <label htmlFor="auto_reject_approval" className="cursor-pointer space-y-1">
              <span className="text-sm font-semibold text-ink-500 block">
                Require recruiter approval for automated rejections
              </span>
              <span className="text-xs text-stone-500 block leading-relaxed">
                When enabled, candidates who fail resume screening or interview score thresholds will NOT be immediately auto-rejected or emailed.
                Instead, they will enter a <span className="font-semibold text-stone-700">Needs Review</span> status with a recommended rejection reason, allowing your team to manually review and approve or override the decision.
              </span>
            </label>
          </div>
        </div>
      </div>
    </SettingsSection>
  );
}
