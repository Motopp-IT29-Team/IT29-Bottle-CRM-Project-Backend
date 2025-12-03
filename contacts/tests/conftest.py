"""
Contacts module-specific test fixtures.
"""
import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from common.models import User, Profile, Address
from contacts.models import Contact
from teams.models import Teams


@pytest.fixture
def create_user(db):
    """Factory fixture to create users."""
    def _create_user(**kwargs):
        defaults = {
            'email': 'testuser@test.com',
            'is_active': True,
        }
        defaults.update(kwargs)
        return User.objects.create(**defaults)
    return _create_user


@pytest.fixture
def create_profile(db):
    """Factory fixture to create profiles."""
    def _create_profile(user, org, **kwargs):
        defaults = {
            'role': 'USER',
            'is_active': True,
        }
        defaults.update(kwargs)
        return Profile.objects.create(user=user, org=org, **defaults)
    return _create_profile


@pytest.fixture
def user(db):
    """Create a basic test user."""
    return User.objects.create(
        email='testuser@example.com',
        is_active=True,
    )


@pytest.fixture
def admin_user(db):
    """Create an admin test user."""
    return User.objects.create(
        email='admin@example.com',
        is_active=True,
        is_staff=True,
    )


@pytest.fixture
def admin_profile(db, admin_user, org):
    """Create an admin profile."""
    return Profile.objects.create(
        user=admin_user,
        org=org,
        role='ADMIN',
        is_organization_admin=True,
        is_active=True,
    )


@pytest.fixture
def authenticated_client(db, user, org, create_profile):
    """Return authenticated API client with regular user permissions."""
    profile = Profile.objects.create(
        user=user,
        org=org,
        role='USER',
        is_active=True
    )
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    client.defaults['HTTP_ORG'] = str(org.id)
    client.profile = profile
    return client


@pytest.fixture
def admin_authenticated_client(db, admin_user, org, admin_profile):
    """Return authenticated API client with admin permissions."""
    client = APIClient()
    refresh = RefreshToken.for_user(admin_user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    client.defaults['HTTP_ORG'] = str(org.id)
    client.profile = admin_profile
    return client


@pytest.fixture
def create_address(db):
    """Factory fixture to create addresses."""
    def _create_address(**kwargs):
        defaults = {
            'address_line': 'Test Address',
            'street': 'Test Street',
            'city': 'Test City',
            'state': 'Test State',
            'postcode': '12345',
            'country': 'US',
        }
        defaults.update(kwargs)
        return Address.objects.create(**defaults)
    return _create_address


@pytest.fixture
def create_contact(db):
    """Factory fixture to create contacts."""
    def _create_contact(org, created_by_user=None, address=None, **kwargs):
        if address is None:
            address = Address.objects.create(
                address_line='Test Address',
                city='Test City',
                country='US'
            )

        suffix = kwargs.pop('suffix', '')
        defaults = {
            'first_name': 'John',
            'last_name': 'Doe',
            'organization': 'Test Org',
            'title': 'CEO',
            'primary_email': f'john.doe{suffix}@test.com',
            'mobile_number': f'+31612345{suffix:0>3}',
            'department': 'Sales',
            'language': 'English',
            'org': org,
            'address': address,
        }
        defaults.update(kwargs)

        contact = Contact.objects.create(**defaults)
        if created_by_user:
            contact.created_by = created_by_user
            contact.save()
        return contact
    return _create_contact


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