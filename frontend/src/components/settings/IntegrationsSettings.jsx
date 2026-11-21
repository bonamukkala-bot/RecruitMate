import { useState, useEffect } from "react";
import SettingsSection from "./SettingsSection";
import { useSettings } from "../../context/SettingsContext";
import useRole from "../../hooks/useRole";
import { settingsAPI } from "../../api/settings";
import Input from "../ui/Input";
import Button from "../ui/Button";
import Modal from "../ui/Modal";
import {
  Webhook, Send, Plus, Trash2, Key,
  Copy, Calendar, Video, Activity, AlertCircle
} from "lucide-react";
import toast from "react-hot-toast";

const DEFAULT_INTEGRATIONS = {
  slack_webhook_url: "",
  slack_events: {
    new_candidate: false,
    interview_complete: false,
    pending_review: false
  },
  webhook_url: "",
  webhook_events: [],
  google_calendar_enabled: false
};

const WEBHOOK_EVENT_OPTIONS = [
  { id: "candidate.created", label: "Candidate Created", description: "Fired when a new candidate application is submitted or screened" },
  { id: "interview.completed", label: "Interview Completed", description: "Fired when a voice interview finishes and evaluation is computed" },
  { id: "candidate.pending_review", label: "Pending Review", description: "Fired when a candidate auto-rejection requires approval" }
];

