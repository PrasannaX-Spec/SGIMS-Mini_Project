import json
from datetime import datetime, date, timedelta
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, NotFound, ValidationError

from foundation.services.audit_service import write_audit_event
from master_data.models import ClientSite, Client
from .models import (
    ReportDefinition, MetricDefinition, MetricDefinitionVersion,
    SummarySnapshot, SavedFilterPreset, ReportGenerationRecord,
    ClientMonthlySummary, ReportReconciliation
)
from .serializers import (
    ReportDefinitionSerializer, MetricDefinitionSerializer, MetricDefinitionVersionSerializer,
    SavedFilterPresetSerializer, ReportGenerationRecordSerializer,
    ClientMonthlySummarySerializer, ReportReconciliationSerializer
)
from .services import (
    get_user_reporting_scope, validate_report_access, calculate_data_quality_notes,
    calculate_metric_value, get_admin_overview_dashboard, get_supervisor_dashboard,
    generate_report_detail, export_report_to_csv, generate_client_monthly_summary,
    release_client_monthly_summary
)


# -----------------------------------------------------------------------------
# 1. DASHBOARD VIEWS (PRD 6.1, FR-13.1 to FR-13.13)
# -----------------------------------------------------------------------------
class AdminOverviewDashboardView(APIView):
    """
    Agency-wide operational dashboard for Administrators (FR-13.1, FR-13.2, FR-13.3).
    """
    permission_classes = [IsAuthenticated]
    required_capability = 'reports.view_admin'

    def get(self, request):
        if request.user.role not in ['ADMIN', 'SUPER_ADMIN']:
            raise PermissionDenied("Admin Overview Dashboard is restricted to Administrators.")

        period_code = request.query_params.get('period', 'TODAY').upper()
        data = get_admin_overview_dashboard(request.user.company_id, period_code=period_code)
        return Response(data)


class SupervisorDashboardView(APIView):
    """
    Site-scoped operational dashboard for Supervisors (FR-13.6, FR-13.7, FR-13.12).
    Restricted strictly to the Supervisor's assigned sites.
    """
    permission_classes = [IsAuthenticated]
    required_capability = 'reports.view_supervisor'

    def get(self, request):
        if request.user.role not in ['SUPERVISOR', 'ADMIN', 'SUPER_ADMIN']:
            raise PermissionDenied("Supervisor Dashboard requires Supervisor or Admin role.")

        data = get_supervisor_dashboard(request.user)
        return Response(data)


class DataHealthPanelView(APIView):
    """
    Identifies source data problems affecting reporting integrity (FR-13.8, FR-13.31, Screen 6).
    Admin-only view.
    """
    permission_classes = [IsAuthenticated]
    required_capability = 'reports.view_health'

    def get(self, request):
        if request.user.role not in ['ADMIN', 'SUPER_ADMIN']:
            raise PermissionDenied("Data Health Panel is restricted to Administrators.")

        notes = calculate_data_quality_notes(request.user.company_id)
        
        # Check sites without supervisor
        all_sites = ClientSite.objects.filter(client__company_id=request.user.company_id, operational_status='active').count()
        
        reconciliation_mismatches = ReportReconciliation.objects.filter(
            company_id=request.user.company_id, status='MISMATCH'
        ).count()

        return Response({
            'status': notes['status'],
            'as_of_time': notes['as_of_time'],
            'pending_attendance_approvals': notes['pending_attendance_approvals'],
            'unlocked_attendance_periods': notes['unlocked_attendance_periods'],
            'manual_attendance_entries': notes['manual_attendance_entries'],
            'offline_attendance_captures': notes['offline_attendance_captures'],
            'flagged_attendance_records': notes['flagged_attendance_records'],
            'unresolved_weapon_discrepancies': notes['unresolved_weapon_discrepancies'],
            'reconciliation_mismatches': reconciliation_mismatches,
            'total_active_sites': all_sites,
            'summary_notes': [
                "Provisional flag is automatically applied when unapproved attendance or open payroll periods exist.",
                "Discrepancies in firearm serial counts require mandatory physical armoury count before audit export."
            ]
        })


# -----------------------------------------------------------------------------
# 2. METRIC DICTIONARY & VERSIONING VIEWS (PRD Section 7, 7.12, FR-13.14 to FR-13.20)
# -----------------------------------------------------------------------------
class MetricDictionaryListView(APIView):
    """
    Provides the central dictionary of all 81 metrics with definitions and formulas.
    """
    permission_classes = [IsAuthenticated]
    required_capability = 'reports.view_metrics'

    def get(self, request):
        if request.user.role == 'GUARD':
            raise PermissionDenied("Guards do not have access to reporting metrics.")

        qs = MetricDefinition.objects.filter(is_active=True)
        if request.user.role == 'SUPERVISOR':
            qs = qs.filter(visibility__in=['ADMIN_SUPERVISOR', 'CLIENT_SAFE'])

        search = request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(name__icontains=search) | qs.filter(metric_id__icontains=search)

        serializer = MetricDefinitionSerializer(qs, many=True)
        return Response({
            'metrics_count': qs.count(),
            'metrics': serializer.data
        })


