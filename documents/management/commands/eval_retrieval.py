"""
Management command to measure retrieval quality against the embedded knowledge base.

Usage:
    # Run the bundled fixture (PT/ES phrasings of each KB topic, plus a few
    # questions the KB has no document for, to catch false positives)
    python manage.py eval_retrieval

    # Run a custom fixture instead
    python manage.py eval_retrieval --file /path/to/fixture.json

Fixture JSON format:
[
  {
    "query": "Como tirar o RUC no Paraguai?",
    "language": "pt",
    "expected_titles": ["Como obter o RUC (Registro Único del Contribuyente) no Paraguai"]
  },
  {
    "query": "¿Cómo saco la licencia de conducir en Paraguay?",
    "language": "es",
    "expected_titles": []
  }
]

`expected_titles` names the Document rows (matched by exact title, same key
ingest_documents uses) that should come back for the query. An empty list
means no document in the KB should answer it — those cases catch false
positives as the KB grows into topics this fixture doesn't know about.

Reports hit@1 (the top result is an expected title), hit@5 (an expected
title is anywhere in the top TOP_K), and the cosine-distance distribution —
split by query language, since the retrieval pipeline's cross-lingual
behavior (Spanish queries against today's Portuguese-only documents) is
otherwise unmeasured (see ROADMAP.md, gap 2 and §3.3).
"""

import json
import statistics

from django.core.management.base import BaseCommand, CommandError
from pgvector.django import CosineDistance

from ai.embeddings import get_embedding
from ai.rag import RELEVANCE_THRESHOLD, TOP_K
from documents.models import Document

