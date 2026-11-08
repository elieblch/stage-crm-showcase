"use client";

import { useCallback, useEffect, useState } from "react";
import { ExternalLink, Mail, Phone, Trash2 } from "lucide-react";

import type { Contact, ContactInput, ContactStatus, Offer } from "@/types";
import {
  createContact,
  deleteContact,
  fetchContacts,
  fetchOffers,
  markContactRelanced,
  updateContact,
} from "@/lib/api";
import {
  Card,
  CardHeader,
  CONTACT_STATUS_LABEL,
  CONTACT_STATUS_ORDER,
  CONTACT_STATUS_PILL,
  Field,
  RelanceBadge,
  SelectField,
  fmtDate,
} from "@/components/ui/shared";
import { DocumentPicker } from "@/components/ui/DocumentPicker";
import { ContactDetail } from "./ContactDetail";

const d = (s: string | null | undefined) => (s ? s.slice(0, 10) : "");

function ContactForm({
  initial,
  prefill,
  warnings,
  offers,
  onSave,
  onCancel,
}: {
  initial?: Contact;
  prefill?: ContactInput;
  warnings?: string[];
  offers: Offer[];
  onSave: (data: ContactInput) => Promise<void>;
  onCancel: () => void;
}) {
  const [name, setName] = useState(initial?.name ?? prefill?.name ?? "");
  const [role, setRole] = useState(initial?.role ?? prefill?.role ?? "");
  const [company, setCompany] = useState(initial?.company ?? prefill?.company ?? "");
  const [email, setEmail] = useState(initial?.email ?? prefill?.email ?? "");
  const [linkedin, setLinkedin] = useState(initial?.linkedin_url ?? prefill?.linkedin_url ?? "");
  const [phone, setPhone] = useState(initial?.phone ?? prefill?.phone ?? "");
  const [offerId, setOfferId] = useState<string>(initial?.offer_id ? String(initial.offer_id) : "");
  const [status, setStatus] = useState<ContactStatus>(initial?.status ?? prefill?.status ?? "a_contacter");
  const [dateFirst, setDateFirst] = useState(d(initial?.date_first_contact));
  const [nextRelance, setNextRelance] = useState(d(initial?.next_relance_date));
  const [noRelance, setNoRelance] = useState(initial?.no_relance ?? false);
  const [notes, setNotes] = useState(initial?.notes ?? prefill?.notes ?? "");
  const [cvDocId, setCvDocId] = useState<number | null>(initial?.cv_document_id ?? null);
  const [lmDocId, setLmDocId] = useState<number | null>(initial?.lm_document_id ?? null);
  const [saving, setSaving] = useState(false);

  const submit = async () => {
    if (!name.trim()) return;
    setSaving(true);
    try {
      await onSave({
        name: name.trim(),
        role: role.trim() || null,
        company: company.trim() || null,
        email: email.trim() || null,
        linkedin_url: linkedin.trim() || null,
        phone: phone.trim() || null,
        offer_id: offerId ? Number(offerId) : null,
        status,
        date_first_contact: dateFirst || null,
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
        title={initial ? "Modifier le contact" : "Nouveau contact"}
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
          <Field label="Nom *" value={name} onChange={setName} placeholder="Jean Dupont" />
          <Field label="Rôle / poste" value={role} onChange={setRole} placeholder="Associate, Recruteur…" />
          <Field label="Entreprise" value={company} onChange={setCompany} placeholder="Lazard" />
          <Field label="Email" type="email" value={email} onChange={setEmail} placeholder="jean@…" />
          <Field label="LinkedIn" value={linkedin} onChange={setLinkedin} placeholder="https://linkedin.com/in/…" />
          <Field label="Téléphone" value={phone} onChange={setPhone} placeholder="+33…" />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <SelectField
            label="Statut"
            value={status}
            onChange={setStatus}
            options={CONTACT_STATUS_ORDER.map((s) => ({ value: s, label: CONTACT_STATUS_LABEL[s] }))}
          />
          <div>
            <label className="block text-xs font-medium text-ink-muted mb-1.5">Offre liée (optionnel)</label>
            <select
              value={offerId}
              onChange={(e) => setOfferId(e.target.value)}
              className="w-full px-3 py-2 border border-line rounded-input text-sm bg-card"
            >
              <option value="">— Aucune —</option>
              {offers.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.title} · {o.company}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Premier contact" type="date" value={dateFirst} onChange={setDateFirst} />
          <Field label="Prochaine relance (override)" type="date" value={nextRelance} onChange={setNextRelance} />
        </div>
        <label className="flex items-center gap-2 text-sm text-ink-muted cursor-pointer">
          <input type="checkbox" checked={noRelance} onChange={(e) => setNoRelance(e.target.checked)} className="accent-brand-400" />
          Ne pas relancer
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
          />
        </div>
      </div>
      <div className="px-6 py-4 border-t border-line flex items-center justify-end gap-2">
        <button onClick={onCancel} className="px-3 py-1.5 text-sm text-ink-muted hover:text-ink">
          Annuler
        </button>
        <button
          onClick={submit}
          disabled={!name.trim() || saving}
          className="px-4 py-1.5 bg-brand-400 text-white rounded-input text-sm font-medium hover:bg-brand-500 disabled:opacity-50"
        >
          {saving ? "Sauvegarde…" : initial ? "Mettre à jour" : "Enregistrer"}
        </button>
      </div>
    </Card>
  );
}

export function ContactsView({
  onChange,
  quickPrefill,
  quickWarnings,
  onQuickConsumed,
}: {
  onChange: () => void;
  quickPrefill?: ContactInput | null;
  quickWarnings?: string[];
  onQuickConsumed?: () => void;
}) {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [offers, setOffers] = useState<Offer[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<ContactStatus | "">("");
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<Contact | null>(null);
  const [selected, setSelected] = useState<Contact | null>(null);
  const [busy, setBusy] = useState<number | null>(null);

  useEffect(() => {
    if (quickPrefill) {
      setEditing(null);
      setShowForm(true);
    }
  }, [quickPrefill]);

  const closeForm = () => {
    setShowForm(false);
    setEditing(null);
    if (quickPrefill) onQuickConsumed?.();
  };

  const load = useCallback(() => {
    setLoading(true);
    fetchContacts({ status: statusFilter || undefined })
      .then(setContacts)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [statusFilter]);

  useEffect(() => {
    load();
    fetchOffers().then(setOffers).catch(() => {});
  }, [load]);

  const save = async (data: ContactInput) => {
    if (editing) {
      const updated = await updateContact(editing.id, data);
      if (selected?.id === editing.id) setSelected(updated);
    } else {
      await createContact(data);
    }
    closeForm();
    load();
    onChange();
  };

  const remove = async (id: number) => {
    if (!confirm("Supprimer ce contact ?")) return;
    await deleteContact(id);
    if (selected?.id === id) setSelected(null);
    load();
    onChange();
  };

  const relance = async (id: number) => {
    setBusy(id);
    try {
      await markContactRelanced(id);
      load();
      onChange();
    } finally {
      setBusy(null);
    }
  };

  const offerName = (id: number | null) => {
    if (!id) return null;
    const o = offers.find((x) => x.id === id);
    return o ? `${o.title} · ${o.company}` : null;
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-ink">Personnes contactées</h1>
          <p className="text-sm text-ink-muted mt-1">
            <span className="font-mono">{contacts.length}</span> contact{contacts.length > 1 ? "s" : ""}
          </p>
        </div>
        <button
          onClick={() => {
            setEditing(null);
            setShowForm(true);
          }}
          className="px-4 py-2 bg-ink text-white rounded-input text-sm font-medium hover:bg-ink/90 transition-default"
        >
          + Ajouter un contact
        </button>
      </div>

      {showForm && (
        <ContactForm
          initial={editing ?? undefined}
          prefill={!editing && quickPrefill ? quickPrefill : undefined}
          warnings={!editing && quickPrefill ? quickWarnings : undefined}
          offers={offers}
          onSave={save}
          onCancel={closeForm}
        />
      )}

      {selected && !showForm && (
        <ContactDetail
          contact={selected}
          offerLabel={offerName(selected.offer_id)}
          onClose={() => setSelected(null)}
          onEdit={() => {
            setEditing(selected);
            setShowForm(true);
          }}
          onDataChange={() => {
            load();
            onChange();
          }}
        />
      )}

      {!showForm && (
        <Card>
          <div className="flex items-center gap-3 flex-wrap text-sm">
            <span className="text-2xs font-semibold text-ink-faint uppercase tracking-wider">Filtres</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as ContactStatus | "")}
              className="px-2.5 py-1.5 border border-line rounded-input text-sm bg-card"
            >
              <option value="">Tous les statuts</option>
              {CONTACT_STATUS_ORDER.map((s) => (
                <option key={s} value={s}>
                  {CONTACT_STATUS_LABEL[s]}
                </option>
              ))}
            </select>
            {statusFilter && (
              <button onClick={() => setStatusFilter("")} className="text-2xs text-ink-faint hover:text-ink underline underline-offset-2">
                Réinitialiser
              </button>
            )}
          </div>
        </Card>
      )}

      {loading ? (
        <div className="text-center text-ink-faint py-12 text-sm">Chargement…</div>
      ) : contacts.length === 0 ? (
        <Card className="text-center py-12">
          <p className="text-sm text-ink-muted">Aucun contact.</p>
          <p className="text-xs text-ink-faint mt-1">Ajoutez les personnes que vous contactez (recruteurs, alumni, référents).</p>
        </Card>
      ) : (
        <div className="space-y-2">
          {contacts.map((c) => (
            <Card key={c.id} noPad className="card-hover">
              <div className="px-5 py-3.5 flex items-center gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-semibold text-ink">{c.name}</span>
                    {c.role && <span className="text-xs text-ink-muted">{c.role}</span>}
                    {c.company && <span className="text-xs text-ink-faint">· {c.company}</span>}
                    {c.needs_relance && <RelanceBadge daysOverdue={c.days_overdue} />}
                  </div>
                  <div className="flex items-center gap-3 mt-1 text-2xs text-ink-faint flex-wrap">
                    {c.email && (
                      <span className="inline-flex items-center gap-1">
                        <Mail size={11} /> {c.email}
                      </span>
                    )}
                    {c.phone && (
                      <span className="inline-flex items-center gap-1">
                        <Phone size={11} /> {c.phone}
                      </span>
                    )}
                    {c.linkedin_url && (
                      <a href={c.linkedin_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-brand-600 hover:underline">
                        <ExternalLink size={11} /> LinkedIn
                      </a>
                    )}
                    {offerName(c.offer_id) && <span className="text-ink-muted">↳ {offerName(c.offer_id)}</span>}
                    {c.date_first_contact && <span>1er contact {fmtDate(c.date_first_contact)}</span>}
                  </div>
                </div>
                <span className={`text-2xs px-2 py-0.5 rounded-pill font-medium shrink-0 ${CONTACT_STATUS_PILL[c.status]}`}>
                  {CONTACT_STATUS_LABEL[c.status]}
                </span>
                {c.needs_relance && (
                  <button
                    onClick={() => relance(c.id)}
                    disabled={busy === c.id}
                    className="px-2.5 py-1 text-2xs font-medium bg-ink text-white rounded-input hover:bg-ink/90 disabled:opacity-50 shrink-0"
                  >
                    Relancé
                  </button>
                )}
                <button
                  onClick={() => {
                    setSelected(c);
                    setShowForm(false);
                    setEditing(null);
                  }}
                  className="text-xs px-2 py-1 border border-line rounded-input hover:bg-surface-100 shrink-0"
                >
                  Détail
                </button>
                <button
                  onClick={() => {
                    setEditing(c);
                    setShowForm(true);
                  }}
                  className="text-xs px-2 py-1 border border-line rounded-input hover:bg-surface-100 shrink-0"
                >
                  Modifier
                </button>
                <button onClick={() => remove(c.id)} className="text-ink-faint hover:text-red-500 shrink-0" title="Supprimer">
                  <Trash2 size={15} />
                </button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
