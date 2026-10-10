# ROADMAP — what to build next in Cheguia

This is the context document for deciding what to work on. It is opinionated on
purpose: it ranks work by how much it moves Cheguia from "a well-built codebase"
toward "a thing Brazilians in Paraguay actually use."

How it relates to the other docs:

| Doc | Answers |
|---|---|
| `README.md` | How do I run it and call the API? |
| `ARCHITECTURE.md` | How does it work as built? |
| `CLAUDE.md` | What are the rules for changing it? |
| **`ROADMAP.md`** (this file) | **What should we build next, and why that first?** |

Keep it honest: when an item ships, move it into the §1 "Where we stand" table
with a pointer to the code that proves it, and flip the README roadmap row in
the same PR.

---

## 1. Where we stand

Everything on the original 8-step plan is done except step 8. Verified against
the code on `main` as of the last audit:

| Capability | State | Evidence |
|---|---|---|
| Settings split, secrets from env | Done | `cheguia/settings/{base,dev,prod}.py`; `prod.py` uses `os.environ[...]` so it crashes on missing vars |
| JWT auth, registration, profile, password change | Done | `users/` — 5 routes, 241 lines of tests |
| Chat sessions + message history | Done | `chat/views.py`, with failure rollback and auto-titling |
| Provider adapter pattern (OpenAI + Gemini) | Done | `ai/providers/`; registry is the only file naming concrete classes |
| pgvector RAG, HNSW index | Done | `documents/migrations/0002_vectorfield.py`, `ai/rag.py` |
| Docker, compose, Gunicorn | Done | `Dockerfile`, `docker-compose.yml`, `gunicorn.conf.py` |
| Rate limiting, JSON logging, opt-in Sentry | Done | `base.py` `DEFAULT_THROTTLE_RATES`, `LOGGING`, `SENTRY_DSN` guard |
| Backend test suite | Done | 814 lines across 5 apps, running in CI under `settings.base` (real auth) |
| CI on every PR | Done | `.github/workflows/` — backend tests + frontend lint/build |
| Next.js frontend | Done | `frontend/` — auth, chat, settings, i18n |
| Django backoffice | Done | all models registered, admin path env-configurable |

That is a genuinely solid foundation. The gaps below are not about code quality.

---

## 2. The three gaps that actually matter

Everything in §3 follows from these. Stated plainly:

**Gap 1 — It has never been deployed.** There is no `fly.toml`, no
`render.yaml`, no Procfile, no Terraform, no k8s manifest. `docker-compose.yml`
is a dev convenience, not a deployment. Nobody outside a laptop has used
Cheguia.

**Gap 2 — The knowledge base has four documents, all in Portuguese.**
`SAMPLE_DOCUMENTS` in `ingest_documents.py` holds exactly 4 entries — RUC/tax,
temporary residency, bank accounts, ANDE — every one of them `"language": "pt"`.
RAG grounding is the entire value proposition over "just ask ChatGPT," and there
is almost nothing to retrieve. Anything outside those four topics gets an
ungrounded LLM answer with no sources.

The language skew is its own problem: `User.language_preference` defaults to
`'es'` and `LANGUAGE_CODE` is `'es-py'`, so the default user is Spanish-speaking
and **100% of the corpus is Portuguese**. Whether a Spanish question retrieves a
Portuguese document at all depends on cross-lingual behavior of
`text-embedding-3-small` that nobody here has measured. There is also no `general`
content and no Guarani, though both are valid enum values.

**Gap 3 — Nothing measures whether answers are good.** No feedback capture, no
retrieval eval set, no analytics writes. `TOP_K=5` and
`RELEVANCE_THRESHOLD=0.3` are unvalidated constants that happen to work against
6 documents; they will quietly stop being right at 200. `AIInteraction` is
defined, migrated, and never written to — token spend and latency go
unrecorded.

---

## 3. Tier 1 — needed before anyone can use this

### 3.1 Deploy the stack

**Why now:** everything else is theoretical until there is a URL.

**What it touches:** new deploy config at repo root; managed Postgres **with the
`vector` extension available** (Neon, Supabase, and RDS all support it — verify
before committing to a host, because a host without pgvector kills the whole RAG
design); `ALLOWED_HOSTS` / `CORS_ALLOWED_ORIGINS` wired to real domains; frontend
deployed separately with `NEXT_PUBLIC_API_URL` pointing at the backend.

**Also fix while deploying:** throttle state currently lives in Django's LocMem
cache, so counts are per-process — with N Gunicorn workers the real limit is
roughly `rate × N` (the comment in `base.py` says so). Throttling is the
AI-spend control. Add a shared cache backend (Redis) and a `CACHES` setting, or
accept the overshoot knowingly and write down the number.

