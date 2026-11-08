"use client";

import { useState } from "react";
import { updateInterest, getUserId } from "@/lib/api";
import type { ApplicationStatus, MatchReasons, ScoringDimension } from "@/types";

// Mode mono-utilisateur : fallback sur l'ID hardcodé si localStorage pas encore hydraté.
const FALLBACK_USER_ID = "993ecd02-97da-47f5-bf56-b9adc3b82743";
export const resolveUserId = (): string => getUserId() || FALLBACK_USER_ID;

// ─── Constants ──────────────────────────────────────────────
export const PLAT: Record<string, string> = {
  welcome_to_the_jungle: "WTTJ",
  greenhouse: "Greenhouse",
  smartrecruiters: "SmartRecruiters",
  workday: "Workday",
  efinancialcareers: "eFinancialCareers",
  jobteaser: "JobTeaser",
};

export const STAT_LABEL: Record<string, string> = {
  draft: "Brouillon", ready: "Pret", sent: "Envoye",
  acknowledged: "Accuse reception", interview: "Entretien",
  offer: "Offre", accepted: "Accepte", rejected: "Refuse",
};

export const STAT_COLOR: Record<string, string> = {
  draft: "bg-gray-100 text-gray-600", ready: "bg-blue-50 text-blue-600",
  sent: "bg-emerald-50 text-emerald-600", acknowledged: "bg-teal-50 text-teal-600",
  interview: "bg-violet-50 text-violet-600", offer: "bg-amber-50 text-amber-700",
  accepted: "bg-green-50 text-green-700", rejected: "bg-red-50 text-red-600",
};

export const STAT_BG: Record<string, string> = {
  draft: "#888780", ready: "#378ADD", sent: "#1D9E75", acknowledged: "#5DCAA5",
  interview: "#7F77DD", offer: "#EF9F27", accepted: "#639922", rejected: "#E24B4A",
};

export const STAT_ORDER: ApplicationStatus[] = [
  "draft", "ready", "sent", "acknowledged", "interview", "offer", "accepted", "rejected",
];

export const DIM_LABEL: Record<ScoringDimension, string> = {
  domain: "Domaine", company: "Entreprise", location: "Localisation",
  skills: "Compétences", education: "Formation", quality: "Qualité offre",
  timing: "Timing", ai: "IA Claude",
};

export const DEFAULT_WEIGHTS: Record<ScoringDimension, number> = {
  domain: 20, company: 15, location: 10, skills: 20,
  education: 10, quality: 10, timing: 10, ai: 5,
};

export function scoreBadge(s: number) {
  return s >= 80 ? "score-high" : s >= 60 ? "score-medium" : "score-low";
}

/** Nettoie une description qui peut contenir du HTML brut ou des entités encodées */
export function cleanHtml(raw: string | null | undefined): string {
  if (!raw) return "";
  let t = raw;
  const el = typeof document !== "undefined" ? document.createElement("textarea") : null;
  if (el) { el.innerHTML = t; t = el.value; }
  if (el && (t.includes("&lt;") || t.includes("&gt;"))) { el.innerHTML = t; t = el.value; }
  t = t.replace(/<[^>]+>/g, " ");
  t = t.replace(/[\u00a0]+/g, " ").replace(/\s+/g, " ").trim();
  return t;
}

// ─── Card ──────────────────────────────────────────────
export function Card({ children, className = "", noPad = false, muted = false }: { children: React.ReactNode; className?: string; noPad?: boolean; muted?: boolean }) {
  const base = muted ? "bg-surface-100 border-transparent" : "bg-card border border-line";
  return <div className={`${base} rounded-card ${noPad ? "" : "p-5"} ${className}`}>{children}</div>;
}

export function CardHeader({ title, right }: { title: string; right?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between px-5 py-3.5 border-b border-line">
      <h3 className="text-[15px] font-semibold text-ink tracking-tight">{title}</h3>
      {right}
    </div>
  );
}

export function Field({ label, value, onChange, type = "text", placeholder }: { label: string; value: string; onChange: (v: string) => void; type?: string; placeholder?: string }) {
  return (
    <div>
      <label className="block text-xs font-medium text-ink-muted mb-1.5">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full px-3 py-2 border border-line rounded-input text-sm text-ink placeholder:text-ink-placeholder bg-card"
      />
    </div>
  );
}

