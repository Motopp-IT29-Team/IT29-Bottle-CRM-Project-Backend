"""
Test coverage:
- Organization creation and listing (POST/GET /api/org/)
- Teams and users view (GET /api/users/get-teams-and-users/)
- Dashboard/Home view (GET /api/dashboard/)

Run with: pytest common/tests/test_organization_management.py -v
"""
import pytest
from rest_framework import status
from common.models import Org, Profile
from teams.models import Teams


@pytest.fixture
def create_team(db):
    """Factory fixture to create teams."""
    def _create_team(name, org, description="Test Team", users=None):
        team = Teams.objects.create(
            name=name,
            description=description,
            org=org
        )
        if users:
            team.users.add(*users)
        return team
    return _create_team


@pytest.mark.django_db
class TestOrganizationCreate:
    """Test organization creation."""
    url = "/api/org/"

    def test_authenticated_user_can_create_organization(self, api_client, user):
        """Test that authenticated user can create new organization."""
        from rest_framework_simplejwt.tokens import RefreshToken
        user.first_name = 'Test'
        user.last_name = 'User'
        user.save()
        refresh = RefreshToken.for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        org_data = {'name': 'NewTestOrganization'}
        response = api_client.post(self.url, org_data, format='json')
        assert response.status_code == status.HTTP_200_OK, \
            f"Expected 200 OK, got {response.status_code}. Response: {response.data}"
        assert response.data['error'] is False
        assert 'New Org is Created' in response.data['message']
        assert 'org' in response.data
        assert response.data['status'] == status.HTTP_201_CREATED
        org = Org.objects.filter(name='NewTestOrganization').first()
        assert org is not None
        assert org.is_active is True

    def test_create_organization_auto_creates_admin_profile(self, api_client, user):
        """Test that creating org automatically creates admin profile for user."""
        from rest_framework_simplejwt.tokens import RefreshToken
        user.first_name = 'Test'
        user.last_name = 'User'
        user.save()
        refresh = RefreshToken.for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        org_data = {
            'name': 'AutoProfileOrg',
            'first_name': 'Admin',
            'last_name': 'User'
        }
        response = api_client.post(self.url, org_data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == status.HTTP_201_CREATED
        org = Org.objects.get(name='AutoProfileOrg')
        profile = Profile.objects.filter(user=user, org=org).first()
        assert profile is not None
        assert profile.role == 'ADMIN'
        assert profile.is_organization_admin is True
        assert profile.first_name == 'Admin'
        assert profile.last_name == 'User'

    def test_create_organization_with_existing_profile_updates_role(self, api_client, user, create_profile):
        """Test that creating org with existing profile updates role to admin."""
        from rest_framework_simplejwt.tokens import RefreshToken
        user.first_name = 'Test'
        user.last_name = 'User'
        user.save()
        new_org = Org.objects.create(name='ExistingProfileOrg', is_active=True)
        existing_profile = create_profile(user=user, org=new_org, role='USER')
        refresh = RefreshToken.for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        org_data = {'name': 'ExistingProfileOrg'}
        response = api_client.post(self.url, org_data, format='json')
        assert response.status_code == status.HTTP_200_OK
        org_created = Org.objects.filter(name='ExistingProfileOrg').latest('created_at')
        profile_updated = Profile.objects.filter(user=user, org=org_created).first()
        if profile_updated:
            assert profile_updated.role == 'ADMIN'
            assert profile_updated.is_organization_admin is True

    def test_create_organization_with_special_characters_fails(self, api_client, user):
        """Test that creating org with special characters fails validation."""
        from rest_framework_simplejwt.tokens import RefreshToken
        user.first_name = 'Test'
        user.last_name = 'User'
        user.save()
        refresh = RefreshToken.for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        org_data = {'name': 'New Test Organization!@#'}
        response = api_client.post(self.url, org_data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['error'] is True
        assert response.data['status'] == status.HTTP_400_BAD_REQUEST
        assert 'special characters' in str(response.data['errors'])

    def test_create_organization_without_name_fails(self, api_client, user):
        """Test that creating org without name fails validation."""
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        org_data = {}
        response = api_client.post(self.url, org_data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['error'] is True
        assert response.data['status'] == status.HTTP_400_BAD_REQUEST

    def test_unauthenticated_user_cannot_create_organization(self, api_client):
        """Test that unauthenticated user cannot create org."""
        org_data = {'name': 'UnauthorizedOrg'}
        response = api_client.post(self.url, org_data, format='json')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_created_organization_has_unique_api_key(self, api_client, user):
        """Test that created organization has unique API key."""
        from rest_framework_simplejwt.tokens import RefreshToken
        user.first_name = 'Test'
        user.last_name = 'User'
        user.save()
        refresh = RefreshToken.for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        org_data = {'name': 'APIKeyOrg'}
        response = api_client.post(self.url, org_data, format='json')
        assert response.status_code == status.HTTP_200_OK
        org = Org.objects.get(name='APIKeyOrg')
        assert org.api_key is not None
        assert len(org.api_key) > 0


@pytest.mark.django_db
class TestOrganizationList:
    """Test organization listing."""
    url = "/api/org/"

    def test_authenticated_user_can_list_their_organizations(self, api_client, user, org, create_profile):
        """Test that user can list all organizations they belong to."""
        from rest_framework_simplejwt.tokens import RefreshToken
        profile1 = create_profile(user=user, org=org, role='ADMIN')
        org2 = Org.objects.create(name='Second Org', is_active=True)
        profile2 = create_profile(user=user, org=org2, role='USER')
        refresh = RefreshToken.for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        response = api_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['error'] is False
        assert 'profile_org_list' in response.data
        assert len(response.data['profile_org_list']) >= 2
        org_names = [item['org']['name'] for item in response.data['profile_org_list']]
        assert org.name in org_names
        assert 'Second Org' in org_names

    def test_list_organizations_includes_profile_role(self, api_client, user, org, create_profile):
        """Test that org list includes user's role in each org."""
        from rest_framework_simplejwt.tokens import RefreshToken
        admin_profile = create_profile(user=user, org=org, role='ADMIN')
        refresh = RefreshToken.for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        response = api_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        profiles = response.data['profile_org_list']
        matching_profile = next((p for p in profiles if p['org']['id'] == str(org.id)), None)
        assert matching_profile is not None
        assert matching_profile['role'] == 'ADMIN'

    def test_user_with_no_organizations_returns_empty_list(self, api_client, user):
        """Test that user with no org profiles returns empty list."""
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        response = api_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['profile_org_list'] == []

    def test_unauthenticated_user_cannot_list_organizations(self, api_client):
        """Test that unauthenticated user cannot list orgs."""
        response = api_client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestGetTeamsAndUsers:
    """Test teams and users view."""
    url = "/api/users/get-teams-and-users/"

    def test_authenticated_user_can_get_teams_and_users(self, authenticated_client, org, create_user, create_profile, create_team):
        """Test that authenticated user can get teams and profiles."""
        user1 = create_user(email='user1@example.com')
        profile1 = create_profile(user=user1, org=org, role='USER')
        team = create_team(name='Sales Team', org=org, users=[profile1])
        response = authenticated_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert 'teams' in response.data
        assert 'profiles' in response.data
        assert len(response.data['teams']) >= 1
        assert len(response.data['profiles']) >= 1

    def test_get_teams_only_from_current_org(self, authenticated_client, org, create_user, create_profile, create_team):
        """Test that only teams from current org are returned."""
        user1 = create_user(email='user1@example.com')
        profile1 = create_profile(user=user1, org=org, role='USER')
        team1 = create_team(name='Org1 Team', org=org, users=[profile1])
        org2 = Org.objects.create(name='Other Org', is_active=True)
        user2 = create_user(email='user2@example.com')
        profile2 = create_profile(user=user2, org=org2, role='USER')
        team2 = create_team(name='Org2 Team', org=org2, users=[profile2])
        response = authenticated_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        team_names = [t['name'] for t in response.data['teams']]
        assert 'Org1 Team' in team_names
        assert 'Org2 Team' not in team_names

    def test_get_profiles_only_active_from_current_org(self, authenticated_client, org, create_user, create_profile):
        """Test that only active profiles from current org are returned."""
        active_user = create_user(email='active@example.com', is_active=True)
        active_profile = create_profile(user=active_user, org=org, role='USER', is_active=True)
        inactive_user = create_user(email='inactive@example.com', is_active=False)
        inactive_profile = create_profile(user=inactive_user, org=org, role='USER', is_active=False)
        response = authenticated_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        profile_emails = [p['user_details']['email'] for p in response.data['profiles']]
        assert 'active@example.com' in profile_emails
        assert 'inactive@example.com' not in profile_emails

    def test_unauthenticated_user_cannot_get_teams_and_users(self, api_client):
        """Test that unauthenticated user cannot access endpoint."""
        response = api_client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_profiles_ordered_by_email(self, authenticated_client, org, create_user, create_profile):
        """Test that profiles are ordered by email."""
        user_z = create_user(email='z@example.com')
        profile_z = create_profile(user=user_z, org=org, role='USER')
        user_a = create_user(email='a@example.com')
        profile_a = create_profile(user=user_a, org=org, role='USER')
        response = authenticated_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        emails = [p['user_details']['email'] for p in response.data['profiles']]
        assert emails == sorted(emails)


@pytest.mark.django_db
class TestDashboardView:
    """Test dashboard/home view."""
    url = "/api/dashboard/"

    def test_authenticated_user_can_access_dashboard(self, admin_authenticated_client):
        """Test that authenticated user can access dashboard."""
        response = admin_authenticated_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert 'accounts_count' in response.data
        assert 'contacts_count' in response.data
        assert 'leads_count' in response.data
        assert 'opportunities_count' in response.data

    def test_dashboard_returns_counts(self, admin_authenticated_client):
        """Test that dashboard returns count fields."""
        response = admin_authenticated_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data['accounts_count'], int)
        assert isinstance(response.data['contacts_count'], int)
        assert isinstance(response.data['leads_count'], int)
        assert isinstance(response.data['opportunities_count'], int)

    def test_dashboard_returns_lists(self, admin_authenticated_client):
        """Test that dashboard returns entity lists."""
        response = admin_authenticated_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert 'accounts' in response.data
        assert 'contacts' in response.data
        assert 'leads' in response.data
        assert 'opportunities' in response.data
        assert isinstance(response.data['accounts'], list)
        assert isinstance(response.data['contacts'], list)
        assert isinstance(response.data['leads'], list)
        assert isinstance(response.data['opportunities'], list)

    def test_unauthenticated_user_cannot_access_dashboard(self, api_client):
        """Test that unauthenticated user cannot access dashboard."""
        response = api_client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_dashboard_data_filtered_by_org(self, admin_authenticated_client, org):
        """Test that dashboard only shows data from current org."""
        response = admin_authenticated_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK