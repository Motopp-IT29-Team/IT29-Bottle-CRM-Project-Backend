from rest_framework import serializers
from leads.models import Lead
from opportunity.models import Opportunity
from contacts.models import Contact
from accounts.models import Account


class RecentLeadSerializer(serializers.ModelSerializer):
    """Serializer for recent leads in dashboard"""
    full_name = serializers.SerializerMethodField()
    created_on_arrow = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = ['id', 'first_name', 'last_name', 'full_name', 'email', 'status', 'source', 'created_at', 'created_on_arrow']

    def get_full_name(self, obj):
        return f"{obj.first_name or ''} {obj.last_name or ''}".strip()

    def get_created_on_arrow(self, obj):
        import arrow
        return arrow.get(obj.created_at).humanize()


class RecentOpportunitySerializer(serializers.ModelSerializer):
    """Serializer for recent opportunities in dashboard"""
    created_on_arrow = serializers.SerializerMethodField()
    account_name = serializers.SerializerMethodField()

    class Meta:
        model = Opportunity
        fields = ['id', 'name', 'stage', 'amount', 'currency', 'probability', 'account_name', 'created_at', 'created_on_arrow']

    def get_created_on_arrow(self, obj):
        import arrow
        return arrow.get(obj.created_at).humanize()

    def get_account_name(self, obj):
        return obj.account.name if obj.account else None


class RecentContactSerializer(serializers.ModelSerializer):
    """Serializer for recent contacts in dashboard"""
    full_name = serializers.SerializerMethodField()
    created_on_arrow = serializers.SerializerMethodField()

    class Meta:
        model = Contact
        fields = ['id', 'first_name', 'last_name', 'full_name', 'primary_email', 'organization', 'created_at', 'created_on_arrow']

    def get_full_name(self, obj):
        return f"{obj.first_name or ''} {obj.last_name or ''}".strip()

    def get_created_on_arrow(self, obj):
        import arrow
        return arrow.get(obj.created_at).humanize()


class DashboardStatsSerializer(serializers.Serializer):
    """Serializer for dashboard statistics"""
    leads_count = serializers.IntegerField()
    opportunities_count = serializers.IntegerField()
    accounts_count = serializers.IntegerField()
    contacts_count = serializers.IntegerField()
    pipeline_value = serializers.DecimalField(max_digits=15, decimal_places=2)
    open_leads_count = serializers.IntegerField()
    won_opportunities_count = serializers.IntegerField()


class DashboardResponseSerializer(serializers.Serializer):
    """Serializer for full dashboard response"""
    stats = DashboardStatsSerializer()
    recent_leads = RecentLeadSerializer(many=True)
    recent_opportunities = RecentOpportunitySerializer(many=True)
    recent_contacts = RecentContactSerializer(many=True)