**Done when:**
- [ ] Backend reachable over HTTPS; `GET /api/health/` returns 200 from the public internet
- [ ] Migrations ran on the managed DB, `vector` extension confirmed present
- [ ] Frontend deployed and talking to the deployed backend end to end
- [ ] `DJANGO_ADMIN_URL` set to something non-obvious; admin reachable only there
- [ ] Secrets set as host env vars — verified nothing landed in git
- [ ] Deploy steps documented in README; `.env.example` updated with any new var

**Watch out:** `prod.py` settings are security posture — per CLAUDE.md §6,
changes there (HSTS, SSL redirect, CORS origins, JWT lifetimes) are an ask, not
a self-serve decision.

### 3.2 Fill the knowledge base — and chunk it

**Why now:** this is the product. Four Portuguese documents is a demo, not a
knowledge base.

Targets, in rough order of how often newcomers hit them: residency (permanent
and temporary, the 2023+ rule changes), cédula, RUC / SET registration and
monthly IVA obligations, ANDE connection and transfer, bank account opening
requirements by bank, ESSAP, driver's licence exchange, and importing a vehicle.
Sources are the official ones — `migraciones.gov.py`, `set.gov.py`,
`ande.gov.py`. The repo already has an `ingest-kb` skill for this workflow.

**The chunking problem — do not skip this.** `ingest_documents` embeds
`title + "\n\n" + content` as **one vector per document**. The four samples are
short enough that this works. A real SET guide or a full residency procedure is
thousands of words, and a single vector over all of it averages out into
something that matches nothing well. Worse, `ai/rag.py` then truncates with
`doc.content[:remaining]` against a 4000-char budget — mid-sentence, keeping the
top of the document regardless of which part was relevant.

So a real KB needs a chunking strategy first: split long source material into
sections of a few hundred words, each ingested as its own `Document` with a
title that carries its search terms (titles participate in retrieval — CLAUDE.md
§1). Decide whether chunks are separate rows or a new model **before** ingesting
200 documents; reshaping it afterwards means re-embedding everything.

**Language coverage is a decision, not an afterthought.** The corpus is entirely
Portuguese today while the default user is Spanish-speaking. Either commit to
ingesting each topic in both PT and ES, or establish by measurement (3.3) that
cross-lingual retrieval works well enough to skip it. Do not leave it to chance —
a Spanish user getting no sources looks identical to a broken RAG pipeline.

**Done when:**
- [ ] Chunking approach decided and written down (row-per-chunk vs. new model)
- [ ] Language strategy decided: dual-ingest, or cross-lingual retrieval proven by measurement
- [ ] Each target topic ingested, in the language its `language` field claims
- [ ] `document_type` / `language` values stay inside the existing enums (§4.13) — new categories need a model change, not a new string
- [ ] Retrieval proven per topic: a natural question returns the right chunk inside the 0.3 threshold, with the query and distance shown
- [ ] Re-ingest keeps titles identical and uses `--update` (§4.14 — a changed title orphans the old row, which then competes in retrieval with stale content)

### 3.3 A retrieval eval set

**Why now:** 3.2 grows the KB by one to two orders of magnitude. `TOP_K=5`, the
0.3 threshold, and the 4000-char budget are currently unvalidated against four
documents. Without a way to measure, tuning them is guessing and regressions are
invisible. It is also the only way to answer the cross-lingual question raised
in 3.2.

**Shape:** a JSON fixture of realistic questions in Portuguese and Spanish, each
with the document(s) that should come back, plus a management command that
reports hit rate and the distance distribution. Per CLAUDE.md §4.9, any
repeatable data operation is a management command in the owning app, with
`--help` text and a usage docstring — like `ingest_documents`.

**Done when:**
- [x] ≥ 30 question/expected-doc pairs covering every `document_type`, both languages —
  32 pairs in the bundled fixture (`documents/management/commands/eval_retrieval.py`),
  covering `tax`/`immigration`/`banking`/`utilities` in both `pt` and `es`, plus 8
  "no document should match" cases. `general` has no pairs yet because the KB has no
  `general` document to expect — add coverage once 3.2 ingests one.
- [x] `python manage.py eval_retrieval` prints hit@1, hit@5, and distances — also
  broken down per query language, to surface the cross-lingual gap from gap 2 directly.
- [ ] Current numbers recorded here as the baseline to beat — **blocked**: embedding
  the fixture's 32 queries needs a real call through `AI_EMBEDDING_PROVIDER` (OpenAI),
  and this environment has no `OPENAI_API_KEY`. Run `python manage.py ingest_documents
  --sample && python manage.py eval_retrieval` with a real key and paste the output
  here as the baseline.
