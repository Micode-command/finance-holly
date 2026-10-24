export default function DashboardSkeleton() {
  return (
    <div className="relative isolate min-h-screen overflow-hidden" aria-busy="true" aria-label="數據載入中">
      <div className="grid-bg absolute inset-0 -z-10" />
      <div className="mx-auto max-w-[1400px] px-4 pt-16 sm:px-6">
        <p className="font-mono text-xs tracking-[0.3em] text-accent">HOLLY · MACRO TERMINAL</p>
        <h1 className="mt-1 text-3xl font-bold">荷莉總經觀測站</h1>
        <div className="glass relative mt-8 h-72 overflow-hidden rounded-3xl p-8">
          <div className="scanline absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-transparent via-accent/10 to-transparent" />
          <p className="font-mono text-sm text-ink-2">⏳ 正在同步聯準會與華爾街數據…</p>
          <p className="mt-2 text-xs text-muted">第一次載入約需 30 秒，之後一小時內都會很快。</p>
        </div>
        <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4 xl:grid-cols-8">
          {Array.from({ length: 8 }, (_, i) => (
            <div key={i} className="glass h-20 animate-pulse rounded-xl" />
          ))}
        </div>
      </div>
    </div>
  );
}
