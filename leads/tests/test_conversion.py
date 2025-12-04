"""
Unit tests for Lead Conversion functionality.

Tests cover:
- Lead conversion to Account, Contact, and Opportunity
- Duplicate detection
- Linking to existing records
- Error handling and validation
- Transaction atomicity
"""
import pytest
from django.urls import reverse
from rest_framework import status

from accounts.models import Account
from contacts.models import Contact
from opportunity.models import Opportunity
from leads.models import Lead
from leads.services import LeadConversionService, LeadConversionError


# ==============================
# Conversion Service Tests
# ==============================

class TestLeadConversionService:
    """Test the LeadConversionService business logic."""

    @pytest.fixture
    def qualified_lead(self, db, org, profile, company):
        """Create a qualified lead ready for conversion."""
        return Lead.objects.create(
            title="Qualified Lead",
            first_name="John",
            last_name="Qualified",
            email="john.qualified@example.com",
            phone="+31612345678",
            account_name="Qualified Account Inc",
            source="call",
            status="qualified",
            org=org,
            company=company,
            created_by=profile.user,
            website="https://qualified.example.com",
            description="A qualified lead ready for conversion",
            address_line="123 Qualified Street",
            city="Amsterdam",
            state="North Holland",
            postcode="1234AB",
            country="NL",
            opportunity_amount=50000.00,
            probability=80,
            industry="SOFTWARE",
            salutation="Mr",
            department="Sales",
            preferred_language="English",
        )

    def test_convert_lead_creates_all_entities(self, qualified_lead, profile):
        """Test that conversion creates Account, Contact, and Opportunity."""
        service = LeadConversionService(
            lead=qualified_lead,
            user=profile.user,
            org=profile.org
        )
        
        result = service.convert()
        
        assert result['account'] is not None
        assert result['contact'] is not None
        assert result['opportunity'] is not None
        assert result['lead'].is_converted is True
        assert result['lead'].status == 'converted'

    def test_convert_lead_account_has_correct_data(self, qualified_lead, profile):
        """Test that the created account has data from the lead."""
        service = LeadConversionService(
            lead=qualified_lead,
            user=profile.user,
            org=profile.org
        )
        
        result = service.convert()
        account = result['account']
        
        assert account.name == qualified_lead.account_name
        assert account.email == qualified_lead.email
        assert account.phone == qualified_lead.phone
        assert account.industry == qualified_lead.industry
        assert account.billing_city == qualified_lead.city
        assert account.website == qualified_lead.website
        assert account.org == qualified_lead.org

    def test_convert_lead_contact_has_correct_data(self, qualified_lead, profile):
        """Test that the created contact has data from the lead."""
        service = LeadConversionService(
            lead=qualified_lead,
            user=profile.user,
            org=profile.org
        )
        
        result = service.convert()
        contact = result['contact']
        
        assert contact.first_name == qualified_lead.first_name
        assert contact.last_name == qualified_lead.last_name
        assert contact.primary_email == qualified_lead.email
        assert contact.mobile_number == qualified_lead.phone
        assert contact.salutation == qualified_lead.salutation
        assert contact.org == qualified_lead.org

    def test_convert_lead_opportunity_has_correct_data(self, qualified_lead, profile):
        """Test that the created opportunity has data from the lead."""
        service = LeadConversionService(
            lead=qualified_lead,
            user=profile.user,
            org=profile.org
        )
        
        result = service.convert()
        opportunity = result['opportunity']
        
        assert opportunity.amount == qualified_lead.opportunity_amount
        assert opportunity.lead_source == qualified_lead.source
        assert opportunity.probability == qualified_lead.probability
        assert opportunity.org == qualified_lead.org
        assert opportunity.account == result['account']

    def test_convert_lead_marks_as_converted(self, qualified_lead, profile):
        """Test that the lead is marked as converted."""
        service = LeadConversionService(
            lead=qualified_lead,
            user=profile.user,
            org=profile.org
        )
        
        result = service.convert()
        
        qualified_lead.refresh_from_db()
        assert qualified_lead.is_converted is True
        assert qualified_lead.status == 'converted'
        assert qualified_lead.converted_at is not None
        assert qualified_lead.converted_account == result['account']
        assert qualified_lead.converted_contact == result['contact']
        assert qualified_lead.converted_opportunity == result['opportunity']

    def test_convert_already_converted_lead_fails(self, qualified_lead, profile):
        """Test that converting an already converted lead raises error."""
        qualified_lead.is_converted = True
        qualified_lead.save()
        
        service = LeadConversionService(
            lead=qualified_lead,
            user=profile.user,
            org=profile.org
        )
        
        with pytest.raises(LeadConversionError) as exc_info:
            service.convert()
        
        assert "already been converted" in str(exc_info.value)

    def test_convert_with_link_to_existing_account(self, qualified_lead, profile, org):
        """Test linking to an existing account during conversion."""
        existing_account = Account.objects.create(
            name="Existing Account",
            email="existing@example.com",
            contact_name="Existing Contact",
            org=org,
            created_by=profile.user,
        )
        
        service = LeadConversionService(
            lead=qualified_lead,
            user=profile.user,
            org=profile.org
        )
        
        result = service.convert(
            account_options={'action': 'link', 'existing_id': existing_account.id}
        )
        
        assert result['account'] == existing_account

    def test_convert_with_link_to_existing_contact(self, qualified_lead, profile, org):
        """Test linking to an existing contact during conversion."""
        existing_contact = Contact.objects.create(
            first_name="Existing",
            last_name="Contact",
            primary_email="existing.contact@example.com",
            mobile_number="+31699887766",
            org=org,
            created_by=profile.user,
        )
        
        service = LeadConversionService(
            lead=qualified_lead,
            user=profile.user,
            org=profile.org
        )
        
        result = service.convert(
            contact_options={'action': 'link', 'existing_id': existing_contact.id}
        )
        
        assert result['contact'] == existing_contact

    def test_convert_without_opportunity(self, qualified_lead, profile):
        """Test conversion without creating an opportunity."""
        service = LeadConversionService(
            lead=qualified_lead,
            user=profile.user,
            org=profile.org
        )
        
        result = service.convert(
            opportunity_options={'create': False}
        )
        
        assert result['account'] is not None
        assert result['contact'] is not None
        assert result['opportunity'] is None


