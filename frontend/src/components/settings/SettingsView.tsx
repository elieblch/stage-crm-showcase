"use client";

import { useEffect, useState } from "react";
import { Check } from "lucide-react";

import { fetchSettings, updateSettings } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/shared";

export function SettingsView() {
  const [delay, setDelay] = useState<number>(10);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    fetchSettings()
      .then((s) => setDelay(s.relance_delay_days))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const save = async () => {
    setSaving(true);
    setSaved(false);
    try {
      const s = await updateSettings({ relance_delay_days: delay });
      setDelay(s.relance_delay_days);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="font-display text-ink">Profil / Réglages</h1>
        <p className="text-sm text-ink-muted mt-1">Paramètres du tracker</p>
      </div>

      <Card noPad>
        <CardHeader title="Relances" />
        <div className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-ink mb-1.5">Délai de relance par défaut</label>
            <p className="text-xs text-ink-muted mb-3">
              Nombre de jours après la dernière action sans réponse avant qu&apos;une relance soit suggérée. Une date de
              relance fixée manuellement sur une offre ou un contact a toujours la priorité sur ce délai.
            </p>
            <div className="flex items-center gap-2">
              <input
                type="number"
                min={0}
                value={loading ? "" : delay}
                onChange={(e) => setDelay(Math.max(0, Number(e.target.value)))}
                className="w-24 px-3 py-2 border border-line rounded-input text-sm text-ink bg-card font-mono"
              />
              <span className="text-sm text-ink-muted">jours</span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={save}
              disabled={saving || loading}
              className="px-4 py-2 bg-brand-400 text-white rounded-input text-sm font-medium hover:bg-brand-500 disabled:opacity-50"
            >
              {saving ? "Enregistrement…" : "Enregistrer"}
            </button>
            {saved && (
              <span className="inline-flex items-center gap-1 text-xs text-brand-600">
                <Check size={14} /> Enregistré
              </span>
            )}
          </div>
        </div>
      </Card>
    </div>
  );
}
