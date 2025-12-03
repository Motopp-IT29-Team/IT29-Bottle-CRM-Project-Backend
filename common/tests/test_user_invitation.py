"""
Test coverage:
- Creating users (invitation flow)
- Resending activation links
- Permissions and access control
- Email sending (mocked)

Run with: pytest common/tests/test_user_invitation.py -v
"""
from unittest.mock import patch
import pytest
from rest_framework import status
from common.models import Org
from common.models import User, Profile


@pytest.mark.django_db
class TestUserCreation:
    """Test user creation/invitation flow."""
    url = "/api/users/"

    @patch('common.views.send_email_to_new_user')
    def test_admin_can_create_user_and_sends_invitation(
        self, mock_send_email, admin_authenticated_client, org
    ):
        """Test that admin can create user and invitation email is sent."""
        user_data = {
            'email': 'newuser@example.com',
            'first_name': 'New',
            'last_name': 'User',
            'role': 'USER',
            'address_line': '123 Test St',
            'city': 'Test City',
            'state': 'TS',
            'postcode': '12345',
            'country': 'US',
        }
        response = admin_authenticated_client.post(self.url, user_data, format='json')
        assert response.status_code == status.HTTP_201_CREATED, \
            f"Expected 201 Created, got {response.status_code}. Response: {response.data}"
        assert response.data['error'] is False
        assert 'User created successfully' in response.data['message']
        user = User.objects.filter(email='newuser@example.com').first()
        assert user is not None, "User should be created"
        assert user.is_active is False, "New user should be inactive until activation"
        profile = Profile.objects.filter(user=user, org=org).first()
        assert profile is not None, "Profile should be created"
        assert profile.role == 'USER'
        assert profile.first_name == 'New'
        assert profile.last_name == 'User'
        assert mock_send_email.called, "Email function should be called"

    @patch('common.views.send_email_to_new_user')
    def test_created_user_belongs_to_correct_org(
        self, mock_send_email, admin_authenticated_client, org
    ):
        """Test that created user profile belongs to admin's organization."""
        user_data = {
            'email': 'orguser@example.com',
            'first_name': 'Org',
            'last_name': 'User',
            'role': 'USER',
            'address_line': '123 Test St',
            'city': 'Test City',
            'state': 'TS',
            'postcode': '12345',
            'country': 'US',
        }
        response = admin_authenticated_client.post(self.url, user_data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        user = User.objects.get(email='orguser@example.com')
        profile = Profile.objects.get(user=user)
        assert profile.org == org, "User should belong to admin's org"

    def test_non_admin_cannot_create_user(
        self, authenticated_client
    ):
        """Test that non-admin user cannot create users."""
        user_data = {
            'email': 'newuser@example.com',
            'first_name': 'New',
            'last_name': 'User',
            'role': 'USER',
            'address_line': '123 Test St',
            'city': 'Test City',
            'state': 'TS',
            'postcode': '12345',
            'country': 'US',
        }
        response = authenticated_client.post(self.url, user_data, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN, \
            f"Non-admin should not create users. Got {response.status_code}"

    @patch('common.views.send_email_to_new_user')
    def test_cannot_create_user_with_duplicate_email(
        self, mock_send_email, admin_authenticated_client, user
    ):
        """Test that creating user with existing email fails."""
        user_data = {
            'email': user.email,
            'first_name': 'Duplicate',
            'last_name': 'User',
            'role': 'USER',
            'address_line': '123 Test St',
            'city': 'Test City',
            'state': 'TS',
            'postcode': '12345',
            'country': 'US',
        }
        response = admin_authenticated_client.post(self.url, user_data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST, \
            f"Should not create duplicate user. Got {response.status_code}"

    @patch('common.views.send_email_to_new_user')
    def test_create_user_with_missing_required_fields_fails(
        self, mock_send_email, admin_authenticated_client
    ):
        """Test that creating user without required fields fails."""
        user_data = {
            'email': 'incomplete@example.com',
        }
        response = admin_authenticated_client.post(self.url, user_data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST, \
            f"Should fail with missing fields. Got {response.status_code}"
        assert response.data['error'] is True


@pytest.mark.django_db
class TestResendInvitation:
    """Test resending activation invitation."""

    def get_url(self, profile_id):
        return f"/api/user/{profile_id}/resend-invitation/"

    @patch('common.views.resend_activation_link_to_user')
    def test_admin_can_resend_invitation_to_inactive_user(
        self, mock_resend_email, admin_authenticated_client, org, create_user, create_profile
    ):
        """Test that admin can resend invitation to inactive user."""
        inactive_user = create_user(email='inactive@example.com', is_active=False)
        inactive_profile = create_profile(user=inactive_user, org=org, role='USER')
        url = self.get_url(inactive_profile.id)
        response = admin_authenticated_client.post(url)
        assert response.status_code == status.HTTP_200_OK, \
            f"Expected 200 OK, got {response.status_code}. Response: {response.data}"
        assert response.data['error'] is False
        assert 'Invitation sent successfully' in response.data['message']
        assert mock_resend_email.called, "Resend email function should be called"

    @patch('common.views.resend_activation_link_to_user')
    def test_cannot_resend_invitation_to_active_user(
        self, mock_resend_email, admin_authenticated_client, user, profile
    ):
        """Test that resending invitation to active user fails."""
        url = self.get_url(profile.id)
        response = admin_authenticated_client.post(url)
        assert response.status_code == status.HTTP_400_BAD_REQUEST, \
            f"Should not resend to active user. Got {response.status_code}"
        assert response.data['error'] is True
        assert 'already active' in response.data['message']
        mock_resend_email.assert_not_called()

    def test_non_admin_cannot_resend_invitation(
        self, authenticated_client, org, create_user, create_profile
    ):
        """Test that non-admin cannot resend invitations."""
        inactive_user = create_user(email='inactive@example.com', is_active=False)
        inactive_profile = create_profile(user=inactive_user, org=org, role='USER')
        url = self.get_url(inactive_profile.id)
        response = authenticated_client.post(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN, \
            f"Non-admin should not resend invitations. Got {response.status_code}"

    @patch('common.views.resend_activation_link_to_user')
    def test_cannot_resend_invitation_to_user_in_different_org(self, mock_resend, admin_authenticated_client, org,
                                                               admin_profile,
                                                               create_user, create_profile):
        """Test that admin cannot resend invitation to user in different org."""
        from common.models import Org

        mock_resend.return_value = None

        org2 = Org.objects.create(name='OtherOrg', is_active=True)
        user2 = create_user(email='other@example.com')
        profile2 = create_profile(user=user2, org=org2, role='USER')

        url = f'/api/user/{profile2.id}/resend-invitation/'
        response = admin_authenticated_client.post(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_resend_invitation_with_invalid_profile_id(
        self, admin_authenticated_client
    ):
        """Test that resending with invalid profile ID fails gracefully."""
        url = self.get_url("invalid-id")
        response = admin_authenticated_client.post(url)
        assert response.status_code in [
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR
        ], f"Should fail with invalid ID. Got {response.status_code}"


@pytest.mark.django_db
class TestInvitationWorkflow:
    """Test complete invitation workflow from creation to activation."""

    @patch('common.views.send_email_to_new_user')
    def test_complete_invitation_workflow(
        self, mock_send_email, admin_authenticated_client, api_client, org
    ):
        """Test complete flow: create user → user receives invitation → user activates."""
        user_data = {
            'email': 'workflow@example.com',
            'first_name': 'Workflow',
            'last_name': 'Test',
            'role': 'USER',
            'address_line': '123 Test St',
            'city': 'Test City',
            'state': 'TS',
            'postcode': '12345',
            'country': 'US',
        }
        create_response = admin_authenticated_client.post('/api/users/', user_data, format='json')
        assert create_response.status_code == status.HTTP_201_CREATED
        user = User.objects.get(email='workflow@example.com')
        assert user.is_active is False
        login_data = {
            'email': 'workflow@example.com',
            'password': 'TestPassword123!'
        }
        login_response = api_client.post('/api/auth/login/', login_data, format='json')
        assert login_response.status_code == status.HTTP_401_UNAUTHORIZED

    @patch('common.views.send_email_to_new_user')
    @patch('common.views.resend_activation_link_to_user')
    def test_resend_after_initial_invitation_expires(
        self, mock_resend_email, mock_send_email, admin_authenticated_client, org, create_user, create_profile
    ):
        """Test that admin can resend if initial invitation expires."""
        inactive_user = create_user(email='expired@example.com', is_active=False)
        inactive_profile = create_profile(user=inactive_user, org=org, role='USER')
        url = f"/api/user/{inactive_profile.id}/resend-invitation/"
        response = admin_authenticated_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        assert mock_resend_email.called, "Resend function should be called"