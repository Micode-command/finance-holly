"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

/** 清除後端快取、重新抓 FRED / Yahoo 數據 (約 30 秒) */
export default function RefreshButton() {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [message, setMessage] = useState<string | null>(null);

  return (
    <span className="inline-flex flex-col items-end gap-1">
      <button
        disabled={pending}
        onClick={() =>
          startTransition(async () => {
            const res = await fetch("/api/refresh", { method: "POST" });
            if (!res.ok) {
              const body = await res.json().catch(() => ({}));
              setMessage(body.detail ?? "暫時無法重新抓取，請稍後再試。");
              return;
            }
            setMessage(null);
            router.refresh();
          })
        }
        className="rounded-lg border border-hairline bg-surface/70 px-3 py-1.5 text-ink-2 hover:border-accent/50 hover:text-accent disabled:opacity-60"
      >
        {pending ? "⏳ 重新抓取中…" : "🧹 強制重新抓取數據"}
      </button>
      {message && <span role="status" className="text-xs text-warn">{message}</span>}
    </span>
  );
}