FIXTURE = [
    # --- RUC / SET (tax) ---
    {
        "query": "Como tirar o RUC no Paraguai?",
        "language": "pt",
        "expected_titles": ["Como obter o RUC (Registro Único del Contribuyente) no Paraguai"],
    },
    {
        "query": "Quais documentos preciso para abrir o RUC como pessoa física?",
        "language": "pt",
        "expected_titles": ["Como obter o RUC (Registro Único del Contribuyente) no Paraguai"],
    },
    {
        "query": "O RUC tem algum custo para ser emitido?",
        "language": "pt",
        "expected_titles": ["Como obter o RUC (Registro Único del Contribuyente) no Paraguai"],
    },
    {
        "query": "¿Cómo saco el RUC en Paraguay?",
        "language": "es",
        "expected_titles": ["Como obter o RUC (Registro Único del Contribuyente) no Paraguai"],
    },
    {
        "query": "¿Qué formulario se presenta en la SET para obtener el RUC?",
        "language": "es",
        "expected_titles": ["Como obter o RUC (Registro Único del Contribuyente) no Paraguai"],
    },
    {
        "query": "¿Qué documento necesito si soy extranjero sin cédula paraguaya para sacar el RUC?",
        "language": "es",
        "expected_titles": ["Como obter o RUC (Registro Único del Contribuyente) no Paraguai"],
    },
    # --- Residency (immigration) ---
    {
        "query": "Como pedir residência temporária no Paraguai sendo brasileiro?",
        "language": "pt",
        "expected_titles": ["Residência Temporária no Paraguai para Brasileiros"],
    },
    {
        "query": "Quais documentos preciso apostilar para a residência no Paraguai?",
        "language": "pt",
        "expected_titles": ["Residência Temporária no Paraguai para Brasileiros"],
    },
    {
        "query": "Quanto tempo dura a residência temporária paraguaia?",
        "language": "pt",
        "expected_titles": ["Residência Temporária no Paraguai para Brasileiros"],
    },
    {
        "query": "¿Cómo tramito la residencia temporaria en Paraguay siendo brasileño?",
        "language": "es",
        "expected_titles": ["Residência Temporária no Paraguai para Brasileiros"],
    },
    {
        "query": "¿Dónde se presenta la solicitud de residencia, en Migraciones o en el consulado?",
        "language": "es",
        "expected_titles": ["Residência Temporária no Paraguai para Brasileiros"],
    },
    {
        "query": "¿Cuánto cuesta aproximadamente el trámite de residencia temporaria?",
        "language": "es",
        "expected_titles": ["Residência Temporária no Paraguai para Brasileiros"],
    },
    # --- Banking ---
    {
        "query": "Como abrir conta em banco no Paraguai sendo estrangeiro?",
        "language": "pt",
        "expected_titles": ["Abertura de Conta Bancária no Paraguai"],
    },
    {
        "query": "Quais bancos aceitam brasileiros para abrir conta no Paraguai?",
        "language": "pt",
        "expected_titles": ["Abertura de Conta Bancária no Paraguai"],
    },
    {
        "query": "Qual o depósito inicial para abrir conta em dólares no Paraguai?",
        "language": "pt",
        "expected_titles": ["Abertura de Conta Bancária no Paraguai"],
    },
    {
        "query": "¿Cómo abro una cuenta bancaria en Paraguay siendo extranjero?",
        "language": "es",
        "expected_titles": ["Abertura de Conta Bancária no Paraguai"],
    },
    {
        "query": "¿Qué banco paraguayo es más fácil para que un brasileño abra una cuenta?",
        "language": "es",
        "expected_titles": ["Abertura de Conta Bancária no Paraguai"],
    },
    {
        "query": "¿Cuánto tiempo tarda el banco en abrir la cuenta después de entregar los documentos?",
        "language": "es",
        "expected_titles": ["Abertura de Conta Bancária no Paraguai"],
    },
    # --- ANDE (utilities) ---
    {
        "query": "Como ligar a luz da ANDE em uma casa nova em Assunção?",
        "language": "pt",
        "expected_titles": ["Ligação de Energia Elétrica - ANDE (Asunción e Grande Asunción)"],
    },
    {
        "query": "Quanto custa o kWh residencial da ANDE no Paraguai?",
        "language": "pt",
        "expected_titles": ["Ligação de Energia Elétrica - ANDE (Asunción e Grande Asunción)"],
    },
    {
        "query": "Quanto tempo demora a instalação de um novo medidor da ANDE?",
        "language": "pt",
        "expected_titles": ["Ligação de Energia Elétrica - ANDE (Asunción e Grande Asunción)"],
    },
    {
        "query": "¿Cómo solicito una nueva conexión eléctrica de ANDE en Asunción?",
        "language": "es",
        "expected_titles": ["Ligação de Energia Elétrica - ANDE (Asunción e Grande Asunción)"],
    },
    {
        "query": "¿Qué documentos pide ANDE para transferir la titularidad del medidor?",
        "language": "es",
        "expected_titles": ["Ligação de Energia Elétrica - ANDE (Asunción e Grande Asunción)"],
    },
    {
        "query": "¿Cuál es la tarifa residencial de electricidad en Paraguay?",
        "language": "es",
        "expected_titles": ["Ligação de Energia Elétrica - ANDE (Asunción e Grande Asunción)"],
    },
    # --- Topics the KB has no document for yet (ROADMAP §2 gap 2, §3.2) ---
    {"query": "Como tirar a carteira de motorista paraguaia?", "language": "pt", "expected_titles": []},
    {"query": "¿Cómo se importa un auto a Paraguay?", "language": "es", "expected_titles": []},
    {"query": "Como funciona a ligação de água da ESSAP?", "language": "pt", "expected_titles": []},
    {"query": "¿Dónde saco la cédula de identidad paraguaya?", "language": "es", "expected_titles": []},
    {"query": "Qual é a multa por ficar com o visto vencido no Paraguai?", "language": "pt", "expected_titles": []},
    {"query": "¿Cómo tramito un permiso de trabajo en Paraguay?", "language": "es", "expected_titles": []},
    {"query": "Onde aprender guarani em Assunção?", "language": "pt", "expected_titles": []},
    {"query": "¿Qué trámite se hace para comprar una propiedad en Paraguay?", "language": "es", "expected_titles": []},
]


