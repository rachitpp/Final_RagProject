const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

/**
 * POST a question to /chat and yield the answer as plain-text chunks as they
 * stream in. `conversationId` scopes the server-side memory for follow-ups;
 * `signal` lets the caller cancel an in-flight generation.
 */
export async function* streamChat(
  question: string,
  conversationId: string,
  signal?: AbortSignal,
): AsyncGenerator<string> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, conversation_id: conversationId }),
    signal,
  });

  if (!res.ok || !res.body) {
    throw new Error(`Chat request failed: ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const text = decoder.decode(value, { stream: true });
    if (text) yield text;
  }
}

/** Clear this conversation's server-side memory (the 'New chat' action). */
export async function resetConversation(conversationId: string): Promise<void> {
  await fetch(`${API_BASE}/reset`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ conversation_id: conversationId }),
  });
}

export interface LibraryDoc {
  name: string;
  pages: number | null;
}

export interface LibraryInfo {
  documents: LibraryDoc[];
  total_pages: number;
  model: string;
}

/** Fetch the indexed-document library + active model for the sidebar. */
export async function fetchLibrary(): Promise<LibraryInfo> {
  const res = await fetch(`${API_BASE}/library`);
  if (!res.ok) throw new Error(`Library request failed: ${res.status}`);
  return res.json();
}
