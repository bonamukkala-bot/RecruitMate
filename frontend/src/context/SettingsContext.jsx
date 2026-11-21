import { createContext, useContext, useState, useEffect, useCallback } from "react";
import { settingsAPI } from "../api/settings";
import { useAuth } from "./AuthContext";
import toast from "react-hot-toast";

const SettingsContext = createContext(null);

export function SettingsProvider({ children }) {
  const { company } = useAuth();
  const [settings, setSettings] = useState(null);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState(null);

  const fetchSettings = useCallback(async () => {
    if (!company) {
      setSettings(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await settingsAPI.get();
      if (res.data.success) {
        setSettings(res.data.settings);
      } else {
        setError(res.data.error || "Failed to load settings");
      }
    } catch (err) {
      const msg = err.response?.data?.error || "Failed to load settings";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [company]);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  const updateSection = async (section, data) => {
    try {
      const res = await settingsAPI.updateSection(section, data);
      if (res.data.success) {
        setSettings((prev) => ({
          ...prev,
          [section]: res.data.data
        }));
        toast.success(res.data.message || `${section.toUpperCase()} settings saved`);
        return { success: true, data: res.data.data };
      } else {
        toast.error(res.data.error || "Failed to update settings");
        return { success: false, error: res.data.error };
      }
    } catch (err) {
      const msg = err.response?.data?.error || "Failed to update settings";
      toast.error(msg);
      return { success: false, error: msg };
    }
  };

  const resetSection = async (section) => {
    try {
      const res = await settingsAPI.resetSection(section);
      if (res.data.success) {
        setSettings((prev) => ({
          ...prev,
          [section]: res.data.data
        }));
        toast.success(res.data.message || `${section.toUpperCase()} settings reset to defaults`);
        return { success: true, data: res.data.data };
      } else {
        toast.error(res.data.error || "Failed to reset settings");
        return { success: false, error: res.data.error };
      }
    } catch (err) {
      const msg = err.response?.data?.error || "Failed to reset settings";
      toast.error(msg);
      return { success: false, error: msg };
    }
  };

  return (
    <SettingsContext.Provider
      value={{
        settings,
        loading,
        error,
        refreshSettings: fetchSettings,
        updateSection,
        resetSection
      }}
    >
      {children}
    </SettingsContext.Provider>
  );
}

export function useSettings() {
  const context = useContext(SettingsContext);
  if (!context) {
    throw new Error("useSettings must be used within a SettingsProvider");
  }
  return context;
}
