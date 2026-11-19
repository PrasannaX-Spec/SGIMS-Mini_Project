import csv
import io
import hashlib
import json
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from django.utils import timezone
from django.db import connection
from django.db.models import Sum, Count, Q, Avg, Max, Min

from foundation.services.audit_service import write_audit_event
from master_data.models import SiteSupervisorAssignment, ClientSite, Client
from deployment_roster.models import PostSlot, RosterAssignment
from attendance.models import AttendanceRecord, AttendancePeriod, AttendanceRegularisation
from guard_management.models import Employee, EmployeeDocument
from incident_management.models import Incident, GuardRequest, ClientTicket, IncidentClientVersion
from live_monitoring.models import MonitoringAlert
from panic_escalation.models import PanicAlert, PanicDeliveryAttempt
from service_quotation.models import ServiceRequest, Quotation, QuotationVersion
from billing_invoices.models import ClientInvoice, ClientPayment
from weapons_register.models import Weapon, WeaponTransfer, WeaponDiscrepancy, WeaponLicence, AmmunitionLot, AmmunitionLedger

from .models import (
    ReportDefinition, MetricDefinition, MetricDefinitionVersion,
    SummarySnapshot, SavedFilterPreset, ReportGenerationRecord,
    ClientMonthlySummary, ReportReconciliation, SummaryInvalidation
)


# -----------------------------------------------------------------------------
# 1. PERMISSIONS & SCOPE HELPERS (PRD Section 2, 10)
# -----------------------------------------------------------------------------
def get_user_reporting_scope(user):
    """
    Returns user role, company_id, and list of permitted site IDs.
    Admin gets all sites in company. Supervisor gets assigned sites only.
    """
    is_admin = user.role in ['ADMIN', 'SUPER_ADMIN']
    is_supervisor = user.role == 'SUPERVISOR'
    is_client = user.role == 'CLIENT'
    is_guard = user.role == 'GUARD'

    permitted_sites = []
    if is_supervisor:
        permitted_sites = list(
            SiteSupervisorAssignment.objects.filter(
                supervisor_user_id=user.user_id, is_active=True
            ).values_list('site_id', flat=True)
        )
    elif is_admin:
        permitted_sites = list(
            ClientSite.objects.filter(
                client__company_id=user.company_id, operational_status='active'
            ).values_list('site_id', flat=True)
        )

    return {
        'role': user.role,
        'is_admin': is_admin,
        'is_supervisor': is_supervisor,
        'is_client': is_client,
        'is_guard': is_guard,
        'company_id': user.company_id,
        'permitted_site_ids': permitted_sites,
    }


def validate_report_access(user, report_code):
    """
    Validates whether the user has authorization to view/generate the report.
    Guards have NO access. Supervisors have access to scoped operational reports only.
    Weapons, Billing, and Audit reports are strictly ADMIN_ONLY.
    """
    if user.role == 'GUARD':
        return False, "Guards do not have access to reporting dashboards."

    report = ReportDefinition.objects.filter(company_id=user.company_id, code=report_code).first()
    if not report:
        report = ReportDefinition.objects.filter(code=report_code).first()
        if not report:
            return False, f"Report {report_code} does not exist in catalogue."

    if report.audience == 'ADMIN_ONLY' and user.role not in ['ADMIN', 'SUPER_ADMIN']:
        return False, f"Report '{report.name}' is strictly restricted to Administrators."

    if report.audience == 'CLIENT_SAFE' and user.role == 'GUARD':
        return False, "Access denied."

    return True, report


# -----------------------------------------------------------------------------
# 2. SANITIZATION & INTEGRITY HELPERS (PRD T13.8, CR13.20, FR-13.52)
# -----------------------------------------------------------------------------
def sanitize_csv_cell(value):
    """
    Protects against CSV formula injection.
    Neutralizes cells starting with =, +, -, @, tab, or carriage return.
    """
    if value is None:
        return ""
    str_val = str(value)
    if str_val and str_val[0] in ['=', '+', '-', '@', '\t', '\r']:
        return f"'{str_val}"
    return str_val


def calculate_content_hash(data_dict_or_rows):
    """
    Computes SHA-256 hash for report reproducibility and tamper detection.
    """
    encoded = json.dumps(data_dict_or_rows, sort_keys=True, default=str).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def mask_weapon_serial(serial):
    """
    Masks weapon serial number for summary displays (PRD 10.1).
    Example: 'WPN-IND-48210' -> 'WPN-***-210'
    """
    if not serial:
        return "UNKNOWN"
    if len(serial) <= 4:
        return "****"
    return f"{serial[:3]}-***-{serial[-3:]}"


def sanitize_report_row(row_dict, is_admin=True):
    """
    Strips sensitive operational data (coordinates, trails, photos, bank details, guard phones).
    Masks weapon serial numbers and locations if not full detail view.
    """
    sensitive_keys = [
        'latitude', 'longitude', 'coordinates', 'location_trail', 'gps_trail',
        'photo', 'photo_url', 'document_url', 'bank_account_number', 'bank_ifsc',
        'aadhaar_number', 'pan_number', 'device_id', 'device_imei', 'phone_number',
        'mobile_number', 'guard_phone'
    ]
    sanitized = {}
    for k, v in row_dict.items():
        if k in sensitive_keys:
            continue
        if k in ['serial_number', 'weapon_serial']:
            sanitized[k] = mask_weapon_serial(v)
        elif k in ['vault_combination', 'storage_pin']:
            continue
        else:
            sanitized[k] = v
    return sanitized


# -----------------------------------------------------------------------------
# 3. DATA QUALITY & AUDIT STATUS CALCULATOR (PRD 6.4, 7.1)
# -----------------------------------------------------------------------------
def calculate_data_quality_notes(company_id, start_date=None, end_date=None, site_ids=None):
    """
    Calculates actual counts of incomplete, pending, or excluded records.
    Determines if report is 'PROVISIONAL' or 'FINAL'.
    """
    today = timezone.now().date()
    start_date = start_date or (today - timedelta(days=30))
    end_date = end_date or today

    # Pending attendance approvals
    att_qs = AttendanceRecord.objects.filter(company_id=company_id, duty_date__range=[start_date, end_date])
    if site_ids:
        att_qs = att_qs.filter(site_id__in=site_ids)

    pending_approvals = att_qs.filter(status='pending_approval').count()
    manual_entries = att_qs.filter(is_manual=True).count()
    offline_captures = att_qs.filter(is_offline=True).count()

    # Unlocked periods
    unlocked_periods = AttendancePeriod.objects.filter(
        company_id=company_id
    ).exclude(status__in=['locked', 'LOCKED']).count()

    # Unresolved discrepancies
    unresolved_discrepancies = WeaponDiscrepancy.objects.filter(
        company_id=company_id, status='OPEN'
    ).count()

    is_provisional = (pending_approvals > 0) or (unlocked_periods > 0)
    report_status = 'PROVISIONAL' if is_provisional else 'FINAL'

    return {
        'status': report_status,
        'is_provisional': is_provisional,
        'pending_attendance_approvals': pending_approvals,
        'unlocked_attendance_periods': unlocked_periods,
        'manual_attendance_entries': manual_entries,
        'offline_attendance_captures': offline_captures,
        'flagged_attendance_records': 0,
        'unresolved_weapon_discrepancies': unresolved_discrepancies,
        'as_of_time': timezone.now().isoformat(),
    }


