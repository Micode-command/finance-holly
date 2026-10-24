"use client";

import { createContext, useContext, useState } from "react";

import type { Range } from "@/lib/types";

type RangeChoice = "auto" | Range;

const RangeCtx = createContext<{ range: RangeChoice; setRange: (r: RangeChoice) => void }>({
  range: "auto",
  setRange: () => {},
});

export const useRange = () => useContext(RangeCtx);

export function RangeProvider({ children }: { children: React.ReactNode }) {
  const [range, setRange] = useState<RangeChoice>("auto");
  return <RangeCtx.Provider value={{ range, setRange }}>{children}</RangeCtx.Provider>;
}

const OPTIONS: { value: RangeChoice; label: string }[] = [
  { value: "auto", label: "自動" },
  { value: "3M", label: "3 個月" },
  { value: "1Y", label: "1 年" },
  { value: "3Y", label: "3 年" },
];

export function RangeToggle() {
  const { range, setRange } = useRange();
  return (
    <div role="radiogroup" aria-label="圖表區間" className="inline-flex rounded-lg border border-hairline bg-surface/70 p-0.5 text-sm">
      {OPTIONS.map((o) => (
        <button
          key={o.value}
          role="radio"
          aria-checked={range === o.value}
          onClick={() => setRange(o.value)}
          className={`rounded-md px-3 py-1 transition-colors ${
            range === o.value ? "bg-accent/15 text-accent" : "text-ink-2 hover:bg-neutral"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
