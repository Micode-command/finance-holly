"use client";

import { useState, useSyncExternalStore } from "react";

import type { StockBrief, StockCheck } from "@/lib/types";
import PortfolioCheckTool from "./PortfolioCheckTool";
import { type Access, buttonCls, inputCls, postTool } from "./shared";
import StockCheckResult from "./StockCheckResult";

const PASSCODE_KEY = "holly-passcode";
const noopSubscribe = () => () => {};

/** 瀏覽器記住密碼 (只存在這台裝置；私密視窗等情況存不了就算了) */
function loadPasscode() {
  try {
    return localStorage.getItem(PASSCODE_KEY) ?? "";
  } catch {
    return "";
  }
}

function StockCheckTool({ access }: { access: Access }) {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<StockBrief[]>([]);
  const [result, setResult] = useState<StockCheck | null>(null);

  async function run(q = query) {
    if (!q.trim() || !access.passcode.trim()) {
      setError("請輸入公司名稱或代號，以及上方的使用密碼。");
      return;
    }
    setLoading(true);
    setError(null);
    setCandidates([]);
    const [body, err] = await postTool<StockCheck | { status: "ambiguous"; candidates: StockBrief[] }>("/api/stock-check", { query: q, passcode: access.passcode });
    setLoading(false);
    if (err || !body) return setError(err);
    access.remember();
    if (body.status === "ambiguous") return setCandidates(body.candidates);
    setResult(body);
  }

  return (
    <div className="space-y-4">
      <p className="text-xs text-muted">輸入一家公司，結合今天的大盤局勢與它的財報、營收、估值、籌碼，評估未來 3 個月的股價情境與風險。</p>
      <form className="grid gap-2 sm:grid-cols-[1fr_auto]" onSubmit={(e) => { e.preventDefault(); run(); }}>
        <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="公司名稱或股票代號，例如：愛普、6531、台積電"
          aria-label="公司名稱或股票代號" maxLength={30} className={inputCls} />
        <button type="submit" disabled={loading} className={buttonCls}>{loading ? "分析中…" : "🔍 開始健檢"}</button>
      </form>
      {loading && <p className="text-sm text-ink-2">⏳ 正在抓取股價、月營收、財報並請 AI 分析，大約 20～40 秒…</p>}
      {error && <p className="rounded-lg bg-bad/10 px-3 py-2 text-sm text-bad">{error}</p>}
      {candidates.length > 0 && (
        <div>
          <p className="text-sm text-ink-2">找到多家符合的公司，請選一家：</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {candidates.map((c) => (
              <button key={c.id} onClick={() => { setQuery(c.id); run(c.id); }}
                className="rounded-full border border-hairline px-3 py-1 text-sm hover:border-accent hover:text-accent">
                {c.name} <span className="font-mono text-muted">{c.id}</span>
              </button>
            ))}
          </div>
        </div>
      )}
      {result && !loading && <StockCheckResult r={result} />}
    </div>
  );
}

const TABS = [
  { id: "stock", label: "🔍 個股健檢" },
  { id: "portfolio", label: "💼 我的配置健檢" },
] as const;

/** 互動工具：放在首頁 header 下方，需要密碼才能使用 (避免 AI 額度被濫用) */
export default function ToolsPanel() {
  const [tab, setTab] = useState<(typeof TABS)[number]["id"]>("stock");
  // 伺服器端沒有 localStorage：先給空字串，進到瀏覽器後才讀記住的密碼 (避免 hydration 不一致)
  const stored = useSyncExternalStore(noopSubscribe, loadPasscode, () => "");
  const [typed, setTyped] = useState<string | null>(null);
  const [rememberIt, setRememberIt] = useState(true);
  const passcode = typed ?? stored;
  const access: Access = {
    passcode,
    remember: () => {
      try {
        if (rememberIt) localStorage.setItem(PASSCODE_KEY, passcode);
        else localStorage.removeItem(PASSCODE_KEY);
      } catch {}
    },
  };

  return (
    <section id="tools" className="glass scroll-mt-20 rounded-2xl p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-bold">🧰 互動工具</h2>
        <div role="tablist" className="flex gap-1 rounded-lg border border-hairline p-0.5 text-sm">
          {TABS.map((t) => (
            <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)}
              className={`rounded-md px-3 py-1 ${tab === t.id ? "bg-accent/15 text-accent" : "text-ink-2"}`}>
              {t.label}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2">
        <input value={passcode} onChange={(e) => setTyped(e.target.value)} type="password" inputMode="numeric" autoComplete="off"
          placeholder="使用密碼" aria-label="使用密碼" className={`${inputCls} w-36`} />
        <label className="flex items-center gap-2 text-xs text-muted">
          <input type="checkbox" checked={rememberIt} onChange={(e) => setRememberIt(e.target.checked)} />
          在這台裝置記住密碼
        </label>
      </div>

      <div className="mt-4">
        {tab === "stock" ? <StockCheckTool access={access} /> : <PortfolioCheckTool access={access} />}
      </div>
    </section>
  );
}
