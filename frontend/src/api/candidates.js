import api from "./axios";

export const candidatesAPI = {
  // Text-based screening
  screen: (jobId, data) => api.post(`/candidates/${jobId}/screen`, data),

  // File-based resume screening
  screenFromFile: (jobId, file, candidateName, candidateEmail) => {
    const formData = new FormData();
    formData.append("resume_file",     file);
    formData.append("candidate_name",  candidateName);
    formData.append("candidate_email", candidateEmail);
    return api.post(`/candidates/${jobId}/screen`, formData, {
      headers: { "Content-Type": "multipart/form-data" }
    });
  },

  getAll      : ()                     => api.get("/candidates/"),
  getAllByJob  : (jobId)               => api.get(`/candidates/${jobId}`),
  getOne      : (candidateId)         => api.get(`/candidates/detail/${candidateId}`),
  updateStatus: (candidateId, status) => api.patch(`/candidates/detail/${candidateId}/status`, { status }),
  delete      : (candidateId)         => api.delete(`/candidates/detail/${candidateId}`),

  // Smart Candidate Search — params: { skill, status, min_score, max_score, date_from, date_to }
  search: (params) => api.get("/candidates/search", { params }),

  // CSV export — same params as search, returns a raw file blob
  exportCSV: (params) => api.get("/candidates/export", { params, responseType: "blob" }),

  // Candidate Comparison Tool — pass 2-3 candidate ids
  compare: (candidateIds) => api.post("/candidates/compare", { candidate_ids: candidateIds })
};