import math
from datetime import datetime, timedelta
import pytz
from django.utils import timezone
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import PermissionDenied, ValidationError

from foundation.models import User, Company, ConsentRecord
from foundation.services.settings_service import get_setting
from foundation.services.audit_service import write_audit_event
from master_data.models import ClientSite, SiteShift
from guard_management.models import Employee
from deployment_roster.models import RosterAssignment
from attendance.models import AttendanceRecord

from live_monitoring.models import (
    MonitoringDuty,
    LocationPoint,
    Heartbeat,
    GuardMonitoringStatus,
    MonitoringStatusHistory,
    AlertRule,
    MonitoringAlert,
    SupervisorPing,
    OutageGroup,
    TrackingConfiguration
)

IST = pytz.timezone('Asia/Kolkata')


def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Computes exact great-circle distance between two GPS coordinates in meters.
    """
    R = 6371000.0  # Earth radius in meters
    phi1 = math.radians(float(lat1))
    phi2 = math.radians(float(lat2))
    delta_phi = math.radians(float(lat2) - float(lat1))
    delta_lambda = math.radians(float(lon2) - float(lon1))

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def classify_geofence_boundary(lat, lon, accuracy_m, site):
    """
    FR-7.33, FR-7.34, Section 10.5:
    D = distance between coordinates and site center
    R = geofence radius
    A = horizontal accuracy

    D + A <= R -> Confidently Inside
    D - A > R  -> Confidently Outside
    Otherwise  -> Boundary Uncertain
    """
    if not site.latitude or not site.longitude:
        return 0.0, 'INSIDE'

    radius = 100.0
    if hasattr(site, 'geofence') and site.geofence and site.geofence.radius_meters:
        radius = float(site.geofence.radius_meters)

    dist = haversine_distance(lat, lon, site.latitude, site.longitude)
    acc = float(accuracy_m or 0.0)

    if (dist + acc) <= radius:
        return dist, 'INSIDE'
    elif (dist - acc) > radius:
        return dist, 'OUTSIDE'
    else:
        return dist, 'UNCERTAIN'


def start_monitoring_duty(
    assignment_id,
    attendance_record_id,
    duty_start_at=None,
    actor_user=None,
    request=None
):
    """
    FR-7.1, FR-7.2, FR-7.3, FR-7.4:
    Starts a monitoring session for an active assignment upon valid Module 6 check-in.
    Verifies separate continuous-location consent through Module 1.
    """
    assignment = RosterAssignment.objects.select_related('employee', 'site', 'shift').get(assignment_id=assignment_id)
    company_id = assignment.company_id
    employee = assignment.employee

    if not duty_start_at:
        duty_start_at = timezone.now()

    # Check separate continuous location consent (Module 1, FR-7.3)
    # The guard's linked user account must have an active LOCATION consent record
    guard_user = User.objects.filter(guard_profile_id=employee.employee_id, status='ACTIVE').first()
    consent_record = None
    consent_version = None
    has_consent = False

    if guard_user:
        consent_record = ConsentRecord.objects.filter(
            user=guard_user,
            item='LOCATION',
            decision='GRANTED'
        ).order_by('-recorded_at').first()
        if consent_record:
            has_consent = True
            consent_version = consent_record.policy_version

    tracking_state = 'ACTIVE' if has_consent else 'NOT_TRACKED'
    primary_status = 'on_duty_at_site' if has_consent else 'not_tracked'
    display_status = 'On Duty at Site' if has_consent else 'Not Tracked'

    duty, created = MonitoringDuty.objects.update_or_create(
        company_id=company_id,
        assignment=assignment,
        defaults={
            'employee': employee,
            'site': assignment.site,
            'shift': assignment.shift,
            'attendance_record_id': attendance_record_id,
            'duty_start_at': duty_start_at,
            'tracking_start_at': duty_start_at if has_consent else None,
            'consent_record': consent_record,
            'consent_policy_version': consent_version,
            'tracking_state': tracking_state,
        }
    )

    # Initialize or update GuardMonitoringStatus
    GuardMonitoringStatus.objects.update_or_create(
        duty=duty,
        defaults={
            'company_id': company_id,
            'employee': employee,
            'assignment': assignment,
            'site': assignment.site,
            'primary_status': primary_status,
            'has_active_alert': False,
            'display_status': display_status,
            'consecutive_outside_count': 0,
            'last_communication_at': duty_start_at,
            'status_calculated_at': timezone.now()
        }
    )

    # Append status history
    MonitoringStatusHistory.objects.create(
        company_id=company_id,
        duty=duty,
        employee=employee,
        previous_status='not_started',
        new_status=primary_status,
        trigger_type='DUTY_STARTED',
        changed_at=duty_start_at
    )

    return duty


def stop_monitoring_duty(duty_id, duty_end_at=None, reason='CHECK_OUT', actor_user=None, request=None):
    """
    FR-7.7, FR-7.8:
    Stops location collection immediately on check-out or at cutoff.
    Rejects subsequent location records outside the duty window.
    """
    duty = MonitoringDuty.objects.select_related('employee').get(duty_id=duty_id)
    if not duty_end_at:
        duty_end_at = timezone.now()

    duty.tracking_state = 'STOPPED'
    duty.duty_end_at = duty_end_at
    duty.tracking_end_at = duty_end_at
    duty.save()

    # Update status to Off Duty
    status_obj = GuardMonitoringStatus.objects.filter(duty=duty).first()
    if status_obj:
        prev = status_obj.primary_status
        status_obj.primary_status = 'off_duty'
        status_obj.display_status = 'Off Duty'
        status_obj.has_active_alert = False
        status_obj.status_calculated_at = timezone.now()
        status_obj.save()

        MonitoringStatusHistory.objects.create(
            company_id=duty.company_id,
            duty=duty,
            employee=duty.employee,
            previous_status=prev,
            new_status='off_duty',
            trigger_type=reason,
            changed_at=duty_end_at
        )

    # Auto-resolve any active alerts for this duty
    MonitoringAlert.objects.filter(
        duty=duty,
        state__in=['RAISED', 'ACKNOWLEDGED']
    ).update(
        state='AUTO_RESOLVED',
        resolved_at=timezone.now(),
        resolution_note=f'Auto-resolved upon duty termination ({reason})'
    )

    return duty


def ingest_location_batch(duty_id, locations_data, actor_user=None, request=None):
    """
    FR-7.11 to FR-7.24:
    Idempotent location ingestion. Validates duty window, coordinates,
    accuracy, geofence, debounce, and anomaly flags.
    """
    duty = MonitoringDuty.objects.select_related('site', 'employee', 'assignment', 'company').get(duty_id=duty_id)
    company_id = duty.company_id
    employee = duty.employee
    assignment = duty.assignment
    site = duty.site

    # Duty window validation (FR-7.9, FR-7.24)
    now_utc = timezone.now()
    if duty.tracking_state == 'STOPPED' and duty.duty_end_at:
        cutoff_mins = get_setting('post_shift_cutoff_mins', company_id) or 30
        if now_utc > (duty.duty_end_at + timedelta(minutes=cutoff_mins)):
            raise ValidationError("Duty monitoring is closed. Points outside permitted window are rejected.")

    status_obj = GuardMonitoringStatus.objects.get(duty=duty)
    debounce_target = get_setting('geofence_debounce_count', company_id) or 3

    accepted_points = []
    duplicate_count = 0
    rejected_count = 0
    last_accepted_point = None

    for item in locations_data:
        client_gen_id = item.get('client_generated_id')
        lat = item.get('latitude')
        lon = item.get('longitude')
        acc = item.get('accuracy_m', 0.0)
        captured_at_str = item.get('device_captured_at')

        # Idempotency check (FR-7.20, FR-7.21, AC-7.12)
        if LocationPoint.objects.filter(company_id=company_id, employee=employee, client_generated_id=client_gen_id).exists():
            duplicate_count += 1
            continue

        try:
            captured_at = datetime.fromisoformat(captured_at_str)
            if timezone.is_naive(captured_at):
                captured_at = timezone.make_aware(captured_at, pytz.UTC)
        except Exception:
            captured_at = now_utc

        # Coordinate bounds validation (FR-7.24, AC-7.10)
        if lat is None or lon is None or not (-90.0 <= float(lat) <= 90.0) or not (-180.0 <= float(lon) <= 180.0):
            rejected_count += 1
            LocationPoint.objects.create(
                company_id=company_id,
                duty=duty,
                employee=employee,
                assignment=assignment,
                client_generated_id=client_gen_id,
                latitude=0.0,
                longitude=0.0,
                accuracy_m=0.0,
                device_captured_at=captured_at,
                accepted=False,
                rejection_reason='Malformed or out-of-bounds coordinates'
            )
            continue

        point = LocationPoint.objects.create(
            company_id=company_id,
            duty=duty,
            employee=employee,
            assignment=assignment,
            client_generated_id=client_gen_id,
            latitude=lat,
            longitude=lon,
            accuracy_m=acc,
            device_captured_at=captured_at,
            server_received_at=now_utc,
            mock_location=item.get('mock_location', False),
            battery_percent=item.get('battery_percent'),
            charging_state=item.get('charging_state'),
            network_type=item.get('network_type'),
            app_version=item.get('app_version'),
            location_permission=item.get('location_permission'),
            battery_optimization_state=item.get('battery_optimization_state'),
            sequence_number=item.get('sequence_number'),
            accepted=True
        )

        accepted_points.append(point)
        last_accepted_point = point

        # Check mock location anomaly (FR-7.53, AC-7.14)
        if point.mock_location:
            raise_monitoring_alert(
                duty=duty,
                alert_type='MOCK_LOCATION_DETECTED',
                severity='HIGH',
                trigger_value=f'Mock location provider signal reported at {point.device_captured_at}',
                site=site
            )

        # Check device time mismatch (FR-7.55)
        time_diff = abs((now_utc - point.device_captured_at).total_seconds())
        if time_diff > 300:  # > 5 minutes
            raise_monitoring_alert(
                duty=duty,
                alert_type='TIME_MISMATCH',
                severity='NORMAL',
                trigger_value=f'Device clock discrepancy: {int(time_diff)} seconds',
                site=site
            )

        # Geofence classification with accuracy awareness (FR-7.33, FR-7.34, FR-7.36)
        dist, boundary = classify_geofence_boundary(lat, lon, acc, site)

        if boundary == 'OUTSIDE':
            status_obj.consecutive_outside_count += 1
            if status_obj.consecutive_outside_count >= debounce_target:
                if status_obj.primary_status != 'on_duty_outside_site':
                    prev_status = status_obj.primary_status
                    status_obj.primary_status = 'on_duty_outside_site'
                    status_obj.display_status = 'On Duty (Outside Site)'
                    status_obj.save()

                    MonitoringStatusHistory.objects.create(
                        company_id=company_id,
                        duty=duty,
                        employee=employee,
                        previous_status=prev_status,
                        new_status='on_duty_outside_site',
                        trigger_type='GEOFENCE_EXIT_CONFIRMED',
                        related_location=point,
                        changed_at=point.device_captured_at
                    )

                    raise_monitoring_alert(
                        duty=duty,
                        alert_type='GEOFENCE_EXIT',
                        severity='HIGH',
                        trigger_value=f'Guard outside geofence: {dist:.1f}m from site center (Accuracy: ±{acc}m)',
                        site=site
                    )
        elif boundary == 'INSIDE':
            if status_obj.consecutive_outside_count > 0:
                status_obj.consecutive_outside_count = 0

            if status_obj.primary_status != 'on_duty_at_site':
                prev_status = status_obj.primary_status
                status_obj.primary_status = 'on_duty_at_site'
                status_obj.display_status = 'On Duty at Site'
                status_obj.save()

                MonitoringStatusHistory.objects.create(
                    company_id=company_id,
                    duty=duty,
                    employee=employee,
                    previous_status=prev_status,
                    new_status='on_duty_at_site',
                    trigger_type='GEOFENCE_ENTRY_CONFIRMED',
                    related_location=point,
                    changed_at=point.device_captured_at
                )

                # Auto-resolve active geofence alerts
                MonitoringAlert.objects.filter(
                    duty=duty,
                    alert_type='GEOFENCE_EXIT',
                    state__in=['RAISED', 'ACKNOWLEDGED']
                ).update(
                    state='AUTO_RESOLVED',
                    resolved_at=now_utc,
                    resolution_note='Guard returned within site perimeter'
                )

    if last_accepted_point:
        status_obj.last_location_point = last_accepted_point
        status_obj.last_communication_at = last_accepted_point.device_captured_at
        status_obj.status_calculated_at = now_utc
        # Check if any active alerts remain
        status_obj.has_active_alert = MonitoringAlert.objects.filter(
            duty=duty, state__in=['RAISED', 'ACKNOWLEDGED']
        ).exists()
        status_obj.save()

    return {
        'accepted_count': len(accepted_points),
        'duplicate_count': duplicate_count,
        'rejected_count': rejected_count,
        'latest_server_timestamp': now_utc.isoformat()
    }


def ingest_heartbeat(duty_id, heartbeat_data, actor_user=None, request=None):
    """
    FR-7.18, FR-7.19:
    Heartbeat collection when guard is stationary.
    Tracks battery level, network condition, app version, permission health.
    """
    duty = MonitoringDuty.objects.select_related('employee', 'site').get(duty_id=duty_id)
    company_id = duty.company_id
    employee = duty.employee
    client_gen_id = heartbeat_data.get('client_generated_id')
    now_utc = timezone.now()

    # Deduplication (FR-7.21)
    if Heartbeat.objects.filter(company_id=company_id, employee=employee, client_generated_id=client_gen_id).exists():
        return {'status': 'DUPLICATE', 'server_received_at': now_utc.isoformat()}

    captured_at_str = heartbeat_data.get('captured_at')
    try:
        captured_at = datetime.fromisoformat(captured_at_str)
        if timezone.is_naive(captured_at):
            captured_at = timezone.make_aware(captured_at, pytz.UTC)
    except Exception:
        captured_at = now_utc

    battery = heartbeat_data.get('battery_percent')
    perm_state = heartbeat_data.get('permission_state')

    hb = Heartbeat.objects.create(
        company_id=company_id,
        duty=duty,
        employee=employee,
        client_generated_id=client_gen_id,
        captured_at=captured_at,
        received_at=now_utc,
        battery_percent=battery,
        charging_state=heartbeat_data.get('charging_state'),
        network_type=heartbeat_data.get('network_type'),
        app_version=heartbeat_data.get('app_version'),
        permission_state=perm_state,
        sequence_number=heartbeat_data.get('sequence_number')
    )

    # Battery alert check (FR-7.51)
    if battery is not None and battery <= 15:
        raise_monitoring_alert(
            duty=duty,
            alert_type='LOW_BATTERY',
            severity='NORMAL',
            trigger_value=f'Device battery level critical: {battery}%',
            site=duty.site
        )

    # Location permission alert check (FR-7.52)
    if perm_state in ('UNAVAILABLE', 'DENIED', 'REVOKED'):
        raise_monitoring_alert(
            duty=duty,
            alert_type='PERMISSION_UNAVAILABLE',
            severity='HIGH',
            trigger_value=f'Tracking permission reported as {perm_state}',
            site=duty.site
        )

    # Update status object
    status_obj = GuardMonitoringStatus.objects.get(duty=duty)
    status_obj.last_heartbeat = hb
    status_obj.last_communication_at = captured_at

    # If status was Stale or No Contact, restore to valid on-duty status
    if status_obj.primary_status in ('stale', 'no_contact'):
        new_stat = 'on_duty_outside_site' if status_obj.consecutive_outside_count >= 3 else 'on_duty_at_site'
        prev_stat = status_obj.primary_status
        status_obj.primary_status = new_stat
        status_obj.display_status = 'On Duty (Outside Site)' if new_stat == 'on_duty_outside_site' else 'On Duty at Site'

        MonitoringStatusHistory.objects.create(
            company_id=company_id,
            duty=duty,
            employee=employee,
            previous_status=prev_stat,
            new_status=new_stat,
            trigger_type='HEARTBEAT_RESUMED',
            changed_at=captured_at
        )

    status_obj.status_calculated_at = now_utc
    status_obj.save()

    return {
        'status': 'ACCEPTED',
        'server_received_at': now_utc.isoformat(),
        'current_status': status_obj.primary_status
    }


def recalculate_duty_statuses(company_id=None):
    """
    FR-7.41, Section 10.3, AC-7.22, AC-7.23:
    Evaluates stale and no-contact thresholds across active duties.
    Stale threshold: 10 minutes.
    No-contact threshold: 20 minutes.
    Post-shift cutoff: 30 minutes after shift end.
    """
    now_utc = timezone.now()
    qs = GuardMonitoringStatus.objects.filter(
        duty__tracking_state='ACTIVE'
    ).select_related('duty', 'duty__site', 'employee')

    if company_id:
        qs = qs.filter(company_id=company_id)

    stale_mins = 10
    no_contact_mins = 20

    updated_count = 0
    for stat in qs:
        last_comm = stat.last_communication_at
        if not last_comm:
            continue

        elapsed_mins = (now_utc - last_comm).total_seconds() / 60.0
        duty = stat.duty

        # Check post-shift cutoff
        if duty.assignment and duty.assignment.end_time:
            # Shift end is anchor for cutoff
            cutoff = duty.assignment.end_time + timedelta(minutes=30)
            if now_utc > cutoff:
                stop_monitoring_duty(duty.duty_id, duty_end_at=cutoff, reason='POST_SHIFT_CUTOFF')
                updated_count += 1
                continue

        # No Contact check (> 20 mins)
        if elapsed_mins >= no_contact_mins:
            if stat.primary_status != 'no_contact':
                prev = stat.primary_status
                stat.primary_status = 'no_contact'
                stat.display_status = 'No Contact'
                stat.status_calculated_at = now_utc
                stat.save()

                MonitoringStatusHistory.objects.create(
                    company_id=stat.company_id,
                    duty=duty,
                    employee=stat.employee,
                    previous_status=prev,
                    new_status='no_contact',
                    trigger_type='NO_CONTACT_THRESHOLD_EXCEEDED',
                    changed_at=now_utc
                )

                raise_monitoring_alert(
                    duty=duty,
                    alert_type='NO_CONTACT',
                    severity='HIGH',
                    trigger_value=f'No communication received for {int(elapsed_mins)} minutes',
                    site=stat.site
                )
                updated_count += 1
        # Stale check (> 10 mins)
        elif elapsed_mins >= stale_mins:
            if stat.primary_status in ('on_duty_at_site', 'on_duty_outside_site'):
                prev = stat.primary_status
                stat.primary_status = 'stale'
                stat.display_status = 'Low Signal or Stale'
                stat.status_calculated_at = now_utc
                stat.save()

                MonitoringStatusHistory.objects.create(
                    company_id=stat.company_id,
                    duty=duty,
                    employee=stat.employee,
                    previous_status=prev,
                    new_status='stale',
                    trigger_type='STALE_THRESHOLD_EXCEEDED',
                    changed_at=now_utc
                )
                updated_count += 1

    return updated_count


def raise_monitoring_alert(duty, alert_type, severity='NORMAL', trigger_value='', site=None):
    """
    FR-7.46 to FR-7.65:
    Configurable alert creation with deduplication and cooldown controls.
    """
    company_id = duty.company_id
    employee = duty.employee
    target_site = site or duty.site
    now_utc = timezone.now()

    # Find matching AlertRule
    rule = AlertRule.objects.filter(company_id=company_id, rule_code=alert_type, enabled=True).first()
    cooldown_seconds = rule.cooldown_seconds if rule else 900
    alert_severity = rule.severity if rule else severity

    # Deduplication & Cooldown Check (FR-7.57, AC-7.28)
    # Check if an active alert already exists for this duty and alert_type
    active_exists = MonitoringAlert.objects.filter(
        duty=duty,
        alert_type=alert_type,
        state__in=['RAISED', 'ACKNOWLEDGED']
    ).exists()
    if active_exists:
        return None

    # Check cooldown since last resolution
    recent_resolved = MonitoringAlert.objects.filter(
        duty=duty,
        alert_type=alert_type,
        state__in=['RESOLVED', 'AUTO_RESOLVED', 'DISMISSED'],
        resolved_at__gte=now_utc - timedelta(seconds=cooldown_seconds)
    ).exists()
    if recent_resolved:
        return None

    alert = MonitoringAlert.objects.create(
        company_id=company_id,
        duty=duty,
        employee=employee,
        site=target_site,
        alert_rule=rule,
        alert_type=alert_type,
        severity=alert_severity,
        state='RAISED',
        trigger_value=trigger_value,
        raised_at=now_utc
    )

    # Enable alert overlay on GuardMonitoringStatus (FR-7.43, Section 10.2)
    GuardMonitoringStatus.objects.filter(duty=duty).update(
        has_active_alert=True,
        status_calculated_at=now_utc
    )

    return alert


def acknowledge_alert(alert_id, actor_user, request=None):
    """
    FR-7.60, AC-7.30: Acknowledges alert by supervisor/admin.
    """
    alert = MonitoringAlert.objects.select_related('duty').get(alert_id=alert_id)
    alert.state = 'ACKNOWLEDGED'
    alert.acknowledged_at = timezone.now()
    alert.acknowledged_by = actor_user
    alert.save()
    return alert


def resolve_alert(alert_id, resolution_note, actor_user, request=None):
    """
    FR-7.60, FR-7.61, AC-7.31: Resolves alert with mandatory resolution note.
    """
    if not resolution_note or not resolution_note.strip():
        raise ValidationError("Resolution note is mandatory to resolve a monitoring alert.")

    alert = MonitoringAlert.objects.select_related('duty').get(alert_id=alert_id)
    now_utc = timezone.now()
    alert.state = 'RESOLVED'
    alert.resolved_at = now_utc
    alert.resolved_by = actor_user
    alert.resolution_note = resolution_note.strip()
    alert.save()

    # Check if other active alerts remain on duty
    has_other_active = MonitoringAlert.objects.filter(
        duty=alert.duty,
        state__in=['RAISED', 'ACKNOWLEDGED']
    ).exclude(alert_id=alert_id).exists()

    if not has_other_active:
        GuardMonitoringStatus.objects.filter(duty=alert.duty).update(
            has_active_alert=False,
            status_calculated_at=now_utc
        )

    return alert


def dismiss_alert_as_false_alarm(alert_id, dismissal_reason, actor_user, request=None):
    """
    FR-7.60, FR-7.62, AC-7.32: Dismisses alert as false alarm with mandatory reason.
    """
    if not dismissal_reason or not dismissal_reason.strip():
        raise ValidationError("Dismissal reason is mandatory when dismissing an alert as a false alarm.")

    alert = MonitoringAlert.objects.select_related('duty').get(alert_id=alert_id)
    now_utc = timezone.now()
    alert.state = 'DISMISSED'
    alert.resolved_at = now_utc
    alert.resolved_by = actor_user
    alert.dismissal_reason = dismissal_reason.strip()
    alert.save()

    has_other_active = MonitoringAlert.objects.filter(
        duty=alert.duty,
        state__in=['RAISED', 'ACKNOWLEDGED']
    ).exclude(alert_id=alert_id).exists()

    if not has_other_active:
        GuardMonitoringStatus.objects.filter(duty=alert.duty).update(
            has_active_alert=False,
            status_calculated_at=now_utc
        )

    return alert


def send_supervisor_ping(duty_id, supervisor_user, request=None):
    """
    FR-7.66 to FR-7.72, AC-7.37 to AC-7.40:
    Sends check-on-you ping with a 5-minute cooldown.
    """
    duty = MonitoringDuty.objects.select_related('employee').get(duty_id=duty_id)
    now_utc = timezone.now()
    cooldown_mins = 5

    recent_ping = SupervisorPing.objects.filter(
        duty=duty,
        sent_at__gte=now_utc - timedelta(minutes=cooldown_mins)
    ).first()

    if recent_ping:
        raise ValidationError(f"A ping was recently sent to this guard. Please wait {cooldown_mins} minutes between pings.")

    ping = SupervisorPing.objects.create(
        company_id=duty.company_id,
        duty=duty,
        employee=duty.employee,
        supervisor=supervisor_user,
        sent_at=now_utc,
        delivery_state='DELIVERED',  # Simulated delivery
        response_state='PENDING'
    )
    return ping


def respond_to_ping(ping_id, response_value="I am fine", actor_user=None, request=None):
    """
    FR-7.68, AC-7.38: One-tap guard confirmation.
    """
    ping = SupervisorPing.objects.get(ping_id=ping_id)
    ping.response_state = 'RESPONDED'
    ping.responded_at = timezone.now()
    ping.response_value = response_value
    ping.save()
    return ping


# ==============================================================================
# DOWNSTREAM CROSS-MODULE INTERFACES (Modules 8, 9, 10, 13)
# ==============================================================================

def get_last_known_position(employee_id, duty_id=None):
    """
    Section 14.2: Query for Module 9 (Panic).
    Returns last position with trust classification:
    - TRUSTED: Fresh (< 10 mins) and accurate (<= 50m)
    - STALE: Older than 10 mins
    - LOW_ACCURACY: Accuracy > 50m
    - UNAVAILABLE: No position found
    """
    qs = LocationPoint.objects.filter(employee_id=employee_id, accepted=True)
    if duty_id:
        qs = qs.filter(duty_id=duty_id)

    last_pt = qs.order_by('-device_captured_at').first()
    if not last_pt:
        return {'trust_flag': 'UNAVAILABLE', 'position': None}

    now_utc = timezone.now()
    age_seconds = int((now_utc - last_pt.device_captured_at).total_seconds())

    if age_seconds > 600:
        trust_flag = 'STALE'
    elif float(last_pt.accuracy_m) > 50.0:
        trust_flag = 'LOW_ACCURACY'
    else:
        trust_flag = 'TRUSTED'

    return {
        'trust_flag': trust_flag,
        'latitude': float(last_pt.latitude),
        'longitude': float(last_pt.longitude),
        'accuracy_m': float(last_pt.accuracy_m),
        'captured_at': last_pt.device_captured_at.isoformat(),
        'age_seconds': age_seconds,
        'duty_id': str(last_pt.duty_id)
    }


def get_guard_position_at_time(employee_id, target_time, window_minutes=30):
    """
    Section 14.3: Query for Module 8 (Incident Reporting).
    Finds closest position within time window.
    """
    start_win = target_time - timedelta(minutes=window_minutes)
    end_win = target_time + timedelta(minutes=window_minutes)

    pts = LocationPoint.objects.filter(
        employee_id=employee_id,
        accepted=True,
        device_captured_at__gte=start_win,
        device_captured_at__lte=end_win
    ).order_by('device_captured_at')

    closest_pt = None
    min_diff = float('inf')

    for pt in pts:
        diff = abs((pt.device_captured_at - target_time).total_seconds())
        if diff < min_diff:
            min_diff = diff
            closest_pt = pt

    if not closest_pt:
        return {'available': False, 'position': None}

    return {
        'available': True,
        'latitude': float(closest_pt.latitude),
        'longitude': float(closest_pt.longitude),
        'accuracy_m': float(closest_pt.accuracy_m),
        'captured_at': closest_pt.device_captured_at.isoformat(),
        'time_delta_seconds': int(min_diff)
    }


def get_client_safe_status(client_company_id, site_id=None):
    """
    Section 14.4: Sanitized query for Module 10 (Client Portal).
    Only returns safe status word and timestamp.
    NEVER returns coordinates, accuracy, trails, battery, alerts, or internal notes.
    """
    qs = GuardMonitoringStatus.objects.filter(
        site__client__company_id=client_company_id
    ).select_related('employee', 'site', 'duty')

    if site_id:
        qs = qs.filter(site_id=site_id)

    results = []
    for stat in qs:
        # Map internal status to client-safe status word
        if stat.primary_status == 'on_duty_at_site':
            safe_word = 'On duty at site'
        elif stat.primary_status == 'not_started':
            safe_word = 'Not yet arrived'
        elif stat.primary_status == 'off_duty':
            safe_word = 'Off duty'
        else:
            safe_word = 'Status unavailable'

        results.append({
            'guard_id': str(stat.employee_id),
            'guard_name': stat.employee.full_name,
            'guard_code': stat.employee.employee_code,
            'site_name': stat.site.site_name,
            'client_safe_status': safe_word,
            'last_updated': stat.status_calculated_at.isoformat()
        })

    return results
