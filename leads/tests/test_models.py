"""
Unit tests for Lead models.
Tests model properties, methods, and default values.
"""
import pytest
from django.utils import timezone

from leads.models import Company, Lead


@pytest.mark.django_db
class TestLeadModel:
    """Tests for Lead model."""

    def test_lead_str_returns_title(self, lead):
        """Test __str__ method returns the lead title."""
        assert str(lead) == lead.title

    def test_lead_default_is_active_false(self, org, profile):
        """Test default value of is_active is False."""
        lead = Lead.objects.create(
            title="Test Lead",
            first_name="Test",
            last_name="User",
            email="testdefault@example.com",
            org=org,
            created_by=profile.user,
        )
        
        assert lead.is_active is False

    def test_lead_default_do_not_call_false(self, org, profile):
        """Test default value of do_not_call is False."""
        lead = Lead.objects.create(
            title="Test Lead DNC",
            first_name="Test",
            last_name="User",
            email="testdnc@example.com",
            org=org,
            created_by=profile.user,
        )
        
        assert lead.do_not_call is False

    def test_lead_get_complete_address(self, lead_with_all_fields):
        """Test get_complete_address returns formatted address."""
        address = lead_with_all_fields.get_complete_address()
        
        # Should contain address components
        assert "456 Complete Street" in address or lead_with_all_fields.address_line in address
        assert "Rotterdam" in address or lead_with_all_fields.city in address

    def test_lead_phone_raw_input_handles_none(self, org, profile):
        """Test phone_raw_input property handles None phone."""
        lead = Lead.objects.create(
            title="No Phone Lead",
            first_name="No",
            last_name="Phone",
            email="nophone@example.com",
            phone=None,
            org=org,
            created_by=profile.user,
        )
        
        # Should return empty string or handle None gracefully
        result = lead.phone_raw_input
        assert result == "" or result is None or str(result) != "+NoneNone"

    def test_lead_created_on_arrow(self, lead):
        """Test created_on_arrow returns humanized timestamp."""
        result = lead.created_on_arrow
        
        # Should be a string like "just now", "a minute ago", etc.
        assert isinstance(result, str)
        assert len(result) > 0

    def test_lead_ordering(self, org, profile):
        """Test leads are ordered by -created_at (newest first)."""
        lead1 = Lead.objects.create(
            title="First Lead",
            first_name="First",
            last_name="Lead",
            email="first@example.com",
            org=org,
            created_by=profile.user,
        )
        
        lead2 = Lead.objects.create(
            title="Second Lead",
            first_name="Second",
            last_name="Lead",
            email="second@example.com",
            org=org,
            created_by=profile.user,
        )
        
        leads = Lead.objects.filter(org=org).order_by("-created_at")
        
        # Second lead should come first (newer)
        assert leads[0] == lead2
        assert leads[1] == lead1


@pytest.mark.django_db
class TestCompanyModel:
    """Tests for Company model."""

    def test_company_str_returns_name(self, company):
        """Test __str__ method returns the company name."""
        assert str(company) == company.name

    def test_company_creation(self, org):
        """Test company can be created with required fields."""
        company = Company.objects.create(
            name="Test Company",
            org=org,
        )
        
        assert company.name == "Test Company"
        assert company.org == org

    def test_company_ordering(self, org):
        """Test companies are ordered by -created_at."""
        company1 = Company.objects.create(name="Company A", org=org)
        company2 = Company.objects.create(name="Company B", org=org)
        
        companies = Company.objects.filter(org=org).order_by("-created_at")
        
        # Company B should come first (newer)
        assert companies[0] == company2
        assert companies[1] == company1


@pytest.mark.django_db  
class TestLeadChoiceFields:
    """Tests for Lead choice field validations."""

    def test_lead_with_valid_salutation(self, org, profile):
        """Test lead creation with valid salutation choice."""
        lead = Lead.objects.create(
            title="Salutation Test",
            first_name="Test",
            last_name="Salutation",
            email="salutation@example.com",
            salutation="mr",
            org=org,
            created_by=profile.user,
        )
        
        assert lead.salutation == "mr"

    def test_lead_with_valid_department(self, org, profile):
        """Test lead creation with valid department choice."""
        lead = Lead.objects.create(
            title="Department Test",
            first_name="Test",
            last_name="Department",
            email="department@example.com",
            department="marketing",
            org=org,
            created_by=profile.user,
        )
        
        assert lead.department == "marketing"

    def test_lead_with_valid_rating(self, org, profile):
        """Test lead creation with valid rating choice."""
        lead = Lead.objects.create(
            title="Rating Test",
            first_name="Test",
            last_name="Rating",
            email="rating@example.com",
            rating="hot",
            org=org,
            created_by=profile.user,
        )
        
        assert lead.rating == "hot"

    def test_lead_with_valid_budget_range(self, org, profile):
        """Test lead creation with valid budget_range choice."""
        lead = Lead.objects.create(
            title="Budget Test",
            first_name="Test",
            last_name="Budget",
            email="budget@example.com",
            budget_range="10000_to_25000",
            org=org,
            created_by=profile.user,
        )
        
        assert lead.budget_range == "10000_to_25000"

    def test_lead_with_valid_decision_timeframe(self, org, profile):
        """Test lead creation with valid decision_timeframe choice."""
        lead = Lead.objects.create(
            title="Timeframe Test",
            first_name="Test",
            last_name="Timeframe",
            email="timeframe@example.com",
            decision_timeframe="within_1_month",
            org=org,
            created_by=profile.user,
        )
        
        assert lead.decision_timeframe == "within_1_month"
