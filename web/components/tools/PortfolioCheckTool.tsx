"use client";

import { useState } from "react";

import type { PortfolioCheck } from "@/lib/types";
import PortfolioResult from "./PortfolioResult";
import { type Access, buttonCls, inputCls, postTool } from "./shared";

type Row = { query: string; weight: string };
const MAX_ROWS = 10;
const GOALS = [
  { value: "long_term", label: "長期持有、依局勢調整比重" },
  { value: "income", label: "穩健領息、重視現金流" },
  { value: "growth", label: "積極成長、可承受較大波動" },
];

export default function PortfolioCheckTool({ access }: { access: Access }) {
  const [rows, setRows] = useState<Row[]>([{ query: "", weight: "" }, { query: "", weight: "" }, { query: "", weight: "" }]);
  const [cash, setCash] = useState("");
  const [goal, setGoal] = useState("long_term");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PortfolioCheck | null>(null);

  const update = (i: number, key: keyof Row, value: string) => setRows((rs) => rs.map((r, j) => (j === i ? { ...r, [key]: value } : r)));

  async function run() {
    const filled = rows.filter((r) => r.query.trim());
    if (!filled.length || !access.passcode.trim()) {
      setError("請至少輸入一筆持股，以及上方的使用密碼。");
      return;
    }
    setLoading(true);
    setError(null);
    const [body, err] = await postTool<PortfolioCheck>("/api/portfolio-check", {
      passcode: access.passcode, goal, cash: Number(cash) || 0,
      holdings: filled.map((r) => ({ query: r.query.trim(), weight: Number(r.weight) || 0 })),
    });
    setLoading(false);
    if (err || !body) return setError(err);
    access.remember();
    setResult(body);
  }

  return (
    <div className="space-y-4">
      <p className="text-xs text-muted">
        填入你的持股與比重 (可以填 % 或金額，例如「40」或「400000」，會自動換算成比例)。會依今天的大盤局勢給調整建議。
        <b className="text-ink-2"> 持股資料只用於這次分析，不會儲存。</b>
      </p>
      <form onSubmit={(e) => { e.preventDefault(); run(); }} className="space-y-2">
        {rows.map((r, i) => (
          <div key={i} className="grid grid-cols-[minmax(0,1fr)_5.5rem_auto] gap-2 sm:grid-cols-[minmax(0,1fr)_7rem_auto]">
            <input value={r.query} onChange={(e) => update(i, "query", e.target.value)} placeholder={i === 0 ? "例：台積電、0050、00937B" : "股票名稱或代號"}
              aria-label={`第 ${i + 1} 筆持股`} maxLength={30} className={inputCls} />
            <input value={r.weight} onChange={(e) => update(i, "weight", e.target.value)} placeholder="比重或金額" inputMode="decimal"
              aria-label={`第 ${i + 1} 筆比重`} className={inputCls} />
            <button type="button" onClick={() => setRows((rs) => (rs.length > 1 ? rs.filter((_, j) => j !== i) : rs))}
              aria-label={`刪除第 ${i + 1} 筆`} className="px-2 text-muted hover:text-alert">✕</button>
          </div>
        ))}
        <div className="flex flex-wrap items-center gap-2">
          {rows.length < MAX_ROWS && (
            <button type="button" onClick={() => setRows((rs) => [...rs, { query: "", weight: "" }])}
              className="rounded-lg border border-dashed border-hairline px-3 py-2 text-sm text-ink-2 hover:border-accent hover:text-accent">
              ＋ 新增持股
            </button>
          )}
          <span className="text-xs text-muted">最多 {MAX_ROWS} 筆</span>
        </div>
        <div className="grid gap-2 pt-2 sm:grid-cols-[10rem_1fr_auto]">
          <input value={cash} onChange={(e) => setCash(e.target.value)} placeholder="現金比重或金額" inputMode="decimal" aria-label="現金" className={inputCls} />
          <select value={goal} onChange={(e) => setGoal(e.target.value)} aria-label="投資目標" className={`${inputCls} bg-surface`}>
            {GOALS.map((g) => <option key={g.value} value={g.value}>投資目標：{g.label}</option>)}
          </select>
          <button type="submit" disabled={loading} className={buttonCls}>{loading ? "分析中…" : "💼 開始健檢"}</button>
        </div>
      </form>
      {loading && <p className="text-sm text-ink-2">⏳ 正在抓取每檔持股的股價、配息並請 AI 分析，大約 20～60 秒…</p>}
      {error && <p className="rounded-lg bg-alert/10 px-3 py-2 text-sm text-alert">{error}</p>}
      {result && !loading && <PortfolioResult r={result} />}
    </div>
  );
}
