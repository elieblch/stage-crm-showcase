"use client";

import { useEffect, useState } from "react";
import { Download, FileText, X } from "lucide-react";

import type { Contact, DocumentBrief, Offer } from "@/types";
import { documentDownloadUrl, fetchOfferContacts } from "@/lib/api";
import {
  Card,
  CardHeader,
  CONTACT_STATUS_LABEL,
  CONTACT_STATUS_PILL,
  OFFER_STATUS_LABEL,
  OFFER_STATUS_PILL,
  PRIORITY_LABEL,
  RelanceBadge,
  fmtDate,
} from "@/components/ui/shared";
import { Timeline } from "@/components/ui/Timeline";
import { InterviewsSection } from "./InterviewsSection";

// Affichage en lecture seule d'un document lié (la sélection se fait dans le formulaire).
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

export function OfferDetail({
  offer,
  onClose,
  onEdit,
  onDataChange,
  onNavStories,
}: {
  offer: Offer;
  onClose: () => void;
  onEdit: () => void;
  onDataChange?: () => void;
  onNavStories?: () => void;
}) {
  const [contacts, setContacts] = useState<Contact[]>([]);

  useEffect(() => {
    fetchOfferContacts(offer.id).then(setContacts).catch(() => setContacts([]));
  }, [offer.id]);

  return (
    <Card noPad>
      <CardHeader
        title={offer.title}
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
          <span className={`text-2xs px-2 py-0.5 rounded-pill font-medium ${OFFER_STATUS_PILL[offer.status]}`}>
            {OFFER_STATUS_LABEL[offer.status]}
          </span>
          <span className="text-2xs px-2 py-0.5 rounded-pill bg-surface-100 text-ink-muted">
            Priorité {PRIORITY_LABEL[offer.priority]}
          </span>
          {offer.needs_relance && <RelanceBadge daysOverdue={offer.days_overdue} />}
          {offer.no_relance && <span className="text-2xs px-2 py-0.5 rounded-pill bg-gray-100 text-gray-500">Sans relance</span>}
        </div>

        <div className="grid grid-cols-2 gap-y-2 gap-x-4 text-sm">
          <Info label="Entreprise" value={offer.company} />
          <Info label="Localisation" value={offer.location || "—"} />
          <Info label="Source" value={offer.source || "—"} />
          <Info
            label="Lien"
            value={
              offer.url ? (
                <a href={offer.url} target="_blank" rel="noreferrer" className="text-brand-600 hover:underline truncate">
                  Ouvrir l&apos;offre
                </a>
              ) : (
                "—"
              )
            }
          />
          <Info label="Ajoutée le" value={fmtDate(offer.date_added)} />
          <Info label="Candidature" value={fmtDate(offer.date_applied)} />
          <Info label="Deadline" value={fmtDate(offer.deadline)} />
          <Info label="Dernière action" value={fmtDate(offer.last_action_date)} />
          {offer.next_relance_date && <Info label="Relance prévue" value={fmtDate(offer.next_relance_date)} />}
        </div>

        {offer.notes && (
          <div>
            <div className="text-2xs font-semibold text-ink-faint uppercase mb-1">Notes</div>
            <p className="text-sm text-ink-muted whitespace-pre-wrap">{offer.notes}</p>
          </div>
        )}

        <div>
          <div className="text-2xs font-semibold text-ink-faint uppercase mb-2">Documents</div>
          <div className="grid grid-cols-2 gap-3">
            <DocView title="CV" doc={offer.cv_document} />
            <DocView title="Lettre de motivation" doc={offer.lm_document} />
          </div>
        </div>

        <div>
          <div className="text-2xs font-semibold text-ink-faint uppercase mb-2">
            Contacts liés ({contacts.length})
          </div>
          {contacts.length > 0 ? (
            <div className="space-y-1.5">
              {contacts.map((c) => (
                <div key={c.id} className="flex items-center gap-2 text-sm border border-line rounded-input px-3 py-2">
                  <span className="font-medium text-ink">{c.name}</span>
                  {c.role && <span className="text-ink-faint text-xs">· {c.role}</span>}
                  <span className={`ml-auto text-2xs px-2 py-0.5 rounded-pill font-medium ${CONTACT_STATUS_PILL[c.status]}`}>
                    {CONTACT_STATUS_LABEL[c.status]}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-ink-faint">Aucun contact lié à cette offre.</p>
          )}
        </div>

        <div className="border-t border-line pt-4">
          <InterviewsSection
            offerId={offer.id}
            onChange={onDataChange}
            onNavStories={onNavStories}
          />
        </div>

        <div className="border-t border-line pt-4">
          <Timeline parentType="offer" parentId={offer.id} onChange={onDataChange} />
        </div>
      </div>
    </Card>
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
