"use client";

import { useMemo, useState } from "react";
import type { Application, ApplicationStatus } from "@/types";
import { generateCoverLetter, generateEmail, generateInterviewPrep, suggestCvChanges } from "@/lib/api";
import { STAT_ORDER, STAT_LABEL, STAT_COLOR } from "@/components/ui/shared";

// ── Types de réponses IA ─────────────────────────────────
type PrepQuestion = { question: string; suggested_answer: string; story_to_use?: string | null };
type PrepStoryToPrepare = { theme: string; why: string };
type PrepData = {
  company_research?: string;
  common_questions?: PrepQuestion[];
  technical_prep?: string;
  questions_to_ask?: string[];
  dos_and_donts?: { do?: string[]; dont?: string[] };
  stories_to_prepare?: PrepStoryToPrepare[];
};

type CvAdaptation = { section?: string; current?: string; suggested?: string; priority?: string; rationale?: string };
type CvData = { overall_assessment?: string; adaptations?: CvAdaptation[]; keywords_to_add?: string[] };

type EmailData = { subject?: string; body?: string; recipients?: string[] };

// ── Parsing robuste ──────────────────────────────────────
/**
 * Extrait un objet depuis une valeur qui peut être :
 * - Déjà un objet (cas normal)
 * - Une string contenant du JSON (cas fallback backend où Claude a répondu du JSON brut
 *   avec fences ```json que le parse côté backend n'a pas pu manger — on rattrape ici).
 */
function coerceToObject<T extends Record<string, unknown>>(raw: unknown): T | null {
  if (!raw) return null;
  if (typeof raw === "object" && !Array.isArray(raw)) return raw as T;
  if (typeof raw !== "string") return null;
  let s = raw.trim();
  // Strip fences ```json … ```
  if (s.startsWith("```")) {
    s = s.replace(/^```(?:json)?\s*/i, "").replace(/```\s*$/m, "").trim();
  }
  // Extraire le premier objet { … } si présent
  const first = s.indexOf("{");
  const last = s.lastIndexOf("}");
  if (first >= 0 && last > first) s = s.slice(first, last + 1);
  try { return JSON.parse(s) as T; } catch { return null; }
}

/** Si le payload IA a mis tout le JSON dans un seul champ string, on le remonte. */
function normalizePrep(data: Record<string, unknown> | null): PrepData {
  if (!data) return {};
  const research = data.company_research;
  // Heuristique : si company_research ressemble à du JSON brut, c'est que le fallback backend a été pris.
  if (typeof research === "string" && (research.trim().startsWith("```") || research.trim().startsWith("{"))) {
    const recovered = coerceToObject<PrepData>(research);
    if (recovered && (recovered.common_questions || recovered.company_research)) return recovered;
  }
  return data as PrepData;
}

function normalizeCv(data: Record<string, unknown> | null): CvData {
  if (!data) return {};
  const assess = data.overall_assessment;
  if (typeof assess === "string" && (assess.trim().startsWith("```") || assess.trim().startsWith("{"))) {
    const recovered = coerceToObject<CvData>(assess);
    if (recovered) return recovered;
  }
  return data as CvData;
}

function normalizeEmail(data: Record<string, unknown> | null): EmailData {
  if (!data) return {};
  // Cas normal : {subject, body, recipients}
  if (typeof data.body === "string" && typeof data.subject === "string") return data as EmailData;
  // Cas dégradé : body contient le JSON brut
  const body = typeof data.body === "string" ? data.body : "";
  if (body && (body.trim().startsWith("```") || body.trim().startsWith("{"))) {
    const recovered = coerceToObject<EmailData>(body);
    if (recovered) return recovered;
  }
  return data as EmailData;
}

