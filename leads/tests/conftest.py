"""
Shared fixtures for lead tests.
These fixtures provide reusable test data for all lead-related tests.
"""
import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from common.models import Org, Profile, User
from leads.models import Company, Lead


# ==============================
# Base Fixtures
# ==============================

@pytest.fixture
def api_client():
    """Return a DRF APIClient instance."""
    return APIClient()


@pytest.fixture
def user(db):
    """Create and return a test user."""
    return User.objects.create_user(
        email="testuser@example.com",
        password="testpass123",
        first_name="Test",
        last_name="User",
    )


@pytest.fixture
def org(db):
    """Create and return a test organization."""
    return Org.objects.create(
        name="Test Organization",
        is_active=True,
    )


@pytest.fixture
def profile(db, user, org):
    """Create and return a test profile linked to user and org."""
    return Profile.objects.create(
        user=user,
        org=org,
        first_name="Test",
        last_name="User",
        role="ADMIN",
        is_organization_admin=True,
        is_active=True,
    )


@pytest.fixture
def authenticated_client(api_client, user, profile):
    """Return an APIClient with JWT authentication."""
    refresh = RefreshToken.for_user(user)
    api_client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}",
        HTTP_ORG=str(profile.org.id),
    )
    return api_client


# ==============================
# Lead Fixtures
# ==============================

@pytest.fixture
def company(db, org):
    """Create and return a test company."""
    return Company.objects.create(
        name="Test Company",
        org=org,
    )


@pytest.fixture
def valid_lead_data():
    """Return valid lead creation payload."""
    return {
        "title": "Test Lead Title",
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "phone": "+31612345678",
        "account_name": "Test Account",
        "source": "call",  # Valid choice from LEAD_SOURCE
        "status": "new",
        "website": "https://example.com",
        "description": "Test lead description",
        "address_line": "123 Test Street",
        "city": "Amsterdam",
        "state": "North Holland",
        "postcode": "1234AB",
        "country": "NL",
        "opportunity_amount": "10000.00",
        "probability": 50,
        "salutation": "Mr",  # Capitalized
        "department": "Sales",  # Capitalized
        "preferred_language": "English",  # Capitalized
        "rating": "Warm",  # Capitalized
        "budget_range": "5000_to_10000",
        "decision_timeframe": "within_1_month",
        "do_not_call": False,
    }


@pytest.fixture
def lead(db, org, profile, company):
    """Create and return a test lead."""
    lead = Lead.objects.create(
        title="Existing Lead",
        first_name="Jane",
        last_name="Smith",
        email="jane.smith@example.com",
        phone="+31687654321",
        account_name="Existing Account",
        source="partner",
        status="new",
        org=org,
        company=company,
        created_by=profile.user,
    )
    return lead


@pytest.fixture
def lead_with_all_fields(db, org, profile, company):
    """Create and return a lead with all optional fields populated."""
    lead = Lead.objects.create(
        title="Complete Lead",
        first_name="Complete",
        last_name="Lead",
        email="complete.lead@example.com",
        phone="+31699999999",
        account_name="Complete Account",
        source="call",
        status="working",
        org=org,
        company=company,
        created_by=profile.user,
        website="https://complete.example.com",
        description="A complete lead with all fields",
        address_line="456 Complete Street",
        city="Rotterdam",
        state="South Holland",
        postcode="5678CD",
        country="NL",
        opportunity_amount=25000.00,
        probability=75,
        salutation="Ms",
        department="Marketing",
        preferred_language="Dutch",
        rating="Hot",
        budget_range="10000_to_25000",
        decision_timeframe="within_1_week",
        do_not_call=True,
        is_active=True,
    )
    return lead


# ==============================
# Helper Fixtures
# ==============================

@pytest.fixture
def second_user(db):
    """Create a second test user for permission tests."""
    return User.objects.create_user(
        email="seconduser@example.com",
        password="testpass123",
        first_name="Second",
        last_name="User",
    )


@pytest.fixture
def second_org(db):
    """Create a second organization for isolation tests."""
    return Org.objects.create(
        name="Second Organization",
        is_active=True,
    )


@pytest.fixture
def second_profile(db, second_user, second_org):
    """Create a profile in a different organization."""
    return Profile.objects.create(
        user=second_user,
        org=second_org,
        first_name="Second",
        last_name="User",
        role="USER",
        is_organization_admin=False,
        is_active=True,
    )
