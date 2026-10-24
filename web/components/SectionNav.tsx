import { RangeToggle } from "./RangeContext";

/** 吸頂導覽列：跳到各區塊 + 切換所有圖表的區間 */
export default function SectionNav({ items }: { items: { id: string; label: string }[] }) {
  return (
    <nav id="nav" className="sticky top-0 z-20 scroll-mt-0 border-y border-hairline bg-page/75 backdrop-blur-xl">
      <div className="mx-auto flex max-w-[1400px] items-center gap-4 px-4 py-2.5 sm:px-6">
        <ul className="flex min-w-0 flex-1 gap-1 overflow-x-auto text-sm [scrollbar-width:none]">
          {items.map((it) => (
            <li key={it.id} className="shrink-0">
              <a href={`#${it.id}`} className="block rounded-md px-2.5 py-1 text-ink-2 hover:bg-neutral hover:text-accent">
                {it.label}
              </a>
            </li>
          ))}
        </ul>
        <div className="hidden shrink-0 sm:block">
          <RangeToggle />
        </div>
      </div>
    </nav>
  );
}
