"""
Authentication-specific fixtures for common module tests.

These fixtures are available to all tests in common/tests/ directory.
Global fixtures (api_client, org) are in root conftest.py.
"""
import pytest
from rest_framework_simplejwt.tokens import RefreshToken
from common.models import User, Profile
from common.token_generator import account_activation_token
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
import datetime


# ==============================
# User Fixtures
# ==============================

@pytest.fixture
def user(db):
    """
    Create and return an active test user.

    Credentials:
        - Email: testuser@example.com
        - Password: TestPassword123!
    """
    user = User.objects.create(
        email="testuser@example.com",
        first_name="Test",
        last_name="User",
        is_active=True,
    )
    user.set_password("TestPassword123!")
    user.save()
    return user


@pytest.fixture
def inactive_user(db):
    """Create and return an inactive test user."""
    user = User.objects.create(
        email="inactive@example.com",
        first_name="Inactive",
        last_name="User",
        is_active=False,
    )
    user.set_password("TestPassword123!")
    user.save()
    return user


@pytest.fixture
def admin_user(db):
    """Create and return an admin user."""
    user = User.objects.create(
        email="admin@example.com",
        first_name="Admin",
        last_name="User",
        is_active=True,
    )
    user.set_password("AdminPassword123!")
    user.save()
    return user


# ==============================
# Profile Fixtures
# ==============================

@pytest.fixture
def profile(db, user, org):
    """Create and return a regular user profile."""
    return Profile.objects.create(
        user=user,
        org=org,
        first_name="Test",
        last_name="User",
        role="USER",
        is_active=True,
        date_of_joining=datetime.date.today(),
    )


@pytest.fixture
def admin_profile(db, admin_user, org):
    """Create and return an admin profile."""
    return Profile.objects.create(
        user=admin_user,
        org=org,
        first_name="Admin",
        last_name="User",
        role="ADMIN",
        is_organization_admin=True,
        is_active=True,
        date_of_joining=datetime.date.today(),
    )


# ==============================
# Authentication Fixtures
# ==============================

@pytest.fixture
def tokens(user):
    """
    Generate JWT tokens for user.

    Returns:
        dict: {'access': '...', 'refresh': '...'}
    """
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token)
    }


@pytest.fixture
def authenticated_client(api_client, user, profile):
    """
    Return an APIClient with JWT authentication and org header.
    Ready to make authenticated requests to common module endpoints.
    """
    refresh = RefreshToken.for_user(user)
    api_client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}",
        HTTP_ORG=str(profile.org.id),
    )
    return api_client


@pytest.fixture
def admin_authenticated_client(api_client, admin_user, admin_profile):
    """Return an APIClient authenticated as admin."""
    refresh = RefreshToken.for_user(admin_user)
    api_client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}",
        HTTP_ORG=str(admin_profile.org.id),
    )
    return api_client


# ==============================
# Activation Fixtures
# ==============================

@pytest.fixture
def inactive_user_with_activation(db):
    """
    Create an inactive user with activation key.

    Returns dict with user, token, activation_key, uid, and activation_url.
    """
    user = User.objects.create(
        email="activation@example.com",
        first_name="Activation",
        last_name="Test",
        is_active=False,
    )

    # Generate activation token and key
    token = account_activation_token.make_token(user)
    activation_time = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d-%H-%M-%S")
    activation_key = f"{activation_time}{token}"

    user.activation_key = activation_key
    user.save()

    # Generate UID
    uid = urlsafe_base64_encode(force_bytes(user.pk))

    return {
        'user': user,
        'token': token,
        'activation_key': activation_key,
        'uid': uid,
        'activation_url': f'/api/auth/activate-user/{uid}/{token}/{activation_key}/'
    }


# ==============================
# Factory Fixtures
# ==============================

@pytest.fixture
def create_user(db):
    """
    Factory fixture to create multiple users.

    Usage:
        user1 = create_user(email="user1@test.com")
        user2 = create_user(email="user2@test.com", is_active=False)
    """

    def _create_user(email, password="TestPassword123!", **kwargs):
        user = User.objects.create(
            email=email,
            is_active=kwargs.pop('is_active', True),
            first_name=kwargs.pop('first_name', 'Test'),
            last_name=kwargs.pop('last_name', 'User'),
            **kwargs
        )
        user.set_password(password)
        user.save()
        return user

    return _create_user


@pytest.fixture
def create_profile(db):
    """
    Factory fixture to create multiple profiles.

    Usage:
        profile = create_profile(user=user, org=org, role="ADMIN")
    """

    def _create_profile(user, org, role="USER", **kwargs):
        return Profile.objects.create(
            user=user,
            org=org,
            role=role,
            first_name=kwargs.pop('first_name', user.first_name or 'Test'),
            last_name=kwargs.pop('last_name', user.last_name or 'User'),
            is_active=kwargs.pop('is_active', True),
            date_of_joining=kwargs.pop('date_of_joining', datetime.date.today()),
            **kwargs
        )

    return _create_profile