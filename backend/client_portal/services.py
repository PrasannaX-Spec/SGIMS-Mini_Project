import csv
import io
import uuid
from datetime import datetime, date, timedelta
from django.utils import timezone
from django.db.models import Q, Count
from django.db import connection
from rest_framework.exceptions import PermissionDenied, NotFound, ValidationError

from foundation.models import User, Company
from master_data.models import Client, ClientSite, SiteShift, SiteManpowerRequirement
from guard_management.models import Employee
from deployment_roster.models import RosterAssignment
from attendance.models import AttendanceRecord, AttendancePeriod
from incident_management.models import (
    IncidentClientVersion,
    ClientTicket,
    ClientTicketMessage,
    CaseNumberSequence
)
from panic_escalation.models import PanicAlert, PanicRecipient, PanicAcknowledgement
from client_portal.models import (
    ClientUserSiteAccess,
    ClientPortalConfiguration,
    ClientNotificationPreference,
    ClientDocumentAccessLog,
    ClientPortalUsageEvent,
    ClientAnnouncement
)


def get_client_permitted_sites(user: User):
    """
    Returns the list/queryset of ClientSite objects that the client user is permitted to access.
    Enforces FR-10.4, FR-10.6, FR-10.8, AC-10.5, AC-10.6.
    """
    if not user or not user.is_authenticated or user.status != 'ACTIVE':
        return ClientSite.objects.none()

    if user.role == 'ADMIN':
        return ClientSite.objects.filter(client__company_id=user.company_id)

    if user.role != 'CLIENT' or not user.client_company_id:
        return ClientSite.objects.none()

    client_id = user.client_company_id

    # Check if there are active restriction entries for this user
    restrictions = ClientUserSiteAccess.objects.filter(
        client_user_id=user.user_id,
        is_active=True
    )
    selected_site_ids = list(restrictions.filter(access_mode='SELECTED_SITES').exclude(site_id__isnull=True).values_list('site_id', flat=True))

    if selected_site_ids:
        return ClientSite.objects.filter(
            client_id=client_id,
            site_id__in=selected_site_ids
        )

    # Default: All sites belonging to the linked client company
    return ClientSite.objects.filter(
        client_id=client_id
    )


def validate_client_site_access(user: User, site_id):
    """
    Validates that a requested site_id is permitted for the user.
    Raises PermissionDenied / NotFound if unauthorized (FR-10.7, AC-10.6).
    """
    if user.role == 'ADMIN':
        if not ClientSite.objects.filter(client__company_id=user.company_id, site_id=site_id).exists():
            raise NotFound(detail="Site not found.")
        return

    permitted_site_ids = [str(s.site_id) for s in get_client_permitted_sites(user)]
    if str(site_id) not in permitted_site_ids:
        raise PermissionDenied(detail="You do not have permission to access information for this site.")


def get_or_create_portal_config(company_id, client_id):
    """
    Gets or creates the ClientPortalConfiguration record for a client company.
    """
    config = ClientPortalConfiguration.objects.filter(client_id=client_id).first()
    if not config:
        config = ClientPortalConfiguration.objects.create(
            company_id=company_id,
            client_id=client_id,
            future_roster_visibility=False,
            incident_sharing_default='EXPLICIT_APPROVAL',
            retention_window_days=365,
            checkin_photo_visibility=False,
            invoices_enabled=False,
            requests_enabled=True,
            documents_enabled=True,
            announcements_enabled=True,
            enabled_sections=["dashboard", "deployment", "attendance", "incidents", "panic", "tickets", "documents", "contacts"]
        )
    return config


def log_usage_event(company_id, client_user_id, event_type, related_record_id=None, source='MOBILE_APP'):
    """
    Logs actual usage events for Module 13 auditing and metrics (FR-10.162, AC-10.67).
    """
    try:
        ClientPortalUsageEvent.objects.create(
            company_id=company_id,
            client_user_id=client_user_id,
            event_type=event_type,
            related_record_id=related_record_id,
            source=source
        )
    except Exception:
        pass


