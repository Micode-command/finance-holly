"use client";

import { useState } from "react";

import type { RadarResult, RadarStock } from "@/lib/types";
import { type Access, buttonCls, postTool } from "./shared";
import { PlanLadder } from "./Technicals";

const num = (v: number | null | undefined, d = 0, s = "") =>
  v == null ? "—" : `${v.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d })}${s}`;
const signed = (v: number | null | undefined, d = 0, s = "%") => (v == null ? "—" : `${v > 0 ? "+" : ""}${num(v, d, s)}`);

function Funnel({ f }: { f: RadarResult["funnel"] }) {
  const steps = [
    { label: "流動性足夠的上市股", value: f.universe },
    { label: "營收創 12 個月新高", value: f.revHigh },
    { label: "＋ 成長在加速", value: f.accel },
    { label: "＋ 估值合理 (非陷阱)", value: f.passed },
  ];
  return (
    <ol className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      {steps.map((s, i) => (
        <li key={s.label} className={`rounded-lg px-3 py-2 ${i === steps.length - 1 ? "border border-accent/40 bg-accent/10" : "bg-page/60"}`}>
          <p className="font-mono text-lg font-semibold">{s.value}</p>
          <p className="text-[11px] text-muted">{i > 0 && "→ "}{s.label}</p>
        </li>
      ))}
    </ol>
  );
}

function StockCard({ s, onCheck }: { s: RadarStock; onCheck: (code: string) => void }) {
  const gapTone = s.fairGap == null ? "text-ink" : s.fairGap > 0 ? "text-up" : "text-flat";
  return (
    <article className="glass glass-hover flex flex-col gap-2 rounded-xl p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h4 className="font-semibold">{s.name.replace("*", "")} <span className="font-mono text-sm text-muted">{s.code}</span></h4>
          <p className="text-[11px] text-muted">{s.industry}{s.business && `，${s.business}`}</p>
        </div>
        {s.theme ? (
          <span className="shrink-0 rounded border border-accent/40 bg-accent/10 px-1.5 py-0.5 text-[11px] text-accent">{s.theme}</span>
        ) : s.indirectTheme ? (
          <span className="shrink-0 rounded border border-hairline px-1.5 py-0.5 text-[11px] text-muted">間接：{s.indirectTheme}</span>
        ) : null}
      </div>
      <dl className="grid grid-cols-3 gap-1.5 text-center">
        <div className="rounded-md bg-page/60 px-1 py-1.5">
          <dt className="text-[10px] text-muted">現價 → 合理價</dt>
          <dd className="font-mono text-xs font-semibold">{num(s.close)} → {num(s.fairPrice)}</dd>
          <dd className={`font-mono text-[11px] ${gapTone}`}>{s.fairGap != null && s.fairGap > 0 ? "低於合理價 " : "高於合理價 "}{num(Math.abs(s.fairGap ?? 0))}%</dd>
        </div>
        <div className="rounded-md bg-page/60 px-1 py-1.5">
          <dt className="text-[10px] text-muted">近 3 月營收年增</dt>
          <dd className="font-mono text-xs font-semibold text-good">{signed(s.yoy3)}</dd>
          <dd className="font-mono text-[11px] text-muted">加速 {signed(s.accel, 0, " 點")}</dd>
        </div>
        <div className="rounded-md bg-page/60 px-1 py-1.5">
          <dt className="text-[10px] text-muted">本益比 / 自己常態</dt>
          <dd className="font-mono text-xs font-semibold">{num(s.pe, 1)} / {num(s.normalPE, 1)}</dd>
          <dd className="font-mono text-[11px] text-muted">殖利率 {num(s.dividendYield, 1, "%")}</dd>
        </div>
      </dl>
      {s.why && s.theme && <p className="text-xs text-ink-2">{s.why}</p>}
      {s.inorganic && (
        <p className="rounded bg-warn/10 px-2 py-1 text-[11px] text-warn">⚠️ 營收成長含併購 / 新納入子公司，不完全是原本業務的需求成長</p>
      )}
      {s.note && <p className="text-[11px] text-muted">公司營收說明：{s.note.slice(0, 80)}</p>}
      {s.technicals && (
        <details className="group rounded-lg bg-page/50 px-3 py-2">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-2 text-sm">
            <span>
              交易計畫：進場 <span className="font-mono">{num(s.technicals.plan.entryLow, 1)}～{num(s.technicals.plan.entryHigh, 1)}</span>
            </span>
            <span className="text-xs text-muted">
              風險報酬比 <span className="font-mono text-sm text-ink">{s.technicals.plan.rr?.toFixed(1) ?? "—"}</span>
              <span className="ml-1 group-open:hidden">▾</span><span className="ml-1 hidden group-open:inline">▴</span>
            </span>
          </summary>
          <div className="mt-2 space-y-2">
            <PlanLadder plan={s.technicals.plan} close={s.close} compact />
            {s.case && <p className="text-xs leading-relaxed"><b>為何成立：</b>{s.case}</p>}
            {s.invalidation && <p className="text-xs leading-relaxed text-ink-2"><b className="text-ink">失效條件：</b>{s.invalidation}</p>}
            <ul className="space-y-0.5 text-xs text-muted">
              {s.technicals.readings.slice(0, 3).map((r) => <li key={r}>› {r}</li>)}
            </ul>
          </div>
        </details>
      )}
      <button onClick={() => onCheck(s.code)} className="mt-auto self-start rounded-lg border border-hairline px-3 py-1.5 text-sm text-ink-2 hover:border-accent hover:text-accent">
        深入健檢
      </button>
    </article>
  );
}

