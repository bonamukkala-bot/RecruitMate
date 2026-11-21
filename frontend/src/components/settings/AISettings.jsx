import { useState, useEffect } from "react";
import SettingsSection from "./SettingsSection";
import { useSettings } from "../../context/SettingsContext";
import { settingsAPI } from "../../api/settings";
import Input from "../ui/Input";
import Button from "../ui/Button";
import LoadingSpinner from "../ui/LoadingSpinner";
import {
  Bot,
  Zap,
  Cpu,
  Globe,
  Sliders,
  DollarSign,
  AlertTriangle,
  RefreshCw,
  BarChart2,
  Clock,
  ShieldAlert,
  Activity
} from "lucide-react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip
} from "recharts";
import toast from "react-hot-toast";

const DEFAULT_AI = {
  model_default: "openai/gpt-oss-20b",
  model_heavy: "openai/gpt-oss-120b",
  output_language: "English",
  tone: "professional",
  temperature: 0.3,
  monthly_token_budget: 0
};

const LANGUAGE_OPTIONS = [
  { value: "English", label: "English" },
  { value: "Telugu", label: "Telugu (తెలుగు)" },
  { value: "Hindi", label: "Hindi (हिंदी)" }
];

const TONE_OPTIONS = [
  { value: "professional", label: "Professional — Formal and objective" },
  { value: "friendly", label: "Friendly — Warm, encouraging and approachable" },
  { value: "concise", label: "Concise — Direct, structured and to the point" }
];

// Helper to format large numbers
function formatNumber(num) {
  if (num == null) return "0";
  if (num >= 1_000_000) return `${(num / 1_000_000).toFixed(2)}M`;
  if (num >= 1_000) return `${(num / 1_000).toFixed(1)}k`;
  return num.toLocaleString();
}

// Chart Custom Tooltip
function ChartTooltip({ active, payload, label }) {
  if (active && payload && payload.length) {
    return (
      <div className="bg-white border border-stone-200 rounded-xl p-3 shadow-card-md">
        <p className="text-stone-500 text-xs mb-1 font-mono">{label}</p>
        <p className="text-ink-500 text-sm font-semibold">
          Tokens: <span className="text-ledger-600 font-mono">{payload[0]?.value?.toLocaleString()}</span>
        </p>
        {payload[0]?.payload?.cost != null && (
          <p className="text-stone-400 text-xs font-mono mt-0.5">
            Est. Cost: ${Number(payload[0].payload.cost).toFixed(4)}
          </p>
        )}
      </div>
    );
  }
  return null;
}

