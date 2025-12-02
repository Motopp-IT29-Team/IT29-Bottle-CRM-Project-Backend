"""
Test coverage:
- Google OAuth login flow
- User creation from Google data
- User lookup by email
- Token generation
- Error handling

Run with: pytest common/tests/test_google_oauth.py -v
"""
import json
from unittest.mock import patch, MagicMock
import pytest
from rest_framework import status
from common.models import User


@pytest.mark.django_db
class TestGoogleOAuth:
    """Test Google OAuth authentication."""
    url = "/api/auth/google/"

    @patch('common.views.requests.get')
    def test_valid_google_token_returns_jwt_tokens(self, mock_requests_get, api_client):
        """Test that valid Google token returns JWT access and refresh tokens."""
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            'email': 'googleuser@example.com',
            'given_name': 'Google',
            'family_name': 'User',
            'picture': 'https://example.com/photo.jpg'
        })
        mock_requests_get.return_value = mock_response
        google_data = {'token': 'valid-google-token-12345'}
        response = api_client.post(self.url, google_data, format='json')
        assert response.status_code == status.HTTP_200_OK, \
            f"Expected 200 OK, got {response.status_code}. Response: {response.data}"
        assert 'access_token' in response.data
        assert 'refresh_token' in response.data
        assert 'username' in response.data
        assert response.data['username'] == 'googleuser@example.com'

    @patch('common.views.requests.get')
    def test_invalid_google_token_returns_error(self, mock_requests_get, api_client):
        """Test that invalid Google token returns error message."""
        mock_response = MagicMock()
        mock_response.text = json.dumps({'error': 'invalid_token'})
        mock_requests_get.return_value = mock_response
        google_data = {'token': 'invalid-token'}
        response = api_client.post(self.url, google_data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert 'message' in response.data
        assert 'wrong google token' in response.data['message']

    @patch('common.views.requests.get')
    def test_google_login_creates_new_user(self, mock_requests_get, api_client):
        """Test that Google login creates new user if email doesn't exist."""
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            'email': 'newgoogle@example.com',
            'given_name': 'New',
            'family_name': 'GoogleUser',
            'picture': 'https://example.com/newphoto.jpg'
        })
        mock_requests_get.return_value = mock_response
        google_data = {'token': 'valid-google-token'}
        response = api_client.post(self.url, google_data, format='json')
        assert response.status_code == status.HTTP_200_OK
        user = User.objects.filter(email='newgoogle@example.com').first()
        assert user is not None
        assert user.first_name == 'New'
        assert user.last_name == 'GoogleUser'
        assert user.profile_pic == 'https://example.com/newphoto.jpg'
        assert not user.has_usable_password()

    @patch('common.views.requests.get')
    def test_google_login_returns_tokens_for_existing_user(self, mock_requests_get, api_client, user):
        """Test that Google login returns tokens for existing user."""
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            'email': user.email,
            'given_name': 'Test',
            'family_name': 'User',
            'picture': 'https://example.com/photo.jpg'
        })
        mock_requests_get.return_value = mock_response
        google_data = {'token': 'valid-google-token'}
        response = api_client.post(self.url, google_data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert 'access_token' in response.data
        assert 'refresh_token' in response.data
        assert response.data['username'] == user.email
        assert str(response.data['user_id']) == str(user.id)

    @patch('common.views.requests.get')
    def test_google_login_updates_missing_user_names(self, mock_requests_get, api_client, db):
        """Test that Google login updates first_name and last_name if missing."""
        user = User.objects.create(
            email='incomplete@example.com',
            first_name='',
            last_name='',
            is_active=True
        )
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            'email': 'incomplete@example.com',
            'given_name': 'Updated',
            'family_name': 'Name',
            'picture': 'https://example.com/photo.jpg'
        })
        mock_requests_get.return_value = mock_response
        google_data = {'token': 'valid-google-token'}
        response = api_client.post(self.url, google_data, format='json')
        assert response.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.first_name == 'Updated'
        assert user.last_name == 'Name'

    @patch('common.views.requests.get')
    def test_google_login_does_not_overwrite_existing_names(self, mock_requests_get, api_client, user):
        """Test that Google login does not overwrite existing first_name and last_name."""
        original_first = user.first_name
        original_last = user.last_name
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            'email': user.email,
            'given_name': 'Different',
            'family_name': 'Names',
            'picture': 'https://example.com/photo.jpg'
        })
        mock_requests_get.return_value = mock_response
        google_data = {'token': 'valid-google-token'}
        response = api_client.post(self.url, google_data, format='json')
        assert response.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.first_name == original_first
        assert user.last_name == original_last

    @patch('common.views.requests.get')
    def test_google_login_updates_existing_profiles_names(self, mock_requests_get, api_client, org, create_user, create_profile):
        """Test that Google login updates existing profiles if names are missing."""
        user = create_user(email='profileuser@example.com', first_name='', last_name='')
        profile = create_profile(user=user, org=org, role='USER', first_name='', last_name='')
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            'email': 'profileuser@example.com',
            'given_name': 'Profile',
            'family_name': 'Updated',
            'picture': 'https://example.com/photo.jpg'
        })
        mock_requests_get.return_value = mock_response
        google_data = {'token': 'valid-google-token'}
        response = api_client.post(self.url, google_data, format='json')
        assert response.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        profile.refresh_from_db()
        assert user.first_name == 'Profile'
        assert user.last_name == 'Updated'
        assert profile.first_name == 'Profile'
        assert profile.last_name == 'Updated'

    @patch('common.views.requests.get')
    def test_google_login_without_token_fails(self, mock_requests_get, api_client):
        """Test that Google login without token fails."""
        mock_response = MagicMock()
        mock_response.text = json.dumps({'error': 'invalid_request'})
        mock_requests_get.return_value = mock_response
        google_data = {}
        response = api_client.post(self.url, google_data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert 'message' in response.data

    @patch('common.views.requests.get')
    def test_google_login_with_minimal_data(self, mock_requests_get, api_client):
        """Test that Google login works with minimal Google data."""
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            'email': 'minimal@example.com'
        })
        mock_requests_get.return_value = mock_response
        google_data = {'token': 'valid-google-token'}
        response = api_client.post(self.url, google_data, format='json')
        assert response.status_code == status.HTTP_200_OK
        user = User.objects.filter(email='minimal@example.com').first()
        assert user is not None
        assert user.first_name == ''
        assert user.last_name == ''