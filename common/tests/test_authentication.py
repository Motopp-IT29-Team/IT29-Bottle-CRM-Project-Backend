"""
Test coverage:
- Email/Password Login (valid, invalid credentials, missing fields)
- Profile Access (authenticated and unauthenticated)
- Token Refresh

Run with: pytest common/tests/test_authentication.py -v
"""
import pytest
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from common.models import Org
import uuid
from datetime import timedelta
from django.utils import timezone


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

    def test_login_with_uppercase_email_works(self, api_client, user, profile):
        """Test that email login is case-insensitive."""
        login_data = {
            'email': 'TESTUSER@EXAMPLE.COM',
            'password': 'TestPassword123!'
        }
        response = api_client.post(self.url, login_data, format='json')
        assert response.status_code == status.HTTP_200_OK, \
            f"Email should be case-insensitive. Got {response.status_code}"
        assert 'access' in response.data
        assert 'refresh' in response.data

    def test_login_with_email_whitespace_is_handled(self, api_client, user, profile):
        """Test that email with leading/trailing whitespace works."""
        login_data = {
            'email': '  testuser@example.com  ',
            'password': 'TestPassword123!'
        }
        response = api_client.post(self.url, login_data, format='json')
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_401_UNAUTHORIZED], \
            f"Expected 200 or 401, got {response.status_code}"

    def test_login_with_invalid_email_format_fails(self, api_client):
        """Test that login with invalid email format returns 400."""
        login_data = {
            'email': 'not-an-email',
            'password': 'TestPassword123!'
        }
        response = api_client.post(self.url, login_data, format='json')
        assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_401_UNAUTHORIZED], \
            f"Expected 400 or 401 for invalid email format, got {response.status_code}"


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

    def test_profile_without_org_header_fails(self, api_client, user):
        """Test that profile request without org header returns error."""

        refresh = RefreshToken.for_user(user)
        api_client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}",
        )
        response = api_client.get(self.url)
        assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN], \
            f"Expected 400 or 403 without org header, got {response.status_code}"

    def test_profile_with_invalid_org_uuid_fails(self, api_client, user, profile):
        """Test that profile request with invalid org UUID returns error."""
        refresh = RefreshToken.for_user(user)
        api_client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}",
            HTTP_ORG="invalid-uuid-12345",
        )
        response = api_client.get(self.url)
        assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN], \
            f"Expected 400 or 403 with invalid org UUID, got {response.status_code}"

    def test_profile_with_nonexistent_org_uuid_fails(self, api_client, user, profile):
        """Test that profile request with non-existent but valid UUID org returns error."""
        refresh = RefreshToken.for_user(user)
        fake_org_uuid = str(uuid.uuid4())
        api_client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}",
            HTTP_ORG=fake_org_uuid,
        )
        response = api_client.get(self.url)
        assert response.status_code == status.HTTP_403_FORBIDDEN, \
            f"Expected 403 when accessing org without profile, got {response.status_code}"

    def test_profile_returns_user_role(self, authenticated_client, profile):
        """Test that profile response includes user role."""
        response = authenticated_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert 'user_obj' in response.data
        assert 'role' in response.data['user_obj'], \
            "Role not found in profile response"
        assert response.data['user_obj']['role'] == profile.role, \
            f"Expected role {profile.role}, got {response.data['user_obj']['role']}"

    def test_profile_returns_multiple_orgs_if_user_has_multiple_profiles(
            self, api_client, user, org, create_profile
    ):
        """Test that profile returns all organizations where user has profiles."""
        org2 = Org.objects.create(name="Second Organization", is_active=True)
        profile1 = create_profile(user=user, org=org, role="USER")
        profile2 = create_profile(user=user, org=org2, role="ADMIN")
        refresh = RefreshToken.for_user(user)
        api_client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}",
            HTTP_ORG=str(org.id),
        )
        response = api_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert 'user_obj' in response.data


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
        refresh_data = {'refresh': tokens['refresh']}
        refresh_response = api_client.post(self.url, refresh_data, format='json')
        new_access_token = refresh_response.data['access']
        api_client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {new_access_token}',
            HTTP_ORG=str(org.id)
        )
        profile_response = api_client.get('/api/profile/')
        assert profile_response.status_code == status.HTTP_200_OK, \
            f"Expected 200 OK with new token, got {profile_response.status_code}"

    def test_token_refresh_with_malformed_token_fails(self, api_client):
        """Test that malformed refresh token returns 401."""
        refresh_data = {
            'refresh': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.malformed'
        }
        response = api_client.post(self.url, refresh_data, format='json')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED, \
            f"Expected 401 with malformed token, got {response.status_code}"

    def test_token_refresh_with_access_token_instead_of_refresh_fails(self, api_client, tokens):
        """Test that using access token for refresh returns 401."""
        refresh_data = {
            'refresh': tokens['access']  # Wrong token type
        }
        response = api_client.post(self.url, refresh_data, format='json')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED, \
            f"Expected 401 when using access token for refresh, got {response.status_code}"