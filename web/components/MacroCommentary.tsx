"use client";

import { useMemo, useState, useSyncExternalStore } from "react";

import type { MacroNote } from "@/lib/types";

const SHOW = 3;
const TONE = {
  good: { icon: "▲", cls: "text-good", border: "border-good/40" },
  bad: { icon: "▼", cls: "text-bad", border: "border-bad/40" },
  neutral: { icon: "●", cls: "text-warn", border: "border-warn/40" },
} as const;

function pickRandom(n: number, k: number, exclude: number[] = []) {
  // 優先挑上一輪沒出現過的，主題才會一直換
  const fresh = Array.from({ length: n }, (_, i) => i).filter((i) => !exclude.includes(i));
  const pool = fresh.length >= k ? fresh : Array.from({ length: n }, (_, i) => i);
  for (let i = pool.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [pool[i], pool[j]] = [pool[j], pool[i]];
  }
  return pool.slice(0, k);
}

const noopSubscribe = () => () => {};

/** 總經觀點：每次開啟隨機挑幾則 FRED 評語 (中英對照) */
export default function MacroCommentary({ notes }: { notes: MacroNote[] }) {
  // 隨機只能在瀏覽器端做 (伺服器與瀏覽器的亂數不同會造成 hydration 錯誤)：
  // 伺服器端 hydrated=false 先顯示佔位，進到瀏覽器後才抽第一組
  const hydrated = useSyncExternalStore(noopSubscribe, () => true, () => false);
  const k = Math.min(SHOW, notes.length);
  const initial = useMemo(() => (hydrated ? pickRandom(notes.length, k) : null), [hydrated, notes.length, k]);
  const [override, setOverride] = useState<number[] | null>(null);
  const picked = override ?? initial;
  const shuffle = () => setOverride(pickRandom(notes.length, k, picked ?? []));

  if (notes.length === 0) return null;

  return (
    <div>
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted">
          總經觀點 <span className="font-mono tracking-widest">· MACRO VIEW</span>
        </p>
        <button onClick={shuffle} className="rounded-md px-2 py-0.5 text-xs text-ink-2 hover:bg-neutral hover:text-accent">
          🔀 換一組 ({notes.length} 則)
        </button>
      </div>
      <ul className="mt-3 space-y-3" aria-live="polite">
        {picked == null
          ? Array.from({ length: SHOW }, (_, i) => <li key={i} className="h-20 animate-pulse rounded-lg bg-page/60" />)
          : picked.map((i) => {
              const n = notes[i];
              const t = TONE[n.tone];
              return (
                <li key={n.topic} className={`rounded-lg border-l-2 ${t.border} bg-page/50 px-3.5 py-2.5`}>
                  <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                    <span className={`text-sm font-semibold ${t.cls}`}>
                      {t.icon} {n.topic}
                    </span>
                    <span className="font-mono text-[11px] text-muted">
                      {n.metric.label} {n.metric.value}
                      {n.metric.change && ` · ${n.metric.change}`}
                    </span>
                  </div>
                  <p className="mt-1 text-sm leading-relaxed text-ink">{n.zh}</p>
                  <p className="mt-1 text-xs leading-relaxed text-muted">{n.en}</p>
                </li>
              );
            })}
      </ul>
      <p className="mt-2 text-[10px] text-muted">依 FRED 最新數據自動產生 · 每次開啟隨機顯示</p>
    </div>
  );
}
