import type { StockCheck } from "@/lib/types";

const num = (v: number | null | undefined, d = 1, suffix = "") =>
  v == null ? "—" : `${v.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d })}${suffix}`;
const signed = (v: number | null | undefined, d = 1, suffix = "%") => (v == null ? "—" : `${v > 0 ? "+" : ""}${num(v, d, suffix)}`);
const tone = (v: number | null | undefined, invert = false) =>
  v == null || Math.abs(v) < 0.05 ? "text-ink" : v > 0 !== invert ? "text-good" : "text-bad";

const STANCE = { 偏多: "border-good/50 bg-good/10 text-good", 中性: "border-warn/50 bg-warn/10 text-warn", 偏空: "border-bad/50 bg-bad/10 text-bad" } as const;

/** 3 個月價格情境：統計區間 (底色) + AI 悲觀 / 基本 / 樂觀 + 目前股價 */
function PriceRange({ p, ai }: { p: NonNullable<StockCheck["metrics"]["price"]>; ai: StockCheck["ai"] }) {
  const s = ai?.price_3m;
  const lo = Math.min(p.band90[0], s?.bear ?? Infinity) * 0.97;
  const hi = Math.max(p.band90[1], s?.bull ?? -Infinity) * 1.03;
  const x = (v: number) => `${((v - lo) / (hi - lo)) * 100}%`;
  const marks = s
    ? [
        { v: s.bear, label: "悲觀", cls: "bg-bad" },
        { v: s.base, label: "基本", cls: "bg-accent" },
        { v: s.bull, label: "樂觀", cls: "bg-good" },
      ]
    : [];
  return (
    <div>
      <div className="relative mt-8 h-3 rounded-full bg-neutral">
        <div className="absolute inset-y-0 rounded-full bg-accent/15" style={{ left: x(p.band90[0]), right: `calc(100% - ${x(p.band90[1])})` }} />
        <div className="absolute inset-y-0 rounded-full bg-accent/35" style={{ left: x(p.band68[0]), right: `calc(100% - ${x(p.band68[1])})` }} />
        {/* 目前股價 */}
        <div className="absolute -top-6 -translate-x-1/2 text-center" style={{ left: x(p.close) }}>
          <span className="whitespace-nowrap font-mono text-[11px] text-ink">現價 {num(p.close, 1)}</span>
        </div>
        <div className="absolute -top-1 bottom-[-4px] w-0.5 -translate-x-1/2 bg-ink" style={{ left: x(p.close) }} />
        {marks.map((m) => (
          <div key={m.label} className={`absolute top-1/2 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-surface ${m.cls}`} style={{ left: x(m.v) }} />
        ))}
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2 text-center text-xs">
        {marks.map((m) => (
          <div key={m.label} className="rounded-md bg-page/60 px-2 py-1.5">
            <span className="text-muted">{m.label}</span>
            <p className="font-mono text-base font-semibold">{num(m.v, 0)}</p>
            <span className={tone((m.v / p.close - 1) * 100)}>{signed((m.v / p.close - 1) * 100, 0)}</span>
          </div>
        ))}
      </div>
      <p className="mt-2 text-[11px] leading-relaxed text-muted">
        淺色底 = 統計上 3 個月後 90% 機率的區間 ({num(p.band90[0], 0)}～{num(p.band90[1], 0)})，深色底 = 68% 區間 ({num(p.band68[0], 0)}～{num(p.band68[1], 0)})；
        依這檔股票近 60 日的波動 (年化 {num(p.vol, 0, "%")}) 計算，假設不漲不跌只看波動。圓點是 AI 依基本面與大盤局勢給的情境。
      </p>
    </div>
  );
}

function Metric({ label, value, sub, cls = "text-ink" }: { label: string; value: string; sub?: string; cls?: string }) {
  return (
    <div className="rounded-lg bg-page/60 px-3 py-2">
      <p className="text-[11px] text-muted">{label}</p>
      <p className={`font-mono text-sm font-semibold ${cls}`}>{value}</p>
      {sub && <p className="text-[10px] text-muted">{sub}</p>}
    </div>
  );
}

