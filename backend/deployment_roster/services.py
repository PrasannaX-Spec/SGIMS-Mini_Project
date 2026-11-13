import uuid
import pytz
from datetime import datetime, date, time as dtime, timedelta
from decimal import Decimal
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError, PermissionDenied, NotFound

from master_data.models import Company, ClientSite, PostType, SiteShift, SiteManpowerRequirement
from guard_management.models import Employee
from guard_management import services as guard_services
from foundation.services.settings_service import get_setting
from foundation.services.audit_service import write_audit_event
from foundation.services.notification_service import send_notification
from .models import (
    PostSlot,
    Roster,
    RosterAssignment,
    AssignmentHistory,
    ShiftSwapRequest,
    EmergencyRatification,
    DutyAcknowledgement,
    OvertimeRecord,
    RelieverPoolMembership,
)

IST = pytz.timezone('Asia/Kolkata')


# ==============================================================================
# 1. INTERVAL & DATE CALCULATIONS (FR-5.22, E-03)
# ==============================================================================

def calculate_shift_interval(deployment_date, start_time_val, end_time_val):
    """
    Computes exact timezone-aware start and end datetime intervals.
    Correctly accounts for cross-midnight rollover (FR-5.22, AC-13, E-03).
    """
    if isinstance(deployment_date, str):
        deployment_date = datetime.strptime(deployment_date, '%Y-%m-%d').date()

    if isinstance(start_time_val, str):
        # Format HH:MM or HH:MM:SS
        parts = [int(p) for p in start_time_val.split(':')]
        start_time_val = dtime(parts[0], parts[1], parts[2] if len(parts) > 2 else 0)

    if isinstance(end_time_val, str):
        parts = [int(p) for p in end_time_val.split(':')]
        end_time_val = dtime(parts[0], parts[1], parts[2] if len(parts) > 2 else 0)

    start_naive = datetime.combine(deployment_date, start_time_val)
    start_dt = timezone.make_aware(start_naive, IST)

    # Cross-midnight check
    if end_time_val <= start_time_val:
        end_date = deployment_date + timedelta(days=1)
    else:
        end_date = deployment_date

    end_naive = datetime.combine(end_date, end_time_val)
    end_dt = timezone.make_aware(end_naive, IST)

    return start_dt, end_dt


# ==============================================================================
# 2. POST SLOT GENERATION ENGINE (FR-5.1 to FR-5.4, AC-01 to AC-05)
# ==============================================================================

def generate_slots_for_period(site_id, start_date, end_date, actor_user, request=None):
    """
    Generates post slots using active manpower requirements for a site.
    Idempotent: duplicate generation calls will not create duplicate slots (AC-01, AC-02, AC-03).
    """
    site = ClientSite.objects.get(site_id=site_id)
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

    if end_date < start_date:
        raise ValidationError({'end_date': 'End date must be greater than or equal to start date.'})

    requirements = SiteManpowerRequirement.objects.filter(
        site=site,
        is_active=True
    )

    created_count = 0
    curr_date = start_date

    with transaction.atomic():
        while curr_date <= end_date:
            day_name = curr_date.strftime('%a').upper()  # MON, TUE...

            for req in requirements:
                # Effective date check
                if req.effective_from and curr_date < req.effective_from:
                    continue
                if req.effective_to and curr_date > req.effective_to:
                    continue

                for seq in range(1, req.required_count + 1):
                    slot, created = PostSlot.objects.get_or_create(
                        company=site.client.company,
                        site=site,
                        shift=req.shift,
                        post_type=req.post_type,
                        deployment_date=curr_date,
                        slot_sequence=seq,
                        defaults={
                            'requirement': req,
                            'slot_status': 'open'
                        }
                    )
                    if created:
                        created_count += 1

            curr_date += timedelta(days=1)

    return {
        'site_id': str(site.site_id),
        'start_date': str(start_date),
        'end_date': str(end_date),
        'slots_generated': created_count
    }


