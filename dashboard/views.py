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


class DashboardView(APIView):
    """
    Dashboard API endpoint that provides:
    - Key statistics (counts for all CRM entities)
    - Pipeline value (sum of opportunity amounts)
    - Recent leads, opportunities, contacts, tasks, cases
    - Recent activity logs
    """
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        description="Get dashboard statistics and recent items",
        responses={200: DashboardResponseSerializer},
        tags=["Dashboard"]
    )
    def get(self, request, *args, **kwargs):
        org = request.profile.org
        profile = request.profile
        is_admin = profile.role == "ADMIN" or profile.is_admin or request.user.is_superuser

        # DEBUG: Print to server console
        print(f"DEBUG Dashboard - User: {request.user.email}")
        print(f"DEBUG Dashboard - Org ID: {org.id}, Org Name: {org.name}")
        print(f"DEBUG Dashboard - Profile ID: {profile.id}, Role: {profile.role}, is_admin: {profile.is_admin}")
        print(f"DEBUG Dashboard - Is Admin Check: {is_admin}")
        print(f"DEBUG Dashboard - Total Leads in DB: {Lead.objects.count()}")
        print(f"DEBUG Dashboard - Leads with this org: {Lead.objects.filter(org=org).count()}")
        print(f"DEBUG Dashboard - Opportunities with this org: {Opportunity.objects.filter(org=org).count()}")
        print(f"DEBUG Dashboard - Contacts with this org: {Contact.objects.filter(org=org).count()}")
        print(f"DEBUG Dashboard - Accounts with this org: {Account.objects.filter(org=org).count()}")
        print(f"DEBUG Dashboard - ActivityLogs with this org: {ActivityLog.objects.filter(org=org).count()}")

        # Base querysets filtered by organization
        leads_qs = Lead.objects.filter(org=org)
        opportunities_qs = Opportunity.objects.filter(org=org)
        contacts_qs = Contact.objects.filter(org=org)
        accounts_qs = Account.objects.filter(org=org)

        # For non-admin users, filter by assigned or created
        if not is_admin:
            leads_qs = leads_qs.filter(
                Q(assigned_to=profile) | Q(created_by=request.user)
            )
            opportunities_qs = opportunities_qs.filter(
                Q(assigned_to=profile) | Q(created_by=request.user)
            )
            contacts_qs = contacts_qs.filter(
                Q(assigned_to=profile) | Q(created_by=request.user)
            )
            accounts_qs = accounts_qs.filter(
                Q(assigned_to=profile) | Q(created_by=request.user)
            )

        # Calculate statistics
        leads_count = leads_qs.count()
        opportunities_count = opportunities_qs.count()
        accounts_count = accounts_qs.count()
        contacts_count = contacts_qs.count()

        # Pipeline value (sum of opportunity amounts for open opportunities)
        pipeline_value = opportunities_qs.exclude(
            stage__in=['CLOSED WON', 'CLOSED LOST']
        ).aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')

        # Additional stats
        open_leads_count = leads_qs.exclude(
            status__in=['closed', 'converted']
        ).count()

        won_opportunities_count = opportunities_qs.filter(
            stage='CLOSED WON'
        ).count()

        stats = {
            'leads_count': leads_count,
            'opportunities_count': opportunities_count,
            'accounts_count': accounts_count,
            'contacts_count': contacts_count,
            'pipeline_value': pipeline_value,
            'open_leads_count': open_leads_count,
            'won_opportunities_count': won_opportunities_count,
        }

        # Get recent items (last 5 of each)
        recent_leads = leads_qs.order_by('-created_at')[:5]
        recent_opportunities = opportunities_qs.order_by('-created_at')[:5]
        recent_contacts = contacts_qs.order_by('-created_at')[:5]

        # Get recent activity logs
        activity_logs = []
        try:
            activity_logs_qs = ActivityLog.objects.filter(org=org).order_by('-created_at')[:10]
            activity_logs = [
                {
                    'id': str(log.id),
                    'action': log.action,
                    'model_name': log.entity_type,
                    'object_id': str(log.entity_id) if log.entity_id else None,
                    'object_repr': log.entity_name,
                    'user_email': log.user_email or (log.user.email if log.user else None),
                    'created_at': log.created_at.isoformat(),
                    'created_on_arrow': log.created_on_arrow if hasattr(log, 'created_on_arrow') else None,
                }
                for log in activity_logs_qs
            ]
        except Exception:
            # ActivityLog might not exist or have different structure
            pass

        response_data = {
            'stats': stats,
            'recent_leads': RecentLeadSerializer(recent_leads, many=True).data,
            'recent_opportunities': RecentOpportunitySerializer(recent_opportunities, many=True).data,
            'recent_contacts': RecentContactSerializer(recent_contacts, many=True).data,
            'recent_activities': activity_logs,
        }

        return Response(response_data, status=status.HTTP_200_OK)