export function Chevron({ open }: { open: boolean }) {
  return <svg className={`w-4 h-4 text-ink-faint transition-transform ${open ? "rotate-180" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 9l-7 7-7-7" /></svg>;
}

/** Spinner pulsant pour appel Claude — plus subtil qu'un spinner tournant. */
export function ClaudeThinking({ label = "Claude analyse…" }: { label?: string }) {
  return (
    <div className="inline-flex items-center gap-2.5 text-xs text-ink-muted claude-thinking">
      <div className="flex items-center gap-1">
        <span className="w-1 h-1 rounded-full bg-brand-400" />
        <span className="w-1 h-1 rounded-full bg-brand-400" />
        <span className="w-1 h-1 rounded-full bg-brand-400" />
      </div>
      <span>{label}</span>
    </div>
  );
}

// ─── Shared UI ──────────────────────────────────────────────
export function InterestBtn({ id, v, onChange }: { id: string; v: string; onChange?: (v: string) => void }) {
  const [st, setSt] = useState(v);
  const toggle = async (val: "interested" | "not_interested") => {
    const nv = st === val ? "new" : val;
    try { await updateInterest(id, nv); setSt(nv); onChange?.(nv); } catch {}
  };
  return (
    <div className="flex gap-0.5">
      <button onClick={(e) => { e.stopPropagation(); toggle("interested"); }} className={`p-1.5 rounded-lg transition-default ${st === "interested" ? "bg-brand-50 text-brand-400" : "text-gray-300 hover:text-brand-400 hover:bg-brand-50"}`}>
        <svg width="14" height="14" fill="currentColor" viewBox="0 0 20 20"><path d="M2 10.5a1.5 1.5 0 113 0v6a1.5 1.5 0 01-3 0v-6zM6 10.333v5.43a2 2 0 001.106 1.79l.05.025A4 4 0 008.943 18h5.416a2 2 0 001.962-1.608l1.2-6A2 2 0 0015.56 8H12V4a2 2 0 00-2-2 1 1 0 00-1 1v.667a4 4 0 01-.8 2.4L6.8 7.933a4 4 0 00-.8 2.4z" /></svg>
      </button>
      <button onClick={(e) => { e.stopPropagation(); toggle("not_interested"); }} className={`p-1.5 rounded-lg transition-default ${st === "not_interested" ? "bg-red-50 text-red-400" : "text-gray-300 hover:text-red-400 hover:bg-red-50"}`}>
        <svg width="14" height="14" fill="currentColor" viewBox="0 0 20 20"><path d="M18 9.5a1.5 1.5 0 11-3 0v-6a1.5 1.5 0 013 0v6zM14 9.667v-5.43a2 2 0 00-1.106-1.79l-.05-.025A4 4 0 0011.057 2H5.64a2 2 0 00-1.962 1.608l-1.2 6A2 2 0 004.44 12H8v4a2 2 0 002 2 1 1 0 001-1v-.667a4 4 0 01.8-2.4l1.4-1.866a4 4 0 00.8-2.4z" /></svg>
      </button>
    </div>
  );
}

export function ScoreDetail({ reasons }: { reasons: MatchReasons }) {
  // Multi-dim : affichage inline des dimensions fortes
  const dims = reasons?.dimensions;
  if (dims && typeof dims === "object") {
    const strong = Object.entries(dims)
      .filter(([, v]) => typeof v === "number" && (v as number) >= 70)
      .sort(([, a], [, b]) => (b as number) - (a as number))
      .slice(0, 2);
    if (strong.length === 0) return null;
    return (
      <span className="inline-flex items-center gap-1.5 ml-1">
        {strong.map(([k, v]) => (
          <span key={k} className="text-2xs text-gray-400" title={`${DIM_LABEL[k as ScoringDimension]} ${v}%`}>
            {DIM_LABEL[k as ScoringDimension]} {v}
          </span>
        ))}
      </span>
    );
  }
  // Legacy mono-dim : pref_score / cv_score
  const pref = (reasons as Record<string, unknown>)?.pref_score as number | undefined;
  const cv = (reasons as Record<string, unknown>)?.cv_score as number | undefined;
  if (pref == null && cv == null) return null;
  return (
    <span className="inline-flex items-center gap-1.5 ml-1">
      {pref != null && <span className="text-2xs text-gray-400" title="Score preferences">Pref {pref}%</span>}
      {cv != null && cv > 0 && <span className="text-2xs text-violet-400" title="Score matching CV">CV {cv}%</span>}
    </span>
  );
}

export function TagInput({ value, onChange, placeholder }: { value: string[]; onChange: (t: string[]) => void; placeholder?: string }) {
  const [input, setInput] = useState("");
  return (
    <div className="flex flex-wrap gap-1.5 p-2 border border-surface-200 rounded-button bg-white min-h-[38px] items-center focus-within:border-brand-400 focus-within:shadow-[0_0_0_3px_rgba(29,158,117,0.1)] transition-default">
      {value.map((t, i) => (
        <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 bg-brand-50 text-brand-600 rounded-pill text-xs font-medium">
          {t}<button type="button" onClick={() => onChange(value.filter((_, j) => j !== i))} className="text-brand-300 hover:text-brand-600">x</button>
        </span>
      ))}
      <input type="text" value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => {
        if (e.key === "Enter" && input.trim()) { e.preventDefault(); if (!value.includes(input.trim())) onChange([...value, input.trim()]); setInput(""); }
        if (e.key === "Backspace" && !input && value.length) onChange(value.slice(0, -1));
      }} placeholder={!value.length ? placeholder : ""} className="flex-1 min-w-[80px] text-sm outline-none bg-transparent" />
    </div>
  );
}
