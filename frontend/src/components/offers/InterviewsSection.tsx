"use client";

import { useCallback, useEffect, useState } from "react";
import {
  CalendarClock,
  MapPin,
  Phone,
  Plus,
  Trash2,
  User,
  Video,
  type LucideIcon,
} from "lucide-react";

import type {
  Interview,
  InterviewFormat,
  InterviewInput,
  InterviewOutcome,
  InterviewStory,
} from "@/types";
import {
  attachStoryToInterview,
  createInterview,
  deleteInterview,
  detachStoryFromInterview,
  fetchOfferInterviews,
  fetchStories,
  updateInterview,
} from "@/lib/api";
import { fmtDate } from "@/components/ui/shared";

// ─── Métadonnées d'affichage ──────────────────────────────
const FORMAT_META: Record<InterviewFormat, { label: string; Icon: LucideIcon }> = {
  visio: { label: "Visioconférence", Icon: Video },
  onsite: { label: "Sur place", Icon: MapPin },
  phone: { label: "Téléphone", Icon: Phone },
};

const OUTCOME_LABEL: Record<InterviewOutcome, string> = {
  pending: "En attente",
  pending_next: "Étape suivante",
  passed: "Réussi",
  rejected: "Refusé",
};

const OUTCOME_PILL: Record<InterviewOutcome, string> = {
  pending: "bg-gray-100 text-gray-600",
  pending_next: "bg-violet-50 text-violet-600",
  passed: "bg-green-50 text-green-700",
  rejected: "bg-red-50 text-red-600",
};

const FORMATS: InterviewFormat[] = ["visio", "onsite", "phone"];
const OUTCOMES: InterviewOutcome[] = ["pending", "pending_next", "passed", "rejected"];

// Datetime ISO (avec tz) → valeur d'un <input type="datetime-local"> (locale, 16 car).
const toLocalInput = (iso: string | null): string => {
  if (!iso) return "";
  const d = new Date(iso);
  const off = d.getTimezoneOffset() * 60000;
  return new Date(d.getTime() - off).toISOString().slice(0, 16);
};