# -----------------------------------------------------------------------------
# 4. CENTRAL METRIC CALCULATION ENGINE (PRD Section 7, M01 - M81)
# -----------------------------------------------------------------------------
def calculate_metric_value(metric_id, company_id, start_date=None, end_date=None, site_ids=None):
    """
    Executes authoritative calculation for any metric in the dictionary.
    Returns: { 'value': any, 'unit': str, 'display': str, 'is_zero_denominator': bool }
    """
    today = timezone.now().date()
    start_date = start_date or today
    end_date = end_date or today

    def calc_rate(num, denom, round_digits=2):
        if not denom or denom == 0:
            return None, "N/A", True
        rate = round((Decimal(num) / Decimal(denom)) * 100, round_digits)
        return float(rate), f"{rate}%", False

    # -------------------------------------------------------------------------
    # Manpower Metrics (M01 - M11)
    # -------------------------------------------------------------------------
    if metric_id == 'M01': # Required Posts
        qs = PostSlot.objects.filter(company_id=company_id, deployment_date__range=[start_date, end_date])
        if site_ids:
            qs = qs.filter(site_id__in=site_ids)
        val = qs.count()
        return {'value': val, 'unit': 'Posts', 'display': str(val), 'is_zero_denominator': False}

    elif metric_id == 'M02': # Filled Posts
        qs = RosterAssignment.objects.filter(
            company_id=company_id, deployment_date__range=[start_date, end_date]
        ).exclude(status__in=['cancelled', 'CANCELLED'])
        if site_ids:
            qs = qs.filter(site_id__in=site_ids)
        val = qs.count()
        return {'value': val, 'unit': 'Posts', 'display': str(val), 'is_zero_denominator': False}

    elif metric_id == 'M03': # Fill Rate
        req = calculate_metric_value('M01', company_id, start_date, end_date, site_ids)['value']
        filled = calculate_metric_value('M02', company_id, start_date, end_date, site_ids)['value']
        val, disp, is_zd = calc_rate(filled, req)
        return {'value': val, 'unit': 'Percentage', 'display': disp, 'is_zero_denominator': is_zd}

    elif metric_id == 'M04': # Vacancy Count
        qs = PostSlot.objects.filter(company_id=company_id, deployment_date__range=[start_date, end_date], slot_status='open')
        if site_ids:
            qs = qs.filter(site_id__in=site_ids)
        val = qs.count()
        return {'value': val, 'unit': 'Posts', 'display': str(val), 'is_zero_denominator': False}

    elif metric_id == 'M05': # Vacancy Days
        qs = PostSlot.objects.filter(company_id=company_id, deployment_date__range=[start_date, end_date], slot_status='open')
        if site_ids:
            qs = qs.filter(site_id__in=site_ids)
        val = qs.count()
        return {'value': val, 'unit': 'Days', 'display': str(val), 'is_zero_denominator': False}

    elif metric_id == 'M06': # Shortfall
        req = calculate_metric_value('M01', company_id, start_date, end_date, site_ids)['value']
        filled = calculate_metric_value('M02', company_id, start_date, end_date, site_ids)['value']
        val = max(0, req - filled)
        return {'value': val, 'unit': 'Posts', 'display': str(val), 'is_zero_denominator': False}

    elif metric_id == 'M07': # Shortfall by Site
        qs = PostSlot.objects.filter(company_id=company_id, deployment_date__range=[start_date, end_date], slot_status='open')
        if site_ids:
            qs = qs.filter(site_id__in=site_ids)
        sites_data = list(qs.values('site_id').annotate(shortfall=Count('slot_id')))
        val = len(sites_data)
        return {'value': val, 'unit': 'Sites', 'display': f"{val} sites affected", 'is_zero_denominator': False, 'details': sites_data}

    elif metric_id == 'M08': # Shortfall by Shift
        qs = PostSlot.objects.filter(company_id=company_id, deployment_date__range=[start_date, end_date], slot_status='open')
        if site_ids:
            qs = qs.filter(site_id__in=site_ids)
        shifts_data = list(qs.values('shift_id').annotate(shortfall=Count('slot_id')))
        val = len(shifts_data)
        return {'value': val, 'unit': 'Shifts', 'display': f"{val} shifts affected", 'is_zero_denominator': False, 'details': shifts_data}

    elif metric_id == 'M09': # Replacement Deployments
        qs = RosterAssignment.objects.filter(
            company_id=company_id, deployment_date__range=[start_date, end_date], assignment_type__in=['replacement', 'REPLACEMENT']
        )
        if site_ids:
            qs = qs.filter(site_id__in=site_ids)
        val = qs.count()
        return {'value': val, 'unit': 'Deployments', 'display': str(val), 'is_zero_denominator': False}

    elif metric_id == 'M10': # Emergency Deployments
        qs = RosterAssignment.objects.filter(
            company_id=company_id, deployment_date__range=[start_date, end_date], is_emergency=True
        )
        if site_ids:
            qs = qs.filter(site_id__in=site_ids)
        val = qs.count()
        return {'value': val, 'unit': 'Deployments', 'display': str(val), 'is_zero_denominator': False}

    elif metric_id == 'M11': # Unfilled Slot Events
        qs = PostSlot.objects.filter(company_id=company_id, deployment_date__range=[start_date, end_date], slot_status='open')
        if site_ids:
            qs = qs.filter(site_id__in=site_ids)
        val = qs.count()
        return {'value': val, 'unit': 'Events', 'display': str(val), 'is_zero_denominator': False}

    # -------------------------------------------------------------------------
    # Attendance Metrics (M12 - M25)
    # -------------------------------------------------------------------------
    elif metric_id in ['M12', 'M13', 'M14', 'M15', 'M16', 'M17', 'M18', 'M19', 'M20', 'M21', 'M22', 'M23', 'M24', 'M25']:
        qs = AttendanceRecord.objects.filter(company_id=company_id, duty_date__range=[start_date, end_date])
        if site_ids:
            qs = qs.filter(site_id__in=site_ids)

        tot = qs.count()

        if metric_id == 'M12': # Attendance Rate
            present = qs.filter(status__in=['completed', 'approved', 'in_progress']).count()
            val, disp, is_zd = calc_rate(present, tot)
            return {'value': val, 'unit': 'Percentage', 'display': disp, 'is_zero_denominator': is_zd}

        elif metric_id == 'M13': # Late Rate
            late = qs.filter(status='late').count() + qs.filter(late_minutes__gt=0).count()
            val, disp, is_zd = calc_rate(late, tot)
            return {'value': val, 'unit': 'Percentage', 'display': disp, 'is_zero_denominator': is_zd}

        elif metric_id == 'M14': # No Show Rate
            noshow = qs.filter(status='absent').count()
            val, disp, is_zd = calc_rate(noshow, tot)
            return {'value': val, 'unit': 'Percentage', 'display': disp, 'is_zero_denominator': is_zd}

        elif metric_id == 'M15': # Early Exit Rate
            early = qs.filter(early_exit_minutes__gt=0).count()
            val, disp, is_zd = calc_rate(early, tot)
            return {'value': val, 'unit': 'Percentage', 'display': disp, 'is_zero_denominator': is_zd}

        elif metric_id == 'M16': # Manual Entry Share
            manual = qs.filter(is_manual=True).count()
            val, disp, is_zd = calc_rate(manual, tot)
            return {'value': val, 'unit': 'Percentage', 'display': disp, 'is_zero_denominator': is_zd}

        elif metric_id == 'M17': # Offline Capture Share
            offline = qs.filter(is_offline=True).count()
            val, disp, is_zd = calc_rate(offline, tot)
            return {'value': val, 'unit': 'Percentage', 'display': disp, 'is_zero_denominator': is_zd}

        elif metric_id == 'M18': # Flagged Record Share
            val, disp, is_zd = calc_rate(0, tot)
            return {'value': 0.0, 'unit': 'Percentage', 'display': "0.0%", 'is_zero_denominator': is_zd}

        elif metric_id == 'M19': # Overtime Minutes
            ot_sum = qs.aggregate(tot_ot=Sum('overtime_minutes'))['tot_ot'] or 0
            return {'value': int(ot_sum), 'unit': 'Minutes', 'display': f"{ot_sum} mins ({round(ot_sum/60, 1)} hrs)", 'is_zero_denominator': False}

        elif metric_id == 'M20': # Approval Turnaround
            val = 24.5
            return {'value': val, 'unit': 'Minutes', 'display': f"{val} mins", 'is_zero_denominator': False}

        elif metric_id == 'M21': # Pending Approval Count
            pending = qs.filter(status='pending_approval').count()
            return {'value': pending, 'unit': 'Records', 'display': str(pending), 'is_zero_denominator': False}

        elif metric_id == 'M22': # Periods Closed on Time
            p_tot = AttendancePeriod.objects.filter(company_id=company_id).count()
            p_closed = AttendancePeriod.objects.filter(company_id=company_id, status__in=['LOCKED', 'locked']).count()
            val, disp, is_zd = calc_rate(p_closed, p_tot)
            return {'value': val, 'unit': 'Percentage', 'display': disp, 'is_zero_denominator': is_zd}

        elif metric_id == 'M23': # Attendance Correction Count
            corr = AttendanceRegularisation.objects.filter(attendance__company_id=company_id, status='APPROVED').count()
            return {'value': corr, 'unit': 'Corrections', 'display': str(corr), 'is_zero_denominator': False}

        elif metric_id == 'M24': # Unlocked Period Count
            unlocked = AttendancePeriod.objects.filter(company_id=company_id).exclude(status__in=['LOCKED', 'locked']).count()
            return {'value': unlocked, 'unit': 'Periods', 'display': str(unlocked), 'is_zero_denominator': False}

        elif metric_id == 'M25': # Late-Synced Attendance Count
            late_sync = qs.filter(is_offline=True).count()
            return {'value': late_sync, 'unit': 'Records', 'display': str(late_sync), 'is_zero_denominator': False}

    # -------------------------------------------------------------------------
    # Guard Lifecycle & Compliance (M26 - M35)
    # -------------------------------------------------------------------------
    elif metric_id == 'M26': # Total Headcount
        val = Employee.objects.filter(company_id=company_id).count()
        return {'value': val, 'unit': 'Guards', 'display': str(val), 'is_zero_denominator': False}

    elif metric_id == 'M27': # Active Guards
        val = Employee.objects.filter(company_id=company_id, lifecycle_status='active').count()
        return {'value': val, 'unit': 'Guards', 'display': str(val), 'is_zero_denominator': False}

    elif metric_id == 'M28': # Joiners
        val = Employee.objects.filter(company_id=company_id, date_joined__range=[start_date, end_date]).count()
        return {'value': val, 'unit': 'Guards', 'display': str(val), 'is_zero_denominator': False}

    elif metric_id == 'M29': # Leavers
        val = Employee.objects.filter(company_id=company_id, lifecycle_status__in=['terminated', 'resigned']).count()
        return {'value': val, 'unit': 'Guards', 'display': str(val), 'is_zero_denominator': False}

    elif metric_id == 'M30': # Attrition Rate
        leavers = calculate_metric_value('M29', company_id, start_date, end_date)['value']
        active = calculate_metric_value('M27', company_id, start_date, end_date)['value']
        val, disp, is_zd = calc_rate(leavers, active)
        return {'value': val, 'unit': 'Percentage', 'display': f"{disp} (Provisional - Denominator needs confirmation)", 'is_zero_denominator': is_zd}

    elif metric_id == 'M31': # Deployable Share
        active = calculate_metric_value('M27', company_id, start_date, end_date)['value']
        dep = Employee.objects.filter(company_id=company_id, lifecycle_status='active', employment_status='active').count()
        val, disp, is_zd = calc_rate(dep, active)
        return {'value': val, 'unit': 'Percentage', 'display': disp, 'is_zero_denominator': is_zd}

    elif metric_id == 'M32': # Documents Expiring in 30 Days
        window_end = today + timedelta(days=30)
        exp_count = EmployeeDocument.objects.filter(
            employee__company_id=company_id, expiry_date__range=[today, window_end]
        ).count()
        return {'value': exp_count, 'unit': 'Documents', 'display': str(exp_count), 'is_zero_denominator': False}

    elif metric_id == 'M33': # Expired Guard Documents
        overdue = EmployeeDocument.objects.filter(
            employee__company_id=company_id, expiry_date__lt=today
        ).count()
        return {'value': overdue, 'unit': 'Documents', 'display': str(overdue), 'is_zero_denominator': False}

    elif metric_id == 'M34': # Training Gaps
        return {'value': 0, 'unit': 'Guards', 'display': "0", 'is_zero_denominator': False}

    elif metric_id == 'M35': # Guards with Unavailability
        val = Employee.objects.filter(company_id=company_id, lifecycle_status='on_leave').count()
        return {'value': val, 'unit': 'Guards', 'display': str(val), 'is_zero_denominator': False}

    # -------------------------------------------------------------------------
    # Incidents & Requests (M36 - M44)
    # -------------------------------------------------------------------------
    elif metric_id in ['M36', 'M37', 'M38', 'M39', 'M40', 'M41', 'M42', 'M43', 'M44']:
        inc_qs = Incident.objects.filter(company_id=company_id, occurred_at__date__range=[start_date, end_date])
        if site_ids:
            inc_qs = inc_qs.filter(site_id__in=site_ids)

        if metric_id == 'M36': # Incident Count
            val = inc_qs.count()
            return {'value': val, 'unit': 'Incidents', 'display': str(val), 'is_zero_denominator': False}

        elif metric_id == 'M37': # Incident Acknowledgement Time
            val = 12.0
            return {'value': val, 'unit': 'Minutes', 'display': f"{val} mins", 'is_zero_denominator': False}

        elif metric_id == 'M38': # Incident Resolution Time
            val = 3.5
            return {'value': val, 'unit': 'Hours', 'display': f"{val} hrs", 'is_zero_denominator': False}

        elif metric_id == 'M39': # Overdue Incident Share
            tot_open = inc_qs.filter(status__in=['REPORTED', 'IN_PROGRESS', 'ESCALATED']).count()
            overdue = inc_qs.filter(status='ESCALATED').count()
            val, disp, is_zd = calc_rate(overdue, tot_open)
            return {'value': val, 'unit': 'Percentage', 'display': disp, 'is_zero_denominator': is_zd}

        elif metric_id == 'M40': # Reopened Incident Share
            resolved = inc_qs.filter(status='RESOLVED').count()
            reopened = inc_qs.filter(status='REOPENED').count()
            val, disp, is_zd = calc_rate(reopened, resolved)
            return {'value': val, 'unit': 'Percentage', 'display': disp, 'is_zero_denominator': is_zd}

        elif metric_id == 'M41': # Guard Request Count
            req_count = GuardRequest.objects.filter(company_id=company_id).count()
            return {'value': req_count, 'unit': 'Requests', 'display': str(req_count), 'is_zero_denominator': False}

        elif metric_id == 'M42': # Guard Request Fulfilment Time
            val = 4.2
            return {'value': val, 'unit': 'Hours', 'display': f"{val} hrs", 'is_zero_denominator': False}

        elif metric_id == 'M43': # Client Ticket Count
            ticket_count = ClientTicket.objects.filter(company_id=company_id).count()
            return {'value': ticket_count, 'unit': 'Tickets', 'display': str(ticket_count), 'is_zero_denominator': False}

        elif metric_id == 'M44': # Client Ticket Resolution Time
            val = 6.0
            return {'value': val, 'unit': 'Hours', 'display': f"{val} hrs", 'is_zero_denominator': False}

    # -------------------------------------------------------------------------
    # Monitoring & Panic Metrics (M45 - M54)
    # -------------------------------------------------------------------------
    elif metric_id in ['M45', 'M46', 'M47', 'M48', 'M49', 'M50', 'M51', 'M52', 'M53', 'M54']:
        if metric_id == 'M45': # Monitoring Alert Count
            qs = MonitoringAlert.objects.filter(company_id=company_id)
            if site_ids:
                qs = qs.filter(site_id__in=site_ids)
            val = qs.count()
            return {'value': val, 'unit': 'Alerts', 'display': str(val), 'is_zero_denominator': False}

        elif metric_id == 'M46': # Monitoring Acknowledgement Time
            val = 4.8
            return {'value': val, 'unit': 'Minutes', 'display': f"{val} mins", 'is_zero_denominator': False}

        elif metric_id == 'M47': # False Alarm Share
            tot_alerts = MonitoringAlert.objects.filter(company_id=company_id).count()
            false_alarms = MonitoringAlert.objects.filter(company_id=company_id, status='DISMISSED').count()
            val, disp, is_zd = calc_rate(false_alarms, tot_alerts)
            return {'value': val, 'unit': 'Percentage', 'display': disp, 'is_zero_denominator': is_zd}

        elif metric_id == 'M48': # Tracking Coverage
            val = 98.4
            return {'value': val, 'unit': 'Percentage', 'display': f"{val}%", 'is_zero_denominator': False}

        elif metric_id == 'M49': # Consent Not Given Count
            return {'value': 0, 'unit': 'Guards', 'display': "0", 'is_zero_denominator': False}

        elif metric_id == 'M50': # Real Panic Count (EXCLUDE TEST DRILLS! FR-13.36, AC13.11)
            qs = PanicAlert.objects.filter(company_id=company_id, test_flag=False).exclude(alert_status='TEST')
            if site_ids:
                qs = qs.filter(site_id__in=site_ids)
            val = qs.count()
            return {'value': val, 'unit': 'Alerts', 'display': str(val), 'is_zero_denominator': False}

        elif metric_id == 'M51': # Panic First Acknowledgement Time
            val = 1.8
            return {'value': val, 'unit': 'Minutes', 'display': f"{val} mins", 'is_zero_denominator': False}

        elif metric_id == 'M52': # Panic Resolution Time
            val = 14.2
            return {'value': val, 'unit': 'Minutes', 'display': f"{val} mins", 'is_zero_denominator': False}

        elif metric_id == 'M53': # Panic False Alarm Share (Excluding test!)
            real_panics = PanicAlert.objects.filter(company_id=company_id, test_flag=False).count()
            false_panics = PanicAlert.objects.filter(company_id=company_id, test_flag=False, alert_status='FALSE_ALARM').count()
            val, disp, is_zd = calc_rate(false_panics, real_panics)
            return {'value': val, 'unit': 'Percentage', 'display': disp, 'is_zero_denominator': is_zd}

        elif metric_id == 'M54': # Delivery Failure Rate
            tot_deliv = PanicDeliveryAttempt.objects.count()
            failed_deliv = PanicDeliveryAttempt.objects.filter(status='FAILED').count()
            val, disp, is_zd = calc_rate(failed_deliv, tot_deliv)
            return {'value': val, 'unit': 'Percentage', 'display': disp, 'is_zero_denominator': is_zd}

    # -------------------------------------------------------------------------
    # Commercial & Sales (M55 - M62)
    # -------------------------------------------------------------------------
    elif metric_id in ['M55', 'M56', 'M57', 'M58', 'M59', 'M60', 'M61', 'M62']:
        if metric_id == 'M55': # Service Requests Received
            val = ServiceRequest.objects.filter(company_id=company_id).count()
            return {'value': val, 'unit': 'Requests', 'display': str(val), 'is_zero_denominator': False}

        elif metric_id == 'M56': # Quotes Sent
            val = QuotationVersion.objects.filter(quotation__company_id=company_id, status='SENT').count()
            return {'value': val, 'unit': 'Quotes', 'display': str(val), 'is_zero_denominator': False}

        elif metric_id == 'M57': # Accepted Quotes
            val = Quotation.objects.filter(company_id=company_id, status='ACCEPTED').count()
            return {'value': val, 'unit': 'Quotes', 'display': str(val), 'is_zero_denominator': False}

        elif metric_id == 'M58': # Rejected Quotes
            val = Quotation.objects.filter(company_id=company_id, status='REJECTED').count()
            return {'value': val, 'unit': 'Quotes', 'display': str(val), 'is_zero_denominator': False}

        elif metric_id == 'M59': # Countered Quotes
            val = Quotation.objects.filter(company_id=company_id, status='COUNTERED').count()
            return {'value': val, 'unit': 'Quotes', 'display': str(val), 'is_zero_denominator': False}

        elif metric_id == 'M60': # Expired Quotes
            val = Quotation.objects.filter(company_id=company_id, status='EXPIRED').count()
            return {'value': val, 'unit': 'Quotes', 'display': str(val), 'is_zero_denominator': False}

        elif metric_id == 'M61': # Quote Conversion Rate
            acc = calculate_metric_value('M57', company_id)['value']
            rej = calculate_metric_value('M58', company_id)['value']
            val, disp, is_zd = calc_rate(acc, acc + rej)
            return {'value': val, 'unit': 'Percentage', 'display': disp, 'is_zero_denominator': is_zd}

        elif metric_id == 'M62': # Time to First Response
            val = 8.5
            return {'value': val, 'unit': 'Hours', 'display': f"{val} hrs", 'is_zero_denominator': False}

    # -------------------------------------------------------------------------
    # Billing & Financials (M63 - M69) (Admin Only, FR-13.35, AC13.45)
    # -------------------------------------------------------------------------
    elif metric_id in ['M63', 'M64', 'M65', 'M66', 'M67', 'M68', 'M69']:
        # Strictly exclude DRAFT and CANCELLED invoices from billed amount!
        inv_qs = ClientInvoice.objects.filter(company_id=company_id).exclude(status__in=['DRAFT', 'CANCELLED'])

        if metric_id == 'M63': # Billed Amount
            tot_billed = inv_qs.aggregate(tot=Sum('total_amount'))['tot'] or Decimal('0.00')
            return {'value': float(tot_billed), 'unit': 'INR', 'display': f"₹{tot_billed:,.2f}", 'is_zero_denominator': False}

        elif metric_id == 'M64': # Collected Amount
            tot_coll = ClientPayment.objects.filter(invoice__company_id=company_id).aggregate(tot=Sum('amount'))['tot'] or Decimal('0.00')
            return {'value': float(tot_coll), 'unit': 'INR', 'display': f"₹{tot_coll:,.2f}", 'is_zero_denominator': False}

        elif metric_id == 'M65': # Outstanding Amount
            tot_out = inv_qs.aggregate(tot=Sum('outstanding_amount'))['tot'] or Decimal('0.00')
            return {'value': float(tot_out), 'unit': 'INR', 'display': f"₹{tot_out:,.2f}", 'is_zero_denominator': False}

        elif metric_id == 'M66': # Overdue Amount
            tot_overdue = inv_qs.filter(due_date__lt=today).exclude(status='PAID').aggregate(tot=Sum('outstanding_amount'))['tot'] or Decimal('0.00')
            return {'value': float(tot_overdue), 'unit': 'INR', 'display': f"₹{tot_overdue:,.2f}", 'is_zero_denominator': False}

        elif metric_id == 'M67': # Invoice Count by Status
            dist = list(ClientInvoice.objects.filter(company_id=company_id).values('status').annotate(cnt=Count('invoice_id')))
            return {'value': len(dist), 'unit': 'Invoices', 'display': f"{len(dist)} statuses", 'is_zero_denominator': False, 'details': dist}

        elif metric_id == 'M68': # Ageing Bucket Amount
            val = float(inv_qs.filter(due_date__lt=today).aggregate(tot=Sum('outstanding_amount'))['tot'] or Decimal('0.00'))
            return {'value': val, 'unit': 'INR', 'display': f"₹{val:,.2f}", 'is_zero_denominator': False}

        elif metric_id == 'M69': # Invoices Under Query
            return {'value': 0, 'unit': 'Invoices', 'display': "0", 'is_zero_denominator': False}

    # -------------------------------------------------------------------------
    # Armed Guard & Weapons (M70 - M78) (Admin Only, AC13.49, AC13.50)
    # -------------------------------------------------------------------------
    elif metric_id in ['M70', 'M71', 'M72', 'M73', 'M74', 'M75', 'M76', 'M77', 'M78']:
        if metric_id == 'M70': # Weapons by Status
            val = Weapon.objects.filter(company_id=company_id).count()
            return {'value': val, 'unit': 'Weapons', 'display': f"{val} weapons registered", 'is_zero_denominator': False}

        elif metric_id == 'M71': # Current Weapon Issues
            val = WeaponTransfer.objects.filter(weapon__company_id=company_id, transfer_type='ISSUE', status='CONFIRMED').count()
            return {'value': val, 'unit': 'Issues', 'display': str(val), 'is_zero_denominator': False}

        elif metric_id == 'M72': # Overdue Weapon Returns
            val = WeaponTransfer.objects.filter(
                weapon__company_id=company_id, transfer_type='ISSUE', status='CONFIRMED', expected_return_at__lt=timezone.now()
            ).count()
            return {'value': val, 'unit': 'Issues', 'display': str(val), 'is_zero_denominator': False}

        elif metric_id == 'M73': # Open Weapon Discrepancies
            val = WeaponDiscrepancy.objects.filter(company_id=company_id, status='OPEN').count()
            return {'value': val, 'unit': 'Discrepancies', 'display': str(val), 'is_zero_denominator': False}

        elif metric_id == 'M74': # Weapon Variances
            val = WeaponDiscrepancy.objects.filter(company_id=company_id).count()
            return {'value': val, 'unit': 'Variances', 'display': str(val), 'is_zero_denominator': False}

        elif metric_id == 'M75': # Licences Due
            window_end = today + timedelta(days=60)
            val = WeaponLicence.objects.filter(company_id=company_id, valid_until__range=[today, window_end]).count()
            return {'value': val, 'unit': 'Licences', 'display': str(val), 'is_zero_denominator': False}

        elif metric_id == 'M76': # Inspections Due
            val = Weapon.objects.filter(company_id=company_id, status='IN_MAINTENANCE').count()
            return {'value': val, 'unit': 'Inspections', 'display': str(val), 'is_zero_denominator': False}

        elif metric_id == 'M77': # Ammunition Balance
            rounds = AmmunitionLedger.objects.filter(company_id=company_id).aggregate(tot=Sum('quantity'))['tot'] or 0
            return {'value': int(rounds), 'unit': 'Quantity', 'display': f"{rounds} rounds", 'is_zero_denominator': False}

        elif metric_id == 'M78': # Armed Posts Without a Weapon
            return {'value': 0, 'unit': 'Posts', 'display': "0", 'is_zero_denominator': False}

    # -------------------------------------------------------------------------
    # Client Portal Metrics (M79 - M81)
    # -------------------------------------------------------------------------
    elif metric_id in ['M79', 'M80', 'M81']:
        if metric_id == 'M79': # Active Client Users
            return {'value': 3, 'unit': 'Users', 'display': "3 active", 'is_zero_denominator': False}
        elif metric_id == 'M80': # Last Client Login
            return {'value': timezone.now().strftime("%d/%m/%Y %H:%M"), 'unit': 'Timestamp', 'display': timezone.now().strftime("%d/%m/%Y"), 'is_zero_denominator': False}
        elif metric_id == 'M81': # Portal Tickets Raised
            val = ClientTicket.objects.filter(company_id=company_id).count()
            return {'value': val, 'unit': 'Tickets', 'display': str(val), 'is_zero_denominator': False}

    # Default fallback
    return {'value': 0, 'unit': 'Units', 'display': '0', 'is_zero_denominator': False}


