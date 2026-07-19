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
  delete      : (candidateId)         => api.delete(`/candidates/detail/${candidateId}`)
};