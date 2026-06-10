import { useCallback, useState, type KeyboardEvent } from "react";
import { DropdownMenu } from "radix-ui";
import { MoreHorizontal, Pencil, Trash2 } from "lucide-react";
import type { Conversation } from "@/lib/conversations";

interface Props {
  conversations: Conversation[];
  activeId: string;
  /** Disabled (e.g. while a stream is in flight) so we don't switch mid-answer. */
  disabled: boolean;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onRename: (id: string, title: string) => void;
  /** Called after picking a chat — used to dismiss the mobile drawer. */
  onAfterSelect?: () => void;
}

/**
 * The sidebar's recent-chats list. Click a row to switch chats; the per-row menu
 * renames or deletes. Empty chats never appear here (they aren't persisted), so
 * the list only shows conversations that actually have a transcript.
 */
export default function ConversationList({
  conversations,
  activeId,
  disabled,
  onSelect,
  onDelete,
  onRename,
  onAfterSelect,
}: Props) {
  const saved = conversations.filter((c) => c.messages.length > 0);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");

  // Stable ref callback: focuses + selects the rename input when it mounts
  // (no useEffect, and no `autofocus` attribute — which fires on page load and
  // disorients screen readers). Stable identity means it runs once on mount,
  // not on every render.
  const focusAndSelect = useCallback((el: HTMLInputElement | null) => {
    el?.focus();
    el?.select();
  }, []);

  if (saved.length === 0) {
    return (
      <p className="mt-2 font-sans text-[0.76rem] leading-relaxed text-ink-faint">
        Your chats will appear here.
      </p>
    );
  }

  const startEdit = (c: Conversation) => {
    setEditingId(c.id);
    setDraft(c.title);
  };

  const commitEdit = () => {
    if (editingId) onRename(editingId, draft);
    setEditingId(null);
  };

  const onEditKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      commitEdit();
    } else if (e.key === "Escape") {
      e.preventDefault();
      setEditingId(null);
    }
  };

  const pick = (id: string) => {
    if (disabled) return;
    onSelect(id);
    onAfterSelect?.();
  };

  return (
    <ul className="mt-2 flex max-h-[42vh] flex-col gap-px overflow-y-auto">
      {saved.map((c) => {
        const active = c.id === activeId;
        if (editingId === c.id) {
          return (
            <li key={c.id} className="px-0.5 py-0.5">
              <input
                ref={focusAndSelect}
                aria-label="Rename chat"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={onEditKey}
                onBlur={commitEdit}
                className="w-full rounded-md border border-gold/40 bg-paper-3 px-2 py-1.5 font-sans text-[0.82rem] text-ink outline-none"
              />
            </li>
          );
        }
        return (
          <li key={c.id} className="group/row relative">
            <button
              type="button"
              onClick={() => pick(c.id)}
              disabled={disabled}
              title={c.title}
              className={`flex w-full items-center gap-2 rounded-md px-2 py-1.5 pr-7 text-left font-sans text-[0.82rem] transition duration-200 disabled:cursor-not-allowed disabled:opacity-60 ${
                active
                  ? "bg-paper-3 text-ink"
                  : "text-ink-soft hover:bg-paper-3 hover:text-ink"
              }`}
            >
              <span
                aria-hidden="true"
                className={`h-1.5 w-1.5 shrink-0 rounded-full transition ${
                  active ? "bg-gold" : "bg-transparent"
                }`}
              />
              <span className="flex-1 truncate">{c.title}</span>
            </button>

            <DropdownMenu.Root>
              <DropdownMenu.Trigger asChild>
                <button
                  type="button"
                  aria-label="Chat options"
                  className="absolute right-1 top-1/2 -translate-y-1/2 rounded p-1 text-ink-faint opacity-0 transition duration-200 hover:bg-paper-4 hover:text-ink focus-visible:opacity-100 group-hover/row:opacity-100 data-[state=open]:opacity-100"
                >
                  <MoreHorizontal className="h-3.5 w-3.5" />
                </button>
              </DropdownMenu.Trigger>
              <DropdownMenu.Portal>
                <DropdownMenu.Content
                  side="bottom"
                  align="end"
                  sideOffset={4}
                  className="z-50 min-w-[8rem] overflow-hidden rounded-lg border border-rule-strong bg-paper-4 p-1 shadow-[0_12px_32px_-12px_rgba(0,0,0,0.55)] data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95"
                >
                  <DropdownMenu.Item
                    onSelect={() => startEdit(c)}
                    className="flex cursor-pointer items-center gap-2 rounded-md px-2.5 py-1.5 font-sans text-[0.82rem] text-ink outline-none transition duration-200 data-[highlighted]:bg-paper-3"
                  >
                    <Pencil className="h-3.5 w-3.5 text-ink-faint" /> Rename
                  </DropdownMenu.Item>
                  <DropdownMenu.Item
                    onSelect={() => onDelete(c.id)}
                    className="flex cursor-pointer items-center gap-2 rounded-md px-2.5 py-1.5 font-sans text-[0.82rem] text-destructive outline-none transition duration-200 data-[highlighted]:bg-destructive/10"
                  >
                    <Trash2 className="h-3.5 w-3.5" /> Delete
                  </DropdownMenu.Item>
                </DropdownMenu.Content>
              </DropdownMenu.Portal>
            </DropdownMenu.Root>
          </li>
        );
      })}
    </ul>
  );
}