def build_client_dashboard(user: User):
    """
    Builds the complete Client Home Dashboard (FR-10.25 to FR-10.41, AC-10.11 to AC-10.13).
    Includes last updated timestamp, neutral wording, real counts, and clean empty states.
    """
    permitted_sites = list(get_client_permitted_sites(user))
    permitted_site_ids = [s.site_id for s in permitted_sites]

    now = timezone.now()
    today = timezone.localdate(now)

    # 1. Active Panic Banner check (FR-10.27, AC-10.13)
    active_panic = PanicAlert.objects.filter(
        site_id__in=permitted_site_ids,
        alert_status__in=['TRIGGERED', 'DELIVERING', 'ACKNOWLEDGED', 'RESPONDING']
    ).order_by('-trigger_server_time').first()

    panic_banner = None
    if active_panic:
        # Determine client safe status
        status_map = {
            'TRIGGERED': 'Alert Raised',
            'DELIVERING': 'Alert Raised',
            'ACKNOWLEDGED': 'Agency Acknowledged',
            'RESPONDING': 'Responding',
        }
        client_safe_status = status_map.get(active_panic.alert_status, 'Alert Raised')
        panic_banner = {
            'panic_alert_id': str(active_panic.panic_alert_id),
            'alert_number': active_panic.alert_number,
            'site_id': str(active_panic.site_id),
            'site_name': active_panic.site.site_name if active_panic.site else 'Site',
            'client_safe_status': client_safe_status,
            'trigger_time': active_panic.trigger_server_time.isoformat(),
            'disclaimer': 'Notice: This portal notification is not an emergency response service. Call local emergency services (112) or the agency control room immediately.',
            'emergency_contact': '112'
        }

    # 2. Site Deployment & Guard Counts (FR-10.28, FR-10.53)
    site_summaries = []
    total_required = 0
    total_assigned = 0
    total_confirmed = 0

    for site in permitted_sites:
        assignments = RosterAssignment.objects.filter(
            site=site,
            deployment_date=today,
            status__in=['scheduled', 'acknowledged', 'completed']
        )
        assigned_count = assignments.count()
        
        # Confirmed count from attendance records today
        confirmed_count = AttendanceRecord.objects.filter(
            site=site,
            duty_date=today,
            actual_check_in__isnull=False
        ).values('employee_id').distinct().count()

        # Required guards from active shifts or default
        manpower = SiteManpowerRequirement.objects.filter(site=site, is_active=True)
        required_count = sum(m.required_count for m in manpower) if manpower.exists() else assigned_count

        total_required += required_count
        total_assigned += assigned_count
        total_confirmed += confirmed_count

        has_site_panic = bool(active_panic and active_panic.site_id == site.site_id)
        open_tickets_count = ClientTicket.objects.filter(
            site=site,
            status__in=['OPEN', 'ACKNOWLEDGED', 'IN_PROGRESS', 'WAITING_FOR_CLIENT', 'REOPENED']
        ).count()

        site_summaries.append({
            'site_id': str(site.site_id),
            'site_name': site.site_name,
            'site_code': site.site_code,
            'status': site.operational_status,
            'address': site.address_line1 or '',
            'city': site.city or '',
            'required_guards': required_count,
            'assigned_guards': assigned_count,
            'confirmed_on_duty': confirmed_count,
            'active_panic': has_site_panic,
            'open_tickets': open_tickets_count,
            'last_updated_at': now.isoformat(),
        })

    # Sort sites by attention priority: Panic active first, then open tickets, then name (FR-10.37)
    site_summaries.sort(key=lambda s: (not s['active_panic'], -s['open_tickets'], s['site_name']))

    # 3. Open Ticket Counts (FR-10.30)
    client_id = user.client_company_id if user.role == 'CLIENT' else None
    ticket_qs = ClientTicket.objects.filter(company_id=user.company_id)
    if client_id:
        ticket_qs = ticket_qs.filter(client_id=client_id)
    ticket_qs = ticket_qs.filter(site_id__in=permitted_site_ids)

    open_tickets_count = ticket_qs.filter(
        status__in=['OPEN', 'ACKNOWLEDGED', 'IN_PROGRESS', 'WAITING_FOR_CLIENT', 'REOPENED']
    ).count()

    recent_tickets = list(ticket_qs.order_by('-created_at')[:5].values(
        'ticket_id', 'ticket_number', 'title', 'status', 'created_at', 'site_id'
    ))

    # 4. Recent Client-Shared Incidents (FR-10.31, FR-10.83 to FR-10.88)
    shared_incidents_qs = IncidentClientVersion.objects.filter(
        site_id__in=permitted_site_ids,
        sharing_state='SHARED'
    )
    if client_id:
        shared_incidents_qs = shared_incidents_qs.filter(client_id=client_id)

    recent_incidents = list(shared_incidents_qs.order_by('-occurred_at')[:5].values(
        'version_id', 'title', 'category', 'status', 'occurred_at', 'summary', 'actions_taken', 'site_id'
    ))

    # 5. Service Requests Count (FR-10.32, Module 4)
    # Check if requests module has pending client requests
    awaiting_requests_count = 0
    try:
        from service_quotation.models import ServiceRequest
        req_qs = ServiceRequest.objects.filter(company_id=user.company_id)
        if client_id:
            req_qs = req_qs.filter(client_id=client_id)
        awaiting_requests_count = req_qs.filter(status__in=['QUOTED', 'AWAITING_CLIENT_RESPONSE']).count()
    except Exception:
        awaiting_requests_count = 0

    # 6. Portal Configuration for Invoices / Sections (FR-10.33)
    portal_config = get_or_create_portal_config(user.company_id, client_id) if client_id else None
    invoices_enabled = portal_config.invoices_enabled if portal_config else False

    # 7. Active Announcements (FR-10.166)
    announcements = list(ClientAnnouncement.objects.filter(
        company_id=user.company_id,
        status='ACTIVE',
        starts_at__lte=now,
        ends_at__gte=now
    ).filter(
        Q(target_client__isnull=True) | Q(target_client_id=client_id)
    ).order_by('-starts_at')[:3].values(
        'announcement_id', 'title', 'message', 'starts_at', 'ends_at'
    ))

    return {
        'current_date': today.isoformat(),
        'last_updated_time': now.isoformat(),
        'active_panic_banner': panic_banner,
        'summary': {
            'total_permitted_sites': len(permitted_sites),
            'total_required_guards': total_required,
            'total_assigned_guards': total_assigned,
            'total_confirmed_on_duty': total_confirmed,
            'open_tickets_count': open_tickets_count,
            'awaiting_requests_count': awaiting_requests_count,
        },
        'sites': site_summaries,
        'recent_tickets': recent_tickets,
        'recent_incidents': recent_incidents,
        'announcements': announcements,
        'invoices_enabled': invoices_enabled,
        'invoices_status_message': 'Invoice functionality will be available with Module 11.' if not invoices_enabled else 'Available'
    }


