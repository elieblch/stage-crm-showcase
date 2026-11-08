"use client";

import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer } from "recharts";
import type { MatchReasons, ScoringDimension } from "@/types";
import { DIM_LABEL } from "@/components/ui/shared";

const ORDER: ScoringDimension[] = ["domain", "company", "location", "skills", "education", "quality", "timing", "ai"];

export function ScoreRadarChart({ reasons, size = 260 }: { reasons: MatchReasons; size?: number }) {
  const dims = reasons?.dimensions;
  if (!dims || typeof dims !== "object") {
    return <p className="text-xs text-gray-400 italic">Détail multi-dimensions indisponible pour cette offre (scoring legacy).</p>;
  }
  const data = ORDER.map((k) => ({
    dim: DIM_LABEL[k],
    key: k,
    score: typeof dims[k] === "number" ? (dims[k] as number) : 0,
    missing: dims[k] === null || dims[k] === undefined,
  }));
  return (
    <div style={{ width: "100%", height: size }}>
      <ResponsiveContainer>
        <RadarChart data={data} margin={{ top: 10, right: 30, bottom: 10, left: 30 }}>
          <PolarGrid stroke="#E5E7EB" />
          <PolarAngleAxis dataKey="dim" tick={{ fontSize: 11, fill: "#6B7280" }} />
          <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fontSize: 9, fill: "#9CA3AF" }} />
          <Radar name="Score" dataKey="score" stroke="#1d9e75" fill="#1d9e75" fillOpacity={0.35} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
