import { useState, useEffect, useRef } from "react";
import SettingsSection from "./SettingsSection";
import { useSettings } from "../../context/SettingsContext";
import useRole from "../../hooks/useRole";
import { settingsAPI } from "../../api/settings";
import Input from "../ui/Input";
import Button from "../ui/Button";
import { Building2, Globe, Mail, Palette, Upload, Trash2, Eye, Image } from "lucide-react";
import toast from "react-hot-toast";

const DEFAULT_COMPANY = {
  display_name: "",
  website: "",
  logo: "",
  brand_color: "#4f46e5",
  support_email: ""
};

const COLOR_PRESETS = [
  "#4f46e5", // Indigo
  "#2563eb", // Blue
  "#0891b2", // Cyan
  "#059669", // Emerald
  "#d97706", // Amber
  "#dc2626", // Red
  "#7c3aed", // Violet
  "#1e293b"  // Slate
];

export default function CompanySettings() {
  const { settings, loading, updateSection, resetSection } = useSettings();
  const { isAdmin } = useRole();
  const [formData, setFormData] = useState(DEFAULT_COMPANY);
  const [savedSettings, setSavedSettings] = useState(DEFAULT_COMPANY);
  const [saving, setSaving] = useState(false);
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const fileInputRef = useRef(null);

  useEffect(() => {
    if (settings?.company) {
      const initial = {
        display_name: settings.company.display_name ?? "",
        website: settings.company.website ?? "",
        logo: settings.company.logo ?? "",
        brand_color: settings.company.brand_color || "#4f46e5",
        support_email: settings.company.support_email ?? ""
      };
      setFormData(initial);
      setSavedSettings(initial);
    }
  }, [settings]);

  const normalize = (data) => ({
    display_name: (data?.display_name || "").trim(),
    website: (data?.website || "").trim(),
    logo: data?.logo || "",
    brand_color: (data?.brand_color || "#4f46e5").trim().toLowerCase(),
    support_email: (data?.support_email || "").trim().toLowerCase()
  });

  const isDirty = JSON.stringify(normalize(formData)) !== JSON.stringify(normalize(savedSettings));

  // Inline Validation checks
  const errors = {};
  const trimmedHex = (formData.brand_color || "").trim();
  const isValidHex = /^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$/.test(trimmedHex);
  if (!isValidHex) {
    errors.brand_color = "Must be a valid hex color code (e.g. #4F46E5)";
  }

  const trimmedUrl = (formData.website || "").trim();
  if (trimmedUrl && !/^https?:\/\/[^\s/$.?#].[^\s]*$/i.test(trimmedUrl)) {
    errors.website = "Must be a valid URL starting with http:// or https://";
  }

  const trimmedEmail = (formData.support_email || "").trim();
  if (trimmedEmail && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(trimmedEmail)) {
    errors.support_email = "Must be a valid email address (e.g. careers@company.com)";
  }

  if (formData.display_name && formData.display_name.length > 100) {
    errors.display_name = "Display name cannot exceed 100 characters";
  }

  const handleChange = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleSave = async (e) => {
    if (e) e.preventDefault();
    if (!isAdmin) {
      toast.error("Only administrators can update organization settings");
      return;
    }

    if (errors.brand_color) {
      toast.error(errors.brand_color);
      return;
    }
    if (errors.website) {
      toast.error(errors.website);
      return;
    }
    if (errors.support_email) {
      toast.error(errors.support_email);
      return;
    }
    if (errors.display_name) {
      toast.error(errors.display_name);
      return;
    }

    setSaving(true);
    try {
      const res = await updateSection("company", formData);
      if (res.success) {
        setSavedSettings(formData);
      }
    } catch (err) {
      toast.error(err.response?.data?.error || "Failed to save company settings");
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
      const res = await resetSection("company");
      if (res.success) {
        setFormData(DEFAULT_COMPANY);
        setSavedSettings(DEFAULT_COMPANY);
      }
    } catch (err) {
      toast.error("Failed to reset settings");
    } finally {
      setSaving(false);
    }
  };

  const handleLogoUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > 1024 * 1024) {
      toast.error("Logo file must be smaller than 1 MB");
      return;
    }

    if (!["image/png", "image/jpeg", "image/jpg"].includes(file.type)) {
      toast.error("Logo must be a PNG or JPG file");
      return;
    }

    const uploadData = new FormData();
    uploadData.append("logo", file);

    setUploadingLogo(true);
    try {
      const res = await settingsAPI.uploadLogo(uploadData);
      if (res.data?.success) {
        setFormData((prev) => ({ ...prev, logo: res.data.logo }));
        toast.success("Logo uploaded successfully");
      } else {
        toast.error(res.data?.error || "Failed to upload logo");
      }
    } catch (err) {
      toast.error(err.response?.data?.error || "Failed to upload logo");
    } finally {
      setUploadingLogo(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleRemoveLogo = async () => {
    setUploadingLogo(true);
    try {
      const res = await settingsAPI.deleteLogo();
      if (res.data?.success) {
        setFormData((prev) => ({ ...prev, logo: "" }));
        toast.success("Logo removed");
      }
    } catch (err) {
      toast.error("Failed to remove logo");
    } finally {
      setUploadingLogo(false);
    }
  };

  const isValidColorPickerValue = isValidHex && trimmedHex.length === 7;

  return (
    <form onSubmit={handleSave}>
      <SettingsSection
        title="Company Profile & Employer Brand"
        description="Customize your organization's public brand identity, logo, and theme color for candidate interviews and email notifications."
        isDirty={isDirty}
        onSave={handleSave}
        onReset={handleReset}
        saving={saving}
        loading={loading}
      >
        <div className="space-y-8 max-w-2xl">
          {/* Organization Details */}
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-ink-500 uppercase tracking-wider flex items-center gap-2">
              <Building2 size={16} className="text-ledger-500" />
              General Information
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Input
                label="Public Display Name"
                placeholder="e.g. Acme Corporation"
                value={formData.display_name}
                onChange={(e) => handleChange("display_name", e.target.value)}
                disabled={!isAdmin}
                error={errors.display_name}
              />
              <Input
                label="Support / Careers Email"
                placeholder="careers@acme.com"
                type="email"
                icon={Mail}
                value={formData.support_email}
                onChange={(e) => handleChange("support_email", e.target.value)}
                disabled={!isAdmin}
                error={errors.support_email}
              />
            </div>

            <Input
              label="Company Website"
              placeholder="https://www.acme.com"
              type="url"
              icon={Globe}
              value={formData.website}
              onChange={(e) => handleChange("website", e.target.value)}
              disabled={!isAdmin}
              error={errors.website}
            />
          </div>

          <hr className="border-stone-200" />

          {/* Logo Upload */}
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-ink-500 uppercase tracking-wider flex items-center gap-2">
              <Image size={16} className="text-ledger-500" />
              Company Logo
            </h3>
            <p className="text-xs text-stone-500">
              Your logo is displayed in candidate email invitations and at the top of the AI interview portal.
              Allowed formats: PNG, JPG (Max 1 MB).
            </p>

            <div className="flex items-center gap-6">
              {formData.logo ? (
                <div className="relative group p-3 bg-stone-50 border border-stone-200 rounded-xl flex items-center justify-center min-w-[140px] h-24">
                  <img
                    src={formData.logo}
                    alt="Company Logo Preview"
                    className="max-h-16 max-w-[160px] object-contain"
                  />
                  {isAdmin && (
                    <button
                      type="button"
                      onClick={handleRemoveLogo}
                      disabled={uploadingLogo}
                      title="Remove Logo"
                      className="absolute -top-2 -right-2 bg-rose-600 text-white p-1 rounded-full shadow-md hover:bg-rose-700 transition-colors cursor-pointer"
                    >
                      <Trash2 size={13} />
                    </button>
                  )}
                </div>
              ) : (
                <div className="w-32 h-24 border-2 border-dashed border-stone-300 rounded-xl flex flex-col items-center justify-center text-stone-400 bg-stone-50">
                  <Upload size={20} className="mb-1" />
                  <span className="text-[11px] font-medium">No Logo</span>
                </div>
              )}

              {isAdmin && (
                <div>
                  <input
                    type="file"
                    ref={fileInputRef}
                    accept="image/png,image/jpeg"
                    onChange={handleLogoUpload}
                    className="hidden"
                    id="logo-upload-input"
                  />
                  <label htmlFor="logo-upload-input">
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      loading={uploadingLogo}
                      onClick={() => fileInputRef.current?.click()}
                      className="cursor-pointer"
                    >
                      <Upload size={14} className="mr-1.5" />
                      {formData.logo ? "Change Logo" : "Upload Logo"}
                    </Button>
                  </label>
                  <p className="text-[11px] text-stone-400 mt-1.5">
                    PNG or JPG up to 1 MB
                  </p>
                </div>
              )}
            </div>
          </div>

          <hr className="border-stone-200" />

          {/* Brand Theme Color */}
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-ink-500 uppercase tracking-wider flex items-center gap-2">
              <Palette size={16} className="text-ledger-500" />
              Brand Theme Color
            </h3>
            <p className="text-xs text-stone-500">
              Selected accent color is applied to candidate invitation call-to-actions and the interview portal controls.
            </p>

            <div>
              <div className="flex items-center gap-3">
                <input
                  type="color"
                  value={isValidColorPickerValue ? formData.brand_color : "#4f46e5"}
                  onChange={(e) => handleChange("brand_color", e.target.value)}
                  disabled={!isAdmin}
                  className="w-10 h-10 rounded-xl cursor-pointer border border-stone-300 p-0.5 bg-white shrink-0"
                />
                <div className="w-36">
                  <Input
                    label=""
                    value={formData.brand_color}
                    onChange={(e) => handleChange("brand_color", e.target.value)}
                    placeholder="#4F46E5"
                    disabled={!isAdmin}
                    error={errors.brand_color}
                    className="font-mono uppercase text-xs"
                  />
                </div>

                <div className="flex items-center gap-1.5 ml-2">
                  {COLOR_PRESETS.map((color) => (
                    <button
                      key={color}
                      type="button"
                      onClick={() => isAdmin && handleChange("brand_color", color)}
                      style={{ backgroundColor: color }}
                      title={color}
                      className={`w-6 h-6 rounded-full border-2 transition-transform cursor-pointer ${
                        (formData.brand_color || "").toLowerCase() === color.toLowerCase()
                          ? "scale-125 border-ink-600 shadow-sm"
                          : "border-white hover:scale-110"
                      }`}
                    />
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Live Preview Card */}
          <div className="bg-stone-50 border border-stone-200 rounded-xl p-4 space-y-2">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-stone-600 uppercase tracking-wider">
              <Eye size={14} />
              <span>Candidate Experience Preview</span>
            </div>
            <div className="p-4 bg-white border border-stone-200 rounded-lg shadow-sm flex items-center justify-between">
              <div className="flex items-center gap-3">
                {formData.logo ? (
                  <img src={formData.logo} alt="Preview" className="h-8 max-w-[120px] object-contain" />
                ) : (
                  <div className="w-8 h-8 rounded-lg bg-stone-200 flex items-center justify-center font-bold text-xs text-ink-600">
                    {(formData.display_name || "R").charAt(0).toUpperCase()}
                  </div>
                )}
                <div>
                  <h4 className="text-sm font-bold text-ink-600">
                    {formData.display_name || "RecruitMate AI"}
                  </h4>
                  <p className="text-xs text-stone-400">Software Engineer Interview</p>
                </div>
              </div>
              <button
                type="button"
                style={{ backgroundColor: isValidHex ? formData.brand_color : "#4f46e5" }}
                className="text-white text-xs font-semibold px-3 py-1.5 rounded-lg shadow-sm transition-colors"
              >
                Start Interview
              </button>
            </div>
          </div>
        </div>
      </SettingsSection>
    </form>
  );
}
