"""
Test coverage:
- User list (GET /api/users/)
- User detail (GET /api/user/<pk>/)
- User update (PUT /api/user/<pk>/)
- User delete (DELETE /api/user/<pk>/)
- User status (POST /api/user/<pk>/status/)
- Permissions and access control

Run with: pytest common/tests/test_user_management.py -v
"""
from unittest.mock import patch
import pytest
from rest_framework import status
from common.models import User


@pytest.mark.django_db
class TestUserList:
    """Test user list endpoint."""
    url = "/api/users/"

    def test_admin_can_list_users(self, admin_authenticated_client, org, create_user, create_profile):
        """Test that admin can list all users in their org."""
        user1 = create_user(email='user1@example.com')
        profile1 = create_profile(user=user1, org=org, role='USER')
        user2 = create_user(email='user2@example.com')
        profile2 = create_profile(user=user2, org=org, role='USER')
        response = admin_authenticated_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert 'users' in response.data
        assert response.data['total_count'] >= 2

    def test_non_admin_cannot_list_users(self, authenticated_client):
        """Test that non-admin cannot list users."""
        response = authenticated_client.get(self.url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_list_users_filtered_by_email(self, admin_authenticated_client, org, create_user, create_profile):
        """Test filtering users by email."""
        user1 = create_user(email='alice@example.com')
        profile1 = create_profile(user=user1, org=org, role='USER')
        user2 = create_user(email='bob@example.com')
        profile2 = create_profile(user=user2, org=org, role='USER')
        response = admin_authenticated_client.get(f'{self.url}?email=alice')
        assert response.status_code == status.HTTP_200_OK
        user_emails = [u['user_details']['email'] for u in response.data['users']]
        assert 'alice@example.com' in user_emails
        assert 'bob@example.com' not in user_emails

    def test_list_users_filtered_by_role(self, admin_authenticated_client, org, create_user, create_profile):
        """Test filtering users by role."""
        user1 = create_user(email='admin1@example.com')
        profile1 = create_profile(user=user1, org=org, role='ADMIN')
        user2 = create_user(email='user1@example.com')
        profile2 = create_profile(user=user2, org=org, role='USER')
        response = admin_authenticated_client.get(f'{self.url}?role=ADMIN')
        assert response.status_code == status.HTTP_200_OK
        roles = [u['role'] for u in response.data['users']]
        assert 'ADMIN' in roles

    def test_list_users_filtered_by_status(self, admin_authenticated_client, org, create_user, create_profile):
        """Test filtering users by active/inactive status."""
        active_user = create_user(email='active@example.com', is_active=True)
        active_profile = create_profile(user=active_user, org=org, role='USER')
        inactive_user = create_user(email='inactive@example.com', is_active=False)
        inactive_profile = create_profile(user=inactive_user, org=org, role='USER')
        response = admin_authenticated_client.get(f'{self.url}?status=active')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'active'
        user_emails = [u['user_details']['email'] for u in response.data['users']]
        assert 'active@example.com' in user_emails
        assert 'inactive@example.com' not in user_emails

    def test_list_users_only_from_current_org(self, admin_authenticated_client, org, create_user, create_profile):
        """Test that user list only shows users from current org."""
        from common.models import Org
        user1 = create_user(email='org1user@example.com')
        profile1 = create_profile(user=user1, org=org, role='USER')
        org2 = Org.objects.create(name="Other Org", is_active=True)
        user2 = create_user(email='org2user@example.com')
        profile2 = create_profile(user=user2, org=org2, role='USER')
        response = admin_authenticated_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        user_emails = [u['user_details']['email'] for u in response.data['users']]
        assert 'org1user@example.com' in user_emails
        assert 'org2user@example.com' not in user_emails


@pytest.mark.django_db
class TestUserDetail:
    """Test user detail endpoint."""

    def get_url(self, profile_id):
        return f"/api/user/{profile_id}/"

    def test_admin_can_view_user_detail(self, admin_authenticated_client, org, create_user, create_profile):
        """Test that admin can view user details."""
        user = create_user(email='detail@example.com')
        profile = create_profile(user=user, org=org, role='USER')
        url = self.get_url(profile.id)
        response = admin_authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['error'] is False
        assert 'data' in response.data
        assert response.data['data']['profile_obj']['user_details']['email'] == 'detail@example.com'

    def test_user_cannot_view_other_user_detail(self, authenticated_client, org, create_user, create_profile):
        """Test that non-admin user cannot view other user details."""
        other_user = create_user(email='other@example.com')
        other_profile = create_profile(user=other_user, org=org, role='USER')
        url = self.get_url(other_profile.id)
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_cannot_view_user_from_different_org(self, admin_authenticated_client, org, create_user, create_profile):
        """Test that admin cannot view user from different org."""
        from common.models import Org
        other_org = Org.objects.create(name="Other Org", is_active=True)
        other_user = create_user(email='other@example.com')
        other_profile = create_profile(user=other_user, org=other_org, role='USER')
        url = self.get_url(other_profile.id)
        response = admin_authenticated_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_user_detail_includes_assigned_data(self, admin_authenticated_client, org, create_user, create_profile):
        """Test that user detail includes opportunities, contacts, cases."""
        user = create_user(email='assigned@example.com')
        profile = create_profile(user=user, org=org, role='USER')
        url = self.get_url(profile.id)
        response = admin_authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.data['data']
        assert 'opportunity_list' in data
        assert 'contacts' in data
        assert 'cases' in data
        assert 'assigned_data' in data


@pytest.mark.django_db
class TestUserUpdate:
    """Test user update endpoint."""

    def get_url(self, profile_id):
        return f"/api/user/{profile_id}/"

    def test_admin_can_update_user(self, admin_authenticated_client, org, create_user, create_profile):
        """Test that admin can update user details."""
        user = create_user(email='update@example.com')
        profile = create_profile(user=user, org=org, role='USER')
        url = self.get_url(profile.id)
        update_data = {
            'email': 'update@example.com',
            'first_name': 'Updated',
            'last_name': 'Name',
            'role': 'USER',
            'address_line': '456 New St',
            'city': 'New City',
            'state': 'NS',
            'postcode': '54321',
            'country': 'US',
        }
        response = admin_authenticated_client.put(url, update_data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['error'] is False
        assert 'User Updated Successfully' in response.data['message']
        user.refresh_from_db()
        profile.refresh_from_db()
        assert profile.first_name == 'Updated'
        assert profile.last_name == 'Name'

    def test_non_admin_cannot_update_other_user(self, authenticated_client, org, create_user, create_profile):
        """Test that non-admin cannot update other user."""
        other_user = create_user(email='other@example.com')
        other_profile = create_profile(user=other_user, org=org, role='USER')
        url = self.get_url(other_profile.id)
        update_data = {
            'email': 'other@example.com',
            'first_name': 'Hacked',
            'last_name': 'User',
            'role': 'ADMIN',
            'address_line': '123 Test St',
            'city': 'Test City',
            'state': 'TS',
            'postcode': '12345',
            'country': 'US',
        }
        response = authenticated_client.put(url, update_data, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_cannot_update_user_from_different_org(self, admin_authenticated_client, org, create_user, create_profile):
        """Test that admin cannot update user from different org."""
        from common.models import Org
        other_org = Org.objects.create(name="Other Org", is_active=True)
        other_user = create_user(email='other@example.com')
        other_profile = create_profile(user=other_user, org=other_org, role='USER')
        url = self.get_url(other_profile.id)
        update_data = {
            'email': 'other@example.com',
            'first_name': 'Updated',
            'last_name': 'Name',
            'role': 'USER',
            'address_line': '123 Test St',
            'city': 'Test City',
            'state': 'TS',
            'postcode': '12345',
            'country': 'US',
        }
        response = admin_authenticated_client.put(url, update_data, format='json')
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_user_with_invalid_data_fails(self, admin_authenticated_client, org, create_user, create_profile):
        """Test that updating user with invalid data returns validation errors."""
        user = create_user(email='invalid@example.com')
        profile = create_profile(user=user, org=org, role='USER')
        url = self.get_url(profile.id)
        update_data = {
            'email': 'not-an-email',
            'first_name': 'Test',
            'address_line': '123 Test St',
            'city': 'Test City',
            'state': 'TS',
            'postcode': '12345',
            'country': 'US',
        }
        response = admin_authenticated_client.put(url, update_data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['error'] is True


@pytest.mark.django_db
class TestUserDelete:
    """Test user delete endpoint."""

    def get_url(self, profile_id):
        return f"/api/user/{profile_id}/"

    @patch('common.views.send_email_user_delete.delay')
    def test_admin_can_delete_user(self, mock_send_email, admin_authenticated_client, org, create_user, create_profile):
        """Test that admin can delete user."""
        user = create_user(email='delete@example.com')
        profile = create_profile(user=user, org=org, role='USER')
        user_id = user.id
        url = self.get_url(profile.id)
        response = admin_authenticated_client.delete(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['error'] is False
        assert 'deleted successfully' in response.data['message']
        assert not User.objects.filter(id=user_id).exists()
        mock_send_email.assert_called_once()

    def test_non_admin_cannot_delete_user(self, authenticated_client, org, create_user, create_profile):
        """Test that non-admin cannot delete users."""
        other_user = create_user(email='other@example.com')
        other_profile = create_profile(user=other_user, org=org, role='USER')
        url = self.get_url(other_profile.id)
        response = authenticated_client.delete(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_cannot_delete_self(self, admin_authenticated_client, admin_profile):
        """Test that admin cannot delete their own account."""
        url = self.get_url(admin_profile.id)
        response = admin_authenticated_client.delete(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert 'Cannot delete your own account' in response.data['errors']


@pytest.mark.django_db
class TestUserStatus:
    """Test user status (activate/deactivate) endpoint."""

    def get_url(self, profile_id):
        return f"/api/user/{profile_id}/status/"

    def test_admin_can_deactivate_user(self, admin_authenticated_client, org, create_user, create_profile):
        """Test that admin can deactivate active user."""
        user = create_user(email='active@example.com', is_active=True)
        profile = create_profile(user=user, org=org, role='USER')
        url = self.get_url(profile.id)
        response = admin_authenticated_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['error'] is False
        assert 'deactivated' in response.data['message']
        user.refresh_from_db()
        profile.refresh_from_db()
        assert user.is_active is False
        assert profile.deactivated_by is not None
        assert profile.deactivated_at is not None

    def test_admin_can_activate_user(self, admin_authenticated_client, org, create_user, create_profile):
        """Test that admin can activate inactive user."""
        user = create_user(email='inactive@example.com', is_active=False)
        profile = create_profile(user=user, org=org, role='USER', is_active=True)
        url = self.get_url(profile.id)
        response = admin_authenticated_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['error'] is False
        assert 'activated' in response.data['message']
        user.refresh_from_db()
        profile.refresh_from_db()
        assert user.is_active is True
        assert profile.deactivated_by is None
        assert profile.deactivated_at is None

    def test_non_admin_cannot_change_user_status(self, authenticated_client, org, create_user, create_profile):
        """Test that non-admin cannot change user status."""
        user = create_user(email='test@example.com', is_active=True)
        profile = create_profile(user=user, org=org, role='USER')
        url = self.get_url(profile.id)
        response = authenticated_client.post(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_cannot_change_status_for_user_in_different_org(self, admin_authenticated_client, org, create_user, create_profile):
        """Test that admin cannot change status for user in different org."""
        from common.models import Org
        other_org = Org.objects.create(name="Other Org", is_active=True)
        other_user = create_user(email='other@example.com')
        other_profile = create_profile(user=other_user, org=other_org, role='USER')
        url = self.get_url(other_profile.id)
        response = admin_authenticated_client.post(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_status_change_with_nonexistent_profile_fails(self, admin_authenticated_client):
        """Test that changing status for non-existent profile returns 404."""
        import uuid
        fake_id = uuid.uuid4()
        url = self.get_url(fake_id)
        response = admin_authenticated_client.post(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND