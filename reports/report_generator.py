"""
Service for generating PDF reports with charts and data.
"""
from datetime import datetime, timedelta
from io import BytesIO
import os
from django.conf import settings
from django.db.models import Count, Sum, Avg, Q
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
from reportlab.platypus.flowables import HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import matplotlib
matplotlib.use('Agg')  # Use non-GUI backend
import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg
from leads.models import Lead
from opportunity.models import Opportunity
from accounts.models import Account
from contacts.models import Contact
from cases.models import Case
from invoices.models import Invoice


class ReportGeneratorService:
    """Service to generate PDF reports with charts."""
    
    def __init__(self, config_data, org, user):
        self.config = config_data
        self.org = org
        self.user = user
        self.date_from = None
        self.date_to = None
        self.buffer = BytesIO()
        self.styles = getSampleStyleSheet()
        self._setup_dates()
        
    def _setup_dates(self):
        """Setup date range based on preset or custom dates."""
        date_preset = self.config.get('date_preset')
        today = datetime.now().date()
        
        if date_preset == 'today':
            self.date_from = self.date_to = today
        elif date_preset == 'this_week':
            self.date_from = today - timedelta(days=today.weekday())
            self.date_to = today
        elif date_preset == 'this_month':
            self.date_from = today.replace(day=1)
            self.date_to = today
        elif date_preset == 'this_quarter':
            quarter = (today.month - 1) // 3
            self.date_from = today.replace(month=quarter * 3 + 1, day=1)
            self.date_to = today
        elif date_preset == 'this_year':
            self.date_from = today.replace(month=1, day=1)
            self.date_to = today
        elif date_preset == 'last_30_days':
            self.date_from = today - timedelta(days=30)
            self.date_to = today
        elif date_preset == 'last_60_days':
            self.date_from = today - timedelta(days=60)
            self.date_to = today
        elif date_preset == 'last_90_days':
            self.date_from = today - timedelta(days=90)
            self.date_to = today
        else:
            # Custom dates
            self.date_from = self.config.get('date_from')
            self.date_to = self.config.get('date_to')
        
        # Default to last 30 days if no dates specified
        if not self.date_from:
            self.date_from = today - timedelta(days=30)
        if not self.date_to:
            self.date_to = today
    
    def generate(self):
        """Generate the PDF report."""
        doc = SimpleDocTemplate(
            self.buffer,
            pagesize=A4,
            rightMargin=40,
            leftMargin=40,
            topMargin=40,
            bottomMargin=40
        )
        
        story = []
        
        # Add header
        story.extend(self._create_header())
        story.append(Spacer(1, 0.3 * inch))
        
        # Add summary section if enabled
        if self.config.get('include_summary', True):
            story.extend(self._create_summary())
            story.append(Spacer(1, 0.3 * inch))
        
        # Add charts if enabled
        if self.config.get('include_charts', True) and self.config.get('include_graphics', True):
            story.extend(self._create_charts())
            story.append(Spacer(1, 0.3 * inch))
        
        # Add data tables if enabled
        if self.config.get('include_tables', True):
            story.extend(self._create_tables())
        
        # Build PDF
        doc.build(story)
        pdf_data = self.buffer.getvalue()
        self.buffer.close()
        
        return pdf_data
    
    def _create_header(self):
        """Create report header."""
        elements = []
        
        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1976d2'),
            spaceAfter=12,
            alignment=TA_CENTER
        )
        
        report_type = dict(self.get_report_type_choices()).get(
            self.config.get('report_type', 'sales'),
            'Report'
        )
        
        elements.append(Paragraph(report_type, title_style))
        
        # Date range and metadata
        info_style = ParagraphStyle(
            'InfoStyle',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#666666'),
            alignment=TA_CENTER
        )
        
        date_str = f"{self.date_from.strftime('%B %d, %Y')} - {self.date_to.strftime('%B %d, %Y')}"
        elements.append(Paragraph(f"<b>Period:</b> {date_str}", info_style))
        elements.append(Paragraph(
            f"<b>Generated:</b> {datetime.now().strftime('%B %d, %Y %I:%M %p')}",
            info_style
        ))
        elements.append(Paragraph(
            f"<b>Generated by:</b> {self.user.get_full_name() or self.user.email}",
            info_style
        ))
        
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#cccccc')))
        
        return elements
    
    def _create_summary(self):
        """Create summary section with key metrics."""
        elements = []
        
        heading_style = ParagraphStyle(
            'SectionHeading',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#1976d2'),
            spaceAfter=12
        )
        
        elements.append(Paragraph("Executive Summary", heading_style))
        
        # Get metrics based on report type
        metrics = self._get_summary_metrics()
        
        # Create table with metrics
        data = []
        for metric in metrics:
            data.append([
                Paragraph(f"<b>{metric['label']}</b>", self.styles['Normal']),
                Paragraph(str(metric['value']), self.styles['Normal'])
            ])
        
        if data:
            table = Table(data, colWidths=[4 * inch, 2 * inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f5f5f5')),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#dddddd')),
                ('PADDING', (0, 0), (-1, -1), 12),
                ('FONTSIZE', (1, 0), (1, -1), 14),
                ('FONTNAME', (1, 0), (1, -1), 'Helvetica-Bold'),
            ]))
            elements.append(table)
        
        return elements
    
    def _get_summary_metrics(self):
        """Get summary metrics based on report type."""
        report_type = self.config.get('report_type', 'sales')
        metrics = []
        
        # Filter by date range
        date_filter = Q(created_at__gte=self.date_from, created_at__lte=self.date_to)
        
        if report_type == 'sales':
            leads_count = Lead.objects.filter(org=self.org).filter(date_filter).count()
            opportunities_count = Opportunity.objects.filter(org=self.org).filter(date_filter).count()
            
            metrics = [
                {'label': 'Total Leads', 'value': leads_count},
                {'label': 'Total Opportunities', 'value': opportunities_count},
            ]
        
        elif report_type == 'revenue':
            invoices = Invoice.objects.filter(org=self.org).filter(date_filter)
            total_revenue = invoices.aggregate(total=Sum('total_amount'))['total'] or 0
            
            metrics = [
                {'label': 'Total Invoices', 'value': invoices.count()},
                {'label': 'Total Revenue', 'value': f"${total_revenue:,.2f}"},
            ]
        
        elif report_type == 'contact':
            contacts_count = Contact.objects.filter(org=self.org).filter(date_filter).count()
            accounts_count = Account.objects.filter(org=self.org).filter(date_filter).count()
            
            metrics = [
                {'label': 'Total Contacts', 'value': contacts_count},
                {'label': 'Total Accounts', 'value': accounts_count},
            ]
        
        elif report_type == 'case':
            cases = Case.objects.filter(org=self.org).filter(date_filter)
            open_cases = cases.filter(status='open').count()
            closed_cases = cases.filter(status='closed').count()
            
            metrics = [
                {'label': 'Total Cases', 'value': cases.count()},
                {'label': 'Open Cases', 'value': open_cases},
                {'label': 'Closed Cases', 'value': closed_cases},
            ]
        
        return metrics
    
    def _create_charts(self):
        """Create charts section."""
        elements = []
        
        heading_style = ParagraphStyle(
            'SectionHeading',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#1976d2'),
            spaceAfter=12
        )
        
        elements.append(Paragraph("Visual Analytics", heading_style))
        
        graphics_config = self.config.get('graphics_config', {})
        
        # Generate charts based on configuration
        chart_images = self._generate_charts(graphics_config)
        
        for img_buffer in chart_images:
            img = Image(img_buffer, width=5 * inch, height=3 * inch)
            elements.append(img)
            elements.append(Spacer(1, 0.2 * inch))
        
        return elements
    
    def _generate_charts(self, graphics_config):
        """Generate matplotlib charts."""
        chart_buffers = []
        report_type = self.config.get('report_type', 'sales')
        
        # Get chart data
        chart_data = self._get_chart_data()
        
        if not chart_data:
            return chart_buffers
        
        # Chart 1: Bar chart
        if graphics_config.get('show_bar_chart', True):
            fig, ax = plt.subplots(figsize=(8, 5))
            
            labels = chart_data.get('labels', [])
            values = chart_data.get('values', [])
            
            colors_list = graphics_config.get('colors', ['#1976d2', '#dc004e', '#f50057', '#9c27b0', '#3f51b5'])
            
            ax.bar(labels, values, color=colors_list[:len(labels)])
            ax.set_title(chart_data.get('title', 'Data Overview'))
            ax.set_ylabel('Count')
            plt.xticks(rotation=45, ha='right')
            plt.tight_layout()
            
            buffer = BytesIO()
            plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
            buffer.seek(0)
            chart_buffers.append(buffer)
            plt.close()
        
        # Chart 2: Pie chart for distribution
        if graphics_config.get('show_pie_chart', True) and len(chart_data.get('labels', [])) > 0:
            fig, ax = plt.subplots(figsize=(8, 5))
            
            labels = chart_data.get('labels', [])
            values = chart_data.get('values', [])
            colors_list = graphics_config.get('colors', ['#1976d2', '#dc004e', '#f50057', '#9c27b0', '#3f51b5'])
            
            ax.pie(values, labels=labels, autopct='%1.1f%%', colors=colors_list[:len(labels)])
            ax.set_title(chart_data.get('distribution_title', 'Distribution'))
            plt.tight_layout()
            
            buffer = BytesIO()
            plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
            buffer.seek(0)
            chart_buffers.append(buffer)
            plt.close()
        
        return chart_buffers
    
    def _get_chart_data(self):
        """Get data for charts based on report type."""
        report_type = self.config.get('report_type', 'sales')
        date_filter = Q(created_at__gte=self.date_from, created_at__lte=self.date_to)
        
        if report_type == 'sales':
            # Get leads by status
            leads = Lead.objects.filter(org=self.org).filter(date_filter)
            status_data = leads.values('status').annotate(count=Count('id'))
            
            return {
                'title': 'Leads by Status',
                'distribution_title': 'Lead Status Distribution',
                'labels': [item['status'] for item in status_data],
                'values': [item['count'] for item in status_data],
            }
        
        elif report_type == 'case':
            # Get cases by status
            cases = Case.objects.filter(org=self.org).filter(date_filter)
            status_data = cases.values('status').annotate(count=Count('id'))
            
            return {
                'title': 'Cases by Status',
                'distribution_title': 'Case Status Distribution',
                'labels': [item['status'] for item in status_data],
                'values': [item['count'] for item in status_data],
            }
        
        return {}
    
    def _create_tables(self):
        """Create data tables section."""
        elements = []
        
        heading_style = ParagraphStyle(
            'SectionHeading',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#1976d2'),
            spaceAfter=12
        )
        
        elements.append(Paragraph("Detailed Data", heading_style))
        
        # Get table data based on report type
        table_data = self._get_table_data()
        
        if table_data and table_data['rows']:
            # Create table
            data = [table_data['headers']] + table_data['rows']
            
            table = Table(data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1976d2')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f5f5f5')),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#dddddd')),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('PADDING', (0, 0), (-1, -1), 8),
            ]))
            
            elements.append(table)
        
        return elements
    
    def _get_table_data(self):
        """Get table data based on report type."""
        report_type = self.config.get('report_type', 'sales')
        date_filter = Q(created_at__gte=self.date_from, created_at__lte=self.date_to)
        
        if report_type == 'sales':
            leads = Lead.objects.filter(org=self.org).filter(date_filter)[:20]
            
            return {
                'headers': ['Title', 'Email', 'Status', 'Source', 'Created At'],
                'rows': [
                    [
                        lead.title,
                        lead.email or '-',
                        lead.status,
                        lead.source or '-',
                        lead.created_at.strftime('%Y-%m-%d')
                    ]
                    for lead in leads
                ]
            }
        
        elif report_type == 'contact':
            contacts = Contact.objects.filter(org=self.org).filter(date_filter)[:20]
            
            return {
                'headers': ['First Name', 'Last Name', 'Email', 'Phone', 'Created At'],
                'rows': [
                    [
                        contact.first_name,
                        contact.last_name or '-',
                        contact.email or '-',
                        str(contact.phone) if contact.phone else '-',
                        contact.created_at.strftime('%Y-%m-%d')
                    ]
                    for contact in contacts
                ]
            }
        
        elif report_type == 'case':
            cases = Case.objects.filter(org=self.org).filter(date_filter)[:20]
            
            return {
                'headers': ['Name', 'Status', 'Priority', 'Type', 'Created At'],
                'rows': [
                    [
                        case.name,
                        case.status,
                        case.priority or '-',
                        case.case_type or '-',
                        case.created_at.strftime('%Y-%m-%d')
                    ]
                    for case in cases
                ]
            }
        
        return {'headers': [], 'rows': []}
    
    @staticmethod
    def get_report_type_choices():
        """Return report type choices."""
        return [
            ('sales', 'Sales Report'),
            ('revenue', 'Revenue Report'),
            ('activity', 'Activity Report'),
            ('contact', 'Contact/Account Report'),
            ('case', 'Case/Support Report'),
            ('team', 'Team Performance Report'),
        ]
