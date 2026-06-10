import type { Message } from "@/hooks/useChatStream";

/**
 * Client-side conversation history.
 *
 * The backend keeps per-`conversation_id` memory in-process but exposes no way
 * to LIST a user's past chats, so the transcript list lives here in
 * localStorage. Each conversation owns its own id, which is the same id sent to
 * the backend as `conversation_id` — so follow-ups in an old chat still hit the
 * right server-side memory (until the server restarts; the visible transcript
 * survives regardless).
 *
 * Single-store, not namespaced per user: this matches the prior behaviour (the
 * old single `conversation_id` was global too) and suits the internal-tool
 * threat model. Revisit if multiple employees ever share one browser profile.
 */
export interface Conversation {
  id: string;
  /** Derived from the first question; shown in the sidebar list. */
  title: string;
  messages: Message[];
  createdAt: number;
  updatedAt: number;
}

const STORE_KEY = "conversations_v1";
const ACTIVE_KEY = "active_conversation_id";
/** Cap stored chats so localStorage can't grow without bound. */
const MAX_CONVERSATIONS = 50;

/** A new, empty conversation with a fresh id (its backend `conversation_id`). */
export function newConversation(): Conversation {
  const now = Date.now();
  return { id: crypto.randomUUID(), title: "New chat", messages: [], createdAt: now, updatedAt: now };
}

/** First line of the opening question, trimmed to a tidy sidebar label. */
export function titleFrom(question: string): string {
  const firstLine = question.trim().split("\n")[0].trim();
  if (firstLine.length <= 48) return firstLine || "New chat";
  return firstLine.slice(0, 47).trimEnd() + "…";
}

/** Load saved conversations (newest first), tolerating a corrupt/missing store. */
export function loadConversations(): Conversation[] {
  try {
    const raw = localStorage.getItem(STORE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    // Keep only well-formed rows so one bad entry can't break the whole list.
    return parsed.filter(
      (c): c is Conversation =>
        c && typeof c.id === "string" && Array.isArray(c.messages),
    );
  } catch {
    return [];
  }
}

/** Persist conversations — drops empty chats and caps the count (newest kept). */
export function persistConversations(list: Conversation[]): void {
  try {
    const keep = list
      .filter((c) => c.messages.length > 0)
      .sort((a, b) => b.updatedAt - a.updatedAt)
      .slice(0, MAX_CONVERSATIONS);
    localStorage.setItem(STORE_KEY, JSON.stringify(keep));
  } catch {
    // quota / private-mode write failures are non-fatal — history is best-effort
  }
}

export function loadActiveId(): string | null {
  return localStorage.getItem(ACTIVE_KEY);
}

export function persistActiveId(id: string): void {
  try {
    localStorage.setItem(ACTIVE_KEY, id);
  } catch {
    /* non-fatal */
  }
}
