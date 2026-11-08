"use client";

import { useState } from "react";
import { X, Zap } from "lucide-react";

import type { ContactInput, OfferInput } from "@/types";
import { parseQuickAdd, type QuickAddResult } from "@/lib/quickAdd";

const PLACEHOLDER = `{
  "type": "offer",
  "title": "Stage M&A",
  "company": "Lazard",
  "location": "Paris",
  "url": "",
  "source": "LinkedIn",
  "priority": "haute",
  "status": "a_postuler",
  "deadline": "2026-09-30",
  "notes": ""
}`;

// Modal « Ajout rapide » : colle un bloc JSON (offer | contact) → parsing 100 % local
// → pré-remplit le formulaire correspondant. Jamais d'écriture directe en base.
export function QuickAddModal({
  onClose,
  onApply,
}: {
  onClose: () => void;
  onApply: (
    kind: "offer" | "contact",
    fields: OfferInput | ContactInput,
    warnings: string[]
  ) => void;
}) {
  const [text, setText] = useState("");
  const [result, setResult] = useState<QuickAddResult | null>(null);

  const parse = () => setResult(parseQuickAdd(text));

  const apply = () => {
    if (!result || !result.ok) return;
    onApply(result.kind, result.fields, result.warnings);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/30 p-6 overflow-y-auto">
      <div className="bg-card border border-line rounded-card-lg w-full max-w-lg mt-12 shadow-xl">
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-line">
          <h3 className="inline-flex items-center gap-2 text-[15px] font-semibold text-ink tracking-tight">
            <Zap size={16} className="text-brand-500" /> Ajout rapide
          </h3>
          <button onClick={onClose} className="text-ink-faint hover:text-ink">
            <X size={18} />
          </button>
        </div>

        <div className="p-5 space-y-3">
          <p className="text-xs text-ink-muted">
            Collez un bloc JSON structuré (champ <code className="font-mono">type</code> :{" "}
            <code className="font-mono">offer</code> ou <code className="font-mono">contact</code>). Le
            parsing est 100 % local — vous relisez et validez le formulaire avant enregistrement.
          </p>
          <textarea
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              setResult(null);
            }}
            rows={10}
            placeholder={PLACEHOLDER}
            className="w-full px-3 py-2 border border-line rounded-input text-xs font-mono resize-y bg-card"
          />

          {result && !result.ok && (
            <div className="text-xs text-red-600 bg-red-50 border border-red-100 rounded-input px-3 py-2">
              {result.error}
            </div>
          )}

          {result && result.ok && (
            <div className="text-xs bg-surface-50 border border-line rounded-input px-3 py-2 space-y-1">
              <div className="text-ink">
                Détecté :{" "}
                <span className="font-semibold">
                  {result.kind === "offer" ? "Offre" : "Contact"}
                </span>
              </div>
              {result.warnings.length > 0 && (
                <ul className="list-disc list-inside text-amber-700">
                  {result.warnings.map((w, i) => (
                    <li key={i}>{w}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>

        <div className="px-5 py-4 border-t border-line flex items-center justify-end gap-2">
          <button onClick={onClose} className="px-3 py-1.5 text-sm text-ink-muted hover:text-ink">
            Annuler
          </button>
          {result && result.ok ? (
            <button
              onClick={apply}
              className="px-4 py-1.5 bg-brand-400 text-white rounded-input text-sm font-medium hover:bg-brand-500"
            >
              Pré-remplir le formulaire
            </button>
          ) : (
            <button
              onClick={parse}
              disabled={!text.trim()}
              className="px-4 py-1.5 bg-ink text-white rounded-input text-sm font-medium hover:bg-ink/90 disabled:opacity-50"
            >
              Analyser
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
