# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Senior Shield — a FastAPI backend that protects elderly people from phishing by dropping
fake test phishing emails into their mailbox. If the person falls for the trap (clicks the
trap link), a relative can subscribe to unlock a detailed audit. Built for a hackathon;
intended to be consumed by a Lovable frontend. Code comments and API messages are in French.

## Commands

```bash
# Local dev (SQLite, no external config needed for simulated mode)
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # fill in OAuth creds only if testing real Gmail
uvicorn main:app --reload     # interactive docs at http://localhost:8000/docs
```

There is no test suite, linter, or build step configured. Verify changes manually against
`/docs` (Swagger UI) or with curl.

## Architecture

Single-package FastAPI app; every module lives at the repo root and is imported flat
(`import gmail_client`, `from models import ...`). Request flow: `main.py` (routes) →
`schemas.py` (Pydantic validation) → `models.py` (SQLAlchemy ORM) → `database.py` (session).

- **`main.py`** — all routes and business logic. Auth is a hand-rolled `get_current_user`
  dependency that parses the `Authorization: Bearer <jwt>` header (no OAuth2 security
  scheme). `FREE_PHISHING_LIMIT = 3` and `BASE_URL`/`FRONT_URL` are module-level constants.
- **`security.py`** — bcrypt password hashing + HS256 JWT. Tokens encode the user id in
  `sub`; `decode_token` returns the id or `None`. The same `create_token`/`decode_token`
  pair is reused as the OAuth `state` to round-trip the user id through the Gmail callback.
- **`database.py`** — chooses SQLite (`senior_shield.db`) when `DATABASE_URL` is unset,
  Postgres otherwise. Auto-rewrites Render's `postgres://` → `postgresql://`. Tables are
  created on startup via `Base.metadata.create_all` — **there are no migrations**, so model
  changes against an existing DB require dropping/recreating the table or the local `.db`.
- **`phishing.py`** — static template bank (no AI). Templates contain a `{{LINK}}`
  placeholder that `main.py` replaces with the per-email trap URL, and `{prenom}` replaced
  in `generate_phishing_email`. `LEGIT_EMAILS` seeds a fresh account's inbox in simulated mode.
- **`gmail_client.py`** — Gmail OAuth2 + API integration.

### The two-mode dual-source design (most important to understand)

Inbox/email/phishing endpoints transparently switch between two backends based on
`User.gmail_connected` (a property that is true iff a `gmail_refresh_token` is stored):

- **Simulated mode** (default, no Gmail): emails live in the `emails` DB table. The inbox is
  the seeded `LEGIT_EMAILS` plus any phishing tests. `id` is the integer DB id (as a string).
- **Real mode** (Gmail connected): `/inbox` and `/emails/{id}` read the user's actual Gmail
  via the API; phishing tests are injected into the real mailbox using `messages.insert`
  (which does **not** send mail, so it bypasses spam filters) with scopes
  `gmail.readonly` + `gmail.insert`. `id` is the Gmail message id.

`EmailInboxOut.id` is therefore deliberately a `str` to carry either id type. A phishing email
is **always** recorded in the local `emails` table regardless of mode — that local row owns the
`link_token` (click tracking) and `gmail_message_id`, and is what `/audit` counts.

### Click tracking & the product gate

`/phishing/send` embeds `{BASE_URL}/track/click/{token}` where `token = os.urandom(16).hex()`.
Hitting that public route flips `email.clicked = True` and serves an awareness HTML page —
this is "falling for the trap". `/audit` aggregates sent/opened/clicked into a `risk_score`;
in real mode it lazily syncs `opened` state from Gmail's `UNREAD` label. The **free tier caps
at 3 phishing tests** (HTTP 402 beyond) and the **per-email audit `details` are gated behind
`subscription_active`** — that gating is the paid product, so don't expose `details` or
`is_phishing` to the senior-facing inbox responses.

## Conventions & gotchas

- **Never expose `is_phishing`** in any senior-facing response (`EmailInboxOut` omits it by
  design) — revealing which mails are tests defeats the exercise.
- **Never store the Gmail password** — only OAuth tokens. The refresh token is only returned
  on first consent; the callback keeps the existing one if Google omits it.
- CORS is wide open (`allow_origins=["*"]`) for the Lovable frontend.
- `render.yaml` deploys with `rootDir: senior_shield` and the README says `cd senior_shield`,
  but the actual code sits at the repo root — adjust paths if the deploy layout matters.
- Set a real `SECRET_KEY` in production; the default in `security.py` is a dev placeholder.
