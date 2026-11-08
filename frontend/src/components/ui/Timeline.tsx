"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ArrowLeftRight,
  Award,
  CalendarCheck,
  CalendarClock,
  CalendarPlus,
  Circle,
  Download,
  MailOpen,
  MessageCircle,
  MessageSquare,
  Plus,
  RefreshCw,
  Send,
  StickyNote,
  Trash2,
  UserPlus,
  XCircle,
  type LucideIcon,
} from "lucide-react";

import type { Activity, ActivityInput, ActivityType } from "@/types";
import {
  createContactActivity,
  createOfferActivity,
  deleteActivity,
  documentDownloadUrl,
  fetchContactActivities,
  fetchOfferActivities,
} from "@/lib/api";
import { DocumentPicker } from "@/components/ui/DocumentPicker";
import { fmtDate } from "@/components/ui/shared";

type ParentType = "offer" | "contact";

// Métadonnées d'affichage par type d'événement (label FR + icône Lucide + couleur du point).
const ACTIVITY_META: Record<ActivityType, { label: string; Icon: LucideIcon; dot: string }> = {
  applied: { label: "Candidature envoyée", Icon: Send, dot: "#378ADD" },
  relance: { label: "Relance", Icon: RefreshCw, dot: "#EF9F27" },
  response_received: { label: "Réponse reçue", Icon: MailOpen, dot: "#1D9E75" },
  interview_scheduled: { label: "Entretien planifié", Icon: CalendarPlus, dot: "#7F77DD" },
  interview_done: { label: "Entretien passé", Icon: MessageSquare, dot: "#7F77DD" },
  offer_received: { label: "Offre reçue", Icon: Award, dot: "#639922" },
  rejected: { label: "Refus", Icon: XCircle, dot: "#E24B4A" },
  contacted: { label: "Contacté", Icon: UserPlus, dot: "#378ADD" },
  replied: { label: "A répondu", Icon: MessageCircle, dot: "#1D9E75" },
  meeting_scheduled: { label: "RDV planifié", Icon: CalendarClock, dot: "#7F77DD" },
  meeting_done: { label: "RDV effectué", Icon: CalendarCheck, dot: "#639922" },
  note: { label: "Note", Icon: StickyNote, dot: "#888780" },
  status_change: { label: "Changement de statut", Icon: ArrowLeftRight, dot: "#888780" },
  other: { label: "Événement", Icon: Circle, dot: "#A1A1AA" },
};

// Types proposés à la saisie selon le parent (le backend accepte le superset complet).
const OFFER_TYPES: ActivityType[] = [
  "applied",
  "relance",
  "response_received",
  "interview_scheduled",
  "interview_done",
  "offer_received",
  "rejected",
  "status_change",
  "note",
  "other",
];
const CONTACT_TYPES: ActivityType[] = [
  "contacted",
  "relance",
  "replied",
  "response_received",
  "meeting_scheduled",
  "meeting_done",
  "rejected",
  "status_change",
  "note",
  "other",
];

const today = () => new Date().toISOString().slice(0, 10);

