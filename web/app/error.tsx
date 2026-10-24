"use client";

export default function ErrorPage({ error, retry }: { error: unknown; retry: () => void }) {
  return (
    <main className="mx-auto max-w-2xl px-4 py-16">
      <h1 className="text-2xl font-bold">無法載入數據</h1>
      <p className="mt-3 text-ink-2">{error instanceof Error ? error.message : String(error)}</p>
      <p className="mt-3 text-sm text-muted">
        請確認 Python 後端有在執行：<code className="rounded bg-surface px-1.5 py-0.5">uvicorn api.main:app --port 8000</code>
      </p>
      <button onClick={() => retry()} className="mt-6 rounded-lg bg-accent px-4 py-2 font-semibold text-page">
        重試
      </button>
    </main>
  );
}
