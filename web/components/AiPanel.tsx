"use client";

import { useState } from "react";

import type { AiResult, NewsImpact } from "@/lib/types";

// 資金配置五類：固定顏色順序 (categorical slot 1-5)
const ALLOCATION = [
  { key: "twd_cash", label: "台幣存款", color: "var(--cat-1)", fallback: "防禦保命" },
  { key: "usd_assets", label: "外幣與公司債", color: "var(--cat-2)", fallback: "鎖利防禦" },
  { key: "cashflow", label: "月配息現金流", color: "var(--cat-3)", fallback: "震盪護城河" },
  { key: "core_growth", label: "核心股票", color: "var(--cat-4)", fallback: "資本攻擊" },
  { key: "tactical_hedge", label: "黃金與戰術", color: "var(--cat-5)", fallback: "黑天鵝防禦" },
];

const DIRECTION = {
  up: { icon: "▲", cls: "text-up", label: "偏漲" },
  down: { icon: "▼", cls: "text-down", label: "偏跌" },
  mixed: { icon: "◆", cls: "text-flat", label: "震盪" },
} as const;

/** 「已反映 / 部分反映 / 尚未反映」放成標籤，後面的理由照原文 */
function PricedIn({ text }: { text: string }) {
  const m = text.match(/^(已反映|部分反映|尚未反映)[：:，,\s]*/);
  const tag = m?.[1];
  const cls = tag === "尚未反映" ? "bg-flat text-page" : tag === "部分反映" ? "bg-flat/20 text-flat" : "bg-neutral text-ink-2";
  return (
    <p>
      {tag && <span className={`mr-2 rounded px-1.5 py-0.5 text-xs font-semibold ${cls}`}>{tag}</span>}
      {m ? text.slice(m[0].length) : text}
    </p>
  );
}

function Impact({ it, sources }: { it: NewsImpact; sources: AiResult["sources"] }) {
  return (
    <article className="rounded-xl border border-hairline bg-page/50 p-4 sm:p-5">
      <h4 className="text-lg font-bold">{it.event}</h4>
      <p className="mt-1 text-xs text-muted">
        根據：
        {it.sources.map((n, i) => {
          const src = sources?.[n - 1];
          return (
            <span key={n}>
              {i > 0 && "、"}
              {src?.link ? <a href={src.link} target="_blank" rel="noopener noreferrer" className="underline decoration-hairline underline-offset-2 hover:text-accent">{src.title}</a> : src?.title ?? `新聞 ${n}`}
            </span>
          );
        })}
      </p>

      <div className="mt-4 grid gap-4 text-sm leading-relaxed sm:grid-cols-2">
        <div>
          <p className="text-xs text-muted">短期 (1~4 週)</p>
          <p className="mt-1">{it.short_term}</p>
        </div>
        <div>
          <p className="text-xs text-muted">長期 (3~12 個月)</p>
          <p className="mt-1">{it.long_term}</p>
        </div>
      </div>

      {it.affected.length > 0 && (
        <div className="mt-4">
          <p className="text-xs text-muted">誰的價格會受影響</p>
          <ul className="mt-1.5 flex flex-wrap gap-2">
            {it.affected.map((a) => {
              const d = DIRECTION[a.direction] ?? DIRECTION.mixed;
              return (
                <li key={a.asset} className="rounded-md bg-surface-2 px-2.5 py-1.5 text-sm">
                  {a.asset}
                  <span className={`ml-2 font-semibold ${d.cls}`}>{d.icon} {d.label}</span>
                  {a.range && <span className="ml-1.5 font-mono text-ink-2">{a.range}</span>}
                </li>
              );
            })}
          </ul>
        </div>
      )}

      <dl className="mt-4 space-y-3 border-t border-hairline pt-4 text-sm leading-relaxed">
        <div>
          <dt className="text-xs text-muted">市場反映了嗎</dt>
          <dd className="mt-1"><PricedIn text={it.priced_in} /></dd>
        </div>
        <div>
          <dt className="text-xs text-muted">可以考慮的配置方向</dt>
          <dd className="mt-1">{it.allocation}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted">這個判斷什麼時候失效</dt>
          <dd className="mt-1 text-ink-2">{it.invalidation}</dd>
        </div>
      </dl>
    </article>
  );
}