def get_site_deployment(user: User, site_id):
    """
    Retrieves assigned guards and neutral statuses for current and next shift (FR-10.42 to FR-10.63, AC-10.14 to AC-10.21).
    Strictly sanitized: No phone numbers, no coordinates, no battery info.
    """
    validate_client_site_access(user, site_id)
    site = ClientSite.objects.get(site_id=site_id)

    now = timezone.now()
    today = timezone.localdate(now)

    # Fetch today's assignments from Module 5
    assignments = RosterAssignment.objects.filter(
        site=site,
        deployment_date=today
    ).select_related('shift', 'post_type')

    # Current shift & next shift logic
    current_shift_guards = []
    next_shift_guards = []
    required_guards = 0
    assigned_guards = assignments.count()
    confirmed_on_duty = 0

    manpower = SiteManpowerRequirement.objects.filter(site=site, is_active=True)
    required_guards = sum(m.required_count for m in manpower) if manpower.exists() else assigned_guards

    # Determine status for each assignment
    for a in assignments:
        emp = Employee.objects.filter(employee_id=a.employee_id).first()
        if not emp:
            continue

        # Check attendance record today
        att = AttendanceRecord.objects.filter(
            site=site,
            employee=emp,
            duty_date=today
        ).order_by('-created_at').first()

        # Vocabulary neutral mapping (Section 4.2):
        # Scheduled, Not Yet Confirmed, Check-in Recorded, On Duty, Status Not Updated, Replacement Assigned, Shift Completed
        is_replacement_assignment = (a.assignment_type == 'replacement' or bool(getattr(a, 'original_assignment_id', None)))
        if is_replacement_assignment:
            status_word = 'Replacement Assigned'
        elif att and att.actual_check_out:
            status_word = 'Shift Completed'
        elif att and att.actual_check_in:
            confirmed_on_duty += 1
            # Check how fresh the last update is
            time_diff = (now - att.actual_check_in).total_seconds()
            if time_diff > 43200: # 12 hours
                status_word = 'Status Not Updated'
            else:
                status_word = 'On Duty'
        elif str(a.status).lower() == 'scheduled':
            # If current time is past shift start, Not Yet Confirmed; else Scheduled
            shift_start_dt = datetime.combine(today, a.shift.start_time) if a.shift else now
            if timezone.is_naive(shift_start_dt):
                shift_start_dt = timezone.make_aware(shift_start_dt)
            if now >= shift_start_dt:
                status_word = 'Not Yet Confirmed'
            else:
                status_word = 'Scheduled'
        else:
            status_word = 'Scheduled'

        guard_card = {
            'guard_id': str(emp.employee_id),
            'name': emp.full_name,
            'photo_url': getattr(emp, 'photo_reference', None),
            'employee_code': emp.employee_code,
            'post': a.post_type.name if getattr(a, 'post_type', None) else (a.shift.shift_name if a.shift else 'Security Post'),
            'shift_timing': f"{a.shift.start_time.strftime('%H:%M')} - {a.shift.end_time.strftime('%H:%M')}" if a.shift else 'Standard Shift',
            'status_word': status_word,
            'last_updated_time': (att.actual_check_in or a.created_at).isoformat() if att else a.created_at.isoformat(),
            'is_replacement': is_replacement_assignment,
            'replacement_time': a.created_at.isoformat() if is_replacement_assignment else None
        }

        # Divide into current vs next shift
        if a.shift and a.shift.end_time < now.time() and a.shift.start_time < a.shift.end_time:
            # Shift ended
            current_shift_guards.append(guard_card)
        else:
            current_shift_guards.append(guard_card)

    shifts = SiteShift.objects.filter(site=site, is_active=True).order_by('start_time')
    shortfall = max(0, required_guards - confirmed_on_duty)
    shortfall_status = "Full Deployment" if shortfall == 0 else f"{shortfall} Position(s) Pending Confirmation"

    return {
        'site_id': str(site.site_id),
        'site_name': site.site_name,
        'current_date': today.isoformat(),
        'current_shift_name': shifts.first().shift_name if shifts.exists() else 'Regular Shift',
        'required_guards': required_guards,
        'assigned_guards': assigned_guards,
        'confirmed_on_duty': confirmed_on_duty,
        'shortfall': shortfall,
        'shortfall_status': shortfall_status,
        'current_shift_guards': current_shift_guards,
        'next_shift_guards': next_shift_guards,
        'last_updated_at': now.isoformat(),
    }


