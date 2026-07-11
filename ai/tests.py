import hashlib
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase

from ai.exceptions import AIServiceError
from ai.models import EmbeddingCache
from ai.providers.base import ChatResult
from ai.service import (
    BASE_SYSTEM_PROMPT,
    MAX_HISTORY_MESSAGES,
    _build_messages,
    _build_system_prompt,
    _try_rag,
    get_response,
)


class BuildMessagesTests(SimpleTestCase):
    def test_system_prompt_first_and_user_message_last(self):
        messages = _build_messages('pergunta', [], '')

        self.assertEqual(messages[0]['role'], 'system')
        self.assertEqual(messages[0]['content'], BASE_SYSTEM_PROMPT)
        self.assertEqual(messages[-1], {'role': 'user', 'content': 'pergunta'})

    def test_context_is_injected_into_system_prompt(self):
        messages = _build_messages('pergunta', [], 'CONTEXTO-RAG')

        self.assertIn('CONTEXTO-RAG', messages[0]['content'])
        self.assertTrue(messages[0]['content'].startswith(BASE_SYSTEM_PROMPT))

    def test_history_is_capped_at_max(self):
        history = [{'role': 'user', 'content': f'msg-{i}'} for i in range(15)]

        messages = _build_messages('nova', history, '')

        # system + capped history + new user message
        self.assertEqual(len(messages), 1 + MAX_HISTORY_MESSAGES + 1)
        self.assertEqual(messages[1]['content'], 'msg-5')  # oldest kept

    def test_unknown_roles_are_dropped(self):
        history = [
            {'role': 'user', 'content': 'a'},
            {'role': 'system', 'content': 'injetado'},
            {'role': 'tool', 'content': 'b'},
            {'role': 'assistant', 'content': 'c'},
        ]

        messages = _build_messages('nova', history, '')

        roles = [m['role'] for m in messages]
        self.assertEqual(roles, ['system', 'user', 'assistant', 'user'])
        self.assertNotIn('injetado', [m['content'] for m in messages])


class SystemPromptTests(SimpleTestCase):
    def test_no_context_returns_base_prompt(self):
        self.assertEqual(_build_system_prompt(''), BASE_SYSTEM_PROMPT)


class TryRagTests(SimpleTestCase):
    def test_any_failure_degrades_to_empty_results(self):
        # RAG must never take chat down (CLAUDE.md §4.4).
        with patch('ai.embeddings.get_embedding', side_effect=RuntimeError('db caiu')):
            with self.assertLogs('ai.service', level='ERROR'):
                self.assertEqual(_try_rag('pergunta'), ('', []))


class GetResponseTests(SimpleTestCase):
    def _provider(self, result=None, error=None):
        provider = MagicMock()
        if error:
            provider.complete.side_effect = error
        else:
            provider.complete.return_value = result or ChatResult('resposta', tokens_used=7)
        return provider

    @patch('ai.service._try_rag', return_value=('CONTEXTO', ['https://www.set.gov.py/']))
    @patch('ai.providers.get_chat_provider')
    def test_returns_contract_dict_with_rag_sources(self, mock_get_provider, mock_rag):
        provider = self._provider()
        mock_get_provider.return_value = provider

        result = get_response('Preciso de RUC?', [{'role': 'user', 'content': 'antes'}])

        self.assertEqual(result['message'], 'resposta')
        self.assertEqual(result['sources'], ['https://www.set.gov.py/'])
        self.assertEqual(result['tokens_used'], 7)
        self.assertIsInstance(result['processing_time'], float)

        sent = provider.complete.call_args.args[0]
        self.assertIn('CONTEXTO', sent[0]['content'])
        self.assertEqual(sent[-1], {'role': 'user', 'content': 'Preciso de RUC?'})

    @patch('ai.service._try_rag', return_value=('', []))
    @patch('ai.providers.get_chat_provider')
    def test_provider_error_propagates(self, mock_get_provider, mock_rag):
        mock_get_provider.return_value = self._provider(
            error=AIServiceError('sem cota', 429)
        )

        with self.assertRaises(AIServiceError) as ctx:
            get_response('oi')
        self.assertEqual(ctx.exception.status_code, 429)