class TestDuplicateCheck:
    """Test duplicate detection functionality."""

    @pytest.fixture
    def lead_for_duplicate_check(self, db, org, profile, company):
        """Create a lead for duplicate checking."""
        return Lead.objects.create(
            title="Duplicate Check Lead",
            first_name="Duplicate",
            last_name="Check",
            email="duplicate@example.com",
            phone="+31611111111",
            account_name="Duplicate Account",
            source="call",
            status="qualified",
            org=org,
            company=company,
            created_by=profile.user,
        )

    def test_check_duplicates_finds_matching_account_by_name(self, lead_for_duplicate_check, profile, org):
        """Test that duplicate check finds account with matching name."""
        Account.objects.create(
            name="Duplicate Account",
            email="other@example.com",
            contact_name="Some Contact",
            org=org,
            created_by=profile.user,
        )
        
        service = LeadConversionService(
            lead=lead_for_duplicate_check,
            user=profile.user,
            org=profile.org
        )
        
        duplicates = service.check_duplicates()
        
        assert len(duplicates['account_matches']) == 1
        assert duplicates['account_matches'][0]['match_field'] == 'name'

    def test_check_duplicates_finds_matching_account_by_email(self, lead_for_duplicate_check, profile, org):
        """Test that duplicate check finds account with matching email."""
        Account.objects.create(
            name="Different Name",
            email="duplicate@example.com",
            contact_name="Some Contact",
            org=org,
            created_by=profile.user,
        )
        
        service = LeadConversionService(
            lead=lead_for_duplicate_check,
            user=profile.user,
            org=profile.org
        )
        
        duplicates = service.check_duplicates()
        
        assert len(duplicates['account_matches']) == 1
        assert duplicates['account_matches'][0]['match_field'] == 'email'

    def test_check_duplicates_finds_matching_contact_by_email(self, lead_for_duplicate_check, profile, org):
        """Test that duplicate check finds contact with matching email."""
        Contact.objects.create(
            first_name="Other",
            last_name="Person",
            primary_email="duplicate@example.com",
            mobile_number="+31699999999",
            org=org,
            created_by=profile.user,
        )
        
        service = LeadConversionService(
            lead=lead_for_duplicate_check,
            user=profile.user,
            org=profile.org
        )
        
        duplicates = service.check_duplicates()
        
        assert len(duplicates['contact_matches']) == 1
        assert duplicates['contact_matches'][0]['match_field'] == 'email'

    def test_check_duplicates_returns_empty_when_no_matches(self, lead_for_duplicate_check, profile):
        """Test that duplicate check returns empty lists when no matches."""
        service = LeadConversionService(
            lead=lead_for_duplicate_check,
            user=profile.user,
            org=profile.org
        )
        
        duplicates = service.check_duplicates()
        
        assert len(duplicates['account_matches']) == 0
        assert len(duplicates['contact_matches']) == 0


