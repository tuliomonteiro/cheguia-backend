import json
import tempfile
from io import StringIO
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import TestCase

from documents.models import Document

FAKE_VECTOR = [0.0] * 1536


def write_docs_file(docs):
    f = tempfile.NamedTemporaryFile(
        mode='w', suffix='.json', delete=False, encoding='utf-8'
    )
    json.dump(docs, f)
    f.close()
    return f.name


def ingest(*args):
    out = StringIO()
    # Patch at the command's namespace: it imports get_embedding at module
    # level. `time` is replaced too so the per-doc rate-limit sleep is free.
    with patch(
        'documents.management.commands.ingest_documents.get_embedding',
        return_value=FAKE_VECTOR,
    ) as mock_embed, patch('documents.management.commands.ingest_documents.time'):
        call_command('ingest_documents', *args, stdout=out, stderr=out)
    return out.getvalue(), mock_embed


DOC = {
    'title': 'Como obter o RUC',
    'content': 'O RUC é o registro fiscal paraguaio.',
    'document_type': 'tax',
    'language': 'pt',
    'source_url': 'https://www.set.gov.py/',
}


class IngestDocumentsTests(TestCase):
    def test_creates_documents_and_embeds_title_plus_content(self):
        path = write_docs_file([DOC])

        output, mock_embed = ingest('--file', path)

        self.assertIn('1 created', output)
        doc = Document.objects.get(title=DOC['title'])
        self.assertEqual(doc.document_type, 'tax')
        self.assertEqual(len(doc.embedding_vector), 1536)
        # The embedding-text contract: title participates in retrieval.
        mock_embed.assert_called_once_with(f"{DOC['title']}\n\n{DOC['content']}")

    def test_rerun_without_update_skips_existing_title(self):
        path = write_docs_file([DOC])
        ingest('--file', path)

        output, mock_embed = ingest('--file', path)

        self.assertIn('1 skipped', output)
        mock_embed.assert_not_called()
        self.assertEqual(Document.objects.count(), 1)

    def test_update_re_embeds_and_replaces_content(self):
        path = write_docs_file([DOC])
        ingest('--file', path)

        changed = {**DOC, 'content': 'Conteúdo revisado.'}
        output, mock_embed = ingest('--file', write_docs_file([changed]), '--update')

        self.assertIn('1 updated', output)
        mock_embed.assert_called_once()
        self.assertEqual(Document.objects.count(), 1)
        self.assertEqual(Document.objects.get().content, 'Conteúdo revisado.')

    def test_changed_title_creates_new_document(self):
        # Documents the §4.14 trap: a retitle is a NEW row, the old one stays.
        path = write_docs_file([DOC])
        ingest('--file', path)

        renamed = {**DOC, 'title': 'RUC: guia completo'}
        ingest('--file', write_docs_file([renamed]))

        self.assertEqual(Document.objects.count(), 2)

    def test_document_without_title_is_skipped(self):
        path = write_docs_file([{'content': 'sem título'}])

        output, _ = ingest('--file', path)

        self.assertIn('0 created', output)
        self.assertFalse(Document.objects.exists())

    def test_missing_file_raises_command_error(self):
        with self.assertRaises(CommandError):
            ingest('--file', '/tmp/nao-existe.json')


E_TAX = [1.0] + [0.0] * 1535
E_BANK = [0.0, 1.0] + [0.0] * 1534
E_FAR = [0.0, 0.0, 1.0] + [0.0] * 1533


def write_fixture_file(cases):
    f = tempfile.NamedTemporaryFile(
        mode='w', suffix='.json', delete=False, encoding='utf-8'
    )
    json.dump(cases, f)
    f.close()
    return f.name


def eval_retrieval(fixture, embeddings_by_query):
    out = StringIO()
    path = write_fixture_file(fixture)
    with patch(
        'documents.management.commands.eval_retrieval.get_embedding',
        side_effect=lambda query: embeddings_by_query[query],
    ):
        call_command('eval_retrieval', '--file', path, stdout=out, stderr=out)
    return out.getvalue()


class EvalRetrievalTests(TestCase):
    def setUp(self):
        self.tax = Document.objects.create(
            title='Doc Tax', content='conteúdo', document_type='tax',
            language='pt', embedding_vector=E_TAX,
        )
        self.bank = Document.objects.create(
            title='Doc Bank', content='conteúdo', document_type='banking',
            language='pt', embedding_vector=E_BANK,
        )

    def test_exact_match_is_a_hit(self):
        fixture = [{'query': 'q-tax', 'language': 'pt', 'expected_titles': ['Doc Tax']}]
        output = eval_retrieval(fixture, {'q-tax': E_TAX})

        self.assertIn('hit@1: 1/1 (100%)', output)
        self.assertIn('hit@5: 1/1 (100%)', output)

    def test_wrong_top_result_is_a_partial_hit_at_5(self):
        # Query embeds like Doc Bank, but the fixture expects Doc Tax. With
        # only 2 documents both are inside TOP_K, so it still hits at 5.
        fixture = [{'query': 'q-miss', 'language': 'pt', 'expected_titles': ['Doc Tax']}]
        output = eval_retrieval(fixture, {'q-miss': E_BANK})

        self.assertIn('hit@1: 0/1 (0%)', output)
        self.assertIn('hit@5: 1/1 (100%)', output)

    def test_no_expected_document_and_far_result_counts_as_correct_abstention(self):
        fixture = [{'query': 'q-none', 'language': 'es', 'expected_titles': []}]
        output = eval_retrieval(fixture, {'q-none': E_FAR})

        self.assertIn('correctly returned nothing relevant: 1/1 (100%)', output)

    def test_no_expected_document_but_close_result_is_a_false_positive(self):
        fixture = [{'query': 'q-false-positive', 'language': 'es', 'expected_titles': []}]
        output = eval_retrieval(fixture, {'q-false-positive': E_TAX})

        self.assertIn('correctly returned nothing relevant: 0/1 (0%)', output)
        self.assertIn('FALSE POSITIVE', output)

    def test_language_breakdown_is_reported(self):
        fixture = [
            {'query': 'q-pt', 'language': 'pt', 'expected_titles': ['Doc Tax']},
            {'query': 'q-es', 'language': 'es', 'expected_titles': ['Doc Tax']},
        ]
        output = eval_retrieval(fixture, {'q-pt': E_TAX, 'q-es': E_BANK})

        self.assertIn('pt: hit@1 1/1 (100%)', output)
        self.assertIn('es: hit@1 0/1 (0%)', output)

    def test_empty_knowledge_base_raises_command_error(self):
        Document.objects.all().delete()
        with self.assertRaises(CommandError):
            eval_retrieval([{'query': 'q', 'language': 'pt', 'expected_titles': []}], {'q': E_TAX})

    def test_missing_fixture_file_raises_command_error(self):
        with self.assertRaises(CommandError):
            call_command('eval_retrieval', '--file', '/tmp/nao-existe.json')
