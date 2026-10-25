import type { Card, Dashboard, NewsItem, Stance, Vital } from "@/lib/types";
import MacroCommentary from "./MacroCommentary";
import MarketPulse from "./MarketPulse";
import RefreshButton from "./RefreshButton";
import RiskMap from "./RiskMap";

// 台股慣例：加碼 = 紅 (偏多)、減碼 = 綠 (偏空)、維持 = 黃
export const STANCE = {
  defensive: { text: "text-down", label: "減碼" },
  neutral: { text: "text-flat", label: "維持" },
  offensive: { text: "text-up", label: "加碼" },
} satisfies Record<Stance, object>;

function fmtVital(v: Vital) {
  const n = v.value.toLocaleString("en-US", { minimumFractionDigits: v.decimals, maximumFractionDigits: v.decimals });
  return `${v.prefix}${n}${v.suffix}`;
}

/** 報價看板慣例：漲紅、跌綠、平盤黃 (只看方向，不判斷好壞) */
function VitalChange({ v }: { v: Vital }) {
  const cls = v.change > 0 ? "text-up" : v.change < 0 ? "text-down" : "text-flat";
  const unit = v.changeMode === "pct" ? "%" : " 百分點";
  return (
    <span className={`font-mono text-xs ${cls}`}>
      {v.change > 0 ? "▲" : v.change < 0 ? "▼" : "■"} {v.change > 0 ? "+" : ""}
      {v.change.toFixed(2)}
      {unit}
    </span>
  );
}

/** 跑馬燈：內容複製一份接在後面，translateX(-50%) 無縫循環 */
function Ticker({ vitals }: { vitals: Vital[] }) {
  const row = vitals.map((v) => (
    <span key={v.id} className="inline-flex items-center gap-2 px-5">
      <span className="text-muted">{v.label}</span>
      <span className="font-mono text-ink">{fmtVital(v)}</span>
      <VitalChange v={v} />
    </span>
  ));
  return (
    <div className="overflow-hidden border-y border-hairline bg-page/60 py-2 text-sm" aria-hidden>
      <div className="marquee flex w-max whitespace-nowrap">
        {row}
        {row}
      </div>
    </div>
  );
}

function RegimeBar({ regime }: { regime: Dashboard["regime"] }) {
  const parts = [
    { label: "低波動", value: regime.Forecast_Prob_Low_Vol, color: "var(--accent)" },
    { label: "高波動", value: regime.Forecast_Prob_High_Vol, color: "var(--serious)" },
    { label: "黑天鵝", value: regime.Forecast_Prob_Black_Swan, color: "var(--alert)" },
  ];
  return (
    <div>
      <p className="text-xs text-muted">未來一週市場體制機率</p>
      <div className="mt-2 flex h-2 gap-0.5 overflow-hidden rounded-full">
        {parts.map((p) => <div key={p.label} style={{ width: `${p.value}%`, background: p.color }} />)}
      </div>
      <div className="mt-1.5 flex justify-between text-xs">
        {parts.map((p) => (
          <span key={p.label} className="text-ink-2">
            <span className="mr-1 inline-block h-2 w-2 rounded-sm" style={{ background: p.color }} />
            {p.label} <span className="font-mono text-ink">{p.value}%</span>
          </span>
        ))}
      </div>
    </div>
  );
}

function newsTime(iso: string | null) {
  if (!iso) return "";
  return new Date(iso).toLocaleString("zh-TW", { timeZone: "Asia/Taipei", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false });
}

