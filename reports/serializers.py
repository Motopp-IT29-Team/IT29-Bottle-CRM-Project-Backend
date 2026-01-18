from rest_framework import serializers
from .models import ReportConfiguration, GeneratedReport
from common.models import User


class ReportConfigurationSerializer(serializers.ModelSerializer):
    """Serializer for report configuration."""
    
    created_by_name = serializers.SerializerMethodField()
    report_type_display = serializers.CharField(source='get_report_type_display', read_only=True)
    
    class Meta:
        model = ReportConfiguration
        fields = [
            'id', 'name', 'report_type', 'report_type_display',
            'date_from', 'date_to', 'date_preset',
            'filters', 'metrics', 'grouping',
            'include_graphics', 'graphics_config',
            'include_summary', 'include_charts', 'include_tables', 'include_logo',
            'created_by', 'created_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']
    
    def get_created_by_name(self, obj):
        if obj.created_by:
            return f"{obj.created_by.first_name} {obj.created_by.last_name}".strip() or obj.created_by.email
        return None
    
    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['org'] = request.profile.org
        validated_data['created_by'] = request.profile.user
        return super().create(validated_data)


class GeneratedReportSerializer(serializers.ModelSerializer):
    """Serializer for generated reports."""
    
    generated_by_name = serializers.SerializerMethodField()
    configuration_name = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = GeneratedReport
        fields = [
            'id', 'configuration', 'configuration_name',
            'file_path', 'file_url', 'file_name', 'status', 'error_message',
            'generated_by', 'generated_by_name', 'generated_at'
        ]
        read_only_fields = ['id', 'generated_at', 'generated_by']
    
    def get_generated_by_name(self, obj):
        if obj.generated_by:
            return f"{obj.generated_by.first_name} {obj.generated_by.last_name}".strip() or obj.generated_by.email
        return None
    
    def get_configuration_name(self, obj):
        return obj.configuration.name if obj.configuration else None
    
    def get_file_url(self, obj):
        if obj.file_path:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file_path.url)
        return None


class ReportGenerateRequestSerializer(serializers.Serializer):
    """Serializer for report generation request."""
    
    configuration_id = serializers.IntegerField(required=False)
    report_type = serializers.ChoiceField(
        choices=ReportConfiguration.REPORT_TYPE_CHOICES,
        required=False
    )
    date_from = serializers.DateField(required=False, allow_null=True)
    date_to = serializers.DateField(required=False, allow_null=True)
    date_preset = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    filters = serializers.JSONField(required=False, default=dict)
    metrics = serializers.JSONField(required=False, default=list)
    grouping = serializers.ChoiceField(
        choices=ReportConfiguration.GROUPING_CHOICES,
        required=False,
        allow_blank=True,
        allow_null=True
    )
    include_graphics = serializers.BooleanField(default=True)
    graphics_config = serializers.JSONField(required=False, default=dict)
    include_summary = serializers.BooleanField(default=True)
    include_charts = serializers.BooleanField(default=True)
    include_tables = serializers.BooleanField(default=True)
    include_logo = serializers.BooleanField(default=True)
    
    def validate(self, data):
        # Either configuration_id or report_type must be provided
        if not data.get('configuration_id') and not data.get('report_type'):
            raise serializers.ValidationError(
                "Either configuration_id or report_type must be provided"
            )
        return data
