"use client";

import DOMPurify from "dompurify";
import { useState } from "react";

import type { AiResult } from "@/lib/types";

// 資金配置五類：固定顏色順序 (categorical slot 1-5)
const ALLOCATION = [
  { key: "twd_cash", label: "台幣存款", color: "var(--cat-1)", fallback: "防禦保命" },
  { key: "usd_assets", label: "外幣與公司債", color: "var(--cat-2)", fallback: "鎖利防禦" },
  { key: "cashflow", label: "月配息現金流", color: "var(--cat-3)", fallback: "震盪護城河" },
  { key: "core_growth", label: "核心股票", color: "var(--cat-4)", fallback: "資本攻擊" },
  { key: "tactical_hedge", label: "黃金與戰術", color: "var(--cat-5)", fallback: "黑天鵝防禦" },
];

/** AI 回傳的是 HTML，顯示前一律消毒 */
function SafeHtml({ html }: { html: string }) {
  return <div className="ai-html text-sm text-ink-2" dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(html) }} />;
}

function Allocation({ result }: { result: AiResult }) {
  const alloc = result.allocation_recommendation ?? {};
  const reasons = result.allocation_reasons ?? {};
  const rows = ALLOCATION.map((a) => ({ ...a, value: alloc[a.key] ?? 0 }));
  const total = rows.reduce((s, r) => s + r.value, 0) || 1;
  return (
    <div>
      <h3 className="font-semibold">🛡️ 今日目標資金配置</h3>
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
        <h2 className="text-lg font-bold">🎙️ 荷莉 AI 總經解析</h2>
        <button
          onClick={run}
          disabled={loading}
          className="rounded-lg bg-gradient-to-r from-accent to-accent-2 px-4 py-2 text-sm font-semibold text-page shadow-[0_0_24px_-6px_var(--accent)] transition-opacity hover:opacity-90 disabled:opacity-60"
        >
          {loading ? "🤖 解讀中，約需 20 秒…" : result ? "🔄 重新解讀" : "🤖 生成今日 AI 深度解盤"}
        </button>
      </div>

      {!result && !loading && (
        <p className="mt-2 text-sm text-muted">按下按鈕才會呼叫 AI，保護你的免費 API 額度。</p>
      )}

      {result && (
        <div className="mt-4 space-y-4">
          {result.error && <p className="rounded-lg bg-bad/10 px-3 py-2 text-sm text-bad">{result.error}</p>}
          {result.model && (
            <p className="font-mono text-[11px] text-muted">
              由 {result.model} 產生
              {result.generatedAt && ` · ${new Date(result.generatedAt).toLocaleTimeString("zh-TW", { timeZone: "Asia/Taipei", hour: "2-digit", minute: "2-digit", hour12: false })}`}
              {result.cached && " · 與其他訪客共用同一份解析 (每次數據更新產生一次)"}
            </p>
          )}
          {result.macro_phase_insight && (
            <p className="rounded-lg border-l-4 border-accent bg-page/70 px-4 py-3 text-sm leading-relaxed">{result.macro_phase_insight}</p>
          )}
          {result.broadcast && <SafeHtml html={result.broadcast} />}
          {result.market_insights_html && (
            <div className="grid gap-6 border-t border-hairline pt-4 lg:grid-cols-[1fr_1.8fr]">
              <Allocation result={result} />
              <SafeHtml html={result.market_insights_html} />
            </div>
          )}
        </div>
      )}
    </section>
  );
}
