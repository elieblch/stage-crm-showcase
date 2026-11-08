"use client";

import { useMemo } from "react";
import type { ScoringDimension, ScoringWeights } from "@/types";
import { Card, CardHeader, DIM_LABEL, DEFAULT_WEIGHTS } from "@/components/ui/shared";

const ORDER: ScoringDimension[] = ["domain", "company", "location", "skills", "education", "quality", "timing", "ai"];

const HELP: Record<ScoringDimension, string> = {
  domain: "Alignement entre vos domaines cibles et le domaine de l'offre",
  company: "Présence de l'offre chez une entreprise cible (globale ou personnelle)",
  location: "Match avec vos localisations souhaitées",
  skills: "Recouvrement de votre CV et skills avec le texte de l'offre",
  education: "Heuristique : Bac+5/Grande école vs Bac+2/BTS",
  quality: "Complétude de l'offre (description, salaire, contact, dates)",
  timing: "Date de début vs votre fenêtre préférée",
  ai: "Note globale attribuée par Claude",
};

export function ScoringWeightsSection({ weights, onChange }: { weights: ScoringWeights; onChange: (w: ScoringWeights) => void }) {
  const total = useMemo(() => ORDER.reduce((s, k) => s + (weights[k] ?? 0), 0), [weights]);

  const setWeight = (k: ScoringDimension, v: number) => onChange({ ...weights, [k]: Math.max(0, Math.min(100, v)) });
  const reset = () => onChange({ ...DEFAULT_WEIGHTS });

  const totalColor = total === 100 ? "text-brand-600" : total > 100 ? "text-danger-600" : "text-warn-600";

  return (
    <Card noPad>
      <CardHeader
        title="Poids du scoring"
        right={
          <div className="flex items-center gap-3">
            <span className={`text-xs font-mono font-semibold ${totalColor}`}>Total {total}%</span>
            <button onClick={reset} className="text-2xs text-ink-muted hover:text-ink underline underline-offset-2">Réinitialiser</button>
          </div>
        }
      />
      <div className="p-6 space-y-4">
        <p className="text-sm text-ink-muted">
          Chaque offre est évaluée sur 8 dimensions. Ajustez leur importance dans le calcul du score global. Le total recommandé est 100%.
        </p>
        <div className="grid grid-cols-2 gap-x-8 gap-y-4">
          {ORDER.map((k) => {
            const v = weights[k] ?? 0;
            return (
              <div key={k}>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-sm font-medium text-ink">{DIM_LABEL[k]}</label>
                  <span className="text-sm font-mono font-semibold text-ink">{v}%</span>
                </div>
                <input type="range" min={0} max={40} step={1} value={v} onChange={(e) => setWeight(k, +e.target.value)} className="w-full accent-brand-400" />
                <p className="text-2xs text-ink-faint mt-0.5">{HELP[k]}</p>
              </div>
            );
          })}
        </div>
        {total !== 100 && (
          <div className={`px-3 py-2 rounded-input text-xs ${total > 100 ? "bg-danger-50 text-danger-700" : "bg-warn-50 text-warn-700"}`}>
            Le total est {total}%. {total > 100 ? "Certaines dimensions sont sur-représentées." : "Rapprochez-vous de 100% pour une pondération claire."}
          </div>
        )}
      </div>
    </Card>
  );
}
