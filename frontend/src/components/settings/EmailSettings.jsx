import { useState, useEffect, useRef } from "react";
import SettingsSection from "./SettingsSection";
import { useSettings } from "../../context/SettingsContext";
import { settingsAPI } from "../../api/settings";
import {
  Mail,
  Send,
  Eye,
  CheckCircle2,
  Bell,
  X,
  Code2,
  Sparkles,
  HelpCircle
} from "lucide-react";
import toast from "react-hot-toast";

const DEFAULT_EMAIL = {
  sender_name: "RecruitMate AI",
  reply_to: "",
  templates: {
    interview_invite: {
      subject: "Interview Invitation: {job_title} at {company_name}",
      body:
        "Dear {candidate_name},\n\nYou have been shortlisted for an AI voice interview for the {job_title} role at {company_name}.\n\nPlease complete your interview by clicking your personal interview link.\n\nBest regards,\n{company_name} Team"
    },
    shortlist: {
      subject: "Application Update: {job_title} at {company_name}",
      body:
        "Dear {candidate_name},\n\nCongratulations! You have been advanced to the next round ({next_step}) for the {job_title} role at {company_name}.\n\nScheduled Time: {date}\n\nBest regards,\n{company_name} Team"
    },
    rejection: {
      subject: "Application Status: {job_title} at {company_name}",
      body:
        "Dear {candidate_name},\n\nThank you for taking the time to interview for the {job_title} position at {company_name}. After careful review, we have decided not to move forward with your application at this time.\n\nWe wish you all the best in your job search.\n\nBest regards,\n{company_name} Team"
    },
    otp_footer: "This code expires in 5 minutes. Do not share it with anyone."
  },
  notifications: {
    notify_on_new_candidate: true,
    notify_on_interview_complete: true,
    notify_on_pending_review: true,
    daily_digest: false
  }
};

const TEMPLATE_KEYS = [
  { id: "interview_invite", label: "Interview Invitation" },
  { id: "shortlist", label: "Shortlist Update" },
  { id: "rejection", label: "Rejection Notice" },
  { id: "otp_footer", label: "Verification Code" }
];

const ALLOWED_VARS = [
  { tag: "{candidate_name}", desc: "Candidate's full name" },
  { tag: "{job_title}", desc: "Applied position title" },
  { tag: "{company_name}", desc: "Your company name" },
  { tag: "{next_step}", desc: "Next hiring stage name" },
  { tag: "{date}", desc: "Scheduled interview date/time" }
];