export function InterviewsSection({
  offerId,
  onChange,
  onNavStories,
}: {
  offerId: number;
  onChange?: () => void;
  onNavStories?: () => void;
}) {
  const [interviews, setInterviews] = useState<Interview[]>([]);
  const [stories, setStories] = useState<InterviewStory[]>([]);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<Interview | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    fetchOfferInterviews(offerId)
      .then(setInterviews)
      .catch(() => setInterviews([]))
      .finally(() => setLoading(false));
  }, [offerId]);

  useEffect(() => {
    load();
    fetchStories().then(setStories).catch(() => setStories([]));
  }, [load]);

  const closeForm = () => {
    setAdding(false);
    setEditing(null);
  };

  const remove = async (it: Interview) => {
    if (!confirm(`Supprimer l'entretien « ${it.round_label} » ?`)) return;
    await deleteInterview(it.id);
    load();
    onChange?.();
  };

  const afterSave = () => {
    closeForm();
    load();
    onChange?.();
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <div className="text-2xs font-semibold text-ink-faint uppercase tracking-wider">
          Entretiens ({interviews.length})
        </div>
        {!adding && !editing && (
          <button
            onClick={() => setAdding(true)}
            className="inline-flex items-center gap-1 text-2xs font-medium text-brand-600 hover:text-brand-700"
          >
            <Plus size={13} /> Ajouter un entretien
          </button>
        )}
      </div>

      {(adding || editing) && (
        <InterviewForm
          offerId={offerId}
          initial={editing}
          stories={stories}
          onSaved={afterSave}
          onCancel={closeForm}
          onNavStories={onNavStories}
        />
      )}

      {loading ? (
        <p className="text-xs text-ink-faint py-3">Chargement…</p>
      ) : interviews.length === 0 && !adding ? (
        <p className="text-xs text-ink-faint py-3">Aucun entretien pour cette offre.</p>
      ) : (
        <div className="space-y-2.5 mt-1">
          {interviews.map((it) => (
            <InterviewCard
              key={it.id}
              interview={it}
              onEdit={() => {
                setAdding(false);
                setEditing(it);
              }}
              onDelete={() => remove(it)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function InterviewCard({
  interview: it,
  onEdit,
  onDelete,
}: {
  interview: Interview;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const fmt = it.format ? FORMAT_META[it.format] : null;
  const FmtIcon = fmt?.Icon;
  return (
    <div className="border border-line rounded-card p-3.5 group">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-sm font-medium text-ink">{it.round_label}</span>
        <span className={`text-2xs px-2 py-0.5 rounded-pill font-medium ${OUTCOME_PILL[it.outcome]}`}>
          {OUTCOME_LABEL[it.outcome]}
        </span>
        <div className="ml-auto flex items-center gap-1.5 opacity-0 group-hover:opacity-100 transition-default">
          <button
            onClick={onEdit}
            className="text-2xs px-2 py-0.5 border border-line rounded-input hover:bg-surface-100 text-ink-muted"
          >
            Modifier
          </button>
          <button
            onClick={onDelete}
            className="text-ink-faint hover:text-red-500"
            title="Supprimer l'entretien"
          >
            <Trash2 size={13} />
          </button>
        </div>
      </div>

      <div className="flex items-center gap-3 flex-wrap mt-1.5 text-xs text-ink-muted">
        {it.scheduled_at && (
          <span className="inline-flex items-center gap-1">
            <CalendarClock size={13} className="text-ink-faint" strokeWidth={1.75} />
            <span className="font-mono">
              {fmtDate(it.scheduled_at)}
              {" · "}
              {new Date(it.scheduled_at).toLocaleTimeString("fr-FR", {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </span>
          </span>
        )}
        {fmt && FmtIcon && (
          <span className="inline-flex items-center gap-1">
            <FmtIcon size={13} className="text-ink-faint" strokeWidth={1.75} />
            {fmt.label}
          </span>
        )}
        {it.interviewer && (
          <span className="inline-flex items-center gap-1">
            <User size={13} className="text-ink-faint" strokeWidth={1.75} />
            {it.interviewer}
          </span>
        )}
      </div>

      {(it.questions || it.feeling || it.next_step) && (
        <div className="mt-2 space-y-1.5">
          {it.questions && <DetailBlock label="Questions" value={it.questions} />}
          {it.feeling && <DetailBlock label="Ressenti" value={it.feeling} />}
          {it.next_step && <DetailBlock label="Prochaine étape" value={it.next_step} />}
        </div>
      )}

      {it.stories.length > 0 && (
        <div className="mt-2 flex items-center gap-1.5 flex-wrap">
          <span className="text-2xs text-ink-faint uppercase tracking-wide">Stories</span>
          {it.stories.map((s) => (
            <span
              key={s.id}
              className="text-2xs px-2 py-0.5 bg-brand-50 text-brand-600 rounded-pill font-medium"
            >
              {s.title}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function DetailBlock({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-2xs font-semibold text-ink-faint uppercase">{label}</div>
      <p className="text-xs text-ink-muted whitespace-pre-wrap">{value}</p>
    </div>
  );
}

function InterviewForm({
  offerId,
  initial,
  stories,
  onSaved,
  onCancel,
  onNavStories,
}: {
  offerId: number;
  initial: Interview | null;
  stories: InterviewStory[];
  onSaved: () => void;
  onCancel: () => void;
  onNavStories?: () => void;
}) {
  const [roundLabel, setRoundLabel] = useState(initial?.round_label ?? "");
  const [scheduledAt, setScheduledAt] = useState(toLocalInput(initial?.scheduled_at ?? null));
  const [interviewer, setInterviewer] = useState(initial?.interviewer ?? "");
  const [format, setFormat] = useState<InterviewFormat | "">(initial?.format ?? "");
  const [outcome, setOutcome] = useState<InterviewOutcome>(initial?.outcome ?? "pending");
  const [questions, setQuestions] = useState(initial?.questions ?? "");
  const [feeling, setFeeling] = useState(initial?.feeling ?? "");
  const [nextStep, setNextStep] = useState(initial?.next_step ?? "");
  const [storyIds, setStoryIds] = useState<number[]>(
    initial ? initial.stories.map((s) => s.id) : []
  );
  const [saving, setSaving] = useState(false);

  const toggleStory = (id: number) =>
    setStoryIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));

  const submit = async () => {
    if (!roundLabel.trim()) return;
    setSaving(true);
    try {
      const payload: InterviewInput = {
        round_label: roundLabel.trim(),
        scheduled_at: scheduledAt ? new Date(scheduledAt).toISOString() : null,
        interviewer: interviewer.trim() || null,
        format: format || null,
        outcome,
        questions: questions.trim() || null,
        feeling: feeling.trim() || null,
        next_step: nextStep.trim() || null,
      };

      if (initial) {
        await updateInterview(initial.id, payload);
        // Diff des stories rattachées.
        const before = initial.stories.map((s) => s.id);
        const toAttach = storyIds.filter((id) => !before.includes(id));
        const toDetach = before.filter((id) => !storyIds.includes(id));
        for (const id of toAttach) await attachStoryToInterview(initial.id, id);
        for (const id of toDetach) await detachStoryFromInterview(initial.id, id);
      } else {
        const created = await createInterview(offerId, payload);
        for (const id of storyIds) await attachStoryToInterview(created.id, id);
      }
      onSaved();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="border border-line rounded-card p-4 mb-3 space-y-3 bg-surface-50">
      <div className="grid grid-cols-2 gap-3">
        <FormField label="Round *">
          <input
            type="text"
            value={roundLabel}
            onChange={(e) => setRoundLabel(e.target.value)}
            placeholder="RH, Technique, Superday…"
            className="w-full px-2.5 py-1.5 border border-line rounded-input text-sm bg-card"
          />
        </FormField>
        <FormField label="Date & heure">
          <input
            type="datetime-local"
            value={scheduledAt}
            onChange={(e) => setScheduledAt(e.target.value)}
            className="w-full px-2.5 py-1.5 border border-line rounded-input text-sm bg-card"
          />
        </FormField>
        <FormField label="Interlocuteur">
          <input
            type="text"
            value={interviewer}
            onChange={(e) => setInterviewer(e.target.value)}
            placeholder="Nom de l'interlocuteur"
            className="w-full px-2.5 py-1.5 border border-line rounded-input text-sm bg-card"
          />
        </FormField>
        <FormField label="Format">
          <select
            value={format}
            onChange={(e) => setFormat(e.target.value as InterviewFormat | "")}
            className="w-full px-2.5 py-1.5 border border-line rounded-input text-sm bg-card"
          >
            <option value="">— Non précisé —</option>
            {FORMATS.map((f) => (
              <option key={f} value={f}>
                {FORMAT_META[f].label}
              </option>
            ))}
          </select>
        </FormField>
        <FormField label="Issue">
          <select
            value={outcome}
            onChange={(e) => setOutcome(e.target.value as InterviewOutcome)}
            className="w-full px-2.5 py-1.5 border border-line rounded-input text-sm bg-card"
          >
            {OUTCOMES.map((o) => (
              <option key={o} value={o}>
                {OUTCOME_LABEL[o]}
              </option>
            ))}
          </select>
        </FormField>
      </div>

      <FormField label="Questions posées">
        <textarea
          value={questions}
          onChange={(e) => setQuestions(e.target.value)}
          rows={2}
          className="w-full px-2.5 py-1.5 border border-line rounded-input text-sm resize-y bg-card"
        />
      </FormField>
      <FormField label="Ressenti">
        <textarea
          value={feeling}
          onChange={(e) => setFeeling(e.target.value)}
          rows={2}
          className="w-full px-2.5 py-1.5 border border-line rounded-input text-sm resize-y bg-card"
        />
      </FormField>
      <FormField label="Prochaine étape">
        <textarea
          value={nextStep}
          onChange={(e) => setNextStep(e.target.value)}
          rows={2}
          className="w-full px-2.5 py-1.5 border border-line rounded-input text-sm resize-y bg-card"
        />
      </FormField>

      {/* Multi-select des stories STAR (Story Bank existante). */}
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <label className="block text-2xs font-medium text-ink-muted">
            Stories STAR à préparer
          </label>
          {onNavStories && (
            <button
              type="button"
              onClick={onNavStories}
              className="text-2xs text-brand-600 hover:text-brand-700 font-medium"
            >
              + Créer une story
            </button>
          )}
        </div>
        {stories.length === 0 ? (
          <p className="text-2xs text-ink-faint">
            Aucune story dans la Story Bank pour le moment.
          </p>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {stories.map((s) => {
              const on = storyIds.includes(s.id);
              return (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => toggleStory(s.id)}
                  className={`text-2xs px-2 py-1 rounded-pill font-medium border transition-default ${
                    on
                      ? "bg-brand-50 text-brand-600 border-brand-200"
                      : "bg-card text-ink-muted border-line hover:bg-surface-100"
                  }`}
                >
                  {s.title}
                </button>
              );
            })}
          </div>
        )}
      </div>

      <div className="flex items-center justify-end gap-2">
        <button onClick={onCancel} className="text-2xs text-ink-muted hover:text-ink">
          Annuler
        </button>
        <button
          onClick={submit}
          disabled={saving || !roundLabel.trim()}
          className="px-3 py-1 bg-brand-400 text-white rounded-input text-2xs font-medium hover:bg-brand-500 disabled:opacity-50"
        >
          {saving ? "Enregistrement…" : initial ? "Enregistrer" : "Ajouter"}
        </button>
      </div>
    </div>
  );
}

function FormField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-2xs font-medium text-ink-muted mb-1">{label}</label>
      {children}
    </div>
  );
}
