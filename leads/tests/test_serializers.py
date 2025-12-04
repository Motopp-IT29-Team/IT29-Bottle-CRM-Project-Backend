"""
Unit tests for Lead serializers.
Tests validation logic, required fields, and duplicate checks.
"""
import pytest
from unittest.mock import Mock

from leads.models import Lead
from leads.serializer import LeadSerializer, LeadCreateSerializer


@pytest.mark.django_db
class TestLeadCreateSerializer:
    """Tests for LeadCreateSerializer validation."""

    # ==============================
    # Valid Data Tests
    # ==============================

    def test_valid_lead_data_is_valid(self, org, profile, valid_lead_data):
        """Test serializer is valid with correct data."""
        request = Mock()
        request.profile = profile
        
        serializer = LeadCreateSerializer(
            data=valid_lead_data,
            request_obj=request,
        )
        
        assert serializer.is_valid(), serializer.errors

    def test_valid_optional_fields(self, org, profile):
        """Test serializer accepts all optional fields."""
        request = Mock()
        request.profile = profile
        
        data = {
            "title": "Optional Fields Lead",
            "first_name": "Optional",
            "last_name": "Test",
            "email": "optional@example.com",
            "phone": "+31612345000",
            "account_name": "Optional Account",
            "source": "call",
            "status": "new",
            # Optional fields
            "salutation": "Dr",
            "department": "Marketing",
            "preferred_language": "Dutch",
            "rating": "Hot",
            "budget_range": "over_25000",
            "decision_timeframe": "within_1_week",
            "do_not_call": True,
            "probability": 80,
        }
        
        serializer = LeadCreateSerializer(data=data, request_obj=request)
        assert serializer.is_valid(), serializer.errors

    # ==============================
    # Required Field Tests
    # ==============================

    def test_missing_first_name_fails(self, profile, valid_lead_data):
        """Test validation fails when first_name is missing."""
        request = Mock()
        request.profile = profile
        
        del valid_lead_data["first_name"]
        serializer = LeadCreateSerializer(data=valid_lead_data, request_obj=request)
        
        assert not serializer.is_valid()
        assert "first_name" in serializer.errors

    def test_missing_last_name_fails(self, profile, valid_lead_data):
        """Test validation fails when last_name is missing."""
        request = Mock()
        request.profile = profile
        
        del valid_lead_data["last_name"]
        serializer = LeadCreateSerializer(data=valid_lead_data, request_obj=request)
        
        assert not serializer.is_valid()
        assert "last_name" in serializer.errors

    def test_missing_email_fails(self, profile, valid_lead_data):
        """Test validation fails when email is missing."""
        request = Mock()
        request.profile = profile
        
        del valid_lead_data["email"]
        serializer = LeadCreateSerializer(data=valid_lead_data, request_obj=request)
        
        assert not serializer.is_valid()
        assert "email" in serializer.errors

    def test_missing_phone_fails(self, profile, valid_lead_data):
        """Test validation fails when phone is missing."""
        request = Mock()
        request.profile = profile
        
        del valid_lead_data["phone"]
        serializer = LeadCreateSerializer(data=valid_lead_data, request_obj=request)
        
        assert not serializer.is_valid()
        assert "phone" in serializer.errors

    def test_missing_title_fails(self, profile, valid_lead_data):
        """Test validation fails when title is missing."""
        request = Mock()
        request.profile = profile
        
        del valid_lead_data["title"]
        serializer = LeadCreateSerializer(data=valid_lead_data, request_obj=request)
        
        assert not serializer.is_valid()
        assert "title" in serializer.errors

    def test_missing_account_name_fails(self, profile, valid_lead_data):
        """Test validation fails when account_name is missing."""
        request = Mock()
        request.profile = profile
        
        del valid_lead_data["account_name"]
        serializer = LeadCreateSerializer(data=valid_lead_data, request_obj=request)
        
        assert not serializer.is_valid()
        assert "account_name" in serializer.errors

    def test_missing_source_fails(self, profile, valid_lead_data):
        """Test validation fails when source is missing."""
        request = Mock()
        request.profile = profile
        
        del valid_lead_data["source"]
        serializer = LeadCreateSerializer(data=valid_lead_data, request_obj=request)
        
        assert not serializer.is_valid()
        assert "source" in serializer.errors

    def test_missing_status_fails(self, profile, valid_lead_data):
        """Test validation fails when status is missing."""
        request = Mock()
        request.profile = profile
        
        del valid_lead_data["status"]
        serializer = LeadCreateSerializer(data=valid_lead_data, request_obj=request)
        
        assert not serializer.is_valid()
        assert "status" in serializer.errors

    # ==============================
    # Duplicate Validation Tests
    # ==============================

    def test_duplicate_email_in_same_org_fails(self, org, profile, lead, valid_lead_data):
        """Test validation fails for duplicate email in same organization."""
        request = Mock()
        request.profile = profile
        
        # Use the same email as existing lead
        valid_lead_data["email"] = lead.email
        valid_lead_data["title"] = "Different Title"
        valid_lead_data["phone"] = "+31600000001"
        valid_lead_data["account_name"] = "Different Account"
        
        serializer = LeadCreateSerializer(data=valid_lead_data, request_obj=request)
        
        assert not serializer.is_valid()
        assert "email" in serializer.errors
        assert "already exists" in str(serializer.errors["email"][0]).lower()

    def test_duplicate_phone_in_same_org_fails(self, org, profile, lead, valid_lead_data):
        """Test validation fails for duplicate phone in same organization."""
        request = Mock()
        request.profile = profile
        
        # Use the same phone as existing lead
        valid_lead_data["phone"] = str(lead.phone)
        valid_lead_data["title"] = "Different Title"
        valid_lead_data["email"] = "different@example.com"
        valid_lead_data["account_name"] = "Different Account"
        
        serializer = LeadCreateSerializer(data=valid_lead_data, request_obj=request)
        
        assert not serializer.is_valid()
        assert "phone" in serializer.errors
        assert "already exists" in str(serializer.errors["phone"][0]).lower()

    # ==============================
    # Choice Field Validation Tests
    # ==============================

    def test_invalid_budget_range_choice_fails(self, profile, valid_lead_data):
        """Test validation fails for invalid budget_range choice."""
        request = Mock()
        request.profile = profile
        
        valid_lead_data["budget_range"] = "invalid_choice"
        serializer = LeadCreateSerializer(data=valid_lead_data, request_obj=request)
        
        assert not serializer.is_valid()
        assert "budget_range" in serializer.errors

    def test_invalid_decision_timeframe_choice_fails(self, profile, valid_lead_data):
        """Test validation fails for invalid decision_timeframe choice."""
        request = Mock()
        request.profile = profile
        
        valid_lead_data["decision_timeframe"] = "invalid_choice"
        serializer = LeadCreateSerializer(data=valid_lead_data, request_obj=request)
        
        assert not serializer.is_valid()
        assert "decision_timeframe" in serializer.errors

    def test_probability_over_100_fails(self, profile, valid_lead_data):
        """Test validation fails when probability exceeds 100."""
        request = Mock()
        request.profile = profile
        
        valid_lead_data["probability"] = 150
        serializer = LeadCreateSerializer(data=valid_lead_data, request_obj=request)
        
        assert not serializer.is_valid()
        assert "probability" in serializer.errors