export default function EmailSettings() {
  const { settings, updateSection, resetSection } = useSettings();
  const [formData, setFormData] = useState(DEFAULT_EMAIL);
  const [activeTemplateTab, setActiveTemplateTab] = useState("interview_invite");
  const [saving, setSaving] = useState(false);
  const [sendingTest, setSendingTest] = useState(false);

  // Preview modal state
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewData, setPreviewData] = useState(null);

  const bodyInputRef = useRef(null);

  useEffect(() => {
    if (settings?.email) {
      setFormData({
        sender_name: settings.email.sender_name ?? DEFAULT_EMAIL.sender_name,
        reply_to: settings.email.reply_to ?? "",
        templates: {
          interview_invite: {
            subject:
              settings.email.templates?.interview_invite?.subject ??
              DEFAULT_EMAIL.templates.interview_invite.subject,
            body:
              settings.email.templates?.interview_invite?.body ??
              DEFAULT_EMAIL.templates.interview_invite.body
          },
          shortlist: {
            subject:
              settings.email.templates?.shortlist?.subject ??
              DEFAULT_EMAIL.templates.shortlist.subject,
            body:
              settings.email.templates?.shortlist?.body ??
              DEFAULT_EMAIL.templates.shortlist.body
          },
          rejection: {
            subject:
              settings.email.templates?.rejection?.subject ??
              DEFAULT_EMAIL.templates.rejection.subject,
            body:
              settings.email.templates?.rejection?.body ??
              DEFAULT_EMAIL.templates.rejection.body
          },
          otp_footer:
            settings.email.templates?.otp_footer ??
            DEFAULT_EMAIL.templates.otp_footer
        },
        notifications: {
          notify_on_new_candidate:
            settings.email.notifications?.notify_on_new_candidate ?? true,
          notify_on_interview_complete:
            settings.email.notifications?.notify_on_interview_complete ?? true,
          notify_on_pending_review:
            settings.email.notifications?.notify_on_pending_review ?? true,
          daily_digest:
            settings.email.notifications?.daily_digest ?? false
        }
      });
    }
  }, [settings]);

  // Compute dirty state
  const originalEmail = settings?.email || DEFAULT_EMAIL;
  const isDirty = JSON.stringify(formData) !== JSON.stringify(originalEmail);

  const handleSenderChange = (field, value) => {
    setFormData((prev) => ({
      ...prev,
      [field]: value
    }));
  };

  const handleTemplateChange = (templateKey, field, value) => {
    setFormData((prev) => {
      if (templateKey === "otp_footer") {
        return {
          ...prev,
          templates: {
            ...prev.templates,
            otp_footer: value
          }
        };
      }
      return {
        ...prev,
        templates: {
          ...prev.templates,
          [templateKey]: {
            ...prev.templates[templateKey],
            [field]: value
          }
        }
      };
    });
  };

  const handleNotificationToggle = (field) => {
    setFormData((prev) => ({
      ...prev,
      notifications: {
        ...prev.notifications,
        [field]: !prev.notifications[field]
      }
    }));
  };

  const insertVariable = (varTag) => {
    if (activeTemplateTab === "otp_footer") {
      const current = formData.templates.otp_footer || "";
      handleTemplateChange("otp_footer", null, current + " " + varTag);
      return;
    }

    const currentTemplate = formData.templates[activeTemplateTab];
    const currentBody = currentTemplate.body || "";

    if (bodyInputRef.current) {
      const start = bodyInputRef.current.selectionStart;
      const end = bodyInputRef.current.selectionEnd;
      const newBody =
        currentBody.substring(0, start) + varTag + currentBody.substring(end);
      handleTemplateChange(activeTemplateTab, "body", newBody);
      setTimeout(() => {
        if (bodyInputRef.current) {
          bodyInputRef.current.focus();
          bodyInputRef.current.setSelectionRange(
            start + varTag.length,
            start + varTag.length
          );
        }
      }, 0);
    } else {
      handleTemplateChange(activeTemplateTab, "body", currentBody + " " + varTag);
    }
  };

  const handleOpenPreview = async () => {
    setPreviewLoading(true);
    setPreviewOpen(true);
    try {
      const reqPayload = {
        template_type: activeTemplateTab
      };
      if (activeTemplateTab === "otp_footer") {
        reqPayload.body = formData.templates.otp_footer;
      } else {
        reqPayload.subject = formData.templates[activeTemplateTab].subject;
        reqPayload.body = formData.templates[activeTemplateTab].body;
      }

      const res = await settingsAPI.previewEmail(reqPayload);
      if (res.data?.success) {
        setPreviewData(res.data.preview);
      } else {
        toast.error(res.data?.error || "Failed to generate preview");
        setPreviewOpen(false);
      }
    } catch (err) {
      toast.error(err.response?.data?.error || "Error generating preview");
      setPreviewOpen(false);
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleSendTestEmail = async () => {
    setSendingTest(true);
    try {
      const reqPayload = {
        template_type: activeTemplateTab
      };
      if (activeTemplateTab === "otp_footer") {
        reqPayload.body = formData.templates.otp_footer;
      } else {
        reqPayload.subject = formData.templates[activeTemplateTab].subject;
        reqPayload.body = formData.templates[activeTemplateTab].body;
      }

      const res = await settingsAPI.sendTestEmail(reqPayload);
      if (res.data?.success) {
        toast.success(res.data.message || "Test email sent successfully!");
      } else {
        toast.error(res.data?.error || "Failed to send test email");
      }
    } catch (err) {
      const errMsg = err.response?.data?.error || "Error sending test email";
      toast.error(errMsg);
    } finally {
      setSendingTest(false);
    }
  };

  const handleSave = async () => {
    // Validation
    if (!formData.sender_name || formData.sender_name.trim().length === 0) {
      toast.error("Sender name cannot be empty");
      return;
    }
    if (formData.sender_name.length > 100) {
      toast.error("Sender name must be under 100 characters");
      return;
    }

    if (
      formData.reply_to &&
      !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(formData.reply_to.trim())
    ) {
      toast.error("Reply-to must be a valid email address");
      return;
    }

    for (const key of ["interview_invite", "shortlist", "rejection"]) {
      const tmpl = formData.templates[key];
      if (!tmpl.subject || tmpl.subject.trim().length === 0) {
        toast.error(`Subject for ${key} cannot be empty`);
        return;
      }
      if (tmpl.subject.length > 150) {
        toast.error(`Subject for ${key} cannot exceed 150 characters`);
        return;
      }
      if (!tmpl.body || tmpl.body.trim().length === 0) {
        toast.error(`Body for ${key} cannot be empty`);
        return;
      }
      if (tmpl.body.length > 5000) {
        toast.error(`Body for ${key} cannot exceed 5000 characters`);
        return;
      }
    }

    if (formData.templates.otp_footer?.length > 500) {
      toast.error("Verification footer cannot exceed 500 characters");
      return;
    }

    setSaving(true);
    try {
      const res = await updateSection("email", formData);
      if (res.success) {
        toast.success("Email settings saved successfully");
      }
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    setSaving(true);
    try {
      const res = await resetSection("email");
      if (res.success) {
        setFormData(DEFAULT_EMAIL);
      }
    } finally {
      setSaving(false);
    }
  };

  const activeTemplate = formData.templates[activeTemplateTab];

  return (
    <div className="space-y-6">
      <SettingsSection
        title="Email Settings & Templates"
        description="Configure your organization's sender profile, candidate notification templates, and automated team alerts."
      >
        <div className="space-y-8">
          {/* SECTION 1: Sender Profile */}
          <div className="border border-stone-200/80 rounded-xl p-5 bg-stone-50/50 space-y-4">
            <div className="flex items-center gap-2 text-ink-500 font-semibold text-sm">
              <Mail size={16} className="text-ledger-600" />
              <span>Sender Profile</span>
            </div>
            <p className="text-xs text-stone-500">
              Candidate emails are dispatched using your verified sending domain with your chosen sender identity.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
              <div>
                <label className="block text-xs font-medium text-ink-400 mb-1">
                  Sender Display Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={formData.sender_name}
                  onChange={(e) => handleSenderChange("sender_name", e.target.value)}
                  maxLength={100}
                  className="w-full text-sm border border-stone-200 rounded-lg px-3 py-2 bg-white text-ink-500 focus:outline-none focus:ring-1 focus:ring-ledger-500"
                  placeholder="e.g. Acme Corp Talent Team"
                />
                <span className="text-[11px] text-stone-400 mt-1 block">
                  {formData.sender_name.length} / 100 characters
                </span>
              </div>

              <div>
                <label className="block text-xs font-medium text-ink-400 mb-1">
                  Reply-To Email Address (Optional)
                </label>
                <input
                  type="email"
                  value={formData.reply_to}
                  onChange={(e) => handleSenderChange("reply_to", e.target.value)}
                  className="w-full text-sm border border-stone-200 rounded-lg px-3 py-2 bg-white text-ink-500 focus:outline-none focus:ring-1 focus:ring-ledger-500"
                  placeholder="e.g. careers@company.com"
                />
                <span className="text-[11px] text-stone-400 mt-1 block">
                  Replies from candidates will be routed to this address
                </span>
              </div>
            </div>
          </div>

          {/* SECTION 2: Email Templates */}
          <div className="space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <h4 className="text-sm font-semibold text-ink-500">
                  Candidate Email Templates
                </h4>
                <p className="text-xs text-stone-500 mt-0.5">
                  Customize the automated messages sent to applicants at key hiring milestones.
                </p>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleOpenPreview}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-stone-200 bg-white text-stone-700 hover:bg-stone-50 transition-colors shadow-sm"
                >
                  <Eye size={13} className="text-stone-500" />
                  <span>Preview</span>
                </button>
                <button
                  type="button"
                  onClick={handleSendTestEmail}
                  disabled={sendingTest}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-ledger-200 bg-ledger-50 text-ledger-700 hover:bg-ledger-100 transition-colors shadow-sm disabled:opacity-50"
                >
                  <Send size={13} className="text-ledger-600" />
                  <span>{sendingTest ? "Sending..." : "Send Test to Me"}</span>
                </button>
              </div>
            </div>

            {/* Template Navigation Tabs */}
            <div className="flex items-center gap-1 border-b border-stone-200 pb-px">
              {TEMPLATE_KEYS.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setActiveTemplateTab(tab.id)}
                  className={`px-3.5 py-2 text-xs font-medium rounded-t-lg transition-all ${
                    activeTemplateTab === tab.id
                      ? "border-b-2 border-ledger-600 text-ledger-700 bg-ledger-50/40 font-semibold"
                      : "text-stone-600 hover:text-ink-500 hover:bg-stone-50"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Variable Pills / Cheat Sheet */}
            <div className="bg-stone-50/70 border border-stone-200/70 rounded-lg p-3 space-y-2">
              <div className="flex items-center justify-between text-xs text-stone-600 font-medium">
                <span className="flex items-center gap-1">
                  <Code2 size={13} className="text-ledger-600" />
                  Dynamic Placeholders (Click to insert):
                </span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {ALLOWED_VARS.map((v) => (
                  <button
                    key={v.tag}
                    type="button"
                    onClick={() => insertVariable(v.tag)}
                    title={v.desc}
                    className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-mono font-medium rounded-md bg-white border border-stone-200 text-ink-500 hover:border-ledger-400 hover:text-ledger-700 transition-colors shadow-2xs"
                  >
                    <span>{v.tag}</span>
                    <span className="text-[10px] text-stone-400 font-sans">
                      ({v.desc.split(" ")[0]})
                    </span>
                  </button>
                ))}
              </div>
            </div>

            {/* Active Template Editor */}
            {activeTemplateTab === "otp_footer" ? (
              <div className="space-y-4 pt-2">
                <div className="bg-blue-50/60 border border-blue-100 rounded-lg p-3 text-xs text-blue-800 flex items-start gap-2">
                  <HelpCircle size={15} className="text-blue-500 mt-0.5 shrink-0" />
                  <p>
                    For account security, the 6-digit verification code block and layout cannot be altered. You can customize the explanatory footer note displayed below the code.
                  </p>
                </div>

                <div>
                  <label className="block text-xs font-medium text-ink-400 mb-1">
                    Verification Code Footer Notice
                  </label>
                  <textarea
                    rows={3}
                    value={formData.templates.otp_footer}
                    onChange={(e) =>
                      handleTemplateChange("otp_footer", null, e.target.value)
                    }
                    maxLength={500}
                    className="w-full text-sm border border-stone-200 rounded-lg p-3 bg-white text-ink-500 font-sans focus:outline-none focus:ring-1 focus:ring-ledger-500"
                    placeholder="This code expires in 5 minutes. Do not share it with anyone."
                  />
                  <div className="flex justify-between items-center text-[11px] text-stone-400 mt-1">
                    <span>Appears directly below the verification code block.</span>
                    <span>
                      {(formData.templates.otp_footer || "").length} / 500
                    </span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="space-y-4 pt-2">
                <div>
                  <div className="flex justify-between items-center mb-1">
                    <label className="text-xs font-medium text-ink-400">
                      Subject Line <span className="text-red-500">*</span>
                    </label>
                    <span className="text-[11px] text-stone-400">
                      {(activeTemplate?.subject || "").length} / 150
                    </span>
                  </div>
                  <input
                    type="text"
                    value={activeTemplate?.subject || ""}
                    onChange={(e) =>
                      handleTemplateChange(activeTemplateTab, "subject", e.target.value)
                    }
                    maxLength={150}
                    className="w-full text-sm border border-stone-200 rounded-lg px-3 py-2 bg-white text-ink-500 focus:outline-none focus:ring-1 focus:ring-ledger-500"
                    placeholder="Enter email subject line"
                  />
                </div>

                <div>
                  <div className="flex justify-between items-center mb-1">
                    <label className="text-xs font-medium text-ink-400">
                      Email Body Content <span className="text-red-500">*</span>
                    </label>
                    <span className="text-[11px] text-stone-400">
                      {(activeTemplate?.body || "").length} / 5000
                    </span>
                  </div>
                  <textarea
                    ref={bodyInputRef}
                    rows={7}
                    value={activeTemplate?.body || ""}
                    onChange={(e) =>
                      handleTemplateChange(activeTemplateTab, "body", e.target.value)
                    }
                    maxLength={5000}
                    className="w-full text-sm border border-stone-200 rounded-lg p-3 bg-white text-ink-500 font-sans focus:outline-none focus:ring-1 focus:ring-ledger-500 leading-relaxed"
                    placeholder="Write candidate email body content here..."
                  />
                </div>
              </div>
            )}
          </div>

          {/* SECTION 3: Notification Alerts */}
          <div className="border-t border-stone-200 pt-6 space-y-4">
            <div className="flex items-center gap-2 text-ink-500 font-semibold text-sm">
              <Bell size={16} className="text-ledger-600" />
              <span>Automated Owner Notifications</span>
            </div>
            <p className="text-xs text-stone-500">
              Select which candidate events immediately trigger automated email notifications to your team.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
              {/* Toggle 1: New Candidate */}
              <div
                onClick={() => handleNotificationToggle("notify_on_new_candidate")}
                className="flex items-center justify-between p-3.5 rounded-xl border border-stone-200 bg-white hover:bg-stone-50 cursor-pointer transition-colors"
              >
                <div className="space-y-0.5 pr-2">
                  <div className="text-xs font-semibold text-ink-500">
                    New Candidate Intake
                  </div>
                  <div className="text-[11px] text-stone-500">
                    Alert when a candidate submits their resume & finishes screening.
                  </div>
                </div>
                <input
                  type="checkbox"
                  checked={formData.notifications.notify_on_new_candidate}
                  onChange={() => {}}
                  className="rounded text-ledger-600 focus:ring-ledger-500 h-4 w-4 shrink-0"
                />
              </div>

              {/* Toggle 2: Interview Complete */}
              <div
                onClick={() => handleNotificationToggle("notify_on_interview_complete")}
                className="flex items-center justify-between p-3.5 rounded-xl border border-stone-200 bg-white hover:bg-stone-50 cursor-pointer transition-colors"
              >
                <div className="space-y-0.5 pr-2">
                  <div className="text-xs font-semibold text-ink-500">
                    Interview Completed
                  </div>
                  <div className="text-[11px] text-stone-500">
                    Alert when an AI voice interview session is completed.
                  </div>
                </div>
                <input
                  type="checkbox"
                  checked={formData.notifications.notify_on_interview_complete}
                  onChange={() => {}}
                  className="rounded text-ledger-600 focus:ring-ledger-500 h-4 w-4 shrink-0"
                />
              </div>

              {/* Toggle 3: Pending Review */}
              <div
                onClick={() => handleNotificationToggle("notify_on_pending_review")}
                className="flex items-center justify-between p-3.5 rounded-xl border border-stone-200 bg-white hover:bg-stone-50 cursor-pointer transition-colors"
              >
                <div className="space-y-0.5 pr-2">
                  <div className="text-xs font-semibold text-ink-500">
                    Action Required: Review Flagged
                  </div>
                  <div className="text-[11px] text-stone-500">
                    Alert when a candidate requires human approval before rejection.
                  </div>
                </div>
                <input
                  type="checkbox"
                  checked={formData.notifications.notify_on_pending_review}
                  onChange={() => {}}
                  className="rounded text-ledger-600 focus:ring-ledger-500 h-4 w-4 shrink-0"
                />
              </div>

              {/* Toggle 4: Daily Digest */}
              <div
                onClick={() => handleNotificationToggle("daily_digest")}
                className="flex items-center justify-between p-3.5 rounded-xl border border-stone-200 bg-white hover:bg-stone-50 cursor-pointer transition-colors"
              >
                <div className="space-y-0.5 pr-2">
                  <div className="text-xs font-semibold text-ink-500">
                    Daily Hiring Summary
                  </div>
                  <div className="text-[11px] text-stone-500">
                    Morning summary email of active candidates and upcoming rounds.
                    <span className="block text-[10px] text-stone-400 mt-0.5">
                      (Activates when background scheduled digest is enabled)
                    </span>
                  </div>
                </div>
                <input
                  type="checkbox"
                  checked={formData.notifications.daily_digest}
                  onChange={() => {}}
                  className="rounded text-ledger-600 focus:ring-ledger-500 h-4 w-4 shrink-0"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Action Controls */}
        <div className="mt-8 pt-5 border-t border-stone-200 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            {isDirty ? (
              <span className="text-xs font-medium text-amber-600 bg-amber-50 border border-amber-200 px-2.5 py-1 rounded-md">
                Unsaved changes
              </span>
            ) : (
              <span className="text-xs text-stone-400 flex items-center gap-1">
                <CheckCircle2 size={13} className="text-emerald-500" />
                All changes saved
              </span>
            )}
          </div>

          <div className="flex items-center gap-3 w-full sm:w-auto justify-end">
            <button
              type="button"
              onClick={handleReset}
              disabled={saving}
              className="px-4 py-2 text-xs font-medium rounded-lg border border-stone-200 bg-white text-stone-600 hover:bg-stone-50 transition-colors shadow-2xs disabled:opacity-50"
            >
              Reset to Defaults
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={saving || !isDirty}
              className="px-5 py-2 text-xs font-semibold rounded-lg bg-ledger-600 text-white hover:bg-ledger-700 transition-colors shadow-sm disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save Changes"}
            </button>
          </div>
        </div>
      </SettingsSection>

      {/* Live Preview Modal */}
      {previewOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-ink-950/40 backdrop-blur-xs">
          <div className="bg-white rounded-2xl max-w-2xl w-full max-h-[85vh] flex flex-col shadow-2xl border border-stone-200 overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-stone-100 bg-stone-50/70">
              <div className="flex items-center gap-2">
                <Sparkles size={16} className="text-ledger-600" />
                <h3 className="text-sm font-bold text-ink-500">
                  Email Preview:{" "}
                  {TEMPLATE_KEYS.find((k) => k.id === activeTemplateTab)?.label}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setPreviewOpen(false)}
                className="text-stone-400 hover:text-stone-600 p-1 rounded-md hover:bg-stone-100 transition-colors"
              >
                <X size={16} />
              </button>
            </div>

            {/* Content */}
            <div className="p-6 overflow-y-auto space-y-4">
              {previewLoading ? (
                <div className="py-16 text-center text-stone-500 text-sm">
                  Rendering preview with sample data...
                </div>
              ) : previewData ? (
                <div className="space-y-4">
                  <div className="bg-stone-50 border border-stone-200 rounded-lg p-3 space-y-1 text-xs">
                    <div>
                      <span className="font-semibold text-ink-400">From: </span>
                      <span className="text-ink-500">
                        {formData.sender_name} &lt;noreply@recruitmate.ai&gt;
                      </span>
                    </div>
                    {formData.reply_to && (
                      <div>
                        <span className="font-semibold text-ink-400">Reply-To: </span>
                        <span className="text-ink-500">{formData.reply_to}</span>
                      </div>
                    )}
                    <div>
                      <span className="font-semibold text-ink-400">Subject: </span>
                      <span className="text-ink-500 font-medium">
                        {previewData.subject}
                      </span>
                    </div>
                  </div>

                  <div className="border border-stone-200 rounded-xl overflow-hidden bg-stone-50/30 p-2">
                    <div
                      dangerouslySetInnerHTML={{ __html: previewData.html }}
                      className="preview-email-html"
                    />
                  </div>
                </div>
              ) : (
                <div className="py-12 text-center text-stone-500 text-sm">
                  No preview available.
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="px-6 py-3 border-t border-stone-100 bg-stone-50 flex justify-end">
              <button
                type="button"
                onClick={() => setPreviewOpen(false)}
                className="px-4 py-2 text-xs font-semibold rounded-lg bg-stone-200 text-stone-700 hover:bg-stone-300 transition-colors"
              >
                Close Preview
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
