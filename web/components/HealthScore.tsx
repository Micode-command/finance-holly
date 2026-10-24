import type { HealthScore as Health } from "@/lib/types";

const LEVEL = {
  good: { text: "text-good-text", ring: "border-good", icon: "🟢" },
  warn: { text: "text-ink", ring: "border-warn", icon: "🟡" },
  bad: { text: "text-bad", ring: "border-bad", icon: "🔴" },
} as const;

export default function HealthScore({ health }: { health: Health }) {
  const lv = LEVEL[health.level];
  return (
    <section className={`glass rounded-2xl border-l-4 ${lv.ring} p-5 sm:p-6`}>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="min-w-0">
          <h2 className="text-lg font-bold">🇹🇼 台股健康度拆解</h2>
          <p className={`mt-1 text-base font-semibold ${lv.text}`}>
            {lv.icon} {health.status}
          </p>
          <p className="mt-2 inline-block rounded-md bg-page/70 px-2.5 py-1 text-sm text-ink-2">
            💡 盤勢特徵：{health.features.length ? health.features.join("，") : "多空不明"}
          </p>
        </div>
        <div className="text-right">
          <span className={`font-mono text-5xl font-bold ${lv.text}`}>{health.score}</span>
          <span className="ml-1 text-sm text-muted">/ 100</span>
        </div>
      </div>
      <ul className="mt-4 flex flex-wrap gap-2 border-t border-hairline pt-4">
        {health.details.map((d) => (
          <li key={d} className="rounded-full border border-hairline bg-page/70 px-3 py-1 text-sm">
            {d}
          </li>
        ))}
      </ul>
    </section>
  );
}
