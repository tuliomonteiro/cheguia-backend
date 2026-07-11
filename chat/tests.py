from datetime import timedelta
from unittest.mock import patch

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from ai.exceptions import AIServiceError
from chat.models import ChatSession, Message
from users.models import User

SESSIONS = reverse('session-list-create')

AI_RESULT = {
    'message': 'Sim, você precisa de RUC para faturar.',
    'sources': ['https://www.set.gov.py/'],
    'tokens_used': 42,
    'processing_time': 0.1,
}


def messages_url(session_id):
    return reverse('message-list-create', args=[session_id])


class SessionTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='ana@test.local', username='ana', password='S3nha-forte-123!'
        )
        self.other = User.objects.create_user(
            email='otro@test.local', username='otro', password='S3nha-forte-123!'
        )

    def test_requires_authentication(self):
        # Explicit IsAuthenticated decorator — enforced regardless of the
        # settings module's default permissions.
        self.assertEqual(self.client.get(SESSIONS).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_and_list_scoped_to_owner(self):
        self.client.force_authenticate(self.user)
        created = self.client.post(SESSIONS, {'title': 'RUC'})
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)

        ChatSession.objects.create(user=self.other, title='alheia')

        listed = self.client.get(SESSIONS)
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertEqual([s['title'] for s in listed.data], ['RUC'])

    def test_detail_of_another_users_session_is_404(self):
        session = ChatSession.objects.create(user=self.other)
        self.client.force_authenticate(self.user)

        response = self.client.get(reverse('session-detail', args=[session.id]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_session(self):
        session = ChatSession.objects.create(user=self.user)
        self.client.force_authenticate(self.user)

        response = self.client.delete(reverse('session-detail', args=[session.id]))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ChatSession.objects.filter(id=session.id).exists())


class MessageTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='ana@test.local', username='ana', password='S3nha-forte-123!'
        )
        self.session = ChatSession.objects.create(user=self.user)
        self.client.force_authenticate(self.user)

    @patch('chat.views.get_response', return_value=AI_RESULT)
    def test_post_message_persists_turn_and_auto_titles(self, mock_ai):
        content = 'x' * 100  # longer than the 80-char title cap

        response = self.client.post(messages_url(self.session.id), {'content': content})

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['assistant']['content'], AI_RESULT['message'])
        self.assertEqual(response.data['assistant']['sources'], AI_RESULT['sources'])
        self.assertEqual(self.session.messages.count(), 2)

        self.session.refresh_from_db()
        self.assertEqual(self.session.title, content[:80])

    @patch('chat.views.get_response', return_value=AI_RESULT)
    def test_existing_title_is_kept(self, mock_ai):
        self.session.title = 'meu título'
        self.session.save()

        self.client.post(messages_url(self.session.id), {'content': 'oi'})

        self.session.refresh_from_db()
        self.assertEqual(self.session.title, 'meu título')

    @patch('chat.views.get_response', side_effect=AIServiceError('Limite atingido', 429))
    def test_ai_failure_rolls_back_user_message(self, mock_ai):
        response = self.client.post(messages_url(self.session.id), {'content': 'oi'})

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.data['error'], 'Limite atingido')
        # The just-created user message must not survive a failed turn.
        self.assertEqual(self.session.messages.count(), 0)

    @patch('chat.views.get_response', return_value=AI_RESULT)
    def test_history_is_last_10_messages_oldest_first(self, mock_ai):
        base = timezone.now() - timedelta(minutes=30)
        for i in range(12):
            msg = Message.objects.create(
                session=self.session,
                role='user' if i % 2 == 0 else 'assistant',
                content=f'msg-{i}',
            )
            # Force distinct, ordered timestamps (auto_now_add ignores kwargs).
            Message.objects.filter(pk=msg.pk).update(created_at=base + timedelta(seconds=i))

        self.client.post(messages_url(self.session.id), {'content': 'nova pergunta'})

        history = mock_ai.call_args.args[1]
        self.assertEqual(len(history), 10)
        self.assertEqual(history[0]['content'], 'msg-2')
        self.assertEqual(history[-1]['content'], 'msg-11')
        self.assertNotIn('nova pergunta', [entry['content'] for entry in history])

    def test_message_without_content_is_400(self):
        response = self.client.post(messages_url(self.session.id), {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.session.messages.count(), 0)

    @patch('chat.views.get_response', return_value=AI_RESULT)
    def test_post_to_another_users_session_is_404(self, mock_ai):
        other = User.objects.create_user(
            email='otro@test.local', username='otro', password='S3nha-forte-123!'
        )
        foreign = ChatSession.objects.create(user=other)

        response = self.client.post(messages_url(foreign.id), {'content': 'oi'})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        mock_ai.assert_not_called()