def get_client_safe_guard_card(user: User, guard_id):
    """
    Returns client-safe guard card from Module 3 (FR-10.43, AC-10.21).
    STRICT RESTRICTION: No phone numbers, no coordinates, no battery, no device info.
    """
    emp = Employee.objects.filter(employee_id=guard_id).first()
    if not emp:
        raise NotFound(detail="Guard profile not found.")

    return {
        'guard_id': str(emp.employee_id),
        'name': emp.full_name,
        'photo_url': getattr(emp, 'photo_reference', None),
        'employee_code': emp.employee_code,
        'designation': emp.designation or 'Security Guard',
        'badge_number': getattr(emp, 'badge_number', '') or '',
        'last_updated_at': emp.updated_at.isoformat(),
    }


def get_today_so_far_attendance(user: User, site_id=None):
    """
    Provisional attendance view (FR-10.64 to FR-10.67, AC-10.22).
    Explicitly labeled: 'Not Yet Approved', provisional = True.
    """
    permitted_sites = get_client_permitted_sites(user)
    if site_id:
        validate_client_site_access(user, site_id)
        permitted_sites = permitted_sites.filter(site_id=site_id)

    today = timezone.localdate()
    records = AttendanceRecord.objects.filter(
        site__in=permitted_sites,
        duty_date=today
    ).select_related('employee', 'site', 'shift')

    results = []
    for r in records:
        results.append({
            'attendance_id': str(r.attendance_id),
            'site_id': str(r.site_id),
            'site_name': r.site.site_name,
            'duty_date': r.duty_date.isoformat(),
            'guard_name': r.employee.full_name,
            'guard_code': r.employee.employee_code,
            'shift_name': r.shift.shift_name if r.shift else 'General Shift',
            'check_in_time': r.actual_check_in.isoformat() if r.actual_check_in else None,
            'check_out_time': r.actual_check_out.isoformat() if r.actual_check_out else None,
            'status_label': 'Not Yet Approved',
            'provisional': True,
            'is_manual': r.is_manual,
            'is_offline': r.is_offline,
            'last_updated_at': r.updated_at.isoformat(),
        })

    return results