export function Timeline({
  parentType,
  parentId,
  onChange,
}: {
  parentType: ParentType;
  parentId: number;
  onChange?: () => void;
}) {
  const [items, setItems] = useState<Activity[]>([]);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    const fetcher =
      parentType === "offer" ? fetchOfferActivities : fetchContactActivities;
    fetcher(parentId)
      .then(setItems)
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, [parentType, parentId]);

  useEffect(() => {
    load();
  }, [load]);

  const create = async (data: ActivityInput) => {
    if (parentType === "offer") await createOfferActivity(parentId, data);
    else await createContactActivity(parentId, data);
    setAdding(false);
    load();
    onChange?.();
  };

  const remove = async (id: number) => {
    await deleteActivity(id);
    load();
    onChange?.();
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <div className="text-2xs font-semibold text-ink-faint uppercase tracking-wider">
          Timeline
        </div>
        {!adding && (
          <button
            onClick={() => setAdding(true)}
            className="inline-flex items-center gap-1 text-2xs font-medium text-brand-600 hover:text-brand-700"
          >
            <Plus size={13} /> Ajouter un événement
          </button>
        )}
      </div>

      {adding && (
        <ActivityForm
          parentType={parentType}
          onSave={create}
          onCancel={() => setAdding(false)}
        />
      )}

      {loading ? (
        <p className="text-xs text-ink-faint py-3">Chargement…</p>
      ) : items.length === 0 ? (
        <p className="text-xs text-ink-faint py-3">Aucun événement pour l&apos;instant.</p>
      ) : (
        <ol className="relative border-l border-line ml-2 mt-3 space-y-4">
          {items.map((a) => {
            const meta = ACTIVITY_META[a.activity_type] ?? ACTIVITY_META.other;
            const Icon = meta.Icon;
            return (
              <li key={a.id} className="ml-5 group">
                <span
                  className="absolute -left-[7px] flex items-center justify-center w-3.5 h-3.5 rounded-full ring-4 ring-card"
                  style={{ background: meta.dot }}
                />
                <div className="flex items-start gap-2">
                  <Icon size={14} className="text-ink-faint mt-0.5 shrink-0" strokeWidth={1.75} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-medium text-ink">{meta.label}</span>
                      <span className="text-2xs font-mono text-ink-faint">
                        {fmtDate(a.event_date)}
                      </span>
                    </div>
                    {a.note && (
                      <p className="text-xs text-ink-muted mt-0.5 whitespace-pre-wrap">{a.note}</p>
                    )}
                    {a.document && (
                      <a
                        href={documentDownloadUrl(a.document.id)}
                        target="_blank"
                        rel="noreferrer"
                        className="mt-1 inline-flex items-center gap-1 text-2xs text-brand-600 hover:text-brand-700 font-medium"
                      >
                        <Download size={12} /> {a.document.label}
                      </a>
                    )}
                  </div>
                  <button
                    onClick={() => remove(a.id)}
                    className="text-ink-faint hover:text-red-500 opacity-0 group-hover:opacity-100 transition-default shrink-0"
                    title="Supprimer l'événement"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}

function ActivityForm({
  parentType,
  onSave,
  onCancel,
}: {
  parentType: ParentType;
  onSave: (data: ActivityInput) => Promise<void>;
  onCancel: () => void;
}) {
  const types = parentType === "offer" ? OFFER_TYPES : CONTACT_TYPES;
  const [type, setType] = useState<ActivityType>(types[0]);
  const [date, setDate] = useState(today());
  const [note, setNote] = useState("");
  const [docId, setDocId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);

  const submit = async () => {
    if (!date) return;
    setSaving(true);
    try {
      await onSave({
        activity_type: type,
        event_date: date,
        note: note.trim() || null,
        document_id: type === "applied" ? docId : null,
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="border border-line rounded-card p-3 mb-3 space-y-3 bg-surface-50">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-2xs font-medium text-ink-muted mb-1">Type</label>
          <select
            value={type}
            onChange={(e) => setType(e.target.value as ActivityType)}
            className="w-full px-2.5 py-1.5 border border-line rounded-input text-sm bg-card"
          >
            {types.map((t) => (
              <option key={t} value={t}>
                {ACTIVITY_META[t].label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-2xs font-medium text-ink-muted mb-1">Date</label>
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="w-full px-2.5 py-1.5 border border-line rounded-input text-sm bg-card"
          />
        </div>
      </div>
      <div>
        <label className="block text-2xs font-medium text-ink-muted mb-1">Note (optionnel)</label>
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={2}
          className="w-full px-2.5 py-1.5 border border-line rounded-input text-sm resize-y bg-card"
        />
      </div>
      {type === "applied" && (
        <div>
          <label className="block text-2xs font-medium text-ink-muted mb-1">CV envoyé (optionnel)</label>
          <DocumentPicker title="CV" docType="cv" value={docId} onChange={setDocId} />
        </div>
      )}
      <div className="flex items-center justify-end gap-2">
        <button onClick={onCancel} className="text-2xs text-ink-muted hover:text-ink">
          Annuler
        </button>
        <button
          onClick={submit}
          disabled={saving || !date}
          className="px-3 py-1 bg-brand-400 text-white rounded-input text-2xs font-medium hover:bg-brand-500 disabled:opacity-50"
        >
          {saving ? "Ajout…" : "Ajouter"}
        </button>
      </div>
    </div>
  );
}