function List({ title, items, icon }: { title: string; items?: string[]; icon: string }) {
  if (!items?.length) return null;
  return (
    <div>
      <p className="text-sm font-semibold">{title}</p>
      <ul className="mt-1.5 space-y-1 text-sm text-ink-2">
        {items.map((it) => (
          <li key={it} className="flex gap-2">
            <span>{icon}</span>
            <span>{it}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function StockCheckResult({ r }: { r: StockCheck }) {
  const { price: p, revenue: rev, income: inc, balance: bal, valuation: val, flows } = r.metrics;
  const ai = r.ai;
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h3 className="text-xl font-bold">
            {r.stock.name} <span className="font-mono text-base text-muted">{r.stock.id}</span>
          </h3>
          <p className="text-xs text-muted">
            {r.stock.industry}
            {p && ` · ${p.date} 收盤 ${num(p.close, 2)}`}
          </p>
        </div>
        {ai && <span className={`rounded-full border px-3 py-1 text-sm font-semibold ${STANCE[ai.stance] ?? STANCE["中性"]}`}>AI 觀點：{ai.stance}</span>}
      </div>

      {r.error && <p className="rounded-lg bg-warn/10 px-3 py-2 text-sm text-warn">⚠️ {r.error}</p>}
      {ai?.summary && <p className="rounded-lg border-l-4 border-accent bg-page/60 px-4 py-3 text-base">{ai.summary}</p>}

      {p && (
        <section>
          <p className="text-sm font-semibold">📈 3 個月股價情境</p>
          <PriceRange p={p} ai={ai} />
          {ai?.outsideBand && <p className="mt-1 text-xs text-warn">⚠️ AI 的基本情境明顯超出統計區間，請特別保守看待。</p>}
          {ai?.reasoning && <p className="mt-3 text-sm leading-relaxed text-ink-2">{ai.reasoning}</p>}
        </section>
      )}

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {p && <Metric label="近 1 月 / 3 月" value={`${signed(p.ret1m, 0)} / ${signed(p.ret3m, 0)}`} cls={tone(p.ret3m)} sub={`近 1 年 ${signed(p.ret1y, 0)}`} />}
        {p && <Metric label="距 200 日線" value={signed(p.ma200dev)} cls={tone(p.ma200dev)} sub={`52 週 ${num(p.low52, 0)}～${num(p.high52, 0)}`} />}
        {p && <Metric label="年化波動 / Beta" value={`${num(p.vol, 0, "%")} / ${num(p.beta, 2)}`} sub="Beta > 1 = 比大盤震盪" />}
        {rev && <Metric label={`月營收 ${rev.month}`} value={`${num(rev.latest, 2)} 億`} sub={`年增 ${signed(rev.yoy, 0)} · 今年累計 ${signed(rev.ytdYoy, 0)}`} cls={tone(rev.yoy)} />}
        {inc && <Metric label={`毛利率 (${inc.quarter.slice(0, 7)})`} value={num(inc.grossMargin, 1, "%")} sub={`去年同季 ${num(inc.grossMarginYearAgo, 1, "%")}`} cls={tone((inc.grossMargin ?? 0) - (inc.grossMarginYearAgo ?? inc.grossMargin ?? 0))} />}
        {inc && <Metric label="近四季 EPS" value={num(inc.epsTTM, 2)} sub={`前四季 ${num(inc.epsTTMPrev, 2)}`} cls={tone((inc.epsTTM ?? 0) - (inc.epsTTMPrev ?? inc.epsTTM ?? 0))} />}
        {val && <Metric label="本益比 / 位階" value={`${num(val.pe, 1)} 倍`} sub={`近 3 年位階 ${num(val.pePercentile, 0)} · 殖利率 ${num(val.dividendYield, 2, "%")}`} />}
        {bal && <Metric label="負債比 / 流動比" value={`${num(bal.debtRatio, 0, "%")} / ${num(bal.currentRatio, 0, "%")}`} sub={bal.cash != null ? `現金 ${num(bal.cash, 1)} 億` : undefined} />}
        {flows && <Metric label={`外資 ${flows.days} 日買賣超`} value={`${flows.foreign20d > 0 ? "+" : ""}${num(flows.foreign20d, 0)} 張`} cls={tone(flows.foreign20d)} sub={`投信 ${flows.trust20d > 0 ? "+" : ""}${num(flows.trust20d, 0)} 張`} />}
      </div>

      {ai && (
        <div className="grid gap-5 md:grid-cols-3">
          <List title="✅ 優勢" items={ai.strengths} icon="›" />
          <List title="⚠️ 目前的主要風險" items={ai.risks} icon="›" />
          <List title="🚀 可能的催化劑" items={ai.catalysts} icon="›" />
        </div>
      )}
      {ai?.valuation && <p className="text-sm text-ink-2"><b className="text-ink">估值：</b>{ai.valuation}</p>}
      {ai?.for_long_term_holder && (
        <p className="rounded-lg bg-accent/10 px-4 py-3 text-sm"><b>💼 給長期持有者：</b>{ai.for_long_term_holder}</p>
      )}

      <p className="border-t border-hairline pt-3 text-[11px] leading-relaxed text-muted">
        數據：FinMind (證交所 / 公開資訊觀測站) · 大盤：本站今日「{r.market?.label}」(機會 {r.market?.opportunity} / 風險 {r.market?.risk})
        {r.model && ` · AI：${r.model}`}
        {r.cached && " · 1 小時內有人查過，與其他訪客共用同一份分析"}
        <br />
        三個月股價為情境推估，不是預測保證，也不構成投資建議；個股風險遠高於大盤，請自行判斷並控制部位。
      </p>
    </div>
  );
}