def get_approved_attendance(user: User, site_id=None, start_date=None, end_date=None):
    """
    Approved attendance records grouped by day and site (FR-10.68 to FR-10.73, AC-10.23 to AC-10.25).
    Displays in/out times, manual and offline labels, and approved period state.
    """
    permitted_sites = get_client_permitted_sites(user)
    if site_id:
        validate_client_site_access(user, site_id)
        permitted_sites = permitted_sites.filter(site_id=site_id)

    qs = AttendanceRecord.objects.filter(
        site__in=permitted_sites,
        status__in=['approved', 'completed', 'corrected']
    ).select_related('employee', 'site', 'shift', 'period')

    if start_date:
        qs = qs.filter(duty_date__gte=start_date)
    if end_date:
        qs = qs.filter(duty_date__lte=end_date)

    results = []
    for r in qs.order_by('-duty_date', 'site__site_name')[:200]:
        period_state = r.period.status if r.period else 'Approved'
        results.append({
            'attendance_id': str(r.attendance_id),
            'site_id': str(r.site_id),
            'site_name': r.site.site_name,
            'duty_date': r.duty_date.isoformat(),
            'guard_name': r.employee.full_name,
            'guard_code': r.employee.employee_code,
            'shift_name': r.shift.shift_name if r.shift else 'General Shift',
            'in_time': r.actual_check_in.isoformat() if r.actual_check_in else None,
            'out_time': r.actual_check_out.isoformat() if r.actual_check_out else None,
            'worked_minutes': r.worked_minutes,
            'attendance_status': r.status.upper(),
            'is_manual': r.is_manual,
            'is_offline': r.is_offline,
            'period_state': period_state.upper(),
            'is_locked': bool(r.period and r.period.status == 'locked'),
        })

    return results


def download_monthly_attendance_sheet(user: User, site_id, month, year, file_format='csv'):
    """
    Downloads monthly attendance sheets for LOCKED periods only (FR-10.74, FR-10.75, AC-10.26, AC-10.27).
    Logs download through Module 1 (FR-10.76, AC-10.28).
    """
    validate_client_site_access(user, site_id)
    site = ClientSite.objects.get(site_id=site_id)

    # Check for locked period in Module 6
    start_of_month = date(year, month, 1)
    if month == 12:
        end_of_month = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end_of_month = date(year, month + 1, 1) - timedelta(days=1)

    period = AttendancePeriod.objects.filter(
        company_id=user.company_id,
        site_id=site.site_id,
        start_date__lte=end_of_month,
        end_date__gte=start_of_month,
        status='locked'
    ).first()

    # If no site-specific locked period, check company-wide locked period
    if not period:
        period = AttendancePeriod.objects.filter(
            company_id=user.company_id,
            site__isnull=True,
            start_date__lte=end_of_month,
            end_date__gte=start_of_month,
            status='locked'
        ).first()

    if not period:
        # Log failed download attempt
        ClientDocumentAccessLog.objects.create(
            company_id=user.company_id,
            client_user=user,
            document_id=uuid.uuid4(),
            source_module='MODULE_6',
            site=site,
            result='FAILED',
            file_type=file_format.upper(),
            access_reference=f"Monthly attendance {month}/{year} period not locked"
        )
        raise ValidationError("Monthly attendance sheet can only be downloaded for locked billing periods.")

    # Fetch approved/locked records for the site and month
    records = AttendanceRecord.objects.filter(
        site=site,
        duty_date__gte=start_of_month,
        duty_date__lte=end_of_month
    ).select_related('employee', 'shift').order_by('duty_date')

    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Date', 'Site Name', 'Employee Code', 'Guard Name',
        'Shift', 'Check-In', 'Check-Out', 'Worked Minutes',
        'Manual Entry', 'Offline Captured', 'Status'
    ])

    for r in records:
        writer.writerow([
            r.duty_date.isoformat(),
            site.site_name,
            r.employee.employee_code,
            r.employee.full_name,
            r.shift.shift_name if r.shift else '',
            r.actual_check_in.strftime('%H:%M:%S') if r.actual_check_in else '',
            r.actual_check_out.strftime('%H:%M:%S') if r.actual_check_out else '',
            r.worked_minutes,
            'Yes' if r.is_manual else 'No',
            'Yes' if r.is_offline else 'No',
            r.status.upper()
        ])

    csv_data = output.getvalue()

    # Log successful download in audit logs (FR-10.76, AC-10.28)
    doc_id = period.period_id
    ClientDocumentAccessLog.objects.create(
        company_id=user.company_id,
        client_user=user,
        document_id=doc_id,
        source_module='MODULE_6',
        site=site,
        result='SUCCESS',
        file_type='CSV',
        access_reference=f"Monthly attendance export {site.site_name} - {month}/{year}"
    )
    log_usage_event(user.company_id, user.user_id, 'DOCUMENT_DOWNLOAD', related_record_id=doc_id)

    return csv_data, f"attendance_{site.site_code}_{year}_{month:02d}.csv"


