import type { BottomFishing as BF } from "@/lib/types";

type Item = {
  title: string;
  ok: boolean;
  target: string;
  values: { label: string; value: string; ok: boolean }[];
  why: string;
};

function SignalCard({ item }: { item: Item }) {
  return (
    <article className={`glass glass-hover flex h-full flex-col justify-between gap-3 rounded-xl p-4 ${item.ok ? "!border-good" : ""}`}>
      <div>
        <div className="flex items-center justify-between">
          <h3 className="font-semibold">{item.title}</h3>
          <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${item.ok ? "bg-good text-white" : "bg-neutral text-ink-2"}`}>
            {item.ok ? "✅ 已達成" : "⏳ 未達成"}
          </span>
        </div>
        <p className="mt-1 text-xs text-muted">目標：{item.target}</p>
        <div className="mt-3 flex gap-2">
          {item.values.map((v) => (
            <div key={v.label} className="flex-1 rounded-md bg-page/70 px-2.5 py-1.5">
              <div className="text-[11px] text-muted">{v.label}</div>
              <div className={`font-mono text-lg font-semibold ${v.ok ? "text-good" : "text-ink"}`}>{v.value}</div>
            </div>
          ))}
        </div>
      </div>
      <p className="text-xs leading-relaxed text-ink-2">💡 {item.why}</p>
    </article>
  );
}

export default function BottomFishing({ bf }: { bf: BF | null }) {
  return (
    <section>
      <h2 className="text-2xl font-bold">🚦 四大長線買入確認信號</h2>
      <p className="mt-1 text-sm text-ink-2">
        4 個條件滿足 3 個以上時，代表市場系統性風險解除，是重新大舉買入股票與長債的歷史級時刻。
      </p>
      {!bf ? (
        <p className="glass mt-3 rounded-lg p-4 text-sm text-ink-2">缺少原油、CPI 或美債殖利率數據，暫時無法判斷。</p>
      ) : (
        <>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {[
              { title: "1. 原油解除通膨警報", ok: bf.oilOk, target: "布蘭特 < $90",
                values: [{ label: "布蘭特原油", value: `$${bf.values.Brent.toFixed(2)}`, ok: bf.oilOk }],
                why: "油價是萬物齊漲的源頭。跌破 90 元代表通膨惡夢結束，聯準會才有底氣救市。" },
              { title: "2. CPI 實質降溫", ok: bf.cpiOk, target: "CPI 年增率 < 2.5%",
                values: [{ label: "CPI 年增率", value: `${bf.values.CPI_YoY.toFixed(2)}%`, ok: bf.cpiOk }],
                why: "物價漲幅達標，聯準會不再需要用高利率壓榨實體經濟。" },
              { title: "3. 長天期美債解除警報", ok: bf.longRatesOk, target: "10 年 < 4.3% 且 30 年 < 4.5%",
                values: [
                  { label: "10 年期", value: `${bf.values.DGS10.toFixed(2)}%`, ok: bf.values.DGS10 < 4.3 },
                  { label: "30 年期", value: `${bf.values.DGS30.toFixed(2)}%`, ok: bf.values.DGS30 < 4.5 },
                ],
                why: "兩大長期利率同時回落，代表高息壓榨結束，長線大戶才會放心進場。" },
              { title: "4. 聯準會降息定價", ok: bf.cutPricedIn, target: "2 年債 < 基準利率 - 1 碼",
                values: [
                  { label: "2 年期國債", value: `${bf.values.DGS2.toFixed(2)}%`, ok: bf.cutPricedIn },
                  { label: "基準利率 IORB", value: `${bf.values.IORB.toFixed(2)}%`, ok: false },
                ],
                why: "2 年債代表聰明錢的預期，大幅低於官方利率代表市場在賭降息。" },
            ].map((item) => <SignalCard key={item.title} item={item} />)}
          </div>
          <p className={`mt-3 rounded-lg px-4 py-3 text-sm font-medium ${bf.met >= 3 ? "border border-good/40 bg-good/10 text-good" : "border border-warn/40 bg-warn/10 text-ink"}`}>
            {bf.met >= 3
              ? `🔥 已滿足 ${bf.met}/4 項條件：歷史級長線買點浮現，可開始將資金轉向風險資產。`
              : `⚠️ 目前滿足 ${bf.met}/4 項條件：尚未出現明確多頭訊號，資金應保持防禦姿態，耐心等待。`}
          </p>
        </>
      )}
    </section>
  );
}
