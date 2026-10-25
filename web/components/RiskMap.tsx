import type { MarketScores, Stance } from "@/lib/types";

// 與 holly/verdict.py 的門檻一致：機會 ≥55 加碼、<35 減碼；風險 ≥65 = 動盪
const OPP_ADD = 55, OPP_TRIM = 35, RISK_STORM = 65;
const W = 560, H = 420, L = 40, R = 16, T = 16, B = 40;
const TRAIL_DAYS = 30;

/** 分段線性刻度：每個區間在畫面上一樣大 (分數 0~35 / 35~55 / 55~100 各佔 1/3 高度) */
function piecewise(breaks: number[], v: number) {
  const c = Math.min(100, Math.max(0, v));
  const n = breaks.length - 1;
  for (let i = 0; i < n; i++) {
    if (c <= breaks[i + 1]) return (i + (c - breaks[i]) / (breaks[i + 1] - breaks[i])) / n;
  }
  return 1;
}
const x = (risk: number) => L + piecewise([0, RISK_STORM, 100], risk) * (W - L - R);
const y = (opp: number) => H - B - piecewise([0, OPP_TRIM, OPP_ADD, 100], opp) * (H - T - B);

const ZONES = [
  { r: [0, RISK_STORM], o: [OPP_ADD, 100], label: "加碼區", tone: "var(--up)" },
  { r: [RISK_STORM, 100], o: [OPP_ADD, 100], label: "加碼，但分批", tone: "var(--up)" },
  { r: [0, RISK_STORM], o: [OPP_TRIM, OPP_ADD], label: "維持", tone: "var(--flat)" },
  { r: [RISK_STORM, 100], o: [OPP_TRIM, OPP_ADD], label: "維持，波動大", tone: "var(--flat)" },
  { r: [0, RISK_STORM], o: [0, OPP_TRIM], label: "減碼區", tone: "var(--down)" },
  { r: [RISK_STORM, 100], o: [0, OPP_TRIM], label: "防守區", tone: "var(--down)" },
];


const STANCE_COLOR: Record<Stance, string> = { offensive: "var(--up)", neutral: "var(--flat)", defensive: "var(--down)" };

