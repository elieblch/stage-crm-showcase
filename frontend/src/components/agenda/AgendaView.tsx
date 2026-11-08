"use client";

import { useEffect, useState } from "react";
import {
  AlertCircle,
  CalendarCheck,
  Download,
  Flag,
  RefreshCw,
  type LucideIcon,
} from "lucide-react";

import type { AgendaItem, AgendaKind } from "@/types";
import { agendaIcsUrl, fetchAgenda } from "@/lib/api";
import type { Tab } from "@/components/layout/Sidebar";
import { Card } from "@/components/ui/shared";

const KIND_META: Record<AgendaKind, { label: string; Icon: LucideIcon; pill: string; dot: string }> = {
  relance: { label: "Relance", Icon: RefreshCw, pill: "bg-amber-50 text-amber-700", dot: "#EF9F27" },
  deadline: { label: "Deadline", Icon: Flag, pill: "bg-red-50 text-red-600", dot: "#E24B4A" },
  interview: { label: "Entretien", Icon: CalendarCheck, pill: "bg-violet-50 text-violet-600", dot: "#7F77DD" },
};

const WINDOWS = [7, 30, 90];

const todayIso = () => new Date().toISOString().slice(0, 10);

function headerLabel(iso: string): string {
  const today = todayIso();
  const tomorrow = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
  const base = new Date(iso).toLocaleDateString("fr-FR", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
  if (iso === today) return `${base} · Aujourd'hui`;
  if (iso === tomorrow) return `${base} · Demain`;
  if (iso < today) return `${base} · En retard`;
  return base;
}

export function AgendaView({ onNav }: { onNav: (t: Tab) => void }) {
  const [days, setDays] = useState(30);
  const [items, setItems] = useState<AgendaItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchAgenda(days)
      .then((r) => setItems(r.items))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, [days]);

  // Groupement par jour (items déjà triés par date croissante côté backend).
  const groups: { date: string; items: AgendaItem[] }[] = [];
  for (const it of items) {
    const last = groups[groups.length - 1];
    if (last && last.date === it.date) last.items.push(it);
    else groups.push({ date: it.date, items: [it] });
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="font-display text-ink">Agenda</h1>
          <p className="text-sm text-ink-muted mt-1">
            Relances, deadlines et entretiens à venir.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex border border-line rounded-input overflow-hidden">
            {WINDOWS.map((w) => (
              <button
                key={w}
                onClick={() => setDays(w)}
                className={`px-3 py-1.5 text-sm ${
                  days === w ? "bg-surface-100 text-ink font-medium" : "text-ink-faint hover:text-ink"
                }`}
              >
                {w} j
              </button>
            ))}
          </div>
          <a
            href={agendaIcsUrl(days)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-ink text-white rounded-input text-sm font-medium hover:bg-ink/90 transition-default"
          >
            <Download size={15} /> Exporter .ics
          </a>
        </div>
      </div>

      {loading ? (
        <div className="text-center text-ink-faint py-12 text-sm">Chargement…</div>
      ) : groups.length === 0 ? (
        <Card className="text-center py-12">
          <p className="text-sm text-ink-muted">Aucune échéance sur cette période.</p>
          <p className="text-xs text-ink-faint mt-1">
            Élargissez la fenêtre ou planifiez des relances et entretiens.
          </p>
        </Card>
      ) : (
        <div className="space-y-5">
          {groups.map((g) => (
            <div key={g.date}>
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs font-semibold text-ink uppercase tracking-wide first-letter:uppercase">
                  {headerLabel(g.date)}
                </span>
                <span className="text-2xs font-mono text-ink-faint">
                  {new Date(g.date).toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit" })}
                </span>
                <div className="flex-1 h-px bg-line" />
              </div>
              <div className="space-y-2">
                {g.items.map((it) => {
                  const meta = KIND_META[it.kind];
                  const Icon = meta.Icon;
                  return (
                    <Card
                      key={`${it.kind}-${it.entity_type}-${it.entity_id}-${it.date}`}
                      noPad
                      className="card-hover cursor-pointer"
                    >
                      <button
                        onClick={() => onNav(it.entity_type === "offer" ? "offres" : "contacts")}
                        className="w-full text-left px-5 py-3 flex items-center gap-3"
                      >
                        <span
                          className="w-2 h-2 rounded-full shrink-0"
                          style={{ background: meta.dot }}
                          aria-hidden
                        />
                        <Icon size={16} className="text-ink-faint shrink-0" strokeWidth={1.75} />
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium text-ink truncate">{it.label}</div>
                          {(it.company || it.status) && (
                            <div className="text-2xs text-ink-faint mt-0.5">
                              {[it.company, it.status].filter(Boolean).join(" · ")}
                            </div>
                          )}
                        </div>
                        <span className={`text-2xs px-2 py-0.5 rounded-pill font-medium shrink-0 ${meta.pill}`}>
                          {meta.label}
                        </span>
                        {it.overdue && (
                          <span className="inline-flex items-center gap-1 text-2xs px-2 py-0.5 rounded-pill bg-red-50 text-red-600 font-medium shrink-0">
                            <AlertCircle size={11} /> En retard
                          </span>
                        )}
                      </button>
                    </Card>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
