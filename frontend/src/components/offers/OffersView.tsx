"use client";

import { useCallback, useEffect, useState } from "react";
import { LayoutGrid, List as ListIcon, Trash2 } from "lucide-react";

import type { Offer, OfferInput, OfferPriority, OfferStatus } from "@/types";
import {
  createOffer,
  deleteOffer,
  fetchOffers,
  updateOffer,
} from "@/lib/api";
import {
  Card,
  OFFER_STATUS_BG,
  OFFER_STATUS_LABEL,
  OFFER_STATUS_ORDER,
  OFFER_STATUS_PILL,
  PRIORITY_LABEL,
  PRIORITY_PILL,
  RelanceBadge,
  fmtDate,
} from "@/components/ui/shared";
import { OfferForm } from "./OfferForm";
import { OfferDetail } from "./OfferDetail";

type View = "list" | "kanban";

export function OffersView({
  onChange,
  quickPrefill,
  quickWarnings,
  onQuickConsumed,
  onNavStories,
}: {
  onChange: () => void;
  quickPrefill?: OfferInput | null;
  quickWarnings?: string[];
  onQuickConsumed?: () => void;
  onNavStories?: () => void;
}) {
  const [offers, setOffers] = useState<Offer[]>([]);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState<View>("list");
  const [statusFilter, setStatusFilter] = useState<OfferStatus | "">("");
  const [priorityFilter, setPriorityFilter] = useState<OfferPriority | "">("");
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<Offer | null>(null);
  const [selected, setSelected] = useState<Offer | null>(null);

  // Ouvre le formulaire pré-rempli quand un bloc « Ajout rapide » est appliqué.
  useEffect(() => {
    if (quickPrefill) {
      setEditing(null);
      setSelected(null);
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
    fetchOffers({
      status: statusFilter || undefined,
      priority: priorityFilter || undefined,
    })
      .then(setOffers)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [statusFilter, priorityFilter]);

  useEffect(() => {
    load();
  }, [load]);

  const save = async (data: OfferInput) => {
    if (editing) await updateOffer(editing.id, data);
    else await createOffer(data);
    closeForm();
    load();
    onChange();
  };

  const remove = async (id: number) => {
    if (!confirm("Supprimer cette offre ?")) return;
    await deleteOffer(id);
    if (selected?.id === id) setSelected(null);
    load();
    onChange();
  };

  const moveTo = async (offer: Offer, status: OfferStatus) => {
    if (offer.status === status) return;
    // Maj optimiste.
    setOffers((prev) => prev.map((o) => (o.id === offer.id ? { ...o, status } : o)));
    await updateOffer(offer.id, { status });
    load();
    onChange();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-ink">Offres en ligne</h1>
          <p className="text-sm text-ink-muted mt-1">
            <span className="font-mono">{offers.length}</span> offre{offers.length > 1 ? "s" : ""} suivie
            {offers.length > 1 ? "s" : ""}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex border border-line rounded-input overflow-hidden">
            <button
              onClick={() => setView("list")}
              className={`px-2.5 py-1.5 ${view === "list" ? "bg-surface-100 text-ink" : "text-ink-faint"}`}
              title="Liste"
            >
              <ListIcon size={15} />
            </button>
            <button
              onClick={() => setView("kanban")}
              className={`px-2.5 py-1.5 ${view === "kanban" ? "bg-surface-100 text-ink" : "text-ink-faint"}`}
              title="Kanban"
            >
              <LayoutGrid size={15} />
            </button>
          </div>
          <button
            onClick={() => {
              setEditing(null);
              setShowForm(true);
              setSelected(null);
            }}
            className="px-4 py-2 bg-ink text-white rounded-input text-sm font-medium hover:bg-ink/90 transition-default"
          >
            + Ajouter une offre
          </button>
        </div>
      </div>

      {showForm && (
        <OfferForm
          initial={editing ?? undefined}
          prefill={!editing && quickPrefill ? quickPrefill : undefined}
          warnings={!editing && quickPrefill ? quickWarnings : undefined}
          onSave={save}
          onCancel={closeForm}
        />
      )}

      {selected && !showForm && (
        <OfferDetail
          offer={selected}
          onClose={() => setSelected(null)}
          onEdit={() => {
            setEditing(selected);
            setShowForm(true);
          }}
          onDataChange={() => {
            load();
            onChange();
          }}
          onNavStories={onNavStories}
        />
      )}

      {/* Filtres */}
      {!showForm && (
        <Card>
          <div className="flex items-center gap-3 flex-wrap text-sm">
            <span className="text-2xs font-semibold text-ink-faint uppercase tracking-wider">Filtres</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as OfferStatus | "")}
              className="px-2.5 py-1.5 border border-line rounded-input text-sm bg-card"
            >
              <option value="">Tous les statuts</option>
              {OFFER_STATUS_ORDER.map((s) => (
                <option key={s} value={s}>
                  {OFFER_STATUS_LABEL[s]}
                </option>
              ))}
            </select>
            <select
              value={priorityFilter}
              onChange={(e) => setPriorityFilter(e.target.value as OfferPriority | "")}
              className="px-2.5 py-1.5 border border-line rounded-input text-sm bg-card"
            >
              <option value="">Toutes priorités</option>
              {(["haute", "moyenne", "basse"] as OfferPriority[]).map((p) => (
                <option key={p} value={p}>
                  {PRIORITY_LABEL[p]}
                </option>
              ))}
            </select>
            {(statusFilter || priorityFilter) && (
              <button
                onClick={() => {
                  setStatusFilter("");
                  setPriorityFilter("");
                }}
                className="text-2xs text-ink-faint hover:text-ink underline underline-offset-2"
              >
                Réinitialiser
              </button>
            )}
          </div>
        </Card>
      )}

      {loading ? (
        <div className="text-center text-ink-faint py-12 text-sm">Chargement…</div>
      ) : offers.length === 0 ? (
        <Card className="text-center py-12">
          <p className="text-sm text-ink-muted">Aucune offre.</p>
          <p className="text-xs text-ink-faint mt-1">Ajoutez manuellement les offres repérées en ligne.</p>
        </Card>
      ) : view === "list" ? (
        <OfferTable offers={offers} onSelect={setSelected} onDelete={remove} selectedId={selected?.id} />
      ) : (
        <OfferKanban offers={offers} onMove={moveTo} onSelect={setSelected} />
      )}
    </div>
  );
}