def reconcile_slots_on_requirement_change(requirement_id, actor_user, request=None):
    """
    Reconciles future unassigned slots when a manpower requirement increases or decreases.
    Past slots and assigned slots remain protected (FR-5.3, AC-04, AC-05, E-01).
    """
    req = SiteManpowerRequirement.objects.get(requirement_id=requirement_id)
    today = date.today()

    # Cancel future unassigned slots that exceed the new required_count
    future_slots = PostSlot.objects.filter(
        requirement=req,
        deployment_date__gte=today,
        slot_status='open',
        slot_sequence__gt=req.required_count
    )
    cancelled_count = future_slots.update(slot_status='cancelled')

    return {'cancelled_unassigned_slots': cancelled_count}


# ==============================================================================
# 3. CONFLICT & FATIGUE VALIDATION ENGINE (FR-5.21 to FR-5.26, AC-12 to AC-18)
# ==============================================================================

def check_assignment_conflicts(employee_id, start_dt, end_dt, post_type_id, deployment_date, exclude_assignment_id=None):
    """
    Validates hard conflicts and soft fatigue warnings for an assignment.
    Hard conflicts cannot be overridden. Soft warnings require an audited Admin reason.
    """
    employee = Employee.objects.get(employee_id=employee_id)
    post_type = PostType.objects.get(post_type_id=post_type_id)
    company_id = employee.company_id

    errors = []
    warnings = []

    # 1. Hard Check: Module 3 Deployability
    dep = guard_services.is_guard_deployable_on_date(employee.employee_id, deployment_date, post_type_id=post_type_id)
    if not dep.get('deployable', False):
        reasons_list = dep.get('failure_reasons') or dep.get('reasons') or ['Failed Module 3 check']
        errors.append(f"Guard {employee.full_name} is not deployable: {', '.join(reasons_list)}")

    # 2. Hard Check: Armed post eligibility (AC-08, FR-5.10)
    if post_type.requires_armed_authorization:
        from guard_management.models import EmployeeDocument
        from django.db.models import Q
        arms_doc = EmployeeDocument.objects.filter(
            employee=employee,
            document_type='arms_licence',
            verification_status='verified',
            is_active=True
        ).filter(
            Q(expiry_date__isnull=True) | Q(expiry_date__gte=deployment_date)
        ).first()
        if not arms_doc:
            errors.append(f"Post {post_type.name} requires an armed security guard with a verified licence (AC-08).")

    # 3. Hard Check: Shift interval overlap (AC-12, AC-13, FR-5.21)
    overlap_qs = RosterAssignment.objects.filter(
        employee=employee,
        status__in=['scheduled', 'acknowledged', 'completed'],
        start_time__lt=end_dt,
        end_time__gt=start_dt
    )
    if exclude_assignment_id:
        overlap_qs = overlap_qs.exclude(assignment_id=exclude_assignment_id)

    overlap = overlap_qs.first()
    if overlap:
        errors.append(f"Shift collision: Guard is already assigned to {overlap.site.site_name} from {overlap.start_time.strftime('%Y-%m-%d %H:%M')} to {overlap.end_time.strftime('%Y-%m-%d %H:%M')} (AC-12).")

    if errors:
        return {'hard_blocked': True, 'errors': errors, 'warnings': warnings}

    # 4. Soft Warning 1: Minimum Rest Gap (AC-14, FR-5.23)
    min_rest_gap = int(get_setting('min_rest_gap_hours', company_id) or 8)
    prev_shift = RosterAssignment.objects.filter(
        employee=employee,
        status__in=['scheduled', 'acknowledged', 'completed'],
        end_time__lte=start_dt
    ).order_by('-end_time').first()

    if prev_shift:
        gap_hours = (start_dt - prev_shift.end_time).total_seconds() / 3600.0
        if gap_hours < min_rest_gap:
            warnings.append(f"Insufficient rest gap: Only {gap_hours:.1f} hours since prior shift at {prev_shift.site.site_name} (minimum recommended {min_rest_gap} hours).")

    # 5. Soft Warning 2: Consecutive Working Days (AC-15, FR-5.23)
    max_days = int(get_setting('max_consecutive_days', company_id) or 6)
    # Check backwards from deployment_date
    consecutive = 0
    check_day = deployment_date - timedelta(days=1)
    while consecutive < 14:
        has_duty = RosterAssignment.objects.filter(
            employee=employee,
            deployment_date=check_day,
            status__in=['scheduled', 'acknowledged', 'completed']
        ).exists()
        if has_duty:
            consecutive += 1
            check_day -= timedelta(days=1)
        else:
            break

    if consecutive >= max_days:
        warnings.append(f"Consecutive duty limit: Guard has worked {consecutive} consecutive days leading up to this shift (limit {max_days} days).")

    # 6. Soft Warning 3: Weekly Hours Limit (AC-16, FR-5.23)
    weekly_limit = float(get_setting('weekly_hours_warning_limit', company_id) or 48.0)
    week_start = deployment_date - timedelta(days=deployment_date.weekday())
    week_end = week_start + timedelta(days=6)

    existing_shifts = RosterAssignment.objects.filter(
        employee=employee,
        deployment_date__gte=week_start,
        deployment_date__lte=week_end,
        status__in=['scheduled', 'acknowledged', 'completed']
    )
    if exclude_assignment_id:
        existing_shifts = existing_shifts.exclude(assignment_id=exclude_assignment_id)

    curr_week_hours = sum(
        (s.end_time - s.start_time).total_seconds() / 3600.0 for s in existing_shifts
    )
    duty_hours = (end_dt - start_dt).total_seconds() / 3600.0

    if (curr_week_hours + duty_hours) > weekly_limit:
        warnings.append(f"Weekly hours threshold exceeded: Assignment brings weekly total to {curr_week_hours + duty_hours:.1f} hours (limit {weekly_limit:.0f} hours).")

    return {
        'hard_blocked': False,
        'errors': [],
        'warnings': warnings
    }