@pytest.mark.django_db
class TestLeadSerializer:
    """Tests for LeadSerializer (read serializer)."""

    def test_serializer_contains_expected_fields(self, lead):
        """Test that serializer outputs all expected fields."""
        serializer = LeadSerializer(lead)
        data = serializer.data
        
        expected_fields = [
            "id", "title", "first_name", "last_name", "phone", "email",
            "status", "source", "address_line", "city", "state", "postcode",
            "country", "website", "description", "account_name",
            "opportunity_amount", "is_active", "salutation", "department",
            "preferred_language", "rating", "budget_range", "decision_timeframe",
            "do_not_call",
        ]
        
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"

    def test_serializer_returns_correct_values(self, lead_with_all_fields):
        """Test that serializer returns correct field values."""
        serializer = LeadSerializer(lead_with_all_fields)
        data = serializer.data
        
        assert data["title"] == "Complete Lead"
        assert data["first_name"] == "Complete"
        assert data["last_name"] == "Lead"
        assert data["email"] == "complete.lead@example.com"
        assert data["status"] == "working"
        assert data["salutation"] == "Ms"
        assert data["department"] == "Marketing"
        assert data["preferred_language"] == "Dutch"
        assert data["rating"] == "Hot"
        assert data["budget_range"] == "10000_to_25000"
        assert data["decision_timeframe"] == "within_1_week"
        assert data["do_not_call"] is True
