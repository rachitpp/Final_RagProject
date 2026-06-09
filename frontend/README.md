# Policy Assistant — Frontend

React 19 + Vite + TypeScript + Tailwind v4 chat client for the travel & leave
policy RAG assistant. Talks to the FastAPI backend in [`../backend`](../backend).

## Develop

```bash
npm install        # requires Node.js 18+ on PATH
npm run dev        # http://localhost:5173
```

The backend must be running (default `http://localhost:8000`). Override the API
base with the `VITE_API_BASE` env var.

## Scripts

- `npm run dev` — Vite dev server with HMR
- `npm run build` — type-check (`tsc -b`) + production build to `dist/`
- `npm run lint` — ESLint
- `npm run preview` — serve the production build locally

## Where things live

- `src/pages/` — `ChatPage` (the chat screen), `AuthPage` (login / activate)
- `src/hooks/` — `useChatStream` (chat state), `AuthProvider` + `useAuth`
  (session), `useTheme`
- `src/lib/api.ts` — backend calls (`streamChat`, `login`, `activate`,
  `fetchLibrary`, …)
- `src/components/` — `Sidebar`, `Welcome`, `ChatMessage`, `Markdown`,
  `ThinkingIndicator`, route `guards`

See [`CLAUDE.md`](CLAUDE.md) for conventions and
[`../docs/OVERVIEW.md`](../docs/OVERVIEW.md) for the full narrative.
