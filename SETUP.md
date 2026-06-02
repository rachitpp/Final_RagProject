# Setup Guide — Environment, pip & Packages

This guide takes you from a fresh machine to a running project. It explains
**what** each step does and **why**, so nothing feels like magic.

> **The 30-second version**
> ```powershell
> python -m venv venv                  # 1. create an isolated environment
> .\venv\Scripts\Activate.ps1          # 2. turn it on
> python -m pip install --upgrade pip  # 3. update the installer
> pip install -r requirements.txt      # 4. install the project's packages
> ```
> Then add your credentials to `.env` and run the app. Details below.

---

## 1. What is a virtual environment (and why bother)?

Python installs packages **globally** by default — every project on your
machine shares the same pile of libraries. That causes conflicts: Project A
needs `langchain 0.3`, Project B needs `0.1`, and they fight.

A **virtual environment** (`venv`) is a private box of Python + packages that
belongs to *one* project. Install whatever you want inside it; the rest of your
system is untouched. Delete the box and the project's packages vanish cleanly.

Think of it as a clean kitchen rented per recipe, instead of one shared kitchen
where every cook's ingredients pile up.

---

## 2. Create the virtual environment

From the project folder (`Final_RagProject`):

**Windows (PowerShell)**
```powershell
python -m venv venv
```

**macOS / Linux**
```bash
python3 -m venv venv
```

This creates a `venv/` folder holding a private copy of Python. You only do this
**once** per project.

> **Python version:** this project is developed on **Python 3.13**. Anything
> **3.10 or newer** is fine. Check yours with `python --version`.

---

## 3. Activate it (turn the box on)

Activating tells your terminal "use *this* project's Python, not the global one."

**Windows (PowerShell)**
```powershell
.\venv\Scripts\Activate.ps1
```

**macOS / Linux**
```bash
source venv/bin/activate
```

When it works, your prompt shows `(venv)` at the start of the line. You must
activate **every time** you open a new terminal to work on the project.

> **PowerShell error: "running scripts is disabled on this system"?**
> Windows blocks scripts by default. Allow them for your user once:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```
> Then run the activate command again.

To leave the environment later, just type `deactivate`.

---

## 4. Upgrade pip (the package installer)

`pip` is the tool that downloads and installs Python packages. The version that
ships inside a new venv is often outdated, which can cause confusing install
errors or slow downloads. Update it first:

```powershell
python -m pip install --upgrade pip
```

> **Why `python -m pip` and not just `pip`?** Writing `python -m pip`
> guarantees you're upgrading the pip that belongs to the Python you're actually
> using (your activated venv). It removes any doubt about *which* pip runs.

---

## 5. Install the project's packages

Every package this project needs is listed in **`requirements.txt`**. Install
them all in one command:

```powershell
pip install -r requirements.txt
```

`-r` means "read this requirements file and install everything in it." pip also
pulls in each package's own dependencies automatically.

### What you're actually installing

| Package | What it does in this project |
|---|---|
| `python-dotenv` | Loads your secret keys from the `.env` file into the program |
| `streamlit` | The web chat interface (`app.py`) |
| `langchain-core` | Core building blocks — documents, prompt templates |
| `langchain-text-splitters` | Splits long documents into overlapping chunks |
| `langchain-qdrant` | Connects LangChain to the Qdrant vector database |
| `qdrant-client` | Talks to **Qdrant Cloud**, where the document vectors live |
| `langchain-google-genai` | Calls **Google Gemini** (the LLM) and the embedding model |
| `pdfplumber` | Reads text **and tables** out of your PDF |
| `langsmith` | Optional tracing — lets you inspect each step of a query |

> **Note:** This project does **not** use PyTorch or sentence-transformers. All
> the AI runs in the cloud on Google Vertex AI, so installs stay small and fast.

---

## 6. Add your credentials (`.env`)

The project needs three secrets. Create a file named **`.env`** in the project
root:

```
GOOGLE_APPLICATION_CREDENTIALS=./your-service-account-key.json
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
QDRANT_API_KEY=your-qdrant-api-key
```

| Variable | Where to get it |
|---|---|
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to your GCP service-account JSON key. GCP Console → IAM & Admin → Service Accounts → Keys → Add Key |
| `GOOGLE_CLOUD_PROJECT` | Your GCP project ID (shown in the console header) |
| `QDRANT_API_KEY` | Qdrant Cloud dashboard → your cluster → API Keys |

The Qdrant cluster URL itself lives in `config/settings.py` (`qdrant_url`).

> **Keep `.env` private.** It contains secrets and should never be committed to
> git. (This project's `.gitignore` already excludes it.)

---

## 7. Run it

**First time only** — load your PDF into the vector database:
```powershell
python create_db.py
```
This reads the PDF, chunks it, creates embeddings, and uploads them to Qdrant.
Re-run it only when the PDF changes. (See `PIPELINE.md` for what happens inside.)

**Then start the assistant** — pick one:
```powershell
python main.py                  # command-line chat
python -m streamlit run app.py  # web interface
```

> **`streamlit` "not recognized" error?** Use `python -m streamlit run app.py`.
> Running it as a module avoids a Windows PATH issue where the `streamlit`
> shortcut isn't found.

---

## Quick troubleshooting

| Symptom | Cause & fix |
|---|---|
| `Activate.ps1 cannot be loaded` | Run the `Set-ExecutionPolicy` command in step 3 |
| `ModuleNotFoundError` after install | The venv isn't activated — look for `(venv)` in your prompt |
| `streamlit is not recognized` | Use `python -m streamlit run app.py` |
| `DefaultCredentialsError` (Google) | `.env` is missing or the GCP key path is wrong |
| `getaddrinfo failed` (Qdrant) | Network/DNS hiccup — check internet, then retry |

---

**Related docs**
- `PIPELINE.md` — how a question becomes an answer, step by step
- `OVERVIEW.md` — what the project is and the techniques behind it
