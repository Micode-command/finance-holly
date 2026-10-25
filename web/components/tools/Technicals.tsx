import type { Technicals, TradePlan } from "@/lib/types";

const MA_COLOR: Record<number, string> = { 20: "var(--flat)", 60: "var(--cat-2)", 120: "var(--cat-5)", 240: "var(--cat-1)" };
const num = (v: number | null | undefined, d = 1) =>
  v == null ? "—" : v.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
const pct = (v: number) => `${v > 0 ? "+" : ""}${v.toFixed(1)}%`;
const GRADE = { 佳: "bg-up text-page", 普通: "bg-flat/20 text-flat", 不划算: "bg-neutral text-ink-2" } as const;

/** 參考交易計畫：目標 / 進場區 / 停損 由上到下排成價格階梯 */
export function PlanLadder({ plan, close, compact = false }: { plan: TradePlan; close: number; compact?: boolean }) {
  const rows = [
    { label: "目標價", value: num(plan.target), sub: `${pct(plan.upside)}　${plan.targetBasis}`, cls: "text-up" },
    { label: "參考進場", value: `${num(plan.entryLow)}～${num(plan.entryHigh)}`, sub: `現價 ${num(close)}，等拉回到區間內分批`, cls: "text-ink" },
    { label: "停損價", value: num(plan.stop), sub: `${pct(plan.downside)}　跌破就認錯出場`, cls: "text-down" },
  ];
  return (
    <div className={compact ? "" : "rounded-xl border border-hairline bg-page/50 p-4"}>
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-semibold">參考交易計畫</p>
        {plan.rr != null && (
          <p className="text-sm">
            風險報酬比 <span className="font-mono text-lg font-semibold">{plan.rr.toFixed(1)}</span>
            {plan.grade && <span className={`ml-2 rounded px-1.5 py-0.5 text-xs font-semibold ${GRADE[plan.grade]}`}>{plan.grade}</span>}
          </p>
        )}
      </div>
      <ul className="mt-2 divide-y divide-hairline">
        {rows.map((r) => (
          <li key={r.label} className="flex flex-wrap items-baseline justify-between gap-x-3 py-2">
            <span className="text-sm text-muted">{r.label}</span>
            <span className={`font-mono text-lg font-semibold ${r.cls}`}>{r.value}</span>
            <span className="w-full text-right text-xs text-muted">{r.sub}</span>
          </li>
        ))}
      </ul>
      {!compact && (
        <p className="mt-2 text-xs leading-relaxed text-muted">
          由程式依支撐壓力與波動 (ATR) 計算：進場在最近支撐區之上，停損在支撐區下方，目標是上方第一個壓力區 (最多到 3 個月統計區間上緣)。
          風險報酬比 = 可能賺的 ÷ 可能賠的，2 以上才算划算。
        </p>
      )}
    </div>
  );
}

