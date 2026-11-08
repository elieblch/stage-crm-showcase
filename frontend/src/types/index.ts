// Types miroir des schemas Pydantic (backend).

export type DocType = "cv" | "lm";

export interface DocumentItem {
  id: number;
  doc_type: DocType;
  label: string;
  original_filename: string;
  file_size: number;
  created_at: string;
}

// Infos document exposées sur les fiches offre / contact.
export interface DocumentBrief {
  id: number;
  doc_type: DocType;
  label: string;
  original_filename: string;
}

export type OfferPriority = "haute" | "moyenne" | "basse";

export type OfferStatus =
  | "a_postuler"
  | "postule"
  | "relance"
  | "entretien"
  | "offre_recue"
  | "refuse"
  | "sans_suite";

export type ContactStatus =
  | "a_contacter"
  | "contacte"
  | "relance"
  | "repondu"
  | "rdv_obtenu"
  | "sans_suite";

export interface Offer {
  id: number;
  title: string;
  company: string;
  location: string | null;
  url: string | null;
  source: string | null;
  priority: OfferPriority;
  status: OfferStatus;
  date_added: string;
  date_applied: string | null;
  deadline: string | null;
  cv_document_id: number | null;
  lm_document_id: number | null;
  cv_document: DocumentBrief | null;
  lm_document: DocumentBrief | null;
  last_action_date: string;
  next_relance_date: string | null;
  no_relance: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
  needs_relance: boolean;
  days_overdue: number | null;
}

export type OfferInput = Partial<
  Pick<
    Offer,
    | "title"
    | "company"
    | "location"
    | "url"
    | "source"
    | "priority"
    | "status"
    | "date_added"
    | "date_applied"
    | "deadline"
    | "next_relance_date"
    | "no_relance"
    | "notes"
    | "cv_document_id"
    | "lm_document_id"
  >
>;

export interface Contact {
  id: number;
  name: string;
  role: string | null;
  company: string | null;
  email: string | null;
  linkedin_url: string | null;
  phone: string | null;
  offer_id: number | null;
  status: ContactStatus;
  date_first_contact: string | null;
  cv_document_id: number | null;
  lm_document_id: number | null;
  cv_document: DocumentBrief | null;
  lm_document: DocumentBrief | null;
  last_action_date: string;
  next_relance_date: string | null;
  no_relance: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
  needs_relance: boolean;
  days_overdue: number | null;
}

export type ContactInput = Partial<
  Pick<
    Contact,
    | "name"
    | "role"
    | "company"
    | "email"
    | "linkedin_url"
    | "phone"
    | "offer_id"
    | "status"
    | "date_first_contact"
    | "next_relance_date"
    | "no_relance"
    | "notes"
    | "cv_document_id"
    | "lm_document_id"
  >
>;

// ─── Activities (timeline) ────────────────────────────────
export type ActivityType =
  | "applied"
  | "relance"
  | "response_received"
  | "interview_scheduled"
  | "interview_done"
  | "offer_received"
  | "rejected"
  | "contacted"
  | "replied"
  | "meeting_scheduled"
  | "meeting_done"
  | "note"
  | "status_change"
  | "other";

export interface Activity {
  id: number;
  offer_id: number | null;
  contact_id: number | null;
  activity_type: ActivityType;
  event_date: string;
  note: string | null;
  document_id: number | null;
  document: DocumentBrief | null;
  created_at: string;
}

export interface ActivityInput {
  activity_type: ActivityType;
  event_date: string;
  note?: string | null;
  document_id?: number | null;
}

export interface InterviewStory {
  id: number;
  title: string;
  situation: string;
  task: string;
  action: string;
  result: string;
  source: string | null;
  reflection: string | null;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface StoryInput {
  title: string;
  situation: string;
  task: string;
  action: string;
  result: string;
  source?: string | null;
  reflection?: string | null;
  tags: string[];
}

// ─── Interviews (rounds d'entretien sous une offre) ───────
export type InterviewFormat = "visio" | "onsite" | "phone";

export type InterviewOutcome = "pending" | "passed" | "rejected" | "pending_next";

// Story STAR exposée en résumé sur une fiche entretien.
export interface StoryBrief {
  id: number;
  title: string;
}

export interface Interview {
  id: number;
  offer_id: number;
  round_label: string;
  scheduled_at: string | null;
  interviewer: string | null;
  format: InterviewFormat | null;
  questions: string | null;
  feeling: string | null;
  next_step: string | null;
  outcome: InterviewOutcome;
  created_at: string;
  updated_at: string;
  stories: StoryBrief[];
}

export interface InterviewInput {
  round_label: string;
  scheduled_at?: string | null;
  interviewer?: string | null;
  format?: InterviewFormat | null;
  questions?: string | null;
  feeling?: string | null;
  next_step?: string | null;
  outcome?: InterviewOutcome;
}

export interface AppSettings {
  relance_delay_days: number;
}

export interface RelanceItem {
  kind: "offer" | "contact";
  id: number;
  title: string;
  company: string | null;
  status: string;
  days_overdue: number;
  due_date: string;
}

export interface DeadlineItem {
  id: number;
  title: string;
  company: string;
  deadline: string;
  days_left: number;
}

export interface RelancesResponse {
  relances: RelanceItem[];
  deadlines: DeadlineItem[];
}

export interface Dashboard {
  offers_by_status: Record<OfferStatus, number>;
  contacts_by_status: Record<ContactStatus, number>;
  offers_total: number;
  contacts_total: number;
  relances_due: number;
  deadlines_soon: number;
}

// ─── Statistiques / funnel ────────────────────────────────
export interface FunnelStage {
  key: string;
  label: string;
  count: number;
}

export interface FunnelStats {
  stages: FunnelStage[];
}

export interface ResponseRateStats {
  applied_count: number;
  responded_count: number;
  response_rate: number | null;
  avg_time_to_response_days: number | null;
}

export interface CvStatItem {
  document_id: number;
  label: string;
  applied_count: number;
  responded_count: number;
  response_rate: number | null;
}

export interface ByCvStats {
  items: CvStatItem[];
}

export interface WeeklyActivityItem {
  week: string;
  week_start: string;
  applied: number;
  relance: number;
}

export interface WeeklyActivityStats {
  weeks: WeeklyActivityItem[];
}

export interface OutreachStats {
  contacted_count: number;
  replied_count: number;
  reply_rate: number | null;
}

// ─── Agenda ───────────────────────────────────────────────
export type AgendaKind = "relance" | "deadline" | "interview";

export interface AgendaItem {
  kind: AgendaKind;
  date: string;
  entity_type: "offer" | "contact";
  entity_id: number;
  label: string;
  company: string | null;
  title: string | null;
  status: string | null;
  note: string | null;
  overdue: boolean;
}

export interface AgendaResponse {
  days: number;
  items: AgendaItem[];
}