- [ ] Threshold/TOP_K changes justified by a before/after from this command, never by
  vibes — no threshold/TOP_K change proposed yet; applies the next time one is.

### 3.4 A disclaimer

**Why now:** Cheguia gives bureaucratic and tax guidance. There is currently no
disclaimer anywhere in the backend or the frontend — grep finds nothing. An
LLM confidently stating the wrong residency requirement or IVA deadline has real
consequences for the person who follows it.

**Done when:**
- [ ] Disclaimer visible in the chat UI, in the user's language (PT/ES)
- [ ] System prompt in `ai/service.py` instructs the model to recommend verifying against the official source and to say when it is unsure
- [ ] Wording is the owner's call — this is a product/legal decision, not an implementation detail

---

## 4. Tier 2 — makes it good

### 4.1 Streaming responses

**Why:** today the user sends a message and watches nothing happen for the full
generation — a `chat` provider timeout budget of 30s with a 120s Gunicorn
ceiling. Streaming is the single largest perceived-quality improvement available,
and it costs nothing per token.

**Why it is not a small change — read before estimating.** The current stack is
WSGI with synchronous Gunicorn workers; a worker is occupied for the whole
request. Server-sent events over sync workers means one worker pinned per
in-flight chat. Getting this right means either moving to `gthread` workers, or
going ASGI (`uvicorn`) — and ASGI touches Django settings, the Dockerfile, and
`gunicorn.conf.py` together. It also needs a new method on the `ChatProvider`
ABC (`stream()`), implemented in **both** adapters, with the same
`AIServiceError` mapping discipline as `complete()` (§4.3), plus a frontend that
consumes SSE incrementally.

**Decide the worker model first.** Everything else follows from it.

**Done when:**
- [ ] `ChatProvider.stream()` on the ABC, implemented for OpenAI and Gemini, errors mapped to `AIServiceError`
- [ ] Streaming endpoint; the assistant `Message` is still persisted on completion, and a mid-stream failure leaves no orphan (the §1 rollback contract still holds)
- [ ] Frontend renders tokens as they arrive
- [ ] Timeout coupling re-checked: Gunicorn's `timeout` must stay above the provider's (CLAUDE.md §1)

### 4.2 Sources should be citations, not bare URLs

**Why:** `retrieve_context()` returns `sources` as a `list[str]` of URLs, in
retrieval order, **with duplicates** when several chunks share a `source_url`
(the frontend type comment already admits "may repeat"). The user sees a naked
`https://set.gov.py/` with no indication of what it says or why it is there.
After chunking (3.2) the duplication gets much worse.

**Shape:** `[{title, url, document_type}]`, deduplicated by URL. This is a
breaking API change — `Message.sources` is a `JSONField` holding already-persisted
rows, so either migrate old rows or have the serializer tolerate both shapes.

**Done when:**
- [ ] Structured, deduplicated sources from `ai/rag.py` through to the API
- [ ] Existing `Message.sources` rows still render (migration or tolerant serializer — state which)
- [ ] Frontend shows title + link; README API reference updated

### 4.3 Message feedback

**Why:** nothing captures whether an answer helped. This is the cheapest
possible signal about whether the product works, and it doubles as the source
of new eval cases for 3.3 — every thumbs-down is a retrieval question worth
adding to the fixture.

**Shape:** thumbs up/down on assistant messages, optional free-text. Follow the
house model conventions — UUID pk, explicit `db_table`, `Meta.ordering`,
timestamps, `__str__` (CLAUDE.md §3). Function-based view, serializer
validation, no ViewSets (§4.8).

**Done when:**
- [x] Model + migration, reviewed by eye, applies clean on a fresh DB — `chat.MessageFeedback`,
  `chat/migrations/0003_messagefeedback.py`
- [x] `POST` endpoint with serializer validation and a test covering success + one failure —
  `chat/views.py:message_feedback`, 7 tests in `chat/tests.py::MessageFeedbackTests`
- [x] Frontend control on assistant messages only — thumbs buttons in `frontend/src/app/page.tsx`,
  rendered only for `m.role === "assistant"`
- [x] Visible in the admin, filterable by rating — `MessageFeedbackAdmin` in `chat/admin.py`
- [x] README API reference updated

### 4.4 Frontend tests

**Why:** `frontend/package.json` has no test runner at all. CI runs `lint` and
`build` — which prove the code compiles, not that login works. The backend is
well covered; the frontend is not covered at all.

**Done when:**
- [ ] Test runner added and wired into the frontend CI job
- [ ] Coverage for the auth flow (login, token refresh on 401, logout) and the chat send path, with the API layer mocked
- [ ] CI fails when they fail