export default function RadarTool({ access, onCheck }: { access: Access; onCheck: (code: string) => void }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<RadarResult | null>(null);

  async function run() {
    if (!access.passcode.trim()) return setError("請先輸入上方的使用密碼。");
    setLoading(true);
    setError(null);
    const [body, err] = await postTool<RadarResult>("/api/radar", { passcode: access.passcode });
    setLoading(false);
    if (err || !body) return setError(err);
    access.remember();
    setResult(body);
  }

  const b = result?.backtest;
  return (
    <div className="space-y-4">
      <p className="text-xs text-muted">
        三層篩選：<b className="text-ink-2">新聞</b>找出需求升溫的技術趨勢 → <b className="text-ink-2">營收</b>證明需求真的來了 (創新高且加速) →
        <b className="text-ink-2"> EPS 合理價</b>排除太貴或便宜到可疑的股票。是「值得研究的候選名單」，不是買進推薦。
      </p>
      <button onClick={run} disabled={loading} className={buttonCls}>{loading ? "掃描中…" : "產生潛力股名單"}</button>
      {loading && <p className="text-sm text-ink-2">正在掃描全市場的營收與估值、計算前 12 檔的技術面，並請 AI 讀新聞歸納趨勢，大約 1 分鐘…</p>}
      {error && <p className="rounded-lg bg-alert/10 px-3 py-2 text-sm text-alert">{error}</p>}

      {result && !loading && (
        <div className="space-y-5">
          <p className="text-[11px] text-muted">
            營收資料 {result.revenueMonth}，價格 {result.priceDate && `${Number(result.priceDate.slice(0, 3)) + 1911}/${result.priceDate.slice(3, 5)}/${result.priceDate.slice(5)}`}
           ，名單每 6 小時更新一次{result.cached && "，這是與其他訪客共用的名單"}{result.model && `，AI：${result.model}`}
          </p>
          {result.error && <p className="rounded-lg bg-alert/10 px-3 py-2 text-sm text-alert">⚠️ {result.error}</p>}
          <Funnel f={result.funnel} />

          {b && (
            <div className="rounded-lg border border-hairline bg-page/60 px-4 py-3 text-sm text-ink-2">
              <p className="font-semibold text-ink">📊 這套條件近五年 ({b.period}) 的實際表現</p>
              <p className="mt-1">
                入選股票 3 個月後上漲 <b className="text-ink">{b.upProb}%</b> (全市場 {b.baseUpProb}%)、贏過一半股票 <b className="text-ink">{b.beatMedian}%</b>；
                平均報酬 <b className="text-ink">+{b.avgReturn}%</b> (全市場 +{b.baseAvgReturn}%)，但中位數只有 +{b.medianReturn}%。
              </p>
              <p className="mt-1 text-xs text-warn">
                ⚠️ 報酬集中在少數大贏家，大約一半的股票 3 個月後是下跌的 → 只買一檔很像賭博，建議分散 3 檔以上並控制部位。
                門檻是在同一段資料上決定的，未來實際表現可能較低。
              </p>
            </div>
          )}

          {result.themes.length > 0 && (
            <div>
              <p className="text-sm font-semibold">🔥 新聞中需求升溫的趨勢</p>
              <div className="mt-2 grid gap-3 md:grid-cols-2">
                {result.themes.map((t) => (
                  <div key={t.name} className="rounded-lg bg-page/60 p-3 text-sm">
                    <p className="font-semibold text-accent">{t.name}</p>
                    <p className="mt-1 text-xs text-ink-2">{t.demand}</p>
                    {t.watch && <p className="mt-1 text-xs text-muted">⚠️ {t.watch}</p>}
                  </div>
                ))}
              </div>
            </div>
          )}

          <div>
            <p className="text-sm font-semibold">🎯 候選股 ({result.stocks.length} 檔，與新聞趨勢直接相關的排前面)</p>
            {result.stocks.length === 0 ? (
              <p className="mt-2 text-sm text-ink-2">今天沒有股票同時符合三個條件。</p>
            ) : (
              <div className="mt-2 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {result.stocks.map((s) => <StockCard key={s.code} s={s} onCheck={onCheck} />)}
              </div>
            )}
          </div>

          <p className="border-t border-hairline pt-3 text-[11px] leading-relaxed text-muted">
            合理價 = 現價 × (自己過去 3 年本益比中位數 ÷ 現在本益比)，等於「近四季 EPS × 自己常態本益比」。公司業務與趨勢對應由 AI 判斷，
            對較小或新的公司可能不準，請以公司公告為準。資料：證交所、公開資訊觀測站。這不是投資建議。
          </p>
        </div>
      )}
    </div>
  );
}