// ── Formatage texte pour Copier ──────────────────────────
function formatPrepAsText(p: PrepData, offerTitle: string, companyName: string): string {
  const lines: string[] = [];
  lines.push(`PRÉPARATION ENTRETIEN — ${companyName} — ${offerTitle}`);
  lines.push("=".repeat(60));
  if (p.company_research) {
    lines.push("", "## RECHERCHE ENTREPRISE", "", p.company_research);
  }
  if (p.common_questions?.length) {
    lines.push("", "## QUESTIONS FRÉQUENTES", "");
    p.common_questions.forEach((q, i) => {
      lines.push(`${i + 1}. ${q.question}`);
      if (q.suggested_answer) lines.push(`   → ${q.suggested_answer}`);
      if (q.story_to_use) lines.push(`   📖 Story à mobiliser : ${q.story_to_use}`);
      lines.push("");
    });
  }
  if (p.technical_prep) {
    lines.push("", "## PRÉPARATION TECHNIQUE", "", p.technical_prep);
  }
  if (p.questions_to_ask?.length) {
    lines.push("", "## QUESTIONS À POSER", "");
    p.questions_to_ask.forEach((q) => lines.push(`• ${q}`));
  }
  if (p.dos_and_donts) {
    if (p.dos_and_donts.do?.length) {
      lines.push("", "## À FAIRE", "");
      p.dos_and_donts.do.forEach((d) => lines.push(`✓ ${d}`));
    }
    if (p.dos_and_donts.dont?.length) {
      lines.push("", "## À ÉVITER", "");
      p.dos_and_donts.dont.forEach((d) => lines.push(`✗ ${d}`));
    }
  }
  if (p.stories_to_prepare?.length) {
    lines.push("", "## STORIES À PRÉPARER", "");
    p.stories_to_prepare.forEach((s) => {
      lines.push(`• ${s.theme} — ${s.why}`);
    });
  }
  return lines.join("\n");
}

