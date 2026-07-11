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
