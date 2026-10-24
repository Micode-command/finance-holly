import { getDashboard } from "@/lib/api";
import AiPanel from "./AiPanel";
import BottomFishing from "./BottomFishing";
import Footer from "./Footer";
import Glossary from "./Glossary";
import ScoreBreakdown from "./ScoreBreakdown";
import Hero from "./Hero";
import MetricCard from "./MetricCard";
import { Reveal } from "./Parallax";
import { RangeProvider, RangeToggle } from "./RangeContext";
import SectionNav from "./SectionNav";
import ToolsPanel from "./tools/ToolsPanel";

/** 抓後端數據並組裝整頁 (Server Component，外層用 <Suspense> 包住) */
export default async function Dashboard() {
  const data = await getDashboard();
  const navItems = [
    { id: "tools", label: "🧰 個股健檢" },
    { id: "ai", label: "AI 解析" },
    { id: "scores", label: "雙分數" },
    { id: "signals", label: "買點信號" },
    ...data.sections.map((s, i) => ({ id: `sec-${i}`, label: s.nav })),
    { id: "glossary", label: "📖 名詞辭典" },
  ];

  return (
    <RangeProvider>
      <Hero data={data} />
      <div className="mx-auto mb-8 w-full max-w-[1400px] px-4 sm:px-6">
        <ToolsPanel />
      </div>
      <SectionNav items={navItems} />

      <main className="mx-auto flex w-full max-w-[1400px] flex-col gap-16 px-4 pt-10 sm:px-6">
        {data.missingFred.length > 0 && (
          <p className="rounded-lg border border-warn/50 bg-warn/10 px-4 py-3 text-sm">
            ⚠️ 以下聯準會 (FRED) 數據抓取失敗，相關卡片會顯示無數據：{data.missingFred.join(", ")}。請確認 FRED_API_KEY 是否有效。
          </p>
        )}

        {data.missingTw.length > 0 && (
          <p className="rounded-lg border border-warn/50 bg-warn/10 px-4 py-3 text-sm">
            ⚠️ 部分台股數據 (證交所 / 國發會 / 經濟部) 暫時抓不到，台股籌碼卡片可能顯示無數據，分數會用其餘因子計算：{data.missingTw.join(", ")}
          </p>
        )}

        <Reveal>
          <div id="ai" className="scroll-mt-20">
            <AiPanel enabled={data.aiEnabled} />
          </div>
        </Reveal>

        <Reveal>
          <div id="scores" className="scroll-mt-20">
            <ScoreBreakdown scores={data.scores} />
          </div>
        </Reveal>

        <Reveal>
          <div id="signals" className="scroll-mt-20">
            <BottomFishing bf={data.bottomFishing} />
          </div>
        </Reveal>

        <div className="flex justify-end sm:hidden">
          <RangeToggle />
        </div>

        {data.sections.map((section, i) => (
          <section key={section.title} id={`sec-${i}`} className="scroll-mt-20">
            <Reveal>
              <p className="font-mono text-xs tracking-[0.25em] text-accent">{String(i + 1).padStart(2, "0")} / {String(data.sections.length).padStart(2, "0")}</p>
              <h2 className="mt-1 text-2xl font-bold">{section.title}</h2>
              {section.intro && <p className="mt-1 text-sm text-ink-2">{section.intro}</p>}
            </Reveal>
            <div className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {section.cards.map((card, j) => (
                <Reveal key={card.id} delay={j * 70}>
                  <MetricCard card={card} />
                </Reveal>
              ))}
            </div>
          </section>
        ))}
        <section id="glossary" className="scroll-mt-20">
          <Reveal>
            <p className="font-mono text-xs tracking-[0.25em] text-accent">GLOSSARY</p>
            <h2 className="mt-1 text-2xl font-bold">📖 名詞小辭典</h2>
            <p className="mt-1 text-sm text-ink-2">看不懂的名詞都在這裡：中文、英文全名、白話解釋，以及它對台股的影響。卡片上有虛線底線的名詞點一下也會跳到這裡。</p>
          </Reveal>
          <div className="mt-5"><Glossary /></div>
        </section>
      </main>

      <Footer data={data} />
    </RangeProvider>
  );
}
