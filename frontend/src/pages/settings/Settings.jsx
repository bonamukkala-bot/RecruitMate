import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ShieldCheck, ShieldOff } from "lucide-react";
import { authAPI } from "../../api/auth";
import { ENABLED_TABS, SETTINGS_TABS } from "../../config/settings";
import SettingsSection from "../../components/settings/SettingsSection";
import HiringSettings from "../../components/settings/HiringSettings";
import InterviewSettings from "../../components/settings/InterviewSettings";
import EmailSettings from "../../components/settings/EmailSettings";
import AISettings from "../../components/settings/AISettings";
import TeamSettings from "../../components/settings/TeamSettings";
import CompanySettings from "../../components/settings/CompanySettings";
import PrivacySettings from "../../components/settings/PrivacySettings";
import Input from "../../components/ui/Input";
import Button from "../../components/ui/Button";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import toast from "react-hot-toast";
import clsx from "clsx";

export default function Settings() {
  const { tab } = useParams();
  const navigate = useNavigate();

  const firstEnabledTab = ENABLED_TABS[0] || "security";
  const activeTab = ENABLED_TABS.includes(tab) ? tab : firstEnabledTab;

  // Sync URL with valid enabled tab
  useEffect(() => {
    if (!tab || !ENABLED_TABS.includes(tab)) {
      navigate(`/settings/${firstEnabledTab}`, { replace: true });
    }
  }, [tab, firstEnabledTab, navigate]);

  // Only render tabs that are listed in ENABLED_TABS
  const visibleTabs = SETTINGS_TABS.filter((t) => ENABLED_TABS.includes(t.id));

  // ── 2FA Security State ─────────────────────────────────────────────────────
  const [qrCode, setQrCode]               = useState(null);
  const [secret, setSecret]               = useState(null);
  const [code, setCode]                   = useState("");
  const [enabled, setEnabled]             = useState(false);
  const [loading2FA, setLoading2FA]       = useState(false);
  const [statusLoading, setStatusLoading] = useState(true);
  const [showDisableForm, setShowDisableForm] = useState(false);
  const [disablePassword, setDisablePassword] = useState("");

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await authAPI.get2FAStatus();
        setEnabled(res.data.enabled);
      } catch (err) {
        toast.error(err.response?.data?.error || "Could not fetch 2FA status");
      } finally {
        setStatusLoading(false);
      }
    };
    fetchStatus();
  }, []);

  const handleStartSetup = async () => {
    setLoading2FA(true);
    try {
      const res = await authAPI.setup2FA();
      if (res.data.success) {
        setQrCode(res.data.qr_code);
        setSecret(res.data.secret);
      } else {
        toast.error(res.data.error || "Could not start 2FA setup");
      }
    } catch (err) {
      toast.error(err.response?.data?.error || "Something went wrong");
    } finally {
      setLoading2FA(false);
    }
  };

  const handleConfirm = async (e) => {
    e.preventDefault();
    setLoading2FA(true);
    try {
      const res = await authAPI.enable2FA(code);
      if (res.data.success) {
        toast.success("2FA enabled successfully!");
        setEnabled(true);
        setQrCode(null);
      } else {
        toast.error(res.data.error || "Invalid code");
      }
    } catch (err) {
      toast.error(err.response?.data?.error || "Something went wrong");
    } finally {
      setLoading2FA(false);
    }
  };

  const handleDisable = async (e) => {
    e.preventDefault();
    setLoading2FA(true);
    try {
      const res = await authAPI.disable2FA(disablePassword);
      if (res.data.success) {
        toast.success("2FA disabled successfully");
        setEnabled(false);
        setShowDisableForm(false);
        setDisablePassword("");
        setQrCode(null);
      } else {
        toast.error(res.data.error || "Failed to disable 2FA");
      }
    } catch (err) {
      toast.error(err.response?.data?.error || "Something went wrong");
    } finally {
      setLoading2FA(false);
    }
  };

  const currentTabObj = SETTINGS_TABS.find((t) => t.id === activeTab) || SETTINGS_TABS[0];

  return (
    <div className="max-w-7xl mx-auto space-y-6 animate-fade-in">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-ink-500 font-display">Company Settings</h1>
        <p className="text-stone-500 text-sm mt-1">
          Manage your organization's rules, security and AI settings.
        </p>
      </div>

      {/* Main Layout: Stack on <768px, 4-col grid on >=768px */}
      <div className="flex flex-col md:grid md:grid-cols-4 gap-6 items-start">
        {/* Menu: Horizontal scroll on <768px, vertical sidebar on >=768px */}
        <div className="w-full bg-white rounded-2xl border border-stone-200 shadow-card p-2 md:p-3 md:col-span-1">
          <p className="text-xs font-semibold uppercase tracking-wider text-stone-400 px-3 py-2 hidden md:block">
            Settings Menu
          </p>

          <nav className="flex flex-row md:flex-col gap-1 overflow-x-auto md:overflow-visible pb-1 md:pb-0 scrollbar-none">
            {visibleTabs.map((tabItem) => {
              const Icon = tabItem.icon;
              const isActive = activeTab === tabItem.id;
              return (
                <button
                  key={tabItem.id}
                  onClick={() => navigate(`/settings/${tabItem.id}`)}
                  className={clsx(
                    "flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all text-left whitespace-nowrap shrink-0 md:shrink",
                    isActive
                      ? "bg-ledger-50 text-ledger-700 font-semibold border border-ledger-200"
                      : "text-stone-600 hover:text-ink-500 hover:bg-stone-50 border border-transparent"
                  )}
                >
                  <Icon size={18} className={clsx("shrink-0", isActive ? "text-ledger-600" : "text-stone-400")} />
                  <span className="truncate">{tabItem.label}</span>
                </button>
              );
            })}
          </nav>
        </div>

        {/* Content Area */}
        <div className="w-full md:col-span-3 space-y-6">
          {/* TAB: Security */}
          {activeTab === "security" && (
            <SettingsSection
              title="Two-Factor Authentication (2FA)"
              description="Add an extra layer of protection to safeguard your company recruitment data."
            >
              {statusLoading ? (
                <div className="py-12 flex flex-col items-center justify-center text-stone-400">
                  <LoadingSpinner size="md" text="Loading security status..." />
                </div>
              ) : enabled ? (
                <div className="space-y-6">
                  <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-4 rounded-xl bg-verified-50 border border-verified-200">
                    <div className="flex items-center gap-3 text-verified-700">
                      <div className="w-10 h-10 rounded-xl bg-verified-100 flex items-center justify-center shrink-0">
                        <ShieldCheck size={22} className="text-verified-600" />
                      </div>
                      <div>
                        <p className="font-semibold text-verified-900">2FA is currently active</p>
                        <p className="text-xs text-verified-700 mt-0.5">
                          Every login for your account requires a time-based verification code.
                        </p>
                      </div>
                    </div>
                    {!showDisableForm && (
                      <Button onClick={() => setShowDisableForm(true)} variant="danger" loading={loading2FA}>
                        Disable 2FA
                      </Button>
                    )}
                  </div>

                  {showDisableForm && (
                    <div className="p-5 rounded-xl border border-red-200 bg-red-50/50 space-y-3">
                      <p className="text-sm font-semibold text-red-900">Confirm Deactivation</p>
                      <p className="text-xs text-stone-600">
                        Please enter your current account password to disable two-factor authentication.
                      </p>
                      <form onSubmit={handleDisable} className="space-y-4 max-w-md pt-2">
                        <Input
                          label="Account Password"
                          name="password"
                          type="password"
                          placeholder="••••••••"
                          value={disablePassword}
                          onChange={(e) => setDisablePassword(e.target.value)}
                          required
                        />
                        <div className="flex gap-2">
                          <Button type="submit" variant="danger" loading={loading2FA}>
                            Confirm & Disable
                          </Button>
                          <Button
                            type="button"
                            onClick={() => { setShowDisableForm(false); setDisablePassword(""); }}
                            variant="secondary"
                          >
                            Cancel
                          </Button>
                        </div>
                      </form>
                    </div>
                  )}
                </div>
              ) : !qrCode ? (
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-4 rounded-xl bg-stone-50 border border-stone-200">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-stone-100 flex items-center justify-center shrink-0 text-stone-400">
                      <ShieldOff size={22} />
                    </div>
                    <div>
                      <p className="font-semibold text-ink-500">2FA is currently disabled</p>
                      <p className="text-xs text-stone-500 mt-0.5">
                        Prevent unauthorized account access by requiring an authenticator code.
                      </p>
                    </div>
                  </div>
                  <Button onClick={handleStartSetup} loading={loading2FA} variant="primary">
                    Enable 2FA
                  </Button>
                </div>
              ) : (
                <div className="space-y-6 max-w-md">
                  <div className="space-y-2">
                    <p className="text-sm font-medium text-ink-500">
                      1. Scan QR Code with your authenticator app
                    </p>
                    <p className="text-xs text-stone-500">
                      Use Google Authenticator, Microsoft Authenticator, Authy, or 1Password.
                    </p>
                    <div className="p-3 bg-white border border-stone-200 rounded-xl inline-block shadow-sm">
                      <img src={qrCode} alt="2FA QR Code" className="w-48 h-48 mx-auto" />
                    </div>
                    {secret && (
                      <p className="text-xs text-stone-500">
                        Manual entry code: <code className="font-mono bg-stone-100 px-1.5 py-0.5 rounded text-ink-600">{secret}</code>
                      </p>
                    )}
                  </div>

                  <form onSubmit={handleConfirm} className="space-y-3 pt-2">
                    <p className="text-sm font-medium text-ink-500">
                      2. Enter the 6-digit code shown in your app
                    </p>
                    <Input
                      label="Verification Code"
                      name="code"
                      type="text"
                      placeholder="000000"
                      value={code}
                      onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                      maxLength={6}
                      required
                    />
                    <div className="flex gap-2">
                      <Button type="submit" variant="primary" loading={loading2FA}>
                        Verify & Activate
                      </Button>
                      <Button type="button" variant="secondary" onClick={() => setQrCode(null)}>
                        Cancel
                      </Button>
                    </div>
                  </form>
                </div>
              )}
            </SettingsSection>
          )}

          {/* TAB: Hiring Rules */}
          {activeTab === "hiring" && <HiringSettings />}

          {/* TAB: Interview */}
          {activeTab === "interview" && <InterviewSettings />}

          {/* TAB: Email */}
          {activeTab === "email" && <EmailSettings />}

          {/* TAB: AI */}
          {activeTab === "ai" && <AISettings />}

          {/* TAB: Team */}
          {activeTab === "team" && <TeamSettings />}

          {/* TAB: Company */}
          {activeTab === "company" && <CompanySettings />}

          {/* TAB: Privacy */}
          {activeTab === "privacy" && <PrivacySettings />}

          {/* Placeholder for future enabled tabs */}
          {activeTab !== "security" && activeTab !== "hiring" && activeTab !== "interview" && activeTab !== "email" && activeTab !== "ai" && activeTab !== "team" && activeTab !== "company" && activeTab !== "privacy" && (
            <SettingsSection
              title={currentTabObj.label}
              description={currentTabObj.description}
            >
              <div className="text-center py-12 px-4 max-w-lg mx-auto space-y-4">
                <div className="w-14 h-14 rounded-2xl bg-ledger-50 border border-ledger-100 text-ledger-600 mx-auto flex items-center justify-center shadow-card">
                  <currentTabObj.icon size={26} />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-ink-500 font-display">
                    {currentTabObj.label} Configuration
                  </h3>
                  <p className="text-sm text-stone-500 mt-1">
                    {currentTabObj.description}
                  </p>
                </div>
              </div>
            </SettingsSection>
          )}
        </div>
      </div>
    </div>
  );
}
