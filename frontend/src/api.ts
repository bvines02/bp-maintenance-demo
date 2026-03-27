import axios from "axios";

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000" });

export const getAssetSummary = () => api.get("/assets/summary").then(r => r.data);
export const getAssets = (params?: Record<string, string>) => api.get("/assets/", { params }).then(r => r.data);
export const getWorkOrderSummary = () => api.get("/workorders/summary").then(r => r.data);
export const getWorkOrders = (params?: Record<string, string>) => api.get("/workorders/", { params }).then(r => r.data);
export const getCostSummary = () => api.get("/analysis/cost-summary").then(r => r.data);
export const getDutyStandbyOpportunities = () => api.get("/analysis/duty-standby").then(r => r.data);
export const getDeferralOpportunities = () => api.get("/analysis/deferral-opportunities").then(r => r.data);
export const getDeferralSummary = () => api.get("/analysis/deferral-summary").then(r => r.data);
export const getAllOpportunities = () => api.get("/analysis/optimisation-opportunities").then(r => r.data);
export const getCorrectiveSummary = () => api.get("/analysis/corrective-summary").then(r => r.data);
export const getH1_1 = () => api.get("/analysis/hypothesis/h1-1").then(r => r.data);
export const getH1_2 = () => api.get("/analysis/hypothesis/h1-2").then(r => r.data);
export const getH1_3 = () => api.get("/analysis/hypothesis/h1-3").then(r => r.data);
export const sendChat = (messages: { role: string; content: string }[]) =>
  api.post("/chat/", { messages }).then(r => r.data);
