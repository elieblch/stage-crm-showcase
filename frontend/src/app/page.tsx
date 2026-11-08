"use client";

import { useCallback, useEffect, useState } from "react";

import { Sidebar, type Tab } from "@/components/layout/Sidebar";
import { DashboardView } from "@/components/dashboard/DashboardView";
import { OffersView } from "@/components/offers/OffersView";
import { ContactsView } from "@/components/contacts/ContactsView";
import { DocumentsView } from "@/components/documents/DocumentsView";
import { StoryBankView } from "@/components/stories/StoryBankView";
import { StatsView } from "@/components/stats/StatsView";
import { AgendaView } from "@/components/agenda/AgendaView";
import { SettingsView } from "@/components/settings/SettingsView";
import { QuickAddModal } from "@/components/ui/QuickAddModal";
import { fetchDashboard } from "@/lib/api";
import type { ContactInput, OfferInput } from "@/types";

export default function App() {
  const [tab, setTab] = useState<Tab>("dashboard");
  const [relancesDue, setRelancesDue] = useState(0);
  const [quickOpen, setQuickOpen] = useState(false);

  const [offerPrefill, setOfferPrefill] = useState<{ fields: OfferInput; warnings: string[] } | null>(null);
  const [contactPrefill, setContactPrefill] = useState<{ fields: ContactInput; warnings: string[] } | null>(null);

  const refreshBadge = useCallback(() => {
    fetchDashboard()
      .then((d) => setRelancesDue(d.relances_due))
      .catch(() => {});
  }, []);

  useEffect(() => {
    refreshBadge();
  }, [refreshBadge]);

  const onQuickApply = (
    kind: "offer" | "contact",
    fields: OfferInput | ContactInput,
    warnings: string[]
  ) => {
    setQuickOpen(false);
    if (kind === "offer") {
      setOfferPrefill({ fields: fields as OfferInput, warnings });
      setTab("offres");
    } else {
      setContactPrefill({ fields: fields as ContactInput, warnings });
      setTab("contacts");
    }
  };

  return (
    <div className="min-h-screen bg-bg text-ink">
      <Sidebar tab={tab} setTab={setTab} relancesDue={relancesDue} onQuickAdd={() => setQuickOpen(true)} />
      <main className="pl-60">
        <div className="max-w-5xl mx-auto px-10 py-10">
          {tab === "dashboard" && <DashboardView onNav={setTab} onChange={refreshBadge} />}
          {tab === "offres" && (
            <OffersView
              onChange={refreshBadge}
              quickPrefill={offerPrefill?.fields ?? null}
              quickWarnings={offerPrefill?.warnings}
              onQuickConsumed={() => setOfferPrefill(null)}
              onNavStories={() => setTab("stories")}
            />
          )}
          {tab === "contacts" && (
            <ContactsView
              onChange={refreshBadge}
              quickPrefill={contactPrefill?.fields ?? null}
              quickWarnings={contactPrefill?.warnings}
              onQuickConsumed={() => setContactPrefill(null)}
            />
          )}
          {tab === "documents" && <DocumentsView />}
          {tab === "stories" && <StoryBankView />}
          {tab === "stats" && <StatsView />}
          {tab === "agenda" && <AgendaView onNav={setTab} />}
          {tab === "reglages" && <SettingsView />}
        </div>
      </main>

      {quickOpen && <QuickAddModal onClose={() => setQuickOpen(false)} onApply={onQuickApply} />}
    </div>
  );
}
