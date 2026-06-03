import { useEffect, useState } from "react";
import { FileText, Moon, Plus, Sun } from "lucide-react";
import { fetchLibrary, type LibraryInfo } from "@/lib/api";

export default function Sidebar({
  onNewChat,
  disabled,
  theme,
  onToggleTheme,
}: {
  onNewChat: () => void;
  disabled: boolean;
  theme: "dark" | "light";
  onToggleTheme: () => void;
}) {
  const [lib, setLib] = useState<LibraryInfo | null>(null);

  useEffect(() => {
    fetchLibrary()
      .then(setLib)
      .catch(() => setLib(null));
  }, []);

  const docCount = lib?.documents.length ?? 0;
  const countLabel = lib
    ? `${docCount} ${docCount === 1 ? "document" : "documents"}` +
      (lib.total_pages ? ` · ${lib.total_pages} pages` : "")
    : "Loading…";

  return (
    <aside className="z-10 hidden w-72 shrink-0 flex-col border-r border-rule bg-paper-2 px-5 py-7 md:flex">
      <div className="font-serif text-xl font-bold tracking-tight text-ink">
        <span className="text-gold" aria-hidden="true">◐</span> RAG Assistant
      </div>
      <p className="mt-1 font-sans text-[0.82rem] leading-relaxed text-ink-muted">
        Ask questions across your indexed documents.
      </p>

      <button
        type="button"
        onClick={onNewChat}
        disabled={disabled}
        className="mt-5 inline-flex items-center justify-center gap-2 rounded-lg border border-rule-strong px-3 py-2 font-sans text-sm text-ink transition duration-200 hover:bg-paper-3 disabled:opacity-50"
      >
        <Plus className="h-4 w-4" /> New chat
      </button>

      <div className="mt-6 border-t border-rule pt-4">
        <div className="font-sans text-[0.62rem] font-semibold uppercase tracking-[0.18em] text-ink-faint">
          Library
        </div>
        <div className="font-sans text-xs text-ink-muted">{countLabel}</div>
        <ul className="mt-2 flex max-h-[55vh] flex-col gap-px overflow-y-auto">
          {lib?.documents.map((d) => (
            <li
              key={d.name}
              title={d.name}
              className="group flex items-center gap-2 rounded-md px-1.5 py-1.5 font-sans text-[0.76rem] text-ink-soft transition duration-200 hover:bg-paper-3 hover:text-ink"
            >
              <FileText className="h-3.5 w-3.5 shrink-0 text-ink-faint transition group-hover:text-gold" />
              <span className="flex-1 truncate">{d.name}</span>
              {d.pages != null && (
                <span className="shrink-0 rounded-full border border-rule bg-paper-3 px-2 py-0.5 font-mono text-[0.62rem] text-ink-muted">
                  {d.pages} pp.
                </span>
              )}
            </li>
          ))}
        </ul>
      </div>

      <div className="mt-auto flex items-center justify-between border-t border-rule pt-4">
        <div className="flex items-center gap-2 font-sans text-xs text-ink-faint">
          <span className="status-dot" aria-hidden="true" />
          <span>
            Ready · <span className="text-ink-muted">{lib?.model ?? "Gemini 2.5 Flash"}</span>
          </span>
        </div>
        <button
          type="button"
          onClick={onToggleTheme}
          aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          className="rounded-md p-1.5 text-ink-faint transition duration-200 hover:bg-paper-3 hover:text-ink"
        >
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>
      </div>
    </aside>
  );
}
