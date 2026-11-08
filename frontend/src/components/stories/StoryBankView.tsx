"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import type { InterviewStory, StoryInput } from "@/types";
import { createStory, deleteStory, fetchStories, updateStory } from "@/lib/api";
import { Card, CardHeader, TagInput } from "@/components/ui/shared";

const TAG_SUGGESTIONS = [
  "leadership",
  "teamwork",
  "problem_solving",
  "technical",
  "finance",
  "quantitatif",
  "communication",
  "gestion_projet",
  "initiative",
  "adaptabilité",
];

type FormState = {
  id?: number;
  title: string;
  source: string;
  situation: string;
  task: string;
  action: string;
  result: string;
  reflection: string;
  tags: string[];
};

const EMPTY_FORM: FormState = {
  title: "",
  source: "",
  situation: "",
  task: "",
  action: "",
  result: "",
  reflection: "",
  tags: [],
};

const STEPS: { label: string; fields: (keyof FormState)[]; hint: string; placeholder?: string }[] = [
  {
    label: "Identité",
    fields: ["title", "source"],
    hint: "Un titre court et mémorable, et d'où vient l'expérience.",
    placeholder: "Ex: Restructuration portefeuille stage SG 2024",
  },
  {
    label: "Situation",
    fields: ["situation"],
    hint: "Quel était le contexte ? Quand, où, avec qui ?",
    placeholder: "En stage au desk taux de la Société Générale, pendant une période de forte volatilité…",
  },
  {
    label: "Task",
    fields: ["task"],
    hint: "Quel était l'objectif ou le défi que tu devais relever ?",
    placeholder: "Construire en 3 jours un dashboard de monitoring de l'exposition du desk.",
  },
  {
    label: "Action",
    fields: ["action"],
    hint: "Qu'as-tu fait concrètement, étape par étape ?",
    placeholder: "J'ai interrogé 3 traders, extrait les données, conçu le dashboard, puis l'ai testé avant déploiement.",
  },
  {
    label: "Result & Reflection",
    fields: ["result", "reflection"],
    hint: "Quel résultat mesurable ? Que retiens-tu ?",
    placeholder: "Résultat : adopté par les 6 traders du desk pendant 3 mois. Reflection : un produit simple et testé bat un produit complexe sans feedback.",
  },
];