# ==============================================================================
# 4. ASSIGNMENT SERVICE (FR-5.5 to FR-5.12, AC-06 to AC-11, AC-17)
# ==============================================================================

def assign_guard_to_slot(slot_id, employee_id, assignment_type='regular', soft_override_reason=None, actor_user=None, request=None):
    """
    Assigns an eligible guard to a post slot.
    Generates a permanent unique assignment_id used by Module 6 (FR-5.7, AC-06, AC-41).
    """
    slot = PostSlot.objects.get(slot_id=slot_id)
    employee = Employee.objects.get(employee_id=employee_id)
    site = slot.site

    # Check site operational status (AC-10)
    if site.operational_status in ('suspended', 'closed'):
        raise ValidationError({'site': f"Cannot assign guards to {site.site_name} because site is {site.operational_status} (AC-10)."})

    # Check slot status
    if slot.slot_status not in ('open', 'at_risk'):
        raise ValidationError({'slot': f"Slot is already {slot.slot_status} (AC-09)."})

    # Check if duplicate assignment on this slot
    if RosterAssignment.objects.filter(slot=slot, employee=employee, status__in=['scheduled', 'acknowledged']).exists():
        raise ValidationError({'detail': 'Guard is already assigned to this slot (AC-09).'})

    # Calculate shift time boundaries
    shift = slot.shift
    start_dt, end_dt = calculate_shift_interval(slot.deployment_date, shift.start_time, shift.end_time)

    # Run conflict & fatigue validation
    validation = check_assignment_conflicts(
        employee_id=employee.employee_id,
        start_dt=start_dt,
        end_dt=end_dt,
        post_type_id=slot.post_type_id,
        deployment_date=slot.deployment_date
    )

    if validation['hard_blocked']:
        raise ValidationError({'hard_conflicts': validation['errors']})

    if validation['warnings'] and not soft_override_reason:
        raise ValidationError({
            'soft_warnings': validation['warnings'],
            'requires_override': True,
            'message': 'Soft fatigue warnings detected. An Admin override reason is required to proceed (AC-17).'
        })

    with transaction.atomic():
        assignment = RosterAssignment.objects.create(
            company=site.client.company,
            slot=slot,
            employee=employee,
            site=site,
            shift=shift,
            post_type=slot.post_type,
            deployment_date=slot.deployment_date,
            start_time=start_dt,
            end_time=end_dt,
            assignment_type=assignment_type,
            status='scheduled',
            created_by_user_id=actor_user.user_id if actor_user else None
        )

        slot.slot_status = 'filled'
        slot.save(update_fields=['slot_status', 'updated_at'])

        # Overtime flagging (FR-5.25)
        duty_hours = (end_dt - start_dt).total_seconds() / 3600.0
        daily_threshold = float(get_setting('daily_overtime_threshold_hours', site.client.company_id) or 8.0)
        if duty_hours > daily_threshold:
            OvertimeRecord.objects.create(
                assignment=assignment,
                threshold_type='daily',
                flagged_hours=Decimal(str(round(duty_hours - daily_threshold, 2))),
                approval_status='pending',
                reason='Scheduled shift hours exceed standard daily threshold'
            )

        # Append-only history record (FR-5.59, AC-25)
        AssignmentHistory.objects.create(
            assignment=assignment,
            action='created',
            new_values={
                'employee_code': employee.employee_code,
                'guard_name': employee.full_name,
                'site': site.site_name,
                'date': str(slot.deployment_date),
                'shift': shift.shift_name,
                'type': assignment_type,
                'soft_override': soft_override_reason
            },
            actor_user_id=actor_user.user_id if actor_user else None,
            reason=soft_override_reason or 'Initial roster slot assignment'
        )

    # Audit log (FR-5.26)
    write_audit_event(
        action_code='roster.assigned',
        actor_user=actor_user,
        module='deployment_roster',
        record_type='ROSTER_ASSIGNMENT',
        record_id=str(assignment.assignment_id),
        new_values={'slot_id': str(slot.slot_id), 'guard': employee.full_name, 'date': str(slot.deployment_date)},
        reason=f"Assigned guard {employee.employee_code} to {site.site_name} ({slot.deployment_date})",
        request=request
    )

    return assignment


