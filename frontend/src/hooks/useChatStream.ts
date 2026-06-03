import { useCallback, useRef, useState } from "react";
import { toast } from "sonner";
import { resetConversation, streamChat } from "@/lib/api";

export interface Message {
  role: "user" | "assistant";
  content: string;
}

const STORAGE_KEY = "conversation_id";

/** Persist the conversation id so a refresh keeps the same chat memory. */
function loadConversationId(): string {
  let id = localStorage.getItem(STORAGE_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(STORAGE_KEY, id);
  }
  return id;
}

export function useChatStream() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [conversationId, setConversationId] = useState<string>(loadConversationId);
  const abortRef = useRef<AbortController | null>(null);

  const send = useCallback(
    async (question: string) => {
      const controller = new AbortController();
      abortRef.current = controller;

      // Append the user turn + an empty assistant turn we fill as tokens arrive.
      setMessages((prev) => [
        ...prev,
        { role: "user", content: question },
        { role: "assistant", content: "" },
      ]);
      setIsStreaming(true);

      let gotContent = false;
      try {
        for await (const chunk of streamChat(question, conversationId, controller.signal)) {
          gotContent = true;
          setMessages((prev) => {
            const next = [...prev];
            const last = next[next.length - 1];
            next[next.length - 1] = { ...last, content: last.content + chunk };
            return next;
          });
        }
      } catch (err) {
        const aborted = (err as Error)?.name === "AbortError";
        if (aborted) {
          // User pressed Stop. Keep partial text; drop the bubble if empty.
          if (!gotContent) setMessages((prev) => prev.slice(0, -1));
        } else {
          // Hard failure: remove the broken assistant turn, offer a retry.
          setMessages((prev) => prev.slice(0, -1));
          toast.error("Couldn't reach the server.", {
            action: { label: "Retry", onClick: () => void send(question) },
          });
        }
      } finally {
        setIsStreaming(false);
        abortRef.current = null;
      }
    },
    [conversationId],
  );

  const stop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const reset = useCallback(async () => {
    abortRef.current?.abort();
    try {
      await resetConversation(conversationId);
    } catch {
      // ignore network errors on reset
    }
    const id = crypto.randomUUID();
    localStorage.setItem(STORAGE_KEY, id);
    setConversationId(id);
    setMessages([]);
    toast("New chat started.", { duration: 1600 });
  }, [conversationId]);

  return { messages, isStreaming, send, stop, reset };
}