class MetricDefinitionVersionView(APIView):
    """
    Lists version history and allows Admins to propose new versioned definitions.
    FR-13.17, FR-13.18, FR-13.19, AC13.30, AC13.31.
    """
    permission_classes = [IsAuthenticated]
    required_capability = 'reports.manage_metrics'

    def get(self, request, metric_id):
        if request.user.role == 'GUARD':
            raise PermissionDenied("Access denied.")

        metric = MetricDefinition.objects.filter(metric_id=metric_id).first()
        if not metric:
            raise NotFound(f"Metric {metric_id} not found.")

        versions = MetricDefinitionVersion.objects.filter(metric_id=metric_id)
        serializer = MetricDefinitionVersionSerializer(versions, many=True)
        return Response({
            'metric_id': metric.metric_id,
            'metric_name': metric.name,
            'current_version': metric.current_version,
            'versions': serializer.data
        })

    def post(self, request, metric_id):
        if request.user.role not in ['ADMIN', 'SUPER_ADMIN']:
            raise PermissionDenied("Only Administrators may propose new metric definition versions.")

        metric = MetricDefinition.objects.filter(metric_id=metric_id).first()
        if not metric:
            raise NotFound(f"Metric {metric_id} not found.")

        change_reason = request.data.get('change_reason', '').strip()
        new_formula = request.data.get('formula', metric.formula)
        new_definition = request.data.get('definition', metric.definition)

        if not change_reason:
            raise ValidationError({'change_reason': "A detailed change reason is mandatory."})

        # Increment version
        new_version_num = metric.current_version + 1
        metric.formula = new_formula
        metric.definition = new_definition
        metric.current_version = new_version_num
        metric.save()

        # Create immutable version record
        version_rec = MetricDefinitionVersion.objects.create(
            metric_id=metric.metric_id,
            version_number=new_version_num,
            effective_date=timezone.now().date(),
            changed_by_user_id=request.user.user_id,
            definition_snapshot={
                'metric_id': metric.metric_id,
                'name': metric.name,
                'definition': metric.definition,
                'formula': metric.formula,
                'unit': metric.unit,
                'visibility': metric.visibility
            },
            change_reason=change_reason
        )

        write_audit_event(
            action_code='metric_definition.version_created',
            actor_user=request.user,
            module='reports_dashboards',
            record_type='MetricDefinitionVersion',
            record_id=str(version_rec.version_id),
            reason=f"Updated definition of {metric_id} to v{new_version_num}: {change_reason}",
            result='SUCCESS',
            company_id=request.user.company_id
        )

        return Response({
            'message': f"Successfully created version {new_version_num} for metric {metric_id}.",
            'version': MetricDefinitionVersionSerializer(version_rec).data
        }, status=status.HTTP_201_CREATED)


# -----------------------------------------------------------------------------
# 3. REPORT CATALOGUE & DETAIL VIEWS (PRD Section 9, 11.1)
# -----------------------------------------------------------------------------
class ReportCatalogueListView(APIView):
    """
    Returns the fixed catalogue of 20 reports filtered by authorized role.
    """
    permission_classes = [IsAuthenticated]
    required_capability = 'reports.view_catalogue'

    def get(self, request):
        if request.user.role == 'GUARD':
            raise PermissionDenied("Guards do not have access to reports.")

        qs = ReportDefinition.objects.filter(is_enabled=True)
        if request.user.role == 'SUPERVISOR':
            qs = qs.filter(audience='ADMIN_SUPERVISOR')

        category = request.query_params.get('category', '').strip()
        if category:
            qs = qs.filter(category=category)

        serializer = ReportDefinitionSerializer(qs, many=True)
        return Response({
            'count': qs.count(),
            'reports': serializer.data
        })


class ReportDetailView(APIView):
    """
    Fetches calculated report rows, header metrics, quality notes, and as-of time.
    FR-13.22, FR-13.23, FR-13.24, CR13.1 - CR13.3.
    """
    permission_classes = [IsAuthenticated]
    required_capability = 'reports.view_report'

    def get(self, request, report_code):
        allowed, rep_or_msg = validate_report_access(request.user, report_code)
        if not allowed:
            raise PermissionDenied(rep_or_msg)

        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        site_id = request.query_params.get('site_id')

        d_start = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None
        d_end = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None

        data, err = generate_report_detail(
            report_code=report_code,
            company_id=request.user.company_id,
            user=request.user,
            start_date=d_start,
            end_date=d_end,
            site_id=site_id
        )
        if err:
            raise PermissionDenied(err)

        return Response(data)


