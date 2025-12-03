"""
Test coverage:
- Multi-organization access control
- HTTP_ORG header validation
- Profile-based organization switching
- Middleware behavior with org context

Run with: pytest common/tests/test_organization_context.py -v
"""
import uuid
import pytest
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from common.models import Org


@pytest.mark.django_db
class TestOrganizationContext:
    """Test organization context and access control."""

    def test_authenticated_request_with_valid_org_succeeds(
            self, api_client, user, profile, org
    ):
        """Test that authenticated user with valid org header can access protected endpoint."""
        refresh = RefreshToken.for_user(user)
        api_client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}",
            HTTP_ORG=str(org.id),
        )

        response = api_client.get('/api/profile/')
        assert response.status_code == status.HTTP_200_OK, \
            f"Expected 200 OK with valid org, got {response.status_code}"

    def test_authenticated_request_without_org_header_fails(
            self, api_client, user, profile
    ):
        """Test that authenticated user without org header gets 400."""
        refresh = RefreshToken.for_user(user)
        api_client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}",
            # No HTTP_ORG header
        )

        response = api_client.get('/api/profile/')
        assert response.status_code == status.HTTP_403_FORBIDDEN, \
            f"Expected 400 without org header, got {response.status_code}"

    def test_authenticated_request_with_invalid_org_uuid_fails(
            self, api_client, user, profile
    ):
        """Test that request with invalid org UUID returns 404 or 403."""
        refresh = RefreshToken.for_user(user)
        api_client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}",
            HTTP_ORG="not-a-valid-uuid",
        )

        response = api_client.get('/api/profile/')
        assert response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_400_BAD_REQUEST
        ], f"Expected 403/404/400 with invalid UUID, got {response.status_code}"

    def test_authenticated_request_with_nonexistent_org_fails(
            self, api_client, user, profile
    ):
        """Test that request with non-existent org UUID returns 403 or 404."""
        fake_org_id = str(uuid.uuid4())
        refresh = RefreshToken.for_user(user)
        api_client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}",
            HTTP_ORG=fake_org_id,
        )
        response = api_client.get('/api/profile/')
        assert response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND
        ], f"Expected 403/404 with non-existent org, got {response.status_code}"

    def test_user_cannot_access_org_without_profile(
            self, api_client, user, org, create_profile
    ):
        """Test that user without profile in org cannot access that org."""
        org2 = Org.objects.create(name="Other Organization", is_active=True)
        refresh = RefreshToken.for_user(user)
        api_client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}",
            HTTP_ORG=str(org2.id),
        )
        response = api_client.get('/api/profile/')
        assert response.status_code == status.HTTP_403_FORBIDDEN, \
            f"User should not access org without profile. Got {response.status_code}"


@pytest.mark.django_db
class TestMultiOrganizationAccess:
    """Test multi-organization scenarios."""

    def test_user_with_multiple_profiles_can_switch_orgs(
            self, api_client, user, org, create_profile
    ):
        """Test that user with profiles in multiple orgs can switch between them."""
        org1 = org
        profile1 = create_profile(user=user, org=org1, role="USER")
        org2 = Org.objects.create(name="Second Organization", is_active=True)
        profile2 = create_profile(user=user, org=org2, role="ADMIN")
        refresh = RefreshToken.for_user(user)
        api_client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}",
            HTTP_ORG=str(org1.id),
        )
        response1 = api_client.get('/api/profile/')
        assert response1.status_code == status.HTTP_200_OK
        assert response1.data['current_org']['id'] == str(org1.id)
        assert response1.data['user_obj']['role'] == 'USER'
        api_client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}",
            HTTP_ORG=str(org2.id),
        )
        response2 = api_client.get('/api/profile/')
        assert response2.status_code == status.HTTP_200_OK
        assert response2.data['current_org']['id'] == str(org2.id)
        assert response2.data['user_obj']['role'] == 'ADMIN'

    def test_user_profile_role_differs_across_orgs(
            self, api_client, user, org, create_profile
    ):
        """Test that user can have different roles in different orgs."""
        org1 = org
        profile1 = create_profile(user=user, org=org1, role="USER")
        org2 = Org.objects.create(name="Admin Organization", is_active=True)
        profile2 = create_profile(user=user, org=org2, role="ADMIN")
        refresh = RefreshToken.for_user(user)
        api_client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}",
            HTTP_ORG=str(org1.id),
        )
        response1 = api_client.get('/api/profile/')
        assert response1.data['user_obj']['role'] == 'USER'
        api_client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}",
            HTTP_ORG=str(org2.id),
        )
        response2 = api_client.get('/api/profile/')
        assert response2.data['user_obj']['role'] == 'ADMIN'

    def test_inactive_profile_cannot_access_org(
            self, api_client, user, org, create_profile
    ):
        """Test that user with inactive profile cannot access org."""
        profile = create_profile(user=user, org=org, role="USER", is_active=False)
        refresh = RefreshToken.for_user(user)
        api_client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}",
            HTTP_ORG=str(org.id),
        )
        response = api_client.get('/api/profile/')
        assert response.status_code == status.HTTP_403_FORBIDDEN, \
            f"Inactive profile should not access org. Got {response.status_code}"


