from rest_framework import serializers

from accounts.models import Account, Tags
from common.serializer import (
    AttachmentsSerializer,
    LeadCommentSerializer,
    OrganizationSerializer,
    ProfileSerializer,
    UserSerializer,
)
from contacts.serializer import ContactSerializer
from leads.models import Company, Lead
from teams.serializer import TeamsSerializer


class TagsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tags
        fields = ("id", "name", "slug")


class CompanySwaggerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ("name",)


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ("id", "name", "org")


class LeadSerializer(serializers.ModelSerializer):
    contacts = ContactSerializer(read_only=True, many=True)
    assigned_to = ProfileSerializer(read_only=True, many=True)
    created_by = UserSerializer()
    country = serializers.SerializerMethodField()
    tags = TagsSerializer(read_only=True, many=True)
    lead_attachment = AttachmentsSerializer(read_only=True, many=True)
    teams = TeamsSerializer(read_only=True, many=True)
    lead_comments = LeadCommentSerializer(read_only=True, many=True)

    status_display = serializers.SerializerMethodField()
    source_display = serializers.SerializerMethodField()
    industry_display = serializers.SerializerMethodField()
    salutation_display = serializers.SerializerMethodField()
    department_display = serializers.SerializerMethodField()
    preferred_language_display = serializers.SerializerMethodField()
    rating_display = serializers.SerializerMethodField()
    budget_range_display = serializers.SerializerMethodField()
    decision_timeframe_display = serializers.SerializerMethodField()

    def get_country(self, obj):
        return obj.get_country_display()

    def get_status_display(self, obj):
        return obj.get_status_display() if obj.status else None

    def get_source_display(self, obj):
        return obj.get_source_display() if obj.source else None

    def get_industry_display(self, obj):
        return obj.get_industry_display() if obj.industry else None

    def get_salutation_display(self, obj):
        return obj.get_salutation_display() if obj.salutation else None

    def get_department_display(self, obj):
        return obj.get_department_display() if obj.department else None

    def get_preferred_language_display(self, obj):
        return obj.get_preferred_language_display() if obj.preferred_language else None

    def get_rating_display(self, obj):
        return obj.get_rating_display() if obj.rating else None

    def get_budget_range_display(self, obj):
        return obj.get_budget_range_display() if obj.budget_range else None

    def get_decision_timeframe_display(self, obj):
        return obj.get_decision_timeframe_display() if obj.decision_timeframe else None

    class Meta:
        model = Lead
        fields = (
            "id",
            "title",
            "first_name",
            "last_name",
            "phone",
            "email",
            "status",
            "status_display",
            "source",
            "source_display",
            "address_line",
            "contacts",
            "street",
            "city",
            "state",
            "postcode",
            "country",
            "website",
            "description",
            "lead_attachment",
            "lead_comments",
            "assigned_to",
            "account_name",
            "opportunity_amount",
            "created_by",
            "created_at",
            "is_active",
            "enquiry_type",
            "tags",
            "created_from_site",
            "teams",
            "industry",
            "industry_display",
            "company",
            "organization",
            "probability",
            "close_date",
            "salutation",
            "salutation_display",
            "department",
            "department_display",
            "preferred_language",
            "preferred_language_display",
            "rating",
            "rating_display",
            "budget_range",
            "budget_range_display",
            "decision_timeframe",
            "decision_timeframe_display",
            "do_not_call",
        )


class LeadCreateSerializer(serializers.ModelSerializer):
    probability = serializers.IntegerField(max_value=100)

    def __init__(self, *args, **kwargs):
        request_obj = kwargs.pop("request_obj", None)
        super().__init__(*args, **kwargs)

        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.fields["email"].required = True
        self.fields["phone"].required = True
        self.fields["title"].required = True
        self.fields["account_name"].required = True
        self.fields["source"].required = True
        self.fields["status"].required = True

        self.org = request_obj.profile.org

        if self.instance:
            if self.instance.created_from_site:
                prev_choices = self.fields["source"]._get_choices()
                prev_choices = prev_choices + [("micropyramid", "Micropyramid")]
                self.fields["source"]._set_choices(prev_choices)

    def validate_email(self, email):
        """Check for duplicate email"""
        if self.instance:
            if (
                    Lead.objects.filter(email__iexact=email, org=self.org)
                            .exclude(id=self.instance.id)
                            .exists()
            ):
                raise serializers.ValidationError(
                    "Lead already exists with this email"
                )
        else:
            if Lead.objects.filter(email__iexact=email, org=self.org).exists():
                raise serializers.ValidationError(
                    "Lead already exists with this email"
                )
        return email

    def validate_phone(self, phone):
        """Check for duplicate phone"""
        if self.instance:
            if (
                    Lead.objects.filter(phone=phone, org=self.org)
                            .exclude(id=self.instance.id)
                            .exists()
            ):
                raise serializers.ValidationError(
                    "Lead already exists with this phone number"
                )
        else:
            if Lead.objects.filter(phone=phone, org=self.org).exists():
                raise serializers.ValidationError(
                    "Lead already exists with this phone number"
                )
        return phone

    def validate_account_name(self, account_name):
        if self.instance:
            return account_name

        if Account.objects.filter(name__iexact=account_name, org=self.org).exists():
            raise serializers.ValidationError(
                "Account already exists with this name"
            )
        return account_name

    def validate_title(self, title):
        if self.instance:
            if (
                    Lead.objects.filter(title__iexact=title, org=self.org)
                            .exclude(id=self.instance.id)
                            .exists()
            ):
                raise serializers.ValidationError("Lead already exists with this title")
        else:
            if Lead.objects.filter(title__iexact=title, org=self.org).exists():
                raise serializers.ValidationError("Lead already exists with this title")
        return title

    class Meta:
        model = Lead
        fields = (
            "first_name",
            "last_name",
            "account_name",
            "title",
            "phone",
            "email",
            "status",
            "source",
            "website",
            "description",
            "address_line",
            "street",
            "city",
            "state",
            "postcode",
            "opportunity_amount",
            "country",
            "org",
            "industry",
            "company",
            "organization",
            "probability",
            "close_date",
            "salutation",
            "department",
            "preferred_language",
            "rating",
            "budget_range",
            "decision_timeframe",
            "do_not_call",
        )


class LeadCreateSwaggerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = ["title", "first_name", "last_name", "account_name", "phone", "email", "lead_attachment",
                  "opportunity_amount", "website",
                  "description", "teams", "assigned_to", "contacts", "status", "source", "address_line", "street",
                  "city", "state", "postcode",
                  "country", "tags", "company", "probability", "industry", "skype_ID"]


class CreateLeadFromSiteSwaggerSerializer(serializers.Serializer):
    apikey = serializers.CharField()
    title = serializers.CharField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    phone = serializers.CharField()
    email = serializers.CharField()
    source = serializers.CharField()
    description = serializers.CharField()


class LeadDetailEditSwaggerSerializer(serializers.Serializer):
    comment = serializers.CharField()
    lead_attachment = serializers.FileField()


class LeadCommentEditSwaggerSerializer(serializers.Serializer):
    comment = serializers.CharField()


class LeadUploadSwaggerSerializer(serializers.Serializer):
    leads_file = serializers.FileField()