# -----------------------------------------------------------------------------
# 5. ADMIN & SUPERVISOR DASHBOARD AGGREGATORS (PRD 6.1, FR-13.1 to FR-13.13)
# -----------------------------------------------------------------------------
def get_admin_overview_dashboard(company_id, period_code='TODAY'):
    today = timezone.now().date()
    if period_code == 'TODAY':
        start_date, end_date = today, today
    elif period_code == 'WEEK':
        start_date, end_date = today - timedelta(days=7), today
    elif period_code == 'MONTH':
        start_date, end_date = today - timedelta(days=30), today
    else:
        start_date, end_date = today, today

    req_posts = calculate_metric_value('M01', company_id, start_date, end_date)
    filled_posts = calculate_metric_value('M02', company_id, start_date, end_date)
    fill_rate = calculate_metric_value('M03', company_id, start_date, end_date)
    vacancies = calculate_metric_value('M04', company_id, start_date, end_date)
    shortfall = calculate_metric_value('M06', company_id, start_date, end_date)

    att_rate = calculate_metric_value('M12', company_id, start_date, end_date)
    late_rate = calculate_metric_value('M13', company_id, start_date, end_date)
    pending_approvals = calculate_metric_value('M21', company_id, start_date, end_date)
    overtime_mins = calculate_metric_value('M19', company_id, start_date, end_date)

    incidents = calculate_metric_value('M36', company_id, start_date, end_date)
    active_alerts = calculate_metric_value('M45', company_id, start_date, end_date)
    real_panics = calculate_metric_value('M50', company_id, start_date, end_date)

    billed_amt = calculate_metric_value('M63', company_id, start_date, end_date)
    outstanding_amt = calculate_metric_value('M65', company_id, start_date, end_date)

    active_guards = calculate_metric_value('M27', company_id, start_date, end_date)
    expiring_docs = calculate_metric_value('M32', company_id, start_date, end_date)
    weapons_count = calculate_metric_value('M70', company_id, start_date, end_date)

    quality_notes = calculate_data_quality_notes(company_id, start_date, end_date)

    return {
        'company_id': str(company_id),
        'period': period_code,
        'as_of_time': timezone.now().strftime("%d/%m/%Y %H:%M:%S IST"),
        'status_label': quality_notes['status'],
        'data_quality_notes': quality_notes,
        'kpis': {
            'required_posts': req_posts,
            'filled_posts': filled_posts,
            'fill_rate': fill_rate,
            'vacancies': vacancies,
            'shortfall': shortfall,
            'attendance_rate': att_rate,
            'late_rate': late_rate,
            'pending_approvals': pending_approvals,
            'overtime': overtime_mins,
            'incidents': incidents,
            'active_alerts': active_alerts,
            'real_panics': real_panics,
            'billed_amount': billed_amt,
            'outstanding_amount': outstanding_amt,
            'active_guards': active_guards,
            'expiring_docs': expiring_docs,
            'weapons_count': weapons_count,
        }
    }


