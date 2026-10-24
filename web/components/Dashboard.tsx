import { getDashboard } from "@/lib/api";
import AiPanel from "./AiPanel";
import BottomFishing from "./BottomFishing";
import Footer from "./Footer";
import HealthScore from "./HealthScore";
import Hero from "./Hero";
import MetricCard from "./MetricCard";
import { Reveal } from "./Parallax";
import { RangeProvider, RangeToggle } from "./RangeContext";
import SectionNav from "./SectionNav";

/** 抓後端數據並組裝整頁 (Server Component，外層用 <Suspense> 包住) */
export default async function Dashboard() {
  const data = await getDashboard();
  const navItems = [
    { id: "ai", label: "AI 解析" },
    { id: "signals", label: "買點信號" },
    ...data.sections.map((s, i) => ({ id: `sec-${i}`, label: s.nav })),
  ];

  return (
    <RangeProvider>
      <Hero data={data} />
      <SectionNav items={navItems} />

      <main className="mx-auto flex w-full max-w-[1400px] flex-col gap-16 px-4 pt-10 sm:px-6">
        {data.missingFred.length > 0 && (
          <p className="rounded-lg border border-warn/50 bg-warn/10 px-4 py-3 text-sm">
            ⚠️ 以下聯準會 (FRED) 數據抓取失敗，相關卡片會顯示無數據：{data.missingFred.join(", ")}。請確認 FRED_API_KEY 是否有效。
          </p>
        )}

        <Reveal>
          <div id="ai" className="grid scroll-mt-20 items-start gap-6 lg:grid-cols-[1.4fr_1fr]">
            <AiPanel enabled={data.aiEnabled} />
            <HealthScore health={data.health} />
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
      </main>

      <Footer data={data} />
    </RangeProvider>
  );
}
