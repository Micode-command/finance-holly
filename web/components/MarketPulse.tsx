"use client";

import { useEffect, useState } from "react";

import type { MarketStatus, NewsItem, OpenForecast } from "@/lib/types";

const REFRESH_MS = 5 * 60 * 1000;
// 分頁開著不動超過 2 小時就停止自動更新：免費主機每月只有 750 小時，
// 一直有請求進來會讓前後端都無法休眠，很快把時數用完
const MAX_AUTO_REFRESHES = 24;

const STATE_STYLE: Record<MarketStatus["state"], { dot: string; icon: string; pulse?: boolean }> = {
  open: { dot: "bg-good", icon: "🟢", pulse: true },
  pre_open: { dot: "bg-warn", icon: "⏰" },
  closed: { dot: "bg-accent", icon: "🌙" },
  holiday: { dot: "bg-accent-2", icon: "🏖️" },
  weekend: { dot: "bg-accent-2", icon: "🏖️" },
  suspended: { dot: "bg-alert", icon: "⚠️" },
};

const pct = (v: number | null | undefined, digits = 2) => (v == null ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(digits)}%`);
const tone = (v: number | null | undefined) => (v == null || Math.abs(v) < 0.05 ? "text-ink-2" : v > 0 ? "text-good" : "text-bad");
const fmtDay = (iso: string) => {
  const d = new Date(`${iso}T00:00:00+08:00`);
  return `${d.getMonth() + 1}/${d.getDate()} (${"日一二三四五六"[d.getDay()]})`;
};

function Forecast({ f, status, news }: { f: OpenForecast; status: MarketStatus; news: NewsItem[] }) {
  if (!f.model) {
    return <p className="text-sm text-ink-2">🕒 {f.message}</p>;
  }
  const up = (f.gapPct ?? 0) > 0;
  return (
    <div className="grid gap-5 lg:grid-cols-[1.1fr_1.3fr_1fr]">
      <div>
        <p className="text-xs text-muted">預估下次開盤，{fmtDay(status.nextOpenDay)} 09:00</p>
        <p className={`mt-3 font-mono text-4xl font-bold leading-none ${tone(f.gapPct)}`}>
          {up ? "▲" : "▼"} {pct(f.gapPct)}
        </p>
        <p className="mt-1 text-sm">
          <span className={`font-semibold ${tone(f.gapPct)}`}>{f.direction}</span>
          {f.gapPoints != null && <span className="ml-2 font-mono text-ink-2">約 {f.gapPoints > 0 ? "+" : ""}{f.gapPoints.toLocaleString()} 點</span>}
        </p>
        <p className="mt-2 text-xs text-ink-2">
          可能區間 <span className="font-mono text-ink">{pct(f.low)} ～ {pct(f.high)}</span>
          {f.lastClose && <>，基準 {fmtDay(f.lastClosedDay)} 收盤 <span className="font-mono">{f.lastClose.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span></>}
        </p>
        {status.note && <p className="mt-1 text-xs text-warn">⚠️ {status.note}</p>}
      </div>

      <ul className="space-y-1.5 text-sm">
        {f.inputs.map((i) => (
          <li key={i.key} className="flex items-baseline justify-between gap-3 border-b border-hairline pb-1.5 last:border-0">
            <span className="text-ink-2">
              {i.label}
              {i.detail && <span className="ml-1.5 text-[11px] text-muted">{i.detail}</span>}
            </span>
            <span className={`shrink-0 font-mono ${tone(i.pct)}`}>{i.pct == null ? "尚無新資料" : pct(i.pct)}</span>
          </li>
        ))}
      </ul>

      <div className="space-y-2 text-xs text-ink-2">
        <p>
          依據：<span className="text-ink">{f.modelLabel}</span>。2022 年後回測：開盤方向猜對 <b className="text-ink">{f.hitRate}%</b>，八成的日子誤差在
          ±{f.band}% 內。
        </p>
        <p className="text-muted">只預估「開盤」；開盤後還會受盤中消息影響，若用它判斷整天漲跌，方向大約 75% 準。</p>
        {news.length > 0 && (
          <div>
            <p className="font-semibold text-ink">可能影響開盤的新聞</p>
            <ul className="mt-1 space-y-1">
              {news.map((n) => (
                <li key={n.link}>
                  <a href={n.link} target="_blank" rel="noopener noreferrer" className="hover:text-accent">› {n.title}</a>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

/** 台股現在的開休市狀態；休市 / 收盤後顯示下次開盤的預估。每 5 分鐘自動更新。 */
export default function MarketPulse({ news }: { news: NewsItem[] }) {
  const [data, setData] = useState<{ status: MarketStatus; forecast: OpenForecast | null } | null>(null);
  const [updatedAt, setUpdatedAt] = useState<string>("");
  const [paused, setPaused] = useState(false);
  const [round, setRound] = useState(0);   // 使用者按「恢復更新」時 +1，重新啟動自動更新

  useEffect(() => {
    let alive = true;
    let count = 0;
    const load = () =>
      fetch("/api/market")
        .then((r) => (r.ok ? r.json() : null))
        .then((d) => {
          if (alive && d?.status) {
            setData(d);
            setUpdatedAt(new Date().toLocaleTimeString("zh-TW", { hour: "2-digit", minute: "2-digit", hour12: false }));
          }
        })
        .catch(() => {});
    load();
    const id = setInterval(() => {
      if (document.visibilityState !== "visible") return;     // 分頁在背景時不打擾主機
      if (++count >= MAX_AUTO_REFRESHES) {
        clearInterval(id);
        setPaused(true);
        return;
      }
      load();
    }, REFRESH_MS);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [round]);

  if (!data) return <div className="glass h-14 animate-pulse rounded-2xl" aria-label="讀取台股開盤狀態" />;
  const { status, forecast } = data;
  const s = STATE_STYLE[status.state];

  return (
    <section className="glass rounded-2xl p-4 sm:p-5" aria-live="polite">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="relative flex h-2.5 w-2.5">
          {s.pulse && <span className={`absolute inline-flex h-full w-full animate-ping rounded-full ${s.dot} opacity-60`} />}
          <span className={`relative inline-flex h-2.5 w-2.5 rounded-full ${s.dot}`} />
        </span>
        <span className="font-semibold">
          {s.icon} 台股{status.label}
        </span>
        <span className="text-sm text-ink-2">{status.detail}</span>
        {updatedAt && (
          <span className="ml-auto font-mono text-[11px] text-muted">
            更新 {updatedAt}，
            {paused ? (
              <button onClick={() => { setPaused(false); setRound((r) => r + 1); }} className="text-accent underline">
                自動更新已暫停，點此更新
              </button>
            ) : (
              "每 5 分鐘"
            )}
          </span>
        )}
      </div>
      {forecast && (
        <div className="mt-4 border-t border-hairline pt-4">
          <Forecast f={forecast} status={status} news={news} />
        </div>
      )}
    </section>
  );
}
