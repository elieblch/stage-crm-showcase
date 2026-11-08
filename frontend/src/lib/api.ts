import axios from "axios";

import type {
  Activity,
  ActivityInput,
  AgendaResponse,
  AppSettings,
  ByCvStats,
  Contact,
  ContactInput,
  Dashboard,
  DocType,
  DocumentItem,
  FunnelStats,
  Interview,
  InterviewInput,
  InterviewStory,
  Offer,
  OfferInput,
  OutreachStats,
  RelancesResponse,
  ResponseRateStats,
  StoryInput,
  WeeklyActivityStats,
} from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL: `${API_BASE}/api/v1`,
  headers: { "Content-Type": "application/json" },
});

// URL absolue d'un fichier (téléchargement direct hors axios).
export const fileUrl = (path: string) => `${API_BASE}/api/v1${path}`;

// ─── Offers ───────────────────────────────────────────────
export const fetchOffers = (params?: {
  status?: string;
  priority?: string;
  needs_relance?: boolean;
}): Promise<Offer[]> => api.get("/offers", { params }).then((r) => r.data);

export const fetchOffer = (id: number): Promise<Offer> =>
  api.get(`/offers/${id}`).then((r) => r.data);

export const createOffer = (data: OfferInput): Promise<Offer> =>
  api.post("/offers", data).then((r) => r.data);

export const updateOffer = (id: number, data: OfferInput): Promise<Offer> =>
  api.put(`/offers/${id}`, data).then((r) => r.data);

export const deleteOffer = (id: number): Promise<void> =>
  api.delete(`/offers/${id}`).then(() => undefined);

export const markOfferRelanced = (id: number): Promise<Offer> =>
  api.post(`/offers/${id}/mark-relanced`).then((r) => r.data);

export const fetchOfferContacts = (id: number): Promise<Contact[]> =>
  api.get(`/offers/${id}/contacts`).then((r) => r.data);

// ─── Documents (bibliothèque CV / LM) ─────────────────────
export const fetchDocuments = (docType?: DocType): Promise<DocumentItem[]> =>
  api.get("/documents", { params: docType ? { doc_type: docType } : {} }).then((r) => r.data);

export const uploadDocument = (
  docType: DocType,
  label: string,
  file: File
): Promise<DocumentItem> => {
  const fd = new FormData();
  fd.append("doc_type", docType);
  fd.append("label", label);
  fd.append("file", file);
  return api
    .post("/documents", fd, { headers: { "Content-Type": "multipart/form-data" } })
    .then((r) => r.data);
};

export const renameDocument = (id: number, label: string): Promise<DocumentItem> =>
  api.patch(`/documents/${id}`, { label }).then((r) => r.data);

export const deleteDocument = (id: number): Promise<{ affected: number }> =>
  api.delete(`/documents/${id}`).then((r) => r.data);

export const documentDownloadUrl = (id: number) => fileUrl(`/documents/${id}/download`);

// ─── Contacts ─────────────────────────────────────────────
export const fetchContacts = (params?: {
  status?: string;
  offer_id?: number;
  needs_relance?: boolean;
}): Promise<Contact[]> => api.get("/contacts", { params }).then((r) => r.data);

export const createContact = (data: ContactInput): Promise<Contact> =>
  api.post("/contacts", data).then((r) => r.data);

export const updateContact = (id: number, data: ContactInput): Promise<Contact> =>
  api.put(`/contacts/${id}`, data).then((r) => r.data);

export const deleteContact = (id: number): Promise<void> =>
  api.delete(`/contacts/${id}`).then(() => undefined);

export const markContactRelanced = (id: number): Promise<Contact> =>
  api.post(`/contacts/${id}/mark-relanced`).then((r) => r.data);

// ─── Activities (timeline) ────────────────────────────────
export const fetchOfferActivities = (offerId: number): Promise<Activity[]> =>
  api.get(`/offers/${offerId}/activities`).then((r) => r.data);

export const createOfferActivity = (offerId: number, data: ActivityInput): Promise<Activity> =>
  api.post(`/offers/${offerId}/activities`, data).then((r) => r.data);

