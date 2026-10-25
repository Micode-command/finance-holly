import type { MarketScores, ScoreFactor } from "@/lib/types";
import ScoreHistoryChart from "./ScoreHistoryChart";
import TermLink from "./TermLink";

function FactorRow({ f, tone }: { f: ScoreFactor; tone: "opp" | "risk" }) {
  // 機會：分數高 = 好 (綠)；風險：分數高 = 危險 (紅)
  const high = f.score >= 65;
  const low = f.score <= 35;
  const color = tone === "opp" ? (high ? "var(--good)" : low ? "var(--bad)" : "var(--muted)") : high ? "var(--bad)" : low ? "var(--good)" : "var(--muted)";
  return (
    <li>
      <div className="flex items-baseline justify-between gap-2 text-sm">
        <span className="text-ink">{f.label}</span>
        <span className="font-mono text-xs text-ink-2">
          {f.value}，<span className="text-ink">{f.score}</span>
        </span>
      </div>
      <div className="mt-1 h-1.5 rounded-full bg-neutral">
        <div className="h-full rounded-full" style={{ width: `${Math.max(3, f.score)}%`, background: color }} />
      </div>
      <p className="mt-1 text-[11px] text-muted">{f.why}</p>
    </li>
  );
}

function Panel({ title, term, score, change, factors, tone, children }: {
  title: string; term: string; score: number; change: number; factors: ScoreFactor[]; tone: "opp" | "risk"; children?: React.ReactNode;
}) {
  return (
    <div className="glass rounded-2xl p-5">
      <div className="flex items-baseline justify-between">
        <h3 className="font-semibold"><TermLink id={term}>{title}</TermLink></h3>
        <span className="font-mono">
          <span className="text-3xl font-bold">{score}</span>
          <span className={`ml-2 text-xs ${change === 0 ? "text-muted" : (change > 0) === (tone === "opp") ? "text-good" : "text-bad"}`}>
            {change > 0 ? "▲" : change < 0 ? "▼" : "■"} {change > 0 ? "+" : ""}{change} / 週
          </span>
        </span>
      </div>
      {children}
      <ul className="mt-4 space-y-3">
        {factors.map((f) => <FactorRow key={f.key} f={f} tone={tone} />)}
      </ul>
    </div>
  );
}

/** 雙分數拆解：每個因子各自打幾分、為什麼 */
export default function ScoreBreakdown({ scores }: { scores: MarketScores | null }) {
  if (!scores) {
    return <p className="glass rounded-2xl p-5 text-sm text-ink-2">分數需要至少 3 個因子的數據，目前數據不足。</p>;
  }
  const odds = scores.odds;
  return (
    <section>
      <h2 className="text-2xl font-bold">🧭 台股雙分數拆解</h2>
      <p className="mt-1 text-sm text-ink-2">
        每個因子都換算成「今天在過去 3 年排第幾」(0～100)，再平均成分數。條越長 = 對該分數貢獻越大。
      </p>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Panel title="3 個月機會分數" term="opportunity_score" score={scores.opportunity} change={scores.opportunity_change_5d}
          factors={scores.opportunity_details} tone="opp">
          {odds && (
            <p className="mt-2 rounded-md bg-page/70 px-3 py-2 text-sm text-ink-2">
              📊 過去 10 年分數在 <b className="text-ink">{odds.range}</b> 之間的 {odds.days} 個交易日，3 個月後台股上漲機率{" "}
              <b className="text-ink">{odds.upProb}%</b>、平均報酬 <b className="text-ink">{odds.avgReturn > 0 ? "+" : ""}{odds.avgReturn}%</b>
              <span className="text-muted">（所有日子的基本上漲機率是 {odds.baseUpProb}%）</span>
            </p>
          )}
        </Panel>
        <Panel title="風險溫度" term="risk_score" score={scores.risk} change={scores.risk_change_5d} factors={scores.risk_details} tone="risk">
          <p className="mt-2 rounded-md bg-page/70 px-3 py-2 text-sm text-ink-2">
            ⚠️ 風險溫度越高，接下來一個月台股波動通常越大。<b className="text-ink">風險高不等於會跌</b>：恐慌時機會分數常常同時升高。
          </p>
        </Panel>
      </div>
      <div className="glass mt-4 rounded-2xl p-5">
        <p className="text-sm text-ink-2">近一年走勢 <span className="text-muted">(綠底 = 加碼區 ≥55，紅底 = 減碼區 &lt;35)</span></p>
        <div className="mt-2"><ScoreHistoryChart history={scores.history} /></div>
      </div>
    </section>
  );
}
