import "server-only";

import type { Dashboard } from "./types";

/** Python 後端位址 (api/main.py)；部署時用環境變數 API_URL 覆寫 */
export const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";

const ATTEMPTS = 4;              // Render 免費方案閒置後會休眠，喚醒 + 抓數據約 1 分鐘
const ATTEMPT_TIMEOUT_MS = 75_000;
const RETRY_DELAY_MS = 5_000;

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export async function getDashboard(): Promise<Dashboard> {
  let lastError: unknown;
  for (let i = 0; i < ATTEMPTS; i++) {
    try {
      const res = await fetch(`${API_URL}/api/dashboard`, { signal: AbortSignal.timeout(ATTEMPT_TIMEOUT_MS) });
      if (res.ok) return res.json();
      const body = await res.json().catch(() => ({}));
      lastError = new Error(body.detail ?? `後端回應錯誤 (${res.status})`);
      // 4xx 是請求本身的問題，重試也沒用；5xx / 主機喚醒中才重試
      if (res.status < 500) break;
    } catch (e) {
      lastError = e;   // 連線失敗 / 逾時：多半是後端還在喚醒
    }
    if (i < ATTEMPTS - 1) await sleep(RETRY_DELAY_MS);
  }
  throw lastError instanceof Error ? lastError : new Error("後端暫時沒有回應");
}
