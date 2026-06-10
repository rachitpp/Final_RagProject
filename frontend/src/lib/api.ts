const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

// ───────────────────────────── Auth ─────────────────────────────
// The JWT lives in localStorage; it's the only thing we persist about the
// session. Band/role are never stored client-side — they're resolved
// server-side from the token on every request.
//
// Storage choice — localStorage (decision, not an accident): simple, survives
// refresh, works with the Bearer-header flow below, and avoids CSRF (no ambient
// cookie). The tradeoff is XSS exposure: a script on the page could read the
// token. We accept it for an internal tool with a tiny first-party surface; the
// more hardened alternative is an httpOnly, SameSite cookie set by the server
// (immune to XSS reads, but then you must handle CSRF). Revisit before any
// public/multi-tenant exposure.
const TOKEN_KEY = "auth_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

/** Error carrying the HTTP status so callers can branch on it (e.g. 401). */
export class AuthError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "AuthError";
    this.status = status;
  }
}

interface TokenResponse {
  access_token: string;
  token_type: string;
}

/** Pull a human-readable message out of a FastAPI error body (string detail
 * or a pydantic validation array), falling back to a generic line. */
async function errorMessage(res: Response): Promise<string> {
  try {
    const data = await res.json();
    const detail = data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length) {
      return detail.flatMap((e: { msg?: string }) => (e.msg ? [e.msg] : [])).join("; ");
    }
  } catch {
    /* non-JSON body */
  }
  return `Request failed (${res.status}).`;
}

async function postForToken(
  path: string,
  body: Record<string, unknown>,
): Promise<TokenResponse> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new AuthError(await errorMessage(res), res.status);
  return res.json();
}

/** Sign in with employee id + password; stores the JWT on success. */
export async function login(employeeId: string, password: string): Promise<void> {
  const { access_token } = await postForToken("/auth/login", {
    employee_id: employeeId,
    password,
  });
  setToken(access_token);
}

/** First-time activation: prove identity (id + roster email), set a password.
 * The backend returns a token, so the user is signed in immediately. */
export async function activate(
  employeeId: string,
  email: string,
  password: string,
): Promise<void> {
  const { access_token } = await postForToken("/auth/activate", {
    employee_id: employeeId,
    email,
    password,
  });
  setToken(access_token);
}

/** Clear the session (sign out). */
export function logout(): void {
  clearToken();
}

/** Authorization header for protected calls, or {} when signed out. */
function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/** The signed-in user's own profile (from GET /auth/me). Band is shown to the
 * user as their own; it's never trusted from the client for personalization. */
export interface Profile {
  employee_id: string;
  name: string;
  band: number;
  role: string;
}

/** Fetch the current user's profile. Throws AuthError(401) if the token is
 * missing/expired so the caller can sign out. */
export async function fetchMe(): Promise<Profile> {
  const res = await fetch(`${API_BASE}/auth/me`, { headers: { ...authHeaders() } });
  if (res.status === 401) {
    clearToken();
    throw new AuthError("Your session has expired. Please sign in again.", 401);
  }
  if (!res.ok) throw new Error(`Profile request failed: ${res.status}`);
  return res.json();
}

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
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ question, conversation_id: conversationId }),
    signal,
  });

  if (res.status === 401) {
    clearToken();
    throw new AuthError("Your session has expired. Please sign in again.", 401);
  }
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
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ conversation_id: conversationId }),
  });
}

export interface LibraryDoc {
  name: string;
  /** Employee-facing policy title from the backend registry (e.g. "Domestic Travel"). */
  title: string;
  /** Topic key the UI maps to an icon (the retrieval scope: domestic | foreign | leave). */
  topic: string;
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