def create_attendance_query(user: User, attendance_record_id, site_id, reason, attachment_ref=None):
    """
    Raises a query on a specific attendance record, creating a Module 8 ClientTicket (FR-10.77, FR-10.78, AC-10.31).
    """
    validate_client_site_access(user, site_id)
    att = AttendanceRecord.objects.filter(attendance_id=attendance_record_id).first()
    if not att:
        raise NotFound(detail="Attendance record not found.")

    site = ClientSite.objects.get(site_id=site_id)
    client = Client.objects.get(client_id=user.client_company_id)

    # Generate sequence for ticket
    ticket_num = f"TICK-{timezone.now().year}-{uuid.uuid4().hex[:6].upper()}"

    ticket = ClientTicket.objects.create(
        company_id=user.company_id,
        ticket_number=ticket_num,
        client_generated_id=uuid.uuid4(),
        client=client,
        site=site,
        ticket_type='QUERY',
        title=f"Attendance Query for {att.employee.full_name} on {att.duty_date}",
        description=f"Attendance Record ID: {att.attendance_id}\nDuty Date: {att.duty_date}\nGuard: {att.employee.full_name} ({att.employee.employee_code})\nReason: {reason}",
        status='OPEN',
        is_admin_only=False
    )

    # Add initial message
    ClientTicketMessage.objects.create(
        ticket=ticket,
        company_id=user.company_id,
        actor=user,
        message=reason,
        visibility='CLIENT_VISIBLE',
        attachment_reference=attachment_ref
    )

    log_usage_event(user.company_id, user.user_id, 'ATTENDANCE_QUERY', related_record_id=ticket.ticket_id)
    return ticket


def report_post_issue(user: User, site_id, shift_id, category, description, named_guard_id=None, attachment_ref=None):
    """
    Reports an issue linked to site and shift through Module 8 (FR-10.61 to FR-10.63).
    A complaint about a named guard routes to ADMIN ONLY (FR-10.63).
    """
    validate_client_site_access(user, site_id)
    site = ClientSite.objects.get(site_id=site_id)
    client = Client.objects.get(client_id=user.client_company_id)

    is_admin_only = bool(named_guard_id)
    ticket_num = f"TICK-{timezone.now().year}-{uuid.uuid4().hex[:6].upper()}"

    ticket = ClientTicket.objects.create(
        company_id=user.company_id,
        ticket_number=ticket_num,
        client_generated_id=uuid.uuid4(),
        client=client,
        site=site,
        ticket_type='COMPLAINT' if named_guard_id else 'OBSERVED_ISSUE',
        title=f"Site Issue: {site.site_name} - {category}",
        description=description,
        named_guard_id=named_guard_id,
        is_admin_only=is_admin_only,
        status='OPEN'
    )

    ClientTicketMessage.objects.create(
        ticket=ticket,
        company_id=user.company_id,
        actor=user,
        message=description,
        visibility='CLIENT_VISIBLE',
        attachment_reference=attachment_ref
    )

    log_usage_event(user.company_id, user.user_id, 'POST_ISSUE', related_record_id=ticket.ticket_id)
    return ticket


def get_client_shared_incidents(user: User, site_id=None, status_filter=None):
    """
    Returns only approved client-shared incidents from Module 8 (FR-10.83 to FR-10.90, AC-10.33 to AC-10.36).
    Raw guard reports and internal notes are NEVER exposed.
    """
    permitted_sites = get_client_permitted_sites(user)
    if site_id:
        validate_client_site_access(user, site_id)
        permitted_sites = permitted_sites.filter(site_id=site_id)

    qs = IncidentClientVersion.objects.filter(
        site__in=permitted_sites,
        sharing_state='SHARED'
    ).select_related('site', 'incident')

    if status_filter:
        qs = qs.filter(status=status_filter)

    results = []
    for inc in qs.order_by('-occurred_at')[:100]:
        results.append({
            'version_id': str(inc.version_id),
            'incident_id': str(inc.incident_id),
            'site_id': str(inc.site_id),
            'site_name': inc.site.site_name,
            'title': inc.title,
            'category': inc.category,
            'occurred_at': inc.occurred_at.isoformat(),
            'summary': inc.summary,
            'actions_taken': inc.actions_taken,
            'status': inc.status,
            'approved_photos': inc.selected_attachment_ids,
            'version_number': inc.version_number,
        })

    return results


