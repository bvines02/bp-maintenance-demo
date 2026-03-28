import axios from "axios";

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL ?? "http://localhost:8000" });

const p = (platforms?: string) => platforms ? { platforms } : {};

export const getAssetSummary = (platforms?: string) => api.get("/assets/summary", { params: p(platforms) }).then(r => r.data);
export const getAssets = (params?: Record<string, string>, platforms?: string) =>
  api.get("/assets/", { params: { ...params, ...p(platforms) } }).then(r => r.data);
export const getWorkOrderSummary = (platforms?: string) => api.get("/workorders/summary", { params: p(platforms) }).then(r => r.data);
export const getWorkOrders = (params?: Record<string, string>, platforms?: string) =>
  api.get("/workorders/", { params: { ...params, ...p(platforms) } }).then(r => r.data);
export const getCostSummary = (platforms?: string) => api.get("/analysis/cost-summary", { params: p(platforms) }).then(r => r.data);
export const getDutyStandbyOpportunities = (platforms?: string) => api.get("/analysis/duty-standby", { params: p(platforms) }).then(r => r.data);
export const getDeferralOpportunities = (platforms?: string) => api.get("/analysis/deferral-opportunities", { params: p(platforms) }).then(r => r.data);
export const getDeferralSummary = (platforms?: string) => api.get("/analysis/deferral-summary", { params: p(platforms) }).then(r => r.data);
export const getAllOpportunities = (platforms?: string) => api.get("/analysis/optimisation-opportunities", { params: p(platforms) }).then(r => r.data);
export const getCorrectiveSummary = (platforms?: string) => api.get("/analysis/corrective-summary", { params: p(platforms) }).then(r => r.data);
export const getH1_1 = (platforms?: string, extra?: Record<string, unknown>) =>
  api.get("/analysis/hypothesis/h1-1", { params: { ...p(platforms), ...extra } }).then(r => r.data);
export const getH1_2 = (platforms?: string) => api.get("/analysis/hypothesis/h1-2", { params: p(platforms) }).then(r => r.data);
export const getH1_3 = (platforms?: string, extra?: Record<string, unknown>) =>
  api.get("/analysis/hypothesis/h1-3", { params: { ...p(platforms), ...extra } }).then(r => r.data);
export const getH2_1 = (platforms?: string, extra?: Record<string, unknown>) =>
  api.get("/analysis/hypothesis/h2-1", { params: { ...p(platforms), ...extra } }).then(r => r.data);
export const getH2_2 = (platforms?: string, extra?: Record<string, unknown>) =>
  api.get("/analysis/hypothesis/h2-2", { params: { ...p(platforms), ...extra } }).then(r => r.data);
export const getH2_3 = (platforms?: string, extra?: Record<string, unknown>) =>
  api.get("/analysis/hypothesis/h2-3", { params: { ...p(platforms), ...extra } }).then(r => r.data);
export const getH2_4 = (platforms?: string) => api.get("/analysis/hypothesis/h2-4", { params: p(platforms) }).then(r => r.data);
export const sendChat = (messages: { role: string; content: string }[]) =>
  api.post("/chat/", { messages }).then(r => r.data);
