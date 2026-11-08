"use client";

import { useState } from "react";
import type { ContactStatus, OfferPriority, OfferStatus } from "@/types";

// ─── Métadonnées statuts offres ───────────────────────────
export const OFFER_STATUS_ORDER: OfferStatus[] = [
  "a_postuler",
  "postule",
  "relance",
  "entretien",
  "offre_recue",
  "refuse",
  "sans_suite",
];

export const OFFER_STATUS_LABEL: Record<OfferStatus, string> = {
  a_postuler: "À postuler",
  postule: "Postulé",
  relance: "Relancé",
  entretien: "Entretien",
  offre_recue: "Offre reçue",
  refuse: "Refusé",
  sans_suite: "Sans suite",
};

export const OFFER_STATUS_BG: Record<OfferStatus, string> = {
  a_postuler: "#888780",
  postule: "#378ADD",
  relance: "#EF9F27",
  entretien: "#7F77DD",
  offre_recue: "#639922",
  refuse: "#E24B4A",
  sans_suite: "#A1A1AA",
};

export const OFFER_STATUS_PILL: Record<OfferStatus, string> = {
  a_postuler: "bg-gray-100 text-gray-600",
  postule: "bg-blue-50 text-blue-600",
  relance: "bg-amber-50 text-amber-700",
  entretien: "bg-violet-50 text-violet-600",
  offre_recue: "bg-green-50 text-green-700",
  refuse: "bg-red-50 text-red-600",
  sans_suite: "bg-gray-50 text-gray-400",
};

// ─── Métadonnées statuts contacts ─────────────────────────
export const CONTACT_STATUS_ORDER: ContactStatus[] = [
  "a_contacter",
  "contacte",
  "relance",
  "repondu",
  "rdv_obtenu",
  "sans_suite",
];

export const CONTACT_STATUS_LABEL: Record<ContactStatus, string> = {
  a_contacter: "À contacter",
  contacte: "Contacté",
  relance: "Relancé",
  repondu: "A répondu",
  rdv_obtenu: "RDV obtenu",
  sans_suite: "Sans suite",
};

export const CONTACT_STATUS_PILL: Record<ContactStatus, string> = {
  a_contacter: "bg-gray-100 text-gray-600",
  contacte: "bg-blue-50 text-blue-600",
  relance: "bg-amber-50 text-amber-700",
  repondu: "bg-teal-50 text-teal-600",
  rdv_obtenu: "bg-green-50 text-green-700",
  sans_suite: "bg-gray-50 text-gray-400",
};

// ─── Priorité ─────────────────────────────────────────────
export const PRIORITY_LABEL: Record<OfferPriority, string> = {
  haute: "Haute",
  moyenne: "Moyenne",
  basse: "Basse",
};

export const PRIORITY_PILL: Record<OfferPriority, string> = {
  haute: "bg-red-50 text-red-600",
  moyenne: "bg-amber-50 text-amber-700",
  basse: "bg-gray-100 text-gray-500",
};

export function fmtDate(d: string | null | undefined): string {
  if (!d) return "—";
  return new Date(d).toLocaleDateString("fr-FR", { day: "2-digit", month: "short", year: "numeric" });
}

// ─── Card ─────────────────────────────────────────────────
export function Card({
  children,
  className = "",
  noPad = false,
  muted = false,
}: {
  children: React.ReactNode;
  className?: string;
  noPad?: boolean;
  muted?: boolean;
}) {
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

// ─── Field ────────────────────────────────────────────────
export function Field({
  label,
  value,
  onChange,
  type = "text",
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  placeholder?: string;
}) {
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

export function SelectField<T extends string>({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: string }[];
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-ink-muted mb-1.5">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as T)}
        className="w-full px-3 py-2 border border-line rounded-input text-sm text-ink bg-card"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}

export function Chevron({ open }: { open: boolean }) {
  return (
    <svg
      className={`w-4 h-4 text-ink-faint transition-transform ${open ? "rotate-180" : ""}`}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
    >
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 9l-7 7-7-7" />
    </svg>
  );
}

// ─── Badge « relance nécessaire » ─────────────────────────
export function RelanceBadge({ daysOverdue }: { daysOverdue: number | null }) {
  return (
    <span className="inline-flex items-center gap-1 text-2xs px-2 py-0.5 bg-amber-50 text-amber-700 rounded-pill font-medium">
      <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
      Relance
      {daysOverdue != null && daysOverdue > 0 ? ` · ${daysOverdue}j` : ""}
    </span>
  );
}

// ─── TagInput ─────────────────────────────────────────────
export function TagInput({
  value,
  onChange,
  placeholder,
}: {
  value: string[];
  onChange: (t: string[]) => void;
  placeholder?: string;
}) {
  const [input, setInput] = useState("");
  return (
    <div className="flex flex-wrap gap-1.5 p-2 border border-surface-200 rounded-button bg-white min-h-[38px] items-center focus-within:border-brand-400 focus-within:shadow-[0_0_0_3px_rgba(29,158,117,0.1)] transition-default">
      {value.map((t, i) => (
        <span
          key={i}
          className="inline-flex items-center gap-1 px-2 py-0.5 bg-brand-50 text-brand-600 rounded-pill text-xs font-medium"
        >
          {t}
          <button
            type="button"
            onClick={() => onChange(value.filter((_, j) => j !== i))}
            className="text-brand-300 hover:text-brand-600"
          >
            ×
          </button>
        </span>
      ))}
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && input.trim()) {
            e.preventDefault();
            if (!value.includes(input.trim())) onChange([...value, input.trim()]);
            setInput("");
          }
          if (e.key === "Backspace" && !input && value.length) onChange(value.slice(0, -1));
        }}
        placeholder={!value.length ? placeholder : ""}
        className="flex-1 min-w-[80px] text-sm outline-none bg-transparent"
      />
    </div>
  );
}
