---
name: ingest-kb
description: Turn raw source material (pasted text, an official URL, or a PDF) into knowledge-base documents — correctly chunked, typed, and sourced — then ingest via the management command and prove retrieval works. Use whenever adding or updating Paraguay content (migraciones, SET, ANDE, banking…).
---

# Ingest Knowledge Base Content

The product is only as good as this pipeline. A document that is ingested but never
retrieved is invisible; a document with wrong facts is worse than none. This skill turns
source material into `ingest_documents --file` JSON and proves it retrievable.

## Step 1 — Acquire the text

- **Pasted text:** use as-is.
- **URL:** fetch it (WebFetch or `curl -sL`). Only official or clearly authoritative
  sources: `*.gov.py` (set.gov.py, migraciones.gov.py, ande.gov.py, essap.com.py),
  consulates, banks' own sites. If the user hands you a blog/forum post, flag it —
  ingest only if they confirm, and keep the real URL as `source_url` so provenance is
  visible.
- **PDF:** extract with PyMuPDF (not committed as a dependency — install ad hoc, don't
  add to requirements.txt unless asked):
  ```bash
  pip install pymupdf
  python3 - "$PDF_PATH" <<'EOF'
  import sys, fitz
  with fitz.open(sys.argv[1]) as doc:
      print("\n".join(page.get_text() for page in doc))
  EOF
  ```
  PDF text is dirty: strip headers/footers repeated on every page, fix hyphenated
  line-breaks, drop page numbers. Read the extraction before using it.

## Step 2 — Edit for retrieval, don't dump

Raw source text retrieves poorly. Rewrite each document so it stands alone:

- **One topic per document.** "Requisitos de residência temporária" and "custos e prazos
  da residência" are two documents, not one. The retriever returns whole documents into
  a 4000-char context budget (`ai/rag.py`) — a 12-page dump wastes the budget.
- **Target 300–1500 chars of content each.** Above ~3000 chars, split; make each chunk
  self-contained (repeat the subject in the text — "A residência temporária no
  Paraguai…" — because the chunk is embedded without its neighbors).
- **Lead with the terms users will ask with.** Users ask "como tirar RUC", "conta no
  banco sendo brasileiro". Include the acronym AND its expansion. Note the title is part
  of the embedded text (`ingest_documents` embeds `title + "\n\n" + content`), so put
  search terms in the title too.
- **Keep concrete facts:** form numbers (formulário 621), office names, addresses,
  costs in guaraníes, schedules. These are what people actually need.
- **State the date of validity** inside the content when the source shows one
  ("Vigente desde 03/2026") — bureaucratic rules rot.

## Step 3 — Build the JSON

Schema per `documents/management/commands/ingest_documents.py`:

```json
[
  {
    "title": "Como obter o RUC no Paraguai (pessoa física)",
    "content": "…",
    "document_type": "tax",
    "language": "pt",
    "source_url": "https://www.set.gov.py/…"
  }
]
```

Hard constraints (model enums — invalid values fail or corrupt filtering):
- `document_type` ∈ `immigration | tax | utilities | banking | general`
- `language` ∈ `es | pt | gu` — and must match the language the content is actually
  written in. Prefer `pt` for content targeting the Brazilian audience; keep `es` when
  the source's precise legal wording matters.
- `title` ≤ 500 chars, specific enough to be a useful citation label.
- `source_url` = the real source. Never fabricate one.

Save to a file (e.g. `kb/2026-07-residencia.json` if the user wants it versioned,
otherwise the scratchpad). Validate before ingesting:

```bash
python3 -c "import json,sys; d=json.load(open(sys.argv[1])); \
assert isinstance(d,list) and all({'title','content','document_type'} <= set(x) for x in d); \
print(len(d),'docs OK')" FILE.json
```

## Step 4 — Check for duplicates, then ingest

```bash
python manage.py shell -c "
from documents.models import Document
for t in [TITLES]:
    print(Document.objects.filter(title__icontains=t.split('(')[0][:30]).values_list('title', flat=True))"
```

Matching semantics (from the command's source): rows are matched by **exact title**.
Same title without `--update` → skipped. Same title with `--update` → content and
embedding replaced in place. **Different title → a brand-new document**, leaving the old
one orphaned to compete in retrieval with stale content. So: updating content = keep the
title byte-identical and pass `--update`; renaming = delete the old row explicitly in
the same operation. Don't silently double-ingest — near-duplicates crowd out other
results in top-K retrieval.

```bash
python manage.py ingest_documents --file FILE.json
# (--update re-embeds existing titles instead of skipping them)
```

Confirm each document got an embedding (the command reports; verify count went up):

```bash
python manage.py shell -c "
from documents.models import Document
print('embedded:', Document.objects.exclude(embedding_vector=None).count(), '/', Document.objects.count())"
```

## Step 5 — Prove retrieval (mandatory)

For each ingested document, form one question a real user would ask (in the document's
language) and check it retrieves within threshold:

```python
# manage.py shell
from ai.embeddings import get_embedding
from pgvector.django import CosineDistance
from documents.models import Document
q = "preciso de RUC para abrir empresa no Paraguai?"
v = get_embedding(q)
for d in Document.objects.exclude(embedding_vector=None).annotate(dist=CosineDistance('embedding_vector', v)).order_by('dist')[:5]:
    print(round(d.dist, 4), d.title)
```

Pass: the new document appears in the top 5 with distance ≤ 0.3 (the
`RELEVANCE_THRESHOLD` in `ai/rag.py`). If it's close but above threshold, the fix is
better content (Step 2 — more question-like phrasing in the text), **not** raising the
threshold — that's a product decision, escalate per CLAUDE.md §6.

Optionally finish with one live `POST /api/chat/` asking the test question and confirm
`sources` cites the new document.

## Step 6 — Report

List: documents ingested (title, type, language, chars), duplicates handled, and per
document the test query + best distance. Flag any content you had to guess about
(ambiguous dates, conflicting sources) instead of burying the guess.
