"use client";

import { useEffect, useState } from "react";
import { fetchUser, fetchPreferences, fetchDocuments, updateUser, updatePreferences, uploadDocument, deleteDocument, setDocumentPrimary } from "@/lib/api";
import type { UserDocument, ScoringWeights } from "@/types";
import { Card, CardHeader, Field, TagInput, DEFAULT_WEIGHTS, resolveUserId } from "@/components/ui/shared";
import { JobTeaserSection } from "@/components/profil/JobTeaserSection";
import { ScoringWeightsSection } from "@/components/profil/ScoringWeightsSection";
import { NewsletterSection } from "@/components/profil/NewsletterSection";

const DOC_LABELS: Record<string, string> = { cv: "CV", bulletin: "Bulletin", projet: "Projet", certification: "Certification", lettre_ref: "Lettre de reference", lettre_motivation: "Lettre de motivation" };

export function ProfilView() {
  const userId = resolveUserId();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");
  const [name, setName] = useState(""); const [email, setEmail] = useState(""); const [phone, setPhone] = useState(""); const [linkedin, setLinkedin] = useState("");
  const [domains, setDomains] = useState<string[]>([]); const [locations, setLocations] = useState<string[]>([]); const [contracts, setContracts] = useState<string[]>([]);
  const [companies, setCompanies] = useState<string[]>([]); const [kw, setKw] = useState<string[]>([]); const [exKw, setExKw] = useState<string[]>([]);
  const [minDur, setMinDur] = useState<number | "">(""); const [maxDur, setMaxDur] = useState<number | "">("");
  const [startDate, setStartDate] = useState(""); const [minScore, setMinScore] = useState(50);
  const [weights, setWeights] = useState<ScoringWeights>(DEFAULT_WEIGHTS);
  const [newsletterEnabled, setNewsletterEnabled] = useState(true);
  const [newsletterTime, setNewsletterTime] = useState("08:00:00");
  const [docs, setDocs] = useState<UserDocument[]>([]);
  const [file, setFile] = useState<File | null>(null); const [docType, setDocType] = useState("cv"); const [docTitle, setDocTitle] = useState(""); const [uploading, setUploading] = useState(false);
  const [delId, setDelId] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([fetchUser(userId), fetchPreferences(userId), fetchDocuments(userId)]).then(([u, p, d]) => {
      setName(u.full_name || ""); setEmail(u.email || ""); setPhone(u.phone || ""); setLinkedin(u.linkedin_url || "");
      setDomains(p.target_domains || []); setLocations(p.target_locations || []); setContracts(p.contract_types || []);
      setCompanies(p.target_companies || []); setKw(p.keywords || []); setExKw(p.excluded_keywords || []);
      setMinDur(p.min_duration_months ?? ""); setMaxDur(p.max_duration_months ?? ""); setStartDate(p.start_date_earliest || ""); setMinScore(p.min_match_score ?? 50);
      setWeights({ ...DEFAULT_WEIGHTS, ...(p.scoring_weights || {}) });
      setNewsletterEnabled(p.newsletter_enabled ?? true);
      setNewsletterTime(p.newsletter_time || "08:00:00");
      setDocs(d || []);
    }).catch(() => {}).finally(() => setLoading(false));
  }, [userId]);

  const save = async () => {
    setSaving(true); setMsg("");
    try {
      await Promise.all([
        updateUser(userId, { full_name: name, email, phone: phone || null, linkedin_url: linkedin || null }),
        updatePreferences(userId, {
          target_domains: domains, target_locations: locations, contract_types: contracts,
          target_companies: companies, keywords: kw, excluded_keywords: exKw,
          min_duration_months: minDur === "" ? null : minDur, max_duration_months: maxDur === "" ? null : maxDur,
          start_date_earliest: startDate || null, min_match_score: minScore,
          scoring_weights: weights,
          newsletter_enabled: newsletterEnabled,
          newsletter_time: newsletterTime,
        }),
      ]);
      setMsg("Profil sauvegarde. Rescoring en cours..."); setTimeout(() => setMsg(""), 5000);
    } catch { alert("Erreur."); } finally { setSaving(false); }
  };

  const upload = async () => {
    if (!file || !docTitle.trim()) return; setUploading(true);
    try { await uploadDocument(userId, file, docType, docTitle.trim()); setFile(null); setDocTitle(""); setDocType("cv"); setDocs(await fetchDocuments(userId)); } catch { alert("Erreur upload."); } finally { setUploading(false); }
  };

  if (loading) return <div className="text-center text-gray-400 py-12">Chargement...</div>;

  const byType: Record<string, UserDocument[]> = {}; docs.forEach((d) => { (byType[d.doc_type] ||= []).push(d); });

  return (
    <div className="space-y-8 max-w-3xl mx-auto">
      <div>
        <h1 className="font-display text-ink">Mon profil</h1>
        <p className="text-sm text-ink-muted mt-1">Informations personnelles, critères de recherche, poids du scoring.</p>
      </div>

      <Card noPad>
        <CardHeader title="Informations personnelles" />
        <div className="p-6 grid grid-cols-2 gap-4">
          <Field label="Nom complet" value={name} onChange={setName} />
          <Field label="Email" value={email} onChange={setEmail} type="email" />
          <Field label="Telephone" value={phone} onChange={setPhone} placeholder="+33 6 ..." />
          <Field label="LinkedIn" value={linkedin} onChange={setLinkedin} placeholder="https://linkedin.com/in/..." />
        </div>
      </Card>

      <Card noPad>
        <CardHeader title="Criteres de recherche" />
        <div className="p-6 space-y-5">
          <div><label className="block text-sm font-medium text-gray-700 mb-1.5">Domaines cibles</label><TagInput value={domains} onChange={setDomains} placeholder="Finance de marche, M&A..." /></div>
          <div><label className="block text-sm font-medium text-gray-700 mb-1.5">Localisations</label><TagInput value={locations} onChange={setLocations} placeholder="Paris, Londres..." /></div>
          <div><label className="block text-sm font-medium text-gray-700 mb-1.5">Types de contrat</label><TagInput value={contracts} onChange={setContracts} placeholder="Stage, Alternance..." /></div>
          <div><label className="block text-sm font-medium text-gray-700 mb-1.5">Entreprises cibles</label><TagInput value={companies} onChange={setCompanies} placeholder="Goldman Sachs, BNP..." /></div>
          <div><label className="block text-sm font-medium text-gray-700 mb-1.5">Mots-cles</label><TagInput value={kw} onChange={setKw} placeholder="trading, quant..." /></div>
          <div><label className="block text-sm font-medium text-gray-700 mb-1.5">Mots-cles exclus</label><TagInput value={exKw} onChange={setExKw} placeholder="comptabilite, audit..." /></div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Date de debut souhaitee</label>
            <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="w-full px-3 py-2 border border-surface-200 rounded-button text-sm" />
            <p className="text-xs text-gray-400 mt-1">Fenetre : 1 mois avant a 3 mois apres cette date.</p>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div><label className="block text-sm font-medium text-gray-700 mb-1.5">Duree min (mois)</label><input type="number" value={minDur} onChange={(e) => setMinDur(e.target.value === "" ? "" : +e.target.value)} className="w-full px-3 py-2 border border-surface-200 rounded-button text-sm" min={0} placeholder="3" /></div>
            <div><label className="block text-sm font-medium text-gray-700 mb-1.5">Duree max (mois)</label><input type="number" value={maxDur} onChange={(e) => setMaxDur(e.target.value === "" ? "" : +e.target.value)} className="w-full px-3 py-2 border border-surface-200 rounded-button text-sm" min={0} placeholder="6" /></div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Score minimum : {minScore}%</label>
            <input type="range" min={0} max={100} value={minScore} onChange={(e) => setMinScore(+e.target.value)} className="w-full accent-brand-400" />
            <div className="flex justify-between text-2xs text-gray-400 mt-1"><span>0</span><span>50</span><span>100</span></div>
          </div>
        </div>
      </Card>

      <ScoringWeightsSection weights={weights} onChange={setWeights} />

      <NewsletterSection
        enabled={newsletterEnabled}
        time={newsletterTime}
        minScore={minScore}
        recipient={email}
        onChange={(v) => {
          if (v.enabled !== undefined) setNewsletterEnabled(v.enabled);
          if (v.time !== undefined) setNewsletterTime(v.time);
          if (v.minScore !== undefined) setMinScore(v.minScore);
          if (v.recipient !== undefined) setEmail(v.recipient);
        }}
      />

      <Card>
        <div className="flex items-center justify-between">
          {msg && <div className="px-3 py-1.5 bg-brand-50 text-brand-700 rounded-input text-sm font-medium">{msg}</div>}
          <button onClick={save} disabled={saving} className="ml-auto px-5 py-2 bg-ink text-white rounded-input font-medium text-sm hover:bg-ink/90 disabled:opacity-50">{saving ? "Sauvegarde…" : "Sauvegarder"}</button>
        </div>
      </Card>

      <JobTeaserSection />

      <Card noPad>
        <CardHeader title="Mes documents" />
        <div className="p-6 space-y-5">
          <div className="flex items-end gap-3">
            <div className="flex-1"><label className="block text-2xs font-semibold text-gray-400 uppercase tracking-wider mb-1.5">Fichier</label><input type="file" accept=".pdf,.docx,.doc,.txt" onChange={(e) => setFile(e.target.files?.[0] || null)} className="text-sm" /></div>
            <div><label className="block text-2xs font-semibold text-gray-400 uppercase tracking-wider mb-1.5">Type</label><select value={docType} onChange={(e) => setDocType(e.target.value)} className="px-3 py-1.5 border border-surface-200 rounded-button text-sm">{Object.entries(DOC_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></div>
            <div className="flex-1"><label className="block text-2xs font-semibold text-gray-400 uppercase tracking-wider mb-1.5">Titre</label><input type="text" value={docTitle} onChange={(e) => setDocTitle(e.target.value)} placeholder="Mon CV 2026" className="w-full px-3 py-1.5 border border-surface-200 rounded-button text-sm" /></div>
            <button onClick={upload} disabled={uploading || !file || !docTitle.trim()} className="px-4 py-1.5 bg-brand-400 text-white rounded-button text-sm font-medium hover:bg-brand-500 disabled:opacity-50 transition-default">{uploading ? "..." : "Upload"}</button>
          </div>
          {Object.entries(byType).map(([type, list]) => (
            <div key={type}>
              <h3 className="text-sm font-medium text-gray-700 mb-2">{DOC_LABELS[type] || type}</h3>
              <div className="space-y-1.5">{list.map((d) => (
                <div key={d.id} className="flex items-center justify-between px-3 py-2.5 bg-surface-50 rounded-button">
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-gray-800">{d.title}</span>
                    {d.is_primary && <span className="text-2xs px-1.5 py-0.5 bg-amber-50 text-amber-600 rounded-pill font-medium">Principal</span>}
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="text-2xs text-gray-400 mr-1">{new Date(d.uploaded_at).toLocaleDateString("fr-FR")}</span>
                    <button onClick={() => setDocumentPrimary(userId, d.id).then(() => fetchDocuments(userId).then(setDocs))} className={`p-1 rounded ${d.is_primary ? "text-amber-500" : "text-gray-300 hover:text-amber-400"}`}>
                      <svg width="13" height="13" fill="currentColor" viewBox="0 0 20 20"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" /></svg>
                    </button>
                    {delId === d.id ? (
                      <><button onClick={() => deleteDocument(userId, d.id).then(() => { setDocs((p) => p.filter((x) => x.id !== d.id)); setDelId(null); })} className="text-2xs text-red-600 font-semibold">Oui</button><button onClick={() => setDelId(null)} className="text-2xs text-gray-400">Non</button></>
                    ) : (
                      <button onClick={() => setDelId(d.id)} className="p-1 text-gray-300 hover:text-red-400 transition-default">
                        <svg width="13" height="13" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                      </button>
                    )}
                  </div>
                </div>
              ))}</div>
            </div>
          ))}
          {!docs.length && <p className="text-sm text-gray-400 text-center py-4">Aucun document.</p>}
        </div>
      </Card>
    </div>
  );
}