/** 近一年股價 + 四條均線 + 支撐 / 壓力區 + 120 日趨勢線 */
function PriceChart({ t }: { t: Technicals }) {
  const rows = t.chart ?? [];
  if (rows.length < 20) return null;
  const W = 900, H = 320, L = 4, R = 56, T = 10, B = 22;
  const mas = t.chartMas ?? [];
  const closes = rows.map((r) => r[1] as number);
  const zoneVals = [...t.supports, ...t.resistances].flatMap((z) => [z.low, z.high]);
  const all = [...closes, ...rows.flatMap((r) => r.slice(2).filter((v): v is number => typeof v === "number")), ...zoneVals, t.plan.stop, t.plan.target];
  const lo = Math.min(...all) * 0.98, hi = Math.max(...all) * 1.02;
  const xi = (i: number) => L + (i / (rows.length - 1)) * (W - L - R);
  const y = (v: number) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
  const path = (vals: (number | null)[]) => {
    let d = "", pen = false;
    vals.forEach((v, i) => {
      if (v == null) { pen = false; return; }
      d += `${pen ? "L" : "M"}${xi(i).toFixed(1)},${y(v).toFixed(1)}`;
      pen = true;
    });
    return d;
  };
  const dates = rows.map((r) => r[0] as string);
  const trend = t.trend;
  const ti = trend ? dates.indexOf(trend.start[0]) : -1;
  const ticks = [0, Math.floor(rows.length / 2), rows.length - 1];

  return (
    <figure>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={`近一年股價走勢，收盤 ${num(t.close)}`}>
        {t.supports.map((z) => (
          <rect key={`s${z.low}`} x={L} width={W - L - R} y={y(z.high) - 2} height={Math.max(4, y(z.low) - y(z.high) + 4)} fill="var(--accent)" fillOpacity={0.12} />
        ))}
        {t.resistances.map((z) => (
          <rect key={`r${z.low}`} x={L} width={W - L - R} y={y(z.high) - 2} height={Math.max(4, y(z.low) - y(z.high) + 4)} fill="var(--serious)" fillOpacity={0.14} />
        ))}
        {mas.map((n, k) => (
          <path key={n} d={path(rows.map((r) => r[2 + k] as number | null))} fill="none" stroke={MA_COLOR[n]} strokeWidth={1.2} strokeOpacity={0.9} />
        ))}
        <path d={path(closes)} fill="none" stroke="var(--ink)" strokeWidth={1.8} strokeLinejoin="round" />
        {trend && ti >= 0 && (
          <line x1={xi(ti)} y1={y(trend.start[1])} x2={xi(rows.length - 1)} y2={y(trend.end[1])} stroke="var(--ink-2)" strokeDasharray="6 4" strokeWidth={1.5} />
        )}
        <line x1={L} x2={W - R} y1={y(t.plan.stop)} y2={y(t.plan.stop)} stroke="var(--down)" strokeDasharray="3 3" />
        <line x1={L} x2={W - R} y1={y(t.plan.target)} y2={y(t.plan.target)} stroke="var(--up)" strokeDasharray="3 3" />
        {[
          { v: t.plan.target, label: "目標", c: "var(--up)" },
          { v: closes.at(-1)!, label: "現價", c: "var(--ink)" },
          { v: t.plan.stop, label: "停損", c: "var(--down)" },
        ].map((m) => (
          <text key={m.label} x={W - R + 4} y={y(m.v) + 4} fill={m.c} fontSize={11} className="font-mono">{num(m.v, 0)}</text>
        ))}
        {ticks.map((i, k) => (
          <text key={i} x={xi(i)} y={H - 6} fill="var(--muted)" fontSize={11} textAnchor={k === 0 ? "start" : k === 2 ? "end" : "middle"}>
            {dates[i].slice(0, 7).replace("-", "/")}
          </text>
        ))}
      </svg>
      <figcaption className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
        <span><span className="mr-1 inline-block w-4 border-t-2 border-ink align-middle" />收盤</span>
        {mas.map((n) => {
          const m = t.mas.find((x) => x.days === n);
          return (
            <span key={n}>
              <span className="mr-1 inline-block w-4 border-t-2 align-middle" style={{ borderColor: MA_COLOR[n] }} />
              {m?.name ?? `${n} 日`}
            </span>
          );
        })}
        <span><span className="mr-1 inline-block h-2.5 w-4 bg-accent/30 align-middle" />支撐區</span>
        <span><span className="mr-1 inline-block h-2.5 w-4 bg-serious/30 align-middle" />壓力區</span>
        {trend && <span><span className="mr-1 inline-block w-4 border-t-2 border-dashed border-ink-2 align-middle" />近 {trend.days} 日趨勢線</span>}
      </figcaption>
    </figure>
  );
}