def cancel_future_assignment(assignment_id, reason, actor_user, request=None):
    """
    Cancels a future scheduled assignment with preserved history (FR-5.12, AC-25, AC-29).
    Past locked assignments require the separate locked assignment protocol.
    """
    if not reason or not reason.strip():
        raise ValidationError({'reason': 'A mandatory cancellation reason must be provided (AC-25).'})

    assignment = RosterAssignment.objects.get(assignment_id=assignment_id)
    today = date.today()

    if assignment.deployment_date < today:
        raise ValidationError({'detail': 'Past assignments are locked and cannot be cancelled through regular workflow (AC-24).'})

    with transaction.atomic():
        old_status = assignment.status
        assignment.status = 'cancelled'
        assignment.save(update_fields=['status', 'updated_at'])

        slot = assignment.slot
        slot.slot_status = 'open'
        slot.save(update_fields=['slot_status', 'updated_at'])

        AssignmentHistory.objects.create(
            assignment=assignment,
            action='cancelled',
            previous_values={'status': old_status},
            new_values={'status': 'cancelled'},
            actor_user_id=actor_user.user_id if actor_user else None,
            reason=reason.strip()
        )

    write_audit_event(
        action_code='roster.cancelled',
        actor_user=actor_user,
        module='deployment_roster',
        record_type='ROSTER_ASSIGNMENT',
        record_id=str(assignment.assignment_id),
        new_values={'status': 'cancelled', 'reason': reason},
        reason=f"Cancelled assignment for {assignment.employee.full_name}: {reason}",
        request=request
    )

    return assignment


# ==============================================================================
# 5. REPLACEMENT & ABSENCE WORKFLOW (FR-5.35 to FR-5.40, AC-30 to AC-33)
# ==============================================================================

