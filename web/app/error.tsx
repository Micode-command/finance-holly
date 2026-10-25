"use client";

import { useEffect, useState, useSyncExternalStore } from "react";

const AUTO_RETRY_SECONDS = 20;
const MAX_AUTO_RETRIES = 5;
const RETRY_KEY = "holly-auto-retry";
const noopSubscribe = () => () => {};

function readRetries() {
  try {
    return Number(sessionStorage.getItem(RETRY_KEY) ?? 0);
  } catch {
    return 0;
  }
}

export default function ErrorPage({ error, retry }: { error: unknown; retry: () => void }) {
  const [left, setLeft] = useState(AUTO_RETRY_SECONDS);
  // 伺服器端沒有 sessionStorage：先當 0，進到瀏覽器才讀真正的次數 (避免 hydration 不一致)
  const retries = useSyncExternalStore(noopSubscribe, readRetries, () => 0);
  const auto = retries < MAX_AUTO_RETRIES;

  // 免費主機休眠後第一次打開常常會失敗：倒數後自動重新整理，最多 5 次
  useEffect(() => {
    if (!auto) return;
    const id = setInterval(() => {
      setLeft((s) => {
        if (s <= 1) {
          clearInterval(id);
          try {
            sessionStorage.setItem(RETRY_KEY, String(retries + 1));
          } catch {}
          window.location.reload();
          return 0;
        }
        return s - 1;
      });
    }, 1000);
    return () => clearInterval(id);
  }, [auto, retries]);

  const detail = error instanceof Error ? error.message : String(error);
  return (
    <main className="mx-auto max-w-2xl px-4 py-16">
      <p className="text-sm text-muted">荷莉總經觀測站</p>
      <h1 className="mt-2 text-2xl font-bold">⏳ 主機正在喚醒中</h1>
      <p className="mt-3 leading-relaxed text-ink-2">
        網站使用免費主機，一段時間沒人使用會進入休眠；喚醒並抓取最新的聯準會與市場數據大約需要 1～2 分鐘。
      </p>
      {auto ? (
        <p className="mt-4 text-ink">
          將在 <span className="font-mono text-accent">{left}</span> 秒後自動重新載入 (第 {retries + 1} / {MAX_AUTO_RETRIES} 次)…
        </p>
      ) : (
        <p className="mt-4 text-alert">已經自動重試多次仍無法載入，可能是資料來源暫時異常，請稍後再試。</p>
      )}
      <button
        onClick={() => {
          try {
            sessionStorage.removeItem(RETRY_KEY);
          } catch {}
          retry();
        }}
        className="mt-6 rounded-lg bg-accent px-4 py-2 font-semibold text-page"
      >
        立即重試
      </button>
      <details className="mt-8 text-xs text-muted">
        <summary className="cursor-pointer">技術細節</summary>
        <p className="mt-2 break-all">{detail}</p>
        {process.env.NODE_ENV === "development" && (
          <p className="mt-2">本機開發：請確認 Python 後端有在執行 (uvicorn api.main:app --port 8000)</p>
        )}
      </details>
    </main>
  );
}
