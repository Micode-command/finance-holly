"use client";

import { useMemo } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceArea,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatValue, RANGE_DAYS } from "@/lib/format";
import type { Card } from "@/lib/types";
import { useRange } from "./RangeContext";

const DAY = 86_400_000;
const RECENT_DAYS = 30; // 「最近一個月」底色

type Point = { t: number; v: number };

/** 取整齊的刻度 (1 / 2 / 2.5 / 5 × 10^n)，避免 +2.08、-1.55 這種難讀的數字 */
function niceTicks(lo: number, hi: number, count = 4) {
  const raw = (hi - lo) / (count - 1) || 1;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw)!;
  const start = Math.floor(lo / step) * step;
  const ticks: number[] = [];
  for (let v = start; v <= hi + step * 0.001; v += step) ticks.push(Number(v.toFixed(10)));
  if (ticks.at(-1)! < hi) ticks.push(Number((ticks.at(-1)! + step).toFixed(10)));
  return ticks;
}

/** 第一個刻度靠左、最後一個靠右對齊，不會被裁掉 */
function DateTick(props: { x?: number; y?: number; payload?: { value: number }; index?: number; format: (t: number) => string }) {
  const { x = 0, y = 0, payload, index = 0, format } = props;
  const anchor = index === 0 ? "start" : index === 2 ? "end" : "middle";
  return (
    <text x={x} y={y + 12} textAnchor={anchor} fill="var(--muted)" fontSize={11}>
      {payload ? format(payload.value) : ""}
    </text>
  );
}

export default function TrendChart({ card }: { card: Card }) {
  const { range: globalRange } = useRange();
  const range = globalRange === "auto" ? card.defaultRange : globalRange;

  const { points, ticks, domain, refLines, sparse } = useMemo(() => {
    const all: Point[] = (card.series ?? []).map(([d, v]) => ({ t: Date.parse(d), v }));
    const end = all.at(-1)?.t ?? 0;
    // 月/季資料在短區間內點太少時，至少保留 6 個點才看得出方向
    let pts = all.filter((p) => p.t >= end - RANGE_DAYS[range] * DAY);
    if (pts.length < 6) pts = all.slice(-6);

    const vals = pts.map((p) => p.v);
    let lo = Math.min(...vals);
    let hi = Math.max(...vals);
    const span = hi - lo || Math.abs(hi) * 0.1 || 1;
    // 門檻線離數據不遠才畫進來，太遠會把走勢壓扁
    const refs = card.refLines.filter((r) => r.value >= lo - span * 0.6 && r.value <= hi + span * 0.6);
    for (const r of refs) {
      lo = Math.min(lo, r.value);
      hi = Math.max(hi, r.value);
    }
    const ticks = niceTicks(lo, hi);
    return { points: pts, ticks, domain: [ticks[0], ticks.at(-1)!] as [number, number], refLines: refs, sparse: pts.length < 40 };
  }, [card.series, card.refLines, range]);

  if (points.length < 2) return <div className="h-36 text-sm text-muted">數據不足</div>;

  const first = points[0].t;
  const last = points.at(-1)!;
  const spanDays = (last.t - first) / DAY;
  const dateFmt = (t: number) => {
    const d = new Date(t);
    return spanDays > 400
      ? `${d.getFullYear()}/${String(d.getMonth() + 1).padStart(2, "0")}`
      : `${d.getMonth() + 1}/${d.getDate()}`;
  };

  return (
    <div className="h-36 w-full" role="img" aria-label={`${card.title} 走勢圖，最新值 ${formatValue(card, last.v)}`}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={points} margin={{ top: 8, right: 4, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id={`fill-${card.id}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--series)" stopOpacity={0.18} />
              <stop offset="100%" stopColor="var(--series)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} stroke="var(--grid)" strokeWidth={1} />
          {/* 最近一個月的底色：一眼看出「現在」在哪 */}
          <ReferenceArea x1={Math.max(first, last.t - RECENT_DAYS * DAY)} x2={last.t} fill="var(--recent)" ifOverflow="hidden" />
          <XAxis
            dataKey="t"
            type="number"
            scale="time"
            domain={[first, last.t]}
            ticks={[first, first + (last.t - first) / 2, last.t]}
            tick={<DateTick format={dateFmt} />}
            axisLine={{ stroke: "var(--axis)" }}
            tickLine={false}
            interval={0}
            padding={{ left: 0, right: 6 }}
          />
          <YAxis
            orientation="right"
            domain={domain}
            ticks={ticks}
            tickFormatter={(v: number) => formatValue(card, v, { compact: true })}
            tick={{ fill: "var(--muted)", fontSize: 11, style: { fontVariantNumeric: "tabular-nums" } }}
            axisLine={false}
            tickLine={false}
            width={52}
          />
          {refLines.map((r) => (
            <ReferenceLine
              key={r.value}
              y={r.value}
              stroke="var(--bad)"
              strokeOpacity={0.55}
              strokeDasharray="4 3"
              label={{ value: formatValue(card, r.value, { compact: true }), position: "insideBottomLeft", fill: "var(--bad)", fontSize: 10 }}
            />
          ))}
          <Area dataKey="v" type="linear" stroke="none" fill={`url(#fill-${card.id})`} isAnimationActive={false} />
          <Line
            dataKey="v"
            type="linear"
            stroke="var(--series)"
            strokeWidth={2}
            dot={sparse ? { r: 2.5, fill: "var(--series)", strokeWidth: 0 } : false}
            activeDot={{ r: 4, fill: "var(--series)", stroke: "var(--surface)", strokeWidth: 2 }}
            isAnimationActive={false}
          />
          {/* 最新一點：實心點 + 外圈 */}
          <ReferenceDot x={last.t} y={last.v} r={4.5} fill="var(--series)" stroke="var(--surface)" strokeWidth={2} />
          <Tooltip
            cursor={{ stroke: "var(--axis)", strokeWidth: 1 }}
            isAnimationActive={false}
            content={({ active, payload }) => {
              const p = active && payload?.[0]?.payload as Point | undefined;
              if (!p) return null;
              const d = new Date(p.t);
              return (
                <div className="rounded-md border border-hairline bg-surface-2 px-2.5 py-1.5 text-xs shadow-lg">
                  <div className="text-muted">{`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`}</div>
                  <div className="font-mono font-semibold text-ink">{formatValue(card, p.v)}</div>
                </div>
              );
            }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
