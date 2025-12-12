"""
Lead Conversion Service

Handles the business logic for converting a Lead into Account, Contact, and Opportunity.
All operations are performed within an atomic transaction to ensure data consistency.
"""

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from accounts.models import Account
from contacts.models import Contact
from common.models import Address
from opportunity.models import Opportunity
from leads.models import Lead


class LeadConversionError(Exception):
    """Custom exception for lead conversion errors"""
    pass


class LeadConversionService:
    """
    Service class for handling lead conversion operations.
    
    Converts a qualified lead into:
    - Account (create new or link to existing)
    - Contact (create new or link to existing)
    - Opportunity (optional, create new)
    """

    def __init__(self, lead: Lead, user, org):
        self.lead = lead
        self.user = user
        self.org = org

    def check_duplicates(self):
        """
        Check for potential duplicate accounts and contacts.
        
        Returns:
            dict: {
                'account_matches': [{'id', 'name', 'email', 'match_field', 'match_score'}],
                'contact_matches': [{'id', 'name', 'email', 'match_field', 'match_score'}]
            }
        """
        account_matches = []
        contact_matches = []

        # Check for matching accounts by company name or email
        if self.lead.account_name:
            accounts = Account.objects.filter(
                Q(name__iexact=self.lead.account_name) | Q(email__iexact=self.lead.email),
                org=self.org
            ).distinct()
            
            for account in accounts:
                match_field = 'name' if account.name and account.name.lower() == self.lead.account_name.lower() else 'email'
                account_matches.append({
                    'id': account.id,
                    'name': account.name,
                    'email': account.email,
                    'match_field': match_field,
                    'match_score': 1.0
                })

        # Check for matching contacts by email or phone
        contacts = Contact.objects.filter(
            Q(primary_email__iexact=self.lead.email) | Q(mobile_number=self.lead.phone),
            org=self.org
        ).distinct()
        
        for contact in contacts:
            match_field = 'email' if contact.primary_email and contact.primary_email.lower() == self.lead.email.lower() else 'phone'
            contact_matches.append({
                'id': contact.id,
                'name': f"{contact.first_name} {contact.last_name}",
                'email': contact.primary_email,
                'match_field': match_field,
                'match_score': 1.0
            })

        return {
            'account_matches': account_matches,
            'contact_matches': contact_matches
        }

    def validate_lead_for_conversion(self):
        """
        Validate that the lead can be converted.
        
        Raises:
            LeadConversionError: If the lead cannot be converted
        """
        if self.lead.is_converted:
            raise LeadConversionError("This lead has already been converted.")
        
        if self.lead.status == 'converted':
            raise LeadConversionError("This lead has already been converted.")
        
        # Optional: Require qualified status for conversion
        # if self.lead.status != 'qualified':
        #     raise LeadConversionError("Only qualified leads can be converted.")

    @transaction.atomic
    def convert(self, account_options=None, contact_options=None, opportunity_options=None):
        """
        Convert the lead to Account, Contact, and Opportunity.
        
        Args:
            account_options: dict with 'action' ('create'/'link') and optionally 'existing_id', 'name'
            contact_options: dict with 'action' ('create'/'link') and optionally 'existing_id'
            opportunity_options: dict with 'create', 'name', 'stage', 'amount', 'close_date'
            
        Returns:
            dict: {
                'lead': Lead,
                'account': Account,
                'contact': Contact,
                'opportunity': Opportunity or None
            }
            
        Raises:
            LeadConversionError: If conversion fails
        """
        # Set defaults
        account_options = account_options or {'action': 'create'}
        contact_options = contact_options or {'action': 'create'}
        opportunity_options = opportunity_options or {'create': True}

        # Validate lead
        self.validate_lead_for_conversion()

        # Step 1: Handle Account
        account = self._handle_account(account_options)

        # Step 2: Handle Contact
        contact = self._handle_contact(contact_options)

        # Step 3: Handle Opportunity
        opportunity = None
        if opportunity_options.get('create', True):
            opportunity = self._create_opportunity(account, contact, opportunity_options)

        # Step 4: Mark lead as converted
        self._mark_lead_converted(account, contact, opportunity)

        return {
            'lead': self.lead,
            'account': account,
            'contact': contact,
            'opportunity': opportunity
        }

    def _handle_account(self, options):
        """Create new or link to existing account"""
        action = options.get('action', 'create')
        
        if action == 'link':
            existing_id = options.get('existing_id')
            try:
                account = Account.objects.get(id=existing_id, org=self.org)
                return account
            except Account.DoesNotExist:
                raise LeadConversionError(f"Account with id {existing_id} not found.")
        
        # Create new account
        account_name = options.get('name') or self.lead.account_name or self.lead.title
        
        account = Account.objects.create(
            name=account_name,
            email=self.lead.email,
            phone=self.lead.phone,
            industry=self.lead.industry,
            billing_address_line=self.lead.address_line,
            billing_street=self.lead.street,
            billing_city=self.lead.city,
            billing_state=self.lead.state,
            billing_postcode=self.lead.postcode,
            billing_country=self.lead.country,
            website=self.lead.website,
            description=self.lead.description,
            contact_name=f"{self.lead.first_name} {self.lead.last_name}",
            lead=self.lead,
            org=self.org,
            created_by=self.user,
            is_active=True,
            status='open'
        )

        if self.lead.assigned_to:
            account.assigned_to.add(self.lead.assigned_to)
        account.teams.set(self.lead.teams.all())
        account.tags.set(self.lead.tags.all())

        return account

    def _handle_contact(self, options):
        """Create new or link to existing contact"""
        action = options.get('action', 'create')

        if action == 'link':
            existing_id = options.get('existing_id')
            try:
                contact = Contact.objects.get(id=existing_id, org=self.org)
                return contact
            except Contact.DoesNotExist:
                raise LeadConversionError(f"Contact with id {existing_id} not found.")

        # Create address for contact if needed
        address = None
        if self.lead.address_line or self.lead.city or self.lead.state:
            address = Address.objects.create(
                address_line=self.lead.address_line or '',
                street=self.lead.street or '',
                city=self.lead.city or '',
                state=self.lead.state or '',
                postcode=self.lead.postcode or '',
                country=self.lead.country or ''
            )

        # Create new contact
        contact = Contact.objects.create(
            salutation=self.lead.salutation or '',
            first_name=self.lead.first_name,
            last_name=self.lead.last_name,
            primary_email=self.lead.email,
            mobile_number=self.lead.phone,
            organization=self.lead.organization or self.lead.account_name,
            department=self.lead.department,
            language=self.lead.preferred_language,
            do_not_call=self.lead.do_not_call,
            description=self.lead.description,
            address=address,
            org=self.org,
            created_by=self.user,
            is_active=True,
            country=self.lead.country
        )

        if self.lead.assigned_to:
            contact.assigned_to.add(self.lead.assigned_to)
        contact.teams.set(self.lead.teams.all())

        return contact

    def _create_opportunity(self, account, contact, options):
        """Create a new opportunity linked to account and contact"""
        opp_name = options.get('name') or f"{account.name} - Opportunity"
        stage = options.get('stage') or 'QUALIFICATION'
        amount = options.get('amount') or self.lead.opportunity_amount
        close_date = options.get('close_date') or self.lead.close_date

        opportunity = Opportunity.objects.create(
            name=opp_name,
            account=account,
            stage=stage,
            amount=amount,
            lead_source=self.lead.source,
            probability=self.lead.probability or 0,
            budget_range=self.lead.budget_range or '',
            decision_timeframe=self.lead.decision_timeframe or '',
            closed_on=close_date,
            description=self.lead.description,
            org=self.org,
            created_by=self.user,
            is_active=True
        )

        # Add contact to opportunity
        opportunity.contacts.add(contact)

        if self.lead.assigned_to:
            opportunity.assigned_to.add(self.lead.assigned_to)
        opportunity.teams.set(self.lead.teams.all())
        opportunity.tags.set(self.lead.tags.all())

        return opportunity

    def _mark_lead_converted(self, account, contact, opportunity):
        """Mark the lead as converted with references to created entities"""
        self.lead.is_converted = True
        self.lead.status = 'converted'
        self.lead.converted_at = timezone.now()
        self.lead.converted_by = self.user.profile if hasattr(self.user, 'profile') else None
        self.lead.converted_account = account
        self.lead.converted_contact = contact
        self.lead.converted_opportunity = opportunity
        self.lead.save()