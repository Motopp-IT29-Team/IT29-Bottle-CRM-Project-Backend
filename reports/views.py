from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.http import FileResponse, HttpResponse
from django.core.files.base import ContentFile
from datetime import datetime
from .models import ReportConfiguration, GeneratedReport
from .serializers import (
    ReportConfigurationSerializer,
    GeneratedReportSerializer,
    ReportGenerateRequestSerializer
)
from .report_generator import ReportGeneratorService
from common.access_decorators_mixins import SalesAccessRequiredMixin


class ReportConfigurationListCreateView(SalesAccessRequiredMixin, APIView):
    """API view to list and create report configurations."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """List all report configurations for the organization."""
        configs = ReportConfiguration.objects.filter(org=request.profile.org)
        serializer = ReportConfigurationSerializer(configs, many=True)
        
        return Response({
            'error': False,
            'data': serializer.data
        }, status=status.HTTP_200_OK)
    
    def post(self, request):
        """Create a new report configuration."""
        serializer = ReportConfigurationSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            serializer.save()
            return Response({
                'error': False,
                'message': 'Report configuration created successfully',
                'data': serializer.data
            }, status=status.HTTP_201_CREATED)
        
        return Response({
            'error': True,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class ReportConfigurationDetailView(SalesAccessRequiredMixin, APIView):
    """API view to retrieve, update, and delete report configurations."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pk):
        """Retrieve a report configuration."""
        try:
            config = ReportConfiguration.objects.get(
                pk=pk,
                org=request.profile.org
            )
            serializer = ReportConfigurationSerializer(config)
            
            return Response({
                'error': False,
                'data': serializer.data
            }, status=status.HTTP_200_OK)
        except ReportConfiguration.DoesNotExist:
            return Response({
                'error': True,
                'message': 'Report configuration not found'
            }, status=status.HTTP_404_NOT_FOUND)
    
    def put(self, request, pk):
        """Update a report configuration."""
        try:
            config = ReportConfiguration.objects.get(
                pk=pk,
                org=request.profile.org
            )
            serializer = ReportConfigurationSerializer(
                config,
                data=request.data,
                partial=True,
                context={'request': request}
            )
            
            if serializer.is_valid():
                serializer.save()
                return Response({
                    'error': False,
                    'message': 'Report configuration updated successfully',
                    'data': serializer.data
                }, status=status.HTTP_200_OK)
            
            return Response({
                'error': True,
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        except ReportConfiguration.DoesNotExist:
            return Response({
                'error': True,
                'message': 'Report configuration not found'
            }, status=status.HTTP_404_NOT_FOUND)
    
    def delete(self, request, pk):
        """Delete a report configuration."""
        try:
            config = ReportConfiguration.objects.get(
                pk=pk,
                org=request.profile.org
            )
            config.delete()
            
            return Response({
                'error': False,
                'message': 'Report configuration deleted successfully'
            }, status=status.HTTP_200_OK)
        except ReportConfiguration.DoesNotExist:
            return Response({
                'error': True,
                'message': 'Report configuration not found'
            }, status=status.HTTP_404_NOT_FOUND)


class ReportGenerateView(APIView):
    """API view to generate reports."""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Generate a PDF report based on provided configuration."""
        print("=== Report Generation Request ===")
        print(f"Request data: {request.data}")
        print(f"User: {request.user}")
        
        serializer = ReportGenerateRequestSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response({
                'error': True,
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        config_data = serializer.validated_data
        
        # If configuration_id is provided, use it
        if config_data.get('configuration_id'):
            try:
                config_obj = ReportConfiguration.objects.get(
                    pk=config_data['configuration_id'],
                    org=request.profile.org
                )
                # Use config object data and override with any provided data
                final_config = {
                    'report_type': config_obj.report_type,
                    'date_from': config_obj.date_from,
                    'date_to': config_obj.date_to,
                    'date_preset': config_obj.date_preset,
                    'filters': config_obj.filters,
                    'metrics': config_obj.metrics,
                    'grouping': config_obj.grouping,
                    'include_graphics': config_obj.include_graphics,
                    'graphics_config': config_obj.graphics_config,
                    'include_summary': config_obj.include_summary,
                    'include_charts': config_obj.include_charts,
                    'include_tables': config_obj.include_tables,
                    'include_logo': config_obj.include_logo,
                }
                # Override with request data
                for key, value in config_data.items():
                    if key != 'configuration_id' and value is not None:
                        final_config[key] = value
            except ReportConfiguration.DoesNotExist:
                return Response({
                    'error': True,
                    'message': 'Report configuration not found'
                }, status=status.HTTP_404_NOT_FOUND)
        else:
            final_config = config_data
            config_obj = None
        
        # Generate report
        try:
            generator = ReportGeneratorService(
                final_config,
                request.profile.org,
                request.profile.user
            )
            
            # Check if there's any data to report
            if not generator.has_data():
                return Response({
                    'error': True,
                    'message': generator.get_no_data_message()
                }, status=status.HTTP_400_BAD_REQUEST)
            
            pdf_data = generator.generate()
            
            # Save generated report
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            report_type = final_config.get('report_type', 'report')
            filename = f"{report_type}_{timestamp}.pdf"
            
            generated_report = GeneratedReport.objects.create(
                configuration=config_obj,
                file_name=filename,
                status='completed',
                org=request.profile.org,
                generated_by=request.profile.user
            )
            
            # Save PDF file
            generated_report.file_path.save(filename, ContentFile(pdf_data))
            
            serializer = GeneratedReportSerializer(
                generated_report,
                context={'request': request}
            )
            
            return Response({
                'error': False,
                'message': 'Report generated successfully',
                'data': serializer.data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            # Log error and create failed report record
            generated_report = GeneratedReport.objects.create(
                configuration=config_obj,
                file_name=f"failed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                status='failed',
                error_message=str(e),
                org=request.profile.org,
                generated_by=request.profile.user
            )
            
            return Response({
                'error': True,
                'message': f'Failed to generate report: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ReportDownloadView(APIView):
    """API view to download generated reports."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pk):
        """Download a generated report."""
        print(f"=== Download Request for report {pk} ===")
        try:
            report = GeneratedReport.objects.get(
                pk=pk,
                org=request.profile.org
            )
            
            print(f"Report found: {report.file_name}, status: {report.status}")
            print(f"File path: {report.file_path}")
            
            if report.status != 'completed' or not report.file_path:
                return Response({
                    'error': True,
                    'message': 'Report file not available'
                }, status=status.HTTP_404_NOT_FOUND)
            
            return FileResponse(
                report.file_path.open('rb'),
                as_attachment=True,
                filename=report.file_name,
                content_type='application/pdf'
            )
            
        except GeneratedReport.DoesNotExist:
            return Response({
                'error': True,
                'message': 'Report not found'
            }, status=status.HTTP_404_NOT_FOUND)


class GeneratedReportsListView(SalesAccessRequiredMixin, APIView):
    """API view to list generated reports."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """List all generated reports for the organization."""
        reports = GeneratedReport.objects.filter(org=request.profile.org)[:50]
        serializer = GeneratedReportSerializer(
            reports,
            many=True,
            context={'request': request}
        )
        
        return Response({
            'error': False,
            'data': serializer.data
        }, status=status.HTTP_200_OK)
