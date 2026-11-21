import { createContext, useContext, useState, useEffect } from "react";
import { authAPI } from "../api/auth";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [company, setCompany]   = useState(null);
  const [loading, setLoading]   = useState(true);

  // ── Load from localStorage on mount ─────────────────────────────────────
  useEffect(() => {
    const token   = localStorage.getItem("token");
    const stored = localStorage.getItem("company");
    if (token && stored) {
      try {
        const parsed = JSON.parse(stored);
        setCompany({
          ...parsed,
          role: parsed.role || "owner"
        });
      } catch {
        setCompany(null);
      }
    }
    setLoading(false);
  }, []);

  // ── Login ────────────────────────────────────────────────────────────────
  const login = async (email, password, totpCode) => {
    const payload = { email, password };
    if (totpCode) payload.totp_code = totpCode;

    const res  = await authAPI.login(payload);
    const data = res.data;

    if (data.success) {
      const userObj = {
        company_id  : data.company_id,
        company_name: data.company_name,
        email,
        role        : data.role || "owner",
        user_id     : data.user_id || data.company_id,
        name        : data.name || ""
      };
      localStorage.setItem("token",   data.token);
      localStorage.setItem("company", JSON.stringify(userObj));
      setCompany(userObj);
    }
    return data;
  };

  // ── Register ─────────────────────────────────────────────────────────────
  const register = async (formData) => {
    const res = await authAPI.register(formData);
    return res.data;
  };

  // ── Verify OTP ───────────────────────────────────────────────────────────
  const verifyOTP = async (email, otp) => {
    const res  = await authAPI.verifyOTP({ email, otp });
    const data = res.data;
    if (data.success) {
      const userObj = {
        company_name: data.company_name,
        email,
        role        : "owner"
      };
      localStorage.setItem("token",   data.token);
      localStorage.setItem("company", JSON.stringify(userObj));
      setCompany(userObj);
    }
    return data;
  };

  // ── Logout ───────────────────────────────────────────────────────────────
  const logout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("company");
    setCompany(null);
  };

  return (
    <AuthContext.Provider value={{ company, loading, login, register, verifyOTP, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}