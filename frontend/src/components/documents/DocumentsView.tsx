"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Download, FileText, Pencil, Trash2, Upload } from "lucide-react";

import type { DocType, DocumentItem } from "@/types";
import {
  deleteDocument,
  documentDownloadUrl,
  fetchContacts,
  fetchDocuments,
  fetchOffers,
  renameDocument,
  uploadDocument,
} from "@/lib/api";
import { Card, CardHeader, fmtDate } from "@/components/ui/shared";

const DOC_TYPE_LABEL: Record<DocType, string> = { cv: "CV", lm: "Lettre de motivation" };

function fmtSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} o`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} Ko`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`;
}

export function DocumentsView() {
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [usage, setUsage] = useState<Record<number, number>>({});
  const [typeFilter, setTypeFilter] = useState<DocType | "">("");
  const [loading, setLoading] = useState(true);

  // Upload form.
  const [newType, setNewType] = useState<DocType>("cv");
  const [newLabel, setNewLabel] = useState("");
  const [newFile, setNewFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Rename inline.
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editLabel, setEditLabel] = useState("");

  const computeUsage = useCallback(async () => {
    const [offers, contacts] = await Promise.all([fetchOffers(), fetchContacts()]);
    const map: Record<number, number> = {};
    const bump = (id: number | null) => {
      if (id != null) map[id] = (map[id] || 0) + 1;
    };
    // Chaque fiche compte une fois même si elle référence le même doc deux fois.
    offers.forEach((o) => {
      const ids = new Set([o.cv_document_id, o.lm_document_id].filter((x): x is number => x != null));
      ids.forEach(bump);
    });
    contacts.forEach((c) => {
      const ids = new Set([c.cv_document_id, c.lm_document_id].filter((x): x is number => x != null));
      ids.forEach(bump);
    });
    setUsage(map);
  }, []);

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([fetchDocuments(typeFilter || undefined).then(setDocs), computeUsage()])
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [typeFilter, computeUsage]);

  useEffect(() => {
    load();
  }, [load]);

  const submitUpload = async () => {
    if (!newFile || !newLabel.trim()) return;
    setBusy(true);
    setErr(null);
    try {
      await uploadDocument(newType, newLabel.trim(), newFile);
      setNewLabel("");
      setNewFile(null);
      load();
    } catch {
      setErr("Échec de l'upload (PDF, max 10 Mo).");
    } finally {
      setBusy(false);
    }
  };

  const saveRename = async (id: number) => {
    if (!editLabel.trim()) return;
    await renameDocument(id, editLabel.trim());
    setEditingId(null);
    load();
  };

  const remove = async (doc: DocumentItem) => {
    const n = usage[doc.id] || 0;
    const msg =
      n > 0
        ? `Supprimer « ${doc.label} » ?\n${n} fiche${n > 1 ? "s" : ""} perdr${n > 1 ? "ont" : "a"} le lien vers ce document.`
        : `Supprimer « ${doc.label} » ?`;
    if (!confirm(msg)) return;
    await deleteDocument(doc.id);
    load();
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-ink">Documents</h1>
        <p className="text-sm text-ink-muted mt-1">
          Bibliothèque de CV et lettres de motivation réutilisables sur vos offres et contacts.
        </p>
      </div>

      {/* Upload */}
      <Card noPad>
        <CardHeader title="Ajouter un document" />
        <div className="p-5 flex items-end gap-3 flex-wrap">
          <div>
            <label className="block text-xs font-medium text-ink-muted mb-1.5">Type</label>
            <select
              value={newType}
              onChange={(e) => setNewType(e.target.value as DocType)}
              className="px-3 py-2 border border-line rounded-input text-sm bg-card"
            >
              <option value="cv">CV</option>
              <option value="lm">Lettre de motivation</option>
            </select>
          </div>
          <div className="flex-1 min-w-[180px]">
            <label className="block text-xs font-medium text-ink-muted mb-1.5">Label</label>
            <input
              type="text"
              value={newLabel}
              onChange={(e) => setNewLabel(e.target.value)}
              placeholder="CV_quant_v2"
              className="w-full px-3 py-2 border border-line rounded-input text-sm bg-card"
            />
          </div>
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            className="inline-flex items-center gap-1.5 text-sm text-ink-muted border border-dashed border-line rounded-input px-3 py-2 hover:border-brand-400 hover:text-brand-600 transition-default"
          >
            <Upload size={14} /> {newFile ? newFile.name : "Choisir un PDF"}
          </button>
          <input
            ref={inputRef}
            type="file"
            accept="application/pdf"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0] ?? null;
              setNewFile(f);
              if (f && !newLabel.trim()) setNewLabel(f.name.replace(/\.pdf$/i, ""));
              e.target.value = "";
            }}
          />
          <button
            type="button"
            onClick={submitUpload}
            disabled={!newFile || !newLabel.trim() || busy}
            className="px-4 py-2 bg-brand-400 text-white rounded-input text-sm font-medium hover:bg-brand-500 disabled:opacity-50"
          >
            {busy ? "Envoi…" : "Ajouter"}
          </button>
          {err && <p className="text-2xs text-red-500 w-full">{err}</p>}
        </div>
      </Card>

      {/* Filtre */}
      <Card>
        <div className="flex items-center gap-3 flex-wrap text-sm">
          <span className="text-2xs font-semibold text-ink-faint uppercase tracking-wider">Filtres</span>
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value as DocType | "")}
            className="px-2.5 py-1.5 border border-line rounded-input text-sm bg-card"
          >
            <option value="">Tous les types</option>
            <option value="cv">CV</option>
            <option value="lm">Lettres de motivation</option>
          </select>
          {typeFilter && (
            <button onClick={() => setTypeFilter("")} className="text-2xs text-ink-faint hover:text-ink underline underline-offset-2">
              Réinitialiser
            </button>
          )}
        </div>
      </Card>

      {/* Liste */}
      {loading ? (
        <div className="text-center text-ink-faint py-12 text-sm">Chargement…</div>
      ) : docs.length === 0 ? (
        <Card className="text-center py-12">
          <p className="text-sm text-ink-muted">Aucun document.</p>
          <p className="text-xs text-ink-faint mt-1">Ajoutez vos CV et lettres de motivation réutilisables.</p>
        </Card>
      ) : (
        <Card noPad>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-2xs text-ink-faint uppercase tracking-wider border-b border-line">
                <th className="text-left font-medium px-5 py-2.5">Label</th>
                <th className="text-left font-medium px-3 py-2.5">Type</th>
                <th className="text-left font-medium px-3 py-2.5">Fichier</th>
                <th className="text-left font-medium px-3 py-2.5">Lié à</th>
                <th className="text-left font-medium px-3 py-2.5">Ajouté</th>
                <th className="px-3 py-2.5"></th>
              </tr>
            </thead>
            <tbody>
              {docs.map((doc) => (
                <tr key={doc.id} className="border-b border-line-subtle">
                  <td className="px-5 py-3">
                    {editingId === doc.id ? (
                      <div className="flex items-center gap-2">
                        <input
                          value={editLabel}
                          onChange={(e) => setEditLabel(e.target.value)}
                          onKeyDown={(e) => e.key === "Enter" && saveRename(doc.id)}
                          autoFocus
                          className="px-2 py-1 border border-line rounded-input text-sm bg-card"
                        />
                        <button onClick={() => saveRename(doc.id)} className="text-2xs text-brand-600 font-medium">
                          OK
                        </button>
                        <button onClick={() => setEditingId(null)} className="text-2xs text-ink-faint">
                          Annuler
                        </button>
                      </div>
                    ) : (
                      <span className="inline-flex items-center gap-2 font-medium text-ink">
                        <FileText size={14} className="text-ink-faint" /> {doc.label}
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-3">
                    <span className="text-2xs px-2 py-0.5 rounded-pill font-medium bg-surface-100 text-ink-muted">
                      {DOC_TYPE_LABEL[doc.doc_type]}
                    </span>
                  </td>
                  <td className="px-3 py-3 text-ink-faint text-xs">
                    {doc.original_filename} · {fmtSize(doc.file_size)}
                  </td>
                  <td className="px-3 py-3 text-ink-muted text-xs font-mono">
                    {usage[doc.id] ? `${usage[doc.id]} fiche${usage[doc.id] > 1 ? "s" : ""}` : "—"}
                  </td>
                  <td className="px-3 py-3 text-ink-faint text-xs font-mono">{fmtDate(doc.created_at)}</td>
                  <td className="px-3 py-3">
                    <div className="flex items-center justify-end gap-2">
                      <a
                        href={documentDownloadUrl(doc.id)}
                        target="_blank"
                        rel="noreferrer"
                        className="text-ink-faint hover:text-brand-600"
                        title="Télécharger"
                      >
                        <Download size={15} />
                      </a>
                      <button
                        onClick={() => {
                          setEditingId(doc.id);
                          setEditLabel(doc.label);
                        }}
                        className="text-ink-faint hover:text-ink"
                        title="Renommer"
                      >
                        <Pencil size={15} />
                      </button>
                      <button
                        onClick={() => remove(doc)}
                        className="text-ink-faint hover:text-red-500"
                        title="Supprimer"
                      >
                        <Trash2 size={15} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