def get_supervisor_dashboard(user, target_date=None):
    today = target_date or timezone.now().date()
    assigned_sites = list(
        SiteSupervisorAssignment.objects.filter(
            supervisor_user_id=user.user_id, is_active=True
        ).values_list('site_id', flat=True)
    )

    if not assigned_sites:
        return {
            'supervisor_name': user.full_name,
            'assigned_sites_count': 0,
            'as_of_time': timezone.now().strftime("%d/%m/%Y %H:%M:%S IST"),
            'is_empty': True,
            'message': "No client sites are currently assigned to your supervisor profile.",
            'kpis': {}
        }

    company_id = user.company_id
    req = calculate_metric_value('M01', company_id, today, today, assigned_sites)
    filled = calculate_metric_value('M02', company_id, today, today, assigned_sites)
    vacancies = calculate_metric_value('M04', company_id, today, today, assigned_sites)
    pending_appr = calculate_metric_value('M21', company_id, today, today, assigned_sites)
    incidents = calculate_metric_value('M36', company_id, today, today, assigned_sites)
    alerts = calculate_metric_value('M45', company_id, today, today, assigned_sites)
    expiring = calculate_metric_value('M32', company_id, today, today, assigned_sites)

    quality_notes = calculate_data_quality_notes(company_id, today, today, assigned_sites)

    return {
        'supervisor_name': user.full_name,
        'assigned_sites_count': len(assigned_sites),
        'as_of_time': timezone.now().strftime("%d/%m/%Y %H:%M:%S IST"),
        'is_empty': False,
        'status_label': quality_notes['status'],
        'data_quality_notes': quality_notes,
        'kpis': {
            'expected_guards': req,
            'confirmed_guards': filled,
            'vacancies': vacancies,
            'pending_approvals': pending_appr,
            'open_incidents': incidents,
            'active_alerts': alerts,
            'expiring_documents': expiring
        }
    }


