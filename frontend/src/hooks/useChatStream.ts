import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { AuthError, resetConversation, streamChat } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import {
  type Conversation,
  loadActiveId,
  loadConversations,
  newConversation,
  persistActiveId,
  persistConversations,
  titleFrom,
} from "@/lib/conversations";

export interface Message {
  role: "user" | "assistant";
  content: string;
  /** Set on the assistant turn when the request failed, so the UI can show a
   *  persistent inline retry instead of a vanishing toast. */
  error?: boolean;
}

const EMPTY: Message[] = [];

/** Pick the initial conversation list + active id from storage (once). */
function initState(): { conversations: Conversation[]; activeId: string } {
  const stored = loadConversations();
  if (stored.length > 0) {
    const saved = loadActiveId();
    const activeId = stored.some((c) => c.id === saved) ? (saved as string) : stored[0].id;
    return { conversations: stored, activeId };
  }
  const fresh = newConversation();
  return { conversations: [fresh], activeId: fresh.id };
}

export function useChatStream() {
  const navigate = useNavigate();
  const { logout } = useAuth();

  // One lazy initializer so the list and the active id come from a SINGLE
  // initState() call — splitting them into two initializers would let StrictMode
  // pair a list from one call with an active id from another.
  const [seed] = useState(initState);
  const [conversations, setConversations] = useState<Conversation[]>(seed.conversations);
  const [activeId, setActiveId] = useState<string>(seed.activeId);
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  // Persist only when idle: streaming mutates the list on every token, and we
  // don't want a localStorage write per token. The transition out of streaming
  // (and every select/new/delete/rename, which happen while idle) flushes the
  // final state.
  useEffect(() => {
    if (!isStreaming) persistConversations(conversations);
  }, [conversations, isStreaming]);

  useEffect(() => {
    persistActiveId(activeId);
  }, [activeId]);

  const messages = useMemo<Message[]>(
    () => conversations.find((c) => c.id === activeId)?.messages ?? EMPTY,
    [conversations, activeId],
  );

  // Replace the LAST message of a specific conversation (the streaming target),
  // preserving the identity of every other message object so completed bubbles
  // skip re-render / re-parse (see ChatMessage's memo).
  const updateLast = useCallback((convId: string, fn: (m: Message) => Message) => {
    setConversations((prev) =>
      prev.map((c) => {
        if (c.id !== convId) return c;
        const msgs = c.messages.slice();
        msgs[msgs.length - 1] = fn(msgs[msgs.length - 1]);
        return { ...c, messages: msgs, updatedAt: Date.now() };
      }),
    );
  }, []);

  const dropLast = useCallback((convId: string) => {
    setConversations((prev) =>
      prev.map((c) =>
        c.id === convId ? { ...c, messages: c.messages.slice(0, -1) } : c,
      ),
    );
  }, []);

  // Stream an answer into the trailing (empty) assistant message of `convId`,
  // which is captured at call time so a mid-stream conversation switch still
  // fills the conversation the question was asked in.
  const streamInto = useCallback(
    async (question: string, convId: string) => {
      const controller = new AbortController();
      abortRef.current = controller;
      setIsStreaming(true);

      let gotContent = false;
      try {
        for await (const chunk of streamChat(question, convId, controller.signal)) {
          gotContent = true;
          updateLast(convId, (last) => ({ ...last, content: last.content + chunk }));
        }
      } catch (err) {
        if (err instanceof AuthError && err.status === 401) {
          // Token missing/expired: drop the empty turn, clear shared auth state,
          // and bounce to login.
          dropLast(convId);
          logout();
          toast.error("Your session has expired. Please sign in again.");
          navigate("/login", { replace: true });
          return;
        }
        const aborted = (err as Error)?.name === "AbortError";
        if (aborted) {
          // User pressed Stop. Keep partial text; drop the bubble if empty.
          if (!gotContent) dropLast(convId);
        } else {
          // Hard failure: flag the assistant turn (keeping any partial text) so
          // the UI shows a persistent inline error + Retry.
          updateLast(convId, (last) => ({ ...last, error: true }));
        }
      } finally {
        setIsStreaming(false);
        abortRef.current = null;
      }
    },
    [updateLast, dropLast, navigate, logout],
  );

  const send = useCallback(
    async (question: string) => {
      const convId = activeId;
      // Append the user turn + an empty assistant turn we fill as tokens arrive,
      // and title the chat from its first question.
      setConversations((prev) =>
        prev.map((c) =>
          c.id === convId
            ? {
                ...c,
                title: c.messages.length === 0 ? titleFrom(question) : c.title,
                messages: [
                  ...c.messages,
                  { role: "user", content: question },
                  { role: "assistant", content: "" },
                ],
                updatedAt: Date.now(),
              }
            : c,
        ),
      );
      await streamInto(question, convId);
    },
    [activeId, streamInto],
  );

  // Re-run the most recent (failed) turn in place: clear the error + partial text
  // on the trailing assistant message, then stream into it again.
  const retry = useCallback(
    async (question: string) => {
      const convId = activeId;
      updateLast(convId, (last) =>
        last.role === "assistant" ? { role: "assistant", content: "" } : last,
      );
      await streamInto(question, convId);
    },
    [activeId, updateLast, streamInto],
  );

  const stop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  // Start a fresh chat: a new conversation (hence a new backend memory scope) at
  // the top, dropping any still-empty chats so the list doesn't accumulate them.
  const reset = useCallback(() => {
    abortRef.current?.abort();
    const fresh = newConversation();
    setConversations((prev) => [fresh, ...prev.filter((c) => c.messages.length > 0)]);
    setActiveId(fresh.id);
    toast("New chat started.", { duration: 1600 });
  }, []);

  const selectConversation = useCallback((id: string) => {
    abortRef.current?.abort();
    setActiveId(id);
  }, []);

  const deleteConversation = useCallback(
    (id: string) => {
      // Free the server-side memory for this id too (best-effort).
      resetConversation(id).catch(() => {});
      const remaining = conversations.filter((c) => c.id !== id);
      const nextList = remaining.length > 0 ? remaining : [newConversation()];
      setConversations(nextList);
      setActiveId((cur) =>
        nextList.some((c) => c.id === cur) ? cur : nextList[0].id,
      );
    },
    [conversations],
  );

  const renameConversation = useCallback((id: string, title: string) => {
    const trimmed = title.trim();
    if (!trimmed) return;
    setConversations((prev) =>
      prev.map((c) => (c.id === id ? { ...c, title: trimmed } : c)),
    );
  }, []);

  return {
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
  };
}