@pytest.mark.django_db
class TestExemptURLs:
    """Test URLs that don't require org context."""

    def test_login_endpoint_works_without_org_header(self, api_client, user, profile):
        """Test that login endpoint doesn't require org header."""
        login_data = {
            'email': user.email,
            'password': 'TestPassword123!'
        }
        response = api_client.post('/api/auth/login/', login_data, format='json')
        assert response.status_code == status.HTTP_200_OK, \
            f"Login should work without org header. Got {response.status_code}"

    def test_google_auth_endpoint_works_without_org_header(self, api_client):
        """Test that Google auth endpoint doesn't require org header."""
        google_data = {
            'token': 'fake-google-token'
        }
        response = api_client.post('/api/auth/google/', google_data, format='json')
        assert response.status_code != status.HTTP_403_FORBIDDEN, \
            "Google auth should not require org header"

    def test_org_list_endpoint_works_without_org_header(
            self, api_client, user, profile
    ):
        """Test that org list endpoint works without org header."""
        refresh = RefreshToken.for_user(user)
        api_client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}",
        )
        response = api_client.get('/api/org/')
        assert response.status_code == status.HTTP_200_OK, \
            f"Org list should work without org header. Got {response.status_code}"


@pytest.mark.django_db
class TestOrganizationDataIsolation:
    """Test that data is properly isolated between organizations."""

    def test_user_cannot_see_data_from_other_org(
            self, api_client, user, org, create_user, create_profile
    ):
        """Test that user cannot access users list from org where they have no profile."""
        org1 = org
        admin_profile1 = create_profile(user=user, org=org1, role="ADMIN")
        org2 = Org.objects.create(name="Other Company", is_active=True)
        other_user = create_user(email="other@company.com")
        other_profile = create_profile(user=other_user, org=org2, role="USER")
        refresh = RefreshToken.for_user(user)
        api_client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}",
            HTTP_ORG=str(org2.id),
        )

        response = api_client.get('/api/users/')
        assert response.status_code == status.HTTP_403_FORBIDDEN, \
            f"User should not access other org's data. Got {response.status_code}"

    def test_user_lists_are_org_specific(
            self, api_client, user, org, create_user, create_profile, admin_user, admin_profile
    ):
        """Test that users list returns only users from current org."""
        org1 = org
        org2 = Org.objects.create(name="Second Company", is_active=True)
        user2 = create_user(email="user2@company.com")
        profile2 = create_profile(user=user2, org=org2, role="USER")
        refresh = RefreshToken.for_user(admin_user)
        api_client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}",
            HTTP_ORG=str(org1.id),
        )
        response = api_client.get('/api/users/')
        assert response.status_code == status.HTTP_200_OK
        user_emails = [u['user_details']['email'] for u in response.data['users']]
        assert admin_user.email in user_emails
        assert user2.email not in user_emails, \
            "Users from other org should not appear in list"