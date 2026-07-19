import api from "./axios";

export const jobsAPI = {
  // AI Generate JD from one line brief
  generateJD: (brief) => api.post("/jobs/generate-jd", { brief }),

  // Text-based JD creation
  create: (data) => api.post("/jobs/", data),

  // File-based JD creation (PDF or Word)
  createFromFile: (file) => {
    const formData = new FormData();
    formData.append("jd_file", file);
    return api.post("/jobs/", formData, {
      headers: { "Content-Type": "multipart/form-data" }
    });
  },

  getAll      : ()            => api.get("/jobs/"),
  getOne      : (id)          => api.get(`/jobs/${id}`),
  updateStatus: (id, status)  => api.patch(`/jobs/${id}/status`, { status }),
  delete      : (id)          => api.delete(`/jobs/${id}`),
  getAnalytics: () => api.get("/jobs/analytics")
};