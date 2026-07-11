from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from users.models import User

REGISTER = reverse('auth-register')
TOKEN = reverse('auth-token-obtain')
REFRESH = reverse('auth-token-refresh')
ME = reverse('auth-me')


def register_payload(**overrides):
    payload = {
        'email': 'ana@test.local',
        'username': 'ana',
        'password': 'S3nha-forte-123!',
        'password2': 'S3nha-forte-123!',
    }
    payload.update(overrides)
    return payload


class RegisterTests(APITestCase):
    def setUp(self):
        cache.clear()  # anon throttle counters persist in LocMem across tests

    def test_register_creates_user(self):
        response = self.client.post(REGISTER, register_payload(language_preference='pt'))

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['email'], 'ana@test.local')
        self.assertEqual(response.data['language_preference'], 'pt')
        self.assertNotIn('password', response.data)
        self.assertTrue(User.objects.filter(email='ana@test.local').exists())

    def test_language_preference_defaults_to_spanish(self):
        response = self.client.post(REGISTER, register_payload())
        self.assertEqual(response.data['language_preference'], 'es')

    def test_password_mismatch_rejected(self):
        response = self.client.post(REGISTER, register_payload(password2='outra-senha'))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.exists())

    def test_duplicate_email_rejected(self):
        self.client.post(REGISTER, register_payload())
        response = self.client.post(REGISTER, register_payload(username='outro'))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(User.objects.count(), 1)


class TokenTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            email='ana@test.local', username='ana', password='S3nha-forte-123!'
        )

    def test_obtain_pair_with_email_login(self):
        response = self.client.post(
            TOKEN, {'email': 'ana@test.local', 'password': 'S3nha-forte-123!'}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_wrong_password_rejected(self):
        response = self.client.post(
            TOKEN, {'email': 'ana@test.local', 'password': 'errada'}
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_returns_new_access_and_rotates_refresh(self):
        tokens = self.client.post(
            TOKEN, {'email': 'ana@test.local', 'password': 'S3nha-forte-123!'}
        ).data

        response = self.client.post(REFRESH, {'refresh': tokens['refresh']})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        # ROTATE_REFRESH_TOKENS: a fresh refresh token comes back too —
        # the frontend token store depends on this.
        self.assertIn('refresh', response.data)
        self.assertNotEqual(response.data['refresh'], tokens['refresh'])


class MeTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            email='ana@test.local', username='ana', password='S3nha-forte-123!'
        )

    def test_requires_authentication(self):
        # `me` carries an explicit IsAuthenticated decorator, so this holds
        # even under dev settings where the default permission is AllowAny.
        response = self.client.get(ME)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_returns_profile_with_bearer_token(self):
        access = self.client.post(
            TOKEN, {'email': 'ana@test.local', 'password': 'S3nha-forte-123!'}
        ).data['access']

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        response = self.client.get(ME)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], 'ana@test.local')