def create_replacement_assignment(original_assignment_id, replacement_employee_id, reason, actor_user, request=None):
    """
    Creates a replacement assignment linked to the original assignment (AC-31, FR-5.38).
    Preserves original assignment identifier and tracks reason.
    """
    if not reason or not reason.strip():
        raise ValidationError({'reason': 'Replacement reason is mandatory.'})

    orig = RosterAssignment.objects.get(assignment_id=original_assignment_id)
    rep_guard = Employee.objects.get(employee_id=replacement_employee_id)
    slot = orig.slot

    # Validate replacement guard
    validation = check_assignment_conflicts(
        employee_id=rep_guard.employee_id,
        start_dt=orig.start_time,
        end_dt=orig.end_time,
        post_type_id=orig.post_type_id,
        deployment_date=orig.deployment_date
    )
    if validation['hard_blocked']:
        raise ValidationError({'hard_conflicts': validation['errors']})

    with transaction.atomic():
        # Update original assignment status
        orig_old_status = orig.status
        orig.status = 'no_show' if orig.deployment_date <= date.today() else 'cancelled'
        orig.save(update_fields=['status', 'updated_at'])

        AssignmentHistory.objects.create(
            assignment=orig,
            action='replaced',
            previous_values={'status': orig_old_status},
            new_values={'status': orig.status, 'replaced_by': rep_guard.full_name},
            actor_user_id=actor_user.user_id if actor_user else None,
            reason=reason.strip()
        )

        # Create linked replacement assignment
        replacement = RosterAssignment.objects.create(
            company=orig.company,
            slot=slot,
            roster=orig.roster,
            employee=rep_guard,
            site=orig.site,
            shift=orig.shift,
            post_type=orig.post_type,
            deployment_date=orig.deployment_date,
            start_time=orig.start_time,
            end_time=orig.end_time,
            assignment_type='replacement',
            status='scheduled',
            original_assignment=orig,
            created_by_user_id=actor_user.user_id if actor_user else None
        )

        slot.slot_status = 'filled'
        slot.save(update_fields=['slot_status', 'updated_at'])

        AssignmentHistory.objects.create(
            assignment=replacement,
            action='created',
            new_values={'type': 'replacement', 'linked_to': str(orig.assignment_id)},
            actor_user_id=actor_user.user_id if actor_user else None,
            reason=f"Replacement for {orig.employee.full_name}: {reason}"
        )

    # High-priority notification to replacement guard (FR-5.38)
    if hasattr(rep_guard, 'user') and rep_guard.user:
        try:
            send_notification(
                type_code='POLICY_UPDATED',
                recipient_hint=rep_guard.user,
                params={'title': 'Urgent: Replacement Duty Assigned', 'body': f"Assigned as replacement at {orig.site.site_name} on {orig.deployment_date}"},
                company_id=orig.company_id
            )
        except Exception:
            pass

    return replacement


def report_no_show_from_module6(assignment_id, detection_timestamp, reason="No check-in detected", actor_user=None, request=None):
    """
    Interface called by Module 6 attendance when a guard fails to check in (FR-5.36, AC-30, Section 10.5).
    Marks assignment as no_show, slot as at_risk, and alerts the supervisor.
    """
    assignment = RosterAssignment.objects.get(assignment_id=assignment_id)
    slot = assignment.slot

    with transaction.atomic():
        assignment.status = 'no_show'
        assignment.save(update_fields=['status', 'updated_at'])

        slot.slot_status = 'at_risk'
        slot.save(update_fields=['slot_status', 'updated_at'])

        AssignmentHistory.objects.create(
            assignment=assignment,
            action='no_show',
            previous_values={'status': 'scheduled'},
            new_values={'status': 'no_show'},
            actor_user_id=actor_user.user_id if actor_user else None,
            reason=reason
        )

    write_audit_event(
        action_code='roster.no_show',
        actor_user=actor_user,
        module='deployment_roster',
        record_type='ROSTER_ASSIGNMENT',
        record_id=str(assignment.assignment_id),
        new_values={'status': 'no_show'},
        reason=f"No-show recorded for {assignment.employee.full_name} at {assignment.site.site_name}",
        request=request
    )

    return {'assignment_id': str(assignment.assignment_id), 'slot_status': 'at_risk'}


# ==============================================================================
# 6. SHIFT SWAP WORKFLOW (FR-5.41 to FR-5.43, AC-34 to AC-35)
# ==============================================================================

