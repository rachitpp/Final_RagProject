# Roadmap

## ⭐ Next major turning point: per-employee auth + band-aware personalization

> Planned, not yet built — but the groundwork is already visible in the
> dependencies. This is the most important upcoming change to the project.

The policies answer differently **depending on the employee's grade/band** — the
`compute_entitlement` tool and the rate tables are already organized by band
(e.g. `9/10`). Today the **user has to know and state their band** in every
question. The turning point is to make the assistant **know who is asking** and
**automatically scope every answer to that person's band.**

### The signal this is coming
`backend/requirements.txt` already pins packages the current code does **not**
use yet (there are no auth/login/employee routes in `api/routes/` — only `chat`,
`health`, `meta`):

| Package | Pinned for (per `INSTALL.md`) |
|---|---|
| `pyjwt` | JWT auth tokens |
| `python-multipart` | form parsing (**login**) |
| `openpyxl` | read the **.xlsx employee sheet** |
| `pandas` | load / validate that sheet |

### What this milestone will likely involve
1. A **login flow** — `POST /login` (form parsed via `python-multipart`),
   issuing a **JWT** (`pyjwt`) that the frontend stores and sends on each `/chat`.
2. An **employee directory** — load an `.xlsx` roster (`openpyxl` + `pandas`)
   mapping each employee to their **band**, validated at startup.
3. **Band-aware answers** — inject the authenticated user's band into the
   pipeline so retrieval/pinning and `compute_entitlement` resolve *their* exact
   entitlement without the user stating their band.
4. **Frontend auth** — a login page/route (`react-router-dom` is already a
   dependency), auth state, attaching the JWT to API calls, and a logout action.
5. A **persistent conversation store** (the in-memory `ConversationStore` is
   already flagged "swap for Redis/DB later") so history survives restarts and
   ties to a real user identity.

### Why it's a turning point
It shifts the app from an anonymous Q&A demo into a **personalized,
authenticated internal tool** — the difference between "look up the policy" and
"tell *me* what *I* can claim." It touches auth, the data model (employees +
bands), the retrieval grounding, and the entire frontend session lifecycle.

> Confirm this is still the intended direction before building it — the plan was
> inferred from the unused-but-pinned dependencies, not from an explicit spec.
