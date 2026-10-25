export default function DashboardSkeleton() {
  return (
    <div className="min-h-screen" aria-busy="true" aria-label="數據載入中">
      <div className="mx-auto max-w-[1400px] px-4 pt-16 sm:px-6">
        <h1 className="text-3xl font-bold">荷莉總經觀測站</h1>
        <div className="glass mt-8 h-72 rounded-2xl p-8">
          <p className="text-ink-2">正在同步聯準會、證交所與國際市場數據…</p>
          <p className="mt-2 text-sm text-muted">主機休眠後第一次載入約需 1 分鐘，之後一小時內都會很快。</p>
        </div>
        <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4 xl:grid-cols-8">
          {Array.from({ length: 8 }, (_, i) => (
            <div key={i} className="glass h-20 animate-pulse rounded-lg" />
          ))}
        </div>
      </div>
    </div>
  );
}