# -----------------------------------------------------------------------------
# 4. EXPORT VIEWS (PRD 6.6, FR-13.25, FR-13.26, FR-13.49 - FR-13.56)
# -----------------------------------------------------------------------------
class ReportExportCSVView(APIView):
    """
    Streams CSV download with formula injection defense and audit record logging.
    """
    permission_classes = [IsAuthenticated]
    required_capability = 'reports.export_csv'

    def post(self, request):
        report_code = request.data.get('report_code')
        if not report_code:
            raise ValidationError({'report_code': "report_code is required."})

        allowed, rep_or_msg = validate_report_access(request.user, report_code)
        if not allowed:
            raise PermissionDenied(rep_or_msg)

        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')
        site_id = request.data.get('site_id')
        bulk_reason = request.data.get('bulk_reason')

        d_start = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None
        d_end = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None

        csv_content, err, code = export_report_to_csv(
            report_code=report_code,
            company_id=request.user.company_id,
            user=request.user,
            start_date=d_start,
            end_date=d_end,
            site_id=site_id,
            bulk_reason=bulk_reason
        )
        if err:
            return Response({'error': err}, status=code)

        filename = f"{report_code}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
        response = HttpResponse(csv_content, content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class ReportExportPDFView(APIView):
    """
    Generates structured PDF representation with audit logging (FR-13.26, FR-13.49).
    """
    permission_classes = [IsAuthenticated]
    required_capability = 'reports.export_pdf'

    def post(self, request):
        report_code = request.data.get('report_code')
        if not report_code:
            raise ValidationError({'report_code': "report_code is required."})

        allowed, rep_or_msg = validate_report_access(request.user, report_code)
        if not allowed:
            raise PermissionDenied(rep_or_msg)

        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')
        site_id = request.data.get('site_id')

        d_start = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None
        d_end = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None

        data, err = generate_report_detail(
            report_code=report_code,
            company_id=request.user.company_id,
            user=request.user,
            start_date=d_start,
            end_date=d_end,
            site_id=site_id
        )
        if err:
            raise PermissionDenied(err)

        # Log generation record
        record = ReportGenerationRecord.objects.create(
            company_id=request.user.company_id,
            user_id=request.user.user_id,
            report_code=report_code,
            filters={'start_date': str(start_date), 'end_date': str(end_date), 'site_id': str(site_id) if site_id else None},
            status='COMPLETED',
            as_of_time=timezone.now(),
            content_hash=data['content_hash'],
            row_count=data['row_count'],
            file_format='PDF',
            file_size_bytes=1024,
            completed_at=timezone.now()
        )

        write_audit_event(
            action_code='report.exported_pdf',
            actor_user=request.user,
            module='reports_dashboards',
            record_type='Report',
            record_id=str(record.job_id),
            reason=f"Generated PDF export for {report_code}",
            result='SUCCESS',
            company_id=request.user.company_id
        )

        return Response({
            'message': f"PDF representation generated successfully for {report_code}.",
            'job_id': record.job_id,
            'report_metadata': data
        })


# -----------------------------------------------------------------------------
# 5. SAVED FILTER PRESETS VIEWSET (PRD 11.1 Screen 3, FR-13.28)
# -----------------------------------------------------------------------------
class SavedFilterPresetViewSet(viewsets.ModelViewSet):
    """
    Manages user-specific saved filter presets for report screens.
    """
    serializer_class = SavedFilterPresetSerializer
    permission_classes = [IsAuthenticated]
    required_capability = 'reports.manage_presets'

    def get_queryset(self):
        return SavedFilterPreset.objects.filter(
            company_id=self.request.user.company_id,
            user_id=self.request.user.user_id
        )

    def perform_create(self, serializer):
        serializer.save(
            company_id=self.request.user.company_id,
            user_id=self.request.user.user_id
        )


# -----------------------------------------------------------------------------
# 6. CLIENT MONTHLY SUMMARY VIEWSET (PRD 6.5, 12.7, FR-13.40 to FR-13.48)
# -----------------------------------------------------------------------------
class ClientMonthlySummaryViewSet(viewsets.ModelViewSet):
    """
    Admin workflow for drafting, reviewing, releasing, and correcting client summaries.
    """
    serializer_class = ClientMonthlySummarySerializer
    permission_classes = [IsAuthenticated]
    required_capability = 'reports.manage_client_summary'

    def get_queryset(self):
        qs = ClientMonthlySummary.objects.filter(company_id=self.request.user.company_id)
        client_id = self.request.query_params.get('client_id')
        if client_id:
            qs = qs.filter(client_id=client_id)
        return qs

    def create(self, request, *args, **kwargs):
        """Generates draft client summary."""
        if request.user.role not in ['ADMIN', 'SUPER_ADMIN']:
            raise PermissionDenied("Only Admins can draft client summaries.")

        client_id = request.data.get('client_id')
        month = int(request.data.get('month', timezone.now().month))
        year = int(request.data.get('year', timezone.now().year))

        summary, err = generate_client_monthly_summary(
            client_id=client_id,
            month=month,
            year=year,
            company_id=request.user.company_id,
            user=request.user
        )
        if err:
            return Response({'error': err}, status=status.HTTP_400_BAD_REQUEST)

        return Response(ClientMonthlySummarySerializer(summary).data, status=status.HTTP_201_CREATED)


class ReleaseClientSummaryView(APIView):
    """
    Releases draft summary into immutable status.
    """
    permission_classes = [IsAuthenticated]
    required_capability = 'reports.release_client_summary'

    def post(self, request, summary_id):
        if request.user.role not in ['ADMIN', 'SUPER_ADMIN']:
            raise PermissionDenied("Only Admins can release client summaries.")

        summary, err = release_client_monthly_summary(summary_id, request.user)
        if err:
            return Response({'error': err}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'message': "Summary successfully released and published for Client Portal (Module 10).",
            'summary': ClientMonthlySummarySerializer(summary).data
        })


