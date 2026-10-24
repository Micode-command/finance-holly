import { changeTone, formatChange, formatValue, prBand } from "@/lib/format";
import type { Card } from "@/lib/types";
import TrendChart from "./TrendChart";

const TONE_TEXT = { good: "text-good-text", bad: "text-bad", flat: "text-muted" } as const;
const TONE_ICON = { good: "▲", bad: "▼", flat: "■" } as const;

function ChangeChips({ card }: { card: Card }) {
  return (
    <div>
      <p className="mb-1 text-[11px] text-muted">變化{card.changeMode === "abs" ? " (百分點)" : " (%)"}</p>
    <dl className="grid grid-cols-3 gap-1.5">
      {card.changes?.map((c) => {
        const tone = c.value == null ? "flat" : changeTone(card, c.value);
        const arrow = c.value == null ? "" : c.value > 0 ? "▲" : c.value < 0 ? "▼" : TONE_ICON.flat;
        return (
          <div key={c.label} className="rounded-md bg-page/70 px-2 py-1">
            <dt className="text-[11px] text-muted">{c.label}</dt>
            <dd className={`font-mono text-xs font-semibold ${TONE_TEXT[tone]}`}>
              {c.value == null ? "—" : `${arrow} ${formatChange(card, c.value)}`}
            </dd>
          </div>
        );
      })}
    </dl>
    </div>
  );
}

const BAND_FILL = {
  bad: "bg-bad",
  serious: "bg-serious",
  neutral: "bg-muted",
  goodSoft: "bg-good/60",
  good: "bg-good",
} as const;

/** PR 位階條：0-100 的位置 + 文字標籤 (不只靠顏色) */
function PrMeter({ label, value }: { label: string; value: number }) {
  const band = prBand(value);
  return (
    <div className="min-w-0">
      <div className="flex items-baseline justify-between text-[11px]">
        <span className="text-muted">{label} 歷史位階</span>
        <span className="font-semibold tabular-nums text-ink">
          {value.toFixed(0)} · {band.label}
        </span>
      </div>
      <div className="relative mt-1 h-1.5 rounded-full bg-neutral">
        {/* 80 / 90 警戒刻度 */}
        <div className="absolute inset-y-0 left-[80%] w-px bg-surface" />
        <div className="absolute inset-y-0 left-[90%] w-px bg-surface" />
        <div
          className={`absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-surface ${BAND_FILL[band.tone]}`}
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
    .join(" · ");
}

function Explanation({ card }: { card: Card }) {
  const d = card.desc;
  return (
    <details className="group text-xs text-ink-2">
      <summary className="cursor-pointer list-none text-muted hover:text-ink-2">
        <span className="group-open:hidden">▸ 這個指標怎麼看</span>
        <span className="hidden group-open:inline">▾ 收合說明</span>
      </summary>
      <div className="mt-2 space-y-1 leading-relaxed">
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
        <p className="mt-3 text-sm text-bad">無數據：請確認 FRED_API_KEY 或稍後重新整理</p>
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
        {(status || card.note) && <p className="mt-1 text-xs text-ink-2">{[card.note, status].filter(Boolean).join(" · ")}</p>}
      </header>

      <ChangeChips card={card} />
      <TrendChart card={card} />

      {card.percentiles && card.percentiles.length > 0 && (
        <div className="grid gap-2" style={{ gridTemplateColumns: `repeat(${card.percentiles.length}, minmax(0, 1fr))` }}>
          {card.percentiles.map((p) => p.value != null && <PrMeter key={p.label} label={p.label} value={p.value} />)}
        </div>
      )}
      <Explanation card={card} />
    </article>
  );
}
