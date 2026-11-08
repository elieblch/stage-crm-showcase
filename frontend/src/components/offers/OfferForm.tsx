"use client";

import { useState } from "react";

import type { Offer, OfferInput, OfferPriority, OfferStatus } from "@/types";
import {
  Card,
  CardHeader,
  Field,
  OFFER_STATUS_LABEL,
  OFFER_STATUS_ORDER,
  PRIORITY_LABEL,
  SelectField,
} from "@/components/ui/shared";
import { DocumentPicker } from "@/components/ui/DocumentPicker";

const d = (s: string | null | undefined) => (s ? s.slice(0, 10) : "");

export function OfferForm({
  initial,
  prefill,
  warnings,
  onSave,
  onCancel,
}: {
  initial?: Offer;
  prefill?: OfferInput;
  warnings?: string[];
  onSave: (data: OfferInput) => Promise<void>;
  onCancel: () => void;
}) {
  const [title, setTitle] = useState(initial?.title ?? prefill?.title ?? "");
  const [company, setCompany] = useState(initial?.company ?? prefill?.company ?? "");
  const [location, setLocation] = useState(initial?.location ?? prefill?.location ?? "");
  const [url, setUrl] = useState(initial?.url ?? prefill?.url ?? "");
  const [source, setSource] = useState(initial?.source ?? prefill?.source ?? "");
  const [priority, setPriority] = useState<OfferPriority>(initial?.priority ?? prefill?.priority ?? "moyenne");
  const [status, setStatus] = useState<OfferStatus>(initial?.status ?? prefill?.status ?? "a_postuler");
  const [dateApplied, setDateApplied] = useState(d(initial?.date_applied));
  const [deadline, setDeadline] = useState(d(initial?.deadline ?? prefill?.deadline));
  const [nextRelance, setNextRelance] = useState(d(initial?.next_relance_date));
  const [noRelance, setNoRelance] = useState(initial?.no_relance ?? false);
  const [notes, setNotes] = useState(initial?.notes ?? prefill?.notes ?? "");
  const [cvDocId, setCvDocId] = useState<number | null>(initial?.cv_document_id ?? null);
  const [lmDocId, setLmDocId] = useState<number | null>(initial?.lm_document_id ?? null);
  const [saving, setSaving] = useState(false);

  const canSave = title.trim().length > 0 && company.trim().length > 0;

  const submit = async () => {
    if (!canSave) return;
    setSaving(true);
    try {
      await onSave({
        title: title.trim(),
        company: company.trim(),
        location: location.trim() || null,
        url: url.trim() || null,
        source: source.trim() || null,
        priority,
        status,
        date_applied: dateApplied || null,
        deadline: deadline || null,
        next_relance_date: nextRelance || null,
        no_relance: noRelance,
        notes: notes.trim() || null,
        cv_document_id: cvDocId,
        lm_document_id: lmDocId,
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card noPad>
      <CardHeader
        title={initial ? "Modifier l'offre" : "Nouvelle offre"}
        right={
          <button onClick={onCancel} className="text-ink-faint hover:text-ink text-lg">
            ×
          </button>
        }
      />
      <div className="p-6 space-y-4">
        {warnings && warnings.length > 0 && (
          <div className="text-2xs text-amber-700 bg-amber-50 border border-amber-100 rounded-input px-3 py-2">
            <span className="font-semibold">Ajout rapide :</span>
            <ul className="list-disc list-inside mt-0.5">
              {warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          </div>
        )}
        <div className="grid grid-cols-2 gap-4">
          <Field label="Intitulé du poste *" value={title} onChange={setTitle} placeholder="Stage M&A" />
          <Field label="Entreprise *" value={company} onChange={setCompany} placeholder="Lazard" />
          <Field label="Localisation" value={location} onChange={setLocation} placeholder="Paris" />
          <Field label="Source" value={source} onChange={setSource} placeholder="Welcome to the Jungle" />
        </div>
        <Field label="Lien de l'offre" value={url} onChange={setUrl} placeholder="https://…" />
        <div className="grid grid-cols-2 gap-4">
          <SelectField
            label="Priorité"
            value={priority}
            onChange={setPriority}
            options={(["haute", "moyenne", "basse"] as OfferPriority[]).map((p) => ({
              value: p,
              label: PRIORITY_LABEL[p],
            }))}
          />
          <SelectField
            label="Statut"
            value={status}
            onChange={setStatus}
            options={OFFER_STATUS_ORDER.map((s) => ({ value: s, label: OFFER_STATUS_LABEL[s] }))}
          />
        </div>
        <div className="grid grid-cols-3 gap-4">
          <Field label="Date de candidature" type="date" value={dateApplied} onChange={setDateApplied} />
          <Field label="Deadline" type="date" value={deadline} onChange={setDeadline} />
          <Field label="Prochaine relance (override)" type="date" value={nextRelance} onChange={setNextRelance} />
        </div>
        <label className="flex items-center gap-2 text-sm text-ink-muted cursor-pointer">
          <input type="checkbox" checked={noRelance} onChange={(e) => setNoRelance(e.target.checked)} className="accent-brand-400" />
          Ne pas relancer (offre morte / suivi manuel)
        </label>
        <div>
          <label className="block text-xs font-medium text-ink-muted mb-1.5">Documents (bibliothèque)</label>
          <div className="grid grid-cols-2 gap-3">
            <DocumentPicker
              title="CV"
              docType="cv"
              value={cvDocId}
              current={initial?.cv_document}
              onChange={setCvDocId}
            />
            <DocumentPicker
              title="Lettre de motivation"
              docType="lm"
              value={lmDocId}
              current={initial?.lm_document}
              onChange={setLmDocId}
            />
          </div>
        </div>
        <div>
          <label className="block text-xs font-medium text-ink-muted mb-1.5">Notes</label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            className="w-full px-3 py-2 border border-line rounded-input text-sm resize-y bg-card"
            placeholder="Contexte, référent, infos utiles…"
          />
        </div>
      </div>
      <div className="px-6 py-4 border-t border-line flex items-center justify-end gap-2">
        <button onClick={onCancel} className="px-3 py-1.5 text-sm text-ink-muted hover:text-ink transition-default">
          Annuler
        </button>
        <button
          onClick={submit}
          disabled={!canSave || saving}
          className="px-4 py-1.5 bg-brand-400 text-white rounded-input text-sm font-medium hover:bg-brand-500 disabled:opacity-50"
        >
          {saving ? "Sauvegarde…" : initial ? "Mettre à jour" : "Enregistrer"}
        </button>
      </div>
    </Card>
  );
}
