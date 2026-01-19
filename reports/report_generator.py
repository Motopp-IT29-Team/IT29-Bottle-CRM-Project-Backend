"""
Service for generating PDF reports with charts and data.
"""
from datetime import datetime, timedelta
from io import BytesIO
import os
from django.conf import settings
from django.db.models import Count, Sum, Avg, Q
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth
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
from leads.models import Lead, Company
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
    
    def has_data(self):
        """Check if there is any data for the selected report type and date range."""
        report_type = self.config.get('report_type', 'leads')
        date_filter = Q(created_at__gte=self.date_from, created_at__lte=self.date_to)
        
        if report_type == 'leads':
            return Lead.objects.filter(org=self.org).filter(date_filter).exists()
        elif report_type == 'accounts':
            return Account.objects.filter(org=self.org).filter(date_filter).exists()
        elif report_type == 'contacts':
            return Contact.objects.filter(org=self.org).filter(date_filter).exists()
        elif report_type == 'opportunities':
            return Opportunity.objects.filter(org=self.org).filter(date_filter).exists()
        elif report_type == 'companies':
            return Company.objects.filter(org=self.org).filter(date_filter).exists()
        elif report_type == 'activity':
            from common.models import ActivityLog
            return ActivityLog.objects.filter(org=self.org).filter(date_filter).exists()
        
        return False
    
    def get_no_data_message(self):
        """Get a user-friendly message when no data is found."""
        report_type = self.config.get('report_type', 'leads')
        report_type_labels = {
            'leads': 'Leads',
            'accounts': 'Accounts',
            'contacts': 'Contacts',
            'opportunities': 'Opportunities',
            'companies': 'Companies',
            'activity': 'Activity Logs',
        }
        label = report_type_labels.get(report_type, report_type.title())
        date_from_str = self.date_from.strftime('%B %d, %Y')
        date_to_str = self.date_to.strftime('%B %d, %Y')
        
        return f"No {label} found for the selected period ({date_from_str} - {date_to_str}). Please select a different date range or report type."
    
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
        
        # Add logo if enabled
        if self.config.get('include_logo', False):
            # Try to find a logo file
            possible_logo_paths = [
                os.path.join(settings.BASE_DIR, 'static', 'assets', 'img', 'logo-business.png'),
                os.path.join(settings.BASE_DIR, 'static', 'assets', 'img', 'logo-saas.png'),
                os.path.join(settings.BASE_DIR, 'static', 'images', 'logo.png'),
                os.path.join(settings.BASE_DIR, 'static', 'logo.png'),
            ]
            
            logo_path = None
            for path in possible_logo_paths:
                if os.path.exists(path):
                    logo_path = path
                    break
            
            if logo_path:
                try:
                    logo = Image(logo_path, width=2 * inch, height=0.6 * inch)
                    logo.hAlign = 'CENTER'
                    elements.append(logo)
                    elements.append(Spacer(1, 0.2 * inch))
                except Exception as e:
                    # If logo fails to load, just skip it
                    print(f"Failed to load logo: {e}")
        
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
        
        # Add grouping info
        grouping = self.config.get('grouping')
        if grouping:
            grouping_labels = {
                'daily': 'Daily',
                'weekly': 'Weekly', 
                'monthly': 'Monthly',
                'user': 'By User',
                'status': 'By Status',
                'source': 'By Source',
                'action': 'By Action',
                'stage': 'By Stage',
            }
            grouping_label = grouping_labels.get(grouping, grouping.title())
            elements.append(Paragraph(f"<b>Data Grouping:</b> {grouping_label}", info_style))
        
        elements.append(Paragraph(
            f"<b>Generated:</b> {datetime.now().strftime('%B %d, %Y %I:%M %p')}",
            info_style
        ))
        
        # Get user display name
        user_name = f"{self.user.first_name} {self.user.last_name}".strip() or self.user.email
        elements.append(Paragraph(
            f"<b>Generated by:</b> {user_name}",
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
        
        # Check if all metrics have zero values
        all_zero = all(metric['value'] == 0 or metric['value'] == '0' for metric in metrics)
        
        if not metrics or all_zero:
            no_data_style = ParagraphStyle(
                'NoDataStyle',
                parent=self.styles['Normal'],
                fontSize=12,
                textColor=colors.HexColor('#666666'),
                alignment=TA_CENTER,
                spaceBefore=20,
                spaceAfter=20
            )
            elements.append(Paragraph(
                f"No data found for the selected period ({self.date_from.strftime('%B %d, %Y')} - {self.date_to.strftime('%B %d, %Y')})",
                no_data_style
            ))
            return elements
        
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
        report_type = self.config.get('report_type', 'leads')
        metrics = []
        
        # Filter by date range
        date_filter = Q(created_at__gte=self.date_from, created_at__lte=self.date_to)
        
        if report_type == 'leads':
            leads = Lead.objects.filter(org=self.org).filter(date_filter)
            total_leads = leads.count()
            new_leads = leads.filter(status='assigned').count()
            converted = leads.filter(status='converted').count()
            
            metrics = [
                {'label': 'Total Leads', 'value': total_leads},
                {'label': 'New Leads', 'value': new_leads},
                {'label': 'Converted Leads', 'value': converted},
            ]
        
        elif report_type == 'accounts':
            accounts = Account.objects.filter(org=self.org).filter(date_filter)
            open_accounts = accounts.filter(status='open').count()
            closed_accounts = accounts.filter(status='close').count()
            
            metrics = [
                {'label': 'Total Accounts', 'value': accounts.count()},
                {'label': 'Open Accounts', 'value': open_accounts},
                {'label': 'Closed Accounts', 'value': closed_accounts},
            ]
        
        elif report_type == 'contacts':
            contacts = Contact.objects.filter(org=self.org).filter(date_filter)
            active_contacts = contacts.filter(is_active=True).count()
            
            metrics = [
                {'label': 'Total Contacts', 'value': contacts.count()},
                {'label': 'Active Contacts', 'value': active_contacts},
            ]
        
        elif report_type == 'opportunities':
            opportunities = Opportunity.objects.filter(org=self.org).filter(date_filter)
            won = opportunities.filter(stage='CLOSED WON').count()
            lost = opportunities.filter(stage='CLOSED LOST').count()
            
            metrics = [
                {'label': 'Total Opportunities', 'value': opportunities.count()},
                {'label': 'Won', 'value': won},
                {'label': 'Lost', 'value': lost},
            ]
        
        elif report_type == 'cases':
            cases = Case.objects.filter(org=self.org).filter(date_filter)
            open_cases = cases.filter(status='New').count()
            closed_cases = cases.filter(status='Closed').count()
            
            metrics = [
                {'label': 'Total Cases', 'value': cases.count()},
                {'label': 'New Cases', 'value': open_cases},
                {'label': 'Closed Cases', 'value': closed_cases},
            ]
        
        elif report_type == 'companies':
            companies = Company.objects.filter(org=self.org).filter(date_filter)
            
            # Count leads per company
            total_leads = Lead.objects.filter(
                org=self.org, 
                company__in=companies
            ).count()
            
            metrics = [
                {'label': 'Total Companies', 'value': companies.count()},
                {'label': 'Total Leads (linked to companies)', 'value': total_leads},
            ]
        
        elif report_type == 'activity':
            from common.models import ActivityLog
            activities = ActivityLog.objects.filter(org=self.org).filter(
                Q(created_at__gte=self.date_from, created_at__lte=self.date_to)
            )
            
            # Group by action type
            action_data = activities.values('action').annotate(count=Count('id'))
            
            metrics = [
                {'label': 'Total Activities', 'value': activities.count()},
            ]
            
            # Add counts per action type
            for item in action_data:
                action_label = item['action'].replace('_', ' ').title() if item['action'] else 'Unknown'
                metrics.append({'label': f'{action_label} Actions', 'value': item['count']})
        
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
        
        if not chart_images:
            no_data_style = ParagraphStyle(
                'NoDataStyle',
                parent=self.styles['Normal'],
                fontSize=12,
                textColor=colors.HexColor('#666666'),
                alignment=TA_CENTER,
                spaceBefore=20,
                spaceAfter=20
            )
            elements.append(Paragraph(
                f"No chart data available for the selected period.",
                no_data_style
            ))
            return elements
        
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
        
        labels = chart_data.get('labels', [])
        values = chart_data.get('values', [])
        
        # Check if there's actual data (not just empty or all zeros)
        if not labels or not values or all(v == 0 for v in values):
            return chart_buffers
        
        # Chart 1: Bar chart
        if graphics_config.get('show_bar_chart', True):
            fig, ax = plt.subplots(figsize=(8, 5))
            
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
        if graphics_config.get('show_pie_chart', True) and len(labels) > 0 and sum(values) > 0:
            fig, ax = plt.subplots(figsize=(8, 5))
            
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
        """Get data for charts based on report type and grouping."""
        report_type = self.config.get('report_type', 'leads')
        grouping = self.config.get('grouping', 'status')
        date_filter = Q(created_at__gte=self.date_from, created_at__lte=self.date_to)
        
        # Handle time-based grouping (daily, weekly, monthly)
        if grouping in ['daily', 'weekly', 'monthly']:
            return self._get_time_grouped_chart_data(report_type, grouping, date_filter)
        
        # Handle entity-based grouping
        if report_type == 'leads':
            leads = Lead.objects.filter(org=self.org).filter(date_filter)
            
            if grouping == 'user':
                data = leads.exclude(assigned_to__isnull=True).values(
                    'assigned_to__user__email'
                ).annotate(count=Count('id'))
                return {
                    'title': 'Leads by Assigned User',
                    'distribution_title': 'Lead Assignment Distribution',
                    'labels': [item['assigned_to__user__email'] or 'Unassigned' for item in data],
                    'values': [item['count'] for item in data],
                }
            elif grouping == 'source':
                data = leads.values('source').annotate(count=Count('id'))
                return {
                    'title': 'Leads by Source',
                    'distribution_title': 'Lead Source Distribution',
                    'labels': [item['source'] or 'Unknown' for item in data],
                    'values': [item['count'] for item in data],
                }
            else:  # Default to status
                data = leads.values('status').annotate(count=Count('id'))
                return {
                    'title': 'Leads by Status',
                    'distribution_title': 'Lead Status Distribution',
                    'labels': [item['status'] or 'Unknown' for item in data],
                    'values': [item['count'] for item in data],
                }
        
        elif report_type == 'accounts':
            accounts = Account.objects.filter(org=self.org).filter(date_filter)
            
            if grouping == 'user':
                # Accounts don't have direct user assignment, group by status
                data = accounts.values('status').annotate(count=Count('id'))
                return {
                    'title': 'Accounts by Status',
                    'distribution_title': 'Account Status Distribution',
                    'labels': [item['status'] or 'Unknown' for item in data],
                    'values': [item['count'] for item in data],
                }
            else:  # Default to status
                data = accounts.values('status').annotate(count=Count('id'))
                return {
                    'title': 'Accounts by Status',
                    'distribution_title': 'Account Status Distribution',
                    'labels': [item['status'] or 'Unknown' for item in data],
                    'values': [item['count'] for item in data],
                }
        
        elif report_type == 'contacts':
            contacts = Contact.objects.filter(org=self.org).filter(date_filter)
            active = contacts.filter(is_active=True).count()
            inactive = contacts.filter(is_active=False).count()
            
            return {
                'title': 'Contacts by Status',
                'distribution_title': 'Contact Activity Distribution',
                'labels': ['Active', 'Inactive'],
                'values': [active, inactive],
            }
        
        elif report_type == 'opportunities':
            opportunities = Opportunity.objects.filter(org=self.org).filter(date_filter)
            
            if grouping == 'user':
                # Group by closed_by user
                data = opportunities.exclude(closed_by__isnull=True).values(
                    'closed_by__user__email'
                ).annotate(count=Count('id'))
                return {
                    'title': 'Opportunities by User',
                    'distribution_title': 'Opportunity User Distribution',
                    'labels': [item['closed_by__user__email'] or 'Unassigned' for item in data],
                    'values': [item['count'] for item in data],
                }
            elif grouping == 'source':
                data = opportunities.values('lead_source').annotate(count=Count('id'))
                return {
                    'title': 'Opportunities by Source',
                    'distribution_title': 'Opportunity Source Distribution',
                    'labels': [item['lead_source'] or 'Unknown' for item in data],
                    'values': [item['count'] for item in data],
                }
            else:  # Default to stage (includes 'stage' and 'status' grouping)
                data = opportunities.values('stage').annotate(count=Count('id'))
                return {
                    'title': 'Opportunities by Stage',
                    'distribution_title': 'Opportunity Stage Distribution',
                    'labels': [item['stage'] or 'Unknown' for item in data],
                    'values': [item['count'] for item in data],
                }
        
        elif report_type == 'cases':
            cases = Case.objects.filter(org=self.org).filter(date_filter)
            
            if grouping == 'user':
                # Cases use ManyToMany for assigned_to, so we count differently
                data = cases.values('status').annotate(count=Count('id'))
                return {
                    'title': 'Cases by Status',
                    'distribution_title': 'Case Status Distribution',
                    'labels': [item['status'] or 'Unknown' for item in data],
                    'values': [item['count'] for item in data],
                }
            else:  # Default to status
                data = cases.values('status').annotate(count=Count('id'))
                return {
                    'title': 'Cases by Status',
                    'distribution_title': 'Case Status Distribution',
                    'labels': [item['status'] or 'Unknown' for item in data],
                    'values': [item['count'] for item in data],
                }
        
        elif report_type == 'companies':
            # Get top companies by lead count
            companies = Company.objects.filter(org=self.org).filter(date_filter).annotate(
                lead_count=Count('lead_company')
            ).order_by('-lead_count')[:10]
            
            if companies:
                return {
                    'title': 'Top Companies by Lead Count',
                    'distribution_title': 'Companies Lead Distribution',
                    'labels': [c.name or 'Unnamed' for c in companies],
                    'values': [c.lead_count for c in companies],
                }
            
            return {
                'title': 'Companies Overview',
                'distribution_title': 'Companies',
                'labels': ['Total Companies'],
                'values': [Company.objects.filter(org=self.org).filter(date_filter).count()],
            }
        
        elif report_type == 'activity':
            from common.models import ActivityLog
            activities = ActivityLog.objects.filter(org=self.org).filter(date_filter)
            
            if grouping == 'user':
                data = activities.values('user_email').annotate(count=Count('id'))
                return {
                    'title': 'Activities by User',
                    'distribution_title': 'User Activity Distribution',
                    'labels': [item['user_email'] or 'Unknown' for item in data],
                    'values': [item['count'] for item in data],
                }
            else:
                # Group by action type
                data = activities.values('action').annotate(count=Count('id'))
                
                if data:
                    return {
                        'title': 'Activities by Action Type',
                        'distribution_title': 'Action Type Distribution',
                        'labels': [item['action'].replace('_', ' ').title() if item['action'] else 'Unknown' for item in data],
                        'values': [item['count'] for item in data],
                    }
                
                # If no action data, try entity type
                data = activities.values('entity_type').annotate(count=Count('id'))
                
                return {
                    'title': 'Activities by Entity Type',
                    'distribution_title': 'Entity Type Distribution',
                    'labels': [item['entity_type'].replace('_', ' ').title() if item['entity_type'] else 'Unknown' for item in data],
                    'values': [item['count'] for item in data],
                }
        
        return {}
    
    def _get_time_grouped_chart_data(self, report_type, grouping, date_filter):
        """Get chart data grouped by time periods (daily, weekly, monthly)."""
        
        # Determine truncation function
        if grouping == 'daily':
            trunc_func = TruncDay('created_at')
            date_format = '%Y-%m-%d'
        elif grouping == 'weekly':
            trunc_func = TruncWeek('created_at')
            date_format = 'Week %W'
        else:  # monthly
            trunc_func = TruncMonth('created_at')
            date_format = '%B %Y'
        
        # Get the model based on report type
        model_map = {
            'leads': Lead,
            'accounts': Account,
            'contacts': Contact,
            'opportunities': Opportunity,
            'cases': Case,
            'companies': Company,
        }
        
        if report_type == 'activity':
            from common.models import ActivityLog
            model = ActivityLog
        else:
            model = model_map.get(report_type)
        
        if not model:
            return {}
        
        # Query with time grouping
        data = model.objects.filter(org=self.org).filter(date_filter).annotate(
            period=trunc_func
        ).values('period').annotate(count=Count('id')).order_by('period')
        
        if not data:
            return {}
        
        # Format labels based on grouping type
        labels = []
        values = []
        for item in data:
            if item['period']:
                if grouping == 'weekly':
                    labels.append(item['period'].strftime('Week %W, %Y'))
                else:
                    labels.append(item['period'].strftime(date_format))
                values.append(item['count'])
        
        report_type_label = report_type.replace('_', ' ').title()
        grouping_label = grouping.title()
        
        return {
            'title': f'{report_type_label} ({grouping_label})',
            'distribution_title': f'{report_type_label} {grouping_label} Distribution',
            'labels': labels,
            'values': values,
        }
    
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
        
        if not table_data or not table_data.get('rows'):
            no_data_style = ParagraphStyle(
                'NoDataStyle',
                parent=self.styles['Normal'],
                fontSize=12,
                textColor=colors.HexColor('#666666'),
                alignment=TA_CENTER,
                spaceBefore=20,
                spaceAfter=20
            )
            report_type_label = self.config.get('report_type', 'items').replace('_', ' ').title()
            elements.append(Paragraph(
                f"No {report_type_label} found for the selected period ({self.date_from.strftime('%B %d, %Y')} - {self.date_to.strftime('%B %d, %Y')}).",
                no_data_style
            ))
            return elements
        
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
        report_type = self.config.get('report_type', 'leads')
        date_filter = Q(created_at__gte=self.date_from, created_at__lte=self.date_to)
        
        if report_type == 'leads':
            leads = Lead.objects.filter(org=self.org).filter(date_filter)[:20]
            
            return {
                'headers': ['Title', 'Name', 'Email', 'Status', 'Source', 'Created At'],
                'rows': [
                    [
                        lead.title or '-',
                        f"{lead.first_name or ''} {lead.last_name or ''}".strip() or '-',
                        lead.email or '-',
                        lead.status or '-',
                        lead.source or '-',
                        lead.created_at.strftime('%Y-%m-%d')
                    ]
                    for lead in leads
                ]
            }
        
        elif report_type == 'accounts':
            accounts = Account.objects.filter(org=self.org).filter(date_filter)[:20]
            
            return {
                'headers': ['Name', 'Contact', 'Email', 'Industry', 'Status', 'Created At'],
                'rows': [
                    [
                        account.name,
                        account.contact_name or '-',
                        account.email or '-',
                        account.industry or '-',
                        account.status or '-',
                        account.created_at.strftime('%Y-%m-%d')
                    ]
                    for account in accounts
                ]
            }
        
        elif report_type == 'contacts':
            contacts = Contact.objects.filter(org=self.org).filter(date_filter)[:20]
            
            return {
                'headers': ['Name', 'Organization', 'Email', 'Phone', 'Active', 'Created At'],
                'rows': [
                    [
                        f"{contact.first_name} {contact.last_name or ''}".strip(),
                        contact.organization or '-',
                        contact.primary_email or '-',
                        str(contact.mobile_number) if contact.mobile_number else '-',
                        'Yes' if contact.is_active else 'No',
                        contact.created_at.strftime('%Y-%m-%d')
                    ]
                    for contact in contacts
                ]
            }
        
        elif report_type == 'opportunities':
            opportunities = Opportunity.objects.filter(org=self.org).filter(date_filter).select_related('account')[:20]
            
            return {
                'headers': ['Name', 'Account', 'Stage', 'Amount', 'Probability', 'Created At'],
                'rows': [
                    [
                        opportunity.name,
                        opportunity.account.name if opportunity.account else '-',
                        opportunity.stage or '-',
                        f"€{opportunity.amount:,.2f}" if opportunity.amount else '-',
                        f"{opportunity.probability}%" if opportunity.probability else '-',
                        opportunity.created_at.strftime('%Y-%m-%d')
                    ]
                    for opportunity in opportunities
                ]
            }
        
        elif report_type == 'cases':
            cases = Case.objects.filter(org=self.org).filter(date_filter).select_related('account')[:20]
            
            return {
                'headers': ['Name', 'Account', 'Status', 'Priority', 'Type', 'Created At'],
                'rows': [
                    [
                        case.name,
                        case.account.name if case.account else '-',
                        case.status or '-',
                        case.priority or '-',
                        case.case_type or '-',
                        case.created_at.strftime('%Y-%m-%d')
                    ]
                    for case in cases
                ]
            }
        
        elif report_type == 'companies':
            # Get companies with lead count
            companies = Company.objects.filter(org=self.org).filter(date_filter).annotate(
                lead_count=Count('lead_company')
            ).order_by('-lead_count')[:20]
            
            return {
                'headers': ['Company Name', 'Leads Count', 'Created At'],
                'rows': [
                    [
                        company.name or 'Unnamed Company',
                        str(company.lead_count),
                        company.created_at.strftime('%Y-%m-%d')
                    ]
                    for company in companies
                ]
            }
        
        elif report_type == 'activity':
            from common.models import ActivityLog
            activities = ActivityLog.objects.filter(org=self.org).filter(
                Q(created_at__gte=self.date_from, created_at__lte=self.date_to)
            ).select_related('user')[:30]
            
            return {
                'headers': ['User', 'Action', 'Entity Type', 'Entity Name', 'Date & Time'],
                'rows': [
                    [
                        activity.user_email or (activity.user.email if activity.user else 'Unknown'),
                        activity.action.replace('_', ' ').title() if activity.action else '-',
                        activity.entity_type.replace('_', ' ').title() if activity.entity_type else '-',
                        activity.entity_name[:30] + '...' if activity.entity_name and len(activity.entity_name) > 30 else (activity.entity_name or '-'),
                        activity.created_at.strftime('%Y-%m-%d %H:%M')
                    ]
                    for activity in activities
                ]
            }
        
        return {'headers': [], 'rows': []}
    
    @staticmethod
    def get_report_type_choices():
        """Return report type choices."""
        return [
            ('leads', 'Leads Report'),
            ('accounts', 'Accounts Report'),
            ('contacts', 'Contacts Report'),
            ('opportunities', 'Opportunities Report'),
            ('companies', 'Companies Report'),
            ('activity', 'Activity Logs Report'),
        ]