export function DetailPanel({ app, onClose, onMove }: { app: Application; onClose: () => void; onMove: (s: ApplicationStatus) => void; onRefresh: () => void }) {
  const [gen, setGen] = useState<string | null>(null);
  const [activeSection, setActiveSection] = useState<string | null>(null);
  const [resultText, setResultText] = useState<string>("");
  const [resultData, setResultData] = useState<Record<string, unknown> | null>(null);
  const [copied, setCopied] = useState(false);

  const generate = async (type: "cl" | "em" | "em_relance" | "em_merci" | "ip" | "cv") => {
    setGen(type); setActiveSection(type); setResultText(""); setResultData(null); setCopied(false);
    try {
      if (type === "cl") {
        const d = await generateCoverLetter(app.id);
        setResultText(typeof d === "string" ? d : (d.cover_letter || JSON.stringify(d)));
      } else if (type.startsWith("em")) {
        const emailType = type === "em_relance" ? "relance" : type === "em_merci" ? "remerciement" : "candidature";
        const d = await generateEmail(app.id, emailType);
        setResultData(d);
        setResultText(d.body || "");
      } else if (type === "ip") {
        const d = await generateInterviewPrep(app.id);
        setResultData(d);
      } else if (type === "cv") {
        const d = await suggestCvChanges(app.id);
        setResultData(d);
      }
    } catch (e) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      setResultText("Erreur : " + (err?.response?.data?.detail || err?.message || "Appel IA echoue"));
    }
    setGen(null);
  };

  const copyToClipboard = (text: string) => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 2000); };

  const prep = useMemo<PrepData>(() => activeSection === "ip" ? normalizePrep(resultData) : {}, [activeSection, resultData]);
  const cv = useMemo<CvData>(() => activeSection === "cv" ? normalizeCv(resultData) : {}, [activeSection, resultData]);
  const email = useMemo<EmailData>(() => activeSection?.startsWith("em") ? normalizeEmail(resultData) : {}, [activeSection, resultData]);
  const emailBody = email.body || resultText;

  return (
    <div className="fixed inset-0 z-50 flex justify-end" onClick={onClose}>
      <div className="absolute inset-0 bg-black/15 backdrop-blur-[2px]" />
      <div className="relative w-full max-w-lg bg-white shadow-2xl overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="sticky top-0 bg-white/90 backdrop-blur-sm border-b border-surface-200 px-6 py-4 flex items-center justify-between z-10">
          <h2 className="font-display text-base font-semibold truncate pr-4">{app.offer?.title}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-lg">&times;</button>
        </div>
        <div className="p-6 space-y-6">
          <div>
            <div className="text-sm font-medium text-gray-700">{app.offer?.company_name}</div>
            {app.offer?.location && <div className="text-sm text-gray-500">{app.offer.location}</div>}
            {app.offer?.source_url && <a href={app.offer.source_url} target="_blank" rel="noopener noreferrer" className="text-sm text-brand-400 hover:underline mt-1 inline-block">Voir l&apos;offre</a>}
          </div>

          <div>
            <label className="block text-2xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Statut</label>
            <div className="flex flex-wrap gap-1.5">{STAT_ORDER.map((s) => (
              <button key={s} onClick={() => onMove(s)} className={`px-3 py-1 rounded-pill text-xs font-medium transition-default ${app.status === s ? STAT_COLOR[s] + " ring-1 ring-offset-1 ring-gray-200" : "bg-surface-100 text-gray-400 hover:bg-surface-200"}`}>{STAT_LABEL[s]}</button>
            ))}</div>
          </div>

          <div>
            <label className="block text-2xs font-medium text-ink-muted uppercase tracking-wider mb-2">Génération IA</label>
            <div className="flex flex-wrap gap-2">
              {([
                ["cl", "Lettre de motivation", "text-brand-700 border-brand-200 hover:bg-brand-50"],
                ["em", "Email candidature", "text-info-700 border-info-600/20 hover:bg-info-50"],
                ["em_relance", "Email relance", "text-info-700 border-info-600/20 hover:bg-info-50"],
                ["em_merci", "Email remerciement", "text-info-700 border-info-600/20 hover:bg-info-50"],
                ["cv", "Suggestions CV", "text-warn-700 border-warn-600/20 hover:bg-warn-50"],
                ["ip", "Prep entretien", "text-purple-700 border-purple-200 hover:bg-purple-50"],
              ] as const).map(([k, l, c]) => (
                <button key={k} onClick={() => generate(k)} disabled={!!gen} className={`px-3 py-1.5 text-xs font-medium rounded-input border bg-card transition-default disabled:opacity-50 ${c}`}>
                  {gen === k ? "Claude analyse…" : l}
                </button>
              ))}
            </div>

            {/* ─── LETTRE DE MOTIVATION ─── */}
            {activeSection === "cl" && resultText && (
              <div className="mt-4 space-y-2">
                <div className="p-4 bg-surface-50 rounded-card border border-surface-200 text-sm text-gray-700 whitespace-pre-wrap max-h-72 overflow-y-auto leading-relaxed">{resultText}</div>
                <div className="flex gap-2">
                  <button onClick={() => copyToClipboard(resultText)} className="px-3 py-1.5 text-xs font-medium bg-brand-50 text-brand-600 rounded-button hover:bg-brand-100 transition-default">{copied ? "Copie !" : "Copier"}</button>
                  <button onClick={() => generate("cl")} disabled={!!gen} className="px-3 py-1.5 text-xs font-medium bg-surface-100 text-gray-600 rounded-button hover:bg-surface-200 transition-default disabled:opacity-50">Regenerer</button>
                </div>
              </div>
            )}

            {/* ─── EMAILS ─── */}
            {activeSection?.startsWith("em") && emailBody && (
              <div className="mt-4 space-y-2">
                {email.subject && (
                  <div className="text-sm"><span className="font-medium text-gray-600">Objet : </span><span className="text-gray-800">{email.subject}</span></div>
                )}
                <div className="p-4 bg-surface-50 rounded-card border border-surface-200 text-sm text-gray-700 whitespace-pre-wrap max-h-72 overflow-y-auto leading-relaxed">{emailBody}</div>
                <div className="flex gap-2">
                  <button onClick={() => copyToClipboard(email.subject ? `Objet: ${email.subject}\n\n${emailBody}` : emailBody)} className="px-3 py-1.5 text-xs font-medium bg-brand-50 text-brand-600 rounded-button hover:bg-brand-100 transition-default">{copied ? "Copie !" : "Copier"}</button>
                  <button onClick={() => generate(activeSection as "em" | "em_relance" | "em_merci")} disabled={!!gen} className="px-3 py-1.5 text-xs font-medium bg-surface-100 text-gray-600 rounded-button hover:bg-surface-200 transition-default disabled:opacity-50">Regenerer</button>
                </div>
              </div>
            )}

            {/* ─── SUGGESTIONS CV ─── */}
            {activeSection === "cv" && resultData && (
              <div className="mt-4 space-y-3">
                {cv.overall_assessment && <p className="text-sm text-gray-700 italic">{cv.overall_assessment}</p>}
                {(cv.adaptations || []).map((a, i) => (
                  <div key={i} className={`p-3 rounded-card border text-sm ${a.priority === "high" ? "border-red-200 bg-red-50/50" : a.priority === "medium" ? "border-orange-200 bg-orange-50/50" : "border-gray-200 bg-gray-50/50"}`}>
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`text-2xs font-bold uppercase ${a.priority === "high" ? "text-red-600" : a.priority === "medium" ? "text-orange-600" : "text-gray-500"}`}>{a.priority}</span>
                      <span className="font-medium text-gray-800">{a.section}</span>
                    </div>
                    {a.suggested && <p className="text-gray-600">{a.suggested}</p>}
                    {a.rationale && <p className="text-xs text-gray-400 mt-1">{a.rationale}</p>}
                  </div>
                ))}
                {(cv.keywords_to_add || []).length > 0 && (
                  <div className="flex flex-wrap gap-1.5 pt-1">{(cv.keywords_to_add || []).map((k, i) => <span key={i} className="px-2 py-0.5 text-2xs bg-blue-50 text-blue-600 rounded-pill">+ {k}</span>)}</div>
                )}
              </div>
            )}

            {/* ─── PREP ENTRETIEN ─── */}
            {activeSection === "ip" && resultData && (
              <div className="mt-4 space-y-5 text-sm">
                {/* Bouton Copier en haut */}
                <div className="flex justify-end">
                  <button
                    onClick={() => copyToClipboard(formatPrepAsText(prep, app.offer?.title || "", app.offer?.company_name || ""))}
                    className="px-3 py-1.5 text-xs font-medium bg-brand-50 text-brand-600 rounded-button hover:bg-brand-100 transition-default"
                  >
                    {copied ? "Copié !" : "Copier la préparation"}
                  </button>
                </div>

                {/* Recherche entreprise */}
                {prep.company_research && (
                  <section>
                    <label className="text-2xs font-semibold text-gray-400 uppercase tracking-wider">Recherche entreprise</label>
                    <p className="text-gray-700 mt-1.5 leading-relaxed whitespace-pre-wrap">{prep.company_research}</p>
                  </section>
                )}

                {/* Questions fréquentes — liste numérotée */}
                {(prep.common_questions || []).length > 0 && (
                  <section>
                    <label className="text-2xs font-semibold text-gray-400 uppercase tracking-wider">Questions fréquentes</label>
                    <ol className="mt-2 space-y-3 list-none counter-reset-questions">
                      {(prep.common_questions || []).map((q, i) => (
                        <li key={i} className="flex gap-3">
                          <span className="shrink-0 w-6 h-6 rounded-full bg-brand-50 text-brand-600 text-xs font-bold flex items-center justify-center mt-0.5">{i + 1}</span>
                          <div className="flex-1 min-w-0">
                            <div className="font-semibold text-gray-800">{q.question}</div>
                            {q.suggested_answer && <div className="text-gray-600 mt-1 leading-relaxed">{q.suggested_answer}</div>}
                            {q.story_to_use && (
                              <div className="mt-1.5 inline-flex items-center gap-1 px-2 py-0.5 bg-green-50 text-green-700 rounded-pill text-2xs font-medium">
                                <span>📖</span>
                                <span>Story : {q.story_to_use}</span>
                              </div>
                            )}
                          </div>
                        </li>
                      ))}
                    </ol>
                  </section>
                )}

                {/* Préparation technique */}
                {prep.technical_prep && (
                  <section>
                    <label className="text-2xs font-semibold text-gray-400 uppercase tracking-wider">Préparation technique</label>
                    <p className="text-gray-700 mt-1.5 leading-relaxed whitespace-pre-wrap">{prep.technical_prep}</p>
                  </section>
                )}

                {/* Questions à poser — bullet list */}
                {(prep.questions_to_ask || []).length > 0 && (
                  <section>
                    <label className="text-2xs font-semibold text-gray-400 uppercase tracking-wider">Questions à poser</label>
                    <ul className="mt-1.5 space-y-1.5 list-disc list-outside pl-5">
                      {(prep.questions_to_ask || []).map((q, i) => (
                        <li key={i} className="text-gray-700 leading-relaxed">{q}</li>
                      ))}
                    </ul>
                  </section>
                )}

                {/* Do / Don't */}
                {(prep.dos_and_donts?.do?.length || prep.dos_and_donts?.dont?.length) ? (
                  <section className="grid grid-cols-1 gap-3">
                    {(prep.dos_and_donts?.do?.length || 0) > 0 && (
                      <div className="p-3 rounded-card border border-green-200 bg-green-50/40">
                        <label className="text-2xs font-semibold text-green-700 uppercase tracking-wider">À faire</label>
                        <ul className="mt-1.5 space-y-1 list-none">
                          {(prep.dos_and_donts?.do || []).map((d, i) => (
                            <li key={i} className="text-xs text-green-900 flex gap-1.5"><span className="text-green-500 shrink-0">✓</span><span>{d}</span></li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {(prep.dos_and_donts?.dont?.length || 0) > 0 && (
                      <div className="p-3 rounded-card border border-red-200 bg-red-50/40">
                        <label className="text-2xs font-semibold text-red-700 uppercase tracking-wider">À éviter</label>
                        <ul className="mt-1.5 space-y-1 list-none">
                          {(prep.dos_and_donts?.dont || []).map((d, i) => (
                            <li key={i} className="text-xs text-red-900 flex gap-1.5"><span className="text-red-500 shrink-0">✗</span><span>{d}</span></li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </section>
                ) : null}

                {/* Stories à préparer */}
                {(prep.stories_to_prepare || []).length > 0 && (
                  <section className="p-4 rounded-card border border-amber-200 bg-amber-50/60">
                    <label className="text-2xs font-semibold text-amber-800 uppercase tracking-wider">Stories à préparer</label>
                    <p className="text-2xs text-amber-700 mt-0.5">Thèmes pour lesquels vous devriez préparer des stories STAR.</p>
                    <div className="mt-2.5 space-y-2">
                      {(prep.stories_to_prepare || []).map((s, i) => (
                        <div key={i} className="bg-white/60 rounded-button p-2.5 border border-amber-200/70">
                          <div className="text-xs font-semibold text-amber-900">{s.theme}</div>
                          <div className="text-xs text-amber-800 mt-0.5 leading-relaxed">{s.why}</div>
                        </div>
                      ))}
                    </div>
                  </section>
                )}

                {/* Fallback : payload inattendu */}
                {!prep.company_research && !(prep.common_questions || []).length && !prep.technical_prep && (
                  <div className="p-3 rounded-button bg-red-50 text-sm text-red-700">
                    Réponse IA inattendue. Réessayez la génération.
                  </div>
                )}
              </div>
            )}

            {gen && (
              <div className="mt-4 flex items-center gap-2 text-xs text-ink-muted claude-thinking">
                <div className="flex items-center gap-1">
                  <span className="w-1 h-1 rounded-full bg-brand-400" />
                  <span className="w-1 h-1 rounded-full bg-brand-400" />
                  <span className="w-1 h-1 rounded-full bg-brand-400" />
                </div>
                <span>Claude analyse…</span>
              </div>
            )}
          </div>

          <div className="text-2xs text-gray-400 space-y-0.5 pt-3 border-t border-surface-200">
            <div>Creee le {new Date(app.created_at).toLocaleDateString("fr-FR")}</div>
            <div>MAJ le {new Date(app.updated_at).toLocaleDateString("fr-FR")}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
