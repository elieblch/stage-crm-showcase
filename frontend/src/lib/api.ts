import axios from "axios";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL: `${API_BASE}/api/v1`,
  headers: {
    "Content-Type": "application/json",
  },
});

// ── User ID (single-user mode) ─────────────────────────
// En mode mono-utilisateur, on stocke l'ID dans localStorage
export const getUserId = (): string | null => {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("stage_crm_user_id");
};

export const setUserId = (id: string) => {
  localStorage.setItem("stage_crm_user_id", id);
};

// ── Dashboard ────────────────────────────────────────────
export const fetchDashboard = (userId: string) =>
  api.get(`/dashboard/${userId}`).then((r) => r.data);

// ── Préférences ──────────────────────────────────────────
export const fetchPreferences = (userId: string) =>
  api.get(`/users/${userId}/preferences`).then((r) => r.data);

export const updatePreferences = (userId: string, data: any) =>
  api.put(`/users/${userId}/preferences`, data).then((r) => r.data);

// ── Offres matchées ──────────────────────────────────────
export const fetchMatches = (userId: string, params?: Record<string, any>) =>
  api.get(`/users/${userId}/matches`, { params }).then((r) => r.data);

export const updateInterest = (matchId: string, interest: string) =>
  api.put(`/matches/${matchId}/interest`, null, { params: { interest } }).then((r) => r.data);

// ── Offres brutes ────────────────────────────────────────
export const fetchOffers = (params?: Record<string, any>) =>
  api.get(`/offers`, { params }).then((r) => r.data);

export const fetchOfferStats = () =>
  api.get(`/offers/stats`).then((r) => r.data);

// ── Scraping ─────────────────────────────────────────────
export const triggerScraping = () =>
  api.post(`/scraping/run`).then((r) => r.data);

export const scoreOffers = (userId: string) =>
  api.post(`/users/${userId}/score-offers/sync`).then((r) => r.data);

// ── Candidatures ─────────────────────────────────────────
export const fetchApplications = (userId: string, status?: string) =>
  api.get(`/users/${userId}/applications`, { params: { status } }).then((r) => r.data);

export const createApplication = (userId: string, offerId: string) =>
  api.post(`/users/${userId}/applications`, { offer_id: offerId }).then((r) => r.data);

export const updateApplication = (appId: string, data: any) =>
  api.put(`/applications/${appId}`, data).then((r) => r.data);

export const deleteApplication = (appId: string) =>
  api.delete(`/applications/${appId}`).then((r) => r.data);

// ── Génération IA ────────────────────────────────────────
export const generateCoverLetter = (appId: string) =>
  api.post(`/applications/${appId}/generate-cover-letter`).then((r) => r.data);

export const generateEmail = (appId: string, emailType: string = "candidature") =>
  api.post(`/applications/${appId}/generate-email`, null, { params: { email_type: emailType } }).then((r) => r.data);

export const generateInterviewPrep = (appId: string, interviewType: string = "general") =>
  api.post(`/applications/${appId}/generate-interview-prep`, null, { params: { interview_type: interviewType } }).then((r) => r.data);

export const suggestCvChanges = (appId: string) =>
  api.post(`/applications/${appId}/suggest-cv-changes`).then((r) => r.data);

// ── Documents ────────────────────────────────────────────
export const fetchDocuments = (userId: string) =>
  api.get(`/users/${userId}/documents`).then((r) => r.data);

export const uploadDocument = (userId: string, file: File, docType: string, title: string) => {
  const formData = new FormData();
  formData.append("file", file);
  return api
    .post(`/users/${userId}/documents`, formData, {
      params: { doc_type: docType, title },
      headers: { "Content-Type": "multipart/form-data" },
    })
    .then((r) => r.data);
};

// ── User ─────────────────────────────────────────────────
export const fetchUser = (userId: string) =>
  api.get(`/users/${userId}`).then((r) => r.data);

export const updateUser = (userId: string, data: any) =>
  api.put(`/users/${userId}`, data).then((r) => r.data);

export const deleteDocument = (userId: string, docId: string) =>
  api.delete(`/users/${userId}/documents/${docId}`).then((r) => r.data);

export const setDocumentPrimary = (userId: string, docId: string) =>
  api.put(`/users/${userId}/documents/${docId}/set-primary`).then((r) => r.data);

// ── Integrations ─────────────────────────────────────────
export const saveJobTeaserCookie = (userId: string, cookieValue: string, baseUrl: string) =>
  api.post(`/users/${userId}/integrations/jobteaser/cookie`, null, { params: { cookie_value: cookieValue, base_url: baseUrl } }).then((r) => r.data);

export const testJobTeaserCookie = (userId: string) =>
  api.post(`/users/${userId}/integrations/jobteaser/test`).then((r) => r.data);

export const jobTeaserStatus = (userId: string) =>
  api.get(`/users/${userId}/integrations/jobteaser/status`).then((r) => r.data);

export const disconnectJobTeaser = (userId: string) =>
  api.delete(`/users/${userId}/integrations/jobteaser`).then((r) => r.data);

export const fetchAlerts = (userId: string) =>
  api.get(`/users/${userId}/alerts`).then((r) => r.data);

// ── Story Bank (STAR) ────────────────────────────────────
import type { InterviewStory, StoryCreate, StoryUpdate } from "@/types";

export const fetchStories = (userId: string, tags?: string[]): Promise<InterviewStory[]> => {
  const params = new URLSearchParams();
  (tags || []).forEach((t) => params.append("tags", t));
  const qs = params.toString();
  return api.get(`/users/${userId}/stories${qs ? `?${qs}` : ""}`).then((r) => r.data);
};

export const createStory = (userId: string, data: StoryCreate): Promise<InterviewStory> =>
  api.post(`/users/${userId}/stories`, data).then((r) => r.data);

export const updateStory = (storyId: string, data: StoryUpdate): Promise<InterviewStory> =>
  api.put(`/stories/${storyId}`, data).then((r) => r.data);

export const deleteStory = (storyId: string): Promise<void> =>
  api.delete(`/stories/${storyId}`).then(() => undefined);

// ── Newsletter ───────────────────────────────────────────
export const sendNewsletterNow = (userId?: string) =>
  api.post(userId ? `/newsletter/send-now?user_id=${userId}` : `/newsletter/send-now`).then((r) => r.data);

// ── Search status (pause / resume) ───────────────────────
export const updateSearchStatus = (userId: string, isActive: boolean) =>
  api.put(`/users/${userId}/search-status`, { is_active: isActive }).then((r) => r.data);