function NewsPanel({ news }: { news: NewsItem[] }) {
  return (
    <div className="glass flex h-full flex-col rounded-2xl p-5">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold">📰 影響股市的新聞時事</h2>
      </div>
      {news.length === 0 ? (
        <p className="mt-4 text-sm text-muted">目前沒有抓到與股市相關的新聞。</p>
      ) : (
        <ul className="mt-3 divide-y divide-hairline">
          {news.map((n) => (
            <li key={n.link || n.title} className="py-3">
              <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
                {n.topics.map((t) => (
                  <span key={t} className="rounded bg-surface-2 px-1.5 py-0.5 text-ink-2">{t}</span>
                ))}
                <span className="ml-auto font-mono text-muted">{newsTime(n.published)}</span>
              </div>
              <a href={n.link} target="_blank" rel="noopener noreferrer" className="mt-1.5 block text-sm leading-snug text-ink hover:text-accent">
                {n.title}
              </a>
              {n.related.length > 0 && (
                <p className="mt-1 text-[11px] text-muted">
                  連動指標：
                  {n.related.map((r, i) => (
                    <span key={r.id}>
                      {i > 0 && "、"}
                      <a href={`#card-${r.id}`} className="text-ink-2 underline decoration-hairline underline-offset-2 hover:text-accent">{r.label}</a>
                    </span>
                  ))}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
      <p className="mt-auto pt-2 text-[11px] text-muted">來源：{news[0]?.source ?? "Yahoo奇摩股市"}，依關鍵字自動分類。每則新聞的影響分析在下方「AI 解析」。</p>
    </div>
  );
}

/** 背景：加權指數近 3 年走勢的大剪影，捲動時比前景慢 (視差) */
function TaiexSilhouette({ card }: { card?: Card }) {
  const s = card?.series ?? [];
  if (s.length < 10) return null;
  const vals = s.map((p) => p[1]);
  const lo = Math.min(...vals), hi = Math.max(...vals);
  const d = vals.map((v, i) => `${i ? "L" : "M"}${((i / (vals.length - 1)) * 1000).toFixed(1)},${(300 - ((v - lo) / (hi - lo || 1)) * 240).toFixed(1)}`).join("");
  return (
    <svg viewBox="0 0 1000 320" preserveAspectRatio="none" className="parallax absolute inset-x-0 top-24 h-[70%] w-full"
      style={{ "--depth": 0.3 } as React.CSSProperties} aria-hidden>
      <path d={`${d}L1000,320L0,320Z`} fill="var(--accent)" fillOpacity={0.035} />
      <path d={d} fill="none" stroke="var(--accent)" strokeOpacity={0.12} strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

export default function Hero({ data }: { data: Dashboard }) {
  const v = data.verdict;
  const s = STANCE[v.stance];
  const taiex = data.sections.flatMap((x) => x.cards).find((c) => c.id === "TAIEX");

  return (
    <header className="relative isolate overflow-hidden">
      <div className="pointer-events-none absolute inset-0 -z-10">
        <TaiexSilhouette card={taiex} />
      </div>

      <Ticker vitals={data.vitals} />

      <div className="mx-auto max-w-[1400px] px-4 pb-14 pt-6 sm:px-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h1 className="text-xl font-bold sm:text-2xl">荷莉總經觀測站</h1>
          <div className="flex items-center gap-3 text-sm text-muted">
            <span>數據更新 <span className="font-mono">{data.asOf}</span></span>
            <RefreshButton />
          </div>
        </div>

        {/* 今日結論 + 機會 × 風險 地圖 */}
        <section className="mt-8 grid items-center gap-8 lg:grid-cols-12" aria-label="今日市場狀態">
          <div className="load-rise min-w-0 lg:col-span-5">
            <p className="text-sm text-ink-2">今天的建議</p>
            <p className={`mt-1 text-7xl font-black leading-none tracking-tight sm:text-8xl ${s.text}`}>{v.label}</p>
            <p className="mt-4 text-xl font-semibold leading-snug sm:text-2xl">{v.headline}</p>
            {data.scores && (
              <dl className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-3">
                <div>
                  <dt className="text-xs text-muted"><a href="#term-opportunity_score" className="hover:text-accent">3 個月機會</a></dt>
                  <dd className="font-mono text-4xl font-semibold">{data.scores.opportunity}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted"><a href="#term-risk_score" className="hover:text-accent">風險溫度</a></dt>
                  <dd className={`font-mono text-4xl font-semibold ${data.scores.risk >= 65 ? "text-serious" : ""}`}>{data.scores.risk}</dd>
                </div>
                {data.scores.odds && (
                  <div className="col-span-2 sm:col-span-1">
                    <dt className="text-xs text-muted">類似分數 3 個月後上漲</dt>
                    <dd className="font-mono text-4xl font-semibold">{data.scores.odds.upProb}%</dd>
                    <dd className="text-xs text-muted">平常是 {data.scores.odds.baseUpProb}%</dd>
                  </div>
                )}
              </dl>
            )}
            <div className="mt-6">
              <p className="text-sm text-muted">今天怎麼做</p>
              <ul className="mt-2 space-y-1.5">
                {v.actions.map((a) => (
                  <li key={a} className="flex gap-2 text-sm leading-relaxed">
                    <span className={`mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-current ${s.text}`} />
                    {a}
                  </li>
                ))}
              </ul>
            </div>
          </div>
          <div className="min-w-0 lg:col-span-7">
            {data.scores && <RiskMap scores={data.scores} stance={v.stance} />}
          </div>
        </section>

        <div className="mt-10">
          <MarketPulse news={data.news.slice(0, 3)} />
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-12">
          <div className="glass min-w-0 rounded-2xl p-5 sm:p-6 lg:col-span-7">
            <h2 className="font-semibold">關鍵原因</h2>
            <ul className="mt-3 space-y-2">
              {v.drivers.slice(0, 5).map((d) => (
                <li key={d.text} className="flex gap-2 text-sm leading-relaxed">
                  <span className={`shrink-0 whitespace-nowrap ${d.tone === "bad" ? "text-down" : "text-up"}`}>{d.tone === "bad" ? "▼ 利空" : "▲ 利多"}</span>
                  <span className="text-ink-2">{d.text}</span>
                </li>
              ))}
              {v.drivers.length === 0 && <li className="text-sm text-ink-2">各項指標多在常態區間</li>}
            </ul>
            <div className="mt-6 border-t border-hairline pt-5">
              <RegimeBar regime={data.regime} />
            </div>
            <div className="mt-6 border-t border-hairline pt-5">
              <MacroCommentary notes={data.macro} />
            </div>
          </div>
          <div className="min-w-0 lg:col-span-5">
            <NewsPanel news={data.news} />
          </div>
        </div>

        {/* 關鍵數字 (看板列) */}
        <dl className="mt-6 grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-hairline bg-hairline sm:grid-cols-4 xl:grid-cols-8">
          {data.vitals.map((vt) => (
            <div key={vt.id} className="bg-surface px-3 py-2.5">
              <dt className="text-xs text-muted">{vt.label}</dt>
              <dd className="mt-0.5 font-mono text-xl font-semibold">{fmtVital(vt)}</dd>
              <dd><VitalChange v={vt} /></dd>
            </div>
          ))}
        </dl>
      </div>
    </header>
  );
}
