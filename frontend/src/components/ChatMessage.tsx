import { memo, useState } from "react";
import { toast } from "sonner";
import { AlertTriangle, Check, Copy, RotateCw } from "lucide-react";
import Markdown from "@/components/Markdown";
import SourcesPanel from "@/components/SourcesPanel";
import ThinkingIndicator from "@/components/ThinkingIndicator";
import type { Message } from "@/hooks/useChatStream";

// Memoized so a streamed token (which only mutates the LAST message object)
// re-renders just the active assistant bubble — completed turns keep a stable
// `message` reference and a constant `isStreaming={false}`, so they skip render
// (and skip re-parsing their markdown) entirely.
const ChatMessage = memo(function ChatMessage({
  message,
  isStreaming,
  onRetry,
}: {
  message: Message;
  isStreaming: boolean;
  /** Provided only for the latest turn; renders an inline Retry when it errored. */
  onRetry?: () => void;
}) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard API can reject (insecure context / permission denied)
      toast.error("Couldn't copy to clipboard.");
    }
  };

  if (message.role === "user") {
    return (
      <div className="flex animate-user-in flex-col items-end pt-5 pb-5">
        <div className="mb-1.5 font-sans text-[0.7rem] font-semibold uppercase tracking-[0.12em] text-ink-soft">
          ◉&nbsp;&nbsp;You
        </div>
        <div className="max-w-[70%] whitespace-pre-wrap rounded-[20px] bg-paper-4 px-4 py-2.5 font-sans text-[0.88rem] leading-relaxed text-ink">
          {message.content}
        </div>
      </div>
    );
  }

  const empty = message.content.length === 0;

  return (
    <div
      className="group animate-msg-in border-t border-rule-strong pt-4"
      aria-busy={isStreaming}
    >
      <div className="mb-2 font-sans text-[0.7rem] font-semibold uppercase tracking-[0.12em] text-ink-soft">
        ◐&nbsp;&nbsp;Assistant
      </div>

      {message.error ? (
        // Failed turn: show any partial text that arrived, then a persistent
        // inline error with Retry (role="alert" so it's announced). This replaces
        // the old fire-and-forget toast.
        <>
          {!empty && <Markdown content={message.content} />}
          <div
            role="alert"
            className="mt-1 flex items-center gap-2.5 rounded-lg border border-rule-strong bg-paper-3/40 px-3 py-2.5 font-sans text-[0.84rem] text-ink-soft"
          >
            <AlertTriangle className="h-4 w-4 shrink-0 text-destructive" />
            <span>Couldn't reach the server.</span>
            {onRetry && (
              <button
                type="button"
                onClick={onRetry}
                className="ml-auto inline-flex items-center gap-1 font-medium text-ink transition duration-200 hover:text-gold"
              >
                <RotateCw className="h-3.5 w-3.5" /> Retry
              </button>
            )}
          </div>
        </>
      ) : empty && isStreaming ? (
        <ThinkingIndicator />
      ) : (
        /* A blinking caret trails the streaming answer via CSS (see .assistant-prose
           in index.css) instead of being concatenated into the markdown string —
           so a half-streamed table or code block never mis-parses. */
        <Markdown content={message.content} streaming={isStreaming} />
      )}

      {!empty && !isStreaming && !message.error && (
        <>
          <SourcesPanel content={message.content} />
          <div className="mt-3">
            <button
              type="button"
              onClick={copy}
              aria-label="Copy answer"
              className="inline-flex items-center gap-1.5 rounded-lg border border-rule-strong px-2.5 py-1 font-sans text-xs text-ink-muted transition duration-200 hover:bg-paper-3 hover:text-ink"
            >
              {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
        </>
      )}
    </div>
  );
});

export default ChatMessage;