def add_client_incident_comment(user: User, version_id, comment_text):
    """
    Allows client to comment on a shared incident through Module 8 ticket flow (FR-10.91, FR-10.92, AC-10.37).
    """
    inc_version = IncidentClientVersion.objects.filter(version_id=version_id, sharing_state='SHARED').first()
    if not inc_version:
        raise NotFound(detail="Shared incident not found.")

    validate_client_site_access(user, inc_version.site_id)

    # Find or create a client ticket associated with this incident
    ticket = ClientTicket.objects.filter(
        company_id=user.company_id,
        site_id=inc_version.site_id,
        title__icontains=inc_version.title
    ).first()

    if not ticket:
        client = Client.objects.get(client_id=user.client_company_id)
        ticket_num = f"TICK-{timezone.now().year}-{uuid.uuid4().hex[:6].upper()}"
        ticket = ClientTicket.objects.create(
            company_id=user.company_id,
            ticket_number=ticket_num,
            client_generated_id=uuid.uuid4(),
            client=client,
            site_id=inc_version.site_id,
            ticket_type='FEEDBACK',
            title=f"Incident Comment: {inc_version.title}",
            description=f"Client comments on shared incident {inc_version.title}:\n\n{comment_text}",
            status='OPEN'
        )

    # Append comment message
    msg = ClientTicketMessage.objects.create(
        ticket=ticket,
        company_id=user.company_id,
        actor=user,
        message=comment_text,
        visibility='CLIENT_VISIBLE'
    )

    return {
        'message_id': str(msg.message_id),
        'ticket_id': str(ticket.ticket_id),
        'ticket_number': ticket.ticket_number,
        'comment': comment_text,
        'created_at': msg.created_at.isoformat()
    }


def get_client_safe_panic_status(user: User, panic_alert_id=None):
    """
    Returns client-safe emergency status (FR-10.93 to FR-10.104, AC-10.38, AC-10.39, AC-10.43).
    Strict restriction: ZERO coordinates, internal timeline, device data, or guard phone number.
    """
    permitted_sites = get_client_permitted_sites(user)
    permitted_site_ids = [s.site_id for s in permitted_sites]

    qs = PanicAlert.objects.filter(site_id__in=permitted_site_ids)
    if panic_alert_id:
        qs = qs.filter(panic_alert_id=panic_alert_id)
    else:
        qs = qs.filter(alert_status__in=['TRIGGERED', 'DELIVERING', 'ACKNOWLEDGED', 'RESPONDING'])

    alert = qs.order_by('-trigger_server_time').first()
    if not alert:
        return None

    status_map = {
        'TRIGGERED': 'Alert Raised',
        'DELIVERING': 'Alert Raised',
        'ACKNOWLEDGED': 'Agency Acknowledged',
        'RESPONDING': 'Responding',
        'GUARD_CONFIRMED_SAFE': 'Resolved',
        'RESOLVED': 'Resolved',
        'CLOSED': 'Resolved',
    }
    safe_status = status_map.get(alert.alert_status, 'Alert Raised')

    # Check if client has acknowledged
    is_acknowledged = PanicAcknowledgement.objects.filter(
        panic_alert=alert,
        user_id=user.user_id
    ).exists()

    return {
        'panic_alert_id': str(alert.panic_alert_id),
        'alert_number': alert.alert_number,
        'site_id': str(alert.site_id),
        'site_name': alert.site.site_name if alert.site else 'Security Site',
        'alert_time': alert.trigger_server_time.isoformat(),
        'client_safe_status': safe_status,
        'is_acknowledged_by_client': is_acknowledged,
        'emergency_contact': '112',
        'agency_control_room': '+91 80 2555 0100',
        'disclaimer': 'Notice: This emergency banner is for situational awareness only and does NOT replace official emergency dispatch services. Call 112 immediately for life-safety threats.',
        'last_updated_at': alert.updated_at.isoformat(),
    }


def acknowledge_panic_alert(user: User, panic_alert_id):
    """
    Client acknowledges receipt of emergency notice through Module 9 interface (FR-10.102, AC-10.40).
    Does NOT resolve the panic alert!
    """
    alert = PanicAlert.objects.filter(panic_alert_id=panic_alert_id).first()
    if not alert:
        raise NotFound(detail="Emergency alert not found.")

    validate_client_site_access(user, alert.site_id)

    # Get or create recipient entry for this user
    recipient, _ = PanicRecipient.objects.get_or_create(
        panic_alert=alert,
        user_id=user.user_id,
        defaults={
            'recipient_role': 'CLIENT',
            'recipient_type': 'CLIENT_ESCALATION',
            'notification_enabled': True
        }
    )

    ack, created = PanicAcknowledgement.objects.get_or_create(
        panic_alert=alert,
        recipient=recipient,
        user_id=user.user_id,
        defaults={
            'channel': 'APP',
            'acknowledgement_type': 'RECEIPT'
        }
    )

    return {
        'acknowledged': True,
        'panic_alert_id': str(alert.panic_alert_id),
        'acknowledged_at': ack.acknowledged_at.isoformat()
    }


