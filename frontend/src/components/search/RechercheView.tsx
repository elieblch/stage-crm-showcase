"use client";

import { useEffect, useMemo, useState } from "react";
import { fetchMatches, createApplication } from "@/lib/api";
import type { OfferMatch } from "@/types";
import { Card, PLAT, cleanHtml, scoreBadge, InterestBtn, ScoreDetail, Chevron, resolveUserId } from "@/components/ui/shared";
import { ScoreRadarChart } from "@/components/search/ScoreRadarChart";

function extractCities(raw: string | null | undefined): string[] {
  if (!raw) return [];
  const parts = raw.split(/[,/]|(?:\s+or\s+)|(?:\s+and\s+)/i).map((s) => s.trim()).filter(Boolean);
  return parts.map((p) =>
    p.replace(/\b[A-Z]{2,3}$/, "").replace(/\b\d{5}\b/, "").replace(/,?\s*(France|Germany|Netherlands|Poland|Denmark|Australia|China|United States|UK|Switzerland|IDF)$/i, "").trim()
  ).filter((p) => p.length > 1);
}

function FilterSelect({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options: { v: string; l: string }[] }) {
  return (
    <div>
      <label className="block text-2xs font-medium text-ink-muted mb-1.5">{label}</label>
      <select value={value} onChange={(e) => onChange(e.target.value)} className="px-3 py-1.5 border border-line rounded-input text-sm bg-card text-ink pr-8 hover:border-ink-faint transition-default">
        {options.map((o) => <option key={o.v} value={o.v}>{o.l}</option>)}
      </select>
    </div>
  );
}

function OfferRow({ m, onApply, onInterest }: { m: OfferMatch; onApply: (id: string) => void; onInterest: (id: string, v: string) => void }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const o = m.offer;
  const hasMultidim = !!(m.match_reasons?.dimensions && typeof m.match_reasons.dimensions === "object");

  return (
    <div className="bg-card border border-line rounded-card card-hover overflow-hidden">
      <div className="px-5 py-3.5 cursor-pointer" onClick={() => setOpen(!open)}>
        <div className="flex items-center gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-sm font-semibold text-ink truncate">{o.title}</span>
              <span className={`font-mono px-2 py-0.5 rounded-pill text-2xs font-semibold shrink-0 ${scoreBadge(m.match_score)}`}>{m.match_score}</span>
              <ScoreDetail reasons={m.match_reasons} />
            </div>
            <div className="flex items-center gap-2 text-xs text-ink-muted flex-wrap">
              <span className="font-medium text-ink">{o.company_name}</span>
              {o.location && <><span className="text-ink-placeholder">·</span><span>{o.location}</span></>}
              {o.domain && <><span className="text-ink-placeholder">·</span><span>{o.domain}</span></>}
              {o.duration_months && <><span className="text-ink-placeholder">·</span><span>{o.duration_months} mois</span></>}
              {o.salary && <><span className="text-ink-placeholder">·</span><span>{o.salary}</span></>}
              <span className="ml-1 px-1.5 py-0.5 bg-surface-100 rounded text-2xs text-ink-faint font-mono">{PLAT[o.source_platform] || o.source_platform}</span>
            </div>
          </div>
          <InterestBtn id={m.id} v={m.user_interest} onChange={(v) => onInterest(m.id, v)} />
          <Chevron open={open} />
        </div>
      </div>
      {open && (
        <div className="px-5 pb-5 pt-3 border-t border-line-subtle bg-surface-100/40 transition-expand">
          {hasMultidim && (
            <div className="mb-4">
              <div className="text-2xs font-medium text-ink-muted uppercase tracking-wider mb-1">Score par dimension</div>
              <ScoreRadarChart reasons={m.match_reasons} />
            </div>
          )}
          {m.ai_summary && <p className="text-sm text-ink-muted italic mb-3">{cleanHtml(m.ai_summary)}</p>}
          {o.description && <p className="text-sm text-ink-muted leading-relaxed mb-3 line-clamp-6">{cleanHtml(o.description)}</p>}
          {o.required_skills?.length > 0 && <div className="flex flex-wrap gap-1.5 mb-4">{o.required_skills.map((s, i) => <span key={i} className="text-2xs px-2 py-0.5 bg-info-50 text-info-700 rounded-pill">{s}</span>)}</div>}
          <div className="flex gap-2">
            {o.source_url && <a href={o.source_url} target="_blank" rel="noopener noreferrer" className="px-3 py-1.5 text-sm font-medium border border-line rounded-input hover:border-ink-faint transition-default">Voir l&apos;offre</a>}
            <button onClick={(e) => { e.stopPropagation(); setBusy(true); onApply(o.id); }} disabled={busy} className="px-3 py-1.5 text-sm font-medium bg-ink text-white rounded-input hover:bg-ink/90 disabled:opacity-50">{busy ? "…" : "Candidater"}</button>
          </div>
        </div>
      )}
    </div>
  );
}

