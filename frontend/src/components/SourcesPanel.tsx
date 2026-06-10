import { FileText } from "lucide-react";
import { extractSources, prettyFile } from "@/lib/citations";

/**
 * The aggregated "Sources" footer under a completed answer. The inline gold
 * chips (Markdown.tsx) mark each citation in context; this collects the UNIQUE
 * sources into one tidy, scannable list at the end — the "References" of the
 * answer. Renders nothing when the answer cited nothing (e.g. a genuine miss).
 */
export default function SourcesPanel({ content }: { content: string }) {
  const sources = extractSources(content);
  if (sources.length === 0) return null;

  return (
    <div className="mt-4 border-t border-rule pt-3">
      <div className="mb-2 font-sans text-[0.62rem] font-semibold uppercase tracking-[0.18em] text-ink-faint">
        {sources.length === 1 ? "Source" : "Sources"}
      </div>
      <ul className="flex flex-wrap gap-1.5">
        {sources.map((s) => (
          <li key={s.label}>
            <span
              title={`${prettyFile(s.file)} · page ${s.page}`}
              className="inline-flex items-center gap-1.5 rounded-md border border-rule-strong bg-paper-3/50 px-2 py-1 font-sans text-[0.74rem] text-ink-soft"
            >
              <FileText className="h-3.5 w-3.5 shrink-0 text-gold" />
              <span className="font-medium text-ink">{prettyFile(s.file)}</span>
              <span className="text-ink-faint">p.{s.page}</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
