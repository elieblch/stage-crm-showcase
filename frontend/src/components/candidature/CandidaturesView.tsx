"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchApplications, updateApplication, deleteApplication } from "@/lib/api";
import type { Application, ApplicationStatus } from "@/types";
import { Card, STAT_ORDER, STAT_LABEL, STAT_BG, resolveUserId } from "@/components/ui/shared";
import { DetailPanel } from "@/components/candidature/DetailPanel";

export function CandidaturesView() {
  const userId = resolveUserId();
  const [apps, setApps] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [panel, setPanel] = useState<Application | null>(null);

  const load = useCallback(async () => { try { setApps(await fetchApplications(userId)); } catch {} setLoading(false); }, [userId]);
  useEffect(() => { load(); }, [load]);

  const move = async (id: string, s: ApplicationStatus) => {
    setApps((p) => p.map((a) => a.id === id ? { ...a, status: s, updated_at: new Date().toISOString() } : a));
    if (panel?.id === id) setPanel((p) => p ? { ...p, status: s } : p);
    try { await updateApplication(id, { status: s }); } catch { load(); }
  };

  const del = async (id: string) => {
    try { await deleteApplication(id); setApps((p) => p.filter((a) => a.id !== id)); if (panel?.id === id) setPanel(null); } catch { alert("Erreur lors de la suppression."); }
  };

  const onDragStart = (e: React.DragEvent, id: string) => { e.dataTransfer.setData("text/plain", id); e.dataTransfer.effectAllowed = "move"; };
  const onDrop = (e: React.DragEvent, s: ApplicationStatus) => { e.preventDefault(); const id = e.dataTransfer.getData("text/plain"); if (id) move(id, s); };
  const onDragOver = (e: React.DragEvent) => { e.preventDefault(); e.dataTransfer.dropEffect = "move"; };

  if (loading) return <div className="text-center text-gray-400 py-12">Chargement...</div>;

  return (
    <div>
      <h1 className="font-display text-ink mb-6">Candidatures</h1>
      {apps.length === 0 ? (
        <Card className="text-center py-12 text-ink-faint">Aucune candidature. Allez dans Recherche pour en créer.</Card>
      ) : (
        <div className="flex gap-3 overflow-x-auto pb-4">
          {STAT_ORDER.map((s) => {
            const col = apps.filter((a) => a.status === s);
            return (
              <div key={s} className="flex-shrink-0 w-64" onDrop={(e) => onDrop(e, s)} onDragOver={onDragOver}>
                {/* Header : bordure top colorée 3px */}
                <div className="rounded-t-card border-t-[3px] bg-surface-100/60 px-3 py-2 flex items-center gap-2" style={{ borderColor: STAT_BG[s] }}>
                  <span className="kanban-col-header text-ink">{STAT_LABEL[s]}</span>
                  <span className="text-2xs text-ink-faint font-mono ml-auto">{col.length}</span>
                </div>
                <div className="space-y-2 min-h-[80px] rounded-b-card bg-surface-100/40 p-2">
                  {col.map((a) => (
                    <div
                      key={a.id}
                      draggable
                      onDragStart={(e) => onDragStart(e, a.id)}
                      onClick={() => setPanel(a)}
                      className="bg-card rounded-card border border-line p-3 card-hover group cursor-pointer"
                    >
                      <div className="flex items-start justify-between gap-1">
                        <div className="text-sm font-medium text-ink truncate">{a.offer?.title || "Offre"}</div>
                        {a.status === "draft" && (
                          <button
                            onClick={(e) => { e.stopPropagation(); if (confirm("Supprimer cette candidature ?")) del(a.id); }}
                            className="opacity-0 group-hover:opacity-100 p-0.5 text-ink-faint hover:text-danger-600 transition-default"
                            title="Supprimer"
                          >
                            <svg width="13" height="13" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                          </button>
                        )}
                      </div>
                      <div className="text-xs text-ink-muted mt-0.5 truncate">{a.offer?.company_name}</div>
                      <div className="flex items-center gap-1.5 mt-2">
                        <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: STAT_BG[s] }} />
                        <span className="text-2xs text-ink-faint font-mono">{new Date(a.updated_at).toLocaleDateString("fr-FR")}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
      {panel && <DetailPanel app={panel} onClose={() => setPanel(null)} onMove={(s) => move(panel.id, s)} onRefresh={load} />}
    </div>
  );
}
