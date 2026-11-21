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
  purgeExpired: (execute = false) => api.post("/privacy/purge-expired", { execute }),
  // Integrations endpoints
  testSlack: (webhook_url) => api.post("/integrations/slack/test", { webhook_url }),
  getWebhooks: () => api.get("/integrations/webhooks"),
  createWebhook: (data) => api.post("/integrations/webhooks", data),
  deleteWebhook: (id) => api.delete(`/integrations/webhooks/${id}`),
  testWebhook: (id) => api.post(`/integrations/webhooks/${id}/test`),
  getWebhookDeliveries: () => api.get("/integrations/webhooks/deliveries"),
  getApiKeys: () => api.get("/integrations/api-keys"),
  createApiKey: (data) => api.post("/integrations/api-keys", data),
  revokeApiKey: (id) => api.delete(`/integrations/api-keys/${id}`),
  getGoogleStatus: () => api.get("/integrations/google/status"),
  disconnectGoogle: () => api.post("/integrations/google/disconnect")
};
