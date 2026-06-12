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
 * NAMESPACED PER USER: every key is suffixed with the signed-in employee_id, so
 * each account on this browser has its own bucket — signing in as a different
 * employee must never surface the previous user's transcripts (mirrors the
 * backend, which scopes its memory by employee_id:conversation_id). Transcripts
 * do remain in localStorage after sign-out, readable via devtools — the same
 * accepted internal-tool tradeoff as the JWT in lib/api.ts.
 */
export interface Conversation {
  id: string;
  /** Derived from the first question; shown in the sidebar list. */
  title: string;
  messages: Message[];
  createdAt: number;
  updatedAt: number;
}

const STORE_PREFIX = "conversations_v1";
const ACTIVE_PREFIX = "active_conversation_id";
/** Cap stored chats so localStorage can't grow without bound. */
const MAX_CONVERSATIONS = 50;

const storeKey = (userId: string) => `${STORE_PREFIX}:${userId}`;
const activeKey = (userId: string) => `${ACTIVE_PREFIX}:${userId}`;

// The pre-namespacing build kept ONE global bucket under these bare keys. That
// data names no owner, and showing it to whoever signs in next is exactly the
// cross-user leak the namespacing fixes — so it's deleted, never migrated.
try {
  localStorage.removeItem(STORE_PREFIX);
  localStorage.removeItem(ACTIVE_PREFIX);
} catch {
  /* private mode — nothing stored there anyway */
}

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

/** Load the user's saved conversations (newest first), tolerating a
 * corrupt/missing store. */
export function loadConversations(userId: string): Conversation[] {
  try {
    const raw = localStorage.getItem(storeKey(userId));
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

/** Persist the user's conversations — drops empty chats and caps the count
 * (newest kept). */
export function persistConversations(userId: string, list: Conversation[]): void {
  try {
    const keep = list
      .filter((c) => c.messages.length > 0)
      .sort((a, b) => b.updatedAt - a.updatedAt)
      .slice(0, MAX_CONVERSATIONS);
    localStorage.setItem(storeKey(userId), JSON.stringify(keep));
  } catch {
    // quota / private-mode write failures are non-fatal — history is best-effort
  }
}

export function loadActiveId(userId: string): string | null {
  return localStorage.getItem(activeKey(userId));
}

export function persistActiveId(userId: string, id: string): void {
  try {
    localStorage.setItem(activeKey(userId), id);
  } catch {
    /* non-fatal */
  }
}