def request_shift_swap(assignment_a_id, target_employee_id, assignment_b_id, reason, requesting_guard_user):
    """
    Submits a shift swap request between two guards at the same site (AC-34, AC-35).
    """
    assign_a = RosterAssignment.objects.get(assignment_id=assignment_a_id)
    assign_b = RosterAssignment.objects.get(assignment_id=assignment_b_id)
    target_guard = Employee.objects.get(employee_id=target_employee_id)

    # Must be at the same site (FR-5.41, AC-34)
    if assign_a.site_id != assign_b.site_id:
        raise ValidationError({'site': 'Shift swaps can only be requested between duties at the exact same site (AC-34).'})

    swap = ShiftSwapRequest.objects.create(
        company=assign_a.company,
        site=assign_a.site,
        requesting_employee=assign_a.employee,
        target_employee=target_guard,
        assignment_a=assign_a,
        assignment_b=assign_b,
        reason=reason,
        status='pending'
    )

    return swap


def approve_shift_swap(swap_id, supervisor_user, request=None):
    """
    Atomically approves a shift swap and exchanges guard assignments (AC-34, AC-35).
    Crucial: Permanent assignment_id values remain identical and stable for Module 6.
    """
    swap = ShiftSwapRequest.objects.get(swap_id=swap_id)
    if swap.status != 'pending':
        raise ValidationError({'status': f"Swap request is already {swap.status}."})

    assign_a = swap.assignment_a
    assign_b = swap.assignment_b
    guard_a = assign_a.employee
    guard_b = assign_b.employee

    # Re-validate Guard B for Assignment A's shift
    val_b = check_assignment_conflicts(
        employee_id=guard_b.employee_id,
        start_dt=assign_a.start_time,
        end_dt=assign_a.end_time,
        post_type_id=assign_a.post_type_id,
        deployment_date=assign_a.deployment_date,
        exclude_assignment_id=assign_b.assignment_id
    )
    if val_b['hard_blocked']:
        swap.status = 'rejected'
        swap.save()
        raise ValidationError({'detail': f"Swap rejected: Guard {guard_b.full_name} cannot cover shift A: {', '.join(val_b['errors'])} (AC-35)."})

    # Re-validate Guard A for Assignment B's shift
    val_a = check_assignment_conflicts(
        employee_id=guard_a.employee_id,
        start_dt=assign_b.start_time,
        end_dt=assign_b.end_time,
        post_type_id=assign_b.post_type_id,
        deployment_date=assign_b.deployment_date,
        exclude_assignment_id=assign_a.assignment_id
    )
    if val_a['hard_blocked']:
        swap.status = 'rejected'
        swap.save()
        raise ValidationError({'detail': f"Swap rejected: Guard {guard_a.full_name} cannot cover shift B: {', '.join(val_a['errors'])} (AC-35)."})

    with transaction.atomic():
        # Atomically swap guards
        assign_a.employee = guard_b
        assign_a.save(update_fields=['employee', 'updated_at'])

        assign_b.employee = guard_a
        assign_b.save(update_fields=['employee', 'updated_at'])

        AssignmentHistory.objects.create(
            assignment=assign_a,
            action='swapped',
            previous_values={'guard': guard_a.full_name},
            new_values={'guard': guard_b.full_name},
            actor_user_id=supervisor_user.user_id if supervisor_user else None,
            reason=f"Approved shift swap #{swap.swap_id}"
        )
        AssignmentHistory.objects.create(
            assignment=assign_b,
            action='swapped',
            previous_values={'guard': guard_b.full_name},
            new_values={'guard': guard_a.full_name},
            actor_user_id=supervisor_user.user_id if supervisor_user else None,
            reason=f"Approved shift swap #{swap.swap_id}"
        )

        swap.status = 'approved'
        swap.reviewed_by_user_id = supervisor_user.user_id if supervisor_user else None
        swap.reviewed_at = timezone.now()
        swap.save(update_fields=['status', 'reviewed_by_user_id', 'reviewed_at'])

    return swap


# ==============================================================================
# 7. EMERGENCY DEPLOYMENT (FR-5.40, AC-33, E-13)
# ==============================================================================

