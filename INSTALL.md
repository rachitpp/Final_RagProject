# Installation

How to install all dependencies for the **backend (FastAPI)** and the
**frontend (React + Vite)**.

## Prerequisites

- **Python 3.12+** (the backend `venv` is built on it)
- **Node.js 18+** (ships with `npm`) — check with `node -v`
- Credentials in `backend/.env` (Vertex AI service-account JSON + Qdrant API key
  + `QDRANT_URL` cluster endpoint — see `backend/.env.example`)

---

## 1. Backend — FastAPI (Python)

Everything is pinned in `backend/requirements.txt`. Install it into the project's
virtual environment.

```bash
cd backend
python -m venv venv          # only if venv/ doesn't exist yet
./venv/bin/python -m pip install -r requirements.txt
```

> **Why `./venv/bin/python -m pip` and not just `pip`?**
> If you use Anaconda, a bare `pip` can resolve to conda's pip and install into
> the wrong place — even when `(venv)` shows in your prompt. Always call the
> venv's interpreter explicitly.

The key packages this installs (on top of the existing RAG stack —
LangChain, Qdrant, pdfplumber, etc.):

```
fastapi              # the API framework
uvicorn[standard]    # ASGI server
sse-starlette        # streaming responses
python-multipart     # form parsing (login)
pyjwt                # JWT auth tokens
openpyxl             # read the .xlsx employee sheet
pandas               # load / validate that sheet
```

If you ever need to install just those directly:

```bash
./venv/bin/python -m pip install fastapi "uvicorn[standard]" sse-starlette python-multipart pyjwt openpyxl pandas
```

---

## 2. Frontend — React + Vite

All packages are listed in `frontend/package.json`, so one command installs them:

```bash
cd frontend
npm install
```

The key packages this installs:

```
react, react-dom, vite, typescript     # base app (Vite scaffold)
tailwindcss, @tailwindcss/vite          # styling
react-router-dom                        # routing (/login, /chat)
react-markdown, remark-gfm              # render markdown answers + tables
sonner                                  # toast notifications
lucide-react                            # icons
@fontsource-variable/source-serif-4     # serif body font
@fontsource-variable/geist              # sans UI font
ai, @ai-sdk/react                       # AI SDK (streaming helpers)
```

> **shadcn/ui** components live in `src/components/ui` and are configured via
> `components.json` (already set up). To add a new one later:
> `npx shadcn@latest add <component>`.

---

## 3. Run both (two terminals)

```bash
# Terminal 1 — backend  → http://localhost:8000
cd backend
./venv/bin/python -m uvicorn api.main:app --reload --port 8000

# Terminal 2 — frontend → http://localhost:5173
cd frontend
npm run dev
```

> Run the backend **from inside `backend/`** with `./venv/bin/python -m uvicorn`
> (not the bare `uvicorn` command — the venv's console scripts can have a stale
> path if the folder was moved).

Open **http://localhost:5173** in your browser.