export default function IntegrationsSettings() {
  const { settings, loading, updateSection, resetSection } = useSettings();
  const { isAdmin } = useRole();
  const [formData, setFormData] = useState(DEFAULT_INTEGRATIONS);
  const [savedIntegrations, setSavedIntegrations] = useState(DEFAULT_INTEGRATIONS);
  const [saving, setSaving] = useState(false);

  // ── Slack State ────────────────────────────────────────────────────────────
  const [testingSlack, setTestingSlack] = useState(false);

  // ── Webhooks State ─────────────────────────────────────────────────────────
  const [webhooks, setWebhooks] = useState([]);
  const [loadingWebhooks, setLoadingWebhooks] = useState(false);
  const [webhookModalOpen, setWebhookModalOpen] = useState(false);
  const [webhookUrl, setWebhookUrl] = useState("");
  const [selectedEvents, setSelectedEvents] = useState(["candidate.created", "interview.completed"]);
  const [creatingWebhook, setCreatingWebhook] = useState(false);
  const [newWebhookSecret, setNewWebhookSecret] = useState(null);

  // ── Webhook Deliveries State ───────────────────────────────────────────────
  const [deliveriesModalOpen, setDeliveriesModalOpen] = useState(false);
  const [deliveries, setDeliveries] = useState([]);
  const [loadingDeliveries, setLoadingDeliveries] = useState(false);

  // ── API Keys State ─────────────────────────────────────────────────────────
  const [apiKeys, setApiKeys] = useState([]);
  const [loadingKeys, setLoadingKeys] = useState(false);
  const [apiKeyModalOpen, setApiKeyModalOpen] = useState(false);
  const [keyName, setKeyName] = useState("");
  const [keyScopes, setKeyScopes] = useState(["read:candidates", "write:jobs"]);
  const [keyExpiryDays, setKeyExpiryDays] = useState(90);
  const [creatingKey, setCreatingKey] = useState(false);
  const [generatedRawKey, setGeneratedRawKey] = useState(null);
  const [keyNameError, setKeyNameError] = useState("");
  const [keyScopeError, setKeyScopeError] = useState("");

  // ── Google Calendar State ──────────────────────────────────────────────────
  const [googleStatus, setGoogleStatus] = useState({ enabled: false, connected: false, calendar_email: "" });

  useEffect(() => {
    if (settings?.integrations) {
      const initial = {
        slack_webhook_url: settings.integrations.slack_webhook_url ?? "",
        slack_events: {
          new_candidate: Boolean(settings.integrations.slack_events?.new_candidate),
          interview_complete: Boolean(settings.integrations.slack_events?.interview_complete),
          pending_review: Boolean(settings.integrations.slack_events?.pending_review)
        },
        webhook_url: settings.integrations.webhook_url ?? "",
        webhook_events: settings.integrations.webhook_events ?? [],
        google_calendar_enabled: Boolean(settings.integrations.google_calendar_enabled)
      };
      setFormData(initial);
      setSavedIntegrations(initial);
    }
  }, [settings]);

  // Load external resources
  useEffect(() => {
    fetchWebhooks();
    fetchApiKeys();
    fetchGoogleStatus();
  }, []);

  const fetchWebhooks = async () => {
    setLoadingWebhooks(true);
    try {
      const res = await settingsAPI.getWebhooks();
      if (res.data?.success) setWebhooks(res.data.webhooks);
    } catch {
      // quiet fallback
    } finally {
      setLoadingWebhooks(false);
    }
  };

  const fetchApiKeys = async () => {
    setLoadingKeys(true);
    try {
      const res = await settingsAPI.getApiKeys();
      if (res.data?.success) setApiKeys(res.data.api_keys);
    } catch {
      // quiet fallback
    } finally {
      setLoadingKeys(false);
    }
  };

  const fetchGoogleStatus = async () => {
    try {
      const res = await settingsAPI.getGoogleStatus();
      if (res.data?.success) setGoogleStatus(res.data);
    } catch {
      // quiet fallback
    }
  };

  const isDirty = JSON.stringify(formData) !== JSON.stringify(savedIntegrations);

  // Slack URL validation
  const slackUrl = (formData.slack_webhook_url || "").trim();
  const isSlackUrlValid = !slackUrl || slackUrl.startsWith("https://hooks.slack.com/") || slackUrl.includes("...");
  const slackUrlError = !isSlackUrlValid ? "Slack webhook URL must start with 'https://hooks.slack.com/'" : undefined;

  const handleSlackEventToggle = (eventKey) => {
    setFormData((prev) => ({
      ...prev,
      slack_events: {
        ...prev.slack_events,
        [eventKey]: !prev.slack_events[eventKey]
      }
    }));
  };

  const handleSave = async (e) => {
    if (e) e.preventDefault();
    if (!isAdmin) {
      toast.error("Only administrators can update integration settings");
      return;
    }
    if (slackUrlError) {
      toast.error(slackUrlError);
      return;
    }

    setSaving(true);
    try {
      const res = await updateSection("integrations", formData);
      if (res.success) {
        setSavedIntegrations(formData);
      }
    } catch (err) {
      toast.error(err.response?.data?.error || "Failed to save integrations");
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    if (!isAdmin) return;
    setSaving(true);
    try {
      const res = await resetSection("integrations");
      if (res.success) {
        setFormData(DEFAULT_INTEGRATIONS);
        setSavedIntegrations(DEFAULT_INTEGRATIONS);
      }
    } finally {
      setSaving(false);
    }
  };

  const handleTestSlack = async () => {
    if (slackUrlError) {
      toast.error(slackUrlError);
      return;
    }
    setTestingSlack(true);
    try {
      const res = await settingsAPI.testSlack(formData.slack_webhook_url);
      if (res.data?.success) {
        toast.success("Test message delivered to Slack channel!");
      } else {
        toast.error(res.data?.error || "Slack test failed");
      }
    } catch (err) {
      toast.error(err.response?.data?.error || "Could not reach Slack webhook");
    } finally {
      setTestingSlack(false);
    }
  };

  // ── Webhook Handlers ───────────────────────────────────────────────────────
  const handleCreateWebhook = async (e) => {
    e.preventDefault();
    if (!webhookUrl.startsWith("https://")) {
      toast.error("Webhook destination URL must start with https://");
      return;
    }
    if (selectedEvents.length === 0) {
      toast.error("Select at least one subscribed event");
      return;
    }

    setCreatingWebhook(true);
    try {
      const res = await settingsAPI.createWebhook({ url: webhookUrl, events: selectedEvents });
      if (res.data?.success) {
        setNewWebhookSecret(res.data.webhook.secret);
        fetchWebhooks();
        setWebhookUrl("");
        toast.success("Webhook endpoint registered");
      }
    } catch (err) {
      toast.error(err.response?.data?.error || "Failed to create webhook");
    } finally {
      setCreatingWebhook(false);
    }
  };

  const handleDeleteWebhook = async (id) => {
    try {
      const res = await settingsAPI.deleteWebhook(id);
      if (res.data?.success) {
        toast.success("Webhook deleted");
        fetchWebhooks();
      }
    } catch {
      toast.error("Failed to delete webhook");
    }
  };

  const handleTestWebhook = async (id) => {
    try {
      const res = await settingsAPI.testWebhook(id);
      if (res.data?.success) {
        toast.success(res.data.message || "Test ping delivered");
      } else {
        toast.error(res.data?.error || "Test delivery failed");
      }
    } catch (err) {
      toast.error(err.response?.data?.error || "Test delivery failed");
    }
  };

  const handleViewDeliveries = async () => {
    setDeliveriesModalOpen(true);
    setLoadingDeliveries(true);
    try {
      const res = await settingsAPI.getWebhookDeliveries();
      if (res.data?.success) setDeliveries(res.data.deliveries);
    } catch {
      toast.error("Failed to fetch delivery logs");
    } finally {
      setLoadingDeliveries(false);
    }
  };

  // ── API Key Handlers ───────────────────────────────────────────────────────
  const handleCreateApiKey = async (e) => {
    e.preventDefault();
    setKeyNameError("");
    setKeyScopeError("");

    const trimmedName = keyName.trim();
    let hasError = false;
    if (!trimmedName) {
      setKeyNameError("API key name is required");
      hasError = true;
    }
    if (keyScopes.length === 0) {
      setKeyScopeError("At least one permission scope is required");
      hasError = true;
    }
    if (hasError) {
      toast.error(trimmedName ? "Select at least one permission scope" : "API key name is required");
      return;
    }

    setCreatingKey(true);
    try {
      const res = await settingsAPI.createApiKey({
        name: trimmedName,
        scopes: keyScopes,
        expires_in_days: keyExpiryDays
      });
      if (res.data?.success) {
        setGeneratedRawKey(res.data.key);
        fetchApiKeys();
        setKeyName("");
        setKeyNameError("");
        setKeyScopeError("");
        toast.success(res.data.message || "API Key generated");
      } else {
        toast.error(res.data?.error || "Failed to generate API Key");
      }
    } catch (err) {
      toast.error(err.response?.data?.error || err.message || "Failed to generate API Key");
    } finally {
      setCreatingKey(false);
    }
  };

  const handleRevokeKey = async (id) => {
    try {
      const res = await settingsAPI.revokeApiKey(id);
      if (res.data?.success) {
        toast.success(res.data.message || "API Key revoked");
        fetchApiKeys();
      } else {
        toast.error(res.data?.error || "Failed to revoke API key");
      }
    } catch (err) {
      toast.error(err.response?.data?.error || "Failed to revoke API key");
    }
  };

  return (
    <>
      <form onSubmit={handleSave}>
        <SettingsSection
          title="Integrations & Developer APIs"
          description="Connect RecruitMate to Slack for real-time notifications, configure signed outgoing webhooks, manage external API keys, and set up calendar sync."
          isDirty={isDirty}
          onSave={handleSave}
          onReset={handleReset}
          saving={saving}
          loading={loading}
        >
        <div className="space-y-10 max-w-3xl">

          {/* 1. Slack Integration */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-ink-500 uppercase tracking-wider flex items-center gap-2">
                  <Send size={16} className="text-ledger-500" />
                  Slack Channel Notifications
                </h3>
                <p className="text-xs text-stone-500 mt-1">
                  Send real-time recruitment alerts directly into a Slack channel via incoming webhooks.
                </p>
              </div>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                loading={testingSlack}
                disabled={!formData.slack_webhook_url || testingSlack || !isAdmin}
                onClick={handleTestSlack}
                title="Send a sample alert to verify connection"
              >
                Send Test Message
              </Button>
            </div>

            <Input
              label="Slack Incoming Webhook URL"
              placeholder="https://hooks.slack.com/services/..."
              value={formData.slack_webhook_url}
              onChange={(e) => setFormData((prev) => ({ ...prev, slack_webhook_url: e.target.value }))}
              error={slackUrlError}
              disabled={!isAdmin}
            />

            <div className="space-y-2 pt-1">
              <p className="text-xs font-medium text-stone-700">Notification Triggers</p>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <label className="flex items-start gap-2.5 p-3 rounded-xl border border-stone-200 bg-stone-50/50 cursor-pointer hover:bg-stone-50 transition-colors">
                  <input
                    type="checkbox"
                    checked={formData.slack_events.new_candidate}
                    onChange={() => handleSlackEventToggle("new_candidate")}
                    disabled={!isAdmin}
                    className="mt-0.5 rounded border-stone-300 text-ledger-600 focus:ring-ledger-500"
                  />
                  <div>
                    <p className="text-xs font-semibold text-ink-500">New Candidate</p>
                    <p className="text-[11px] text-stone-500 leading-tight mt-0.5">Application received</p>
                  </div>
                </label>

                <label className="flex items-start gap-2.5 p-3 rounded-xl border border-stone-200 bg-stone-50/50 cursor-pointer hover:bg-stone-50 transition-colors">
                  <input
                    type="checkbox"
                    checked={formData.slack_events.interview_complete}
                    onChange={() => handleSlackEventToggle("interview_complete")}
                    disabled={!isAdmin}
                    className="mt-0.5 rounded border-stone-300 text-ledger-600 focus:ring-ledger-500"
                  />
                  <div>
                    <p className="text-xs font-semibold text-ink-500">Interview Complete</p>
                    <p className="text-[11px] text-stone-500 leading-tight mt-0.5">Voice interview finished</p>
                  </div>
                </label>

                <label className="flex items-start gap-2.5 p-3 rounded-xl border border-stone-200 bg-stone-50/50 cursor-pointer hover:bg-stone-50 transition-colors">
                  <input
                    type="checkbox"
                    checked={formData.slack_events.pending_review}
                    onChange={() => handleSlackEventToggle("pending_review")}
                    disabled={!isAdmin}
                    className="mt-0.5 rounded border-stone-300 text-ledger-600 focus:ring-ledger-500"
                  />
                  <div>
                    <p className="text-xs font-semibold text-ink-500">Pending Review</p>
                    <p className="text-[11px] text-stone-500 leading-tight mt-0.5">Approval required</p>
                  </div>
                </label>
              </div>
            </div>
          </div>

          <hr className="border-stone-200" />

          {/* 2. Outgoing Webhooks */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-ink-500 uppercase tracking-wider flex items-center gap-2">
                  <Webhook size={16} className="text-ledger-500" />
                  Outgoing Webhooks
                </h3>
                <p className="text-xs text-stone-500 mt-1">
                  Deliver signed HMAC-SHA256 payloads to your servers when recruitment events occur.
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={handleViewDeliveries}
                >
                  <Activity size={14} className="mr-1.5" />
                  Delivery Logs
                </Button>
                {isAdmin && (
                  <Button
                    type="button"
                    variant="primary"
                    size="sm"
                    onClick={() => { setWebhookModalOpen(true); setNewWebhookSecret(null); }}
                  >
                    <Plus size={14} className="mr-1.5" />
                    Add Endpoint
                  </Button>
                )}
              </div>
            </div>

            {loadingWebhooks ? (
              <p className="text-xs text-stone-400">Loading webhooks...</p>
            ) : webhooks.length === 0 ? (
              <div className="p-6 text-center border-2 border-dashed border-stone-200 rounded-xl bg-stone-50/50">
                <Webhook size={24} className="mx-auto text-stone-400 mb-1" />
                <p className="text-xs font-semibold text-stone-600">No outgoing webhooks configured</p>
                <p className="text-[11px] text-stone-400 mt-0.5">Subscribe endpoints to receive automated updates</p>
              </div>
            ) : (
              <div className="divide-y divide-stone-200 border border-stone-200 rounded-xl overflow-hidden bg-white">
                {webhooks.map((wh) => (
                  <div key={wh.id} className="p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-stone-50/50 transition-colors">
                    <div className="space-y-1">
                      <p className="text-xs font-mono font-semibold text-ink-500 break-all">{wh.url}</p>
                      <div className="flex flex-wrap gap-1.5">
                        {wh.events.map((ev) => (
                          <span key={ev} className="text-[10px] bg-stone-100 text-stone-700 font-mono px-2 py-0.5 rounded-md border border-stone-200">
                            {ev}
                          </span>
                        ))}
                      </div>
                    </div>
                    {isAdmin && (
                      <div className="flex items-center gap-1.5 shrink-0">
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          onClick={() => handleTestWebhook(wh.id)}
                          className="text-xs py-1 px-2.5"
                        >
                          Ping Test
                        </Button>
                        <button
                          type="button"
                          onClick={() => handleDeleteWebhook(wh.id)}
                          className="p-1.5 text-stone-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors cursor-pointer"
                          title="Delete Webhook"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          <hr className="border-stone-200" />

          {/* 3. API Keys & Public v1 API */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-ink-500 uppercase tracking-wider flex items-center gap-2">
                  <Key size={16} className="text-ledger-500" />
                  API Keys (Public v1 API)
                </h3>
                <p className="text-xs text-stone-500 mt-1">
                  Authenticate programmatic job listings and candidate ingestion. Rate limited to 60 req/min.
                </p>
              </div>
              {isAdmin && (
                <Button
                  type="button"
                  variant="primary"
                  size="sm"
                  onClick={() => {
                    setKeyName("");
                    setKeyScopes(["read:candidates", "write:jobs"]);
                    setKeyExpiryDays(90);
                    setKeyNameError("");
                    setKeyScopeError("");
                    setGeneratedRawKey(null);
                    setApiKeyModalOpen(true);
                  }}
                >
                  <Plus size={14} className="mr-1.5" />
                  Generate Key
                </Button>
              )}
            </div>

            {loadingKeys ? (
              <p className="text-xs text-stone-400">Loading API keys...</p>
            ) : apiKeys.length === 0 ? (
              <div className="p-6 text-center border-2 border-dashed border-stone-200 rounded-xl bg-stone-50/50">
                <Key size={24} className="mx-auto text-stone-400 mb-1" />
                <p className="text-xs font-semibold text-stone-600">No active API keys</p>
                <p className="text-[11px] text-stone-400 mt-0.5">Generate an API key to integrate external ATS or career portals</p>
              </div>
            ) : (
              <div className="divide-y divide-stone-200 border border-stone-200 rounded-xl overflow-hidden bg-white">
                {apiKeys.map((key) => (
                  <div key={key.id} className="p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-stone-50/50 transition-colors">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-ink-500">{key.name}</span>
                        <code className="text-xs bg-stone-100 text-stone-700 px-2 py-0.5 rounded border border-stone-200">
                          {key.key_prefix}
                        </code>
                        {key.revoked ? (
                          <span className="text-[10px] bg-rose-50 text-rose-700 border border-rose-200 px-1.5 py-0.5 rounded font-medium">
                            Revoked
                          </span>
                        ) : (
                          <span className="text-[10px] bg-emerald-50 text-emerald-700 border border-emerald-200 px-1.5 py-0.5 rounded font-medium">
                            Active
                          </span>
                        )}
                      </div>
                      <div className="flex flex-wrap items-center gap-2 text-[11px] text-stone-500">
                        <span>Scopes: {key.scopes.join(", ")}</span>
                        {key.created_at && (
                          <span>• Created: {new Date(key.created_at).toLocaleDateString()}</span>
                        )}
                        {key.last_used_at && <span>• Last used: {new Date(key.last_used_at).toLocaleDateString()}</span>}
                        {key.expires_at && <span>• Expires: {new Date(key.expires_at).toLocaleDateString()}</span>}
                      </div>
                    </div>
                    {isAdmin && !key.revoked && (
                      <Button
                        type="button"
                        variant="danger"
                        size="sm"
                        onClick={() => handleRevokeKey(key.id)}
                        className="text-xs py-1 px-2.5 shrink-0"
                      >
                        Revoke
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          <hr className="border-stone-200" />

          {/* 4. Google Calendar & Meet Sync */}
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-ink-500 uppercase tracking-wider flex items-center gap-2">
              <Calendar size={16} className="text-ledger-500" />
              Google Calendar & Meet Video
            </h3>

            <div className="p-5 border border-stone-200 rounded-2xl bg-stone-50/70 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <Video size={16} className="text-stone-600" />
                  <p className="text-xs font-bold text-ink-500">Automated Google Meet Scheduling</p>
                  <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold border ${
                    googleStatus.connected
                      ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                      : "bg-stone-200 text-stone-700 border-stone-300"
                  }`}>
                    {googleStatus.connected ? "Connected" : "Not configured"}
                  </span>
                </div>
                <p className="text-xs text-stone-500 leading-relaxed max-w-xl">
                  {googleStatus.enabled
                    ? googleStatus.connected
                      ? `Syncing calendar events and video interview rooms for ${googleStatus.calendar_email || "your account"}.`
                      : "Google OAuth credentials available. Connect your account to enable automated Google Meet interview invites."
                    : "Google Calendar & Meet integration is currently disabled on your server. Contact your administrator or enable GOOGLE_CALENDAR_ENABLED in your environment variables to turn on Google Meet room generation."}
                </p>
              </div>

              {googleStatus.enabled && isAdmin && (
                googleStatus.connected ? (
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={async () => {
                      await settingsAPI.disconnectGoogle();
                      fetchGoogleStatus();
                      toast.success("Google Calendar disconnected");
                    }}
                  >
                    Disconnect
                  </Button>
                ) : (
                  <Button
                    type="button"
                    variant="primary"
                    size="sm"
                    onClick={() => toast("Google OAuth login flow will open in production.", { icon: "ℹ️" })}
                  >
                    Connect Google
                  </Button>
                )
              )}
            </div>
          </div>

        </div>
      </SettingsSection>
    </form>

      {/* ── Modal: Register Webhook ────────────────────────────────────────── */}
      <Modal
        isOpen={webhookModalOpen}
        onClose={() => setWebhookModalOpen(false)}
        title={newWebhookSecret ? "Webhook Signing Secret" : "Register Outgoing Webhook"}
      >
        {newWebhookSecret ? (
          <div className="space-y-4">
            <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800 space-y-1">
              <p className="font-bold flex items-center gap-1.5">
                <AlertCircle size={14} />
                Copy your signing secret now
              </p>
              <p>This secret is used to sign HMAC-SHA256 headers. For your security, it will not be displayed again.</p>
            </div>
            <div className="flex items-center gap-2 p-2.5 bg-stone-100 rounded-lg border border-stone-300">
              <code className="text-xs font-mono font-bold text-ink-500 flex-1 break-all select-all">
                {newWebhookSecret}
              </code>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => {
                  navigator.clipboard.writeText(newWebhookSecret);
                  toast.success("Signing secret copied");
                }}
              >
                <Copy size={13} className="mr-1" />
                Copy
              </Button>
            </div>
            <div className="flex justify-end pt-2">
              <Button type="button" variant="primary" onClick={() => setWebhookModalOpen(false)}>
                Done
              </Button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleCreateWebhook} className="space-y-4">
            <Input
              label="Endpoint URL (HTTPS only)"
              placeholder="https://api.yourdomain.com/webhooks/recruitmate"
              value={webhookUrl}
              onChange={(e) => setWebhookUrl(e.target.value)}
              required
            />
            <div className="space-y-2">
              <label className="text-xs font-semibold text-stone-700">Subscribed Events</label>
              <div className="space-y-2">
                {WEBHOOK_EVENT_OPTIONS.map((opt) => (
                  <label key={opt.id} className="flex items-start gap-2.5 p-2.5 rounded-lg border border-stone-200 bg-stone-50/50 cursor-pointer hover:bg-stone-50">
                    <input
                      type="checkbox"
                      checked={selectedEvents.includes(opt.id)}
                      onChange={(e) => {
                        if (e.target.checked) setSelectedEvents([...selectedEvents, opt.id]);
                        else setSelectedEvents(selectedEvents.filter((x) => x !== opt.id));
                      }}
                      className="mt-0.5 rounded border-stone-300 text-ledger-600 focus:ring-ledger-500"
                    />
                    <div>
                      <p className="text-xs font-semibold text-ink-500">{opt.label}</p>
                      <p className="text-[11px] text-stone-500">{opt.description}</p>
                    </div>
                  </label>
                ))}
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="secondary" onClick={() => setWebhookModalOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" variant="primary" loading={creatingWebhook}>
                Register Endpoint
              </Button>
            </div>
          </form>
        )}
      </Modal>

      {/* ── Modal: Generate API Key ────────────────────────────────────────── */}
      <Modal
        isOpen={apiKeyModalOpen}
        onClose={() => {
          setApiKeyModalOpen(false);
          setGeneratedRawKey(null);
          setKeyNameError("");
          setKeyScopeError("");
        }}
        title={generatedRawKey ? "Your New API Key" : "Generate External API Key"}
      >
        {generatedRawKey ? (
          <div className="space-y-4">
            <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800 space-y-1">
              <p className="font-bold flex items-center gap-1.5">
                <AlertCircle size={14} />
                Copy your API Key now
              </p>
              <p>Store this key securely. We only store an irreversible hash and cannot show it to you again.</p>
            </div>
            <div className="flex items-center gap-2 p-2.5 bg-stone-100 rounded-lg border border-stone-300">
              <code className="text-xs font-mono font-bold text-ink-500 flex-1 break-all select-all">
                {generatedRawKey}
              </code>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => {
                  navigator.clipboard.writeText(generatedRawKey);
                  toast.success("API Key copied");
                }}
              >
                <Copy size={13} className="mr-1" />
                Copy
              </Button>
            </div>
            <div className="flex justify-end pt-2">
              <Button
                type="button"
                variant="primary"
                onClick={() => {
                  setApiKeyModalOpen(false);
                  setGeneratedRawKey(null);
                }}
              >
                Done
              </Button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleCreateApiKey} className="space-y-4">
            <Input
              label="Key Identifier / Name"
              placeholder="e.g. Careers Page Intake"
              value={keyName}
              onChange={(e) => {
                setKeyName(e.target.value);
                if (keyNameError) setKeyNameError("");
              }}
              error={keyNameError}
              required
            />
            <div className="space-y-2">
              <label className="text-xs font-semibold text-stone-700">Access Scopes</label>
              <div className="space-y-1.5">
                <label className="flex items-center gap-2 text-xs text-stone-700 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={keyScopes.includes("read:candidates")}
                    onChange={(e) => {
                      if (keyScopeError) setKeyScopeError("");
                      if (e.target.checked) setKeyScopes([...keyScopes, "read:candidates"]);
                      else setKeyScopes(keyScopes.filter((s) => s !== "read:candidates"));
                    }}
                    className="rounded border-stone-300 text-ledger-600 focus:ring-ledger-500"
                  />
                  <span><code>read:candidates</code> — Ingest candidate applications</span>
                </label>
                <label className="flex items-center gap-2 text-xs text-stone-700 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={keyScopes.includes("write:jobs")}
                    onChange={(e) => {
                      if (keyScopeError) setKeyScopeError("");
                      if (e.target.checked) setKeyScopes([...keyScopes, "write:jobs"]);
                      else setKeyScopes(keyScopes.filter((s) => s !== "write:jobs"));
                    }}
                    className="rounded border-stone-300 text-ledger-600 focus:ring-ledger-500"
                  />
                  <span><code>write:jobs</code> — List open positions</span>
                </label>
              </div>
              {keyScopeError && (
                <p className="text-red-500 text-xs font-medium">{keyScopeError}</p>
              )}
            </div>
            <div>
              <label className="text-xs font-semibold text-stone-700 block mb-1">Expiration</label>
              <select
                value={keyExpiryDays}
                onChange={(e) => setKeyExpiryDays(Number(e.target.value))}
                className="input w-full text-xs"
              >
                <option value={30}>30 Days</option>
                <option value={90}>90 Days</option>
                <option value={365}>1 Year</option>
                <option value={0}>No Expiry (Never)</option>
              </select>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setApiKeyModalOpen(false);
                  setKeyNameError("");
                  setKeyScopeError("");
                }}
              >
                Cancel
              </Button>
              <Button type="submit" variant="primary" loading={creatingKey}>
                Create Key
              </Button>
            </div>
          </form>
        )}
      </Modal>

      {/* ── Modal: Webhook Delivery Logs ───────────────────────────────────── */}
      <Modal
        isOpen={deliveriesModalOpen}
        onClose={() => setDeliveriesModalOpen(false)}
        title="Recent Webhook Deliveries (Last 50)"
      >
        <div className="space-y-4 max-h-[60vh] overflow-y-auto">
          {loadingDeliveries ? (
            <p className="text-xs text-stone-400">Loading delivery records...</p>
          ) : deliveries.length === 0 ? (
            <p className="text-xs text-stone-500 text-center py-6">No delivery attempts recorded yet.</p>
          ) : (
            <div className="divide-y divide-stone-200 border border-stone-200 rounded-xl overflow-hidden bg-white text-xs">
              {deliveries.map((d) => (
                <div key={d.id} className="p-3 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-bold text-ink-500">{d.event}</span>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                      d.success ? "bg-emerald-50 text-emerald-700 border border-emerald-200" : "bg-rose-50 text-rose-700 border border-rose-200"
                    }`}>
                      {d.success ? `HTTP ${d.status_code}` : d.error_message || "Failed"}
                    </span>
                  </div>
                  <p className="text-[11px] text-stone-500 font-mono truncate">{d.url}</p>
                  <div className="flex items-center justify-between text-[10px] text-stone-400">
                    <span>{d.response_time_ms} ms • Attempt {d.attempt}</span>
                    <span>{new Date(d.delivered_at).toLocaleString()}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
          <div className="flex justify-end pt-2">
            <Button type="button" variant="secondary" onClick={() => setDeliveriesModalOpen(false)}>
              Close
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
}
