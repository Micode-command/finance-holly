import { TERM_BY_ID } from "@/lib/glossary";

/** 名詞連結：虛線底線 + 滑鼠停留顯示一句話解釋，點了跳到下方小辭典 */
export default function TermLink({ id, children }: { id: string; children?: React.ReactNode }) {
  const term = TERM_BY_ID[id];
  if (!term) return <>{children}</>;
  return (
    <a
      href={`#term-${id}`}
      title={`${term.name}：${term.short}`}
      className="underline decoration-muted decoration-dotted underline-offset-4 hover:text-accent hover:decoration-accent"
    >
      {children ?? term.name}
    </a>
  );
}
