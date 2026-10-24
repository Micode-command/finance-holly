"use client";

import { CartesianGrid, Legend, Line, LineChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

const SERIES = [
  { key: "o", name: "3 個月機會分數", color: "var(--cat-1)" },
  { key: "r", name: "風險溫度", color: "var(--cat-2)" },
] as const;

/** 近一年兩個分數的走勢 (同一個 0~100 刻度，不用雙 Y 軸) */
export default function ScoreHistoryChart({ history }: { history: [string, number, number][] }) {
  const data = history.map(([d, o, r]) => ({ t: Date.parse(d), o, r }));
  if (data.length < 2) return null;
  const fmt = (t: number) => {
    const d = new Date(t);
    return `${d.getFullYear() % 100}/${d.getMonth() + 1}`;
  };
  return (
    <div className="h-56 w-full" role="img" aria-label="近一年機會分數與風險溫度走勢">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
          <CartesianGrid vertical={false} stroke="var(--grid)" />
          {/* 機會分數的加碼 / 減碼區 */}
          <ReferenceArea y1={55} y2={100} fill="var(--good)" fillOpacity={0.06} />
          <ReferenceArea y1={0} y2={35} fill="var(--bad)" fillOpacity={0.06} />
          <XAxis dataKey="t" type="number" scale="time" domain={["dataMin", "dataMax"]} tickFormatter={fmt}
            tick={{ fill: "var(--muted)", fontSize: 11 }} axisLine={{ stroke: "var(--axis)" }} tickLine={false} minTickGap={40} />
          <YAxis domain={[0, 100]} ticks={[0, 35, 55, 100]} tick={{ fill: "var(--muted)", fontSize: 11 }} axisLine={false} tickLine={false} />
          <Tooltip
            isAnimationActive={false}
            cursor={{ stroke: "var(--axis)" }}
            contentStyle={{ background: "var(--surface-2)", border: "1px solid var(--hairline)", borderRadius: 8, fontSize: 12 }}
            labelStyle={{ color: "var(--muted)" }}
            labelFormatter={(t) => new Date(Number(t)).toISOString().slice(0, 10)}
            formatter={(v, name) => [Number(v).toFixed(0), name]}
          />
          <Legend wrapperStyle={{ fontSize: 12, color: "var(--ink-2)" }} iconType="plainline" />
          {SERIES.map((s) => (
            <Line key={s.key} dataKey={s.key} name={s.name} stroke={s.color} strokeWidth={2} dot={false} isAnimationActive={false} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
