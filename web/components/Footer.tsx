import type { Dashboard } from "@/lib/types";
import { STANCE } from "./Hero";
import { Reveal } from "./Parallax";

export default function Footer({ data }: { data: Dashboard }) {
  const s = STANCE[data.verdict.stance];
  return (
    <footer className="relative isolate mt-24 overflow-hidden border-t border-hairline">
      <div
        className="parallax pointer-events-none absolute inset-x-0 -bottom-40 -z-10 mx-auto h-80 w-[60rem] max-w-full rounded-full blur-3xl"
        style={{ "--depth": -0.08, background: `radial-gradient(circle, ${s.glow}, transparent 70%)` } as React.CSSProperties}
      />
      <div className="mx-auto max-w-[1100px] px-4 py-16 text-center sm:px-6">
        <Reveal>
          <p className="font-mono text-xs tracking-[0.3em] text-muted">TODAY&apos;S VERDICT · {data.asOf}</p>
          <p className="mt-5 text-2xl font-bold leading-relaxed sm:text-3xl">
            <span className={`glow-text ${s.text}`}>{s.icon}</span> {data.verdict.one_liner}
          </p>
        </Reveal>
        <p className="mt-10 text-xs leading-relaxed text-muted">
          本站結論由量化規則自動歸納，AI 解析由 Gemini 產生，僅供參考，不構成任何投資建議。
          <br />
          數據來源：FRED (聖路易聯準銀行) · Yahoo Finance · Yahoo奇摩股市
        </p>
      </div>
    </footer>
  );
}
