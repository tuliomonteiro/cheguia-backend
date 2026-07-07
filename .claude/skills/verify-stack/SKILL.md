---
name: verify-stack
description: End-to-end smoke test of the Cheguia backend — boot, migrations, auth, chat, and a RAG retrieval proof with diagnostics. Use after any change to ai/, chat/, documents/, settings, or Docker files, and before opening a PR.
---

# Verify Stack

Prove the whole pipeline works: server boots → migrations apply → JWT auth issues tokens
→ chat answers → RAG actually retrieves and cites. Do not report success on any step you
did not execute; paste real output.

## Step 0 — Preconditions

```bash
test -f .env || { echo "No .env — copy .env.example and fill OPENAI_API_KEY"; }
grep -E '^OPENAI_API_KEY=sk-' .env >/dev/null || echo "WARN: OPENAI_API_KEY looks unset — chat steps will 500"
```

Decide the runtime: if Docker is available, prefer `docker compose up -d --build`
(DB_HOST must be `db`). Bare-metal needs local Postgres with pgvector and DB_HOST
`localhost`. If the server is already running on :8000, reuse it — don't start a second.

Wait for readiness by polling, not sleeping blind:

```bash
for i in $(seq 1 30); do curl -sf http://localhost:8000/api/health/ && break; sleep 2; done
```

## Step 1 — Health and migrations

```bash
curl -sf http://localhost:8000/api/health/            # expect {"status": "healthy", ...}
docker compose exec web python manage.py showmigrations | grep '\[ \]' && echo "UNAPPLIED MIGRATIONS" || echo "migrations OK"
```

(Bare-metal: drop the `docker compose exec web` prefix on manage.py commands throughout.)

## Step 2 — Auth round-trip

Register (idempotent-ish: reuse the user if it already exists), obtain a token pair,
refresh, and call `/me`:

```bash
curl -s -X POST http://localhost:8000/api/auth/register/ -H 'Content-Type: application/json' \
  -d '{"email":"smoke@test.local","username":"smoke","password":"Sm0ke-test-pass!","password2":"Sm0ke-test-pass!"}'

TOKENS=$(curl -s -X POST http://localhost:8000/api/auth/token/ -H 'Content-Type: application/json' \
  -d '{"email":"smoke@test.local","password":"Sm0ke-test-pass!"}')
ACCESS=$(echo "$TOKENS" | python3 -c 'import sys,json; print(json.load(sys.stdin)["access"])')
REFRESH=$(echo "$TOKENS" | python3 -c 'import sys,json; print(json.load(sys.stdin)["refresh"])')

curl -s http://localhost:8000/api/auth/me/ -H "Authorization: Bearer $ACCESS"
curl -s -X POST http://localhost:8000/api/auth/token/refresh/ -H 'Content-Type: application/json' \
  -d "{\"refresh\": \"$REFRESH\"}"
```

Pass criteria: register → 201 (or 400 "already exists" on rerun), token → both `access`
and `refresh` present, `/me` → the user's email, refresh → a new access token.

Remember (§4.7 of CLAUDE.md): under dev settings, endpoints answer without tokens too —
that is expected and proves nothing about auth. The token round-trip above is the test.

## Step 3 — RAG retrieval proof

The trick: ingest a document containing a fact the base model cannot know, then confirm
the chat response cites it. This separates "LLM answered from training data" from "RAG
retrieved our document".

```bash
cat > /tmp/smoke_doc.json <<'EOF'
[{
  "title": "Documento de verificação Cheguia",
  "content": "O escritório fictício de testes da Cheguia fica na Rua Verificación 4242, Asunción, e atende às terças-feiras das 9h às 13h. Código interno de verificação: CHEGUIA-SMOKE-4242.",
  "document_type": "general",
  "language": "pt",
  "source_url": "https://example.com/cheguia-smoke"
}]
EOF
docker compose exec -T web python manage.py ingest_documents --file /tmp/smoke_doc.json \
  || { docker compose cp /tmp/smoke_doc.json web:/tmp/smoke_doc.json && docker compose exec web python manage.py ingest_documents --file /tmp/smoke_doc.json; }

curl -s -X POST http://localhost:8000/api/chat/ -H 'Content-Type: application/json' \
  -d '{"message": "Qual é o código interno de verificação do escritório de testes da Cheguia?"}'
```

Pass criteria — all three:
1. Response 200 with a `message`.
2. `sources` contains `https://example.com/cheguia-smoke`.
3. The message mentions `CHEGUIA-SMOKE-4242`.

## Step 4 — If Step 3 fails, diagnose in this order (do NOT tweak thresholds first)

Run in `python manage.py shell`:

```python
from documents.models import Document
from ai.models import EmbeddingCache
print("docs:", Document.objects.count(), "embedded:", Document.objects.exclude(embedding_vector=None).count())
print("cache entries:", EmbeddingCache.objects.count())

from ai.embeddings import get_embedding
from pgvector.django import CosineDistance
v = get_embedding("código interno de verificação Cheguia")
for d in Document.objects.exclude(embedding_vector=None).annotate(dist=CosineDistance('embedding_vector', v)).order_by('dist')[:5]:
    print(round(d.dist, 4), d.title)
```

Interpretation:
- `embedded: 0` → ingestion failed; check the ingest command output / OPENAI_API_KEY.
- Smoke doc appears but distance > 0.3 → retrieval threshold excluded it; report the
  actual distance — changing `RELEVANCE_THRESHOLD` in `ai/rag.py` is a product decision,
  escalate per CLAUDE.md §6.
- Distances look fine but `sources` empty in the API response → bug between `ai/rag.py`
  and `ai/service.py`; read `_try_rag` and check the logs for the swallowed exception
  (`docker compose logs web | grep -A5 "RAG retrieval failed"`).

## Step 5 — Session flow (authenticated)

```bash
SID=$(curl -s -X POST http://localhost:8000/api/sessions/ -H "Authorization: Bearer $ACCESS" \
  -H 'Content-Type: application/json' -d '{"title":"smoke"}' | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])')
curl -s -X POST "http://localhost:8000/api/sessions/$SID/messages/" -H "Authorization: Bearer $ACCESS" \
  -H 'Content-Type: application/json' -d '{"content":"Preciso de RUC?"}'
curl -s "http://localhost:8000/api/sessions/$SID/" -H "Authorization: Bearer $ACCESS"
curl -s -X DELETE "http://localhost:8000/api/sessions/$SID/" -H "Authorization: Bearer $ACCESS" -o /dev/null -w '%{http_code}\n'
```

Pass criteria: create → 201, message post → assistant reply persisted, detail → both
messages present, delete → 204.

## Step 6 — Cleanup and report

Remove the smoke document so it never pollutes real answers:

```python
from documents.models import Document
Document.objects.filter(source_url="https://example.com/cheguia-smoke").delete()
```

Report as a table: step | pass/fail | evidence (one line of real output each). Any fail
= the overall verdict is FAIL, even if later steps passed.
