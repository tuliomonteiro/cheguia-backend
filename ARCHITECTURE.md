# Cheguia — System Architecture

Cheguia helps Brazilians and other newcomers navigate Paraguayan bureaucracy
(immigration, SET/RUC taxes, ANDE, banking) through a chat assistant whose answers are
grounded in a curated knowledge base and cited to official sources.

This document describes the system **as built**. For setup, API examples, and env-var
tables see `README.md`; for contributor rules and known traps see `CLAUDE.md`.

## Components

| Component | Where | What |
|---|---|---|
| Backend | repo root | Django 4.2 + DRF; JWT auth, chat sessions, RAG pipeline, provider adapters |
| Frontend | `frontend/` | Next.js 16 (App Router, React 19, TS, Tailwind 4); deployed independently |
| Database | PostgreSQL + pgvector | Relational data + 1536-dim vectors, HNSW-indexed |
| AI providers | OpenAI (chat + embeddings), Gemini (chat) | Behind an adapter registry — nothing else knows SDKs |
| CI | `.github/workflows/ci.yml` | Backend tests (pgvector service container, `base` settings) + frontend lint/build on every PR |

## Anatomy of a chat turn

```
POST /api/sessions/{id}/messages/   (Authorization: Bearer <access>)
  │
  ├─ JWT authentication (simplejwt) → 401 if invalid/expired
  ├─ ChatRateThrottle ('chat' scope, default 15/min) → 429 BEFORE any AI spend
  ├─ Ownership check (session belongs to user) → 404 otherwise
  ├─ Serializer validation → 400
  │
  ├─ user Message row created
  ├─ history = last 10 messages of the session (oldest first)
  │
  ├─ ai.service.get_response(content, history)
  │     ├─ _try_rag(): embed query → cosine search → (context, sources)
  │     │     └─ ANY failure logs + degrades to ("", []) — RAG is never fatal
  │     ├─ _build_messages(): system prompt (+context), history capped at 10,
  │     │     roles other than user/assistant silently dropped
  │     └─ provider.complete(messages)  — 30s timeout
  │           └─ SDK errors → AIServiceError(message, status_code)
  │
  ├─ on AIServiceError: user Message DELETED (no orphan turn),
  │     response = {'error': str} with the adapter's status code
  └─ on success: assistant Message stored (content + sources),
        session auto-titled from first user message (content[:80]),
        201 with {'user': …, 'assistant': …}
```

`POST /api/chat/` is the stateless variant: same service call, no session, no history.

## AI layer

**Adapter pattern.** `ai/providers/base.py` defines `ChatProvider.complete(messages) ->
ChatResult(content, tokens_used)` and `EmbeddingProvider.embed(text) -> list[float]`
(with a `dimensions` class attribute). Concrete adapters (`openai_provider.py`,
`gemini_provider.py`) are known only to the registry in `ai/providers/__init__.py`,
selected by `AI_CHAT_PROVIDER` / `AI_EMBEDDING_PROVIDER`. AI SDK imports are legal only
inside `ai/providers/` — everything else calls `ai.service.get_response()` or
`ai.embeddings.get_embedding()`.

**Error contract.** Adapters map every SDK error to `AIServiceError(message,
status_code)`: auth → 500, rate limit → 429, timeout/connection/API → 503. Views catch
exactly that exception; a raw provider stack trace never reaches a client.

**Prompting.** The system prompt (Portuguese, in `ai/service.py`) instructs the model to
answer in the user's language (Portuguese or Spanish) and cite sources. Retrieved
context is appended to the system prompt, never interleaved with history.

**Embeddings + cache.** `ai/embeddings.py` caches vectors in `EmbeddingCache` keyed by
SHA-256 of the text. `model_used` is stored but **not part of the key** — switching
embedding models without clearing the cache silently mixes embedding spaces (see
CLAUDE.md §4.5 for the required migration procedure).

**Retrieval** (`ai/rag.py`): top-5 by cosine distance over `documents.embedding_vector`
(HNSW index, `vector_cosine_ops`), relevance threshold 0.3 (distance; lower = closer),
context budget 4000 chars. Embedding text at ingest is `title + "\n\n" + content`, so
titles participate in retrieval. `source_url`s of the retrieved documents come back to
the client as citations.

## Data model

| Table | Model | Notes |
|---|---|---|
| `users` | `users.User` | Custom user: UUID pk, unique email as login, `language_preference` (`es`/`pt`, default `es`), `is_premium` (stored, not yet used by any feature) |
| `chat_sessions` | `chat.ChatSession` | UUID pk, FK user, auto-title, ordered `-updated_at` |
| `messages` | `chat.Message` | role user/assistant/system, `sources` JSON list of URLs, ordered `created_at` |
| `documents` | `documents.Document` | KB entry: `document_type` ∈ immigration/tax/utilities/banking/general, `language` ∈ es/pt/gu, `VectorField(dimensions=1536)` |
| `document_templates` | `documents.DocumentTemplate` | Defined and migrated; no feature uses it yet |
| `embedding_cache` | `ai.EmbeddingCache` | SHA-256 → vector (+ `model_used`) |
| `ai_interactions` | `ai.AIInteraction` | **Dead model** — migrated, nothing writes to it |

All models follow the house style: UUID pk, explicit `db_table`, explicit ordering,
`created_at`/`updated_at`, `__str__`.