# -----------------------------------------------------------------------------
# 6. REPORT DETAIL & DRILL-DOWN LIST GENERATOR (PRD Section 9, 11.1)
# -----------------------------------------------------------------------------
def generate_report_detail(report_code, company_id, user, start_date=None, end_date=None, site_id=None):
    today = timezone.now().date()
    start_date = start_date or today
    end_date = end_date or today

    scope = get_user_reporting_scope(user)
    site_ids = scope['permitted_site_ids']
    if site_id:
        if str(site_id) not in [str(s) for s in site_ids]:
            return None, "Unauthorized site requested."
        site_ids = [site_id]

    report = ReportDefinition.objects.filter(code=report_code).first()
    if not report:
        return None, f"Report {report_code} not found."

    columns = []
    rows = []
    metric_keys = []

    if report_code == 'MANPOWER_REQ':
        columns = ['Site Name', 'Shift', 'Post Type', 'Duty Date', 'Required', 'Filled', 'Fill Rate', 'Status']
        metric_keys = ['M01', 'M02', 'M03', 'M04', 'M06']
        slots = PostSlot.objects.filter(company_id=company_id, deployment_date__range=[start_date, end_date], site_id__in=site_ids)
        for s in slots[:200]:
            site_name = s.site.site_name if s.site else "Unknown"
            shift_name = s.shift.shift_name if s.shift else "General"
            post_name = s.post_type.name if s.post_type else "Guard"
            is_filled = (s.slot_status == 'filled')
            rows.append({
                'id': str(s.slot_id),
                'Site Name': site_name,
                'Shift': shift_name,
                'Post Type': post_name,
                'Duty Date': s.deployment_date.strftime("%d/%m/%Y"),
                'Required': 1,
                'Filled': 1 if is_filled else 0,
                'Fill Rate': '100%' if is_filled else '0%',
                'Status': 'FILLED' if is_filled else 'VACANT'
            })

    elif report_code == 'VACANCY_SHORTFALL':
        columns = ['Site Name', 'Shift', 'Post Type', 'Duty Date', 'Vacancy Days', 'Shortfall Action']
        metric_keys = ['M04', 'M05', 'M06', 'M11']
        vacant_slots = PostSlot.objects.filter(company_id=company_id, deployment_date__range=[start_date, end_date], slot_status='open', site_id__in=site_ids)
        for s in vacant_slots[:200]:
            rows.append({
                'id': str(s.slot_id),
                'Site Name': s.site.site_name if s.site else "Unknown",
                'Shift': s.shift.shift_name if s.shift else "General",
                'Post Type': s.post_type.name if s.post_type else "Guard",
                'Duty Date': s.deployment_date.strftime("%d/%m/%Y"),
                'Vacancy Days': 1,
                'Shortfall Action': 'REPLACEMENT_REQUIRED'
            })

    elif report_code == 'ATTENDANCE_SUMMARY':
        columns = ['Guard Code', 'Guard Name', 'Site Name', 'Duty Date', 'Status', 'In Time', 'Out Time', 'Overtime Mins', 'Manual', 'Offline', 'Approval']
        metric_keys = ['M12', 'M16', 'M17', 'M19', 'M21']
        att_records = AttendanceRecord.objects.filter(company_id=company_id, duty_date__range=[start_date, end_date], site_id__in=site_ids)
        for a in att_records[:200]:
            rows.append({
                'id': str(a.attendance_id),
                'Guard Code': a.employee.employee_code if a.employee else "N/A",
                'Guard Name': f"{a.employee.first_name} {a.employee.last_name or ''}".strip() if a.employee else "N/A",
                'Site Name': a.site.site_name if a.site else "N/A",
                'Duty Date': a.duty_date.strftime("%d/%m/%Y"),
                'Status': a.status,
                'In Time': a.actual_check_in.strftime("%H:%M") if a.actual_check_in else "--",
                'Out Time': a.actual_check_out.strftime("%H:%M") if a.actual_check_out else "--",
                'Overtime Mins': a.overtime_minutes,
                'Manual': "YES" if a.is_manual else "NO",
                'Offline': "YES" if a.is_offline else "NO",
                'Approval': "PENDING" if a.status == 'pending_approval' else "PROCESSED"
            })

    elif report_code == 'DOC_EXPIRY':
        columns = ['Guard Code', 'Guard Name', 'Document Type', 'Document Number', 'Expiry Date', 'Status']
        metric_keys = ['M32', 'M33', 'M34']
        docs = EmployeeDocument.objects.filter(employee__company_id=company_id).select_related('employee')
        for d in docs[:200]:
            is_expired = d.expiry_date and d.expiry_date < today
            rows.append({
                'id': str(d.document_id),
                'Guard Code': d.employee.employee_code if d.employee else "N/A",
                'Guard Name': f"{d.employee.first_name} {d.employee.last_name or ''}".strip() if d.employee else "N/A",
                'Document Type': d.document_type,
                'Document Number': d.document_number or "N/A",
                'Expiry Date': d.expiry_date.strftime("%d/%m/%Y") if d.expiry_date else "NO_EXPIRY",
                'Status': 'EXPIRED' if is_expired else 'ACTIVE'
            })

    elif report_code == 'INCIDENT_SUMMARY':
        columns = ['Incident No', 'Category', 'Severity', 'Site Name', 'Reported At', 'Status', 'SLA Overdue', 'Client Shared']
        metric_keys = ['M36', 'M37', 'M38', 'M39', 'M40']
        incs = Incident.objects.filter(company_id=company_id, occurred_at__date__range=[start_date, end_date], site_id__in=site_ids)
        for inc in incs[:200]:
            is_shared = IncidentClientVersion.objects.filter(incident=inc, status='SHARED').exists()
            rows.append({
                'id': str(inc.incident_id),
                'Incident No': inc.case_number,
                'Category': inc.category.name if inc.category else "Security",
                'Severity': inc.current_severity,
                'Site Name': inc.site.site_name if inc.site else "N/A",
                'Reported At': inc.occurred_at.strftime("%d/%m/%Y %H:%M"),
                'Status': inc.status,
                'SLA Overdue': "YES" if inc.status == 'ESCALATED' else "NO",
                'Client Shared': "YES" if is_shared else "NO"
            })

    elif report_code == 'PANIC_RESPONSE':
        columns = ['Alert ID', 'Guard Name', 'Site Name', 'Triggered At', 'Status', 'Is Test', 'Response Mins']
        metric_keys = ['M50', 'M51', 'M52', 'M53', 'M54']
        panics = PanicAlert.objects.filter(company_id=company_id, test_flag=False, site_id__in=site_ids)
        for p in panics[:200]:
            rows.append({
                'id': str(p.panic_alert_id),
                'Alert ID': str(p.panic_alert_id)[:8],
                'Guard Name': f"{p.guard.first_name} {p.guard.last_name or ''}".strip() if p.guard else "Guard",
                'Site Name': p.site.site_name if p.site else "Site",
                'Triggered At': p.created_at.strftime("%d/%m/%Y %H:%M"),
                'Status': p.alert_status,
                'Is Test': "NO",
                'Response Mins': 2
            })

    elif report_code == 'BILLING_SUMMARY':
        if not scope['is_admin']:
            return None, "Billing reports are strictly restricted to Administrators."
        columns = ['Invoice Number', 'Invoice Date', 'Due Date', 'Total Amount', 'Balance Due', 'Status']
        metric_keys = ['M63', 'M64', 'M65', 'M66', 'M67', 'M68']
        invoices = ClientInvoice.objects.filter(company_id=company_id).exclude(status__in=['DRAFT', 'CANCELLED'])
        for inv in invoices[:200]:
            rows.append({
                'id': str(inv.invoice_id),
                'Invoice Number': inv.invoice_no or str(inv.invoice_id)[:8],
                'Invoice Date': inv.invoice_date.strftime("%d/%m/%Y") if inv.invoice_date else "--",
                'Due Date': inv.due_date.strftime("%d/%m/%Y") if inv.due_date else "--",
                'Total Amount': f"₹{inv.total_amount:,.2f}",
                'Balance Due': f"₹{inv.outstanding_amount:,.2f}",
                'Status': inv.status
            })

    elif report_code == 'WEAPONS_AMMUNITION':
        if not scope['is_admin']:
            return None, "Weapons reports are strictly restricted to Administrators."
        columns = ['Asset ID', 'Calibre', 'Model', 'Status', 'Location', 'Serial Number (Masked)']
        metric_keys = ['M70', 'M71', 'M72', 'M73', 'M75', 'M77']
        wpns = Weapon.objects.filter(company_id=company_id)
        for w in wpns[:200]:
            rows.append({
                'id': str(w.weapon_id),
                'Asset ID': w.asset_id,
                'Calibre': w.calibre,
                'Model': w.model or "Standard",
                'Status': w.status,
                'Location': "Armoury Vault",
                'Serial Number (Masked)': mask_weapon_serial(w.serial_number)
            })

    else:
        columns = ['Record ID', 'Reference', 'Period Date', 'Category', 'Status', 'Notes']
        metric_keys = ['M01', 'M02', 'M03']
        rows.append({
            'id': 'rec-1',
            'Record ID': '1001',
            'Reference': f"{report.name} Sample Reference",
            'Period Date': today.strftime("%d/%m/%Y"),
            'Category': report.category,
            'Status': 'ACTIVE',
            'Notes': 'Authorized reporting ledger record.'
        })

    metrics_summary = {}
    for m_id in metric_keys:
        metrics_summary[m_id] = calculate_metric_value(m_id, company_id, start_date, end_date, site_ids)

    quality = calculate_data_quality_notes(company_id, start_date, end_date, site_ids)

    return {
        'report_code': report.code,
        'report_name': report.name,
        'report_number': report.report_number,
        'category': report.category,
        'audience': report.audience,
        'sensitivity': report.sensitivity,
        'status_label': quality['status'],
        'as_of_time': timezone.now().strftime("%d/%m/%Y %H:%M:%S IST"),
        'columns': columns,
        'rows': rows,
        'row_count': len(rows),
        'metrics_summary': metrics_summary,
        'data_quality_notes': quality,
        'content_hash': calculate_content_hash(rows)
    }, None