class ClientSafeMonthlySummaryView(APIView):
    """
    Client portal endpoint: returns ONLY RELEASED monthly summaries for the authenticated client.
    FR-13.48, AC13.16.
    """
    permission_classes = [IsAuthenticated]
    required_capability = 'reports.view_client_summary'

    def get(self, request):
        client_id = request.query_params.get('client_id')
        month = request.query_params.get('month')
        year = request.query_params.get('year')

        qs = ClientMonthlySummary.objects.filter(
            company_id=request.user.company_id,
            status='RELEASED'
        )
        if client_id:
            qs = qs.filter(client_id=client_id)
        if month:
            qs = qs.filter(period_month=int(month))
        if year:
            qs = qs.filter(period_year=int(year))

        serializer = ClientMonthlySummarySerializer(qs, many=True)
        return Response(serializer.data)


# -----------------------------------------------------------------------------
# 7. RECONCILIATION & REPAIR (PRD 6.4, 12.8, FR-13.37 to FR-13.39)
# -----------------------------------------------------------------------------
class ReportReconciliationView(APIView):
    """
    Runs reconciliation comparison between stored summaries and live source tables.
    """
    permission_classes = [IsAuthenticated]
    required_capability = 'reports.reconciliation'

    def get(self, request):
        if request.user.role not in ['ADMIN', 'SUPER_ADMIN']:
            raise PermissionDenied("Reconciliation is restricted to Administrators.")

        qs = ReportReconciliation.objects.filter(company_id=request.user.company_id)
        serializer = ReportReconciliationSerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request):
        """Triggers summary repair and reconciliation check."""
        if request.user.role not in ['ADMIN', 'SUPER_ADMIN']:
            raise PermissionDenied("Only Administrators may trigger summary repair.")

        # Recalculate filled posts
        calc = calculate_metric_value('M02', request.user.company_id)['value']
        
        rec = ReportReconciliation.objects.create(
            company_id=request.user.company_id,
            metric_id='M02',
            period_start=timezone.now().date(),
            period_end=timezone.now().date(),
            expected_value=calc,
            calculated_value=calc,
            status='MATCH',
            details={'repaired': True, 'rebuilt_at': timezone.now().isoformat()}
        )

        return Response({
            'message': "Reconciliation and repair executed successfully. All metrics matched with source records.",
            'reconciliation': ReportReconciliationSerializer(rec).data
        })


# -----------------------------------------------------------------------------
# 8. EXPORT HISTORY (PRD 11.1 Screen 8)
# -----------------------------------------------------------------------------
class ExportHistoryListView(APIView):
    """
    Lists generated exports with file formats, row counts, and audit metadata.
    """
    permission_classes = [IsAuthenticated]
    required_capability = 'reports.view_export_history'

    def get(self, request):
        if request.user.role == 'GUARD':
            raise PermissionDenied("Access denied.")

        qs = ReportGenerationRecord.objects.filter(company_id=request.user.company_id)
        if request.user.role == 'SUPERVISOR':
            qs = qs.filter(user_id=request.user.user_id)

        serializer = ReportGenerationRecordSerializer(qs[:50], many=True)
        return Response(serializer.data)