Vector schema changes follow `documents/migrations/0002_vectorfield.py`: `RunSQL` with
explicit `reverse_sql`, `CREATE EXTENSION IF NOT EXISTS vector` before first use, an
HNSW index per searchable column, and cross-app migration dependencies (`ai/0002`
depends on `documents/0002`).

## API surface

| Endpoint | Auth | Throttle | Purpose |
|---|---|---|---|
| `POST /api/auth/register/` | public | anon | Create account (email login, `language_preference`) |
| `POST /api/auth/token/` | public | anon | JWT pair (60-min access, 7-day rotating refresh) |
| `POST /api/auth/token/refresh/` | public | anon | New access + rotated refresh |
| `GET /api/auth/me/` | JWT | user | Profile |
| `GET/POST /api/sessions/` | JWT | user | List/create own sessions |
| `GET/DELETE /api/sessions/{id}/` | JWT | user | Detail with messages / delete (cross-user → 404) |
| `GET/POST /api/sessions/{id}/messages/` | JWT | **chat** | History / send a turn |
| `POST /api/chat/` | settings-dependent¹ | **chat** | Stateless quick chat |
| `GET /api/health/` | public | anon | Liveness |

¹ Deliberately carries no permission decorator: `IsAuthenticated` under `base`/`prod`
settings, `AllowAny` under `dev` (CLAUDE.md §4.7). Endpoints meant to be public carry an
explicit `AllowAny`.

Views are function-based (`@api_view` + decorators), validation via serializers —
no ViewSets, routers, signals, or celery.

**Rate limiting**: DRF throttling — anon 30/min, user 120/min, chat scope 15/min
(`THROTTLE_*` env vars). `@throttle_classes` *replaces* the defaults on the chat
endpoints, so the chat scope is their only limit; it fires before the view body, so a
throttled request costs no AI money. Counters live in the default LocMem cache —
per-process, so the effective limit is ≈ rate × gunicorn workers until a shared cache
(e.g. Redis) is introduced.

## Frontend

`frontend/src/lib/` is the integration layer:

- **`api.ts`** — typed fetch client for every endpoint. On a 401 from an authenticated
  call it refreshes the token once (single-flight across concurrent requests, rotated
  pair persisted before retry) and replays the request; unauthenticated 401s (bad
  credentials) pass through.
- **`token-store.ts`** — sole owner of the JWT pair: in-memory source of truth,
  best-effort `localStorage` persistence, change subscription. Only a definitively
  rejected refresh token clears it (= logout); network blips never do.
- **`auth-context.tsx`** — React state synced to the token store; login/register/logout.
- **`i18n.ts`** — pt/es dictionaries. Logged-in user's `language_preference` wins,
  browser language before login, Spanish fallback (matches backend default);
  hydration-safe via `useSyncExternalStore`.

Pages: chat (`app/page.tsx` — session sidebar with delete, optimistic sends with
rollback), login, register (with language selector persisted to the backend). Assistant
replies render as sanitized GFM Markdown (react-markdown: raw HTML escaped,
`javascript:` URLs neutralized); RAG sources render as deduplicated links labeled by
hostname. User messages stay plain text.

## Operations

**Settings** (`cheguia/settings/`): `base.py` holds everything incl. `IsAuthenticated`
default and JWT config; `dev.py` opens permissions (`AllowAny`) and uses readable logs;
`prod.py` hard-requires `ALLOWED_HOSTS`/`CORS_ALLOWED_ORIGINS` from env. Secrets come
from env only (`SECRET_KEY` crashes if missing). Anything verified unauthenticated under
dev proves nothing about auth.

**Logging**: JSON lines on stdout (`python-json-logger`), level via `LOG_LEVEL`; dev
swaps in a plain formatter. **Sentry** initializes only when `SENTRY_DSN` is set —
otherwise the SDK is never imported; `send_default_pii=False`, tracing off by default.

**Runtime**: docker-compose runs `pgvector/pgvector:pg16` (+healthcheck) and the web
container (dev settings, source bind-mounted). `docker/entrypoint.sh` polls the DB (30 ×
2s), runs `migrate --noinput`, then execs gunicorn. Gunicorn: sync workers
(`min(2×CPU+1, 9)`), `timeout = 120` — deliberately above the 30s provider timeout;
raising one means checking the other.

**Ingestion**: `python manage.py ingest_documents --sample|--file docs.json
[--update]` is the only sanctioned KB loader. Rows match by exact title: same title
without `--update` is skipped; a changed title creates a new row and orphans the old one
(delete explicitly when renaming).

**Tests**: 46 across the five apps' `tests.py`, AI mocked at the seams
(`get_response` in view tests, provider `complete`/`embed` in service tests); pgvector
retrieval tests run against the real extension. CI runs them under `base` settings so
the auth default is in force.

## Invariants worth money

1. A failed AI turn deletes the just-created user message — no orphans.
2. RAG failures degrade to a plain LLM answer; retrieval never takes chat down.
3. Provider exceptions never escape as raw 500s — always `AIServiceError` → status.
4. History sent to the model: last 10 messages, user/assistant roles only.
5. Embedding model/provider/dimensions changes require migration + re-embed + cache
   clear, in one PR (CLAUDE.md §4.5) — otherwise retrieval is silently poisoned.
6. Gunicorn timeout > provider timeout.
