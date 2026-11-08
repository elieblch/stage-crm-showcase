"use client";

import { useEffect, useRef, useState } from "react";
import { Download, FileText, Upload, X } from "lucide-react";

import type { DocType, DocumentBrief, DocumentItem } from "@/types";
import { documentDownloadUrl, fetchDocuments, uploadDocument } from "@/lib/api";

// Sélecteur de document (CV / LM) depuis la bibliothèque, avec option « uploader
// un nouveau » qui ajoute le document ET le sélectionne immédiatement sur la fiche.
export function DocumentPicker({
  title,
  docType,
  value,
  current,
  onChange,
}: {
  title: string;
  docType: DocType;
  value: number | null;
  current?: DocumentBrief | null;
  onChange: (id: number | null) => void;
}) {
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [uploading, setUploading] = useState(false);
  const [label, setLabel] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const load = () =>
    fetchDocuments(docType)
      .then(setDocs)
      .catch(() => {});

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [docType]);

  const selectedLabel =
    docs.find((d) => d.id === value)?.label ??
    (current && current.id === value ? current.label : null);

  const doUpload = async () => {
    if (!file || !label.trim()) return;
    setBusy(true);
    setErr(null);
    try {
      const doc = await uploadDocument(docType, label.trim(), file);
      await load();
      onChange(doc.id); // sélection immédiate sur la fiche
      setUploading(false);
      setLabel("");
      setFile(null);
    } catch {
      setErr("Échec de l'upload (PDF, max 10 Mo).");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="border border-line rounded-card p-3">
      <div className="flex items-center gap-2 mb-2">
        <FileText size={15} className="text-ink-faint" strokeWidth={1.75} />
        <span className="text-xs font-medium text-ink">{title}</span>
        {value != null && (
          <a
            href={documentDownloadUrl(value)}
            target="_blank"
            rel="noreferrer"
            className="ml-auto inline-flex items-center gap-1 text-2xs text-brand-600 hover:text-brand-700 font-medium"
          >
            <Download size={12} /> Télécharger
          </a>
        )}
      </div>

      {uploading ? (
        <div className="space-y-2">
          <input
            type="text"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="Label (ex. CV_quant_v2)"
            className="w-full px-3 py-1.5 border border-line rounded-input text-sm bg-card"
          />
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            className="w-full inline-flex items-center justify-center gap-1.5 text-xs text-ink-muted border border-dashed border-line rounded-input py-2 hover:border-brand-400 hover:text-brand-600 transition-default"
          >
            <Upload size={13} /> {file ? file.name : "Choisir un PDF"}
          </button>
          <input
            ref={inputRef}
            type="file"
            accept="application/pdf"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0] ?? null;
              setFile(f);
              if (f && !label.trim()) setLabel(f.name.replace(/\.pdf$/i, ""));
              e.target.value = "";
            }}
          />
          {err && <p className="text-2xs text-red-500">{err}</p>}
          <div className="flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={() => {
                setUploading(false);
                setErr(null);
                setFile(null);
              }}
              className="text-2xs text-ink-muted hover:text-ink"
            >
              Annuler
            </button>
            <button
              type="button"
              onClick={doUpload}
              disabled={!file || !label.trim() || busy}
              className="px-3 py-1 bg-brand-400 text-white rounded-input text-2xs font-medium hover:bg-brand-500 disabled:opacity-50"
            >
              {busy ? "Envoi…" : "Ajouter & sélectionner"}
            </button>
          </div>
        </div>
      ) : (
        <div className="flex items-center gap-2">
          <select
            value={value ?? ""}
            onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}
            className="flex-1 px-2.5 py-1.5 border border-line rounded-input text-sm bg-card"
          >
            <option value="">— Aucun —</option>
            {/* Document lié hors liste courante (sécurité) */}
            {value != null && !docs.some((d) => d.id === value) && selectedLabel && (
              <option value={value}>{selectedLabel}</option>
            )}
            {docs.map((d) => (
              <option key={d.id} value={d.id}>
                {d.label}
              </option>
            ))}
          </select>
          {value != null && (
            <button
              type="button"
              onClick={() => onChange(null)}
              className="text-ink-faint hover:text-red-500 shrink-0"
              title="Retirer le lien"
            >
              <X size={15} />
            </button>
          )}
          <button
            type="button"
            onClick={() => setUploading(true)}
            className="shrink-0 inline-flex items-center gap-1 text-2xs text-ink-muted hover:text-brand-600 border border-line rounded-input px-2 py-1.5"
            title="Uploader un nouveau document"
          >
            <Upload size={12} /> Nouveau
          </button>
        </div>
      )}
    </div>
  );
}