export const fetchContactActivities = (contactId: number): Promise<Activity[]> =>
  api.get(`/contacts/${contactId}/activities`).then((r) => r.data);

export const createContactActivity = (
  contactId: number,
  data: ActivityInput
): Promise<Activity> =>
  api.post(`/contacts/${contactId}/activities`, data).then((r) => r.data);

export const deleteActivity = (id: number): Promise<void> =>
  api.delete(`/activities/${id}`).then(() => undefined);

// ─── Stories ──────────────────────────────────────────────
export const fetchStories = (tags?: string[]): Promise<InterviewStory[]> => {
  const params = new URLSearchParams();
  (tags || []).forEach((t) => params.append("tags", t));
  const qs = params.toString();
  return api.get(`/stories${qs ? `?${qs}` : ""}`).then((r) => r.data);
};

export const createStory = (data: StoryInput): Promise<InterviewStory> =>
  api.post("/stories", data).then((r) => r.data);

export const updateStory = (id: number, data: Partial<StoryInput>): Promise<InterviewStory> =>
  api.put(`/stories/${id}`, data).then((r) => r.data);

export const deleteStory = (id: number): Promise<void> =>
  api.delete(`/stories/${id}`).then(() => undefined);

// ─── Interviews (rounds d'entretien sous une offre) ───────
export const fetchOfferInterviews = (offerId: number): Promise<Interview[]> =>
  api.get(`/offers/${offerId}/interviews`).then((r) => r.data);

export const createInterview = (
  offerId: number,
  data: InterviewInput
): Promise<Interview> =>
  api.post(`/offers/${offerId}/interviews`, data).then((r) => r.data);

export const updateInterview = (
  id: number,
  data: Partial<InterviewInput>
): Promise<Interview> => api.patch(`/interviews/${id}`, data).then((r) => r.data);

export const deleteInterview = (id: number): Promise<void> =>
  api.delete(`/interviews/${id}`).then(() => undefined);

export const attachStoryToInterview = (
  interviewId: number,
  storyId: number
): Promise<Interview> =>
  api.post(`/interviews/${interviewId}/stories/${storyId}`).then((r) => r.data);

export const detachStoryFromInterview = (
  interviewId: number,
  storyId: number
): Promise<Interview> =>
  api.delete(`/interviews/${interviewId}/stories/${storyId}`).then((r) => r.data);

// ─── Settings ─────────────────────────────────────────────
export const fetchSettings = (): Promise<AppSettings> =>
  api.get("/settings").then((r) => r.data);

export const updateSettings = (data: Partial<AppSettings>): Promise<AppSettings> =>
  api.put("/settings", data).then((r) => r.data);

// ─── Relances & Dashboard ─────────────────────────────────
export const fetchRelances = (): Promise<RelancesResponse> =>
  api.get("/relances").then((r) => r.data);

export const fetchDashboard = (): Promise<Dashboard> =>
  api.get("/dashboard").then((r) => r.data);

// ─── Statistiques ─────────────────────────────────────────
export const fetchFunnel = (): Promise<FunnelStats> =>
  api.get("/stats/funnel").then((r) => r.data);

export const fetchResponseRate = (): Promise<ResponseRateStats> =>
  api.get("/stats/response-rate").then((r) => r.data);

export const fetchByCv = (): Promise<ByCvStats> =>
  api.get("/stats/by-cv").then((r) => r.data);

export const fetchWeeklyActivity = (weeks = 12): Promise<WeeklyActivityStats> =>
  api.get("/stats/weekly-activity", { params: { weeks } }).then((r) => r.data);

export const fetchOutreach = (): Promise<OutreachStats> =>
  api.get("/stats/outreach").then((r) => r.data);

// ─── Agenda ───────────────────────────────────────────────
export const fetchAgenda = (days = 30): Promise<AgendaResponse> =>
  api.get("/agenda", { params: { days } }).then((r) => r.data);

export const agendaIcsUrl = (days = 30) => fileUrl(`/agenda/export.ics?days=${days}`);
