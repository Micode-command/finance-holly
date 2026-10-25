import { formatChange, formatValue, prBand, prBandNeutral } from "@/lib/format";
import { TERM_BY_ID } from "@/lib/glossary";
import type { Card } from "@/lib/types";
import TrendChart from "./TrendChart";

/** 漲跌只看方向：漲紅、跌綠、平盤黃 (指標本身是利多還是利空，寫在說明與位階) */
const dirClass = (v: number) => (Math.abs(v) < 1e-9 ? "text-flat" : v > 0 ? "text-up" : "text-down");

/** 變化量的單位：價格類是 %；利率、百分比類是「百分點」；其他用卡片本身的單位 (億、口、分、兆) */
function changeUnit(card: Card) {
  if (card.changeMode === "pct") return "%";
  const unit = card.suffix.trim();
  if (unit === "%" || unit.includes("百分點")) return "百分點";
  return unit || "增減";
}

function ChangeChips({ card }: { card: Card }) {
  return (
    <div>
      <p className="mb-1 text-[11px] text-muted">變化 ({changeUnit(card)})</p>
    <dl className="grid grid-cols-3 gap-1.5">
      {card.changes?.map((c) => {
        const arrow = c.value == null ? "" : c.value > 0 ? "▲" : c.value < 0 ? "▼" : "■";
        return (
          <div key={c.label} className="rounded-md bg-page/70 px-2 py-1">
            <dt className="text-[11px] text-muted">{c.label}</dt>
            <dd className={`font-mono text-sm font-semibold ${c.value == null ? "text-muted" : dirClass(c.value)}`}>
              {c.value == null ? "—" : `${arrow} ${formatChange(card, c.value)}`}
            </dd>
          </div>
        );
      })}
    </dl>
    </div>
  );
}

// 位階到極端時「亮燈」：標籤改成實心色塊，一眼就看得到
const BAND_STYLE = {
  bad: { dot: "bg-alert", chip: "bg-alert text-page" },
  serious: { dot: "bg-serious", chip: "bg-serious/20 text-serious" },
  neutral: { dot: "bg-ink-2", chip: "text-ink-2" },
  goodSoft: { dot: "bg-up", chip: "bg-up/20 text-good-text" },
  good: { dot: "bg-up", chip: "bg-up text-page" },
  extreme: { dot: "bg-flat", chip: "bg-flat text-page" },
} as const;

/** 近 3 年位階條：0-100 的位置 + 文字標籤 (不只靠顏色) */
const PR_LABEL: Record<string, string> = { "C-PR": "近 3 年位階", "G-120PR": "半年漲幅的 3 年位階", "G-200PR": "200 日漲幅的 3 年位階" };

function PrMeter({ label, value, neutral }: { label: string; value: number; neutral?: boolean }) {
  const band = neutral
    ? { label: prBandNeutral(value), tone: value >= 90 || value <= 10 ? ("extreme" as const) : ("neutral" as const) }
    : prBand(value);
  const st = BAND_STYLE[band.tone];
  return (
    <div className="min-w-0">
      <div className="flex items-center justify-between text-xs">
        <span className="text-muted">{PR_LABEL[label] ?? label}</span>
        <span className="flex items-center gap-1.5">
          <span className="font-mono text-sm text-ink">{value.toFixed(0)}</span>
          <span className={`rounded px-1.5 py-0.5 font-semibold ${st.chip}`}>{band.label}</span>
        </span>
      </div>
      <div className="relative mt-1.5 h-1.5 rounded-full bg-neutral">
        <div className="absolute inset-y-0 left-[10%] w-px bg-surface" />
        <div className="absolute inset-y-0 left-[90%] w-px bg-surface" />
        <div
          className={`absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-surface ${st.dot}`}
          style={{ left: `${Math.min(100, Math.max(0, value))}%` }}
        />
      </div>
    </div>
  );
}

/** 一句話說明「現在」相對門檻線的位置 */
function thresholdStatus(card: Card) {
  if (card.latest == null || card.refLines.length === 0) return null;
  return card.refLines
    .map((r) => `${card.latest! >= r.value ? "高於" : "低於"} ${r.label}`)
    .join("；");
}

function Explanation({ card }: { card: Card }) {
  const d = card.desc;
  const terms = card.terms.map((id) => TERM_BY_ID[id]).filter(Boolean);
  return (
    <details className="group text-xs text-ink-2">
      <summary className="cursor-pointer list-none text-muted hover:text-accent">
        <span className="group-open:hidden">📖 白話解釋：{terms.map((x) => x.name).join("、") || "這個指標怎麼看"}</span>
        <span className="hidden group-open:inline">▾ 收合說明</span>
      </summary>
      {terms.map((term) => (
        <div key={term.id} className="mt-3 rounded-lg bg-page/60 p-3">
          <p className="font-semibold text-ink">{term.name}</p>
          <p className="text-[11px] text-muted">{term.en}</p>
          <p className="mt-1.5 text-ink-2">{term.short}</p>
          <ul className="mt-1.5 space-y-0.5">
            {term.read.slice(0, 3).map((r) => <li key={r}>› {r}</li>)}
          </ul>
          <a href={`#term-${term.id}`} className="mt-1.5 inline-block text-accent hover:underline">看完整解釋</a>
        </div>
      ))}
      <p className="mt-3 font-semibold text-ink">這張卡片的重點</p>
      <div className="mt-1 space-y-1 leading-relaxed">
        {d.kind === "explain" ? (
          <>
            <p><b className="text-ink">公式：</b>{d.formula}</p>
            <p><b className="text-ink">{d.thresholdLabel}：</b>{d.threshold}</p>
            <p><b className="text-ink">連動：</b>{d.impact}</p>
          </>
        ) : (
          <>
            <p>{d.summary}</p>
            <p>{d.hint}</p>
          </>
        )}
      </div>
    </details>
  );
}

export default function MetricCard({ card }: { card: Card }) {
  if (!card.available) {
    return (
      <article id={`card-${card.id}`} className="glass scroll-mt-24 rounded-xl p-4">
        <h3 className="font-semibold">{card.title}</h3>
        <p className="mt-3 text-sm text-alert">無數據：請確認 FRED_API_KEY 或稍後重新整理</p>
      </article>
    );
  }
  const status = thresholdStatus(card);

  return (
    <article id={`card-${card.id}`} className="glass glass-hover flex scroll-mt-24 flex-col gap-3 rounded-xl p-4 target:border-accent">
      <header>
        <h3 className="text-sm font-semibold text-ink-2">{card.title}</h3>
        <div className="mt-1 flex flex-wrap items-baseline justify-between gap-x-2">
          <span className="font-mono text-2xl font-semibold text-ink">
            {formatValue(card, card.latest!, { compact: true, keepDecimals: true })}
            {card.suffix && <span className="ml-1 font-sans text-sm font-normal text-ink-2">{card.suffix.trim()}</span>}
          </span>
          <span className="text-[11px] text-muted">資料日期 {card.lastDate}</span>
        </div>
        {(status || card.note) && <p className="mt-1 text-xs text-ink-2">{[card.note, status].filter(Boolean).join("；")}</p>}
      </header>

      <ChangeChips card={card} />
      <TrendChart card={card} />

      {card.percentiles && card.percentiles.length > 0 && (
        <div className="space-y-2.5">
          {card.percentiles.map((p) => p.value != null && <PrMeter key={p.label} label={p.label} value={p.value} neutral={card.prNeutral} />)}
        </div>
      )}
      <Explanation card={card} />
    </article>
  );
}