/** 機會 × 風險 地圖：近 30 個交易日的軌跡 + 未來 3 個月的推估範圍 */
export default function RiskMap({ scores, stance }: { scores: MarketScores; stance: Stance }) {
  const h = scores.history.slice(-TRAIL_DAYS);
  if (h.length < 2) return null;
  const pts = h.map(([, o, r]) => [x(r), y(o)] as const);
  // 分三段，越近越清楚
  const seg = Math.ceil(pts.length / 3);
  const segments = [0, 1, 2].map((i) => pts.slice(Math.max(0, i * seg - 1), (i + 1) * seg)).filter((s) => s.length > 1);
  const today = h.at(-1)!;
  const po = scores.projection?.opportunity ?? [];
  const pr = scores.projection?.risk ?? [];
  const proj = po.map((p, i) => ({ days: p[0], o: p[1], oLo: p[2], oHi: p[3], r: pr[i]?.[1] ?? today[2], rLo: pr[i]?.[2] ?? today[2], rHi: pr[i]?.[3] ?? today[2] }));
  const end = proj.at(-1);
  const color = STANCE_COLOR[stance];
  const line = (p: readonly (readonly [number, number])[]) => p.map(([a, b], i) => `${i ? "L" : "M"}${a.toFixed(1)},${b.toFixed(1)}`).join("");

  return (
    <figure className="min-w-0">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img"
        aria-label={`今天位在機會 ${today[1]}、風險 ${today[2]}${end ? `；3 個月後推估機會約 ${end.o.toFixed(0)}、風險約 ${end.r.toFixed(0)}` : ""}`}>
        <rect x={x(0)} y={y(100)} width={x(100) - x(0)} height={y(0) - y(100)} fill="var(--page)" />
        {ZONES.map((z) => (
          <g key={z.label}>
            <rect x={x(z.r[0])} y={y(z.o[1])} width={x(z.r[1]) - x(z.r[0])} height={y(z.o[0]) - y(z.o[1])} fill={z.tone} fillOpacity={0.06} />
            <text x={x(z.r[0]) + 10} y={y(z.o[1]) + 20} fill={z.tone} fillOpacity={0.85} fontSize={13} fontWeight={500}>{z.label}</text>
          </g>
        ))}
        <line x1={x(RISK_STORM)} x2={x(RISK_STORM)} y1={y(0)} y2={y(100)} stroke="var(--axis)" />
        {[0, OPP_TRIM, OPP_ADD, 100].map((v) => (
          <g key={v}>
            {v > 0 && v < 100 && <line x1={x(0)} x2={x(100)} y1={y(v)} y2={y(v)} stroke="var(--axis)" />}
            <text x={L - 6} y={y(v) + 4} fill="var(--muted)" fontSize={11} textAnchor="end" className="font-mono">{v}</text>
          </g>
        ))}
        {[0, RISK_STORM, 100].map((v) => (
          <text key={v} x={x(v)} y={H - B + 16} fill="var(--muted)" fontSize={11} textAnchor={v === 0 ? "start" : v === 100 ? "end" : "middle"} className="font-mono">{v}</text>
        ))}

        {/* 一年軌跡 */}
        {segments.map((s, i) => (
          <path key={i} d={line(s)} pathLength={1} className="load-draw" fill="none" stroke="var(--ink)"
            strokeOpacity={0.3 + i * 0.25} strokeWidth={1.5 + i * 0.4} strokeLinejoin="round" style={{ animationDelay: `${0.3 + i * 0.35}s` }} />
        ))}
        <circle cx={pts[0][0]} cy={pts[0][1]} r={3.5} fill="var(--ink-2)" />
        <text x={pts[0][0]} y={pts[0][1] - 10} fill="var(--ink-2)" fontSize={11} textAnchor="middle" paintOrder="stroke" stroke="var(--page)" strokeWidth={3}>30 天前</text>

        {/* 未來 3 個月推估：每一步的 68% 範圍疊成一個錐形 */}
        {end && (
          <>
            <ellipse cx={(x(end.rHi) + x(end.rLo)) / 2} cy={(y(end.oLo) + y(end.oHi)) / 2} rx={Math.max(4, (x(end.rHi) - x(end.rLo)) / 2)} ry={Math.max(4, (y(end.oLo) - y(end.oHi)) / 2)}
              fill="var(--accent)" fillOpacity={0.06} stroke="var(--accent)" strokeOpacity={0.6} strokeDasharray="4 4" />
            <path d={line(proj.map((p) => [x(p.r), y(p.o)] as const))} fill="none" stroke="var(--accent)" strokeWidth={2} strokeDasharray="5 4" />
            <circle cx={x(end.r)} cy={y(end.o)} r={4} fill="var(--accent)" />
            <text x={(x(end.rHi) + x(end.rLo)) / 2} y={y(end.oHi) - 8} fill="var(--accent)" fontSize={12} fontWeight={500} textAnchor="middle" paintOrder="stroke" stroke="var(--page)" strokeWidth={4}>
              3 個月後推估 (圈內 = 68% 可能範圍)
            </text>
          </>
        )}

        <circle cx={x(today[2])} cy={y(today[1])} r={11} fill={color} stroke="var(--page)" strokeWidth={3} />
        <text x={x(today[2]) + (today[2] > 70 ? -18 : 18)} y={y(today[1]) + 5} fill="var(--ink)" fontSize={14} fontWeight={700}
          textAnchor={today[2] > 70 ? "end" : "start"}>今天</text>

        <text x={(L + W - R) / 2} y={H - 8} fill="var(--ink-2)" fontSize={12} textAnchor="middle">風險溫度：往右越動盪</text>
        <text x={12} y={(T + H - B) / 2} fill="var(--ink-2)" fontSize={12} textAnchor="middle" transform={`rotate(-90 12 ${(T + H - B) / 2})`}>3 個月機會：往上越有利</text>
      </svg>
      <figcaption className="mt-2 text-xs leading-relaxed text-muted">
        白線是最近 30 個交易日每天的位置 (越舊越淡)，看得出最近往哪個方向移動；藍色虛線是未來 3 個月的推估路徑，虛線圈是 68% 可能範圍。
        推估依歷史上分數「往平均拉回」的速度計算，不知道未來新聞，僅供參考。三個區域的高度一樣，代表「加碼 / 維持 / 減碼」三種判斷，不代表分數的比例。
      </figcaption>
    </figure>
  );
}
