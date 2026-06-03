// Pull "(domestic travel.pdf, p.2)" citations out of an answer, grouped by file.
const CITATION = /\(([^()]+?\.pdf),\s*p\.(\d+)\)/gi;

export interface CitationSource {
  name: string;
  pages: number[];
}

export function extractCitations(text: string): CitationSource[] {
  const byName = new Map<string, Set<number>>();
  const order: string[] = [];
  let match: RegExpExecArray | null;
  CITATION.lastIndex = 0;

  while ((match = CITATION.exec(text)) !== null) {
    const name = match[1].trim();
    const page = Number(match[2]);
    if (!byName.has(name)) {
      byName.set(name, new Set());
      order.push(name);
    }
    byName.get(name)!.add(page);
  }

  return order.map((name) => ({
    name,
    pages: [...byName.get(name)!].sort((a, b) => a - b),
  }));
}