function Wizard({
  initial,
  onSave,
  onCancel,
}: {
  initial: FormState;
  onSave: (f: FormState) => Promise<void>;
  onCancel: () => void;
}) {
  const [form, setForm] = useState<FormState>(initial);
  const [step, setStep] = useState(0);
  const [saving, setSaving] = useState(false);
  const isEdit = !!initial.id;

  const setField = (k: keyof FormState, v: string | string[]) => setForm((f) => ({ ...f, [k]: v }));

  const canNext = useMemo(() => {
    const required = STEPS[step].fields.filter((f) => f !== "reflection" && f !== "source");
    return required.every((f) => typeof form[f] === "string" && (form[f] as string).trim().length > 0);
  }, [form, step]);

  const submit = async () => {
    setSaving(true);
    try {
      await onSave(form);
    } finally {
      setSaving(false);
    }
  };

  const cur = STEPS[step];

  return (
    <Card noPad>
      <CardHeader
        title={isEdit ? "Modifier la story" : "Nouvelle story STAR"}
        right={
          <button onClick={onCancel} className="text-ink-faint hover:text-ink text-lg">
            ×
          </button>
        }
      />
      <div className="px-6 pt-5 pb-4 border-b border-line">
        <div className="flex items-center gap-2">
          {STEPS.map((s, i) => {
            const done = i < step;
            const active = i === step;
            return (
              <div key={i} className="flex items-center gap-2 flex-1 last:flex-none">
                <div
                  className={`w-6 h-6 rounded-full flex items-center justify-center text-2xs font-semibold font-mono shrink-0 ${
                    done ? "bg-brand-400 text-white" : active ? "bg-ink text-white" : "bg-surface-100 text-ink-faint"
                  }`}
                >
                  {done ? "✓" : i + 1}
                </div>
                <span className={`text-xs font-medium truncate ${active ? "text-ink" : "text-ink-muted"}`}>{s.label}</span>
                {i < STEPS.length - 1 && <div className={`flex-1 h-px ${i < step ? "bg-brand-400" : "bg-line"}`} />}
              </div>
            );
          })}
        </div>
        <p className="text-xs text-ink-muted mt-3">{cur.hint}</p>
      </div>

      <div className="p-6 space-y-4">
        {cur.fields.map((f) => {
          if (f === "title" || f === "source") {
            return (
              <div key={f}>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  {f === "title" ? "Titre" : "Source (libre)"}
                </label>
                <input
                  type="text"
                  value={form[f] as string}
                  onChange={(e) => setField(f, e.target.value)}
                  placeholder={f === "title" ? cur.placeholder : "ex: stage BNP 2024, projet école, association..."}
                  className="w-full px-3 py-2 border border-surface-200 rounded-button text-sm"
                />
              </div>
            );
          }
          if (f === "reflection") {
            return (
              <div key={f}>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">Reflection (optionnel)</label>
                <textarea
                  value={form[f] as string}
                  onChange={(e) => setField(f, e.target.value)}
                  rows={3}
                  placeholder="Ce que tu retires de cette expérience…"
                  className="w-full px-3 py-2 border border-surface-200 rounded-button text-sm resize-y"
                />
              </div>
            );
          }
          return (
            <div key={f}>
              <label className="block text-sm font-medium text-gray-700 mb-1.5 capitalize">
                {f === "situation" ? "Situation" : f === "task" ? "Task" : f === "action" ? "Action" : "Result"}
              </label>
              <textarea
                value={form[f] as string}
                onChange={(e) => setField(f, e.target.value)}
                rows={4}
                placeholder={cur.placeholder}
                className="w-full px-3 py-2 border border-surface-200 rounded-button text-sm resize-y"
              />
            </div>
          );
        })}

        {step === STEPS.length - 1 && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Tags</label>
            <TagInput value={form.tags} onChange={(t) => setField("tags", t)} placeholder="leadership, finance, technical..." />
            <div className="flex flex-wrap gap-1.5 mt-2">
              {TAG_SUGGESTIONS.filter((t) => !form.tags.includes(t)).map((t) => (
                <button
                  key={t}
                  onClick={() => setField("tags", [...form.tags, t])}
                  className="text-2xs px-2 py-0.5 bg-surface-100 text-gray-500 rounded-pill hover:bg-brand-50 hover:text-brand-600 transition-default"
                >
                  + {t}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="px-6 py-4 border-t border-line flex items-center justify-between">
        <button onClick={step === 0 ? onCancel : () => setStep(step - 1)} className="px-3 py-1.5 text-sm text-ink-muted hover:text-ink transition-default">
          {step === 0 ? "Annuler" : "← Précédent"}
        </button>
        {step < STEPS.length - 1 ? (
          <button
            onClick={() => setStep(step + 1)}
            disabled={!canNext}
            className="px-4 py-1.5 bg-ink text-white rounded-input text-sm font-medium hover:bg-ink/90 disabled:opacity-50"
          >
            Suivant →
          </button>
        ) : (
          <button
            onClick={submit}
            disabled={!canNext || saving}
            className="px-4 py-1.5 bg-brand-400 text-white rounded-input text-sm font-medium hover:bg-brand-500 disabled:opacity-50"
          >
            {saving ? "Sauvegarde…" : isEdit ? "Mettre à jour" : "Enregistrer"}
          </button>
        )}
      </div>
    </Card>
  );
}

function StoryCard({ story, onEdit, onDelete }: { story: InterviewStory; onEdit: () => void; onDelete: () => void }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <Card noPad className="card-hover">
      <div className="px-5 py-4 cursor-pointer" onClick={() => setExpanded(!expanded)}>
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-semibold text-gray-900">{story.title}</h3>
            <div className="flex items-center gap-1.5 text-xs text-gray-500 mt-1 flex-wrap">
              {story.source && <span>{story.source}</span>}
              {story.source && story.tags.length > 0 && <span className="text-surface-300">·</span>}
              {story.tags.map((t, i) => (
                <span key={i} className="text-2xs px-2 py-0.5 bg-brand-50 text-brand-600 rounded-pill">
                  {t}
                </span>
              ))}
              <span className="ml-auto text-2xs text-gray-400">{new Date(story.updated_at).toLocaleDateString("fr-FR")}</span>
            </div>
          </div>
          <div className="flex gap-1 shrink-0">
            <button onClick={(e) => { e.stopPropagation(); onEdit(); }} className="p-1.5 text-gray-400 hover:text-brand-500 rounded transition-default" title="Éditer">
              <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
              </svg>
            </button>
            <button onClick={(e) => { e.stopPropagation(); if (confirm("Supprimer cette story ?")) onDelete(); }} className="p-1.5 text-gray-400 hover:text-red-500 rounded transition-default" title="Supprimer">
              <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          </div>
        </div>
      </div>
      {expanded && (
        <div className="px-5 pb-5 pt-0 border-t border-surface-200 bg-surface-50/40 text-sm space-y-3">
          <div><span className="text-2xs font-semibold text-gray-400 uppercase">Situation</span><p className="text-gray-700 mt-0.5 whitespace-pre-wrap">{story.situation}</p></div>
          <div><span className="text-2xs font-semibold text-gray-400 uppercase">Task</span><p className="text-gray-700 mt-0.5 whitespace-pre-wrap">{story.task}</p></div>
          <div><span className="text-2xs font-semibold text-gray-400 uppercase">Action</span><p className="text-gray-700 mt-0.5 whitespace-pre-wrap">{story.action}</p></div>
          <div><span className="text-2xs font-semibold text-gray-400 uppercase">Result</span><p className="text-gray-700 mt-0.5 whitespace-pre-wrap">{story.result}</p></div>
          {story.reflection && <div><span className="text-2xs font-semibold text-gray-400 uppercase">Reflection</span><p className="text-gray-600 italic mt-0.5 whitespace-pre-wrap">{story.reflection}</p></div>}
        </div>
      )}
    </Card>
  );
}

export function StoryBankView() {
  const [stories, setStories] = useState<InterviewStory[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterTags, setFilterTags] = useState<string[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<FormState | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    fetchStories(filterTags.length ? filterTags : undefined)
      .then(setStories)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [filterTags]);

  useEffect(() => {
    load();
  }, [load]);

  const allTags = useMemo(() => {
    const s = new Set<string>();
    stories.forEach((st) => st.tags.forEach((t) => s.add(t)));
    return Array.from(s).sort();
  }, [stories]);

  const save = async (form: FormState) => {
    const payload: StoryInput = {
      title: form.title.trim(),
      situation: form.situation.trim(),
      task: form.task.trim(),
      action: form.action.trim(),
      result: form.result.trim(),
      reflection: form.reflection.trim() || null,
      tags: form.tags,
      source: form.source.trim() || null,
    };
    try {
      if (form.id) await updateStory(form.id, payload);
      else await createStory(payload);
      setShowForm(false);
      setEditing(null);
      load();
    } catch {
      alert("Erreur lors de la sauvegarde.");
    }
  };

  const del = async (id: number) => {
    try {
      await deleteStory(id);
      load();
    } catch {
      alert("Erreur.");
    }
  };

  const openEdit = (s: InterviewStory) => {
    setEditing({
      id: s.id,
      title: s.title,
      source: s.source || "",
      situation: s.situation,
      task: s.task,
      action: s.action,
      result: s.result,
      reflection: s.reflection || "",
      tags: s.tags,
    });
    setShowForm(true);
  };

  const toggleFilter = (t: string) => {
    setFilterTags((p) => (p.includes(t) ? p.filter((x) => x !== t) : [...p, t]));
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-ink">Story Bank</h1>
          <p className="text-sm text-ink-muted mt-1">
            Vos expériences STAR mobilisables en entretien — <span className="font-mono">{stories.length}</span> storie
            {stories.length > 1 ? "s" : ""}
          </p>
        </div>
        {!showForm && (
          <button
            onClick={() => {
              setEditing({ ...EMPTY_FORM });
              setShowForm(true);
            }}
            className="px-4 py-2 bg-ink text-white rounded-input text-sm font-medium hover:bg-ink/90 transition-default"
          >
            + Ajouter une story
          </button>
        )}
      </div>

      {showForm && editing && (
        <Wizard initial={editing} onSave={save} onCancel={() => { setShowForm(false); setEditing(null); }} />
      )}

      {allTags.length > 0 && !showForm && (
        <Card>
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-2xs font-semibold text-gray-400 uppercase tracking-wider mr-1">Filtrer :</span>
            {allTags.map((t) => (
              <button
                key={t}
                onClick={() => toggleFilter(t)}
                className={`text-2xs px-2.5 py-1 rounded-pill font-medium transition-default ${
                  filterTags.includes(t) ? "bg-brand-400 text-white" : "bg-surface-100 text-gray-500 hover:bg-brand-50 hover:text-brand-600"
                }`}
              >
                {t}
              </button>
            ))}
            {filterTags.length > 0 && (
              <button onClick={() => setFilterTags([])} className="text-2xs text-gray-400 hover:text-gray-600 underline underline-offset-2 ml-2">
                Réinitialiser
              </button>
            )}
          </div>
        </Card>
      )}

      {loading ? (
        <div className="text-center text-gray-400 py-12">Chargement...</div>
      ) : stories.length === 0 ? (
        <Card className="text-center py-12">
          <p className="text-sm text-gray-500">Aucune story pour l&apos;instant.</p>
          <p className="text-xs text-gray-400 mt-1">Commencez par ajouter vos expériences marquantes : stage, projet, association, sport, bénévolat…</p>
        </Card>
      ) : (
        <div className="space-y-2.5">
          {stories.map((s) => (
            <StoryCard key={s.id} story={s} onEdit={() => openEdit(s)} onDelete={() => del(s.id)} />
          ))}
        </div>
      )}
    </div>
  );
}
