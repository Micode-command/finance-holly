import type { PortfolioCheck } from "@/lib/types";

const num = (v: number | null | undefined, d = 1, s = "") =>
  v == null ? "—" : `${v.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d })}${s}`;
const signed = (v: number | null | undefined, d = 0, s = "%") => (v == null ? "—" : `${v > 0 ? "+" : ""}${num(v, d, s)}`);
const tone = (v: number | null | undefined) => (v == null || Math.abs(v) < 0.05 ? "text-ink" : v > 0 ? "text-good" : "text-bad");
const RISK = { 低: "border-good/50 bg-good/10 text-good", 中: "border-warn/50 bg-warn/10 text-warn", 高: "border-bad/50 bg-bad/10 text-bad" } as Record<string, string>;
const ACTION = (a: string) => (/加碼|新增/.test(a) ? "bg-good/15 text-good" : /減碼|出清/.test(a) ? "bg-bad/15 text-bad" : "bg-neutral text-ink-2");

function Tile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-lg bg-page/60 px-3 py-2">
      <p className="text-[11px] text-muted">{label}</p>
      <p className="font-mono text-sm font-semibold">{value}</p>
      {sub && <p className="text-[10px] text-muted">{sub}</p>}
    </div>
  );
}

/** 目前 vs 建議比重：每一列兩條橫條 (灰 = 目前、亮 = 建議)，不靠顏色區分持股 */
function WeightBars({ rows }: { rows: NonNullable<PortfolioCheck["ai"]>["suggested_weights"] }) {
  const max = Math.max(...rows.flatMap((r) => [r.current, r.suggested]), 1);
  return (
    <div className="space-y-3">
      <div className="flex gap-4 text-[11px] text-muted">
        <span><span className="mr-1 inline-block h-2 w-3 rounded-sm bg-muted/50" />目前</span>
        <span><span className="mr-1 inline-block h-2 w-3 rounded-sm bg-accent" />建議</span>
      </div>
      {rows.map((r) => {
        const delta = r.suggested - r.current;
        return (
          <div key={r.name}>
            <div className="flex items-baseline justify-between gap-2 text-sm">
              <span className="truncate">{r.name}</span>
              <span className="shrink-0 font-mono text-xs">
                {num(r.current, 0, "%")} → <b>{num(r.suggested, 0, "%")}</b>
                <span className={`ml-1.5 ${Math.abs(delta) < 0.5 ? "text-muted" : delta > 0 ? "text-good" : "text-bad"}`}>
                  {Math.abs(delta) < 0.5 ? "維持" : `${delta > 0 ? "▲" : "▼"} ${num(Math.abs(delta), 0)}`}
                </span>
              </span>
            </div>
            <div className="mt-1 space-y-0.5">
              <div className="h-1.5 rounded-full bg-muted/50" style={{ width: `${(r.current / max) * 100}%` }} />
              <div className="h-1.5 rounded-full bg-accent" style={{ width: `${(r.suggested / max) * 100}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function PortfolioResult({ r }: { r: PortfolioCheck }) {
  const m = r.metrics;
  const ai = r.ai;
  const check = ai?.stanceCheck;
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-xl font-bold">💼 配置健檢結果</h3>
        {ai?.risk_level && <span className={`rounded-full border px-3 py-1 text-sm font-semibold ${RISK[ai.risk_level] ?? RISK["中"]}`}>整體風險：{ai.risk_level}</span>}
      </div>
      {r.error && <p className="rounded-lg bg-warn/10 px-3 py-2 text-sm text-warn">⚠️ {r.error}</p>}
      {ai?.summary && <p className="rounded-lg border-l-4 border-accent bg-page/60 px-4 py-3 text-base">{ai.summary}</p>}

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
        <Tile label="股票類 / 債券 / 現金" value={`${num(m.stockLike, 0)} / ${num(m.bond, 0)} / ${num(m.cash, 0)}`} sub="單位 %" />
        <Tile label="最大單一持股" value={num(m.topHolding.weight, 0, "%")} sub={m.topHolding.name} />
        <Tile label="有效持股數" value={num(m.effectiveN, 1, " 檔")} sub="越接近實際檔數 = 越分散" />
        <Tile label="組合 Beta" value={num(m.beta, 2)} sub="1 = 跟大盤一樣震盪 (含現金)" />
        <Tile label="平均年化波動" value={num(m.avgVol, 0, "%")} />
        <Tile label="持股加權殖利率" value={num(m.dividendYield, 2, "%")} sub="近 12 個月實際配息" />
      </div>

      {ai?.fit_with_market && (
        <p className="text-sm text-ink-2">
          <b className="text-ink">和今日大盤局勢 ({r.market?.label}) 的關係：</b>{ai.fit_with_market}
        </p>
      )}
      {check && !check.ok && (
        <p className="rounded-lg bg-warn/10 px-3 py-2 text-sm text-warn">
          ⚠️ AI 建議股票類比重調整 {signed(check.change)} 個百分點，超出本站今日「{r.market?.label}」建議的 {signed(check.allowed[0])}～{signed(check.allowed[1])}，請保守看待、分批執行。
        </p>
      )}

      {ai?.suggested_weights?.length ? (
        <section className="grid gap-6 lg:grid-cols-2">
          <div>
            <p className="mb-3 text-sm font-semibold">📊 目前 → 建議比重</p>
            <WeightBars rows={ai.suggested_weights} />
          </div>
          <div className="space-y-2">
            <p className="text-sm font-semibold">🛠️ 具體調整</p>
            {ai.suggestions?.map((s, i) => (
              <div key={i} className="flex gap-2 text-sm">
                <span className={`h-fit shrink-0 rounded px-1.5 py-0.5 text-xs font-semibold ${ACTION(s.action)}`}>{s.action}</span>
                <span><b>{s.target}</b>：<span className="text-ink-2">{s.detail}</span></span>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {ai && (
        <div className="grid gap-5 md:grid-cols-3">
          {[["✅ 做得好的地方", ai.strengths], ["⚠️ 需要注意的問題", ai.issues], ["🗓️ 接下來 1～3 個月", ai.next_steps]].map(([title, items]) =>
            (items as string[] | undefined)?.length ? (
              <div key={title as string}>
                <p className="text-sm font-semibold">{title as string}</p>
                <ul className="mt-1.5 space-y-1 text-sm text-ink-2">
                  {(items as string[]).map((it) => <li key={it} className="flex gap-2"><span>›</span><span>{it}</span></li>)}
                </ul>
              </div>
            ) : null,
          )}
        </div>
      )}

      <details className="text-sm">
        <summary className="cursor-pointer text-muted hover:text-ink-2">▸ 每檔持股的數據</summary>
        <div className="mt-2 overflow-x-auto">
          <table className="w-full min-w-[560px] text-left text-xs">
            <thead className="text-muted">
              <tr>{["持股", "比重", "近 3 月", "近 1 年", "年化波動", "Beta", "殖利率"].map((h) => <th key={h} className="py-1.5 pr-3 font-normal">{h}</th>)}</tr>
            </thead>
            <tbody className="font-mono">
              {r.holdings.map((h) => (
                <tr key={h.id} className="border-t border-hairline">
                  <td className="py-1.5 pr-3 font-sans">{h.name} <span className="text-muted">{h.id}</span>{h.isBond && <span className="ml-1 text-[10px] text-accent">債券</span>}</td>
                  <td className="pr-3">{num(h.weight, 0, "%")}</td>
                  <td className={`pr-3 ${tone(h.ret3m)}`}>{signed(h.ret3m)}</td>
                  <td className={`pr-3 ${tone(h.ret1y)}`}>{signed(h.ret1y)}</td>
                  <td className="pr-3">{num(h.vol, 0, "%")}</td>
                  <td className="pr-3">{num(h.beta, 2)}</td>
                  <td>{num(h.dividendYield, 2, "%")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>

      <p className="border-t border-hairline pt-3 text-[11px] leading-relaxed text-muted">
        你輸入的持股只用於這次分析，不會被儲存或分享。大盤：本站今日「{r.market?.label}」(機會 {r.market?.opportunity} / 風險 {r.market?.risk})
        {r.model && ` · AI：${r.model}`}
        <br />
        這是依公開數據產生的一般性建議，不是個人化投資顧問服務；實際調整前請考量自己的資金需求、稅負與交易成本。
      </p>
    </div>
  );
}
