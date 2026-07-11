# CLAUDE.md — Operating Manual for the Cheguia Backend

Cheguia is a chat assistant that helps Brazilians (and other newcomers) navigate
Paraguayan bureaucracy — immigration, SET/RUC taxes, ANDE, banking. This repo is the
Django 4.2 + DRF backend: JWT auth, chat sessions, and a pgvector RAG pipeline over a
curated knowledge base, with swappable AI providers (OpenAI/Gemini) behind an adapter
pattern.

Read this file as rules, not suggestions. When a rule here conflicts with your general
instincts, the rule wins — each one exists because the generic instinct produces a bug
in this specific codebase.

---

## 1. Orientation — where the truth lives

| Concern | File(s) | Note |
|---|---|---|
| Chat orchestration (prompt, history, RAG injection) | `ai/service.py` | The only entry point views use: `get_response()` |
| Provider adapters | `ai/providers/` | Registry in `ai/providers/__init__.py` is the ONLY file that knows concrete classes |
| Embeddings (+ SHA-256 cache) | `ai/embeddings.py`, `EmbeddingCache` in `ai/models.py` | |
| Vector retrieval | `ai/rag.py` | `TOP_K=5`, cosine distance threshold `0.3`, context budget 4000 chars |
| Knowledge base model | `documents/models.py` | `VectorField(dimensions=1536)`, HNSW index in `documents/migrations/0002_vectorfield.py` |
| KB ingestion | `documents/management/commands/ingest_documents.py` | The only sanctioned way to load documents |
| Auth | `users/` + `rest_framework_simplejwt` | Custom `User`, email login, access/refresh rotation |
| Sessions & messages | `chat/` | |
| Stateless quick-chat + health | `api/views.py` | |
| Settings | `cheguia/settings/{base,dev,prod}.py` | Split; secrets from env only |
| Runtime | `docker-compose.yml`, `Dockerfile`, `docker/entrypoint.sh`, `gunicorn.conf.py` | entrypoint waits for DB + migrates |

Contracts hiding in the code that you must preserve:

- **Chat rollback:** `chat/views.py` deletes the just-created user `Message` when the AI
  call raises `AIServiceError`, so a failed turn leaves no orphan in the session. It also
  auto-titles the session from the first user message (`content[:80]`). Keep both.
- **Embedding text = `title + "\n\n" + content`** (see `ingest_documents`). The title
  participates in retrieval — write titles that carry search terms.
- **`EmbeddingCache` is keyed by text hash only.** `model_used` is stored but NOT part of
  the key — after an embedding-model change the cache serves stale vectors from the old
  model. This is why §4.5 demands clearing it.
- **Timeout coupling:** gunicorn `timeout = 120` must stay above the provider timeout
  (default 30s in `ChatProvider.complete`). Raise one, check the other.
- **`AIInteraction` (`ai/models.py`) is a dead model** — defined and migrated, but nothing
  writes to it. Don't assume analytics exist; don't wire writes to it without being asked.

The live settings tree is `cheguia/settings/`. (A stale nested `cheguia/cheguia/`
scaffolding tree used to shadow it — deleted in 2026; if you see it reappear in an old
branch, do not edit it.)

`ARCHITECTURE.md` was rewritten in 2026 to describe the system as built (request flow,
adapter pattern, data model, invariants). `README.md` covers setup and API usage. If
either disagrees with the code, the code wins — and fix the doc in the same PR.

## 2. Running and verifying

```bash
# Preferred: full stack (Postgres already has pgvector in this image)
docker compose up --build          # web on :8000, db on :5432

# Bare-metal alternative (needs local Postgres with pgvector, DB_HOST=localhost in .env)
python manage.py migrate && python manage.py runserver

# Seed the knowledge base
python manage.py ingest_documents --sample
```

Smoke check (dev settings — endpoints are open):
`GET /api/health/` → 200; `POST /api/chat/ {"message": "..."}` → response with `sources`.