export default function AISettings() {
  const { settings, updateSection, resetSection } = useSettings();
  const [formData, setFormData] = useState(DEFAULT_AI);
  const [subTab, setSubTab] = useState("models"); // "models" | "usage"
  const [saving, setSaving] = useState(false);

  // Usage state
  const [usageLoading, setUsageLoading] = useState(false);
  const [usageData, setUsageData] = useState(null);

  // Load from context settings
  useEffect(() => {
    if (settings?.ai) {
      setFormData({
        model_default: settings.ai.model_default ?? DEFAULT_AI.model_default,
        model_heavy: settings.ai.model_heavy ?? DEFAULT_AI.model_heavy,
        output_language: settings.ai.output_language ?? DEFAULT_AI.output_language,
        tone: settings.ai.tone ?? DEFAULT_AI.tone,
        temperature: settings.ai.temperature ?? DEFAULT_AI.temperature,
        monthly_token_budget: settings.ai.monthly_token_budget ?? DEFAULT_AI.monthly_token_budget
      });
    }
  }, [settings]);

  // Load usage data
  const fetchUsage = async () => {
    setUsageLoading(true);
    try {
      const res = await settingsAPI.getAIUsage();
      if (res.data?.success) {
        setUsageData(res.data);
      }
    } catch (err) {
      toast.error(err.response?.data?.error || "Could not load AI usage metrics");
    } finally {
      setUsageLoading(false);
    }
  };

  useEffect(() => {
    fetchUsage();
  }, []);

  const originalAI = settings?.ai || DEFAULT_AI;
  const isDirty = JSON.stringify(formData) !== JSON.stringify(originalAI);

  const allowedModels = usageData?.allowed_models || [
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b"
  ];

  const handleFieldChange = (field, value) => {
    setFormData((prev) => ({
      ...prev,
      [field]: value
    }));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateSection("ai", formData);
      toast.success("AI settings updated successfully");
      fetchUsage(); // refresh usage metrics in case budget was changed
    } catch (err) {
      toast.error(err.response?.data?.error || "Failed to update AI settings");
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    try {
      const res = await resetSection("ai");
      if (res?.data) {
        setFormData(res.data);
      } else {
        setFormData(DEFAULT_AI);
      }
      toast.success("AI settings reset to defaults");
      fetchUsage();
    } catch (err) {
      toast.error(err.response?.data?.error || "Failed to reset AI settings");
    }
  };

  const budget = usageData?.budget || {
    monthly_limit: formData.monthly_token_budget,
    used_tokens: 0,
    percentage: 0,
    status: "normal"
  };

  return (
    <div className="space-y-6">
      {/* Sub-tab Navigation */}
      <div className="flex items-center gap-2 border-b border-stone-200 pb-3">
        <button
          type="button"
          onClick={() => setSubTab("models")}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all ${
            subTab === "models"
              ? "bg-ink-500 text-white shadow-sm"
              : "text-stone-600 hover:text-ink-500 hover:bg-stone-100"
          }`}
        >
          <Bot size={16} />
          <span>Models & Configuration</span>
        </button>
        <button
          type="button"
          onClick={() => {
            setSubTab("usage");
            fetchUsage();
          }}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all ${
            subTab === "usage"
              ? "bg-ink-500 text-white shadow-sm"
              : "text-stone-600 hover:text-ink-500 hover:bg-stone-100"
          }`}
        >
          <BarChart2 size={16} />
          <span>Usage & Analytics</span>
          {budget.status === "warning" && (
            <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
          )}
          {budget.status === "exceeded" && (
            <span className="w-2 h-2 rounded-full bg-rose-500 animate-pulse" />
          )}
        </button>
      </div>

      {/* ────────────────────────────────────────────────────────────────────── */}
      {/* SUB-SECTION: MODELS & CONFIGURATION                                    */}
      {/* ────────────────────────────────────────────────────────────────────── */}
      {subTab === "models" && (
        <SettingsSection
          title="AI Models & Generation"
          description="Select LLM model variants, generation temperature, candidate-facing language and token caps."
          badge="Groq Powered"
          isDirty={isDirty}
          loading={saving}
          onSave={handleSave}
          onReset={handleReset}
        >
          <div className="p-6 space-y-8">
            {/* Model Architecture Selection */}
            <div>
              <h3 className="text-sm font-bold uppercase tracking-wider text-stone-500 mb-4 flex items-center gap-2">
                <Cpu size={16} className="text-ledger-600" />
                Model Architecture
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-stone-700 mb-1.5">
                    Default Model (Standard Workflows)
                  </label>
                  <select
                    value={formData.model_default}
                    onChange={(e) => handleFieldChange("model_default", e.target.value)}
                    className="w-full px-3 py-2 bg-white border border-stone-200 rounded-xl text-sm text-ink-500 focus:outline-none focus:ring-2 focus:ring-ledger-500 font-mono"
                  >
                    {allowedModels.map((m) => (
                      <option key={m} value={m}>
                        {m}
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-stone-400 mt-1.5">
                    Used for JD parsing, interview questions, email drafting and scheduling.
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-stone-700 mb-1.5">
                    Heavy Reasoning Model
                  </label>
                  <select
                    value={formData.model_heavy}
                    onChange={(e) => handleFieldChange("model_heavy", e.target.value)}
                    className="w-full px-3 py-2 bg-white border border-stone-200 rounded-xl text-sm text-ink-500 focus:outline-none focus:ring-2 focus:ring-ledger-500 font-mono"
                  >
                    {allowedModels.map((m) => (
                      <option key={m} value={m}>
                        {m}
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-stone-400 mt-1.5">
                    Used for deep resume screening and rigorous candidate answer evaluation.
                  </p>
                </div>
              </div>
            </div>

            {/* Language & Tone */}
            <div className="border-t border-stone-100 pt-6">
              <h3 className="text-sm font-bold uppercase tracking-wider text-stone-500 mb-4 flex items-center gap-2">
                <Globe size={16} className="text-ledger-600" />
                Language & Persona
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-stone-700 mb-1.5">
                    Candidate-Facing Language
                  </label>
                  <select
                    value={formData.output_language}
                    onChange={(e) => handleFieldChange("output_language", e.target.value)}
                    className="w-full px-3 py-2 bg-white border border-stone-200 rounded-xl text-sm text-ink-500 focus:outline-none focus:ring-2 focus:ring-ledger-500"
                  >
                    {LANGUAGE_OPTIONS.map((lang) => (
                      <option key={lang.value} value={lang.value}>
                        {lang.label}
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-stone-400 mt-1.5">
                    Generated interview questions and candidate communications will adopt this language. Internal scoring keys remain strictly structured.
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-stone-700 mb-1.5">
                    Agent Tone
                  </label>
                  <select
                    value={formData.tone}
                    onChange={(e) => handleFieldChange("tone", e.target.value)}
                    className="w-full px-3 py-2 bg-white border border-stone-200 rounded-xl text-sm text-ink-500 focus:outline-none focus:ring-2 focus:ring-ledger-500"
                  >
                    {TONE_OPTIONS.map((t) => (
                      <option key={t.value} value={t.value}>
                        {t.label}
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-stone-400 mt-1.5">
                    Directs the communicative tone of interview prompts and feedback.
                  </p>
                </div>
              </div>
            </div>

            {/* Generation Parameters & Budget */}
            <div className="border-t border-stone-100 pt-6 space-y-6">
              <h3 className="text-sm font-bold uppercase tracking-wider text-stone-500 flex items-center gap-2">
                <Sliders size={16} className="text-ledger-600" />
                Parameters & Cost Controls
              </h3>

              {/* Temperature Slider */}
              <div className="bg-stone-50/70 p-4 rounded-xl border border-stone-200">
                <div className="flex items-center justify-between mb-2">
                  <label className="text-sm font-medium text-ink-500">
                    Temperature (Creativity vs. Determinism)
                  </label>
                  <span className="font-mono text-sm font-bold px-2 py-0.5 rounded bg-white border border-stone-200 text-ledger-600">
                    {Number(formData.temperature).toFixed(2)}
                  </span>
                </div>
                <input
                  type="range"
                  min="0.0"
                  max="1.0"
                  step="0.05"
                  value={formData.temperature}
                  onChange={(e) => handleFieldChange("temperature", parseFloat(e.target.value))}
                  className="w-full h-2 bg-stone-200 rounded-lg appearance-none cursor-pointer accent-ledger-600"
                />
                <div className="flex justify-between text-xs text-stone-400 mt-1.5">
                  <span>0.0 (Deterministic & Consistent)</span>
                  <span>0.5 (Balanced)</span>
                  <span>1.0 (Creative & Variable)</span>
                </div>
              </div>

              {/* Monthly Token Budget */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-start">
                <div>
                  <Input
                    label="Monthly Token Budget"
                    type="number"
                    min="0"
                    step="10000"
                    value={formData.monthly_token_budget}
                    onChange={(e) =>
                      handleFieldChange(
                        "monthly_token_budget",
                        Math.max(0, parseInt(e.target.value, 10) || 0)
                      )
                    }
                    placeholder="0"
                    hint="Set to 0 for unlimited usage. When set, non-essential calls are blocked upon reaching 100% capacity."
                  />
                </div>
                <div className="p-4 bg-ledger-50/60 rounded-xl border border-ledger-100 text-xs text-ledger-800 space-y-1">
                  <p className="font-semibold flex items-center gap-1.5">
                    <ShieldAlert size={14} className="text-ledger-600" />
                    Budget Protection Policy
                  </p>
                  <p className="text-stone-600 leading-relaxed">
                    At 80% usage, a warning banner appears in the dashboard. At 100%, background resume screening and job description generation will be safely paused to avoid surprise provider charges. Essential auth operations are never interrupted.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </SettingsSection>
      )}

      {/* ────────────────────────────────────────────────────────────────────── */}
      {/* SUB-SECTION: USAGE & ANALYTICS                                         */}
      {/* ────────────────────────────────────────────────────────────────────── */}
      {subTab === "usage" && (
        <div className="space-y-6">
          {/* Header Bar */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-6 rounded-2xl border border-stone-200 shadow-card">
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-ink-500 font-display">AI Usage & Cost Tracking</h2>
                <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-stone-100 text-stone-600">
                  Real-time
                </span>
              </div>
              <p className="text-stone-500 text-sm mt-1">
                Monitor token consumption, latency metrics, and estimated API expenses across agents.
              </p>
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={fetchUsage}
              loading={usageLoading}
              className="self-start sm:self-auto"
            >
              <RefreshCw size={14} className={usageLoading ? "animate-spin" : ""} />
              Refresh
            </Button>
          </div>

          {/* Budget Warning Banner (80% - 99%) */}
          {budget.status === "warning" && (
            <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 flex items-start gap-3">
              <AlertTriangle className="text-amber-600 shrink-0 mt-0.5" size={20} />
              <div className="space-y-1">
                <h4 className="text-sm font-bold text-amber-900">
                  Monthly Token Budget Warning ({budget.percentage}% Used)
                </h4>
                <p className="text-xs text-amber-800">
                  Your organization has consumed {formatNumber(budget.used_tokens)} of your {formatNumber(budget.monthly_limit)} token limit this calendar month. Consider increasing your monthly token budget in the Models tab.
                </p>
              </div>
            </div>
          )}

          {/* Budget Exceeded Banner (>= 100%) */}
          {budget.status === "exceeded" && (
            <div className="bg-rose-50 border border-rose-200 rounded-2xl p-4 flex items-start gap-3">
              <ShieldAlert className="text-rose-600 shrink-0 mt-0.5" size={20} />
              <div className="space-y-1">
                <h4 className="text-sm font-bold text-rose-900">
                  Monthly Token Budget Exceeded ({budget.percentage}%)
                </h4>
                <p className="text-xs text-rose-800">
                  Non-essential AI workflows (resume screening, automatic question generation, JD authoring) are currently paused to protect against unexpected costs. Increase your token allowance in Models & Configuration to resume immediately.
                </p>
              </div>
            </div>
          )}

          {/* Stat Cards Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-white p-5 rounded-2xl border border-stone-200 shadow-card">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-stone-500 uppercase tracking-wider">7-Day Usage</span>
                <div className="w-8 h-8 rounded-lg bg-ledger-50 flex items-center justify-center text-ledger-600">
                  <Activity size={16} />
                </div>
              </div>
              <p className="text-2xl font-bold font-mono text-ink-500 mt-3">
                {formatNumber(usageData?.totals_7d?.total_tokens || 0)}
              </p>
              <p className="text-xs text-stone-400 mt-1">
                {usageData?.totals_7d?.total_calls || 0} API invocations
              </p>
            </div>

            <div className="bg-white p-5 rounded-2xl border border-stone-200 shadow-card">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-stone-500 uppercase tracking-wider">30-Day Usage</span>
                <div className="w-8 h-8 rounded-lg bg-blue-50 flex items-center justify-center text-blue-600">
                  <Zap size={16} />
                </div>
              </div>
              <p className="text-2xl font-bold font-mono text-ink-500 mt-3">
                {formatNumber(usageData?.totals_30d?.total_tokens || 0)}
              </p>
              <p className="text-xs text-stone-400 mt-1">
                {usageData?.totals_30d?.total_calls || 0} API invocations
              </p>
            </div>

            <div className="bg-white p-5 rounded-2xl border border-stone-200 shadow-card">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-stone-500 uppercase tracking-wider">Est. Cost (30d)</span>
                <div className="w-8 h-8 rounded-lg bg-emerald-50 flex items-center justify-center text-emerald-600">
                  <DollarSign size={16} />
                </div>
              </div>
              <div className="flex items-baseline gap-2 mt-3">
                <p className="text-2xl font-bold font-mono text-ink-500">
                  ${Number(usageData?.totals_30d?.estimated_cost || 0).toFixed(4)}
                </p>
                <span className="text-[10px] uppercase font-bold px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800">
                  Estimate
                </span>
              </div>
              <p className="text-xs text-stone-400 mt-1">
                Based on published Groq rates
              </p>
            </div>

            <div className="bg-white p-5 rounded-2xl border border-stone-200 shadow-card">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-stone-500 uppercase tracking-wider">Avg Latency</span>
                <div className="w-8 h-8 rounded-lg bg-purple-50 flex items-center justify-center text-purple-600">
                  <Clock size={16} />
                </div>
              </div>
              <p className="text-2xl font-bold font-mono text-ink-500 mt-3">
                {usageData?.totals_30d?.avg_latency_ms || 0} <span className="text-sm font-normal text-stone-400">ms</span>
              </p>
              <p className="text-xs text-stone-400 mt-1">
                Failure rate: {usageData?.totals_30d?.failure_rate ?? 0}%
              </p>
            </div>
          </div>

          {/* Daily Timeseries Chart */}
          <div className="bg-white p-6 rounded-2xl border border-stone-200 shadow-card">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h3 className="text-base font-bold text-ink-500 font-display">Daily Token Volume</h3>
                <p className="text-xs text-stone-400 mt-0.5">Token consumption over the past 14 days</p>
              </div>
              <div className="flex items-center gap-2 text-xs text-stone-500 font-mono">
                <span className="w-3 h-3 rounded bg-ledger-600 inline-block" />
                <span>Total Tokens</span>
              </div>
            </div>

            {usageLoading && !usageData ? (
              <div className="h-64 flex items-center justify-center">
                <LoadingSpinner size="md" />
              </div>
            ) : (
              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={usageData?.daily_timeseries || []}
                    margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                    <XAxis
                      dataKey="date"
                      stroke="#94a3b8"
                      fontSize={11}
                      tickLine={false}
                      axisLine={false}
                      tickFormatter={(val) => val.slice(5)}
                    />
                    <YAxis
                      stroke="#94a3b8"
                      fontSize={11}
                      tickLine={false}
                      axisLine={false}
                      tickFormatter={(val) => formatNumber(val)}
                    />
                    <Tooltip content={<ChartTooltip />} />
                    <Bar dataKey="tokens" fill="#2A4B7C" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>

          {/* Agent Breakdown Table */}
          <div className="bg-white rounded-2xl border border-stone-200 shadow-card overflow-hidden">
            <div className="p-5 border-b border-stone-100 flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-ink-500 font-display">Usage by Agent (Last 30 Days)</h3>
                <p className="text-xs text-stone-400 mt-0.5">Workload distribution across autonomous agents</p>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="bg-stone-50 border-b border-stone-100 text-stone-500 text-xs font-semibold uppercase tracking-wider">
                    <th className="py-3 px-6">Agent</th>
                    <th className="py-3 px-6">Calls</th>
                    <th className="py-3 px-6">Total Tokens</th>
                    <th className="py-3 px-6">Est. Cost</th>
                    <th className="py-3 px-6">Avg Latency</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100">
                  {usageData?.by_agent?.length ? (
                    usageData.by_agent.map((item) => (
                      <tr key={item.agent} className="hover:bg-stone-50/60 transition-colors">
                        <td className="py-3 px-6 font-mono font-medium text-ink-500">
                          {item.agent}
                        </td>
                        <td className="py-3 px-6 font-mono text-stone-600">
                          {item.calls.toLocaleString()}
                        </td>
                        <td className="py-3 px-6 font-mono text-stone-600">
                          {item.total_tokens.toLocaleString()}
                        </td>
                        <td className="py-3 px-6 font-mono text-emerald-700">
                          ${Number(item.estimated_cost).toFixed(4)}
                        </td>
                        <td className="py-3 px-6 font-mono text-stone-500">
                          {item.avg_latency_ms} ms
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={5} className="py-8 text-center text-stone-400 text-sm">
                        No agent activity recorded in the last 30 days
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Model Breakdown Table */}
          <div className="bg-white rounded-2xl border border-stone-200 shadow-card overflow-hidden">
            <div className="p-5 border-b border-stone-100 flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-ink-500 font-display">Usage by Model (Last 30 Days)</h3>
                <p className="text-xs text-stone-400 mt-0.5">Token consumption partitioned by foundation model</p>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="bg-stone-50 border-b border-stone-100 text-stone-500 text-xs font-semibold uppercase tracking-wider">
                    <th className="py-3 px-6">Model</th>
                    <th className="py-3 px-6">Calls</th>
                    <th className="py-3 px-6">Total Tokens</th>
                    <th className="py-3 px-6">Est. Cost</th>
                    <th className="py-3 px-6">Avg Latency</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100">
                  {usageData?.by_model?.length ? (
                    usageData.by_model.map((item) => (
                      <tr key={item.model} className="hover:bg-stone-50/60 transition-colors">
                        <td className="py-3 px-6 font-mono font-medium text-ink-500">
                          {item.model}
                        </td>
                        <td className="py-3 px-6 font-mono text-stone-600">
                          {item.calls.toLocaleString()}
                        </td>
                        <td className="py-3 px-6 font-mono text-stone-600">
                          {item.total_tokens.toLocaleString()}
                        </td>
                        <td className="py-3 px-6 font-mono text-emerald-700">
                          ${Number(item.estimated_cost).toFixed(4)}
                        </td>
                        <td className="py-3 px-6 font-mono text-stone-500">
                          {item.avg_latency_ms} ms
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={5} className="py-8 text-center text-stone-400 text-sm">
                        No model activity recorded in the last 30 days
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
