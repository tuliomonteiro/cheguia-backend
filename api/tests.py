from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from ai.exceptions import AIServiceError

CHAT = reverse('chat')
HEALTH = reverse('health_check')

AI_RESULT = {
    'message': 'O RUC é emitido pela SET.',
    'sources': ['https://www.set.gov.py/'],
    'tokens_used': 10,
    'processing_time': 0.05,
}


class HealthCheckTests(APITestCase):
    def test_health_is_public(self):
        response = self.client.get(HEALTH)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'healthy')


class QuickChatTests(APITestCase):
    """
    Functional tests only: the chat view deliberately has no permission
    decorator (CLAUDE.md §4.7), so whether it requires auth depends on the
    active settings module (IsAuthenticated in base/prod, AllowAny in dev).
    These tests bypass that with force_authenticate and assert behavior.
    """

    def setUp(self):
        from users.models import User
        self.client.force_authenticate(
            User.objects.create_user(
                email='ana@test.local', username='ana', password='S3nha-forte-123!'
            )
        )

    @patch('api.views.get_response', return_value=AI_RESULT)
    def test_chat_returns_message_and_sources(self, mock_ai):
        response = self.client.post(CHAT, {'message': 'Preciso de RUC?'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], AI_RESULT['message'])
        self.assertEqual(response.data['sources'], AI_RESULT['sources'])
        mock_ai.assert_called_once_with('Preciso de RUC?')

    @patch('api.views.get_response', side_effect=AIServiceError('Serviço indisponível', 503))
    def test_provider_error_maps_to_its_status_code(self, mock_ai):
        response = self.client.post(CHAT, {'message': 'oi'})

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data['error'], 'Serviço indisponível')

    def test_missing_message_is_400(self):
        response = self.client.post(CHAT, {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_message_over_4000_chars_is_400(self):
        response = self.client.post(CHAT, {'message': 'x' * 4001})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
