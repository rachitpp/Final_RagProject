import { Fragment, type ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { FileText } from "lucide-react";

// Citations look like "(domestic travel.pdf, p.2)" — rendered as gold source
// chips with a hover tooltip expanding the page reference.
const CITATION = /\(([^()]+?\.pdf,\s*p\.\d+)\)/gi;

function chipify(node: ReactNode): ReactNode {
  if (typeof node === "string") {
    const out: ReactNode[] = [];
    let last = 0;
    let key = 0;
    let match: RegExpExecArray | null;
    CITATION.lastIndex = 0;
    while ((match = CITATION.exec(node)) !== null) {
      if (match.index > last) out.push(node.slice(last, match.index));
      const label = match[1];
      const tip = label.replace(/,\s*p\./i, " · page ");
      out.push(
        <cite
          key={key++}
          className="group relative mx-0.5 inline-flex max-w-full cursor-default items-center gap-1 whitespace-nowrap rounded-md border border-gold/30 bg-gold/10 px-1.5 py-0.5 align-middle font-mono text-[0.72em] not-italic text-gold"
        >
          <FileText className="h-3 w-3" />
          {label}
          <span className="pointer-events-none absolute bottom-full left-1/2 z-30 mb-1.5 hidden -translate-x-1/2 whitespace-nowrap rounded-md border border-rule-strong bg-paper-2 px-2 py-1 font-sans text-[0.7rem] text-ink-soft shadow-lg group-hover:block">
            {tip}
          </span>
        </cite>,
      );
      last = match.index + match[0].length;
    }
    if (last < node.length) out.push(node.slice(last));
    return out.length > 0 ? out : node;
  }
  if (Array.isArray(node)) {
    return node.map((child, i) => <Fragment key={i}>{chipify(child)}</Fragment>);
  }
  return node;
}

const components: Components = {
  p: ({ children }) => <p className="my-2.5 leading-[1.75]">{chipify(children)}</p>,
  ul: ({ children }) => (
    <ul className="my-3 ml-5 list-disc marker:text-ink-faint">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="my-3 ml-5 list-decimal marker:text-ink-faint">{children}</ol>
  ),
  li: ({ children }) => <li className="my-1.5 leading-[1.7]">{chipify(children)}</li>,
  strong: ({ children }) => <strong className="font-semibold text-ink">{children}</strong>,
  h2: ({ children }) => (
    <h2 className="mb-2 mt-5 font-sans text-[1.1rem] font-semibold text-ink">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="mb-1.5 mt-4 font-sans text-base font-semibold text-ink">{children}</h3>
  ),
  blockquote: ({ children }) => (
    <blockquote className="my-4 border-l-2 border-gold/30 pl-4 italic text-ink-muted">
      {children}
    </blockquote>
  ),
  hr: () => <hr className="my-5 border-t border-rule" />,
  code: ({ children }) => (
    <code className="rounded bg-paper-4 px-1.5 py-0.5 font-mono text-[0.88em] text-ink">
      {children}
    </code>
  ),
  pre: ({ children }) => (
    <pre className="my-3 overflow-x-auto rounded-md bg-paper-4 p-3 font-mono text-sm">
      {children}
    </pre>
  ),
  a: ({ children, href }) => (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="text-gold underline decoration-gold/40 underline-offset-2 transition hover:decoration-gold"
    >
      {children}
    </a>
  ),
  table: ({ children }) => (
    <div className="my-4 overflow-x-auto rounded-md border border-rule-strong">
      <table className="w-full border-collapse font-sans text-[0.82rem] tabular-nums">

        {children}
      </table>
    </div>
  ),
  thead: ({ children }) => <thead className="bg-paper-4 text-ink">{children}</thead>,
  th: ({ children }) => (
    <th className="whitespace-nowrap border-b border-rule px-3 py-2 text-left font-semibold">
      {children}
    </th>
  ),
  tr: ({ children }) => <tr className="transition-colors hover:bg-paper-3">{children}</tr>,
  td: ({ children }) => (
    <td className="border-b border-rule px-3 py-2 align-top text-ink-soft">
      {chipify(children)}
    </td>
  ),
};

export default function Markdown({ content }: { content: string }) {
  return (
    <div className="assistant-prose font-serif text-[0.95rem] text-ink">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
