// Parsing déterministe « Ajout rapide » — 100 % local, aucune IA, aucun appel réseau.
// Colle un bloc JSON structuré (offer | contact) → pré-remplit le bon formulaire.

import type { ContactInput, OfferInput } from "@/types";

const OFFER_STATUSES = [
  "a_postuler",
  "postule",
  "relance",
  "entretien",
  "offre_recue",
  "refuse",
  "sans_suite",
] as const;
const OFFER_PRIORITIES = ["haute", "moyenne", "basse"] as const;
const CONTACT_STATUSES = [
  "a_contacter",
  "contacte",
  "relance",
  "repondu",
  "rdv_obtenu",
  "sans_suite",
] as const;

const DEFAULT_OFFER_STATUS = "a_postuler";
const DEFAULT_OFFER_PRIORITY = "moyenne";
const DEFAULT_CONTACT_STATUS = "a_contacter";

export type QuickAddResult =
  | { ok: true; kind: "offer"; fields: OfferInput; warnings: string[] }
  | { ok: true; kind: "contact"; fields: ContactInput; warnings: string[] }
  | { ok: false; error: string };

// ─── Helpers ──────────────────────────────────────────────
/** Retire un éventuel encadrement ```json … ``` autour du bloc. */
function stripFences(text: string): string {
  const t = text.trim();
  const m = t.match(/^```[a-zA-Z0-9]*\s*\n?([\s\S]*?)\n?```$/);
  return m ? m[1].trim() : t;
}

/** Chaîne nettoyée, ou undefined si vide/absente/non-string (champ ignoré). */
function cleanStr(raw: unknown): string | undefined {
  if (typeof raw !== "string") return undefined;
  const t = raw.trim();
  return t.length ? t : undefined;
}

function normalizeEnum<T extends string>(
  raw: unknown,
  allowed: readonly T[],
  def: T,
  field: string,
  warnings: string[]
): T {
  if (raw === undefined || raw === null) return def; // absent : défaut silencieux
  if (typeof raw !== "string" || raw.trim() === "") {
    warnings.push(`${field} vide → valeur par défaut « ${def} ».`);
    return def;
  }
  const v = raw.trim();
  if (!(allowed as readonly string[]).includes(v)) {
    warnings.push(`${field} « ${v} » invalide → valeur par défaut « ${def} ».`);
    return def;
  }
  return v as T;
}

/** Parse de date tolérant → ISO yyyy-mm-dd, ou null si non reconnaissable. */
function parseDateTolerant(raw: unknown): string | null {
  if (typeof raw !== "string") return null;
  const s = raw.trim();
  if (!s) return null;
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s; // déjà ISO
  // jj/mm/aaaa ou jj-mm-aaaa
  const dmy = s.match(/^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$/);
  if (dmy) {
    const [, d, m, y] = dmy;
    const iso = `${y}-${m.padStart(2, "0")}-${d.padStart(2, "0")}`;
    return Number.isNaN(Date.parse(iso)) ? null : iso;
  }
  // Dernier recours : parsing natif (ex. « June 30, 2026 »).
  const ts = Date.parse(s);
  if (Number.isNaN(ts)) return null;
  return new Date(ts).toISOString().slice(0, 10);
}

// ─── Fonction principale ──────────────────────────────────
export function parseQuickAdd(text: string): QuickAddResult {
  if (typeof text !== "string" || !text.trim()) {
    return { ok: false, error: "Bloc vide : collez un JSON { \"type\": \"offer\" | \"contact\", … }." };
  }

  let obj: unknown;
  try {
    obj = JSON.parse(stripFences(text));
  } catch {
    return { ok: false, error: "JSON invalide : vérifiez la syntaxe du bloc collé." };
  }

  if (obj === null || typeof obj !== "object" || Array.isArray(obj)) {
    return { ok: false, error: "Le bloc doit être un objet JSON." };
  }

  const rec = obj as Record<string, unknown>;
  const type = typeof rec.type === "string" ? rec.type.trim().toLowerCase() : "";

  if (type === "offer") return parseOffer(rec);
  if (type === "contact") return parseContact(rec);
  return {
    ok: false,
    error: 'Champ "type" manquant ou inconnu (attendu : "offer" ou "contact").',
  };
}

function parseOffer(rec: Record<string, unknown>): QuickAddResult {
  const warnings: string[] = [];
  const fields: OfferInput = {
    priority: normalizeEnum(rec.priority, OFFER_PRIORITIES, DEFAULT_OFFER_PRIORITY, "Priorité", warnings),
    status: normalizeEnum(rec.status, OFFER_STATUSES, DEFAULT_OFFER_STATUS, "Statut", warnings),
  };

  const title = cleanStr(rec.title);
  if (title) fields.title = title;
  const company = cleanStr(rec.company);
  if (company) fields.company = company;
  const location = cleanStr(rec.location);
  if (location) fields.location = location;
  const url = cleanStr(rec.url);
  if (url) fields.url = url;
  const source = cleanStr(rec.source);
  if (source) fields.source = source;
  const notes = cleanStr(rec.notes);
  if (notes) fields.notes = notes;

  if (cleanStr(rec.deadline) !== undefined) {
    const dl = parseDateTolerant(rec.deadline);
    if (dl) fields.deadline = dl;
    else warnings.push("Deadline non reconnue → ignorée.");
  }

  return { ok: true, kind: "offer", fields, warnings };
}

function parseContact(rec: Record<string, unknown>): QuickAddResult {
  const warnings: string[] = [];
  const fields: ContactInput = {
    status: normalizeEnum(rec.status, CONTACT_STATUSES, DEFAULT_CONTACT_STATUS, "Statut", warnings),
  };

  const name = cleanStr(rec.name);
  if (name) fields.name = name;
  const role = cleanStr(rec.role);
  if (role) fields.role = role;
  const company = cleanStr(rec.company);
  if (company) fields.company = company;
  const email = cleanStr(rec.email);
  if (email) fields.email = email;
  const linkedin = cleanStr(rec.linkedin_url);
  if (linkedin) fields.linkedin_url = linkedin;
  const phone = cleanStr(rec.phone);
  if (phone) fields.phone = phone;
  const notes = cleanStr(rec.notes);
  if (notes) fields.notes = notes;

  return { ok: true, kind: "contact", fields, warnings };
}
