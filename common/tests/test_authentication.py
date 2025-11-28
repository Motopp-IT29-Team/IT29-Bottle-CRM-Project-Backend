"""
Authentication tests for Bottle CRM.

Test coverage:
- Email/Password Login (valid, invalid credentials, missing fields)
- Profile Access (authenticated and unauthenticated)
- Token Refresh

Run with: pytest common/tests/test_authentication.py -v
"""
import pytest
from rest_framework import status


@pytest.mark.django_db
class TestLogin:
    """Test email/password login functionality."""
    url = "/api/auth/login/"

    def test_login_with_valid_credentials_returns_tokens(self, api_client, user, profile):
        """
        Test that login with correct email and password returns JWT tokens.

        This is our first test to verify that:
        1. Database fixtures work (user, profile created)
        2. API client works
        3. Login endpoint works
        4. JWT tokens are returned
        """
        login_data = {
            'email': 'testuser@example.com',
            'password': 'TestPassword123!'
        }
        response = api_client.post(self.url, login_data, format='json')
        assert response.status_code == status.HTTP_200_OK, \
            f"Expected 200 OK, got {response.status_code}. Response: {response.data}"
        assert 'access' in response.data, \
            "Access token not found in response"
        assert 'refresh' in response.data, \
            "Refresh token not found in response"
        assert response.data['access'] is not None, \
            "Access token is None"
        assert response.data['refresh'] is not None, \
            "Refresh token is None"

    def test_login_with_wrong_password_fails(self, api_client, user):
        """Test that login with incorrect password returns 401."""
        login_data = {
            'email': 'testuser@example.com',
            'password': 'WrongPassword123!'
        }
        response = api_client.post(self.url, login_data, format='json')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED, \
            f"Expected 401 Unauthorized, got {response.status_code}"

    def test_login_with_inactive_user_fails(self, api_client, inactive_user):
        """Test that inactive user cannot login."""
        login_data = {
            'email': 'inactive@example.com',
            'password': 'TestPassword123!'
        }
        response = api_client.post(self.url, login_data, format='json')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED, \
            f"Expected 401 Unauthorized, got {response.status_code}"

    def test_login_with_nonexistent_email_fails(self, api_client):
        """Test that login with non-existent email returns 401."""
        login_data = {
            'email': 'nonexistent@example.com',
            'password': 'TestPassword123!'
        }
        response = api_client.post(self.url, login_data, format='json')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED, \
            f"Expected 401 Unauthorized, got {response.status_code}"

    def test_login_with_missing_email_fails(self, api_client):
        """Test that login without email returns 400."""
        login_data = {
            'password': 'TestPassword123!'
        }
        response = api_client.post(self.url, login_data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST, \
            f"Expected 400 Bad Request, got {response.status_code}"

    def test_login_with_missing_password_fails(self, api_client):
        """Test that login without password returns 400."""
        login_data = {
            'email': 'testuser@example.com'
        }
        response = api_client.post(self.url, login_data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST, \
            f"Expected 400 Bad Request, got {response.status_code}"

    def test_login_with_empty_fields_fails(self, api_client):
        """Test that login with empty email and password returns 400."""
        login_data = {
            'email': '',
            'password': ''
        }
        response = api_client.post(self.url, login_data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST, \
            f"Expected 400 Bad Request, got {response.status_code}"


@pytest.mark.django_db
class TestProfileAccess:
    """Test profile access with authentication."""
    url = "/api/profile/"

    def test_authenticated_user_can_access_profile(self, authenticated_client, user):
        """Test that authenticated user can access their profile."""
        response = authenticated_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK, \
            f"Expected 200 OK, got {response.status_code}"
        assert 'user_obj' in response.data, \
            "user_obj not found in response"
        assert response.data['user_obj']['user_details']['email'] == user.email, \
            f"Expected email {user.email}, got {response.data['user_obj']['user']['email']}"

    def test_unauthenticated_user_cannot_access_profile(self, api_client):
        """Test that unauthenticated user gets 401."""
        response = api_client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED, \
            f"Expected 401 Unauthorized, got {response.status_code}"

    def test_profile_returns_organization_info(self, authenticated_client, org):
        """Test that profile response includes organization information."""
        response = authenticated_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert 'current_org' in response.data, \
            "current_org not found in response"
        assert response.data['current_org']['name'] == org.name, \
            f"Expected org name {org.name}, got {response.data['current_org']['name']}"


@pytest.mark.django_db
class TestTokenRefresh:
    """Test JWT token refresh functionality."""
    url = "/api/auth/refresh-token/"

    def test_token_refresh_with_valid_token_returns_new_access_token(self, api_client, tokens):
        """Test that valid refresh token returns new access token."""
        refresh_data = {
            'refresh': tokens['refresh']
        }
        response = api_client.post(self.url, refresh_data, format='json')
        assert response.status_code == status.HTTP_200_OK, \
            f"Expected 200 OK, got {response.status_code}"
        assert 'access' in response.data, \
            "access token not found in response"
        assert response.data['access'] is not None, \
            "access token is None"
        assert response.data['access'] != tokens['access'], \
            "New access token is the same as original"

    def test_token_refresh_with_invalid_token_fails(self, api_client):
        """Test that invalid refresh token returns 401."""
        refresh_data = {
            'refresh': 'invalid_refresh_token_12345'
        }
        response = api_client.post(self.url, refresh_data, format='json')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED, \
            f"Expected 401 Unauthorized, got {response.status_code}"

    def test_token_refresh_without_token_fails(self, api_client):
        """Test that request without refresh token returns 400."""
        refresh_data = {}
        response = api_client.post(self.url, refresh_data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST, \
            f"Expected 400 Bad Request, got {response.status_code}"

    def test_refreshed_token_can_be_used_for_authentication(self, api_client, tokens, org, profile):
        """Test that new access token from refresh works for authenticated requests."""
        # Arrange - get new access token
        refresh_data = {'refresh': tokens['refresh']}
        refresh_response = api_client.post(self.url, refresh_data, format='json')
        new_access_token = refresh_response.data['access']

        # Act - use new token to access protected endpoint
        api_client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {new_access_token}',
            HTTP_ORG=str(org.id)
        )
        profile_response = api_client.get('/api/profile/')

        # Assert
        assert profile_response.status_code == status.HTTP_200_OK, \
            f"Expected 200 OK with new token, got {profile_response.status_code}"
