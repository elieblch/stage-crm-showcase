"use client";

import { useEffect, useState } from "react";
import { fetchMatches, fetchOfferStats, fetchAlerts, triggerScraping, scoreOffers, sendNewsletterNow, updateSearchStatus } from "@/lib/api";
import type { DashboardStats, OfferMatch } from "@/types";
import { Card, CardHeader, PLAT, InterestBtn, ScoreDetail, scoreBadge, resolveUserId } from "@/components/ui/shared";

function MiniMatch({ m }: { m: OfferMatch }) {
  const o = m.offer;
  return (
    <div className="px-5 py-3.5 flex items-center justify-between gap-4 hover:bg-surface-100 transition-default">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <a href={o.source_url || "#"} target="_blank" rel="noopener noreferrer" className="text-sm font-medium text-ink hover:text-brand-600 truncate transition-default">{o.title}</a>
          <span className={`font-mono px-2 py-0.5 rounded-pill text-2xs font-semibold shrink-0 ${scoreBadge(m.match_score)}`}>{m.match_score}</span>
          <ScoreDetail reasons={m.match_reasons} />
        </div>
        <div className="text-xs text-ink-muted mt-0.5">{o.company_name}{o.location ? ` \u00B7 ${o.location}` : ""} <span className="text-ink-faint ml-1 font-mono">{PLAT[o.source_platform] || o.source_platform}</span></div>
      </div>
      <InterestBtn id={m.id} v={m.user_interest} />
    </div>
  );
}