function OfferTable({
  offers,
  onSelect,
  onDelete,
  selectedId,
}: {
  offers: Offer[];
  onSelect: (o: Offer) => void;
  onDelete: (id: number) => void;
  selectedId?: number;
}) {
  return (
    <Card noPad>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-2xs text-ink-faint uppercase tracking-wider border-b border-line">
            <th className="text-left font-medium px-5 py-2.5">Poste</th>
            <th className="text-left font-medium px-3 py-2.5">Entreprise</th>
            <th className="text-left font-medium px-3 py-2.5">Priorité</th>
            <th className="text-left font-medium px-3 py-2.5">Statut</th>
            <th className="text-left font-medium px-3 py-2.5">Ajoutée</th>
            <th className="px-3 py-2.5"></th>
          </tr>
        </thead>
        <tbody>
          {offers.map((o) => (
            <tr
              key={o.id}
              onClick={() => onSelect(o)}
              className={`border-b border-line-subtle table-row-hover cursor-pointer ${selectedId === o.id ? "bg-surface-100" : ""}`}
            >
              <td className="px-5 py-3">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-ink">{o.title}</span>
                  {o.needs_relance && <RelanceBadge daysOverdue={o.days_overdue} />}
                </div>
              </td>
              <td className="px-3 py-3 text-ink-muted">{o.company}</td>
              <td className="px-3 py-3">
                <span className={`text-2xs px-2 py-0.5 rounded-pill font-medium ${PRIORITY_PILL[o.priority]}`}>
                  {PRIORITY_LABEL[o.priority]}
                </span>
              </td>
              <td className="px-3 py-3">
                <span className={`text-2xs px-2 py-0.5 rounded-pill font-medium ${OFFER_STATUS_PILL[o.status]}`}>
                  {OFFER_STATUS_LABEL[o.status]}
                </span>
              </td>
              <td className="px-3 py-3 text-ink-faint text-xs font-mono">{fmtDate(o.date_added)}</td>
              <td className="px-3 py-3 text-right">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete(o.id);
                  }}
                  className="text-ink-faint hover:text-red-500 transition-default"
                  title="Supprimer"
                >
                  <Trash2 size={15} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

function OfferKanban({
  offers,
  onMove,
  onSelect,
}: {
  offers: Offer[];
  onMove: (o: Offer, s: OfferStatus) => void;
  onSelect: (o: Offer) => void;
}) {
  const [dragId, setDragId] = useState<number | null>(null);

  const onDrop = (e: React.DragEvent, status: OfferStatus) => {
    e.preventDefault();
    const id = Number(e.dataTransfer.getData("text/plain"));
    const offer = offers.find((o) => o.id === id);
    if (offer) onMove(offer, status);
    setDragId(null);
  };

  return (
    <div className="flex gap-3 overflow-x-auto pb-4">
      {OFFER_STATUS_ORDER.map((status) => {
        const col = offers.filter((o) => o.status === status);
        return (
          <div
            key={status}
            className="flex-shrink-0 w-64"
            onDrop={(e) => onDrop(e, status)}
            onDragOver={(e) => {
              e.preventDefault();
              e.dataTransfer.dropEffect = "move";
            }}
          >
            <div className="flex items-center gap-2 mb-2 px-1">
              <span className="w-2 h-2 rounded-sm" style={{ background: OFFER_STATUS_BG[status] }} />
              <span className="kanban-col-header text-ink-muted">{OFFER_STATUS_LABEL[status]}</span>
              <span className="text-2xs font-mono text-ink-faint ml-auto">{col.length}</span>
            </div>
            <div className="space-y-2 min-h-[60px] bg-surface-50 rounded-card p-1.5">
              {col.map((o) => (
                <div
                  key={o.id}
                  draggable
                  onDragStart={(e) => {
                    e.dataTransfer.setData("text/plain", String(o.id));
                    e.dataTransfer.effectAllowed = "move";
                    setDragId(o.id);
                  }}
                  onDragEnd={() => setDragId(null)}
                  onClick={() => onSelect(o)}
                  className={`bg-card border border-line rounded-card p-3 cursor-pointer card-hover ${dragId === o.id ? "opacity-50" : ""}`}
                >
                  <div className="text-sm font-medium text-ink leading-snug">{o.title}</div>
                  <div className="text-xs text-ink-muted mt-0.5">{o.company}</div>
                  <div className="flex items-center gap-1.5 mt-2 flex-wrap">
                    <span className={`text-2xs px-1.5 py-0.5 rounded-pill font-medium ${PRIORITY_PILL[o.priority]}`}>
                      {PRIORITY_LABEL[o.priority]}
                    </span>
                    {o.needs_relance && <RelanceBadge daysOverdue={o.days_overdue} />}
                  </div>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
