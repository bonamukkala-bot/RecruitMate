import api from "./axios";

export const authAPI = {
  register: (data) => api.post("/auth/register", data),
  verifyOTP: (data) => api.post("/auth/verify-otp", data),
  resendOTP: (data) => api.post("/auth/resend-otp", data),
  login: (data) => api.post("/auth/login", data),
  me: () => api.get("/auth/me"),
  setup2FA: () => api.post("/auth/2fa/setup"),
  enable2FA: (code) => api.post("/auth/2fa/enable", { code }),
  get2FAStatus: () => api.get("/auth/2fa/status"),
  disable2FA: (password) => api.post("/auth/2fa/disable", { password }),
  verifyInvite: (token) => api.get(`/auth/verify-invite?token=${encodeURIComponent(token)}`),
  acceptInvite: (data) => api.post("/auth/accept-invite", data)
};