import type { Dashboard, NewsItem, Stance, Vital } from "@/lib/types";
import MacroCommentary from "./MacroCommentary";
import MarketPulse from "./MarketPulse";
import RefreshButton from "./RefreshButton";

export const STANCE = {
  defensive: { icon: "🛡️", text: "text-bad", glow: "rgba(248,113,113,0.35)", ring: "var(--bad)", tag: "TRIM · 減碼" },
  neutral: { icon: "⚖️", text: "text-warn", glow: "rgba(251,191,36,0.28)", ring: "var(--warn)", tag: "HOLD · 維持" },
  offensive: { icon: "🚀", text: "text-good", glow: "rgba(52,211,153,0.32)", ring: "var(--good)", tag: "ADD · 加碼" },
} satisfies Record<Stance, object>;

function fmtVital(v: Vital) {
  const n = v.value.toLocaleString("en-US", { minimumFractionDigits: v.decimals, maximumFractionDigits: v.decimals });
  return `${v.prefix}${n}${v.suffix}`;
}

function VitalChange({ v }: { v: Vital }) {
  const good = v.change === 0 ? null : v.change > 0 !== v.invertColor;
  const cls = good == null ? "text-muted" : good ? "text-good" : "text-bad";
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

/** 健康度環形儀表 */
function Gauge({ score, color, label, term }: { score: number; color: string; label: string; term: string }) {
  const r = 52;
  const c = 2 * Math.PI * r;
  return (
    <div className="relative h-32 w-32 shrink-0" role="img" aria-label={`${label} ${score} 分`}>
      <svg viewBox="0 0 120 120" className="h-full w-full -rotate-90">
        <circle cx="60" cy="60" r={r} fill="none" stroke="var(--neutral)" strokeWidth="8" />
        <circle
          cx="60" cy="60" r={r} fill="none" stroke={color} strokeWidth="8" strokeLinecap="round"
          strokeDasharray={`${(Math.max(score, 1.5) / 100) * c} ${c}`}
          style={{ filter: `drop-shadow(0 0 6px ${color})` }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-mono text-4xl font-bold">{score}</span>
        <a href={`#term-${term}`} className="text-[11px] text-muted hover:text-accent">{label}</a>
      </div>
    </div>
  );
}

function RegimeBar({ regime }: { regime: Dashboard["regime"] }) {
  const parts = [
    { label: "低波動", value: regime.Forecast_Prob_Low_Vol, color: "var(--good)" },
    { label: "高波動", value: regime.Forecast_Prob_High_Vol, color: "var(--warn)" },
    { label: "黑天鵝", value: regime.Forecast_Prob_Black_Swan, color: "var(--bad)" },
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
        <span className="font-mono text-[10px] tracking-widest text-muted">LIVE FEED</span>
      </div>
      {news.length === 0 ? (
        <p className="mt-4 text-sm text-muted">目前沒有抓到與股市相關的新聞。</p>
      ) : (
        <ul className="mt-3 divide-y divide-hairline">
          {news.map((n) => (
            <li key={n.link || n.title} className="py-3">
              <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
                {n.topics.map((t) => (
                  <span key={t} className="rounded border border-accent/30 bg-accent/10 px-1.5 py-0.5 text-accent">{t}</span>
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
      <p className="mt-auto pt-2 text-[10px] text-muted">來源：{news[0]?.source ?? "Yahoo奇摩股市"} · 依關鍵字自動分類</p>
    </div>
  );
}

export default function Hero({ data }: { data: Dashboard }) {
  const v = data.verdict;
  const s = STANCE[v.stance];

  return (
    <header className="relative isolate overflow-hidden">
      {/* 視差背景：越遠的層移動越慢 */}
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="parallax grid-bg absolute inset-0" style={{ "--depth": 0.15 } as React.CSSProperties} />
        <div
          className="parallax absolute -top-40 left-1/2 h-[42rem] w-[42rem] -translate-x-1/2 rounded-full blur-3xl"
          style={{ "--depth": 0.35, background: `radial-gradient(circle, ${s.glow}, transparent 65%)` } as React.CSSProperties}
        />
        <div
          className="parallax absolute top-1/3 -right-40 h-[28rem] w-[28rem] rounded-full blur-3xl"
          style={{ "--depth": 0.55, background: "radial-gradient(circle, rgba(139,92,246,0.22), transparent 65%)" } as React.CSSProperties}
        />
        <div className="parallax grid-floor absolute inset-x-[-50%] bottom-[-35%] h-[70%]" style={{ "--depth": -0.12 } as React.CSSProperties} />
      </div>

      <Ticker vitals={data.vitals} />

      <div className="mx-auto max-w-[1400px] px-4 pb-14 pt-8 sm:px-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="font-mono text-xs tracking-[0.3em] text-accent">HOLLY · MACRO TERMINAL</p>
            <h1 className="mt-1 text-2xl font-bold sm:text-3xl">荷莉總經觀測站</h1>
          </div>
          <div className="flex items-center gap-3 text-sm text-muted">
            <span className="font-mono">數據更新 {data.asOf}</span>
            <RefreshButton />
          </div>
        </div>

        <div className="mt-6">
          <MarketPulse news={data.news.slice(0, 3)} />
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-12">
          {/* 左：今日結論 */}
          <div className="glass relative overflow-hidden rounded-3xl p-6 sm:p-8 lg:col-span-7">
            <div className="scanline pointer-events-none absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-transparent via-accent/5 to-transparent" />
            <p className="font-mono text-xs tracking-[0.25em] text-muted">今日市場狀態 · {s.tag}</p>
            <div className="mt-3 flex flex-wrap items-center gap-6">
              <div className="min-w-0 flex-1">
                <p className={`glow-text text-6xl font-black sm:text-7xl ${s.text}`}>
                  {s.icon} {v.label}
                </p>
                <p className="mt-3 text-xl font-semibold sm:text-2xl">{v.headline}</p>
                {data.scores?.odds && (
                  <p className="mt-2 text-sm text-ink-2">
                    📊 歷史上類似分數，3 個月後台股上漲機率 <b className="font-mono text-ink">{data.scores.odds.upProb}%</b>
                    <span className="text-muted">（平常是 {data.scores.odds.baseUpProb}%）</span>
                  </p>
                )}
              </div>
              {data.scores && (
                <div className="flex gap-3">
                  <Gauge score={data.scores.opportunity} color={s.ring} label="3 個月機會" term="opportunity_score" />
                  <Gauge score={data.scores.risk} color={data.scores.risk >= 65 ? "var(--bad)" : data.scores.risk >= 35 ? "var(--warn)" : "var(--good)"} label="風險溫度" term="risk_score" />
                </div>
              )}
            </div>

            <div className="mt-6 grid gap-5 sm:grid-cols-2">
              <div>
                <p className="text-xs text-muted">今天怎麼做</p>
                <ol className="mt-2 space-y-1.5">
                  {v.actions.map((a, i) => (
                    <li key={a} className="flex gap-2 text-sm">
                      <span className={`font-mono ${s.text}`}>0{i + 1}</span>
                      {a}
                    </li>
                  ))}
                </ol>
              </div>
              <div>
                <p className="text-xs text-muted">關鍵原因</p>
                <ul className="mt-2 space-y-1.5">
                  {v.drivers.slice(0, 4).map((d) => (
                    <li key={d.text} className="flex gap-2 text-sm">
                      <span className={d.tone === "bad" ? "text-bad" : "text-good"}>{d.tone === "bad" ? "▼" : "▲"}</span>
                      <span className="text-ink-2">{d.text}</span>
                    </li>
                  ))}
                  {v.drivers.length === 0 && <li className="text-sm text-ink-2">各項指標多在常態區間</li>}
                </ul>
              </div>
            </div>

            <div className="mt-6 border-t border-hairline pt-5">
              <RegimeBar regime={data.regime} />
            </div>

            <div className="mt-6 border-t border-hairline pt-5">
              <MacroCommentary notes={data.macro} />
            </div>
          </div>

          {/* 右：新聞時事 */}
          <div className="lg:col-span-5">
            <NewsPanel news={data.news} />
          </div>
        </div>

        {/* 關鍵數字 */}
        <dl className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4 xl:grid-cols-8">
          {data.vitals.map((vt) => (
            <div key={vt.id} className="glass rounded-xl px-3 py-2.5">
              <dt className="text-[11px] text-muted">{vt.label}</dt>
              <dd className="mt-0.5 font-mono text-lg font-semibold">{fmtVital(vt)}</dd>
              <dd><VitalChange v={vt} /></dd>
            </div>
          ))}
        </dl>

        <a href="#nav" className="mx-auto mt-10 flex w-fit flex-col items-center gap-1 text-xs text-muted hover:text-accent">
          向下捲動看完整分析
          <span className="animate-bounce">↓</span>
        </a>
      </div>
    </header>
  );
}
