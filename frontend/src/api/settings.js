import api from "./axios";

export const settingsAPI = {
  get: () => api.get("/settings"),
  updateSection: (section, data) => api.put(`/settings/${section}`, data),
  resetSection: (section) => api.post(`/settings/${section}/reset`)
};
