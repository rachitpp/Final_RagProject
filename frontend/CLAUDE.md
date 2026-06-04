# frontend/CLAUDE.md

React 19 + Vite + TypeScript + Tailwind v4 chat client for the RAG backend.
Project-wide rules: root [`CLAUDE.md`](../CLAUDE.md). Full narrative:
[`../docs/OVERVIEW.md`](../docs/OVERVIEW.md).

## Layout

- `src/pages/ChatPage.tsx` — the whole chat screen (composer, auto-grow
  textarea, Enter-to-send / Shift+Enter newline, ChatGPT-style scroll, Stop
  button, starter questions).
- `src/hooks/useChatStream.ts` — chat state. Appends a user turn + empty
  assistant turn, fills it as tokens arrive. Persists `conversation_id` in
  `localStorage`. Handles Stop (keep partial) and failures (drop turn + Retry toast).
- `src/lib/api.ts` — `streamChat()` (reads `POST /chat` body as a stream),
  `resetConversation()`, `fetchLibrary()`.
- `src/components/` — `Sidebar`, `Welcome`, `ChatMessage`, `Markdown`
  (react-markdown + remark-gfm), `ThinkingIndicator`, `ui/button`.
- `src/hooks/useTheme.ts` — light/dark. Toasts via `sonner`.

## Frontend-specific rules

- **Import alias `@` → `src/`** (configured in `vite.config.ts`) — use
  `@/components/...`, not long relative paths.
- **The API contract is a plain-text token stream**, not JSON/SSE. Read the
  response body with a reader and append chunks; don't `await res.json()`.
- **Always send `conversation_id`** on `/chat` and `/reset` — it scopes server
  memory and must survive refresh (hence localStorage).
- **API base from `VITE_API_BASE`** (default `http://localhost:8000`) — don't
  hardcode the URL.

## Gotchas

- **Requires Node.js 18+ on PATH** (`node -v`). `npm` failing with "not
  recognized" means Node isn't installed/on PATH — install it, reopen the terminal.
- The backend's CORS allowlist (`api/main.py`) only includes `localhost:5173`
  and `127.0.0.1:5173`; add the deployed origin there before deploying.
- `README.md` here is still the **stock Vite template** — not app docs.
