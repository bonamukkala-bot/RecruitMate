import api from "./axios";

export const pipelineAPI = {
  sendEmail          : (candidateId, data) => api.post(`/pipeline/send-email/${candidateId}`, data),
  evaluate           : (candidateId, data) => api.post(`/pipeline/evaluate/${candidateId}`, data),
  interviewStart     : (candidateId)       => api.post(`/pipeline/interview/start/${candidateId}`),
  interviewNext      : (data)              => api.post(`/pipeline/interview/next`, data),
  interviewClose     : (candidateId, data) => api.post(`/pipeline/interview/close/${candidateId}`, data),
  createInterviewLink: (candidateId)       => api.post(`/pipeline/interview/create/${candidateId}`),
  schedule           : (candidateId, data) => api.post(`/pipeline/schedule/${candidateId}`, data),
  getLogs            : (candidateId)       => api.get(`/pipeline/logs/${candidateId}`),
  scheduleOffline: (candidateId, data) => api.post(`/pipeline/schedule-offline/${candidateId}`, data),
};