class Command(BaseCommand):
    help = "Measure retrieval quality (hit@1, hit@5, cosine distances) against the embedded knowledge base"

    def add_arguments(self, parser):
        parser.add_argument("--file", type=str, help="Path to a JSON fixture to use instead of the bundled one")

    def handle(self, *args, **options):
        if options["file"]:
            try:
                with open(options["file"], encoding="utf-8") as f:
                    fixture = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError) as exc:
                raise CommandError(f"Could not load file: {exc}")
        else:
            fixture = FIXTURE

        if not Document.objects.exclude(embedding_vector=None).exists():
            raise CommandError("No embedded documents in the knowledge base — run ingest_documents first.")

        rows = [self._evaluate(case) for case in fixture]

        for row in rows:
            if row["expected"]:
                marker = self.style.SUCCESS("OK") if row["hit1"] else (
                    self.style.WARNING("~~") if row["hit5"] else self.style.ERROR("MISS")
                )
            else:
                marker = self.style.SUCCESS("OK") if row["hit1"] else self.style.ERROR("FALSE POSITIVE")
            self.stdout.write(f"  [{marker}] ({row['language']}) {row['query']}")

        self.stdout.write("")
        self._summarize(rows)

    def _evaluate(self, case):
        query = case["query"]
        expected = set(case.get("expected_titles", []))
        vector = get_embedding(query)

        top = list(
            Document.objects
            .exclude(embedding_vector=None)
            .annotate(distance=CosineDistance('embedding_vector', vector))
            .order_by('distance')[:TOP_K]
        )
        top_titles = [doc.title for doc in top]
        top1_distance = top[0].distance if top else None

        if expected:
            hit1 = bool(top_titles) and top_titles[0] in expected
            hit5 = any(title in expected for title in top_titles)
            distance = next((doc.distance for doc in top if doc.title in expected), None)
        else:
            # No document should answer this one — "hit" means the closest
            # result (if any) falls outside the relevance threshold.
            hit1 = hit5 = top1_distance is None or top1_distance > RELEVANCE_THRESHOLD
            distance = top1_distance

        return {
            "query": query,
            "language": case.get("language", "?"),
            "expected": bool(expected),
            "hit1": hit1,
            "hit5": hit5,
            "distance": distance,
        }

    def _summarize(self, rows):
        positive = [r for r in rows if r["expected"]]
        negative = [r for r in rows if not r["expected"]]

        if positive:
            hit1_count = sum(1 for r in positive if r["hit1"])
            hit5_count = sum(1 for r in positive if r["hit5"])
            self.stdout.write(f"hit@1: {hit1_count}/{len(positive)} ({hit1_count / len(positive):.0%})")
            self.stdout.write(f"hit@5: {hit5_count}/{len(positive)} ({hit5_count / len(positive):.0%})")

            for lang in sorted({r["language"] for r in positive}):
                subset = [r for r in positive if r["language"] == lang]
                sub1 = sum(1 for r in subset if r["hit1"])
                sub5 = sum(1 for r in subset if r["hit5"])
                self.stdout.write(
                    f"  {lang}: hit@1 {sub1}/{len(subset)} ({sub1 / len(subset):.0%}), "
                    f"hit@5 {sub5}/{len(subset)} ({sub5 / len(subset):.0%})"
                )
        else:
            self.stdout.write("No expected-document cases in this fixture.")

        if negative:
            correct = sum(1 for r in negative if r["hit1"])
            self.stdout.write(
                f"correctly returned nothing relevant: {correct}/{len(negative)} "
                f"({correct / len(negative):.0%}) — the rest are false positives"
            )

        distances = [r["distance"] for r in rows if r["distance"] is not None]
        if distances:
            self.stdout.write(
                f"distance (closest match per query): min={min(distances):.3f} "
                f"median={statistics.median(distances):.3f} max={max(distances):.3f} "
                f"(relevance threshold={RELEVANCE_THRESHOLD})"
            )