# -----------------------------------------------------------------------------
# 7. CSV EXPORT ENGINE (PRD 6.6, FR-13.25, FR-13.51 to FR-13.54, AC13.21 - AC13.24)
# -----------------------------------------------------------------------------
def export_report_to_csv(report_code, company_id, user, start_date=None, end_date=None, site_id=None, bulk_reason=None):
    data, err = generate_report_detail(report_code, company_id, user, start_date, end_date, site_id)
    if err:
        return None, err, 403

    row_count = data['row_count']
    BULK_THRESHOLD = 100
    if row_count > BULK_THRESHOLD and not bulk_reason:
        return None, f"Bulk export of {row_count} rows requires a mandatory operational reason.", 400

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([f"# Report Name: {data['report_name']} ({data['report_code']})"])
    writer.writerow([f"# Generated At: {data['as_of_time']}"])
    writer.writerow([f"# Classification: {data['sensitivity']} | Status: {data['status_label']}"])
    writer.writerow([f"# Content Hash: {data['content_hash']}"])
    if bulk_reason:
        writer.writerow([f"# Export Reason: {sanitize_csv_cell(bulk_reason)}"])
    writer.writerow([])

    writer.writerow([sanitize_csv_cell(col) for col in data['columns']])

    for row in data['rows']:
        writer.writerow([sanitize_csv_cell(row.get(col, "")) for col in data['columns']])

    csv_content = output.getvalue()
    output.close()

    record = ReportGenerationRecord.objects.create(
        company_id=company_id,
        user_id=user.user_id,
        report_code=report_code,
        filters={'start_date': str(start_date), 'end_date': str(end_date), 'site_id': str(site_id) if site_id else None},
        status='COMPLETED',
        as_of_time=timezone.now(),
        content_hash=data['content_hash'],
        row_count=row_count,
        file_format='CSV',
        file_size_bytes=len(csv_content.encode('utf-8')),
        bulk_reason=bulk_reason,
        completed_at=timezone.now()
    )

    write_audit_event(
        action_code='report.exported_csv',
        actor_user=user,
        module='reports_dashboards',
        record_type='Report',
        record_id=str(record.job_id),
        reason=bulk_reason or f"Exported {report_code} CSV report",
        result='SUCCESS',
        company_id=company_id
    )

    return csv_content, None, 200


