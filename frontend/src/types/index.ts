// ══════════════════════════════════════════════════════════
// Types partagés — miroir des schemas Pydantic du backend
// ══════════════════════════════════════════════════════════

export interface User {
  id: string;
  email: string;
  full_name: string;
  phone?: string;
  linkedin_url?: string;
  is_active_search?: boolean;
  created_at: string;
}

export interface SearchPreferences {
  id: string;
  target_domains: string[];
  target_companies: string[];
  target_locations: string[];
  contract_types: string[];
  min_duration_months?: number;
  max_duration_months?: number;
  start_date_earliest?: string;
  start_date_latest?: string;
  min_salary?: number;
  keywords: string[];
  excluded_keywords: string[];
  newsletter_enabled: boolean;
  newsletter_time: string;
  min_match_score: number;
  scoring_weights?: ScoringWeights;
  updated_at: string;
}

export type ScoringDimension =
  | "domain" | "company" | "location" | "skills"
  | "education" | "quality" | "timing" | "ai";

export type ScoringWeights = Record<ScoringDimension, number>;

export interface MatchReasons {
  dimensions?: Partial<Record<ScoringDimension, number | null>>;
  weights?: Partial<ScoringWeights>;
  ia_scored?: boolean;
  local_score?: number;
  claude_score?: number;
  claude_highlights?: string[];
  claude_concerns?: string[];
  claude_sub_scores?: Partial<Record<ScoringDimension, number>>;
  [legacyKey: string]: unknown;
}

export interface Offer {
  id: string;
  title: string;
  company_name: string;
  company_logo_url?: string;
  location?: string;
  is_remote: boolean;
  domain?: string;
  contract_type?: string;
  duration_months?: number;
  start_date?: string;
  salary?: string;
  source_platform: string;
  source_url?: string;
  description?: string;
  required_skills: string[];
  contact_email?: string;
  created_at: string;
}

export interface OfferMatch {
  id: string;
  offer: Offer;
  match_score: number;
  match_reasons: MatchReasons;
  ai_summary?: string;
  user_interest: "new" | "interested" | "not_interested" | "applied";
  created_at: string;
}

export type ApplicationStatus =
  | "draft"
  | "ready"
  | "sent"
  | "acknowledged"
  | "interview"
  | "offer"
  | "accepted"
  | "rejected";

export interface Application {
  id: string;
  offer: Offer;
  status: ApplicationStatus;
  cover_letter_text?: string;
  email_draft?: string;
  applied_via?: string;
  applied_at?: string;
  recipient_email?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface Interview {
  id: string;
  interview_type?: string;
  scheduled_at?: string;
  duration_minutes: number;
  location?: string;
  interviewer_name?: string;
  interviewer_role?: string;
  prep_notes?: string;
  company_research?: string;
  common_questions?: string;
  feedback?: string;
  rating?: number;
  created_at: string;
}

export interface DashboardStats {
  total_offers_matched: number;
  new_today: number;
  applications_sent: number;
  interviews_scheduled: number;
  pending_follow_ups: number;
  pipeline: Record<ApplicationStatus, number>;
}

export interface UserDocument {
  id: string;
  doc_type: "cv" | "bulletin" | "projet" | "certification" | "lettre_ref" | "lettre_motivation";
  title: string;
  is_primary: boolean;
  uploaded_at: string;
  extracted_text?: string;
  file_path?: string;
}

export interface InterviewStory {
  id: string;
  user_id: string;
  title: string;
  situation: string;
  task: string;
  action: string;
  result: string;
  reflection?: string;
  tags: string[];
  source?: string;
  used_in_interviews: string[];
  created_at: string;
  updated_at: string;
}

export type StoryCreate = Omit<InterviewStory, "id" | "user_id" | "used_in_interviews" | "created_at" | "updated_at">;
export type StoryUpdate = Partial<StoryCreate> & { used_in_interviews?: string[] };

// Pipeline columns pour le kanban
export const PIPELINE_COLUMNS: { key: ApplicationStatus; label: string; color: string }[] = [
  { key: "draft", label: "Brouillon", color: "#888780" },
  { key: "ready", label: "Prêt à envoyer", color: "#378ADD" },
  { key: "sent", label: "Envoyé", color: "#1d9e75" },
  { key: "acknowledged", label: "Accusé réception", color: "#5DCAA5" },
  { key: "interview", label: "Entretien", color: "#7F77DD" },
  { key: "offer", label: "Offre reçue", color: "#EF9F27" },
  { key: "accepted", label: "Accepté", color: "#639922" },
  { key: "rejected", label: "Refusé", color: "#E24B4A" },
];
