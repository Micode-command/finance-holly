import "server-only";

import type { Dashboard } from "./types";

/** Python 後端位址 (api/main.py)；部署時用環境變數 API_URL 覆寫 */
export const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";

export async function getDashboard(): Promise<Dashboard> {
  const res = await fetch(`${API_URL}/api/dashboard`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `後端回應錯誤 (${res.status})`);
  }
  return res.json();
}
