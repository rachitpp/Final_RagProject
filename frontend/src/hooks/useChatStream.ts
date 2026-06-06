import { useCallback, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { AuthError, resetConversation, streamChat } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";

export interface Message {
  role: "user" | "assistant";
  content: string;
  /** Set on the assistant turn when the request failed, so the UI can show a
   *  persistent inline retry instead of a vanishing toast. */
  error?: boolean;
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
  const navigate = useNavigate();
  const { logout } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [conversationId, setConversationId] = useState<string>(loadConversationId);
  const abortRef = useRef<AbortController | null>(null);

  // Stream an answer into the assistant message currently LAST in the list
  // (appended by send, or cleared in place by retry), filling it as tokens
  // arrive. On a hard failure we flag that message `error` and keep it, so the
  // turn can render an inline retry.
  const streamInto = useCallback(
    async (question: string) => {
      const controller = new AbortController();
      abortRef.current = controller;
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
        if (err instanceof AuthError && err.status === 401) {
          // Token missing/expired: drop the turn, clear the shared auth state
          // (so the guards see it everywhere), and bounce to login.
          setMessages((prev) => prev.slice(0, -1));
          logout();
          toast.error("Your session has expired. Please sign in again.");
          navigate("/login", { replace: true });
          return;
        }
        const aborted = (err as Error)?.name === "AbortError";
        if (aborted) {
          // User pressed Stop. Keep partial text; drop the bubble if empty.
          if (!gotContent) setMessages((prev) => prev.slice(0, -1));
        } else {
          // Hard failure: flag the assistant turn (keeping any partial text) so the
          // UI shows a persistent inline error + Retry instead of a fleeting toast.
          setMessages((prev) => {
            const next = [...prev];
            const last = next[next.length - 1];
            next[next.length - 1] = { ...last, error: true };
            return next;
          });
        }
      } finally {
        setIsStreaming(false);
        abortRef.current = null;
      }
    },
    [conversationId, navigate, logout],
  );

  const send = useCallback(
    async (question: string) => {
      // Append the user turn + an empty assistant turn we fill as tokens arrive.
      setMessages((prev) => [
        ...prev,
        { role: "user", content: question },
        { role: "assistant", content: "" },
      ]);
      await streamInto(question);
    },
    [streamInto],
  );

  // Re-run the most recent (failed) turn in place: clear the error + any partial
  // text on the trailing assistant message, then stream into it again. Only the
  // last turn is ever offered a Retry, so the trailing message is the failed one
  // — this avoids the duplicate-question bug a plain re-send would cause.
  const retry = useCallback(
    async (question: string) => {
      setMessages((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last?.role === "assistant") {
          next[next.length - 1] = { role: "assistant", content: "" };
        }
        return next;
      });
      await streamInto(question);
    },
    [streamInto],
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

  return { messages, isStreaming, send, stop, reset, retry };
}
