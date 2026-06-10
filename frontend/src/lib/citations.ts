// Citations the model emits look like "(domestic travel.pdf, p.2)" — a source
// file plus a page. Two consumers share this module so the inline chips
// (Markdown.tsx) and the aggregated "Sources" footer (SourcesPanel.tsx) parse
// the exact same shape and never drift apart.
//
// NOTE: this RegExp carries the `g` flag, so it is STATEFUL (`lastIndex`).
// Always reset `lastIndex = 0` before a fresh scan, or call the helpers below
// which do it for you.
export const CITATION = /\(([^()]+?\.pdf,\s*p\.\d+)\)/gi;

export interface Source {
  /** The raw label exactly as written, e.g. "domestic travel.pdf, p.2". */
  label: string;
  /** Source file, e.g. "domestic travel.pdf". */
  file: string;
  /** Page number. */
  page: number;
}

/** Split a "file.pdf, p.N" label into its parts. Returns null if it doesn't fit. */
function parseLabel(label: string): Source | null {
  const m = /^(.*\.pdf),\s*p\.(\d+)$/i.exec(label.trim());
  if (!m) return null;
  return { label, file: m[1], page: Number(m[2]) };
}

/**
 * Collect the UNIQUE sources cited anywhere in an answer, in first-seen order.
 * Dedupes on file+page so an answer that cites "(leave.pdf, p.2)" three times
 * yields a single chip. Used to render the per-answer Sources footer.
 */
export function extractSources(text: string): Source[] {
  const seen = new Set<string>();
  const out: Source[] = [];
  CITATION.lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = CITATION.exec(text)) !== null) {
    const src = parseLabel(match[1]);
    if (!src) continue;
    const key = `${src.file.toLowerCase()}|${src.page}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(src);
  }
  return out;
}

/** Turn a source file into a human title: drop ".pdf", title-case the words. */
export function prettyFile(file: string): string {
  return file
    .replace(/\.pdf$/i, "")
    .split(/\s+/)
    .map((w) => (w ? w[0].toUpperCase() + w.slice(1) : w))
    .join(" ");
}
