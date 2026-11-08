"use client";

import { useEffect, useState } from "react";
import { saveJobTeaserCookie, testJobTeaserCookie, jobTeaserStatus, disconnectJobTeaser } from "@/lib/api";
import { Card, CardHeader, resolveUserId } from "@/components/ui/shared";

export function JobTeaserSection() {
  const userId = resolveUserId();
  const [status, setStatus] = useState<{ connected: boolean; expires_at?: string } | null>(null);
  const [cookie, setCookie] = useState("");
  const [jtUrl, setJtUrl] = useState("https://em-lyon.jobteaser.com");
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [showGuide, setShowGuide] = useState(false);

  useEffect(() => { jobTeaserStatus(userId).then(setStatus).catch(() => {}); }, [userId]);

  const handleSave = async () => {
    if (!cookie.trim()) return;
    setSaving(true); setError(""); setSuccess("");
    try {
      await saveJobTeaserCookie(userId, cookie.trim(), jtUrl);
      setSuccess("Cookie valide. JobTeaser est connecte.");
      setCookie("");
      setStatus({ connected: true, expires_at: new Date(Date.now() + 14 * 86400000).toISOString() });
    } catch (e) {
      const err = e as { response?: { data?: { detail?: string } } };
      setError(err?.response?.data?.detail || "Cookie invalide ou expire.");
    }
    setSaving(false);
  };

  const handleTest = async () => {
    setTesting(true); setError(""); setSuccess("");
    try {
      const r = await testJobTeaserCookie(userId);
      if (r.valid) setSuccess("Cookie toujours valide.");
      else { setError("Cookie expire ou invalide. Veuillez vous reconnecter."); setStatus({ connected: false }); }
    } catch { setError("Erreur lors du test."); }
    setTesting(false);
  };

  const handleDisconnect = async () => {
    await disconnectJobTeaser(userId).catch(() => {});
    setStatus({ connected: false }); setSuccess(""); setError("");
  };

  const statusBadge = status?.connected
    ? <span className="text-2xs px-2 py-0.5 bg-brand-50 text-brand-600 rounded-pill font-medium">Connecte</span>
    : <span className="text-2xs px-2 py-0.5 bg-gray-100 text-gray-500 rounded-pill">Non connecte</span>;

  return (
    <Card noPad>
      <CardHeader title="Connexion JobTeaser" right={statusBadge} />
      <div className="p-6 space-y-4">
        {status?.connected ? (
          <div className="space-y-3">
            <p className="text-sm text-gray-600">JobTeaser est connecte. Les offres seront scrapees automatiquement lors du prochain scan.</p>
            {status.expires_at && <p className="text-xs text-gray-400">Session expire le {new Date(status.expires_at).toLocaleDateString("fr-FR")}</p>}
            <div className="flex gap-2">
              <button onClick={handleTest} disabled={testing} className="px-4 py-1.5 text-sm font-medium border border-surface-200 rounded-button hover:bg-surface-100 transition-default disabled:opacity-50">{testing ? "Test..." : "Tester la connexion"}</button>
              <button onClick={handleDisconnect} className="px-4 py-1.5 text-sm font-medium border border-red-200 text-red-500 rounded-button hover:bg-red-50 transition-default">Deconnecter</button>
            </div>
          </div>
        ) : (
          <>
            <p className="text-sm text-gray-500">Connectez votre compte JobTeaser en copiant vos cookies de session. Cela permet de scraper les offres de votre ecole sans stocker votre mot de passe.</p>
            <button onClick={() => setShowGuide(!showGuide)} className="text-sm text-brand-400 hover:text-brand-600 font-medium transition-default">{showGuide ? "Masquer le guide" : "Comment recuperer les cookies ?"}</button>

            {showGuide && (
              <div className="bg-surface-50 rounded-card p-4 text-sm text-gray-600 space-y-3 border border-surface-200">
                <p className="font-semibold text-gray-700">Etapes (Chrome) :</p>
                <ol className="list-decimal list-inside space-y-2">
                  <li>Ouvrez <a href="https://em-lyon.jobteaser.com" target="_blank" rel="noopener noreferrer" className="text-brand-400 hover:underline">votre portail JobTeaser</a> et connectez-vous via SSO</li>
                  <li>Ouvrez les DevTools : <span className="font-mono text-xs bg-white px-1 py-0.5 rounded border">F12</span></li>
                  <li>Onglet <span className="font-semibold">Console</span>, tapez :
                    <div className="mt-1 bg-gray-900 text-green-400 font-mono text-xs px-3 py-2 rounded-button select-all">{"copy(document.cookie)"}</div>
                  </li>
                  <li>Collez le resultat dans le champ ci-dessous</li>
                </ol>
                <p className="text-xs text-gray-400">Le cookie expire apres 14-30 jours. Le CRM vous previendra quand il faudra le renouveler.</p>
              </div>
            )}

            <div>
              <label className="block text-2xs font-semibold text-gray-400 uppercase tracking-wider mb-1.5">URL de votre ecole</label>
              <input type="text" value={jtUrl} onChange={(e) => setJtUrl(e.target.value)} className="w-full px-3 py-2 border border-surface-200 rounded-button text-sm" placeholder="https://mon-ecole.jobteaser.com" />
            </div>
            <div>
              <label className="block text-2xs font-semibold text-gray-400 uppercase tracking-wider mb-1.5">Cookies (resultat de document.cookie)</label>
              <textarea value={cookie} onChange={(e) => setCookie(e.target.value)} rows={3} className="w-full px-3 py-2 border border-surface-200 rounded-button text-sm font-mono resize-none" placeholder="Collez ici..." />
            </div>
            <button onClick={handleSave} disabled={saving || !cookie.trim()} className="px-5 py-2 bg-brand-400 text-white rounded-button text-sm font-medium hover:bg-brand-500 transition-default disabled:opacity-50">{saving ? "Verification..." : "Connecter JobTeaser"}</button>
          </>
        )}

        {error && <p className="text-sm text-red-500 bg-red-50 px-3 py-2 rounded-button">{error}</p>}
        {success && <p className="text-sm text-brand-600 bg-brand-50 px-3 py-2 rounded-button">{success}</p>}
      </div>
    </Card>
  );
}