Dev vs prod behavior differs on purpose: `dev.py` sets `AllowAny` as the default
permission; `base.py`/`prod.py` require JWT. **Anything you verify unauthenticated in dev
is NOT evidence auth works.** To test the real thing:
`DJANGO_SETTINGS_MODULE=cheguia.settings.prod` (needs `ALLOWED_HOSTS`,
`CORS_ALLOWED_ORIGINS` in env).

## 3. Conventions

### Followed in this codebase — match them exactly

- **Function-based DRF views** with `@api_view([...])` + `@permission_classes([...])`.
  No ViewSets, no generics, no routers. Validation happens in a serializer via
  `serializer.is_valid(raise_exception=True)` — never manual `request.data.get()` checks.
- **Models:** UUID primary key (`default=uuid.uuid4, editable=False`), explicit
  `db_table`, explicit `Meta.ordering`, `created_at`/`updated_at` timestamps, choices as
  class-level constant lists, a `__str__`.
- **Modern typing:** `list[dict]`, `tuple[str, list[str]]` — no `typing.List`/`Optional`
  imports in new code.
- **Docstrings state contracts** (what's returned, what raises, invariants worth money —
  e.g., "switching embedding providers requires re-embedding"). Comments are sparse and
  explain *why*, never *what*.
- **Language split:** code, comments, commits, docs in English. User-facing AI text
  (system prompts, error messages returned to users, sample KB content) in
  Portuguese/Spanish. The assistant must reply in the user's language — never hardcode
  Spanish-only behavior.
- **Config via env:** every new setting reads `os.getenv()` in `base.py` with a safe
  non-secret default, or `os.environ[...]` (crash-on-missing) in `prod.py` if it is
  security-relevant. Secrets never get committed defaults.
- **Dependencies pinned** with `==` in `requirements.txt`.
- **Git:** branches named `feat/…`, `fix/…`, `docs/…`; commit subjects imperative and
  capitalized ("Add pgvector RAG pipeline with document ingestion"); work lands through
  GitHub PRs, never direct pushes to `main`.

### Added rules (not yet in the codebase — enforce them going forward)

- **Write tests.** Every `tests.py` is currently an empty stub; that is debt, not a
  convention to copy. New endpoints and provider adapters ship with `APITestCase` /
  `SimpleTestCase` coverage. Mock AI at the seam: patch `ai.service.get_response` in view
  tests, patch the provider's `complete`/`embed` in service tests. Tests must never hit a
  real AI API.
- **`.env.example` and README move with the code.** Adding a setting, endpoint, env var,
  or command without updating both is an incomplete change.
- **Keep the README roadmap table honest** — flip Planned→Done in the same PR that does
  the work.

## 4. Named failure modes — and the rule that prevents each

These are the specific mistakes a model will make in this repo. Each has one rule.

