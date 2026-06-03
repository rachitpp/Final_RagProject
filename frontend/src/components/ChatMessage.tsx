import { useState } from "react";
import { Check, Copy } from "lucide-react";
import Markdown from "@/components/Markdown";
import ThinkingIndicator from "@/components/ThinkingIndicator";
import type { Message } from "@/hooks/useChatStream";

export default function ChatMessage({
  message,
  isStreaming,
}: {
  message: Message;
  isStreaming: boolean;
}) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
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
  // A subtle cursor at the tail while the answer is still streaming.
  const display = isStreaming && !empty ? message.content + " ▌" : message.content;

  return (
    <div className="group animate-msg-in border-t border-rule-strong pt-4">
      <div className="mb-2 font-sans text-[0.7rem] font-semibold uppercase tracking-[0.12em] text-ink-soft">
        ◐&nbsp;&nbsp;Assistant
      </div>

      {empty && isStreaming ? <ThinkingIndicator /> : <Markdown content={display} />}

      {!empty && !isStreaming && (
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
      )}
    </div>
  );
}