export function DashboardView({ stats, onRefresh, isActive = true, onResume }: { stats: DashboardStats | null; onRefresh: () => void; isActive?: boolean; onResume?: () => void }) {
  const userId = resolveUserId();
  const [scraping, setScraping] = useState(false);
  const [sendingNewsletter, setSendingNewsletter] = useState(false);
  const [newsletterMsg, setNewsletterMsg] = useState<string | null>(null);
  const [recent, setRecent] = useState<OfferMatch[]>([]);
  const [weekly, setWeekly] = useState<OfferMatch[]>([]);
  const [platCounts, setPlatCounts] = useState<Record<string, number>>({});
  const [alerts, setAlerts] = useState<{ type: string; service: string; message: string; severity: string }[]>([]);

  useEffect(() => {
    fetchMatches(userId, { limit: 5, min_score: 60 }).then(setRecent).catch(() => {});
    fetchMatches(userId, { limit: 200, min_score: 0 }).then((all) => {
      const week = Date.now() - 7 * 86400000;
      setWeekly(all.filter((m: OfferMatch) => new Date(m.created_at).getTime() >= week).sort((a: OfferMatch, b: OfferMatch) => b.match_score - a.match_score).slice(0, 10));
    }).catch(() => {});
    fetchOfferStats().then(setPlatCounts).catch(() => {});
    fetchAlerts(userId).then(setAlerts).catch(() => {});
  }, [userId]);

  const handleScan = async () => {
    setScraping(true);
    try {
      await triggerScraping();
      setTimeout(async () => {
        try {
          await scoreOffers(userId);
          onRefresh();
          const m = await fetchMatches(userId, { limit: 5, min_score: 60 });
          setRecent(m);
          fetchOfferStats().then(setPlatCounts).catch(() => {});
        } catch {}
        setScraping(false);
      }, 5000);
    } catch { setScraping(false); }
  };

  const kpis = [
    { label: "Offres matchées", value: stats?.total_offers_matched ?? 0 },
    { label: "Nouvelles cette semaine", value: weekly.length },
    { label: "Candidatures", value: stats?.applications_sent ?? 0 },
    { label: "Entretiens", value: stats?.interviews_scheduled ?? 0 },
  ];

  return (
    <div className="space-y-10">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="font-display text-ink">Bonjour</h1>
          <p className="text-sm text-ink-muted mt-1">Voici l&apos;état de votre recherche de stage.</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={async () => {
              setSendingNewsletter(true); setNewsletterMsg(null);
              try {
                const r = await sendNewsletterNow(userId);
                const status = r?.status || r?.results?.[0]?.status || "?";
                const offers = r?.offers ?? r?.results?.[0]?.offers ?? 0;
                if (status === "sent") setNewsletterMsg(`✓ Envoyée (${offers} offres)`);
                else if (status === "logged") setNewsletterMsg(`Mode test · ${offers} offres (voir logs)`);
                else if (status === "empty") setNewsletterMsg("Aucune nouvelle offre à envoyer");
                else setNewsletterMsg(`Erreur : ${r?.message || status}`);
              } catch { setNewsletterMsg("Erreur d'envoi"); }
              setSendingNewsletter(false);
              setTimeout(() => setNewsletterMsg(null), 6000);
            }}
            disabled={sendingNewsletter}
            className="px-4 py-2 border border-line bg-card text-ink rounded-input text-sm font-medium hover:border-ink-faint disabled:opacity-50"
            title="Envoyer la newsletter maintenant"
          >
            {sendingNewsletter ? "Envoi…" : "Envoyer la newsletter"}
          </button>
          <button
            onClick={handleScan}
            disabled={scraping}
            className="px-4 py-2 bg-ink text-white rounded-input text-sm font-medium hover:bg-ink/90 disabled:opacity-50"
          >
            {scraping ? "Scan en cours…" : "Lancer un scan"}
          </button>
        </div>
      </div>
      {newsletterMsg && (
        <div className="text-xs text-ink-muted -mt-6">{newsletterMsg}</div>
      )}

      {!isActive && (
        <div className="rounded-card border border-line bg-surface-100 px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2.5 text-sm">
            <span className="w-2 h-2 rounded-full bg-ink-faint" />
            <span className="text-ink font-medium">Recherche en pause</span>
            <span className="text-ink-muted">— scans quotidiens, newsletter et notifications désactivés.</span>
          </div>
          <button
            onClick={async () => {
              try {
                await updateSearchStatus(userId, true);
                onResume?.();
                onRefresh();
              } catch { alert("Erreur lors de la reprise."); }
            }}
            className="px-3 py-1.5 bg-ink text-white rounded-input text-xs font-medium hover:bg-ink/90"
          >
            Reprendre
          </button>
        </div>
      )}

      {/* KPIs — cartes compactes muted */}
      <div className="grid grid-cols-4 gap-3">
        {kpis.map((k) => (
          <div key={k.label} className="bg-surface-100 rounded-card px-4 py-4">
            <div className="text-[26px] font-display text-ink leading-none">{k.value}</div>
            <div className="text-xs text-ink-muted mt-2">{k.label}</div>
          </div>
        ))}
      </div>

      {alerts.length > 0 && (
        <div className="space-y-2">
          {alerts.map((a, i) => (
            <div key={i} className={`px-4 py-3 rounded-card text-sm flex items-center gap-3 border ${a.severity === "warning" ? "bg-warn-50 text-warn-700 border-warn-600/20" : "bg-info-50 text-info-700 border-info-600/20"}`}>
              <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${a.severity === "warning" ? "bg-warn-600" : "bg-info-600"}`} />
              {a.message}
            </div>
          ))}
        </div>
      )}

      {/* Sources */}
      <section>
        <h2 className="font-display text-ink mb-3">Sources de données</h2>
        <div className="grid grid-cols-6 gap-2.5">
          {(["welcome_to_the_jungle", "greenhouse", "smartrecruiters", "workday", "efinancialcareers", "jobteaser"] as const).map((p) => (
            <div key={p} className="bg-card border border-line rounded-card px-3 py-3">
              <div className="text-xs font-medium text-ink-muted truncate">{PLAT[p]}</div>
              <div className="text-xl font-display text-ink mt-1 leading-none">{platCounts[p] || 0}</div>
              <div className="text-2xs text-ink-faint font-mono mt-1">offres</div>
            </div>
          ))}
        </div>
      </section>

      {/* Top matches */}
      <Card noPad>
        <CardHeader title="Meilleures offres pour vous" />
        {recent.length === 0 ? <div className="px-5 py-10 text-center text-sm text-ink-faint">Aucune offre matchée. Lancez un scan.</div> : (
          <div className="divide-y divide-line-subtle">{recent.map((m) => <MiniMatch key={m.id} m={m} />)}</div>
        )}
      </Card>

      {weekly.length > 0 && (
        <Card noPad>
          <CardHeader title="Offres reçues cette semaine" right={<span className="text-2xs text-ink-faint font-mono">{weekly.length} offres</span>} />
          <div className="divide-y divide-line-subtle">{weekly.map((m) => <MiniMatch key={m.id} m={m} />)}</div>
        </Card>
      )}
    </div>
  );
}
