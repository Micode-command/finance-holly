"use client";

import { useEffect, useMemo, useState } from "react";

import { CATEGORIES, GLOSSARY, type Term } from "@/lib/glossary";

export function TermBody({ term }: { term: Term }) {
  return (
    <div className="space-y-2 text-sm leading-relaxed">
      <p className="text-ink">{term.short}</p>
      <p className="text-ink-2">{term.detail}</p>
      <div>
        <p className="text-xs font-semibold text-muted">怎麼看</p>
        <ul className="mt-1 space-y-0.5 text-ink-2">
          {term.read.map((r) => (
            <li key={r} className="flex gap-1.5">
              <span className="text-accent">›</span>
              {r}
            </li>
          ))}
        </ul>
      </div>
      {term.tw && (
        <p className="rounded-md bg-page/70 px-2.5 py-1.5 text-ink-2">
          <span className="font-semibold text-ink">🇹🇼 對台股：</span>
          {term.tw}
        </p>
      )}
    </div>
  );
}

/** 名詞小辭典：可搜尋、可依分類篩選 */
export default function Glossary() {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<string | null>(null);

  // 從卡片點「名詞」跳過來時 (網址 #term-xxx)，自動展開那一則
  useEffect(() => {
    const openTarget = () => {
      const el = document.getElementById(decodeURIComponent(location.hash.slice(1)));
      if (el instanceof HTMLDetailsElement) el.open = true;
    };
    openTarget();
    window.addEventListener("hashchange", openTarget);
    return () => window.removeEventListener("hashchange", openTarget);
  }, []);

  const items = useMemo(() => {
    const q = query.trim().toLowerCase();
    return GLOSSARY.filter(
      (t) =>
        (!category || t.category === category) &&
        (!q || [t.name, t.en, t.short, t.detail].some((s) => s.toLowerCase().includes(q))),
    );
  }, [query, category]);

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="搜尋名詞，例如 VIX、QT、殖利率…"
          aria-label="搜尋名詞"
          className="glass w-full rounded-lg px-3 py-2 text-sm outline-none placeholder:text-muted focus:border-accent sm:w-72"
        />
        <div className="flex flex-wrap gap-1.5 text-xs">
          {[null, ...CATEGORIES].map((c) => (
            <button
              key={c ?? "all"}
              onClick={() => setCategory(c)}
              aria-pressed={category === c}
              className={`rounded-full border px-2.5 py-1 ${category === c ? "border-accent/50 bg-accent/15 text-accent" : "border-hairline text-ink-2 hover:text-accent"}`}
            >
              {c ?? "全部"}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-2">
        {items.map((t) => (
          <details key={t.id} id={`term-${t.id}`} className="glass group scroll-mt-24 rounded-xl p-4 target:border-accent" open={Boolean(query)}>
            <summary className="flex cursor-pointer list-none items-start justify-between gap-3">
              <div>
                <h3 className="font-semibold">{t.name}</h3>
                <p className="font-mono text-[11px] text-muted">{t.en}</p>
                <p className="mt-1 text-sm text-ink-2 group-open:hidden">{t.short}</p>
              </div>
              <span className="mt-0.5 shrink-0 text-xs text-muted group-open:hidden">展開 ▸</span>
              <span className="mt-0.5 hidden shrink-0 text-xs text-muted group-open:inline">收合 ▾</span>
            </summary>
            <div className="mt-3 border-t border-hairline pt-3">
              <TermBody term={t} />
            </div>
          </details>
        ))}
        {items.length === 0 && <p className="text-sm text-muted">找不到相關名詞。</p>}
      </div>
    </div>
  );
}
