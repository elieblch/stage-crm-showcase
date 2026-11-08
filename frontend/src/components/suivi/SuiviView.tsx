"use client";

import { useEffect, useMemo, useState } from "react";
import { fetchApplications, updateApplication } from "@/lib/api";
import type { Application } from "@/types";
import { Card, STAT_ORDER, STAT_LABEL, STAT_COLOR, resolveUserId } from "@/components/ui/shared";
import { DetailPanel } from "@/components/candidature/DetailPanel";

export function SuiviView({ onNav }: { onNav: (t: "candidatures") => void }) {
  const userId = resolveUserId();
  const [apps, setApps] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [panel, setPanel] = useState<Application | null>(null);

  useEffect(() => { fetchApplications(userId).then(setApps).catch(() => {}).finally(() => setLoading(false)); }, [userId]);

  const stats = useMemo(() => { const m: Record<string, number> = {}; apps.forEach((a) => { m[a.status] = (m[a.status] || 0) + 1; }); return m; }, [apps]);
  const next = (a: Application) => ({ draft: "Rediger", ready: "Envoyer", sent: "Attendre", acknowledged: "Preparer entretien", interview: "Entretien", offer: "Decider", accepted: "Terminee", rejected: "-" }[a.status] || "");

  if (loading) return <div className="text-center text-gray-400 py-12">Chargement...</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="font-display text-ink">Suivi</h1>
        <button onClick={() => onNav("candidatures")} className="px-4 py-2 text-sm font-medium bg-ink text-white rounded-input hover:bg-ink/90 transition-default">Vue Kanban</button>
      </div>

      {Object.keys(stats).length > 0 && (
        <div className="flex flex-wrap gap-2">
          {STAT_ORDER.filter((s) => stats[s]).map((s) => <span key={s} className={`px-3 py-1 rounded-pill text-xs font-medium ${STAT_COLOR[s]}`}>{STAT_LABEL[s]} : {stats[s]}</span>)}
        </div>
      )}

      {apps.length === 0 ? (
        <Card className="text-center py-12 text-gray-400">Aucune candidature.</Card>
      ) : (
        <Card noPad className="overflow-hidden">
          <table className="w-full">
            <thead><tr className="border-b border-surface-200 bg-surface-50">
              {["Entreprise", "Poste", "Statut", "Date", "Prochaine action"].map((h) => <th key={h} className="text-left px-5 py-3 text-2xs font-semibold text-gray-400 uppercase tracking-wider">{h}</th>)}
            </tr></thead>
            <tbody className="divide-y divide-surface-200">
              {apps.map((a) => (
                <tr key={a.id} className="table-row-hover cursor-pointer transition-default" onClick={() => setPanel(a)}>
                  <td className="px-5 py-3.5 text-sm font-medium text-gray-900">{a.offer?.company_name || "-"}</td>
                  <td className="px-5 py-3.5 text-sm text-gray-700 truncate max-w-[240px]">{a.offer?.title || "-"}</td>
                  <td className="px-5 py-3.5"><span className={`px-2.5 py-1 rounded-pill text-2xs font-medium ${STAT_COLOR[a.status]}`}>{STAT_LABEL[a.status]}</span></td>
                  <td className="px-5 py-3.5 text-sm text-gray-500">{new Date(a.updated_at).toLocaleDateString("fr-FR")}</td>
                  <td className="px-5 py-3.5 text-sm text-gray-400">{next(a)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {panel && <DetailPanel app={panel} onClose={() => setPanel(null)} onMove={async (s) => { try { await updateApplication(panel.id, { status: s }); setApps((p) => p.map((a) => a.id === panel.id ? { ...a, status: s, updated_at: new Date().toISOString() } : a)); setPanel((p) => p ? { ...p, status: s } : p); } catch {} }} onRefresh={() => fetchApplications(userId).then(setApps).catch(() => {})} />}
    </div>
  );
}