# ==============================
# API View Tests
# ==============================

class TestLeadConvertView:
    """Test the Lead Convert API endpoint."""

    @pytest.fixture
    def qualified_lead(self, db, org, profile, company):
        """Create a qualified lead for API tests."""
        return Lead.objects.create(
            title="API Test Lead",
            first_name="API",
            last_name="Test",
            email="api.test@example.com",
            phone="+31622222222",
            account_name="API Test Account",
            source="email",
            status="qualified",
            org=org,
            company=company,
            created_by=profile.user,
            opportunity_amount=30000.00,
        )

    def test_convert_lead_success(self, authenticated_client, qualified_lead):
        """Test successful lead conversion via API."""
        url = f"/api/leads/{qualified_lead.id}/convert/"
        
        response = authenticated_client.post(url, {}, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['error'] is False
        assert 'successfully' in response.data['message'].lower()

    def test_convert_lead_with_custom_options(self, authenticated_client, qualified_lead):
        """Test lead conversion with custom options."""
        url = f"/api/leads/{qualified_lead.id}/convert/"
        data = {
            'account': {'action': 'create', 'name': 'Custom Account Name'},
            'opportunity': {
                'create': True,
                'name': 'Custom Opportunity',
                'stage': 'QUALIFICATION',
                'amount': '75000.00'
            }
        }
        
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK

    def test_convert_lead_not_found(self, authenticated_client):
        """Test conversion of non-existent lead."""
        url = "/api/leads/00000000-0000-0000-0000-000000000000/convert/"
        
        response = authenticated_client.post(url, {}, format='json')
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_convert_lead_unauthenticated(self, api_client, qualified_lead):
        """Test that unauthenticated request is rejected."""
        url = f"/api/leads/{qualified_lead.id}/convert/"
        
        response = api_client.post(url, {}, format='json')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_convert_already_converted_lead(self, authenticated_client, qualified_lead):
        """Test that converting already converted lead fails."""
        qualified_lead.is_converted = True
        qualified_lead.status = 'converted'
        qualified_lead.save()
        
        url = f"/api/leads/{qualified_lead.id}/convert/"
        
        response = authenticated_client.post(url, {}, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestLeadCheckDuplicatesView:
    """Test the Lead Check Duplicates API endpoint."""

    @pytest.fixture
    def lead_for_check(self, db, org, profile, company):
        """Create a lead for duplicate check API tests."""
        return Lead.objects.create(
            title="Check Lead",
            first_name="Check",
            last_name="Lead",
            email="check.lead@example.com",
            phone="+31633333333",
            account_name="Check Account",
            source="call",
            status="qualified",
            org=org,
            company=company,
            created_by=profile.user,
        )

    def test_check_duplicates_success(self, authenticated_client, lead_for_check):
        """Test successful duplicate check via API."""
        url = f"/api/leads/{lead_for_check.id}/check-duplicates/"
        
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['error'] is False
        assert 'account_matches' in response.data['data']
        assert 'contact_matches' in response.data['data']

    def test_check_duplicates_not_found(self, authenticated_client):
        """Test duplicate check for non-existent lead."""
        url = "/api/leads/00000000-0000-0000-0000-000000000000/check-duplicates/"
        
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_check_duplicates_unauthenticated(self, api_client, lead_for_check):
        """Test that unauthenticated request is rejected."""
        url = f"/api/leads/{lead_for_check.id}/check-duplicates/"
        
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
