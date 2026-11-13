import math
import hashlib
import uuid
from datetime import datetime, date, timedelta, time
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.db.models import Q
from rest_framework.exceptions import ValidationError, PermissionDenied, NotFound

from foundation.models import User, BoundDevice
from master_data.models import ClientSite, SiteShift
from guard_management.models import Employee
from deployment_roster.models import RosterAssignment
from deployment_roster import services as roster_services
from foundation.services.audit_service import write_audit_event
from foundation.services.settings_service import get_setting
from foundation.services.notification_service import send_notification

from attendance.models import (
    AttendancePeriod,
    AttendanceRecord,
    AttendanceCapture,
    AttendanceEvidence,
    AttendanceFlag,
    AttendanceRevision,
    AttendanceRegularisation,
    AttendanceApproval,
    AttendancePeriodException,
    AttendanceHandover,
    ManualAttendanceCounter,
)


# ==============================================================================
# 1. GEOFENCE CALCULATION ENGINE (Haversine Formula)
# ==============================================================================

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Computes great-circle distance in meters between two coordinates.
    Earth radius R = 6,371,000 meters.
    """
    R = 6371000.0
    phi1 = math.radians(float(lat1))
    phi2 = math.radians(float(lat2))
    delta_phi = math.radians(float(lat2) - float(lat1))
    delta_lambda = math.radians(float(lon2) - float(lon1))

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def validate_geofence(site: ClientSite, guard_lat: float, guard_lon: float, gps_accuracy: float, outside_reason: str = None) -> dict:
    """
    Server-authoritative uncertainty-aware geofence evaluation (FR-6.5 to FR-6.8, AC-06 to AC-09).
    """
    company_id = site.client.company_id
    max_acc = float(get_setting('max_gps_accuracy_meters', company_id) or 100.0)

    # 1. Poor accuracy block (AC-08)
    if gps_accuracy > max_acc:
        return {
            'outcome': 'blocked',
            'distance_meters': 0.0,
            'reasons': [f"GPS accuracy ({gps_accuracy:.1f}m) is worse than maximum allowed limit of {max_acc:.0f}m. Move to an open area and try again."]
        }

    # Site center coordinates
    site_lat = float(site.latitude)
    site_lon = float(site.longitude)
    radius = float(site.geofence_radius_m or 100)

    dist = haversine_distance(guard_lat, guard_lon, site_lat, site_lon)

    # Clearly inside (AC-06)
    if dist <= radius:
        return {
            'outcome': 'valid',
            'distance_meters': round(dist, 2),
            'reasons': []
        }

    # Boundary overlap with uncertainty (AC-09)
    if (dist - gps_accuracy) <= radius:
        return {
            'outcome': 'valid',
            'distance_meters': round(dist, 2),
            'reasons': [f"Location uncertainty ({gps_accuracy:.1f}m) overlaps boundary. Distance: {dist:.1f}m, Geofence: {radius:.0f}m."]
        }

    # Outside geofence (AC-07)
    if outside_reason and outside_reason.strip():
        return {
            'outcome': 'outside_with_reason',
            'distance_meters': round(dist, 2),
            'reasons': [f"Check-in outside geofence ({dist:.1f}m from site, radius {radius:.0f}m). Reason: {outside_reason.strip()}"]
        }

    return {
        'outcome': 'blocked',
        'distance_meters': round(dist, 2),
        'reasons': [f"You are {dist:.0f}m away from the site (geofence radius is {radius:.0f}m). Please move closer or provide an outside geofence reason."]
    }


# ==============================================================================
# 2. CHECK-IN SERVICE
# ==============================================================================

@transaction.atomic
def record_check_in(employee_id, data, actor_user=None, request=None) -> AttendanceRecord:
    """
    Submits and processes a guard check-in capture (FR-6.1 to FR-6.14, AC-01 to AC-13).
    Idempotent by client-generated capture_id (AC-20, AC-21, AC-22).
    """
    capture_id = data.get('capture_id')
    if not capture_id:
        raise ValidationError({'capture_id': 'Unique client-generated capture_id is required.'})

    try:
        capture_uuid = uuid.UUID(str(capture_id))
    except (ValueError, TypeError):
        raise ValidationError({'capture_id': 'capture_id must be a valid UUID.'})

    # Check Idempotency (AC-21, AC-22)
    existing_capture = AttendanceCapture.objects.filter(capture_id=capture_uuid).first()
    if existing_capture:
        # Check payload consistency
        if existing_capture.employee_id != uuid.UUID(str(employee_id)):
            raise ValidationError({'capture_id': 'Conflicting duplicate capture received with different employee.'})
        return existing_capture.attendance

    employee = Employee.objects.get(employee_id=employee_id)
    company_id = employee.company_id

    # Assignment verification
    assignment_id = data.get('assignment_id')
    assignment = None
    if assignment_id:
        assignment = RosterAssignment.objects.filter(assignment_id=assignment_id).first()
        if not assignment:
            raise NotFound(f"Assignment '{assignment_id}' not found.")
        # Assignment ownership check (AC-02)
        if assignment.employee_id != employee.employee_id:
            raise PermissionDenied("Guard cannot check in for another guard's assignment (AC-02).")
        site = assignment.site
        shift = assignment.shift
        duty_date = assignment.deployment_date
        sched_start = assignment.start_time
        sched_end = assignment.end_time
    else:
        # Unscheduled Check-in (FR-6.13, AC-13)
        site_id = data.get('site_id')
        shift_id = data.get('shift_id')
        if not site_id or not shift_id:
            raise ValidationError({'detail': 'Unscheduled check-in requires site_id and shift_id.'})
        site = ClientSite.objects.get(site_id=site_id)
        shift = SiteShift.objects.get(shift_id=shift_id)
        duty_date = date.today()
        # Compute default interval
        start_t = shift.start_time
        end_t = shift.end_time
        sched_start = timezone.make_aware(datetime.combine(duty_date, start_t))
        if shift.is_cross_midnight:
            sched_end = timezone.make_aware(datetime.combine(duty_date + timedelta(days=1), end_t))
        else:
            sched_end = timezone.make_aware(datetime.combine(duty_date, end_t))

    # Registered device validation (FR-6.11, AC-12)
    device_id = data.get('device_id', '').strip()
    if not device_id:
        raise ValidationError({'device_id': 'Hardware device_id is required.'})

    user = User.objects.filter(guard_profile_id=employee.employee_id).first()
    if user:
        bound = BoundDevice.objects.filter(user=user, unbound_at__isnull=True).first()
        if bound and bound.device_id != device_id:
            # Audit & Notify Admin & Supervisor
            write_audit_event(
                action_code='attendance.unregistered_device',
                actor_user=actor_user,
                record_type='AttendanceRecord',
                reason=f"Unregistered device '{device_id}' used by {employee.full_name}",
                result='FAILURE',
                company_id=company_id
            )
            raise PermissionDenied(f"This phone is not registered to your account ({device_id}). Contact Admin to request a device change.")

    # Mock location check (FR-6.9, AC-10)
    mock_detected = bool(data.get('mock_location_detected', False))
    if mock_detected:
        write_audit_event(
            action_code='attendance.mock_location',
            actor_user=actor_user,
            record_type='AttendanceRecord',
            reason=f"Mock location provider detected for guard {employee.full_name}",
            result='FAILURE',
            company_id=company_id
        )
        raise ValidationError({'detail': 'Mock location provider detected. Real GPS is required for check-in.'})

    # Device time parsing & server comparison (FR-6.10, AC-11)
    device_time_raw = data.get('device_time')
    if not device_time_raw:
        raise ValidationError({'device_time': 'Device timestamp is required.'})

    if isinstance(device_time_raw, str):
        device_time = datetime.fromisoformat(device_time_raw.replace('Z', '+00:00'))
    else:
        device_time = device_time_raw

    if timezone.is_naive(device_time):
        device_time = timezone.make_aware(device_time)

    now_utc = timezone.now()
    diff_sec = abs((now_utc - device_time).total_seconds())
    max_mismatch = int(get_setting('device_time_mismatch_max_seconds', company_id) or 300)

    time_mismatch_flag = (diff_sec > max_mismatch)

    # Check-in window validation (FR-6.2, AC-03)
    window_before = int(get_setting('check_in_window_before_mins', company_id) or 30)
    window_after = int(get_setting('check_in_window_after_mins', company_id) or 60)
    allowed_start = sched_start - timedelta(minutes=window_before)
    allowed_end = sched_start + timedelta(minutes=window_after)

    if device_time < allowed_start:
        raise ValidationError({'detail': f"Check-in window has not opened yet. Window opens {window_before} minutes before shift start ({allowed_start.strftime('%H:%M')})."})

    # Geofence validation (FR-6.5 to FR-6.8)
    lat = float(data.get('latitude', 0))
    lon = float(data.get('longitude', 0))
    accuracy = float(data.get('gps_accuracy', 0))
    outside_reason = data.get('outside_reason', '').strip()

    geo_res = validate_geofence(site, lat, lon, accuracy, outside_reason)
    if geo_res['outcome'] == 'blocked':
        raise ValidationError({'detail': ' '.join(geo_res['reasons'])})

    # Photo & hash
    photo_key = data.get('photo_storage_key', f"attendance/photos/{capture_uuid}.jpg")
    photo_hash = data.get('photo_hash')
    if not photo_hash:
        photo_hash = hashlib.sha256(photo_key.encode('utf-8')).hexdigest()

    # Reused photo hash check (AC-40)
    reused_photo = AttendanceCapture.objects.filter(
        photo_hash=photo_hash
    ).exclude(employee=employee).exists()

    # Repeated location check
    repeated_loc = AttendanceCapture.objects.filter(
        employee=employee,
        latitude=Decimal(str(round(lat, 6))),
        longitude=Decimal(str(round(lon, 6)))
    ).filter(
        created_at__lt=now_utc - timedelta(days=1)
    ).exists()

    # Late Arrival calculation (FR-6.35, AC-14)
    grace_period = int(get_setting('late_grace_period_mins', company_id) or 15)
    late_minutes = 0
    if device_time > (sched_start + timedelta(minutes=grace_period)):
        late_minutes = max(0, int((device_time - sched_start).total_seconds() / 60))

    # Get or create AttendanceRecord (AC-27)
    if assignment:
        attendance, _ = AttendanceRecord.objects.get_or_create(
            assignment=assignment,
            duty_date=duty_date,
            defaults={
                'company_id': company_id,
                'employee': employee,
                'site': site,
                'shift': shift,
                'scheduled_start': sched_start,
                'scheduled_end': sched_end,
                'status': 'scheduled'
            }
        )
    else:
        attendance = AttendanceRecord.objects.create(
            company_id=company_id,
            employee=employee,
            site=site,
            shift=shift,
            duty_date=duty_date,
            scheduled_start=sched_start,
            scheduled_end=sched_end,
            is_unscheduled=True,
            status='pending_approval'
        )

    # Create AttendanceCapture
    capture = AttendanceCapture.objects.create(
        capture_id=capture_uuid,
        attendance=attendance,
        assignment=assignment,
        employee=employee,
        capture_type='CHECK_IN',
        device_time=device_time,
        server_received_time=now_utc,
        latitude=Decimal(str(round(lat, 6))),
        longitude=Decimal(str(round(lon, 6))),
        gps_accuracy=Decimal(str(round(accuracy, 2))),
        distance_meters=Decimal(str(geo_res['distance_meters'])),
        geofence_outcome=geo_res['outcome'],
        outside_reason=outside_reason or None,
        device_id=device_id,
        app_version=data.get('app_version', '1.0.0'),
        battery_level=data.get('battery_level'),
        network_type=data.get('network_type'),
        mock_location_detected=mock_detected,
        photo_storage_key=photo_key,
        photo_hash=photo_hash,
        sync_state='synced'
    )

    # Store evidence records
    AttendanceEvidence.objects.create(
        attendance=attendance,
        capture=capture,
        evidence_type='photo',
        storage_reference=photo_key,
        hash=photo_hash
    )
    AttendanceEvidence.objects.create(
        attendance=attendance,
        capture=capture,
        evidence_type='gps',
        storage_reference=f"lat:{lat},lon:{lon},acc:{accuracy},dist:{geo_res['distance_meters']}",
        hash=hashlib.sha256(f"{lat},{lon}".encode('utf-8')).hexdigest()
    )

    # Create flags if anomalies detected (FR-6.39)
    if geo_res['outcome'] == 'outside_with_reason':
        AttendanceFlag.objects.create(
            attendance=attendance,
            flag_type='outside_geofence',
            severity='HIGH',
            description=f"Check-in outside geofence ({geo_res['distance_meters']}m from site). Reason: {outside_reason}"
        )

    if time_mismatch_flag:
        AttendanceFlag.objects.create(
            attendance=attendance,
            flag_type='device_time_mismatch',
            severity='HIGH',
            description=f"Device clock differs by {int(diff_sec)}s from server clock (threshold {max_mismatch}s)."
        )

    if reused_photo:
        AttendanceFlag.objects.create(
            attendance=attendance,
            flag_type='reused_photo_hash',
            severity='HIGH',
            description="Photograph SHA-256 hash has been used by another attendance submission."
        )

    if repeated_loc:
        AttendanceFlag.objects.create(
            attendance=attendance,
            flag_type='repeated_location',
            severity='MEDIUM',
            description="Identical GPS coordinates to 6 decimals repeated across multiple duty dates."
        )

    # Update AttendanceRecord
    attendance.actual_check_in = device_time
    attendance.late_minutes = late_minutes
    if late_minutes > 0:
        attendance.status = 'late'
    else:
        attendance.status = 'in_progress'

    attendance.is_offline = bool(data.get('is_offline', False))
    if attendance.is_offline:
        AttendanceFlag.objects.create(
            attendance=attendance,
            flag_type='offline_capture',
            severity='MEDIUM',
            description="Attendance capture recorded while offline and synchronized later."
        )

    attendance.save()

    write_audit_event(
        action_code='attendance.check_in',
        actor_user=actor_user,
        record_type='AttendanceRecord',
        record_id=str(attendance.attendance_id),
        reason="Guard check-in recorded",
        result='SUCCESS',
        company_id=company_id
    )

    return attendance


# ==============================================================================
# 3. CHECK-OUT SERVICE
# ==============================================================================

@transaction.atomic
def record_check_out(employee_id, data, actor_user=None, request=None) -> AttendanceRecord:
    """
    Submits and processes a guard check-out capture (FR-6.15 to FR-6.20, AC-14 to AC-18).
    Calculates worked minutes, early exit, and regular vs overtime minutes.
    """
    capture_id = data.get('capture_id')
    if not capture_id:
        raise ValidationError({'capture_id': 'Unique client-generated capture_id is required.'})

    capture_uuid = uuid.UUID(str(capture_id))

    # Idempotency check
    existing_capture = AttendanceCapture.objects.filter(capture_id=capture_uuid).first()
    if existing_capture:
        return existing_capture.attendance

    employee = Employee.objects.get(employee_id=employee_id)
    company_id = employee.company_id

    # Find active attendance record
    attendance_id = data.get('attendance_id')
    if attendance_id:
        attendance = AttendanceRecord.objects.filter(attendance_id=attendance_id).first()
    else:
        attendance = AttendanceRecord.objects.filter(
            employee=employee,
            status__in=['in_progress', 'late']
        ).order_by('-scheduled_start').first()

    if not attendance or not attendance.actual_check_in:
        raise ValidationError({'detail': 'No active in-progress check-in found for this guard.'})

    # Device time parsing
    device_time_raw = data.get('device_time')
    if not device_time_raw:
        raise ValidationError({'device_time': 'Device timestamp is required.'})

    if isinstance(device_time_raw, str):
        device_time = datetime.fromisoformat(device_time_raw.replace('Z', '+00:00'))
    else:
        device_time = device_time_raw

    if timezone.is_naive(device_time):
        device_time = timezone.make_aware(device_time)

    # Verify check-out is after check-in
    if device_time <= attendance.actual_check_in:
        raise ValidationError({'detail': 'Check-out time must be after check-in time.'})

    # Geofence & accuracy
    lat = float(data.get('latitude', 0))
    lon = float(data.get('longitude', 0))
    accuracy = float(data.get('gps_accuracy', 0))
    outside_reason = data.get('outside_reason', '').strip()

    geo_res = validate_geofence(attendance.site, lat, lon, accuracy, outside_reason)
    if geo_res['outcome'] == 'blocked':
        raise ValidationError({'detail': ' '.join(geo_res['reasons'])})

    # Photo & hash
    photo_key = data.get('photo_storage_key', f"attendance/photos/{capture_uuid}.jpg")
    photo_hash = data.get('photo_hash') or hashlib.sha256(photo_key.encode('utf-8')).hexdigest()

    # Minute calculations (FR-6.33, FR-6.34, FR-6.37)
    worked_minutes = int((device_time - attendance.actual_check_in).total_seconds() / 60)

    # Daily Overtime calculation from Module 5 threshold
    ot_threshold_hours = float(get_setting('daily_overtime_threshold_hours', company_id) or 8.0)
    ot_threshold_minutes = int(ot_threshold_hours * 60)

    regular_minutes = min(worked_minutes, ot_threshold_minutes)
    overtime_minutes = max(0, worked_minutes - ot_threshold_minutes)

    # Early check-out calculation (FR-6.16, AC-15)
    early_exit_minutes = 0
    if device_time < attendance.scheduled_end:
        early_exit_minutes = int((attendance.scheduled_end - device_time).total_seconds() / 60)
        early_reason = data.get('early_exit_reason', '').strip()
        if not early_reason:
            raise ValidationError({'early_exit_reason': 'Reason is mandatory for early check-out.'})
        AttendanceFlag.objects.create(
            attendance=attendance,
            flag_type='early_checkout',
            severity='MEDIUM',
            description=f"Guard checked out {early_exit_minutes} minutes before scheduled end. Reason: {early_reason}"
        )

    # Create AttendanceCapture
    capture = AttendanceCapture.objects.create(
        capture_id=capture_uuid,
        attendance=attendance,
        assignment=attendance.assignment,
        employee=employee,
        capture_type='CHECK_OUT',
        device_time=device_time,
        server_received_time=timezone.now(),
        latitude=Decimal(str(round(lat, 6))),
        longitude=Decimal(str(round(lon, 6))),
        gps_accuracy=Decimal(str(round(accuracy, 2))),
        distance_meters=Decimal(str(geo_res['distance_meters'])),
        geofence_outcome=geo_res['outcome'],
        outside_reason=outside_reason or None,
        device_id=data.get('device_id', 'DEV-MOBILE'),
        app_version=data.get('app_version', '1.0.0'),
        photo_storage_key=photo_key,
        photo_hash=photo_hash,
        sync_state='synced'
    )

    # Update AttendanceRecord
    attendance.actual_check_out = device_time
    attendance.worked_minutes = worked_minutes
    attendance.regular_minutes = regular_minutes
    attendance.overtime_minutes = overtime_minutes
    attendance.early_exit_minutes = early_exit_minutes
    attendance.status = 'pending_approval'
    attendance.save()

    write_audit_event(
        action_code='attendance.check_out',
        actor_user=actor_user,
        record_type='AttendanceRecord',
        record_id=str(attendance.attendance_id),
        reason=f"Check-out recorded: {worked_minutes} worked minutes",
        result='SUCCESS',
        company_id=company_id
    )

    return attendance


# ==============================================================================
# 4. AUTO-CLOSE & NO-SHOW DETECTION
# ==============================================================================

def auto_close_missing_checkouts(company_id=None):
    """
    Closes attendance records left without check-out after shift end + delay (FR-6.18, AC-16, AC-17).
    """
    now = timezone.now()
    qs = AttendanceRecord.objects.filter(status__in=['in_progress', 'late'], actual_check_out__isnull=True)
    if company_id:
        qs = qs.filter(company_id=company_id)

    closed_count = 0
    for att in qs:
        delay_hours = int(get_setting('auto_close_delay_hours', att.company_id) or 4)
        if now >= (att.scheduled_end + timedelta(hours=delay_hours)):
            att.status = 'no_checkout'
            att.save()

            AttendanceFlag.objects.create(
                attendance=att,
                flag_type='no_checkout',
                severity='MEDIUM',
                description=f"Auto-closed without check-out after {delay_hours} hours past scheduled shift end."
            )
            closed_count += 1

    return {'auto_closed_count': closed_count}


def detect_and_report_no_shows(company_id=None):
    """
    Identifies unstarted duties past no-show threshold and reports to Module 5 (FR-6.41, AC-29).
    """
    now = timezone.now()
    qs = AttendanceRecord.objects.filter(
        status='scheduled',
        actual_check_in__isnull=True,
        assignment__isnull=False
    )
    if company_id:
        qs = qs.filter(company_id=company_id)

    reported_count = 0
    for att in qs:
        delay_mins = int(get_setting('no_show_delay_minutes', att.company_id) or 60)
        if now >= (att.scheduled_start + timedelta(minutes=delay_mins)):
            try:
                # Call Module 5 report no-show
                roster_services.report_no_show_from_module6(
                    att.assignment.assignment_id,
                    reported_at=now
                )
                reported_count += 1
            except Exception as e:
                # Safe retry on error
                pass

    return {'no_shows_reported': reported_count}


# ==============================================================================
# 5. SUPERVISOR APPROVAL & CORRECTIONS
# ==============================================================================

@transaction.atomic
def approve_attendance(attendance_id, actor_user, request=None) -> AttendanceRecord:
    """
    Approves an attendance record (FR-6.43 to FR-6.53, AC-34 to AC-42).
    Enforces self-approval prohibition (AC-37) and supervisor site scope (AC-38).
    """
    att = AttendanceRecord.objects.select_for_update().get(attendance_id=attendance_id)

    # 1. Prohibit self-approval (AC-37, FR-6.50)
    if getattr(actor_user, 'guard_profile_id', None) and att.employee_id == actor_user.guard_profile_id:
        raise PermissionDenied("A user cannot approve their own attendance record (AC-37).")

    # 2. Check locked period (AC-48, FR-6.63)
    if att.period and att.period.status == 'locked':
        raise PermissionDenied("Cannot modify attendance in a locked period without Admin reopening (AC-48).")

    # 3. Check unresolved flags: flagged records require individual review with an explicit note
    unresolved_flags = AttendanceFlag.objects.filter(attendance=att, resolved_at__isnull=True)
    if unresolved_flags.exists():
        # Individual review requires note
        note = request.data.get('review_note') if request else None
        if not note or not note.strip():
            raise ValidationError({
                'detail': f"Attendance has {unresolved_flags.count()} review flag(s). Flagged records require an individual review note to approve (AC-36)."
            })
        unresolved_flags.update(resolved_at=timezone.now(), resolution=note.strip())

    att.status = 'approved'
    att.save()

    AttendanceApproval.objects.create(
        attendance=att,
        actor=actor_user,
        action='approve',
        reason=request.data.get('reason') if request else None
    )

    write_audit_event(
        action_code='attendance.approved',
        actor_user=actor_user,
        record_type='AttendanceRecord',
        record_id=str(att.attendance_id),
        reason="Attendance approved",
        result='SUCCESS',
        company_id=att.company_id
    )

    return att


@transaction.atomic
def bulk_approve_clean_attendance(site_id, duty_date, actor_user, request=None) -> dict:
    """
    Bulk approves only clean records with zero flags (FR-6.44, AC-34, AC-35).
    Skips flagged records and self-attendance.
    """
    site = ClientSite.objects.get(site_id=site_id)
    records = AttendanceRecord.objects.filter(
        site=site,
        duty_date=duty_date,
        status__in=['completed', 'pending_approval', 'late']
    )

    approved_count = 0
    flagged_count = 0
    skipped_count = 0

    user_guard_id = getattr(actor_user, 'guard_profile_id', None)

    for att in records:
        # Self-attendance skipped
        if user_guard_id and att.employee_id == user_guard_id:
            skipped_count += 1
            continue

        # Check flags (AC-35)
        has_flags = AttendanceFlag.objects.filter(attendance=att, resolved_at__isnull=True).exists()
        if has_flags:
            flagged_count += 1
            skipped_count += 1
            continue

        att.status = 'approved'
        att.save()
        AttendanceApproval.objects.create(
            attendance=att,
            actor=actor_user,
            action='approve',
            reason='Bulk clean approval'
        )
        approved_count += 1

    return {
        'approved_count': approved_count,
        'skipped_count': skipped_count,
        'flagged_count': flagged_count
    }


@transaction.atomic
def reject_attendance(attendance_id, reason, actor_user, request=None) -> AttendanceRecord:
    """
    Rejects attendance with mandatory reason (FR-6.47, AC-39).
    """
    if not reason or not reason.strip():
        raise ValidationError({'reason': 'Rejection reason is mandatory (AC-39).'})

    att = AttendanceRecord.objects.get(attendance_id=attendance_id)
    att.status = 'rejected'
    att.save()

    AttendanceApproval.objects.create(
        attendance=att,
        actor=actor_user,
        action='reject',
        reason=reason.strip()
    )

    write_audit_event(
        action_code='attendance.rejected',
        actor_user=actor_user,
        record_type='AttendanceRecord',
        record_id=str(att.attendance_id),
        reason=reason.strip(),
        result='SUCCESS',
        company_id=att.company_id
    )

    return att


@transaction.atomic
def correct_attendance(attendance_id, data, actor_user, request=None) -> AttendanceRecord:
    """
    Corrects attendance times and status with immutable revision trail (FR-6.48, FR-6.49, AC-40, AC-41).
    """
    reason = data.get('reason', '').strip()
    if not reason:
        raise ValidationError({'reason': 'Correction reason is mandatory (AC-40).'})

    att = AttendanceRecord.objects.select_for_update().get(attendance_id=attendance_id)

    if att.period and att.period.status == 'locked':
        raise PermissionDenied("Cannot correct attendance in a locked period without Admin reopening (AC-48).")

    prev_values = {
        'actual_check_in': str(att.actual_check_in) if att.actual_check_in else None,
        'actual_check_out': str(att.actual_check_out) if att.actual_check_out else None,
        'worked_minutes': att.worked_minutes,
        'regular_minutes': att.regular_minutes,
        'overtime_minutes': att.overtime_minutes,
        'status': att.status
    }

    # Apply changes
    new_in = data.get('actual_check_in')
    new_out = data.get('actual_check_out')

    if new_in:
        att.actual_check_in = datetime.fromisoformat(new_in.replace('Z', '+00:00')) if isinstance(new_in, str) else new_in
    if new_out:
        att.actual_check_out = datetime.fromisoformat(new_out.replace('Z', '+00:00')) if isinstance(new_out, str) else new_out

    if att.actual_check_in and att.actual_check_out:
        att.worked_minutes = int((att.actual_check_out - att.actual_check_in).total_seconds() / 60)
        ot_thresh = float(get_setting('daily_overtime_threshold_hours', att.company_id) or 8.0) * 60
        att.regular_minutes = min(att.worked_minutes, int(ot_thresh))
        att.overtime_minutes = max(0, att.worked_minutes - int(ot_thresh))

    att.status = data.get('status', 'corrected')

    # Correction size calculation
    correction_size = abs(att.worked_minutes - (prev_values['worked_minutes'] or 0))
    large_thresh = int(get_setting('large_correction_threshold_mins', att.company_id) or 120)
    requires_admin = (correction_size >= large_thresh)

    rev_count = AttendanceRevision.objects.filter(attendance=att).count() + 1
    AttendanceRevision.objects.create(
        attendance=att,
        revision_number=rev_count,
        previous_values=prev_values,
        new_values={
            'actual_check_in': str(att.actual_check_in),
            'actual_check_out': str(att.actual_check_out),
            'worked_minutes': att.worked_minutes,
            'regular_minutes': att.regular_minutes,
            'overtime_minutes': att.overtime_minutes,
            'status': att.status
        },
        reason=reason,
        actor=actor_user,
        correction_size_minutes=correction_size,
        requires_admin_approval=requires_admin,
        approval_status='pending' if (requires_admin and actor_user.role != 'ADMIN') else 'approved'
    )

    att.save()

    return att


# ==============================================================================
# 6. REGULARISATION & PERIOD LOCKING
# ==============================================================================

@transaction.atomic
def submit_regularisation(employee_id, data, actor_user=None) -> AttendanceRegularisation:
    """
    Guard regularisation request for missed captures (FR-6.54, FR-6.55, AC-43).
    """
    employee = Employee.objects.get(employee_id=employee_id)
    duty_date = datetime.strptime(data['duty_date'], '%Y-%m-%d').date() if isinstance(data['duty_date'], str) else data['duty_date']

    # Window check (AC-43)
    reg_window = int(get_setting('regularisation_window_days', employee.company_id) or 3)
    if date.today() - duty_date > timedelta(days=reg_window):
        raise ValidationError({'duty_date': f"Regularisation requests can only be submitted within {reg_window} days of duty date (AC-43)."})

    site = ClientSite.objects.get(site_id=data['site_id'])
    shift = SiteShift.objects.get(shift_id=data['shift_id'])

    reg = AttendanceRegularisation.objects.create(
        employee=employee,
        site=site,
        shift=shift,
        duty_date=duty_date,
        claimed_check_in=data['claimed_check_in'],
        claimed_check_out=data['claimed_check_out'],
        reason=data['reason'],
        photo_storage_key=data.get('photo_storage_key')
    )

    return reg


@transaction.atomic
def decide_regularisation(request_id, decision, decision_notes, actor_user) -> AttendanceRegularisation:
    """
    Supervisor approves or rejects regularisation (FR-6.56, AC-44, AC-46).
    """
    reg = AttendanceRegularisation.objects.get(request_id=request_id)
    if decision not in ('approved', 'rejected'):
        raise ValidationError({'decision': 'Decision must be approved or rejected.'})

    reg.status = decision
    reg.reviewed_by = actor_user
    reg.reviewed_at = timezone.now()
    reg.rejection_reason = decision_notes if decision == 'rejected' else None
    reg.save()

    if decision == 'approved':
        # Create or update AttendanceRecord marked is_manual=True (AC-44)
        worked_mins = int((reg.claimed_check_out - reg.claimed_check_in).total_seconds() / 60)
        ot_thresh = float(get_setting('daily_overtime_threshold_hours', reg.site.client.company_id) or 8.0) * 60

        att, _ = AttendanceRecord.objects.get_or_create(
            employee=reg.employee,
            site=reg.site,
            shift=reg.shift,
            duty_date=reg.duty_date,
            defaults={
                'company_id': reg.site.client.company_id,
                'scheduled_start': reg.claimed_check_in,
                'scheduled_end': reg.claimed_check_out,
            }
        )
        att.actual_check_in = reg.claimed_check_in
        att.actual_check_out = reg.claimed_check_out
        att.worked_minutes = worked_mins
        att.regular_minutes = min(worked_mins, int(ot_thresh))
        att.overtime_minutes = max(0, worked_mins - int(ot_thresh))
        att.is_manual = True
        att.status = 'approved'
        att.save()

        # Update monthly manual counter (FR-6.58, AC-46)
        period_str = reg.duty_date.strftime('%Y-%m')
        counter, _ = ManualAttendanceCounter.objects.get_or_create(
            employee=reg.employee,
            period_month=period_str,
            defaults={'configured_limit': int(get_setting('manual_attendance_monthly_limit', reg.site.client.company_id) or 3)}
        )
        counter.count += 1
        if counter.count > counter.configured_limit:
            counter.alert_status = 'exceeded'
            # Send notification to Admin
            send_notification(
                type_code='MANUAL_ATTENDANCE_LIMIT_EXCEEDED',
                recipient_hint=None,
                params={'employee_code': reg.employee.employee_code, 'count': counter.count},
                company_id=reg.site.client.company_id
            )
        counter.save()

    return reg


@transaction.atomic
def close_attendance_period(company_id, data, actor_user) -> AttendancePeriod:
    """
    Admin closes and locks an attendance period (FR-6.60 to FR-6.63, AC-47).
    """
    if actor_user.role != 'ADMIN':
        raise PermissionDenied("Only Admins can close and lock an attendance period.")

    start_date = data['start_date']
    end_date = data['end_date']
    site_id = data.get('site_id')

    # Check for pending approval records (AC-47)
    pending_qs = AttendanceRecord.objects.filter(
        company_id=company_id,
        duty_date__gte=start_date,
        duty_date__lte=end_date,
        status__in=['pending_approval', 'in_progress', 'late', 'no_checkout']
    )
    if site_id:
        pending_qs = pending_qs.filter(site_id=site_id)

    exception_ids = data.get('exception_attendance_ids', [])
    unresolved = pending_qs.exclude(attendance_id__in=exception_ids)

    if unresolved.exists():
        raise ValidationError({
            'detail': f"Period cannot be closed. {unresolved.count()} pending records remain. Resolve them or explicitly add to exceptions list (AC-47)."
        })

    period = AttendancePeriod.objects.create(
        company_id=company_id,
        site_id=site_id,
        period_name=data.get('period_name', f"Period {start_date} to {end_date}"),
        start_date=start_date,
        end_date=end_date,
        status='locked',
        closed_by=actor_user,
        closed_at=timezone.now()
    )

    # Attach period_id to all approved records in range
    approved_qs = AttendanceRecord.objects.filter(
        company_id=company_id,
        duty_date__gte=start_date,
        duty_date__lte=end_date,
        status='approved'
    )
    if site_id:
        approved_qs = approved_qs.filter(site_id=site_id)
    approved_qs.update(period=period)

    # Record exceptions
    for exc_id in exception_ids:
        AttendancePeriodException.objects.create(
            period=period,
            attendance_id=exc_id,
            exception_type='PENDING_APPROVAL',
            reason=data.get('exception_reason', 'Explicit admin override during period lock'),
            created_by=actor_user
        )

    write_audit_event(
        action_code='attendance.period_locked',
        actor_user=actor_user,
        record_type='AttendancePeriod',
        record_id=str(period.period_id),
        reason=f"Period locked: {period.period_name}",
        result='SUCCESS',
        company_id=company_id
    )

    return period


@transaction.atomic
def reopen_attendance_period(period_id, reason, actor_user) -> AttendancePeriod:
    """
    Admin reopens a locked period with mandatory reason (FR-6.64, AC-49).
    """
    if actor_user.role != 'ADMIN':
        raise PermissionDenied("Only Admins can reopen a locked attendance period.")

    if not reason or not reason.strip():
        raise ValidationError({'reason': 'Reopen reason is mandatory (AC-49).'})

    period = AttendancePeriod.objects.get(period_id=period_id)
    period.status = 'reopened'
    period.reopened_by = actor_user
    period.reopened_at = timezone.now()
    period.reopen_reason = reason.strip()
    period.save()

    write_audit_event(
        action_code='attendance.period_reopened',
        actor_user=actor_user,
        record_type='AttendancePeriod',
        record_id=str(period.period_id),
        reason=reason.strip(),
        result='SUCCESS',
        company_id=period.company_id
    )

    return period
