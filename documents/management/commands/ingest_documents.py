"""
Management command to embed and ingest documents into the knowledge base.

Usage:
    # Ingest bundled sample documents
    python manage.py ingest_documents --sample

    # Ingest from a JSON file
    python manage.py ingest_documents --file /path/to/docs.json

JSON format:
[
  {
    "title": "Como obter o RUC",
    "content": "...",
    "document_type": "tax",
    "language": "pt",
    "source_url": "https://www.set.gov.py/..."
  }
]
"""

import json
import time
from django.core.management.base import BaseCommand, CommandError
from documents.models import Document
from ai.embeddings import get_embedding

SAMPLE_DOCUMENTS = [
    {
        "title": "Como obter o RUC (Registro Único del Contribuyente) no Paraguai",
        "content": (
            "O RUC é o número de identificação fiscal obrigatório para qualquer pessoa física ou jurídica "
            "que realize atividades econômicas no Paraguai.\n\n"
            "Passo a passo para pessoa física:\n"
            "1. Compareça à Subsecretaría de Estado de Tributación (SET) com cédula de identidade paraguaia "
            "ou passaporte válido.\n"
            "2. Preencha o formulário 621 (disponível no site www.set.gov.py).\n"
            "3. Apresente comprovante de endereço (conta de luz, água ou aluguel).\n"
            "4. O RUC é emitido na hora, sem custo.\n\n"
            "Estrangeiros sem cédula paraguaia devem apresentar passaporte e documento de residência. "
            "O número de RUC para pessoa física é baseado no número da cédula de identidade + dígito verificador."
        ),
        "document_type": "tax",
        "language": "pt",
        "source_url": "https://www.set.gov.py/portal/PARAGUAY-SET/inicio",
    },
    {
        "title": "Residência Temporária no Paraguai para Brasileiros",
        "content": (
            "Brasileiros podem solicitar residência temporária no Paraguai com base no Acordo do MERCOSUL, "
            "o que simplifica bastante o processo.\n\n"
            "Documentos necessários:\n"
            "- Passaporte válido (ou RG para brasileiros no MERCOSUL)\n"
            "- Certidão de nascimento apostilada\n"
            "- Certidão de antecedentes criminais apostilada (federal e estadual)\n"
            "- Comprovante de meios de subsistência (extrato bancário ou carta de emprego)\n"
            "- Foto 3x4 recente\n"
            "- Formulário de solicitação preenchido\n\n"
            "O processo é feito na Dirección General de Migraciones (Asunción) ou consulados paraguaios. "
            "A residência temporária tem validade de 2 anos e pode ser convertida em permanente. "
            "Custo aproximado: USD 150-300 mais taxas consulares."
        ),
        "document_type": "immigration",
        "language": "pt",
        "source_url": "https://www.migraciones.gov.py/",
    },
    {
        "title": "Abertura de Conta Bancária no Paraguai",
        "content": (
            "Principais bancos: Banco Continental, Itaú Paraguay, Banco Regional, GNB Paraguay, Sudameris.\n\n"
            "Documentos geralmente exigidos:\n"
            "- Cédula de identidade paraguaia OU passaporte + documento de residência\n"
            "- RUC (para conta pessoa jurídica)\n"
            "- Comprovante de endereço (recente, máx. 90 dias)\n"
            "- Comprovante de renda ou declaração de atividade\n\n"
            "Dicas:\n"
            "- Itaú Paraguay aceita brasileiros com facilidade por ser o mesmo grupo.\n"
            "- Conta em dólares é comum e recomendada para quem recebe do exterior.\n"
            "- Depósito inicial varia de USD 100 a USD 500 dependendo do banco.\n"
            "- O processo leva de 1 a 5 dias úteis após entrega dos documentos."
        ),
        "document_type": "banking",
        "language": "pt",
        "source_url": None,
    },
    {
        "title": "Ligação de Energia Elétrica - ANDE (Asunción e Grande Asunción)",
        "content": (
            "A ANDE (Administración Nacional de Electricidad) é a empresa estatal de energia elétrica do Paraguai.\n\n"
            "Para nova ligação residencial:\n"
            "1. Compareça à agência ANDE mais próxima ou acesse www.ande.gov.py.\n"
            "2. Documentos necessários: cédula de identidade, título do imóvel ou contrato de aluguel, "
            "e planta do imóvel para novos medidores.\n"
            "3. Pague a taxa de instalação (varia conforme tipo de ligação, monofásica ou trifásica).\n"
            "4. A instalação ocorre em 5-15 dias úteis.\n\n"
            "Tarifas: O Paraguai tem uma das energias mais baratas da América do Sul. "
            "Residencial: aprox. USD 0,07-0,09 por kWh. "
            "Para transferência de titularidade em imóvel já ligado, basta apresentar documentos do novo titular."
        ),
        "document_type": "utilities",
        "language": "pt",
        "source_url": "https://www.ande.gov.py/",
    },
]


class Command(BaseCommand):
    help = "Embed and ingest documents into the knowledge base"

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--sample", action="store_true", help="Ingest bundled sample documents")
        group.add_argument("--file", type=str, help="Path to a JSON file with documents to ingest")
        parser.add_argument("--update", action="store_true", help="Re-embed documents that already exist (matched by title)")

    def handle(self, *args, **options):
        if options["sample"]:
            docs = SAMPLE_DOCUMENTS
        else:
            try:
                with open(options["file"], encoding="utf-8") as f:
                    docs = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError) as exc:
                raise CommandError(f"Could not load file: {exc}")

        created = updated = skipped = 0

        for data in docs:
            title = data.get("title", "").strip()
            if not title:
                self.stderr.write(self.style.WARNING("Skipping document with no title."))
                continue

            existing = Document.objects.filter(title=title).first()

            if existing and not options["update"]:
                self.stdout.write(f"  skip  {title}")
                skipped += 1
                continue

            self.stdout.write(f"  {'update' if existing else 'create'} {title} … ", ending="")

            try:
                vector = get_embedding(f"{title}\n\n{data.get('content', '')}")
            except Exception as exc:
                self.stderr.write(self.style.ERROR(f"embedding failed: {exc}"))
                continue

            fields = {
                "content": data.get("content", ""),
                "source_url": data.get("source_url"),
                "document_type": data.get("document_type", "general"),
                "language": data.get("language", "es"),
                "embedding_vector": vector,
            }

            if existing:
                for k, v in fields.items():
                    setattr(existing, k, v)
                existing.save()
                updated += 1
            else:
                Document.objects.create(title=title, **fields)
                created += 1

            self.stdout.write(self.style.SUCCESS("done"))
            time.sleep(0.2)  # gentle rate limiting

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone: {created} created, {updated} updated, {skipped} skipped."
            )
        )