class EmbeddingCacheTests(TestCase):
    def _provider(self, vector, model='modelo-teste'):
        provider = MagicMock()
        provider.embed.return_value = vector
        provider.model_name = model
        return provider

    def test_miss_embeds_and_caches_then_hit_skips_provider(self):
        from ai.embeddings import get_embedding
        vector = [0.0] * 1535 + [1.0]
        provider = self._provider(vector)

        with patch('ai.providers.get_embedding_provider', return_value=provider):
            first = get_embedding('Preciso de RUC?')
            second = get_embedding('Preciso de RUC?')

        provider.embed.assert_called_once()
        self.assertEqual(first, vector)
        self.assertEqual(second, vector)

        text_hash = hashlib.sha256('Preciso de RUC?'.encode()).hexdigest()
        cached = EmbeddingCache.objects.get(text_hash=text_hash)
        self.assertEqual(cached.model_used, 'modelo-teste')

    def test_cache_is_keyed_by_text_hash_only(self):
        # Documents the known trap (CLAUDE.md §4.5): after an embedding-model
        # switch the cache still serves old-model vectors. If this test ever
        # fails because the key gained the model name, §4.5 can be relaxed.
        from ai.embeddings import get_embedding
        old_vector = [1.0] + [0.0] * 1535
        with patch('ai.providers.get_embedding_provider',
                   return_value=self._provider(old_vector, model='modelo-antigo')):
            get_embedding('mesmo texto')

        new_provider = self._provider([0.0] * 1535 + [1.0], model='modelo-novo')
        with patch('ai.providers.get_embedding_provider', return_value=new_provider):
            result = get_embedding('mesmo texto')

        new_provider.embed.assert_not_called()
        self.assertEqual(result, old_vector)


class RetrieveContextTests(TestCase):
    """Real pgvector round-trip: cosine distance filtering and the context budget."""

    def _doc(self, title, vector, source_url='https://www.set.gov.py/', content='conteúdo'):
        from documents.models import Document
        return Document.objects.create(
            title=title,
            content=content,
            document_type='tax',
            language='pt',
            source_url=source_url,
            embedding_vector=vector,
        )

    def test_relevant_within_threshold_irrelevant_excluded(self):
        from ai.rag import retrieve_context
        e1 = [1.0] + [0.0] * 1535
        e2 = [0.0, 1.0] + [0.0] * 1534  # orthogonal: cosine distance 1.0 > 0.3
        relevant = self._doc('Como obter o RUC', e1)
        self._doc('Documento irrelevante', e2, source_url='https://example.com/x')
        self._doc('Sem embedding', None)

        context, sources = retrieve_context(e1)

        self.assertIn(relevant.title, context)
        self.assertNotIn('Documento irrelevante', context)
        self.assertEqual(sources, [relevant.source_url])

    def test_no_relevant_documents_returns_empty(self):
        from ai.rag import retrieve_context
        self._doc('Distante', [0.0, 1.0] + [0.0] * 1534)

        self.assertEqual(retrieve_context([1.0] + [0.0] * 1535), ('', []))

    def test_context_budget_truncates_content(self):
        from ai.rag import MAX_CONTEXT_CHARS, retrieve_context
        vector = [1.0] + [0.0] * 1535
        long_content = 'a' * (MAX_CONTEXT_CHARS + 1000)
        self._doc('Documento longo', vector, content=long_content)

        context, _ = retrieve_context(vector)

        self.assertIn(long_content[:MAX_CONTEXT_CHARS], context)
        self.assertNotIn(long_content, context)

    def test_document_without_source_url_still_contributes_context(self):
        from ai.rag import retrieve_context
        vector = [1.0] + [0.0] * 1535
        self._doc('Sem fonte', vector, source_url=None)

        context, sources = retrieve_context(vector)

        self.assertIn('Sem fonte', context)
        self.assertEqual(sources, [])
