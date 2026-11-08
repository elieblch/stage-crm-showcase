"use client";

import { useState } from "react";
import { LayoutDashboard, Search, Kanban, ListChecks, BookMarked, UserCircle2, Pause, Play } from "lucide-react";
import { updateSearchStatus } from "@/lib/api";

type Tab = "dashboard" | "recherche" | "candidatures" | "suivi" | "stories" | "profil";

const NAV: { id: Tab; label: string; Icon: typeof LayoutDashboard }[] = [
  { id: "dashboard", label: "Dashboard", Icon: LayoutDashboard },
  { id: "recherche", label: "Recherche", Icon: Search },
  { id: "candidatures", label: "Candidatures", Icon: Kanban },
  { id: "suivi", label: "Suivi", Icon: ListChecks },
  { id: "stories", label: "Stories", Icon: BookMarked },
];

export function Sidebar({
  tab, setTab,
  userId, userName = "Utilisateur", userEmail = "user@example.com",
  isActive = true, onStatusChange,
}: {
  tab: Tab;
  setTab: (t: Tab) => void;
  userId: string;
  userName?: string;
  userEmail?: string;
  isActive?: boolean;
  onStatusChange?: (next: boolean) => void;
}) {
  const [toggling, setToggling] = useState(false);
  const initials = userName.slice(0, 1).toUpperCase();

  const toggleStatus = async () => {
    if (toggling) return;
    const next = !isActive;
    const confirmMsg = next
      ? "Reprendre la recherche ? Un scan + scoring complet va être lancé immédiatement."
      : "Mettre la recherche en pause ? Scans, newsletter et notifications seront suspendus.";
    if (!confirm(confirmMsg)) return;
    setToggling(true);
    try {
      await updateSearchStatus(userId, next);
      onStatusChange?.(next);
    } catch {
      alert("Erreur lors du changement de statut.");
    }
    setToggling(false);
  };

  return (
    <aside className="fixed inset-y-0 left-0 w-60 bg-card border-r border-line flex flex-col z-40">
      <div className="h-16 px-5 flex items-center gap-2 border-b border-line">
        <div className="w-7 h-7 rounded-card bg-brand-400 text-white flex items-center justify-center font-display text-base">S</div>
        <div className="flex flex-col leading-tight">
          <span className="font-display text-[17px] text-ink">Stage CRM</span>
          <span className="text-2xs text-ink-faint font-mono">beta</span>
        </div>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-0.5">
        <div className="px-2 mb-2 text-2xs font-semibold text-ink-faint uppercase tracking-wider">Navigation</div>
        {NAV.map(({ id, label, Icon }) => {
          const active = tab === id;
          return (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-card text-sm font-medium transition-default relative ${
                active
                  ? "bg-brand-50 text-brand-600"
                  : "text-ink-muted hover:text-ink hover:bg-surface-100"
              }`}
            >
              {active && <span className="absolute left-0 top-2 bottom-2 w-0.5 bg-brand-400 rounded-pill" aria-hidden />}
              <Icon size={16} strokeWidth={1.75} className={active ? "text-brand-600" : "text-ink-faint"} />
              <span>{label}</span>
            </button>
          );
        })}
      </nav>

      {/* Statut recherche */}
      <button
        onClick={toggleStatus}
        disabled={toggling}
        className="mx-3 mb-2 px-3 py-2 rounded-card flex items-center gap-2.5 border border-line hover:border-ink-faint transition-default text-left disabled:opacity-60"
        title={isActive ? "Mettre en pause" : "Reprendre la recherche"}
      >
        <span className={`w-1.5 h-1.5 rounded-full ${isActive ? "bg-success-600" : "bg-ink-faint"}`} />
        <div className="flex-1 min-w-0">
          <div className="text-xs font-medium text-ink">{isActive ? "Recherche active" : "En pause"}</div>
          <div className="text-2xs text-ink-faint">{isActive ? "Scans quotidiens activés" : "Scans suspendus"}</div>
        </div>
        {isActive ? <Pause size={12} className="text-ink-faint" strokeWidth={1.75} /> : <Play size={12} className="text-ink-faint" strokeWidth={1.75} />}
      </button>

      {/* User */}
      <button
        onClick={() => setTab("profil")}
        className={`m-3 mt-1 px-3 py-2.5 rounded-card flex items-center gap-3 transition-default ${
          tab === "profil" ? "bg-brand-50 ring-1 ring-brand-200" : "hover:bg-surface-100"
        }`}
      >
        <div className="w-8 h-8 rounded-full bg-ink text-white flex items-center justify-center text-xs font-semibold">{initials}</div>
        <div className="flex-1 min-w-0 text-left">
          <div className="text-sm font-medium text-ink truncate">{userName}</div>
          <div className="text-2xs text-ink-muted truncate font-mono">{userEmail}</div>
        </div>
        <UserCircle2 size={14} className="text-ink-faint shrink-0" strokeWidth={1.5} />
      </button>
    </aside>
  );
}
