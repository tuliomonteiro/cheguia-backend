# Cheguia

AI-powered guide for Brazilians and other newcomers navigating Paraguayan bureaucracy. Users can chat in Portuguese or Spanish and get grounded, source-cited answers about immigration, taxes, banking, utilities, and daily life in Paraguay.

This repo contains both the Django backend (root) and the Next.js frontend (`frontend/`).

---

## Table of Contents

- [Overview](#overview)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [API Reference](#api-reference)
- [Getting Started](#getting-started)
  - [With Docker (recommended)](#with-docker-recommended)
  - [Without Docker](#without-docker)
  - [Frontend (Next.js)](#frontend-nextjs)
- [Tests](#tests)
- [Environment Variables](#environment-variables)
- [Knowledge Base](#knowledge-base)
- [Settings](#settings)
- [Development Roadmap](#development-roadmap)

---

## Overview

Cheguia is a chat-based assistant that helps newcomers deal with Paraguayan bureaucracy. The Django backend exposes a REST API, consumed by the Next.js frontend in `frontend/` (a separate app within this repo, deployed independently).

Core features:

- **Conversational AI** — persistent chat sessions with full message history
- **RAG (Retrieval-Augmented Generation)** — answers are grounded in a curated knowledge base of Paraguay-specific documents, retrieved by vector similarity
- **JWT Authentication** — stateless, token-based auth with access/refresh token rotation
- **Multilingual** — responds in the language the user writes in (Portuguese or Spanish)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend framework | Django 4.2 + Django REST Framework |
| AI | LangChain + OpenAI `gpt-4o-mini` |
| Embeddings | OpenAI `text-embedding-3-small` (1536 dimensions) |
| Vector search | PostgreSQL + pgvector (HNSW index, cosine similarity) |
| Auth | djangorestframework-simplejwt (JWT bearer tokens) |
| Server | Gunicorn |
| Containerisation | Docker + docker-compose |
| Frontend framework | Next.js 16 (App Router, React 19, TypeScript) |
| Frontend styling | Tailwind CSS |

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                     Client                          │
│   Next.js app in frontend/ (JWT stored client-side)  │
│              or a mobile app                        │
└────────────────────┬────────────────────────────────┘
                     │ HTTP + JWT
┌────────────────────▼────────────────────────────────┐
│                    Gunicorn                         │
│              (WSGI process manager)                 │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│                Django + DRF                         │
│                                                     │
│  /api/auth/     → JWT register / login / me         │
│  /api/sessions/ → chat session management           │
│  /api/chat/     → stateless quick-chat              │
│  /api/health/   → health check                      │
└──────┬─────────────────────────┬───────────────────-┘
       │                         │
┌──────▼──────┐         ┌────────▼────────────────────┐
│  PostgreSQL  │         │       OpenAI API             │
│  + pgvector  │◄────────│  text-embedding-3-small      │
│              │  embed  │  gpt-4o-mini                 │
│  documents   │  query  └─────────────────────────────┘
│  embeddings  │
│  chat data   │
└─────────────┘
```

### RAG Flow

Every chat message triggers this pipeline before calling the LLM:

```
User message
    │
    ▼
text-embedding-3-small  ──►  1536-dimensional vector
    │
    ▼
HNSW index (cosine similarity, threshold ≤ 0.3)
    │
    ▼
Top-5 relevant document excerpts (≤ 4000 chars)
    │
    ▼
Injected into system prompt
    │
    ▼
gpt-4o-mini  ──►  Grounded answer + source URLs
```

If no documents match the threshold, the model answers from its own knowledge — no errors, no degradation.

---

## Project Structure

```
cheguia-backend/
├── ai/                         # AI processing layer
│   ├── embeddings.py           # OpenAI embeddings with cache
│   ├── rag.py                  # Vector similarity retrieval
│   ├── service.py              # LangChain chat + RAG orchestration
│   └── models.py               # AIInteraction, EmbeddingCache
│
├── chat/                       # Chat sessions and messages
│   ├── models.py               # ChatSession, Message
│   ├── serializers.py
│   ├── views.py                # Session CRUD + message send/receive
│   └── urls.py
│
├── documents/                  # Knowledge base
│   ├── models.py               # Document, DocumentTemplate
│   ├── serializers.py
│   └── management/
│       └── commands/
│           └── ingest_documents.py   # CLI to embed and load documents
│
├── users/                      # Authentication
│   ├── models.py               # Custom User (UUID pk, email login)
│   ├── serializers.py          # RegisterSerializer, UserSerializer
│   ├── views.py                # register, me
│   └── urls.py
│
├── api/                        # Shared / stateless endpoints
│   ├── views.py                # /api/chat/, /api/health/
│   └── urls.py
│
├── cheguia/                    # Django project config
│   ├── settings/
│   │   ├── base.py             # Shared settings (all secrets from env)
│   │   ├── dev.py              # DEBUG=True, AllowAny, localhost CORS
│   │   └── prod.py             # DEBUG=False, HTTPS headers, env-driven hosts
│   ├── urls.py
│   ├── wsgi.py                 # Defaults to prod settings
│   └── asgi.py
│
├── docker/
│   └── entrypoint.sh           # Waits for DB → migrate → start gunicorn
│
├── frontend/                   # Next.js chat UI (separate app, own package.json)
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx      # Wraps the app in AuthProvider
│   │   │   ├── page.tsx        # Chat UI: sessions sidebar + message thread
│   │   │   ├── login/page.tsx
│   │   │   └── register/page.tsx
│   │   └── lib/
│   │       ├── api.ts          # Typed fetch client for every backend endpoint
│   │       └── auth-context.tsx # JWT storage (localStorage) + auth state
│   ├── package.json
│   └── .env.example             # NEXT_PUBLIC_API_URL
│
├── Dockerfile
├── docker-compose.yml
├── gunicorn.conf.py
├── requirements.txt
└── .env.example
```

---

## API Reference

### Authentication — `/api/auth/`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/auth/register/` | Public | Create a new user account |
| POST | `/api/auth/token/` | Public | Login — returns `access` + `refresh` tokens |
| POST | `/api/auth/token/refresh/` | Public | Refresh an access token |
| GET | `/api/auth/me/` | Required | Return the authenticated user's profile |

**Register**
```json
POST /api/auth/register/
{
  "email": "user@example.com",
  "username": "joao",
  "password": "StrongPass123!",
  "password2": "StrongPass123!",
  "language_preference": "pt"
}
```

**Login**
```json
POST /api/auth/token/
{ "email": "user@example.com", "password": "StrongPass123!" }

→ { "access": "eyJ...", "refresh": "eyJ..." }
```

All subsequent requests must include:
```
Authorization: Bearer <access_token>
```

---

### Chat Sessions — `/api/`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/sessions/` | List all sessions for the authenticated user |
| POST | `/api/sessions/` | Create a new chat session |
| GET | `/api/sessions/{id}/` | Get a session with full message history |
| DELETE | `/api/sessions/{id}/` | Delete a session and all its messages |
| GET | `/api/sessions/{id}/messages/` | List messages in a session |
| POST | `/api/sessions/{id}/messages/` | Send a message — triggers AI response |

**Send a message**
```json
POST /api/sessions/{id}/messages/
{ "content": "Como obter o RUC no Paraguai?" }

→ 201
{
  "user": {
    "id": "...",
    "role": "user",
    "content": "Como obter o RUC no Paraguai?",
    "sources": [],
    "created_at": "2025-01-01T12:00:00Z"
  },
  "assistant": {
    "id": "...",
    "role": "assistant",
    "content": "O RUC é o número de identificação fiscal...",
    "sources": ["https://www.set.gov.py/..."],
    "created_at": "2025-01-01T12:00:01Z"
  }
}
```

---

### Other

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/chat/` | Required (dev: open) | Stateless quick-chat (no session history) |
| GET | `/api/health/` | Public | Health check |

---

## Getting Started

### With Docker (recommended)

**Prerequisites:** Docker and Docker Compose.

```bash
# 1. Clone the repository
git clone https://github.com/tuliomonteiro/cheguia-backend.git
cd cheguia-backend

# 2. Create your environment file
cp .env.example .env
# Edit .env — at minimum set SECRET_KEY and OPENAI_API_KEY

# 3. Build and start all services
docker compose up --build

# 4. (Optional) Load sample Paraguay knowledge base documents
docker compose exec web python manage.py ingest_documents --sample
```

The API will be available at **http://localhost:8000**.

The `entrypoint.sh` script automatically runs database migrations on every startup — no manual step needed.

---

### Without Docker

**Prerequisites:** Python 3.11+, PostgreSQL 14+ with the pgvector extension.

```bash
# 1. Clone and enter the project
git clone https://github.com/tuliomonteiro/cheguia-backend.git
cd cheguia-backend

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env
# Edit .env with your database credentials and API keys

# 5. Enable pgvector in PostgreSQL (run once, as a superuser)
psql -U postgres -c "CREATE EXTENSION IF NOT EXISTS vector;"

# 6. Run database migrations
python manage.py migrate

# 7. Start the development server
python manage.py runserver

# 8. (Optional) Load sample documents
python manage.py ingest_documents --sample
```

---

### Frontend (Next.js)

**Prerequisites:** Node.js 20+, and the backend running (Docker or bare-metal) on **http://localhost:8000**.

```bash
cd frontend

# 1. Install dependencies
npm install

# 2. Set up environment variables
cp .env.example .env.local
# Defaults to NEXT_PUBLIC_API_URL=http://localhost:8000 — adjust if the API runs elsewhere

# 3. Start the dev server
npm run dev
```

The UI will be available at **http://localhost:3000**. `cheguia/settings/dev.py` already whitelists `http://localhost:3000` in `CORS_ALLOWED_ORIGINS`, so no backend changes are needed for local dev.

Assistant replies render as sanitized Markdown (GFM — lists, tables, links; raw HTML is escaped and `javascript:` URLs neutralised), and each reply's RAG citations appear as deduplicated links to the official sources (`set.gov.py`, `migraciones.gov.py`, …). User messages always render as plain text.

The UI is localized to Portuguese and Spanish (`frontend/src/lib/i18n.ts`): a logged-in user's `language_preference` wins; before login the browser language decides, with Spanish as the fallback (matching the backend default). The register form includes a language selector that persists the choice to the backend. Sessions can be deleted from the sidebar (hover → ✕, with confirmation).

Auth uses JWT bearer tokens (no cookies): the token pair lives in `frontend/src/lib/token-store.ts` (in-memory, persisted to `localStorage`), and `frontend/src/lib/api.ts` attaches `Authorization: Bearer <access>` to every request. When an authenticated request gets a 401 (access token expired — 60-minute lifetime), the client transparently refreshes via `/api/auth/token/refresh/`, stores the rotated pair, and retries the request once; concurrent requests share a single in-flight refresh. Only a definitively rejected refresh token logs the user out — transient network failures never do. `AuthProvider` (`frontend/src/lib/auth-context.tsx`) subscribes to the token store so rotated tokens propagate to React state and a rejected refresh redirects to `/login`.

---

## Tests

The backend has an `APITestCase`/`SimpleTestCase` suite in each app's `tests.py`
(auth, sessions/messages, quick chat, AI service contracts, embedding cache,
pgvector retrieval, KB ingestion). AI is mocked at the seam — `get_response`
in view tests, the provider's `complete`/`embed` in service tests — so the
suite never hits a real AI API. The pgvector tests run against the real test
database, so Postgres with the `vector` extension must be reachable (same
requirement as `migrate`).

```bash
python manage.py test           # inside docker: docker compose exec web python manage.py test
```

CI (`.github/workflows/ci.yml`) runs the suite on every PR and push to `main`
against a pgvector service container — under `cheguia.settings.base`, so the
`IsAuthenticated` default is in force — plus `eslint` and `next build` for the
frontend.

Note: `api/chat/`'s permission is deliberately settings-dependent (open in dev,
JWT in base/prod), so its tests assert behavior, not auth; endpoints with
explicit `IsAuthenticated` decorators are tested for auth under any settings.

---

## Environment Variables

### Backend

Copy `.env.example` to `.env` and fill in the values.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | Yes | — | Django secret key (long random string) |
| `DJANGO_SETTINGS_MODULE` | No | `cheguia.settings.dev` | Settings module to use |
| `DB_NAME` | No | `paraguay_guide` | PostgreSQL database name |
| `DB_USER` | Yes | — | PostgreSQL user |
| `DB_PASSWORD` | No | `""` | PostgreSQL password |
| `DB_HOST` | No | `localhost` | Database host (`db` when using docker-compose) |
| `DB_PORT` | No | `5432` | Database port |
| `OPENAI_API_KEY` | Yes | — | OpenAI API key (`sk-...`) |
| `ALLOWED_HOSTS` | Prod only | — | Comma-separated list of allowed hostnames |
| `CORS_ALLOWED_ORIGINS` | Prod only | — | Comma-separated list of allowed CORS origins |

### Frontend (`frontend/.env.example` → `frontend/.env.local`)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | No | `http://localhost:8000` | Base URL of the Django backend. Exposed to the browser bundle — never put secrets here. |

---

## Knowledge Base

The RAG system uses documents stored in the `documents` table. Use the management command to populate it:

```bash
# Load bundled sample documents (RUC, residency, banking, ANDE)
python manage.py ingest_documents --sample

# Load from your own JSON file
python manage.py ingest_documents --file /path/to/docs.json

# Re-embed existing documents after content updates
python manage.py ingest_documents --sample --update
```

**JSON format for `--file`:**
```json
[
  {
    "title": "Como obter o RUC",
    "content": "O RUC é o número de identificação fiscal...",
    "document_type": "tax",
    "language": "pt",
    "source_url": "https://www.set.gov.py/"
  }
]
```

Valid `document_type` values: `immigration`, `tax`, `utilities`, `banking`, `general`.

---

## Settings

The settings are split into three files under `cheguia/settings/`:

| File | Used when | Key behaviour |
|------|-----------|---------------|
| `base.py` | Always (imported by dev and prod) | All secrets required from env; JWT auth; IsAuthenticated by default |
| `dev.py` | `manage.py runserver` (default) | `DEBUG=True`; `AllowAny` permissions; localhost CORS |
| `prod.py` | `wsgi.py` / `asgi.py` (default) | `DEBUG=False`; HTTPS/HSTS headers; `ALLOWED_HOSTS` and `CORS_ALLOWED_ORIGINS` from env |

To use production settings locally:
```bash
DJANGO_SETTINGS_MODULE=cheguia.settings.prod python manage.py runserver
```

---

## Development Roadmap

| Step | Status | Description |
|------|--------|-------------|
| 1 | Done | Settings split, secrets externalised, CORS fixed |
| 2 | Done | JWT authentication, DRF serializers, session management |
| 3 | Done | OpenAI integration with per-error HTTP handling |
| 4 | Done | pgvector RAG pipeline, HNSW index, document ingestion |
| 5 | Done | Docker, docker-compose, Gunicorn |
| 6 | Planned | Rate limiting, structured logging, Sentry |
| 7 | Done | Next.js frontend (`frontend/`) — auth, chat sessions, message thread |
| 8 | Planned | User subscriptions and premium features |