def create_emergency_deployment(site_id, shift_id, post_type_id, deployment_date, employee_id, reason, supervisor_user, request=None):
    """
    Supervisor urgent emergency deployment.
    Non-negotiable rule: Emergency deployments MUST still obey all hard conflict checks (AC-33).
    Requires Admin ratification within 24 hours.
    """
    if not reason or not reason.strip():
        raise ValidationError({'reason': 'Emergency deployment reason is mandatory.'})

    site = ClientSite.objects.get(site_id=site_id)
    shift = SiteShift.objects.get(shift_id=shift_id)
    post_type = PostType.objects.get(post_type_id=post_type_id)
    employee = Employee.objects.get(employee_id=employee_id)

    start_dt, end_dt = calculate_shift_interval(deployment_date, shift.start_time, shift.end_time)

    # Enforce hard conflict check
    validation = check_assignment_conflicts(
        employee_id=employee.employee_id,
        start_dt=start_dt,
        end_dt=end_dt,
        post_type_id=post_type.post_type_id,
        deployment_date=deployment_date
    )
    if validation['hard_blocked']:
        raise ValidationError({'hard_conflicts': validation['errors']})

    with transaction.atomic():
        # Find or create slot
        slot = PostSlot.objects.filter(
            site=site,
            shift=shift,
            post_type=post_type,
            deployment_date=deployment_date,
            slot_status='open'
        ).first()

        if not slot:
            slot = PostSlot.objects.create(
                company=site.client.company,
                site=site,
                shift=shift,
                post_type=post_type,
                deployment_date=deployment_date,
                slot_sequence=99,  # Emergency sequence
                slot_status='filled'
            )
        else:
            slot.slot_status = 'filled'
            slot.save(update_fields=['slot_status', 'updated_at'])

        assignment = RosterAssignment.objects.create(
            company=site.client.company,
            slot=slot,
            employee=employee,
            site=site,
            shift=shift,
            post_type=post_type,
            deployment_date=deployment_date,
            start_time=start_dt,
            end_time=end_dt,
            assignment_type='standby',
            status='scheduled',
            is_emergency=True,
            created_by_user_id=supervisor_user.user_id if supervisor_user else None
        )

        # 24 hour deadline for Admin ratification (FR-5.40, AC-33)
        hours = int(get_setting('emergency_ratification_hours', site.client.company_id) or 24)
        EmergencyRatification.objects.create(
            assignment=assignment,
            supervisor_user_id=supervisor_user.user_id,
            reason=reason.strip(),
            status='pending',
            deadline=timezone.now() + timedelta(hours=hours)
        )

        AssignmentHistory.objects.create(
            assignment=assignment,
            action='created',
            new_values={'is_emergency': True, 'reason': reason},
            actor_user_id=supervisor_user.user_id if supervisor_user else None,
            reason=f"Emergency deployment: {reason}"
        )

    return assignment


def ratify_emergency_deployment(ratification_id, decision, admin_user, request=None):
    """
    Admin ratifies or rejects an emergency deployment (AC-33).
    """
    rat = EmergencyRatification.objects.get(ratification_id=ratification_id)
    if rat.status not in ('pending', 'overdue'):
        raise ValidationError({'status': f"Ratification is already {rat.status}."})

    if decision not in ('ratified', 'rejected'):
        raise ValidationError({'decision': "Decision must be 'ratified' or 'rejected'."})

    with transaction.atomic():
        rat.status = decision
        rat.admin_user_id = admin_user.user_id
        rat.reviewed_at = timezone.now()
        rat.save(update_fields=['status', 'admin_user_id', 'reviewed_at'])

        if decision == 'rejected':
            # Cancel emergency assignment
            cancel_future_assignment(
                assignment_id=rat.assignment.assignment_id,
                reason='Emergency deployment rejected by Admin',
                actor_user=admin_user,
                request=request
            )

    return rat


# ==============================================================================
# 8. PUBLISHING & DUTY ACKNOWLEDGEMENT (FR-5.27 to FR-5.34, AC-19 to AC-25)
# ==============================================================================

