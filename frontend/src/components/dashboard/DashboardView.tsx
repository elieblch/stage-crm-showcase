"use client";

import { useCallback, useEffect, useState } from "react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { AlertTriangle, CalendarClock, CheckCircle2 } from "lucide-react";

import type { Dashboard, RelancesResponse } from "@/types";
import { fetchDashboard, fetchRelances, markContactRelanced, markOfferRelanced } from "@/lib/api";
import {
  Card,
  CardHeader,
  CONTACT_STATUS_LABEL,
  OFFER_STATUS_BG,
  OFFER_STATUS_LABEL,
  OFFER_STATUS_ORDER,
  fmtDate,
} from "@/components/ui/shared";
import type { Tab } from "@/components/layout/Sidebar";

export function DashboardView({ onNav, onChange }: { onNav: (t: Tab) => void; onChange: () => void }) {
  const [stats, setStats] = useState<Dashboard | null>(null);
  const [rel, setRel] = useState<RelancesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(() => {
    Promise.all([fetchDashboard(), fetchRelances()])
      .then(([s, r]) => {
        setStats(s);
        setRel(r);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const doRelance = async (kind: "offer" | "contact", id: number) => {
    setBusy(`${kind}-${id}`);
    try {
      if (kind === "offer") await markOfferRelanced(id);
      else await markContactRelanced(id);
      load();
      onChange();
    } finally {
      setBusy(null);
    }
  };

  if (loading) return <div className="text-ink-faint text-sm py-12 text-center">Chargement…</div>;

  const donutData = stats
    ? OFFER_STATUS_ORDER.map((s) => ({
        name: OFFER_STATUS_LABEL[s],
        value: stats.offers_by_status[s] || 0,
        key: s,
      })).filter((d) => d.value > 0)
    : [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-ink">Dashboard</h1>
        <p className="text-sm text-ink-muted mt-1">Vue d&apos;ensemble de votre recherche de stage</p>
      </div>

      {/* Compteurs clés */}
      <div className="grid grid-cols-4 gap-3">
        <Stat label="Offres" value={stats?.offers_total ?? 0} />
        <Stat label="Contacts" value={stats?.contacts_total ?? 0} />
        <Stat
          label="Relances à faire"
          value={stats?.relances_due ?? 0}
          accent={(stats?.relances_due ?? 0) > 0 ? "amber" : undefined}
        />
        <Stat
          label="Deadlines proches"
          value={stats?.deadlines_soon ?? 0}
          accent={(stats?.deadlines_soon ?? 0) > 0 ? "red" : undefined}
        />
      </div>

      {/* Relances à faire — en tête */}
      <Card noPad>
        <CardHeader
          title="Relances à faire"
          right={<span className="text-2xs font-mono text-ink-faint">{rel?.relances.length ?? 0}</span>}
        />
        {rel && rel.relances.length > 0 ? (
          <div className="divide-y divide-line-subtle">
            {rel.relances.map((r) => (
              <div key={`${r.kind}-${r.id}`} className="flex items-center gap-3 px-5 py-3">
                <AlertTriangle size={16} className="text-amber-500 shrink-0" strokeWidth={1.75} />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-ink truncate">
                    {r.title}
                    {r.company && <span className="text-ink-faint font-normal"> · {r.company}</span>}
                  </div>
                  <div className="text-2xs text-ink-muted">
                    {r.kind === "offer" ? "Offre" : "Contact"} · échéance {fmtDate(r.due_date)} ·{" "}
                    <span className="text-amber-700 font-medium">
                      {r.days_overdue > 0 ? `${r.days_overdue}j de retard` : "à relancer aujourd'hui"}
                    </span>
                  </div>
                </div>
                <button
                  onClick={() => doRelance(r.kind, r.id)}
                  disabled={busy === `${r.kind}-${r.id}`}
                  className="px-3 py-1.5 text-xs font-medium bg-ink text-white rounded-input hover:bg-ink/90 transition-default disabled:opacity-50 shrink-0"
                >
                  Marqué comme relancé
                </button>
              </div>
            ))}
          </div>
        ) : (
          <div className="px-5 py-8 text-center text-sm text-ink-muted flex flex-col items-center gap-2">
            <CheckCircle2 size={22} className="text-brand-400" strokeWidth={1.5} />
            Aucune relance en attente. Tout est à jour.
          </div>
        )}
      </Card>

      {/* Deadlines proches */}
      {rel && rel.deadlines.length > 0 && (
        <Card noPad>
          <CardHeader title="Deadlines de candidature proches" />
          <div className="divide-y divide-line-subtle">
            {rel.deadlines.map((d) => (
              <div key={d.id} className="flex items-center gap-3 px-5 py-3">
                <CalendarClock size={16} className="text-red-500 shrink-0" strokeWidth={1.75} />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-ink truncate">
                    {d.title} <span className="text-ink-faint font-normal">· {d.company}</span>
                  </div>
                  <div className="text-2xs text-ink-muted">Limite : {fmtDate(d.deadline)}</div>
                </div>
                <span className="text-xs font-medium text-red-600 shrink-0">
                  {d.days_left === 0 ? "aujourd'hui" : `dans ${d.days_left}j`}
                </span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Répartition par statut */}
      <div className="grid grid-cols-2 gap-4">
        <Card noPad>
          <CardHeader title="Offres par statut" />
          <div className="p-5">
            {donutData.length > 0 ? (
              <div className="flex items-center gap-5">
                <div className="w-36 h-36 shrink-0">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={donutData}
                        dataKey="value"
                        nameKey="name"
                        innerRadius={42}
                        outerRadius={64}
                        paddingAngle={2}
                      >
                        {donutData.map((d) => (
                          <Cell key={d.key} fill={OFFER_STATUS_BG[d.key]} />
                        ))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <div className="flex-1 space-y-1.5">
                  {donutData.map((d) => (
                    <div key={d.key} className="flex items-center gap-2 text-xs">
                      <span className="w-2.5 h-2.5 rounded-sm" style={{ background: OFFER_STATUS_BG[d.key] }} />
                      <span className="text-ink-muted flex-1">{d.name}</span>
                      <span className="font-mono text-ink">{d.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <p className="text-sm text-ink-muted text-center py-6">Aucune offre.</p>
            )}
          </div>
        </Card>

        <Card noPad>
          <CardHeader title="Contacts par statut" />
          <div className="p-5 space-y-2">
            {stats &&
              Object.entries(stats.contacts_by_status)
                .filter(([, v]) => v > 0)
                .map(([k, v]) => (
                  <div key={k} className="flex items-center gap-2 text-sm">
                    <span className="text-ink-muted flex-1">
                      {CONTACT_STATUS_LABEL[k as keyof typeof CONTACT_STATUS_LABEL]}
                    </span>
                    <span className="font-mono text-ink">{v}</span>
                  </div>
                ))}
            {stats && stats.contacts_total === 0 && (
              <p className="text-sm text-ink-muted text-center py-6">Aucun contact.</p>
            )}
          </div>
        </Card>
      </div>

      <div className="flex gap-2">
        <button
          onClick={() => onNav("offres")}
          className="px-4 py-2 bg-brand-400 text-white rounded-input text-sm font-medium hover:bg-brand-500 transition-default"
        >
          + Ajouter une offre
        </button>
        <button
          onClick={() => onNav("contacts")}
          className="px-4 py-2 border border-line text-ink rounded-input text-sm font-medium hover:bg-surface-100 transition-default"
        >
          + Ajouter un contact
        </button>
      </div>
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: number; accent?: "amber" | "red" }) {
  const color = accent === "amber" ? "text-amber-700" : accent === "red" ? "text-red-600" : "text-ink";
  return (
    <Card>
      <div className={`font-display text-3xl ${color}`}>{value}</div>
      <div className="text-xs text-ink-muted mt-1">{label}</div>
    </Card>
  );
}
