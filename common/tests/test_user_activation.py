"""
Test coverage:
- GET request (validate activation link)
- POST request (activate user with password)
- Invalid/expired tokens
- Edge cases

Run with: pytest common/tests/test_user_activation.py -v
"""
import pytest
from rest_framework import status


@pytest.mark.django_db
class TestActivationLinkValidation:
    """Test GET request - validate activation link before showing password form."""

    def test_valid_activation_link_returns_user_email(self, api_client, inactive_user_with_activation):
        """Test that valid activation link returns 200 and user email."""
        url = inactive_user_with_activation['activation_url']
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK, \
            f"Expected 200 OK, got {response.status_code}. Response: {response.data}"
        assert 'message' in response.data
        assert response.data['message'] == 'Link is valid'
        assert 'email' in response.data
        assert response.data['email'] == inactive_user_with_activation['user'].email

    def test_activation_link_with_invalid_uid_fails(self, api_client, inactive_user_with_activation):
        """Test that invalid UID returns 400."""
        token = inactive_user_with_activation['token']
        activation_key = inactive_user_with_activation['activation_key']
        url = f'/api/auth/activate-user/invalid-uid/{token}/{activation_key}/'

        response = api_client.get(url)
        assert response.status_code == status.HTTP_400_BAD_REQUEST, \
            f"Expected 400 Bad Request, got {response.status_code}"
        assert 'error' in response.data

    def test_activation_link_with_invalid_token_fails(self, api_client, inactive_user_with_activation):
        """Test that invalid token returns 400."""
        uid = inactive_user_with_activation['uid']
        activation_key = inactive_user_with_activation['activation_key']
        url = f'/api/auth/activate-user/{uid}/invalid-token-12345/{activation_key}/'

        response = api_client.get(url)
        assert response.status_code == status.HTTP_400_BAD_REQUEST, \
            f"Expected 400 Bad Request, got {response.status_code}"
        assert 'error' in response.data

    def test_activation_link_with_invalid_activation_key_fails(self, api_client, inactive_user_with_activation):
        """Test that invalid activation_key returns 400."""
        uid = inactive_user_with_activation['uid']
        token = inactive_user_with_activation['token']
        url = f'/api/auth/activate-user/{uid}/{token}/wrong-activation-key/'

        response = api_client.get(url)
        assert response.status_code == status.HTTP_400_BAD_REQUEST, \
            f"Expected 400 Bad Request, got {response.status_code}"
        assert 'error' in response.data
        assert 'Invalid or expired activation link' in response.data['error']

    def test_activation_link_for_already_active_user_fails(self, api_client, inactive_user_with_activation):
        """Test that activation link for active user returns 400."""
        user = inactive_user_with_activation['user']
        user.is_active = True
        user.save()

        url = inactive_user_with_activation['activation_url']
        response = api_client.get(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST, \
            f"Expected 400 Bad Request, got {response.status_code}"
        assert 'error' in response.data
        assert 'Account already activated' in response.data['error']

    def test_activation_link_with_nonexistent_user_fails(self, api_client):
        """Test that activation link with non-existent user UID returns 400."""
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes
        import uuid

        fake_uid = urlsafe_base64_encode(force_bytes(str(uuid.uuid4())))
        url = f'/api/auth/activate-user/{fake_uid}/some-token/some-key/'

        response = api_client.get(url)
        assert response.status_code == status.HTTP_400_BAD_REQUEST, \
            f"Expected 400 Bad Request, got {response.status_code}"


@pytest.mark.django_db
class TestUserActivation:
    """Test POST request - activate user with password."""

    def test_activate_user_with_valid_data_activates_and_returns_tokens(
            self, api_client, inactive_user_with_activation
    ):
        """Test successful activation with password sets user active and returns JWT tokens."""
        url = inactive_user_with_activation['activation_url']
        activation_data = {
            'password': 'NewSecurePass123!',
            'password_confirm': 'NewSecurePass123!'
        }

        response = api_client.post(url, activation_data, format='json')

        assert response.status_code == status.HTTP_200_OK, \
            f"Expected 200 OK, got {response.status_code}. Response: {response.data}"
        assert 'message' in response.data
        assert response.data['message'] == 'Account activated successfully'
        assert 'access' in response.data
        assert 'refresh' in response.data
        assert 'user' in response.data
        assert response.data['user']['email'] == inactive_user_with_activation['user'].email

        user = inactive_user_with_activation['user']
        user.refresh_from_db()
        assert user.is_active is True
        assert user.activation_key is None

    def test_activated_user_can_login_with_new_password(
            self, api_client, inactive_user_with_activation
    ):
        """Test that after activation, user can login with the new password."""
        url = inactive_user_with_activation['activation_url']
        activation_data = {
            'password': 'NewSecurePass123!',
            'password_confirm': 'NewSecurePass123!'
        }
        api_client.post(url, activation_data, format='json')

        login_data = {
            'email': inactive_user_with_activation['user'].email,
            'password': 'NewSecurePass123!'
        }
        login_response = api_client.post('/api/auth/login/', login_data, format='json')

        assert login_response.status_code == status.HTTP_200_OK, \
            f"User should be able to login after activation. Got {login_response.status_code}"
        assert 'access' in login_response.data
        assert 'refresh' in login_response.data

    def test_activation_without_password_fails(self, api_client, inactive_user_with_activation):
        """Test that activation without password returns 400."""
        url = inactive_user_with_activation['activation_url']
        activation_data = {
            'password_confirm': 'NewSecurePass123!'
        }

        response = api_client.post(url, activation_data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST, \
            f"Expected 400 Bad Request, got {response.status_code}"
        assert 'error' in response.data
        assert 'Password is required' in response.data['error']

    def test_activation_with_mismatched_passwords_fails(self, api_client, inactive_user_with_activation):
        """Test that mismatched passwords return 400."""
        url = inactive_user_with_activation['activation_url']
        activation_data = {
            'password': 'NewSecurePass123!',
            'password_confirm': 'DifferentPassword456!'
        }

        response = api_client.post(url, activation_data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST, \
            f"Expected 400 Bad Request, got {response.status_code}"
        assert 'error' in response.data
        assert 'Passwords do not match' in response.data['error']

    def test_activation_with_short_password_fails(self, api_client, inactive_user_with_activation):
        """Test that password shorter than 8 characters returns 400."""
        url = inactive_user_with_activation['activation_url']
        activation_data = {
            'password': 'Short1!',
            'password_confirm': 'Short1!'
        }

        response = api_client.post(url, activation_data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST, \
            f"Expected 400 Bad Request, got {response.status_code}"
        assert 'error' in response.data
        assert 'at least 8 characters' in response.data['error']

    def test_activation_of_already_active_user_fails(self, api_client, inactive_user_with_activation):
        """Test that activating an already active user returns 400."""
        user = inactive_user_with_activation['user']
        user.is_active = True
        user.save()

        url = inactive_user_with_activation['activation_url']
        activation_data = {
            'password': 'NewSecurePass123!',
            'password_confirm': 'NewSecurePass123!'
        }

        response = api_client.post(url, activation_data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST, \
            f"Expected 400 Bad Request, got {response.status_code}"
        assert 'error' in response.data
        assert 'Account already activated' in response.data['error']

    def test_activation_with_invalid_uid_fails(self, api_client, inactive_user_with_activation):
        """Test that POST with invalid UID returns 400."""
        token = inactive_user_with_activation['token']
        activation_key = inactive_user_with_activation['activation_key']
        url = f'/api/auth/activate-user/invalid-uid/{token}/{activation_key}/'

        activation_data = {
            'password': 'NewSecurePass123!',
            'password_confirm': 'NewSecurePass123!'
        }

        response = api_client.post(url, activation_data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST, \
            f"Expected 400 Bad Request, got {response.status_code}"

    def test_activation_with_invalid_token_fails(self, api_client, inactive_user_with_activation):
        """Test that POST with invalid token returns 400."""
        uid = inactive_user_with_activation['uid']
        activation_key = inactive_user_with_activation['activation_key']
        url = f'/api/auth/activate-user/{uid}/invalid-token/{activation_key}/'

        activation_data = {
            'password': 'NewSecurePass123!',
            'password_confirm': 'NewSecurePass123!'
        }

        response = api_client.post(url, activation_data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST, \
            f"Expected 400 Bad Request, got {response.status_code}"

    def test_activation_with_wrong_activation_key_fails(self, api_client, inactive_user_with_activation):
        """Test that POST with wrong activation_key returns 400."""
        uid = inactive_user_with_activation['uid']
        token = inactive_user_with_activation['token']
        url = f'/api/auth/activate-user/{uid}/{token}/wrong-key/'

        activation_data = {
            'password': 'NewSecurePass123!',
            'password_confirm': 'NewSecurePass123!'
        }

        response = api_client.post(url, activation_data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST, \
            f"Expected 400 Bad Request, got {response.status_code}"
        assert 'error' in response.data