from decimal import Decimal
from django.db.models import Sum, Q
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from leads.models import Lead
from opportunity.models import Opportunity
from contacts.models import Contact
from accounts.models import Account
from common.models import ActivityLog

from .serializers import (
    RecentLeadSerializer,
    RecentOpportunitySerializer,
    RecentContactSerializer,
    DashboardResponseSerializer,
)

# Constants for pipeline calculation
CLOSED_OPPORTUNITY_STAGES = ['CLOSED WON', 'CLOSED LOST']
EXCLUDED_LEAD_STATUSES = ['closed', 'converted']
QUALIFIED_LEAD_STATUS = 'qualified'


class DashboardView(APIView):
    """
    Dashboard API endpoint that provides:
    - Key statistics (counts for all CRM entities)
    - Pipeline value (sum of qualified leads + open opportunities)
    - Recent leads, opportunities, contacts
    - Recent activity logs
    """
    permission_classes = (IsAuthenticated,)

    def _get_filtered_querysets(self, org, profile, user, is_admin):
        """
        Get base querysets filtered by organization and user permissions.
        
        Returns:
            tuple: (leads_qs, opportunities_qs, contacts_qs, accounts_qs)
        """
        leads_qs = Lead.objects.filter(org=org)
        opportunities_qs = Opportunity.objects.filter(org=org)
        contacts_qs = Contact.objects.filter(org=org)
        accounts_qs = Account.objects.filter(org=org)

        if not is_admin:
            user_filter = Q(assigned_to=profile) | Q(created_by=user)
            leads_qs = leads_qs.filter(user_filter)
            opportunities_qs = opportunities_qs.filter(user_filter)
            contacts_qs = contacts_qs.filter(user_filter)
            accounts_qs = accounts_qs.filter(user_filter)

        return leads_qs, opportunities_qs, contacts_qs, accounts_qs

    def _calculate_pipeline_value(self, leads_qs, opportunities_qs):
        """
        Calculate total pipeline value from qualified leads and open opportunities.
        
        Pipeline value includes:
        - opportunity_amount from leads with status='qualified' (not yet converted)
        - amount from opportunities excluding CLOSED WON/LOST stages
        
        Note: When a qualified lead is converted, its status changes to 'converted',
        removing it from this calculation. The newly created opportunity's amount
        is then counted instead, preventing double-counting.
        
        Returns:
            Decimal: Total pipeline value
        """
        # Sum of open opportunities (excluding closed stages)
        opportunity_value = opportunities_qs.exclude(
            stage__in=CLOSED_OPPORTUNITY_STAGES
        ).aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')

        # Sum of qualified leads (not yet converted to opportunities)
        qualified_leads_value = leads_qs.filter(
            status=QUALIFIED_LEAD_STATUS
        ).aggregate(
            total=Sum('opportunity_amount')
        )['total'] or Decimal('0.00')

        return opportunity_value + qualified_leads_value

    def _get_activity_logs(self, org):
        """Get recent activity logs for the organization."""
        try:
            logs_qs = ActivityLog.objects.filter(org=org).order_by('-created_at')[:10]
            return [
                {
                    'id': str(log.id),
                    'action': log.action,
                    'model_name': log.entity_type,
                    'object_id': str(log.entity_id) if log.entity_id else None,
                    'object_repr': log.entity_name,
                    'user_email': log.user_email or (log.user.email if log.user else None),
                    'created_at': log.created_at.isoformat(),
                    'created_on_arrow': getattr(log, 'created_on_arrow', None),
                }
                for log in logs_qs
            ]
        except Exception:
            return []

    @extend_schema(
        description="Get dashboard statistics and recent items",
        responses={200: DashboardResponseSerializer},
        tags=["Dashboard"]
    )
    def get(self, request, *args, **kwargs):
        org = request.profile.org
        profile = request.profile
        is_admin = profile.role == "ADMIN" or profile.is_admin or request.user.is_superuser

        # Get filtered querysets
        leads_qs, opportunities_qs, contacts_qs, accounts_qs = self._get_filtered_querysets(
            org, profile, request.user, is_admin
        )

        # Calculate pipeline value
        pipeline_value = self._calculate_pipeline_value(leads_qs, opportunities_qs)

        # Build statistics
        stats = {
            'leads_count': leads_qs.count(),
            'opportunities_count': opportunities_qs.count(),
            'accounts_count': accounts_qs.count(),
            'contacts_count': contacts_qs.count(),
            'pipeline_value': pipeline_value,
            'open_leads_count': leads_qs.exclude(status__in=EXCLUDED_LEAD_STATUSES).count(),
            'won_opportunities_count': opportunities_qs.filter(stage='CLOSED WON').count(),
        }

        # Get recent items (last 5 of each)
        recent_leads = leads_qs.order_by('-created_at')[:5]
        recent_opportunities = opportunities_qs.order_by('-created_at')[:5]
        recent_contacts = contacts_qs.order_by('-created_at')[:5]

        response_data = {
            'stats': stats,
            'recent_leads': RecentLeadSerializer(recent_leads, many=True).data,
            'recent_opportunities': RecentOpportunitySerializer(recent_opportunities, many=True).data,
            'recent_contacts': RecentContactSerializer(recent_contacts, many=True).data,
            'recent_activities': self._get_activity_logs(org),
        }

        return Response(response_data, status=status.HTTP_200_OK)