export function RechercheView({ onNav }: { onNav: (t: "candidatures") => void }) {
  const userId = resolveUserId();
  const [matches, setMatches] = useState<OfferMatch[]>([]);
  const [loading, setLoading] = useState(true);
  const [minScore, setMinScore] = useState(40);
  const [showAll, setShowAll] = useState(false);
  const [domain, setDomain] = useState("all");
  const [platform, setPlatform] = useState("all");
  const [loc, setLoc] = useState("all");
  const [dur, setDur] = useState("all");

  useEffect(() => { fetchMatches(userId, { limit: 200, min_score: 0 }).then(setMatches).catch(() => {}).finally(() => setLoading(false)); }, [userId]);

  const domains = useMemo(() => [...new Set(matches.map((m) => m.offer.domain).filter(Boolean))], [matches]);
  const platforms = useMemo(() => [...new Set(matches.map((m) => m.offer.source_platform))], [matches]);

  const cityOptions = useMemo(() => {
    const counts: Record<string, number> = {};
    matches.forEach((m) => {
      const cities = extractCities(m.offer.location);
      if (cities.length === 0) counts["Non precisee"] = (counts["Non precisee"] || 0) + 1;
      else cities.forEach((c) => { counts[c] = (counts[c] || 0) + 1; });
    });
    return Object.entries(counts).sort((a, b) => b[1] - a[1]).map(([city, count]) => ({ v: city, l: `${city} (${count})` }));
  }, [matches]);

  const maskedByScore = useMemo(() => matches.filter((m) => m.match_score < minScore).length, [matches, minScore]);

  const filtered = useMemo(() => {
    return matches
      .filter((m) => showAll || m.match_score >= minScore)
      .filter((m) => domain === "all" || m.offer.domain === domain)
      .filter((m) => platform === "all" || m.offer.source_platform === platform)
      .filter((m) => {
        if (loc === "all") return true;
        if (loc === "Non precisee") return !m.offer.location;
        const cities = extractCities(m.offer.location);
        return cities.some((c) => c.toLowerCase() === loc.toLowerCase());
      })
      .filter((m) => {
        if (dur === "all") return true;
        const d = m.offer.duration_months;
        if (!d) return dur === "unknown";
        if (dur === "1-3") return d >= 1 && d <= 3;
        if (dur === "3-6") return d > 3 && d <= 6;
        if (dur === "6+") return d > 6;
        return true;
      })
      .sort((a, b) => b.match_score - a.match_score);
  }, [matches, minScore, showAll, domain, platform, loc, dur]);

  const apply = async (oid: string) => { try { await createApplication(userId, oid); onNav("candidatures"); } catch { alert("Candidature deja existante ou erreur."); } };
  const onInterest = (id: string, v: string) => setMatches((p) => p.map((m) => m.id === id ? { ...m, user_interest: v as OfferMatch["user_interest"] } : m));

  if (loading) return <div className="text-center text-gray-400 py-12">Chargement...</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="font-display text-ink">Offres correspondantes</h1>
          <p className="text-sm text-ink-muted mt-1">
            <span className="font-mono">{filtered.length}</span> affichées sur <span className="font-mono">{matches.length}</span>
          </p>
        </div>
      </div>

      {/* Bandeau IA intégré — pas d'alert box, juste une ligne discrète */}
      {maskedByScore > 0 && !showAll && (
        <div className="flex items-center gap-3 text-xs text-ink-muted border-b border-line pb-3">
          <span className="inline-flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-brand-400" />
            <span className="text-ink">Classement enrichi par IA</span>
          </span>
          <span className="text-ink-faint">·</span>
          <span>
            <span className="font-mono">{maskedByScore}</span> offre{maskedByScore > 1 ? "s" : ""} masquée{maskedByScore > 1 ? "s" : ""} (score &lt; <span className="font-mono">{minScore}</span>)
          </span>
          <button onClick={() => setShowAll(true)} className="ml-auto text-brand-600 hover:text-brand-700 font-medium">
            Afficher tout
          </button>
        </div>
      )}
      {showAll && (
        <div className="flex items-center gap-3 text-xs text-ink-muted border-b border-line pb-3">
          <span className="inline-flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-ink-faint" />
            Filtre IA désactivé
          </span>
          <button onClick={() => setShowAll(false)} className="ml-auto text-brand-600 hover:text-brand-700 font-medium">
            Réactiver le filtre
          </button>
        </div>
      )}

      {/* Filtres */}
      <div className="flex flex-wrap items-end gap-4 pb-2">
        <div className="w-48">
          <label className="block text-2xs font-medium text-ink-muted mb-1.5">Score min · <span className="font-mono text-ink">{minScore}</span></label>
          <input type="range" min={0} max={100} step={5} value={minScore} onChange={(e) => setMinScore(+e.target.value)} className="w-full accent-brand-400" />
        </div>
        <FilterSelect label="Domaine" value={domain} onChange={setDomain} options={[{ v: "all", l: "Tous" }, ...domains.map((d) => ({ v: d!, l: d! }))]} />
        <FilterSelect label="Plateforme" value={platform} onChange={setPlatform} options={[{ v: "all", l: "Toutes" }, ...platforms.map((p) => ({ v: p, l: PLAT[p] || p }))]} />
        <FilterSelect label="Localisation" value={loc} onChange={setLoc} options={[{ v: "all", l: "Toutes" }, ...cityOptions]} />
        <FilterSelect label="Durée" value={dur} onChange={setDur} options={[{ v: "all", l: "Toutes" }, { v: "1-3", l: "1-3 mois" }, { v: "3-6", l: "3-6 mois" }, { v: "6+", l: "6+ mois" }, { v: "unknown", l: "Non précisée" }]} />
      </div>

      {filtered.length === 0 ? (
        <Card className="text-center py-12 text-ink-faint">Aucune offre avec ces filtres.</Card>
      ) : (
        <div className="space-y-2">
          {filtered.map((m) => <OfferRow key={m.id} m={m} onApply={apply} onInterest={onInterest} />)}
        </div>
      )}
    </div>
  );
}