function Momentum({ t }: { t: Technicals }) {
  const m = t.momentum;
  const arrow = (now: number, prev: number) => (now > prev ? <span className="text-up">▲</span> : <span className="text-down">▼</span>);
  const items = [
    { label: "RSI (14)", value: m.rsi.toFixed(0), from: `一個月前 ${m.rsiPrev.toFixed(0)}`, a: arrow(m.rsi, m.rsiPrev),
      hint: m.rsi >= 70 ? "過熱" : m.rsi <= 30 ? "超賣" : "中性區" },
    { label: "KD (9)", value: `${m.k.toFixed(0)} / ${m.d.toFixed(0)}`, from: `一週前 ${m.kPrev.toFixed(0)} / ${m.dPrev.toFixed(0)}`, a: arrow(m.k, m.kPrev),
      hint: m.k > m.d ? "K 在 D 之上" : "K 在 D 之下" },
    { label: "MACD 柱", value: m.macdHist.toFixed(2), from: `一週前 ${m.macdHistPrev.toFixed(2)}`, a: arrow(m.macdHist, m.macdHistPrev),
      hint: m.macdHist > 0 ? "多方動能" : "空方動能" },
  ];
  return (
    <dl className="grid grid-cols-3 gap-2">
      {items.map((it) => (
        <div key={it.label} className="rounded-lg bg-page/60 px-3 py-2">
          <dt className="text-xs text-muted">{it.label}</dt>
          <dd className="font-mono text-lg font-semibold">{it.a} {it.value}</dd>
          <dd className="text-xs text-muted">{it.from}，{it.hint}</dd>
        </div>
      ))}
    </dl>
  );
}

function Zones({ t }: { t: Technicals }) {
  const z = (list: Technicals["supports"]) =>
    list.length ? list.map((x) => `${num(x.low)}${x.high > x.low ? `～${num(x.high)}` : ""} (轉折 ${x.touches} 次)`).join("、") : "近一年沒有明顯區間";
  return (
    <dl className="grid gap-2 text-sm sm:grid-cols-2">
      <div className="rounded-lg bg-page/60 px-3 py-2">
        <dt className="text-xs text-muted">壓力區 (上方賣壓)</dt>
        <dd className="mt-0.5">{z(t.resistances)}</dd>
      </div>
      <div className="rounded-lg bg-page/60 px-3 py-2">
        <dt className="text-xs text-muted">支撐區 (下方買盤)</dt>
        <dd className="mt-0.5">{z(t.supports)}</dd>
      </div>
      <div className="rounded-lg bg-page/60 px-3 py-2 sm:col-span-2">
        <dt className="text-xs text-muted">關鍵均線</dt>
        <dd className="mt-1 flex flex-wrap gap-x-4 gap-y-1">
          {t.mas.map((m) => (
            <span key={m.days}>
              {m.name} <span className="font-mono">{num(m.value)}</span>
              <span className={m.above ? "text-up" : "text-down"}> {m.above ? "站上" : "跌破"}</span>
              <span className="text-muted">，{m.rising ? "上揚" : "下彎"}</span>
            </span>
          ))}
        </dd>
      </div>
    </dl>
  );
}

/** 個股健檢的技術面區塊 */
export default function TechnicalPanel({ t, ai }: { t: Technicals; ai?: { technical_view?: string; trade_case?: string; invalidation?: string } | null }) {
  return (
    <section className="space-y-4">
      <p className="text-sm font-semibold">技術面與交易計畫</p>
      <PriceChart t={t} />
      <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <div className="space-y-3">
          <Zones t={t} />
          <Momentum t={t} />
          <div>
            <p className="text-xs text-muted">這些指標代表什麼</p>
            <ul className="mt-1.5 space-y-1 text-sm text-ink-2">
              {t.readings.map((r) => <li key={r}>› {r}</li>)}
            </ul>
          </div>
        </div>
        <PlanLadder plan={t.plan} close={t.close ?? t.plan.entryHigh} />
      </div>
      {(ai?.technical_view || ai?.trade_case || ai?.invalidation) && (
        <dl className="space-y-2 rounded-xl bg-accent/10 px-4 py-3 text-sm leading-relaxed">
          {ai.technical_view && <div><dt className="inline font-semibold">技術面解讀：</dt><dd className="inline">{ai.technical_view}</dd></div>}
          {ai.trade_case && <div><dt className="inline font-semibold">這個機會為何成立：</dt><dd className="inline">{ai.trade_case}</dd></div>}
          {ai.invalidation && <div><dt className="inline font-semibold">判斷失效的條件：</dt><dd className="inline">{ai.invalidation}</dd></div>}
        </dl>
      )}
    </section>
  );
}
