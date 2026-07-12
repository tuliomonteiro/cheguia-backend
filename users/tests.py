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


PASSWORD_CHANGE = reverse('auth-password-change')


class UpdateMeTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            email='ana@test.local', username='ana', password='S3nha-forte-123!',
            language_preference='es',
        )
        self.client.force_authenticate(self.user)

    def test_patch_updates_language_preference(self):
        response = self.client.patch(ME, {'language_preference': 'pt'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['language_preference'], 'pt')
        self.user.refresh_from_db()
        self.assertEqual(self.user.language_preference, 'pt')

    def test_patch_cannot_change_email(self):
        response = self.client.patch(ME, {'email': 'outro@test.local'})

        # Unknown/immutable fields are ignored, not applied.
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'ana@test.local')

    def test_invalid_language_rejected(self):
        response = self.client.patch(ME, {'language_preference': 'en'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patch_requires_authentication(self):
        self.client.force_authenticate(None)
        response = self.client.patch(ME, {'language_preference': 'pt'})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PasswordChangeTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            email='ana@test.local', username='ana', password='S3nha-forte-123!'
        )
        self.client.force_authenticate(self.user)

    def _change(self, current='S3nha-forte-123!', new='N0va-senha-456!', new2=None):
        return self.client.post(PASSWORD_CHANGE, {
            'current_password': current,
            'new_password': new,
            'new_password2': new2 if new2 is not None else new,
        })

    def test_change_password_and_login_with_new_one(self):
        response = self._change()
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        self.client.force_authenticate(None)
        old = self.client.post(TOKEN, {'email': 'ana@test.local', 'password': 'S3nha-forte-123!'})
        new = self.client.post(TOKEN, {'email': 'ana@test.local', 'password': 'N0va-senha-456!'})
        self.assertEqual(old.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(new.status_code, status.HTTP_200_OK)

    def test_wrong_current_password_rejected(self):
        response = self._change(current='errada')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('current_password', response.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('S3nha-forte-123!'))

    def test_mismatched_new_passwords_rejected(self):
        response = self._change(new2='D1ferente-789!')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_weak_new_password_rejected(self):
        response = self._change(new='123', new2='123')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_requires_authentication(self):
        self.client.force_authenticate(None)
        self.assertEqual(self._change().status_code, status.HTTP_401_UNAUTHORIZED)


class AdminBackofficeTests(APITestCase):
    """The admin is the backoffice: staff-only, invisible to regular users."""

    def setUp(self):
        cache.clear()
        self.staff = User.objects.create_user(
            email='staff@test.local', username='staff', password='S3nha-adm-1!',
            is_staff=True, is_superuser=True,
        )
        self.regular = User.objects.create_user(
            email='user@test.local', username='user', password='S3nha-usr-1!'
        )

    def test_regular_user_is_redirected_to_admin_login(self):
        self.client.force_login(self.regular)
        response = self.client.get('/admin/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response['Location'])

    def test_staff_sees_index_and_all_registered_changelists(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get('/admin/').status_code, 200)
        for url in (
            reverse('admin:users_user_changelist'),
            reverse('admin:chat_chatsession_changelist'),
            reverse('admin:chat_message_changelist'),
            reverse('admin:documents_document_changelist'),
            reverse('admin:ai_embeddingcache_changelist'),
        ):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_staff_can_open_user_change_form_and_flip_premium(self):
        self.client.force_login(self.staff)
        url = reverse('admin:users_user_change', args=[self.regular.pk])
        self.assertEqual(self.client.get(url).status_code, 200)

        self.regular.is_premium = True
        self.regular.save(update_fields=['is_premium'])
        self.regular.refresh_from_db()
        self.assertTrue(self.regular.is_premium)