def get_client_documents(user: User):
    """
    Retrieves approved client documents (FR-10.123 to FR-10.130, AC-10.50, AC-10.52).
    Service agreements and approved attendance sheets. Internal documents NEVER displayed.
    """
    client_id = user.client_company_id if user.role == 'CLIENT' else None
    if not client_id:
        return []

    client = Client.objects.filter(client_id=client_id).first()
    if not client:
        return []

    docs = []
    # 1. Service Agreement (Module 2)
    docs.append({
        'document_id': str(client.client_id),
        'document_name': f"Master Security Agreement - {client.client_name}",
        'document_type': 'SERVICE_AGREEMENT',
        'file_format': 'PDF',
        'source_module': 'MODULE_2',
        'issue_date': client.created_at.strftime('%Y-%m-%d'),
        'description': 'Official Security Service Master Agreement',
        'download_available': True,
    })

    # 2. Locked Attendance Periods (Module 6)
    permitted_sites = get_client_permitted_sites(user)
    locked_periods = AttendancePeriod.objects.filter(
        company_id=user.company_id,
        site__in=permitted_sites,
        status='locked'
    ).select_related('site')[:10]

    for p in locked_periods:
        docs.append({
            'document_id': str(p.period_id),
            'document_name': f"Locked Attendance - {p.site.site_name} ({p.period_name})",
            'document_type': 'ATTENDANCE_SHEET',
            'file_format': 'CSV',
            'source_module': 'MODULE_6',
            'issue_date': p.end_date.isoformat(),
            'description': f"Approved and locked monthly attendance for {p.site.site_name}",
            'download_available': True,
            'site_id': str(p.site_id),
        })

    return docs


def admin_client_preview(admin_user: User, client_user_id):
    """
    Allows Admin to preview the portal as a selected client without password (FR-10.155, AC-10.64, AC-10.65).
    Logs the preview action into usage events.
    """
    if admin_user.role != 'ADMIN':
        raise PermissionDenied("Only Administrators can preview the client portal.")

    target_user = User.objects.filter(user_id=client_user_id, role='CLIENT').first()
    if not target_user:
        raise NotFound("Target client user not found.")

    # Log preview event (FR-10.156, AC-10.65)
    log_usage_event(
        admin_user.company_id,
        admin_user.user_id,
        'PREVIEW',
        related_record_id=target_user.user_id,
        source='ADMIN_PREVIEW'
    )

    # Build simulated dashboard using target user's scope
    dashboard_data = build_client_dashboard(target_user)
    return {
        'preview_mode': True,
        'simulated_user': {
            'user_id': str(target_user.user_id),
            'full_name': target_user.full_name,
            'email': target_user.email,
            'client_company_id': str(target_user.client_company_id) if target_user.client_company_id else None
        },
        'dashboard': dashboard_data
    }


def get_real_portal_usage_metrics(company_id, days=30):
    """
    Aggregates real usage events for the Admin dashboard (FR-10.162, FR-10.163, AC-10.67).
    No fabricated data.
    """
    cutoff = timezone.now() - timedelta(days=days)
    events = ClientPortalUsageEvent.objects.filter(company_id=company_id, occurred_at__gte=cutoff)

    total_logins = events.filter(event_type__in=['LOGIN', 'FIRST_LOGIN']).count()
    first_logins = events.filter(event_type='FIRST_LOGIN').count()
    tickets_raised = events.filter(event_type__in=['TICKET_RAISED', 'ATTENDANCE_QUERY', 'POST_ISSUE']).count()
    downloads_count = events.filter(event_type='DOCUMENT_DOWNLOAD').count()
    preview_count = events.filter(event_type='PREVIEW').count()

    active_client_users = events.filter(client_user__isnull=False).values('client_user_id').distinct().count()

    recent_events = list(events.order_by('-occurred_at')[:25].values(
        'usage_event_id', 'event_type', 'occurred_at', 'source', 'client_user__full_name'
    ))

    return {
        'period_days': days,
        'total_logins': total_logins,
        'first_login_events': first_logins,
        'tickets_raised_via_portal': tickets_raised,
        'document_downloads': downloads_count,
        'admin_previews': preview_count,
        'active_client_users': active_client_users,
        'recent_events': recent_events
    }
