from django.db import models
from django.contrib.postgres.fields import ArrayField
from common.models import Org, User
import json


class ReportConfiguration(models.Model):
    """Model to store report configurations."""
    
    REPORT_TYPE_CHOICES = [
        ('leads', 'Leads Report'),
        ('accounts', 'Accounts Report'),
        ('contacts', 'Contacts Report'),
        ('opportunities', 'Opportunities Report'),
        ('companies', 'Companies Report'),
        ('activity', 'Activity Logs Report'),
    ]
    
    GROUPING_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('user', 'By User'),
        ('status', 'By Status'),
        ('source', 'By Source'),
        ('action', 'By Action'),
        ('stage', 'By Stage'),
    ]
    
    name = models.CharField(max_length=255, help_text="Report configuration name")
    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES)
    
    # Date range
    date_from = models.DateField(null=True, blank=True)
    date_to = models.DateField(null=True, blank=True)
    date_preset = models.CharField(max_length=50, blank=True, null=True, 
                                   help_text="Preset like 'this_month', 'last_30_days', etc.")
    
    # Filters (stored as JSON)
    filters = models.JSONField(default=dict, blank=True, 
                               help_text="Store filters like users, status, source, etc.")
    
    # Metrics to include
    metrics = models.JSONField(default=list, blank=True,
                              help_text="List of metrics to include in the report")
    
    # Grouping
    grouping = models.CharField(max_length=20, choices=GROUPING_CHOICES, blank=True, null=True)
    
    # Graphics configuration
    include_graphics = models.BooleanField(default=True)
    graphics_config = models.JSONField(default=dict, blank=True,
                                      help_text="Store chart types, colors, and other visual settings")
    
    # Report format options
    include_summary = models.BooleanField(default=True)
    include_charts = models.BooleanField(default=True)
    include_tables = models.BooleanField(default=True)
    include_logo = models.BooleanField(default=False)
    
    # Metadata
    org = models.ForeignKey(Org, on_delete=models.CASCADE, related_name='report_configs')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_reports')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'report_configuration'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.get_report_type_display()}"


class GeneratedReport(models.Model):
    """Model to track generated reports."""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    configuration = models.ForeignKey(ReportConfiguration, on_delete=models.SET_NULL, 
                                     null=True, blank=True, related_name='generated_reports')
    file_path = models.FileField(upload_to='reports/', null=True, blank=True)
    file_name = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True, null=True)
    
    # Metadata
    org = models.ForeignKey(Org, on_delete=models.CASCADE, related_name='generated_reports')
    generated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='generated_reports')
    generated_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'generated_report'
        ordering = ['-generated_at']
    
    def __str__(self):
        return f"{self.file_name} - {self.status}"