def publish_roster(site_id, start_date, end_date, actor_user, request=None):
    """
    Publishes a roster for a site and date range (AC-20, AC-21).
    Makes assignments visible to guards and dispatches notification batch.
    """
    site = ClientSite.objects.get(site_id=site_id)
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

    with transaction.atomic():
        roster, created = Roster.objects.get_or_create(
            site=site,
            start_date=start_date,
            end_date=end_date,
            defaults={
                'company': site.client.company,
                'status': 'published',
                'published_by': actor_user.user_id if actor_user else None,
                'published_at': timezone.now()
            }
        )

        if not created:
            roster.status = 'published'
            roster.published_by = actor_user.user_id if actor_user else None
            roster.published_at = timezone.now()
            roster.save(update_fields=['status', 'published_by', 'published_at', 'updated_at'])

        assignments = RosterAssignment.objects.filter(
            site=site,
            deployment_date__gte=start_date,
            deployment_date__lte=end_date
        )
        assignments.update(roster=roster)

    # Dispatch notifications to unique assigned guards (FR-5.29)
    guard_employees = set(a.employee for a in assignments)
    for g in guard_employees:
        if hasattr(g, 'user') and g.user:
            try:
                send_notification(
                    type_code='POLICY_UPDATED',
                    recipient_hint=g.user,
                    params={'title': 'Duty Roster Published', 'body': f"Duty schedule for {site.site_name} is live."},
                    company_id=site.client.company_id
                )
            except Exception:
                pass

    write_audit_event(
        action_code='roster.published',
        actor_user=actor_user,
        module='deployment_roster',
        record_type='ROSTER',
        record_id=str(roster.roster_id),
        new_values={'site': site.site_name, 'start_date': str(start_date), 'end_date': str(end_date)},
        reason=f"Published roster for {site.site_name} from {start_date} to {end_date}",
        request=request
    )

    return roster


def acknowledge_duty(assignment_id, guard_user, device_id=None, ip_address=None):
    """
    Guard digital duty receipt and acknowledgement (AC-23, FR-5.33).
    """
    assignment = RosterAssignment.objects.get(assignment_id=assignment_id)
    guard = assignment.employee

    # Verify matching user
    if guard_user.role == 'GUARD' and str(guard_user.guard_profile_id) != str(guard.employee_id):
        raise PermissionDenied("You can only acknowledge duties assigned to yourself (AC-39).")

    with transaction.atomic():
        ack, created = DutyAcknowledgement.objects.get_or_create(
            assignment=assignment,
            employee=guard,
            defaults={
                'device_id': device_id,
                'ip_address': ip_address
            }
        )

        assignment.status = 'acknowledged'
        assignment.save(update_fields=['status', 'updated_at'])

        AssignmentHistory.objects.create(
            assignment=assignment,
            action='updated',
            previous_values={'status': 'scheduled'},
            new_values={'status': 'acknowledged'},
            actor_user_id=guard_user.user_id,
            reason="Guard digital acknowledgement"
        )

    return ack


def edit_locked_assignment(assignment_id, new_guard_id, mandatory_reason, admin_user, request=None):
    """
    Admin-only override of past locked assignments (FR-5.34, AC-24, AC-25).
    Original record is preserved in history, reason is required, audit trail is recorded.
    """
    if admin_user.role not in ('ADMIN', 'SUPER_ADMIN'):
        raise PermissionDenied("Only Admin can edit locked past assignments (AC-24, AC-25).")

    if not mandatory_reason or not mandatory_reason.strip():
        raise ValidationError({'reason': 'A mandatory justification reason is required to alter locked assignments (AC-25).'})

    assignment = RosterAssignment.objects.get(assignment_id=assignment_id)
    new_guard = Employee.objects.get(employee_id=new_guard_id)
    old_guard_name = assignment.employee.full_name

    with transaction.atomic():
        assignment.employee = new_guard
        assignment.save(update_fields=['employee', 'updated_at'])

        AssignmentHistory.objects.create(
            assignment=assignment,
            action='locked',
            previous_values={'employee': old_guard_name},
            new_values={'employee': new_guard.full_name},
            actor_user_id=admin_user.user_id,
            reason=mandatory_reason.strip()
        )

    write_audit_event(
        action_code='roster.locked_edit',
        actor_user=admin_user,
        module='deployment_roster',
        record_type='ROSTER_ASSIGNMENT',
        record_id=str(assignment.assignment_id),
        new_values={'new_guard': new_guard.full_name, 'reason': mandatory_reason},
        reason=f"Admin edited locked assignment {assignment.assignment_id}: {mandatory_reason}",
        request=request
    )

    return assignment
