"use client";

import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type {
  ByCvStats,
  FunnelStats,
  OutreachStats,
  ResponseRateStats,
  WeeklyActivityStats,
} from "@/types";
import {
  fetchByCv,
  fetchFunnel,
  fetchOutreach,
  fetchResponseRate,
  fetchWeeklyActivity,
} from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/shared";

const BRAND = "#1D9E75";
const FUNNEL_COLORS = ["#378ADD", "#1D9E75", "#7F77DD", "#639922"];

const pct = (v: number | null) => (v == null ? "—" : `${Math.round(v * 100)}%`);
const num = (v: number | null, suffix = "") =>
  v == null ? "—" : `${Math.round(v * 10) / 10}${suffix}`;

export function StatsView() {
  const [funnel, setFunnel] = useState<FunnelStats | null>(null);
  const [rr, setRr] = useState<ResponseRateStats | null>(null);
  const [byCv, setByCv] = useState<ByCvStats | null>(null);
  const [weekly, setWeekly] = useState<WeeklyActivityStats | null>(null);
  const [outreach, setOutreach] = useState<OutreachStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetchFunnel(),
      fetchResponseRate(),
      fetchByCv(),
      fetchWeeklyActivity(12),
      fetchOutreach(),
    ])
      .then(([f, r, c, w, o]) => {
        setFunnel(f);
        setRr(r);
        setByCv(c);
        setWeekly(w);
        setOutreach(o);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const hasData =
    (funnel?.stages.some((s) => s.count > 0) ?? false) ||
    (rr?.applied_count ?? 0) > 0 ||
    (outreach?.contacted_count ?? 0) > 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-ink">Statistiques</h1>
        <p className="text-sm text-ink-muted mt-1">
          Pilotage de la recherche — calculé localement depuis vos activités.
        </p>
      </div>

      {loading ? (
        <div className="text-center text-ink-faint py-12 text-sm">Chargement…</div>
      ) : !hasData ? (
        <Card className="text-center py-12">
          <p className="text-sm text-ink-muted">Pas encore de données à analyser.</p>
          <p className="text-xs text-ink-faint mt-1">
            Ajoutez des candidatures et des événements (timeline) pour voir apparaître le funnel,
            le taux de réponse et les tendances.
          </p>
        </Card>
      ) : (
        <>
          {/* KPI row */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Kpi label="Taux de réponse" value={pct(rr?.response_rate ?? null)} />
            <Kpi
              label="Délai de réponse moyen"
              value={num(rr?.avg_time_to_response_days ?? null, " j")}
            />
            <Kpi
              label="Candidatures"
              value={String(rr?.applied_count ?? 0)}
              hint={`${rr?.responded_count ?? 0} réponse(s)`}
            />
            <Kpi
              label="Networking"
              value={pct(outreach?.reply_rate ?? null)}
              hint={`${outreach?.replied_count ?? 0}/${outreach?.contacted_count ?? 0} réponses`}
            />
          </div>

          {/* Funnel */}
          <Card noPad>
            <CardHeader title="Pipeline de candidature" />
            <div className="p-5">
              {funnel && funnel.stages.some((s) => s.count > 0) ? (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart
                    layout="vertical"
                    data={funnel.stages}
                    margin={{ left: 20, right: 30, top: 4, bottom: 4 }}
                  >
                    <XAxis type="number" allowDecimals={false} tick={{ fontSize: 12 }} />
                    <YAxis
                      type="category"
                      dataKey="label"
                      width={140}
                      tick={{ fontSize: 12, fill: "#57534E" }}
                    />
                    <Tooltip cursor={{ fill: "#FAFAF9" }} />
                    <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                      {funnel.stages.map((_, i) => (
                        <Cell key={i} fill={FUNNEL_COLORS[i % FUNNEL_COLORS.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <Empty />
              )}
            </div>
          </Card>

          {/* Weekly activity */}
          <Card noPad>
            <CardHeader title="Activité hebdomadaire" />
            <div className="p-5">
              {weekly && weekly.weeks.length > 0 ? (
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={weekly.weeks} margin={{ left: -10, right: 10, top: 4, bottom: 4 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#E8E8E4" vertical={false} />
                    <XAxis dataKey="week" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                    <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
                    <Tooltip />
                    <Line
                      type="monotone"
                      dataKey="applied"
                      name="Candidatures"
                      stroke={BRAND}
                      strokeWidth={2}
                      dot={false}
                    />
                    <Line
                      type="monotone"
                      dataKey="relance"
                      name="Relances"
                      stroke="#EF9F27"
                      strokeWidth={2}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <Empty />
              )}
            </div>
          </Card>

          {/* By CV */}
          <Card noPad>
            <CardHeader title="Taux de réponse par CV" />
            <div className="p-5">
              {byCv && byCv.items.length > 0 ? (
                <div className="space-y-3">
                  {byCv.items.map((c) => (
                    <div key={c.document_id} className="flex items-center gap-3">
                      <div className="w-40 shrink-0 text-sm text-ink truncate" title={c.label}>
                        {c.label}
                      </div>
                      <div className="flex-1 h-6 bg-surface-100 rounded-pill overflow-hidden">
                        <div
                          className="h-full rounded-pill"
                          style={{
                            width: `${Math.round((c.response_rate ?? 0) * 100)}%`,
                            background: BRAND,
                            minWidth: c.response_rate ? "2px" : 0,
                          }}
                        />
                      </div>
                      <div className="w-28 shrink-0 text-right text-xs font-mono text-ink-muted">
                        {pct(c.response_rate)} · {c.responded_count}/{c.applied_count}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-ink-faint">
                  Aucune candidature rattachée à un CV pour l&apos;instant. Ajoutez un événement
                  « Candidature envoyée » avec le CV utilisé.
                </p>
              )}
            </div>
          </Card>
        </>
      )}
    </div>
  );
}

function Kpi({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Card>
      <div className="text-2xs font-semibold text-ink-faint uppercase tracking-wider">{label}</div>
      <div className="mt-1 font-mono text-2xl text-ink">{value}</div>
      {hint && <div className="text-2xs text-ink-faint mt-0.5">{hint}</div>}
    </Card>
  );
}

function Empty() {
  return <p className="text-xs text-ink-faint">Pas encore de données.</p>;
}
