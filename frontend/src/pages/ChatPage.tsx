import {
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import { ArrowUp, Square } from "lucide-react";
import { useChatStream, type Message } from "@/hooks/useChatStream";
import { useTheme } from "@/hooks/useTheme";
import Sidebar from "@/components/Sidebar";
import Welcome from "@/components/Welcome";
import ChatMessage from "@/components/ChatMessage";

interface Turn {
  user: Message;
  assistant?: Message;
}

export default function ChatPage() {
  const { messages, isStreaming, send, stop, reset } = useChatStream();
  const { theme, toggle } = useTheme();
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);
  const lastTurnRef = useRef<HTMLDivElement>(null);
  const turnCount = useRef(0);

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

  // On a NEW question, lift it to the top of the view so the answer has room
  // to stream in below it (ChatGPT-style), instead of staying pinned low.
  useEffect(() => {
    if (turns.length > turnCount.current) {
      lastTurnRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    turnCount.current = turns.length;
  }, [turns.length]);

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
      <Sidebar
        onNewChat={reset}
        disabled={isStreaming}
        theme={theme}
        onToggleTheme={toggle}
      />

      <div className="relative z-10 flex flex-1 flex-col">
        {/* top-edge fade — content dissolves into the paper */}
        <div className="pointer-events-none absolute inset-x-0 top-0 z-10 h-9 bg-gradient-to-b from-paper to-transparent" />

        <main ref={scrollRef} className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-3xl px-5 py-10">
            {turns.length === 0 ? (
              <Welcome onPick={pickStarter} />
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

          <div className="mx-auto max-w-3xl px-5 pb-5">
            <form
              onSubmit={onSubmit}
              className="flex items-end gap-2 rounded-[20px] border border-rule-strong bg-paper-4 px-2 py-1.5 shadow-[0_8px_24px_-10px_rgba(0,0,0,0.5)] transition duration-200 focus-within:border-gold/40"
            >
              <textarea
                ref={taRef}
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
