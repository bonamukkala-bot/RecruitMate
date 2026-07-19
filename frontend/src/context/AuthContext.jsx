import { createContext, useContext, useState, useEffect } from "react";
import { authAPI } from "../api/auth";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [company, setCompany]   = useState(null);
  const [loading, setLoading]   = useState(true);

  // ── Load from localStorage on mount ─────────────────────────────────────
  useEffect(() => {
    const token   = localStorage.getItem("token");
    const company = localStorage.getItem("company");
    if (token && company) {
      setCompany(JSON.parse(company));
    }
    setLoading(false);
  }, []);

  // ── Login ────────────────────────────────────────────────────────────────
  const login = async (email, password) => {
    const res  = await authAPI.login({ email, password });
    const data = res.data;
    if (data.success) {
      localStorage.setItem("token",   data.token);
      localStorage.setItem("company", JSON.stringify({
        company_id  : data.company_id,
        company_name: data.company_name,
        email
      }));
      setCompany({
        company_id  : data.company_id,
        company_name: data.company_name,
        email
      });
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
      localStorage.setItem("token",   data.token);
      localStorage.setItem("company", JSON.stringify({
        company_name: data.company_name,
        email
      }));
      setCompany({ company_name: data.company_name, email });
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