import type { MarketScores, Stance } from "@/lib/types";

// 與 holly/verdict.py 的門檻一致：機會 ≥55 加碼、<35 減碼；風險 ≥65 = 動盪
const OPP_ADD = 55, OPP_TRIM = 35, RISK_STORM = 65;
const W = 560, H = 420, L = 40, R = 16, T = 16, B = 40;
const x = (risk: number) => L + (Math.min(100, Math.max(0, risk)) / 100) * (W - L - R);
const y = (opp: number) => H - B - (Math.min(100, Math.max(0, opp)) / 100) * (H - T - B);

const ZONES = [
  { r: [0, RISK_STORM], o: [OPP_ADD, 100], label: "加碼區", tone: "var(--up)" },
  { r: [RISK_STORM, 100], o: [OPP_ADD, 100], label: "加碼，但分批", tone: "var(--up)" },
  { r: [0, RISK_STORM], o: [OPP_TRIM, OPP_ADD], label: "維持", tone: "var(--flat)" },
  { r: [RISK_STORM, 100], o: [OPP_TRIM, OPP_ADD], label: "維持，波動大", tone: "var(--flat)" },
  { r: [0, RISK_STORM], o: [0, OPP_TRIM], label: "減碼區", tone: "var(--down)" },
  { r: [RISK_STORM, 100], o: [0, OPP_TRIM], label: "防守區", tone: "var(--down)" },
];

const MARKS = [
  { back: 250, label: "1 年前" },
  { back: 126, label: "半年前" },
  { back: 63, label: "3 個月前" },
];

const STANCE_COLOR: Record<Stance, string> = { offensive: "var(--up)", neutral: "var(--flat)", defensive: "var(--down)" };

/** 機會 × 風險 地圖：一年軌跡 (越舊越淡) + 未來 3 個月的推估範圍 */
export default function RiskMap({ scores, stance }: { scores: MarketScores; stance: Stance }) {
  const h = scores.history;
  if (h.length < 2) return null;
  // 每 5 個交易日取一點 (週線)，避免每日雜訊把軌跡糊成一團；最後一點一定保留
  const weekly = h.filter((_, i) => (h.length - 1 - i) % 5 === 0);
  const pts = weekly.map(([, o, r]) => [x(r), y(o)] as const);
  // 一年分四段，越近越清楚
  const seg = Math.ceil(pts.length / 4);
  const segments = [0, 1, 2, 3].map((i) => pts.slice(Math.max(0, i * seg - 1), (i + 1) * seg)).filter((s) => s.length > 1);
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
        {ZONES.map((z) => (
          <g key={z.label}>
            <rect x={x(z.r[0])} y={y(z.o[1])} width={x(z.r[1]) - x(z.r[0])} height={y(z.o[0]) - y(z.o[1])} fill={z.tone} fillOpacity={0.06} />
            <text x={x(z.r[0]) + 10} y={y(z.o[1]) + 20} fill={z.tone} fillOpacity={0.85} fontSize={13} fontWeight={500}>{z.label}</text>
          </g>
        ))}
        <line x1={x(RISK_STORM)} x2={x(RISK_STORM)} y1={y(0)} y2={y(100)} stroke="var(--axis)" />
        {[OPP_TRIM, OPP_ADD].map((v) => (
          <g key={v}>
            <line x1={x(0)} x2={x(100)} y1={y(v)} y2={y(v)} stroke="var(--axis)" />
            <text x={L - 6} y={y(v) + 4} fill="var(--muted)" fontSize={11} textAnchor="end" className="font-mono">{v}</text>
          </g>
        ))}
        <text x={x(RISK_STORM)} y={H - B + 16} fill="var(--muted)" fontSize={11} textAnchor="middle" className="font-mono">{RISK_STORM}</text>

        {/* 一年軌跡 */}
        {segments.map((s, i) => (
          <path key={i} d={line(s)} pathLength={1} className="load-draw" fill="none" stroke="var(--ink)"
            strokeOpacity={0.18 + i * 0.2} strokeWidth={1.2 + i * 0.3} strokeLinejoin="round" style={{ animationDelay: `${0.3 + i * 0.35}s` }} />
        ))}
        {MARKS.map((m) => {
          const p = h[h.length - 1 - m.back];
          if (!p) return null;
          return (
            <g key={m.label}>
              <circle cx={x(p[2])} cy={y(p[1])} r={3} fill="var(--ink-2)" />
              <text x={x(p[2]) + 6} y={y(p[1]) - 6} fill="var(--ink-2)" fontSize={11} paintOrder="stroke" stroke="var(--page)" strokeWidth={3}>{m.label}</text>
            </g>
          );
        })}

        {/* 未來 3 個月推估：每一步的 68% 範圍疊成一個錐形 */}
        {end && (
          <>
            <ellipse cx={x(end.r)} cy={y(end.o)} rx={Math.max(4, (x(end.rHi) - x(end.rLo)) / 2)} ry={Math.max(4, (y(end.oLo) - y(end.oHi)) / 2)}
              fill="var(--accent)" fillOpacity={0.06} stroke="var(--accent)" strokeOpacity={0.6} strokeDasharray="4 4" />
            <path d={line(proj.map((p) => [x(p.r), y(p.o)] as const))} fill="none" stroke="var(--accent)" strokeWidth={2} strokeDasharray="5 4" />
            <circle cx={x(end.r)} cy={y(end.o)} r={4} fill="var(--accent)" />
            <text x={x(end.r) - 10} y={y(end.o) + 4} fill="var(--accent)" fontSize={12} fontWeight={500} textAnchor="end" paintOrder="stroke" stroke="var(--page)" strokeWidth={4}>3 個月後推估</text>
          </>
        )}

        <circle cx={x(today[2])} cy={y(today[1])} r={11} fill={color} stroke="var(--page)" strokeWidth={3} />
        <text x={x(today[2]) + (today[2] > 70 ? -18 : 18)} y={y(today[1]) + 5} fill="var(--ink)" fontSize={14} fontWeight={700}
          textAnchor={today[2] > 70 ? "end" : "start"}>今天</text>

        <text x={(L + W - R) / 2} y={H - 8} fill="var(--ink-2)" fontSize={12} textAnchor="middle">風險溫度：往右越動盪</text>
        <text x={12} y={(T + H - B) / 2} fill="var(--ink-2)" fontSize={12} textAnchor="middle" transform={`rotate(-90 12 ${(T + H - B) / 2})`}>3 個月機會：往上越有利</text>
      </svg>
      <figcaption className="mt-2 text-xs leading-relaxed text-muted">
        實線是過去一年每天的位置 (越舊越淡)；虛線是用歷史上分數「往平均拉回」的速度推估的未來 3 個月路徑，虛線圈是 68% 可能範圍。
        推估只看分數本身的慣性，不知道未來新聞，僅供參考。
      </figcaption>
    </figure>
  );
}
