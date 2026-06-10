import {
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import { useNavigate } from "react-router-dom";
import { Dialog } from "radix-ui";
import { ArrowDown, ArrowUp, Menu, Plus, Square } from "lucide-react";
import { useChatStream, type Message } from "@/hooks/useChatStream";
import { useTheme } from "@/hooks/useTheme";
import { useAuth } from "@/hooks/useAuth";
import Sidebar, { SidebarContent } from "@/components/Sidebar";
import Welcome from "@/components/Welcome";
import ChatMessage from "@/components/ChatMessage";

interface Turn {
  user: Message;
  assistant?: Message;
}

/** Honor the OS "reduce motion" setting for our JS-driven scrolls. */
function scrollBehavior(): ScrollBehavior {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches
    ? "auto"
    : "smooth";
}

export default function ChatPage() {
  const {
    messages,
    isStreaming,
    conversations,
    activeId,
    send,
    stop,
    reset,
    retry,
    selectConversation,
    deleteConversation,
    renameConversation,
  } = useChatStream();
  const { theme, toggle } = useTheme();
  const { logout, profile } = useAuth();
  const navigate = useNavigate();
  const [input, setInput] = useState("");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [showScrollDown, setShowScrollDown] = useState(false);
  const [liveStatus, setLiveStatus] = useState("");

  const onSignOut = () => {
    logout();
    navigate("/", { replace: true });
  };
  const scrollRef = useRef<HTMLDivElement>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);
  const lastTurnRef = useRef<HTMLDivElement>(null);
  const turnCount = useRef(0);
  const wasStreaming = useRef(false);

  const sidebarProps = {
    onNewChat: reset,
    disabled: isStreaming,
    theme,
    onToggleTheme: toggle,
    onSignOut,
    user: profile,
    conversations,
    activeId,
    onSelectConversation: selectConversation,
    onDeleteConversation: deleteConversation,
    onRenameConversation: renameConversation,
  };

  // Pair the flat message list into (question, answer) turns.
  const turns = useMemo<Turn[]>(() => {
    const out: Turn[] = [];
    for (let i = 0; i < messages.length; i++) {
      if (messages[i].role === "user") {
        const next = messages[i + 1];
        const assistant = next?.role === "assistant" ? next : undefined;
        out.push({ user: messages[i], assistant });
        if (assistant) i++;
      }
    }
    return out;
  }, [messages]);

  // Auto-grow the textarea up to a cap, then scroll inside it.
  useLayoutEffect(() => {
    const el = taRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [input]);

  // Focus the composer on load and whenever a stream finishes, so the next
  // question can be typed without reaching for the mouse.
  useEffect(() => {
    if (!isStreaming) taRef.current?.focus();
  }, [isStreaming]);

  // Announce stream start/finish ONCE via a single polite status region, instead
  // of letting the answer bubble re-announce its whole growing text every token.
  useEffect(() => {
    if (isStreaming && !wasStreaming.current) {
      setLiveStatus("Generating answer…");
    } else if (!isStreaming && wasStreaming.current) {
      // On failure the inline error (role="alert") announces; keep status quiet.
      setLiveStatus(messages.at(-1)?.error ? "" : "Answer ready.");
    }
    wasStreaming.current = isStreaming;
  }, [isStreaming, messages]);

  // On a NEW question, lift it to the top of the view so the answer has room
  // to stream in below it (ChatGPT-style), instead of staying pinned low.
  useEffect(() => {
    if (turns.length > turnCount.current) {
      lastTurnRef.current?.scrollIntoView({ behavior: scrollBehavior(), block: "start" });
    }
    turnCount.current = turns.length;
  }, [turns.length]);

  // Show a "jump to latest" affordance only once the reader has scrolled well
  // up past the current turn (the last turn reserves ~a viewport of space, so
  // the trigger sits beyond that to avoid firing during normal reading).
  const onScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
    setShowScrollDown(turns.length > 0 && distance > el.clientHeight * 1.2);
  };

  const scrollToBottom = () => {
    const el = scrollRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: scrollBehavior() });
  };

  const submit = () => {
    const q = input.trim();
    if (!q || isStreaming) return;
    setInput("");
    send(q);
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    submit();
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  // Clicking a starter question fires the search immediately — no detour
  // through the textarea / an extra Enter press.
  const pickStarter = (q: string) => {
    if (isStreaming) return;
    send(q);
  };

  return (
    <div className="relative flex h-screen overflow-hidden bg-paper text-ink">
      {/* Single polite live region for streaming status (a11y) — see effect above. */}
      <div role="status" className="sr-only">
        {liveStatus}
      </div>
      <Sidebar {...sidebarProps} />

      {/* mobile slide-in drawer — Radix handles focus trap, Escape, scroll lock */}
      <Dialog.Root open={drawerOpen} onOpenChange={setDrawerOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-40 bg-black/50 backdrop-blur-[2px] data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:animate-in data-[state=open]:fade-in-0 md:hidden" />
          <Dialog.Content className="fixed inset-y-0 left-0 z-50 flex w-72 max-w-[80vw] flex-col border-r border-rule bg-paper-2 px-5 py-7 shadow-[8px_0_32px_-12px_rgba(0,0,0,0.6)] outline-none data-[state=closed]:animate-out data-[state=closed]:slide-out-to-left data-[state=open]:animate-in data-[state=open]:slide-in-from-left md:hidden">
            <Dialog.Title className="sr-only">Menu</Dialog.Title>
            <Dialog.Description className="sr-only">
              Library, account and appearance.
            </Dialog.Description>
            <SidebarContent {...sidebarProps} onNavigate={() => setDrawerOpen(false)} />
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      <div className="relative z-10 flex flex-1 flex-col">
        {/* mobile top bar — the only nav on small screens (desktop uses the rail) */}
        <header className="flex items-center gap-2 border-b border-rule px-3 py-2.5 md:hidden">
          <button
            type="button"
            onClick={() => setDrawerOpen(true)}
            aria-label="Open menu"
            className="rounded-md p-1.5 text-ink-soft transition duration-200 hover:bg-paper-3 hover:text-ink"
          >
            <Menu className="h-5 w-5" />
          </button>
          <span className="font-serif text-base font-bold tracking-tight text-ink">
            <span className="text-gold" aria-hidden="true">◐</span> Policy Assistant
          </span>
          <button
            type="button"
            onClick={reset}
            disabled={isStreaming}
            aria-label="New chat"
            className="ml-auto rounded-md p-1.5 text-ink-soft transition duration-200 hover:bg-paper-3 hover:text-ink disabled:opacity-50"
          >
            <Plus className="h-5 w-5" />
          </button>
        </header>

        {/* top-edge fade — content dissolves into the paper (desktop only) */}
        <div className="pointer-events-none absolute inset-x-0 top-0 z-10 hidden h-9 bg-gradient-to-b from-paper to-transparent md:block" />

        <main ref={scrollRef} onScroll={onScroll} className="flex-1 overflow-y-auto">
          <div
            className={`mx-auto max-w-3xl px-5 ${
              turns.length === 0
                ? "flex min-h-full flex-col justify-center pb-10 pt-4"
                : "py-10"
            }`}
          >
            {turns.length === 0 ? (
              <Welcome onPick={pickStarter} name={profile?.name} />
            ) : (
              turns.map((t, ti) => {
                const isLast = ti === turns.length - 1;
                return (
                  <div
                    key={ti}
                    ref={isLast ? lastTurnRef : undefined}
                    className={`scroll-mt-6 ${isLast ? "min-h-[calc(100vh-7rem)]" : ""}`}
                  >
                    <ChatMessage message={t.user} isStreaming={false} />
                    {t.assistant && (
                      <ChatMessage
                        message={t.assistant}
                        isStreaming={isStreaming && isLast}
                        onRetry={isLast ? () => retry(t.user.content) : undefined}
                      />
                    )}
                  </div>
                );
              })
            )}
          </div>
        </main>

        {/* composer — pinned low, with a fade rising above it */}
        <div className="relative">
          <div className="pointer-events-none absolute inset-x-0 -top-10 h-10 bg-gradient-to-t from-paper to-transparent" />

          {showScrollDown && (
            <button
              type="button"
              onClick={scrollToBottom}
              aria-label="Scroll to latest"
              className="absolute -top-12 left-1/2 z-20 flex h-9 w-9 -translate-x-1/2 items-center justify-center rounded-full border border-rule-strong bg-paper-4 text-ink shadow-[0_8px_24px_-10px_rgba(0,0,0,0.5)] transition duration-200 hover:bg-paper-3"
            >
              <ArrowDown className="h-4 w-4" />
            </button>
          )}

          <div className="mx-auto max-w-3xl px-5 pb-5">
            <form
              onSubmit={onSubmit}
              className="flex items-end gap-2 rounded-[20px] border border-rule-strong bg-paper-4 px-2 py-1.5 shadow-[0_8px_24px_-10px_rgba(0,0,0,0.5)] transition duration-200 focus-within:border-gold/40"
            >
              <textarea
                ref={taRef}
                aria-label="Ask about the travel policy"
                rows={1}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder="Ask about the travel policy…  (Shift+Enter for a new line)"
                className="no-scrollbar max-h-[200px] flex-1 resize-none bg-transparent px-3 py-2 font-sans text-[0.92rem] text-ink outline-none placeholder:text-ink-faint"
              />
              {isStreaming ? (
                <button
                  type="button"
                  onClick={stop}
                  aria-label="Stop generating"
                  className="mb-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-ink text-paper transition duration-200 hover:bg-ink-soft"
                >
                  <Square className="h-3.5 w-3.5" fill="currentColor" />
                </button>
              ) : (
                <button
                  type="submit"
                  disabled={!input.trim()}
                  aria-label="Send"
                  className="mb-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-ink text-paper transition duration-200 hover:bg-ink-soft disabled:bg-paper-5 disabled:text-ink-faint"
                >
                  <ArrowUp className="h-5 w-5" />
                </button>
              )}
            </form>
          </div>
        </div>
      </div>

      <div className="brand-watermark" aria-hidden="true">◐</div>
    </div>
  );
}
