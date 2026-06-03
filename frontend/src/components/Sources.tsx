import { useState } from "react";
import { ChevronRight } from "lucide-react";
import { extractCitations } from "@/lib/citations";

/** Collapsible "N sources" disclosure built from an answer's citations. */
export default function Sources({ content }: { content: string }) {
  const [open, setOpen] = useState(false);
  const sources = extractCitations(content);
  if (sources.length === 0) return null;

  const total = sources.reduce((n, s) => n + s.pages.length, 0);

  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="inline-flex items-center gap-1.5 font-sans text-xs text-ink-faint transition hover:text-ink-muted"
      >
        <ChevronRight
          className={`h-3 w-3 transition-transform duration-200 ${open ? "rotate-90" : ""}`}
        />
        {total} {total === 1 ? "source" : "sources"}
      </button>

      {open && (
        <ul className="mt-1.5 space-y-1 border-l border-rule pl-3">
          {sources.map((s) => (
            <li key={s.name} className="font-sans text-[0.78rem] text-ink-muted">
              <span className="text-ink-soft">{s.name}</span>{" "}
              <span className="font-mono text-[0.92em] text-ink-faint">
                p. {s.pages.join(", ")}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
