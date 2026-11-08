"use client";

import { useState } from "react";
import { sendNewsletterNow } from "@/lib/api";
import { Card, CardHeader, resolveUserId } from "@/components/ui/shared";

export function NewsletterSection({
  enabled, time, minScore, recipient,
  onChange,
}: {
  enabled: boolean;
  time: string;
  minScore: number;
  recipient: string;
  onChange: (v: { enabled?: boolean; time?: string; minScore?: number; recipient?: string }) => void;
}) {
  const userId = resolveUserId();
  const [sending, setSending] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const sendTest = async () => {
    setSending(true); setMsg(null);
    try {
      const r = await sendNewsletterNow(userId);
      const status = r?.status || r?.results?.[0]?.status || "?";
      const offers = r?.offers ?? r?.results?.[0]?.offers ?? 0;
      if (status === "sent") setMsg(`✓ Envoyée à ${recipient} (${offers} offres)`);
      else if (status === "logged") setMsg(`Mode test · HTML dans les logs (${offers} offres)`);
      else if (status === "empty") setMsg("Aucune offre à envoyer pour le moment");
      else setMsg(`Erreur : ${r?.message || status}`);
    } catch { setMsg("Erreur d'envoi"); }
    setSending(false);
  };

  return (
    <Card noPad>
      <CardHeader
        title="Newsletter"
        right={
          <label className="inline-flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={enabled} onChange={(e) => onChange({ enabled: e.target.checked })} className="sr-only peer" />
            <div className="w-9 h-5 bg-surface-100 rounded-pill peer-checked:bg-brand-400 relative transition-default">
              <div className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${enabled ? "translate-x-4" : ""}`} />
            </div>
            <span className="text-xs font-medium text-ink">{enabled ? "Activée" : "Désactivée"}</span>
          </label>
        }
      />
      <div className="p-6 space-y-5">
        <p className="text-sm text-ink-muted">
          Chaque matin à l&apos;heure choisie, vous recevez par email les nouvelles offres matchées des dernières 24h.
        </p>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-ink-muted mb-1.5">Heure d&apos;envoi</label>
            <input
              type="time" value={time?.slice(0, 5) || "08:00"}
              onChange={(e) => onChange({ time: `${e.target.value}:00` })}
              className="w-full px-3 py-2 border border-line rounded-input text-sm text-ink bg-card"
              disabled={!enabled}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-ink-muted mb-1.5">Destinataire</label>
            <input
              type="email" value={recipient}
              onChange={(e) => onChange({ recipient: e.target.value })}
              placeholder="vous@exemple.com"
              className="w-full px-3 py-2 border border-line rounded-input text-sm text-ink bg-card"
              disabled={!enabled}
            />
          </div>
        </div>

        <div>
          <label className="block text-xs font-medium text-ink-muted mb-1.5">
            Score minimum pour inclusion · <span className="font-mono text-ink">{minScore}</span>
          </label>
          <input
            type="range" min={0} max={100} step={5} value={minScore}
            onChange={(e) => onChange({ minScore: +e.target.value })}
            className="w-full accent-brand-400"
            disabled={!enabled}
          />
          <p className="text-2xs text-ink-faint mt-1">Les offres avec un score &lt; {minScore} ne seront pas incluses dans la newsletter.</p>
        </div>

        <div className="flex items-center gap-3 pt-2 border-t border-line-subtle">
          <button
            onClick={sendTest}
            disabled={sending || !enabled}
            className="px-4 py-1.5 border border-line bg-card text-ink text-sm font-medium rounded-input hover:border-ink-faint disabled:opacity-50"
          >
            {sending ? "Envoi…" : "Envoyer un test"}
          </button>
          {msg && <span className="text-xs text-ink-muted">{msg}</span>}
        </div>
      </div>
    </Card>
  );
}
