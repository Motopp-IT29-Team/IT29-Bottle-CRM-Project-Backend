from django.urls import path
from .views import (
    ReportConfigurationListCreateView,
    ReportConfigurationDetailView,
    ReportGenerateView,
    ReportDownloadView,
    GeneratedReportsListView
)

app_name = 'reports'

urlpatterns = [
    # Report configurations
    path('configurations/', ReportConfigurationListCreateView.as_view(), name='config-list-create'),
    path('configurations/<int:pk>/', ReportConfigurationDetailView.as_view(), name='config-detail'),
    
    # Report generation
    path('generate/', ReportGenerateView.as_view(), name='generate'),
    
    # Generated reports
    path('generated/', GeneratedReportsListView.as_view(), name='generated-list'),
    path('download/<int:pk>/', ReportDownloadView.as_view(), name='download'),
]
