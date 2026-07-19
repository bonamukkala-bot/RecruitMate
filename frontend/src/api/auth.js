import api from "./axios";

export const authAPI = {
  register: (data) => api.post("/auth/register", data),
  verifyOTP: (data) => api.post("/auth/verify-otp", data),
  login: (data) => api.post("/auth/login", data),
  me: () => api.get("/auth/me")
};