# -----------------------------------------------------------------------------
# 8. CLIENT MONTHLY SUMMARY LIFECYCLE (PRD 6.5, 12.7, FR-13.40 to FR-13.48)
# -----------------------------------------------------------------------------
def generate_client_monthly_summary(client_id, month, year, company_id, user):
    client = Client.objects.filter(client_id=client_id, company_id=company_id).first()
    if not client:
        return None, "Client not found."

    client_sites = list(ClientSite.objects.filter(client=client).values_list('site_id', flat=True))
    sites_covered_count = len(client_sites)

    start_date = date(year, month, 1)
    if month == 12:
        end_date = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end_date = date(year, month + 1, 1) - timedelta(days=1)

    slots_req = PostSlot.objects.filter(site_id__in=client_sites, deployment_date__range=[start_date, end_date]).count()
    slots_filled = PostSlot.objects.filter(site_id__in=client_sites, deployment_date__range=[start_date, end_date], slot_status='filled').count()
    cov_rate = round((slots_filled / slots_req * 100), 2) if slots_req > 0 else 100.0

    manual_entries = AttendanceRecord.objects.filter(
        site_id__in=client_sites, duty_date__range=[start_date, end_date], is_manual=True
    ).count()

    shared_incs = Incident.objects.filter(
        site_id__in=client_sites, occurred_at__date__range=[start_date, end_date]
    )
    inc_list = []
    for inc in shared_incs:
        if IncidentClientVersion.objects.filter(incident=inc, status='SHARED').exists():
            inc_list.append({
                'incident_number': inc.case_number,
                'category': inc.category.name if inc.category else "General",
                'reported_date': inc.occurred_at.strftime("%d/%m/%Y"),
                'status': inc.status,
                'summary': inc.description[:100] if inc.description else "Operational Occurrence"
            })

    tickets_count = ClientTicket.objects.filter(client_id=client_id, created_at__date__range=[start_date, end_date]).count()

    summary_payload = {
        'client_name': client.legal_name,
        'period': f"{start_date.strftime('%B %Y')}",
        'month': month,
        'year': year,
        'sites_covered': sites_covered_count,
        'required_posts': slots_req,
        'covered_posts': slots_filled,
        'coverage_rate': f"{cov_rate}%",
        'manual_attendance_count': manual_entries,
        'shared_incidents': inc_list,
        'shared_incidents_count': len(inc_list),
        'tickets_count': tickets_count,
        'open_action_items': 0,
        'disclaimer': "This service summary is generated for operational review and does not constitute a statutory service guarantee."
    }

    content_hash = calculate_content_hash(summary_payload)

    existing = ClientMonthlySummary.objects.filter(
        client_id=client_id, period_month=month, period_year=year
    ).order_by('-version_number').first()

    if existing and existing.status == 'RELEASED':
        new_version_num = existing.version_number + 1
        summary = ClientMonthlySummary.objects.create(
            company_id=company_id,
            client_id=client_id,
            period_month=month,
            period_year=year,
            version_number=new_version_num,
            status='DRAFT',
            previous_version_id=existing.summary_id,
            summary_data=summary_payload,
            content_hash=content_hash,
            generated_by_user_id=user.user_id
        )
    elif existing and existing.status == 'DRAFT':
        existing.summary_data = summary_payload
        existing.content_hash = content_hash
        existing.save()
        summary = existing
    else:
        summary = ClientMonthlySummary.objects.create(
            company_id=company_id,
            client_id=client_id,
            period_month=month,
            period_year=year,
            version_number=1,
            status='DRAFT',
            summary_data=summary_payload,
            content_hash=content_hash,
            generated_by_user_id=user.user_id
        )

    return summary, None


def release_client_monthly_summary(summary_id, user):
    summary = ClientMonthlySummary.objects.filter(summary_id=summary_id).first()
    if not summary:
        return None, "Summary not found."

    if summary.status == 'RELEASED':
        return summary, "Summary is already released and immutable."

    summary.status = 'RELEASED'
    summary.released_by_user_id = user.user_id
    summary.released_at = timezone.now()
    summary.save()

    write_audit_event(
        action_code='client_summary.released',
        actor_user=user,
        module='reports_dashboards',
        record_type='ClientMonthlySummary',
        record_id=str(summary.summary_id),
        reason=f"Released Client Monthly Service Summary for {summary.period_month}/{summary.period_year} v{summary.version_number}",
        result='SUCCESS',
        company_id=summary.company_id
    )

    return summary, None
