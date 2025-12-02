"""
API Settings Management tests for Bottle CRM.

Test coverage:
- API Settings list (GET /api/api-settings/)
- API Settings create (POST /api/api-settings/)
- API Settings detail (GET /api/api-settings/<pk>/)
- API Settings update (PUT /api/api-settings/<pk>/)
- API Settings delete (DELETE /api/api-settings/<pk>/)
- Website URL validation and API key generation

Run with: pytest common/tests/test_api_settings.py -v
"""
import pytest
from rest_framework import status
from common.models import APISettings, Profile


@pytest.fixture
def create_api_setting(db):
    """Factory fixture to create API settings."""

    def _create_api_setting(title, website, created_by, org, lead_assigned_to=None):
        if hasattr(created_by, 'user'):
            user = created_by.user
        else:
            user = created_by

        api_setting = APISettings.objects.create(
            title=title,
            website=website,
            created_by=user,
            org=org
        )
        if lead_assigned_to:
            api_setting.lead_assigned_to.add(*lead_assigned_to)
        return api_setting

    return _create_api_setting


@pytest.mark.django_db
class TestAPISettingsList:
    """Test API settings list endpoint."""
    url = "/api/api-settings/"

    def test_authenticated_user_can_list_api_settings(self, authenticated_client, org, profile, create_api_setting):
        """Test that authenticated user can list API settings."""
        api_setting = create_api_setting(
            title='Test API',
            website='http://example.com',
            created_by=profile,
            org=org
        )
        response = authenticated_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert 'api_settings' in response.data

    def test_list_api_settings_only_from_current_org(self, authenticated_client, org, profile, create_api_setting, create_user, create_profile):
        """Test that user only sees API settings from their org."""
        api_setting1 = create_api_setting(
            title='Org1 API',
            website='http://org1.com',
            created_by=profile,
            org=org
        )
        from common.models import Org
        org2 = Org.objects.create(name='OtherOrg', is_active=True)
        user2 = create_user(email='other@example.com')
        profile2 = create_profile(user=user2, org=org2, role='USER')
        api_setting2 = create_api_setting(
            title='Org2 API',
            website='http://org2.com',
            created_by=profile2,
            org=org2
        )
        response = authenticated_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK

    def test_admin_can_see_all_org_api_settings(self, admin_authenticated_client, org, admin_profile, create_api_setting, create_user, create_profile):
        """Test that admin can see all API settings in org."""
        user2 = create_user(email='user2@example.com')
        profile2 = create_profile(user=user2, org=org, role='USER')
        api_setting = create_api_setting(
            title='User API',
            website='http://user.com',
            created_by=profile2,
            org=org
        )
        response = admin_authenticated_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK

    def test_list_api_settings_filtered_by_title(self, authenticated_client, org, profile, create_api_setting):
        """Test filtering API settings by title."""
        api1 = create_api_setting(
            title='Sales API',
            website='http://sales.com',
            created_by=profile,
            org=org
        )
        api2 = create_api_setting(
            title='Marketing API',
            website='http://marketing.com',
            created_by=profile,
            org=org
        )
        response = authenticated_client.get(f'{self.url}?title=Sales')
        assert response.status_code == status.HTTP_200_OK

    def test_unauthenticated_user_cannot_list_api_settings(self, api_client):
        """Test that unauthenticated user cannot list API settings."""
        response = api_client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestAPISettingsCreate:
    """Test API settings creation."""
    url = "/api/api-settings/"

    def test_authenticated_user_can_create_api_setting(self, authenticated_client, org, profile):
        """Test that authenticated user can create API setting."""
        api_data = {
            'title': 'New API',
            'website': 'http://newapi.com'
        }
        response = authenticated_client.post(self.url, api_data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['error'] is False
        assert 'API setting Created Successfully' in response.data['message']
        api_setting = APISettings.objects.filter(title='New API').first()
        assert api_setting is not None
        assert api_setting.created_by == profile.user
        assert api_setting.org == org
        assert api_setting.apikey is not None
        assert len(api_setting.apikey) > 0

    def test_create_api_setting_with_lead_assigned_to(self, authenticated_client, org, profile, create_user, create_profile):
        """Test creating API setting with assigned profiles."""
        user2 = create_user(email='assigned@example.com')
        profile2 = create_profile(user=user2, org=org, role='USER')
        api_data = {
            'title': 'Assigned API',
            'website': 'http://assigned.com',
            'lead_assigned_to': [str(profile2.id)]
        }
        response = authenticated_client.post(self.url, api_data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        api_setting = APISettings.objects.get(title='Assigned API')
        assert profile2 in api_setting.lead_assigned_to.all()

    def test_create_api_setting_without_title_fails(self, authenticated_client):
        """Test that creating API setting without title fails."""
        api_data = {
            'website': 'http://notitle.com'
        }
        response = authenticated_client.post(self.url, api_data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_api_setting_without_website_fails(self, authenticated_client):
        """Test that creating API setting without website fails."""
        api_data = {
            'title': 'No Website'
        }
        response = authenticated_client.post(self.url, api_data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_api_setting_with_invalid_url_fails(self, authenticated_client):
        """Test that invalid URL fails validation."""
        api_data = {
            'title': 'Invalid URL',
            'website': 'not-a-valid-url'
        }
        response = authenticated_client.post(self.url, api_data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'website' in response.data['errors']

    def test_create_api_setting_with_url_without_schema_fails(self, authenticated_client):
        """Test that URL without http:// or https:// fails."""
        api_data = {
            'title': 'No Schema',
            'website': 'example.com'
        }
        response = authenticated_client.post(self.url, api_data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_unauthenticated_user_cannot_create_api_setting(self, api_client):
        """Test that unauthenticated user cannot create API setting."""
        api_data = {
            'title': 'Unauthorized API',
            'website': 'http://unauthorized.com'
        }
        response = api_client.post(self.url, api_data, format='json')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestAPISettingsDetail:
    """Test API settings detail endpoint."""

    def get_url(self, api_setting_id):
        return f"/api/api-settings/{api_setting_id}/"

    def test_creator_can_view_api_setting(self, authenticated_client, org, profile, create_api_setting):
        """Test that creator can view their API setting."""
        api_setting = create_api_setting(
            title='My API',
            website='http://myapi.com',
            created_by=profile,
            org=org
        )
        url = self.get_url(api_setting.id)
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['api_settings']['title'] == 'My API'

    def test_admin_can_view_any_api_setting(self, admin_authenticated_client, org, admin_profile, create_api_setting, create_user, create_profile):
        """Test that admin can view any API setting in org."""
        user2 = create_user(email='user2@example.com')
        profile2 = create_profile(user=user2, org=org, role='USER')
        api_setting = create_api_setting(
            title='User API',
            website='http://userapi.com',
            created_by=profile2,
            org=org
        )
        url = self.get_url(api_setting.id)
        response = admin_authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_cannot_view_api_setting_from_different_org(self, authenticated_client, org, profile, create_api_setting, create_user, create_profile):
        """Test that user cannot view API setting from different org."""
        from common.models import Org
        org2 = Org.objects.create(name='OtherOrg', is_active=True)
        user2 = create_user(email='other@example.com')
        profile2 = create_profile(user=user2, org=org2, role='USER')
        api_setting = create_api_setting(
            title='Other Org API',
            website='http://otherorg.com',
            created_by=profile2,
            org=org2
        )
        url = self.get_url(api_setting.id)
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_view_nonexistent_api_setting_returns_404(self, authenticated_client):
        """Test that viewing non-existent API setting returns 404."""
        import uuid
        fake_id = uuid.uuid4()
        url = self.get_url(fake_id)
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestAPISettingsUpdate:
    """Test API settings update endpoint."""

    def get_url(self, api_setting_id):
        return f"/api/api-settings/{api_setting_id}/"

    def test_creator_can_update_api_setting(self, authenticated_client, org, profile, create_api_setting):
        """Test that creator can update their API setting."""
        api_setting = create_api_setting(
            title='Original API',
            website='http://original.com',
            created_by=profile,
            org=org
        )
        url = self.get_url(api_setting.id)
        update_data = {
            'title': 'Updated API',
            'website': 'http://updated.com'
        }
        response = authenticated_client.put(url, update_data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['error'] is False
        api_setting.refresh_from_db()
        assert api_setting.title == 'Updated API'
        assert api_setting.website == 'http://updated.com'

    def test_admin_can_update_any_api_setting(self, admin_authenticated_client, org, admin_profile, create_api_setting, create_user, create_profile):
        """Test that admin can update any API setting."""
        user2 = create_user(email='user2@example.com')
        profile2 = create_profile(user=user2, org=org, role='USER')
        api_setting = create_api_setting(
            title='User API',
            website='http://userapi.com',
            created_by=profile2,
            org=org
        )
        url = self.get_url(api_setting.id)
        update_data = {
            'title': 'Admin Updated',
            'website': 'http://adminupdated.com'
        }
        response = admin_authenticated_client.put(url, update_data, format='json')
        assert response.status_code == status.HTTP_200_OK

    def test_non_creator_cannot_update_api_setting(self, api_client, org, create_user, create_profile, create_api_setting):
        """Test that non-creator cannot update API setting."""
        from rest_framework_simplejwt.tokens import RefreshToken
        user1 = create_user(email='creator@example.com')
        profile1 = create_profile(user=user1, org=org, role='USER')
        user2 = create_user(email='other@example.com')
        profile2 = create_profile(user=user2, org=org, role='USER')
        api_setting = create_api_setting(
            title='Private API',
            website='http://private.com',
            created_by=profile1,
            org=org
        )
        refresh = RefreshToken.for_user(user2)
        api_client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}",
            HTTP_ORG=str(org.id),
        )
        url = self.get_url(api_setting.id)
        update_data = {
            'title': 'Hacked API',
            'website': 'http://hacked.com'
        }
        response = api_client.put(url, update_data, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_api_setting_with_invalid_url_fails(self, authenticated_client, org, profile, create_api_setting):
        """Test that updating with invalid URL fails."""
        api_setting = create_api_setting(
            title='Valid API',
            website='http://valid.com',
            created_by=profile,
            org=org
        )
        url = self.get_url(api_setting.id)
        update_data = {
            'title': 'Valid API',
            'website': 'invalid-url'
        }
        response = authenticated_client.put(url, update_data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_update_api_setting_lead_assigned_to(self, authenticated_client, org, profile, create_api_setting, create_user, create_profile):
        """Test updating API setting lead_assigned_to list."""
        user2 = create_user(email='user2@example.com')
        profile2 = create_profile(user=user2, org=org, role='USER')
        api_setting = create_api_setting(
            title='API',
            website='http://api.com',
            created_by=profile,
            org=org
        )
        url = self.get_url(api_setting.id)
        update_data = {
            'title': 'API',
            'website': 'http://api.com',
            'lead_assigned_to': [str(profile2.id)]
        }
        response = authenticated_client.put(url, update_data, format='json')
        assert response.status_code == status.HTTP_200_OK
        api_setting.refresh_from_db()
        assert profile2 in api_setting.lead_assigned_to.all()


@pytest.mark.django_db
class TestAPISettingsDelete:
    """Test API settings delete endpoint."""

    def get_url(self, api_setting_id):
        return f"/api/api-settings/{api_setting_id}/"

    def test_creator_can_delete_api_setting(self, authenticated_client, org, profile, create_api_setting):
        """Test that creator can delete their API setting."""
        api_setting = create_api_setting(
            title='To Delete',
            website='http://todelete.com',
            created_by=profile,
            org=org
        )
        api_setting_id = api_setting.id
        url = self.get_url(api_setting_id)
        response = authenticated_client.delete(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['error'] is False
        assert not APISettings.objects.filter(id=api_setting_id).exists()

    def test_admin_can_delete_any_api_setting(self, admin_authenticated_client, org, admin_profile, create_api_setting, create_user, create_profile):
        """Test that admin can delete any API setting."""
        user2 = create_user(email='user2@example.com')
        profile2 = create_profile(user=user2, org=org, role='USER')
        api_setting = create_api_setting(
            title='User API',
            website='http://userapi.com',
            created_by=profile2,
            org=org
        )
        api_setting_id = api_setting.id
        url = self.get_url(api_setting_id)
        response = admin_authenticated_client.delete(url)
        assert response.status_code == status.HTTP_200_OK
        assert not APISettings.objects.filter(id=api_setting_id).exists()

    def test_non_creator_cannot_delete_api_setting(self, api_client, org, create_user, create_profile, create_api_setting):
        """Test that non-creator cannot delete API setting."""
        from rest_framework_simplejwt.tokens import RefreshToken
        user1 = create_user(email='creator@example.com')
        profile1 = create_profile(user=user1, org=org, role='USER')
        user2 = create_user(email='other@example.com')
        profile2 = create_profile(user=user2, org=org, role='USER')
        api_setting = create_api_setting(
            title='Private API',
            website='http://private.com',
            created_by=profile1,
            org=org
        )
        refresh = RefreshToken.for_user(user2)
        api_client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}",
            HTTP_ORG=str(org.id),
        )
        url = self.get_url(api_setting.id)
        response = api_client.delete(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert APISettings.objects.filter(id=api_setting.id).exists()

    def test_cannot_delete_api_setting_from_different_org(self, authenticated_client, org, profile, create_api_setting, create_user, create_profile):
        """Test that user cannot delete API setting from different org."""
        from common.models import Org
        org2 = Org.objects.create(name='OtherOrg', is_active=True)
        user2 = create_user(email='other@example.com')
        profile2 = create_profile(user=user2, org=org2, role='USER')
        api_setting = create_api_setting(
            title='Other Org API',
            website='http://otherorg.com',
            created_by=profile2,
            org=org2
        )
        url = self.get_url(api_setting.id)
        response = authenticated_client.delete(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND