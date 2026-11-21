import api from "./axios";

export const settingsAPI = {
  get: () => api.get("/settings"),
  updateSection: (section, data) => api.put(`/settings/${section}`, data),
  resetSection: (section) => api.post(`/settings/${section}/reset`),
  previewEmail: (data) => api.post("/settings/email/preview", data),
  sendTestEmail: (data) => api.post("/settings/email/send-test", data),
  getAIUsage: () => api.get("/settings/ai/usage"),
  getTeamMembers: () => api.get("/settings/team/members"),
  inviteMember: (data) => api.post("/settings/team/invite", data),
  updateMemberRole: (memberId, role) => api.patch(`/settings/team/members/${memberId}/role`, { role }),
  updateMemberStatus: (memberId, status) => api.patch(`/settings/team/members/${memberId}/status`, { status }),
  resendInvite: (memberId) => api.post(`/settings/team/members/${memberId}/resend-invite`),
  removeMember: (memberId) => api.delete(`/settings/team/members/${memberId}`),
  getAuditLogs: (page = 1, limit = 50) => api.get(`/settings/team/activity?page=${page}&limit=${limit}`),
  uploadLogo: (formData) => api.post("/settings/company/logo", formData, { headers: { "Content-Type": "multipart/form-data" } }),
  deleteLogo: () => api.delete("/settings/company/logo"),
  purgeExpired: (execute = false) => api.post("/privacy/purge-expired", { execute })
};
