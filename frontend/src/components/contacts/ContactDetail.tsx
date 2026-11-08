"use client";

import { Download, ExternalLink, FileText, Mail, Phone, X } from "lucide-react";

import type { Contact, DocumentBrief } from "@/types";
import { documentDownloadUrl } from "@/lib/api";
import {
  Card,
  CardHeader,
  CONTACT_STATUS_LABEL,
  CONTACT_STATUS_PILL,
  RelanceBadge,
  fmtDate,
} from "@/components/ui/shared";
import { Timeline } from "@/components/ui/Timeline";

function DocView({ title, doc }: { title: string; doc: DocumentBrief | null }) {
  return (
    <div className="border border-line rounded-card p-3">
      <div className="flex items-center gap-2 mb-1.5">
        <FileText size={15} className="text-ink-faint" strokeWidth={1.75} />
        <span className="text-xs font-medium text-ink">{title}</span>
      </div>
      {doc ? (
        <a
          href={documentDownloadUrl(doc.id)}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1.5 text-xs text-brand-600 hover:text-brand-700 font-medium"
        >
          <Download size={13} /> {doc.label}
        </a>
      ) : (
        <span className="text-xs text-ink-faint">Aucun document lié.</span>
      )}
    </div>
  );
}

function Info({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <div className="text-2xs text-ink-faint">{label}</div>
      <div className="text-ink">{value}</div>
    </div>
  );
}

export function ContactDetail({
  contact,
  offerLabel,
  onClose,
  onEdit,
  onDataChange,
}: {
  contact: Contact;
  offerLabel?: string | null;
  onClose: () => void;
  onEdit: () => void;
  onDataChange?: () => void;
}) {
  return (
    <Card noPad>
      <CardHeader
        title={contact.name}
        right={
          <div className="flex items-center gap-2">
            <button onClick={onEdit} className="text-xs px-2.5 py-1 border border-line rounded-input hover:bg-surface-100">
              Modifier
            </button>
            <button onClick={onClose} className="text-ink-faint hover:text-ink">
              <X size={18} />
            </button>
          </div>
        }
      />
      <div className="p-6 space-y-5">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`text-2xs px-2 py-0.5 rounded-pill font-medium ${CONTACT_STATUS_PILL[contact.status]}`}>
            {CONTACT_STATUS_LABEL[contact.status]}
          </span>
          {contact.needs_relance && <RelanceBadge daysOverdue={contact.days_overdue} />}
          {contact.no_relance && (
            <span className="text-2xs px-2 py-0.5 rounded-pill bg-gray-100 text-gray-500">Sans relance</span>
          )}
        </div>

        <div className="grid grid-cols-2 gap-y-2 gap-x-4 text-sm">
          <Info label="Rôle / poste" value={contact.role || "—"} />
          <Info label="Entreprise" value={contact.company || "—"} />
          <Info
            label="Email"
            value={
              contact.email ? (
                <a href={`mailto:${contact.email}`} className="inline-flex items-center gap-1 text-brand-600 hover:underline">
                  <Mail size={12} /> {contact.email}
                </a>
              ) : (
                "—"
              )
            }
          />
          <Info
            label="Téléphone"
            value={
              contact.phone ? (
                <span className="inline-flex items-center gap-1">
                  <Phone size={12} /> {contact.phone}
                </span>
              ) : (
                "—"
              )
            }
          />
          <Info
            label="LinkedIn"
            value={
              contact.linkedin_url ? (
                <a href={contact.linkedin_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-brand-600 hover:underline">
                  <ExternalLink size={12} /> Profil
                </a>
              ) : (
                "—"
              )
            }
          />
          <Info label="Offre liée" value={offerLabel || "—"} />
          <Info label="Premier contact" value={fmtDate(contact.date_first_contact)} />
          <Info label="Dernière action" value={fmtDate(contact.last_action_date)} />
          {contact.next_relance_date && <Info label="Relance prévue" value={fmtDate(contact.next_relance_date)} />}
        </div>

        {contact.notes && (
          <div>
            <div className="text-2xs font-semibold text-ink-faint uppercase mb-1">Notes</div>
            <p className="text-sm text-ink-muted whitespace-pre-wrap">{contact.notes}</p>
          </div>
        )}

        <div>
          <div className="text-2xs font-semibold text-ink-faint uppercase mb-2">Documents</div>
          <div className="grid grid-cols-2 gap-3">
            <DocView title="CV" doc={contact.cv_document} />
            <DocView title="Lettre de motivation" doc={contact.lm_document} />
          </div>
        </div>

        <div className="border-t border-line pt-4">
          <Timeline parentType="contact" parentId={contact.id} onChange={onDataChange} />
        </div>
      </div>
    </Card>
  );
}
