"use client";

import { LayoutDashboard, Briefcase, Users, BookMarked, FolderOpen, Settings, Bell, Zap, BarChart3, CalendarClock } from "lucide-react";

export type Tab = "dashboard" | "offres" | "contacts" | "documents" | "stories" | "stats" | "agenda" | "reglages";

const NAV: { id: Tab; label: string; Icon: typeof LayoutDashboard }[] = [
  { id: "dashboard", label: "Dashboard", Icon: LayoutDashboard },
  { id: "offres", label: "Offres en ligne", Icon: Briefcase },
  { id: "contacts", label: "Personnes contactées", Icon: Users },
  { id: "documents", label: "Documents", Icon: FolderOpen },
  { id: "stories", label: "Stories", Icon: BookMarked },
  { id: "stats", label: "Statistiques", Icon: BarChart3 },
  { id: "agenda", label: "Agenda", Icon: CalendarClock },
  { id: "reglages", label: "Profil / Réglages", Icon: Settings },
];

export function Sidebar({
  tab,
  setTab,
  relancesDue = 0,
  onQuickAdd,
}: {
  tab: Tab;
  setTab: (t: Tab) => void;
  relancesDue?: number;
  onQuickAdd?: () => void;
}) {
  return (
    <aside className="fixed inset-y-0 left-0 w-60 bg-card border-r border-line flex flex-col z-40">
      <div className="h-16 px-5 flex items-center gap-2 border-b border-line">
        <div className="w-7 h-7 rounded-card bg-brand-400 text-white flex items-center justify-center font-display text-base">
          S
        </div>
        <div className="flex flex-col leading-tight">
          <span className="font-display text-[17px] text-ink">Stage CRM</span>
          <span className="text-2xs text-ink-faint font-mono">tracker</span>
        </div>
      </div>

      <div className="px-3 pt-4">
        <button
          onClick={onQuickAdd}
          className="w-full inline-flex items-center justify-center gap-2 px-3 py-2 bg-brand-400 text-white rounded-card text-sm font-medium hover:bg-brand-500 transition-default"
        >
          <Zap size={15} /> Ajout rapide
        </button>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-0.5">
        <div className="px-2 mb-2 text-2xs font-semibold text-ink-faint uppercase tracking-wider">
          Navigation
        </div>
        {NAV.map(({ id, label, Icon }) => {
          const active = tab === id;
          return (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-card text-sm font-medium transition-default relative ${
                active ? "bg-brand-50 text-brand-600" : "text-ink-muted hover:text-ink hover:bg-surface-100"
              }`}
            >
              {active && (
                <span className="absolute left-0 top-2 bottom-2 w-0.5 bg-brand-400 rounded-pill" aria-hidden />
              )}
              <Icon size={16} strokeWidth={1.75} className={active ? "text-brand-600" : "text-ink-faint"} />
              <span className="flex-1 text-left">{label}</span>
              {id === "dashboard" && relancesDue > 0 && (
                <span className="text-2xs font-mono px-1.5 py-0.5 rounded-pill bg-amber-100 text-amber-700">
                  {relancesDue}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      <div className="m-3 px-3 py-2.5 rounded-card border border-line flex items-center gap-2.5">
        <Bell size={14} className="text-ink-faint shrink-0" strokeWidth={1.75} />
        <div className="text-2xs text-ink-muted leading-tight">
          {relancesDue > 0 ? (
            <>
              <span className="font-semibold text-amber-700">{relancesDue}</span> relance
              {relancesDue > 1 ? "s" : ""} à faire
            </>
          ) : (
            "Aucune relance en attente"
          )}
        </div>
      </div>
    </aside>
  );
}