1. **Branching from a stale base.** `main` has historically lagged the real tip by
   entire feature stacks (PRs #2–#6 lived on `docs/readme` while `main` had only #1).
   **Rule:** before starting work, run `git fetch --all` and
   `git log --oneline --graph --all | head -30`; branch from the newest remote tip, not
   from local `main`. If `main` is behind, say so and propose the catch-up merge first.

2. **Importing an AI SDK outside the adapters.** **Rule:** `openai`, `langchain*`,
   `google.*` imports are legal only inside `ai/providers/*.py`. Everything else calls
   `ai.service.get_response()` or `ai.embeddings.get_embedding()`. If a change seems to
   need an SDK import elsewhere, the design is wrong — extend the adapter interface.

3. **Letting raw provider exceptions escape.** **Rule:** adapters map every SDK error to
   `AIServiceError(message, status_code)` (see `_map_openai_error` for the required
   coverage: auth→500, rate limit→429, timeout/connection/API→503). Views catch exactly
   `AIServiceError` and return `Response({'error': str(exc)}, status=exc.status_code)` —
   never a bare 500 with a stack trace.

4. **Making RAG failures fatal.** Chat must degrade to a plain LLM answer when retrieval
   breaks. **Rule:** retrieval goes through `_try_rag()`, which logs the exception and
   returns `("", [])`. Never move retrieval outside that guard or re-raise from it.

5. **Casually changing the embedding model/provider.** The DB stores 1536-dim vectors,
   and `EmbeddingCache` is keyed by text hash alone — after a model switch it will
   silently return old-model vectors, mixing embedding spaces. **Rule:** any change to
   `AI_EMBEDDING_PROVIDER`/`AI_EMBEDDING_MODEL`/dimensions requires, in one PR: a
   migration for `VectorField(dimensions=…)` on `documents.Document` AND
   `ai.EmbeddingCache`, a re-embed of all documents, and clearing `EmbeddingCache`.
   Absent all three, do not touch embedding settings. (This is escalation-worthy — §6.)

6. **Editing the wrong settings tree.** **Rule:** live settings are
   `cheguia/settings/{base,dev,prod}.py` — nothing else. (The stale `cheguia/cheguia/`
   scaffolding this rule used to guard against was deleted in 2026.)

7. **Confusing dev-open endpoints with public endpoints.** In dev everything is
   `AllowAny` by default, so "it worked without a token" proves nothing. **Rule:**
   endpoints meant to be public in production (`health_check`, `register`, token
   endpoints) carry an explicit `@permission_classes([AllowAny])`; everything else gets
   no permission decorator and inherits `IsAuthenticated` from base settings. When
   claiming auth behavior, verify under prod settings.

8. **Rewriting instead of extending the DRF style.** **Rule:** no ViewSets, no
   class-based views, no routers, no signals, no middleware, no celery — unless the task
   explicitly asks for the new machinery. Match `chat/views.py`.

9. **Ad-hoc data scripts.** **Rule:** any repeatable data operation (ingesting,
   re-embedding, backfills) is a Django management command in the owning app, with
   `--help` text and a docstring showing usage — like `ingest_documents`.

10. **DB host confusion.** In docker-compose the hostname is `db`; bare-metal it's
    `localhost`. **Rule:** if you get `OperationalError: could not translate host name
    "db"`, you are running outside compose with a compose-flavored `.env` — fix
    `DB_HOST`, don't touch `settings`.

11. **Editing applied migrations — or botching vector migrations.** **Rule:** never
    modify a migration that exists on any remote branch; add a new one. Vector schema
    changes follow the established pattern (`documents/migrations/0002_vectorfield.py`):
    `RunSQL` with an explicit `reverse_sql`, `CREATE EXTENSION IF NOT EXISTS vector`
    before first use, an HNSW index with `vector_cosine_ops` on every searchable vector
    column, and a cross-app `dependencies` entry on the migration that creates the
    extension (as `ai/0002` depends on `documents/0002`).

12. **Breaking the message-format contract.** History entries are
    `{"role": "user"|"assistant", "content": str}`; `_build_messages` silently drops
    other roles and caps history at `MAX_HISTORY_MESSAGES = 10`. **Rule:** don't invent
    new roles or bypass the cap without changing `ai/service.py` deliberately and saying so.

13. **Inventing KB metadata.** **Rule:** `document_type` must be one of
    `immigration|tax|utilities|banking|general`; `language` one of `es|pt|gu`;
    `source_url` should point at the official source (set.gov.py, migraciones.gov.py,
    ande.gov.py…). New categories require a model change + migration, not a new string.

14. **Retitling KB documents on re-ingest.** `ingest_documents` matches existing rows by
    exact title: same title without `--update` is skipped; a changed title creates a NEW
    document and orphans the old one, which then competes in retrieval with stale
    content. **Rule:** to update content, keep the title identical and pass `--update`;
    to rename, delete the old row explicitly in the same operation.

## 5. Quality bar per deliverable — checkable, not adjectives

A deliverable below its bar is not done. Say which items you verified and how.

**New or changed endpoint**
- [ ] Function-based view; serializer validates input; explicit or deliberate permissions (§4.7)
- [ ] AI-touching paths handle `AIServiceError` (§4.3)
- [ ] URL wired in the owning app's `urls.py`; route name given
- [ ] Test in the app's `tests.py` covering success + at least one failure case, AI mocked
- [ ] Exercised live: actual `curl`/httpie output for success AND failure, shown in your report
- [ ] README API Reference updated

**New or changed model**
- [ ] UUID pk, `db_table`, `Meta.ordering`, timestamps, `__str__`
- [ ] `makemigrations` run; migration reviewed by eye before committing
- [ ] `migrate` succeeds on a fresh DB (`docker compose down -v && docker compose up` or equivalent)
- [ ] Existing data impact stated (nullable? default? backfill needed?)

**New provider adapter**
- [ ] Subclasses `ChatProvider`/`EmbeddingProvider` from `ai/providers/base.py`; embedding adapters set `dimensions`
- [ ] Error mapping covers auth, rate-limit, timeout, connection, generic — all to `AIServiceError` with the status codes from §4.3
- [ ] Registered in `ai/providers/__init__.py` with lazy import; registry docstring updated
- [ ] Zero files outside `ai/providers/` changed (except settings/env/docs)
- [ ] `base.py` settings + `.env.example` + README env-var table updated
- [ ] Verified with a real call, or a test that patches the SDK client

**Knowledge-base content**
- [ ] Valid JSON matching the `ingest_documents --file` schema; enums per §4.13
- [ ] Content in the language its `language` field claims
- [ ] `ingest_documents` runs clean; embedding count reported
- [ ] Retrieval proven: a natural query about the content returns it within the 0.3 distance threshold (show the query and distance)

**Branch / PR**
- [ ] Based on the newest remote tip (§4.1)
- [ ] Branch named `feat/…`, `fix/…`, or `docs/…`; subject imperative, ≤ 72 chars; body says why
- [ ] `git status` clean of accidents: no `.env`, no `venv/`, no `__pycache__`, no test PDFs
- [ ] `python manage.py check` passes; test suite passes
- [ ] README/roadmap/`.env.example` consistent with the change (§3-added)

## 6. When uncertain — exact escalation rules

**Stop and ask the user before** (no exceptions, even if the fix seems obvious):
- Anything destructive to data: dropping/truncating `documents`, `messages`,
  `embedding_cache`; `docker compose down -v` on a DB known to hold real content;
  irreversible migrations on populated tables.
- Changing embedding provider, model, or dimensions (§4.5) — this silently poisons
  retrieval; it's a product decision.
- Auth/security posture: JWT lifetimes, permission defaults, CORS origins, HSTS/SSL
  settings, anything in `prod.py`.
- Git history surgery: force-push, rebase of pushed branches, deleting remote branches,
  merging PRs. Opening a PR is fine; merging is the user's call.
- Spending money or picking paid defaults (switching `AI_CHAT_MODEL` to a pricier model,
  adding a paid service).
- Deleting any file you did not create this session, beyond what the task explicitly named.

**Decide yourself, silently, by precedent** — do not ask about: naming, file placement,
serializer vs. view structure, test layout, docstring style. The answer is "whatever
`chat/` and `ai/` already do."

**Investigate before assuming** — never guess when a command can answer:
- Which settings module is active → `echo $DJANGO_SETTINGS_MODULE`, check
  `manage.py`/`wsgi.py` defaults.
- Whether main/branch is current → `git fetch --all` + graph log (§4.1).
- Why retrieval returns nothing → count embedded docs, check distances against the 0.3
  threshold, check `EmbeddingCache` — in that order — before touching thresholds.
- Whether a bug is code or environment → reproduce inside docker compose first.

**When genuinely blocked** (missing API key, ambiguous product intent, conflicting
instructions): state what you verified, the exact decision you need, and your
recommended option — then stop. Don't fabricate a stub that pretends the decision away.
