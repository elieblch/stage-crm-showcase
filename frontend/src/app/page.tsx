"use client";

import { useEffect, useState } from "react";
import type { DashboardStats, User } from "@/types";
import { fetchDashboard, fetchUser, setUserId } from "@/lib/api";
import { Sidebar } from "@/components/layout/Sidebar";
import { DashboardView } from "@/components/dashboard/DashboardView";
import { RechercheView } from "@/components/search/RechercheView";
import { CandidaturesView } from "@/components/candidature/CandidaturesView";
import { SuiviView } from "@/components/suivi/SuiviView";
import { ProfilView } from "@/components/profil/ProfilView";
import { StoryBankView } from "@/components/stories/StoryBankView";

const USER_ID = "993ecd02-97da-47f5-bf56-b9adc3b82743";

type Tab = "dashboard" | "recherche" | "candidatures" | "suivi" | "stories" | "profil";

export default function App() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [tab, setTab] = useState<Tab>("dashboard");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setUserId(USER_ID);
    Promise.all([fetchDashboard(USER_ID).catch(() => null), fetchUser(USER_ID).catch(() => null)])
      .then(([s, u]) => { setStats(s); setUser(u); })
      .finally(() => setLoading(false));
  }, []);

  const refresh = () => {
    fetchDashboard(USER_ID).then(setStats).catch(() => {});
    fetchUser(USER_ID).then(setUser).catch(() => {});
  };

  if (loading) return <div className="min-h-screen flex items-center justify-center text-ink-faint text-sm">Chargement...</div>;

  const isActive = user?.is_active_search !== false;

  return (
    <div className="min-h-screen bg-bg text-ink">
      <Sidebar
        tab={tab} setTab={setTab}
        userId={USER_ID}
        userName={user?.full_name || "Utilisateur"}
        userEmail={user?.email || "user@example.com"}
        isActive={isActive}
        onStatusChange={(next) => setUser((u) => u ? { ...u, is_active_search: next } : u)}
      />
      <main className="pl-60">
        <div className="max-w-5xl mx-auto px-10 py-10">
          {tab === "dashboard" && <DashboardView stats={stats} onRefresh={refresh} isActive={isActive} onResume={() => setUser((u) => u ? { ...u, is_active_search: true } : u)} />}
          {tab === "recherche" && <RechercheView onNav={setTab} />}
          {tab === "candidatures" && <CandidaturesView />}
          {tab === "suivi" && <SuiviView onNav={setTab} />}
          {tab === "stories" && <StoryBankView />}
          {tab === "profil" && <ProfilView />}
        </div>
      </main>
    </div>
  );
}