---

## 5. Tier 3 — makes it a business

### 5.1 Decide `AIInteraction`'s fate

It is defined, migrated, and **never written to** — grep finds exactly one
reference, its own class definition. Right now it is a claim the schema makes
and the code does not honor.

Two honest options:
- **Wire it up**, if per-user token spend, latency, and which questions retrieve
  nothing are things worth knowing. `get_response()` already returns
  `tokens_used` and `processing_time` — the data exists and gets thrown away.
  That makes AI cost per user visible, which matters the moment real traffic
  arrives.
- **Delete it**, if not. A dead model that looks like analytics is worse than no
  analytics, because it implies numbers someone might go looking for.

Pick one. CLAUDE.md §1 says not to wire writes to it unasked — so this needs a
decision, not a PR.

### 5.2 Premium tier — the unbuilt half

Roadmap step 8 is the only one still "Planned," and two pieces of it are already
sitting in the schema doing nothing:

- `User.is_premium` — exists, shown in the admin and the API, **gates nothing**
- `DocumentTemplate` — full model with 5 template types and an `is_premium`
  flag, plus a serializer in `documents/serializers.py`, and **no view, no URL,
  no generation code**

So the monetization story is half-scaffolded and entirely non-functional. Before
any code: what is actually behind the paywall? Candidates the schema hints at —
generated documents (residency application, power of attorney, rental
contract), higher rate limits, longer history. Then payment, which in Paraguay
means researching what actually works locally (Bancard, Pagopar) rather than
assuming Stripe.

Needs a product decision before an implementation plan.

### 5.3 A document API

`documents/views.py` is still `# Create your views here.` — the knowledge base
is reachable only through the Django admin. There is no way for a user to
browse or search it, and no way for the frontend to show "here is the full
article this answer came from." Worth building once the KB is large enough to
be worth browsing (i.e. after 3.2), and it pairs naturally with 4.2.

---

## 6. Deliberately not doing

Recording these so they do not get re-proposed:

| Not doing | Why |
|---|---|
| Celery / task queue | Nothing needs background jobs yet. CLAUDE.md §4.8 — no new machinery unless the task asks for it. Revisit if bulk re-embedding gets slow. |
| Switching embedding model or dimensions | Escalation-worthy (§4.5). Needs migration + full re-embed + `EmbeddingCache` clear in one PR, and it is a product decision. |
| Rewriting views as ViewSets/CBVs | §4.8. The function-based style is the convention; match `chat/views.py`. |
| Microservices, GraphQL, k8s | No scale problem exists. Deploy the monolith (3.1) and find out what actually hurts. |
| More provider adapters | Two is enough to prove the pattern. Add a third when there is a reason, not for symmetry. |

---

## 7. Decisions only the owner can make

These block work above and cannot be defaulted:

1. **Hosting and budget** (3.1) — which host, and what monthly spend is acceptable for app + managed Postgres + Redis.
2. **Default chat model** (cost) — `gpt-4o-mini` today. Gemini is wired and the tokens exist. Switching the default is a spend decision; CLAUDE.md §6 says ask before picking a pricier default.
3. **Disclaimer wording** (3.4) — legal posture for bureaucratic advice.
4. **Analytics: wire or delete `AIInteraction`** (5.1).
5. **Is premium real, and what is behind it** (5.2) — gates the whole tier.
6. **Chunk granularity** (3.2) — technical, but it sets embedding cost and retrieval quality for everything after, and reversing it means re-embedding the corpus.
7. **Language coverage** (3.2) — ingest every topic in both Portuguese and Spanish, or rely on cross-lingual retrieval. Roughly doubles ingestion and embedding cost if dual, and risks silently serving no sources to Spanish users if not.

---

## 8. Suggested order

Tier 1 is sequenced, not parallel — each step makes the next meaningful:

```
3.1 Deploy ──► 3.2 Fill the KB (+ chunking) ──► 3.3 Eval set ──► 3.4 Disclaimer
                                                      │
                                                      ▼
                          Tier 2, now measurable: 4.1 streaming, 4.2 citations,
                                                  4.3 feedback, 4.4 frontend tests
                                                      │
                                                      ▼
                              Tier 3, once there are real users to learn from
```

The reasoning: deploying first means the KB work has somewhere to land and real
questions to answer. Filling the KB before building the eval set means the eval
measures something real. Both before Tier 2 means streaming and citations ship
against a system whose answer quality is known rather than assumed.

One caveat on 3.2 and 3.3: decide the chunking shape before bulk ingestion, and
stand up the eval set early enough that it captures a baseline you can actually
regress against.