function Allocation({ result }: { result: AiResult }) {
  const alloc = result.allocation ?? {};
  const reasons = result.allocation_reasons ?? {};
  const rows = ALLOCATION.map((a) => ({ ...a, value: alloc[a.key] ?? 0 }));
  const total = rows.reduce((s, r) => s + r.value, 0) || 1;
  return (
    <div>
      <h3 className="font-semibold">今日目標資金配置</h3>
      {/* 100% 堆疊條：段與段之間留 2px 縫 */}
      <div className="mt-3 flex h-4 gap-0.5 overflow-hidden rounded" role="img" aria-label="資金配置比例">
        {rows.map((r) => r.value > 0 && <div key={r.key} style={{ width: `${(r.value / total) * 100}%`, background: r.color }} />)}
      </div>
      <ul className="mt-3 space-y-2">
        {rows.map((r) => (
          <li key={r.key} className="flex gap-2 text-sm">
            <span className="mt-1.5 h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: r.color }} />
            <div>
              <span className="font-semibold">{r.label}</span>
              <span className="ml-1.5 tabular-nums text-ink-2">{r.value}%</span>
              <p className="text-xs text-muted">{reasons[r.key] ?? r.fallback}</p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function AiPanel({ enabled }: { enabled: boolean }) {
  const [result, setResult] = useState<AiResult | null>(null);
  const [loading, setLoading] = useState(false);

  async function run() {
    setLoading(true);
    try {
      const res = await fetch("/api/ai", { method: "POST" });
      const body = await res.json();
      // 429 = 冷卻中 (FastAPI 的錯誤訊息放在 detail)
      setResult(res.ok ? body : { error: body.detail ?? body.error ?? `AI 服務錯誤 (${res.status})` });
    } catch (e) {
      setResult({ error: `無法連線到後端：${e}` });
    } finally {
      setLoading(false);
    }
  }

  if (!enabled) {
    return (
      <section className="glass rounded-2xl p-5 text-sm text-ink-2">
        🤖 尚未設定 GEMINI_API_KEY，AI 解盤功能停用。量化指標仍可正常查看。
      </section>
    );
  }

  return (
    <section className="glass rounded-2xl p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold">AI 解析報告</h2>
          <p className="mt-0.5 text-sm text-muted">總經階段、新聞影響分析、操作劇本與資金配置</p>
        </div>
        <button
          onClick={run}
          disabled={loading}
          className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-page transition-opacity hover:opacity-90 disabled:opacity-60"
        >
          {loading ? "解讀中，約需 30 秒…" : result ? "重新產生報告" : "產生今日 AI 報告"}
        </button>
      </div>

      {!result && !loading && (
        <p className="mt-2 text-sm text-muted">按下按鈕才會呼叫 AI，保護你的免費 API 額度。</p>
      )}

      {result && (
        <div className="mt-4 space-y-4">
          {result.error && <p className="rounded-lg bg-alert/10 px-3 py-2 text-sm text-alert">{result.error}</p>}
          {result.model && (
            <p className="text-xs text-muted">
              由 {result.model} 產生
              {result.generatedAt && `，${new Date(result.generatedAt).toLocaleTimeString("zh-TW", { timeZone: "Asia/Taipei", hour: "2-digit", minute: "2-digit", hour12: false })}`}
              {result.cached && "，與其他訪客共用同一份解析 (每次數據更新產生一次)"}
            </p>
          )}
          {result.phase && <p className="text-lg leading-relaxed">{result.phase}</p>}
          {result.liquidity && <p className="text-sm leading-relaxed text-ink-2">{result.liquidity}</p>}

          {(result.news_impacts?.length ?? 0) > 0 && (
            <div className="border-t border-hairline pt-5">
              <h3 className="font-semibold">新聞會怎麼影響市場</h3>
              <p className="mt-1 text-xs text-muted">AI 挑出最可能影響台股的新聞，拆成短期與長期影響、受影響的價格、是否已反映，以及判斷失效的條件。</p>
              <div className="mt-4 grid gap-4 xl:grid-cols-2">
                {result.news_impacts!.map((it) => <Impact key={it.event} it={it} sources={result.sources} />)}
              </div>
            </div>
          )}

          {(result.playbook || result.tech_hotspots) && (
            <div className="grid gap-6 border-t border-hairline pt-5 md:grid-cols-2">
              {result.playbook && (
                <div>
                  <h3 className="font-semibold">未來一到兩週的操作劇本</h3>
                  <p className="mt-2 text-sm leading-relaxed text-ink-2">{result.playbook}</p>
                </div>
              )}
              {result.tech_hotspots && (
                <div>
                  <h3 className="font-semibold">科技股熱點</h3>
                  <p className="mt-2 text-sm leading-relaxed text-ink-2">{result.tech_hotspots}</p>
                </div>
              )}
            </div>
          )}

          {result.allocation && (
            <div className="border-t border-hairline pt-5">
              <Allocation result={result} />
            </div>
          )}
        </div>
      )}
    </section>
  );
}
