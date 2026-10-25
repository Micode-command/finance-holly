import type { Dashboard } from "@/lib/types";
import { STANCE } from "./Hero";

export default function Footer({ data }: { data: Dashboard }) {
  const s = STANCE[data.verdict.stance];
  return (
    <footer className="mt-24 border-t border-hairline">
      <div className="mx-auto max-w-[1100px] px-4 py-16 text-center sm:px-6">
        <p className="text-sm text-muted">{data.asOf} 的一句話結論</p>
        <p className="mt-4 text-2xl font-bold leading-relaxed sm:text-3xl">
          <span className={s.text}>{s.label}</span>　{data.verdict.one_liner}
        </p>
        <p className="mt-10 text-xs leading-relaxed text-muted">
          本站結論由量化規則自動歸納，AI 解析由 Gemini 產生，僅供參考，不構成任何投資建議。
          <br />
          數據來源：FRED (聖路易聯準銀行)、Yahoo Finance、證交所、期交所、FinMind、Yahoo 奇摩股市
        </p>
      </div>
    </footer>
  );
}
