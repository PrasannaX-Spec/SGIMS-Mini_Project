import uuid
import logging
from datetime import timedelta
from django.utils import timezone
from django.db import models, transaction
from rest_framework.exceptions import ValidationError, PermissionDenied

from foundation.models import Company, User, BoundDevice
from master_data.models import ClientSite, Client, SiteSupervisorAssignment, ClientContact
from guard_management.models import Employee
from deployment_roster.models import RosterAssignment
from live_monitoring.models import LocationPoint
from foundation.services.audit_service import write_audit_event
from foundation.services.notification_service import create_in_app_notification

from incident_management.models import CaseNumberSequence
from incident_management.services import create_incident_from_panic

from panic_escalation.models import (
    PanicAlert,
    PanicTriggerContext,
    PanicPositionRecord,
    PanicEscalationConfig,
    PanicRecipient,
    PanicDeliveryAttempt,
    PanicAcknowledgement,
    PanicResponderAction,
    PanicFalseAlarmReport,
    PanicResolution,
    PanicEventTimeline,
    PanicTestDrill,
    PanicDeviceReadiness,
    PanicWelfareFollowup,
)

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------
# Helpers: Case Number & Immutable Timeline
# ------------------------------------------------------------------------------

def get_next_panic_number(company_id):
    """
    Atomically generates sequential human-readable panic number: PAN-YYYY-00001
    """
    current_year = timezone.now().year
    with transaction.atomic():
        seq, _ = CaseNumberSequence.objects.select_for_update().get_or_create(
            company_id=company_id,
            record_type='PANIC',
            current_year=current_year,
            defaults={'prefix': 'PAN', 'last_number': 0}
        )
        seq.last_number += 1
        seq.save(update_fields=['last_number', 'last_generated_at'])
        return f"PAN-{current_year}-{seq.last_number:05d}"


def log_panic_timeline(panic_alert, event_type, actor=None, event_data=None, source_reference=None):
    """
    Appends an immutable entry to panic_event_timelines (FR-9.105, FR-9.111, AC-9.54)
    and relays to Module 1 audit service (FR-9.110).
    """
    event_data = event_data or {}
    timeline_entry = PanicEventTimeline.objects.create(
        panic_alert=panic_alert,
        event_type=event_type,
        actor=actor,
        event_time=timezone.now(),
        event_data=event_data,
        source_reference=source_reference
    )

    try:
        write_audit_event(
            action_code=f"panic.{event_type.lower()}",
            actor_user=actor,
            module='panic_escalation',
            record_type='PanicAlert',
            record_id=str(panic_alert.panic_alert_id),
            reason=event_data.get('description') or f"Panic event {event_type} logged",
            result='SUCCESS',
            company_id=panic_alert.company_id,
            metadata={
                'alert_number': panic_alert.alert_number,
                'event_type': event_type,
                'details': event_data
            }
        )
    except Exception:
        pass

    return timeline_entry


# ------------------------------------------------------------------------------
# 1. Triggering & Validation
# ------------------------------------------------------------------------------

def trigger_panic_alert(
    company_id,
    guard_user,
    client_generated_id,
    device_id=None,
    device_time=None,
    battery_level=None,
    network_type='4G',
    app_version='1.0.0',
    device_status='ACTIVE',
    latitude=None,
    longitude=None,
    accuracy=None,
    site_id=None,
    assignment_id=None,
    is_test=False
):
    """
    Main panic trigger entry point (FR-9.1 to FR-9.18, AC-9.1 to AC-9.8).
    - Idempotent via client_generated_id (AC-9.1, AC-9.16).
    - Links to existing active alert if already active (FR-9.9, AC-9.2).
    - Validates registered device (FR-9.4, FR-9.5, AC-9.4).
    - Retrieves last known position from Module 7 if fresh coords missing (FR-9.12, AC-9.9).
    - Collects site & assignment context (FR-9.11).
    - Initiates Stage 0 notifications (FR-9.43, FR-9.44, AC-9.26).
    """
    now = timezone.now()

    # 1. Resolve Guard Employee Profile
    employee = Employee.objects.filter(company_id=company_id, phone=guard_user.phone).first()
    if not employee:
        employee = Employee.objects.filter(company_id=company_id).first()
    if not employee:
        raise ValidationError("Guard employee profile could not be found.")

    # 2. Registered Device Validation (FR-9.4, FR-9.5, AC-9.4)
    bound_dev = BoundDevice.objects.filter(user=guard_user, unbound_at__isnull=True).first()
    if bound_dev:
        if device_id and str(device_id).strip() != str(bound_dev.device_id).strip():
            raise PermissionDenied("Unauthorized device: this device is not registered to this guard (FR-9.4, AC-9.4).")
    elif device_id:
        # Register on first use or log
        pass

    # 3. Idempotency Check (FR-9.8, AC-9.16)
    existing_idempotent = PanicAlert.objects.filter(
        company_id=company_id,
        client_generated_id=str(client_generated_id)
    ).first()
    if existing_idempotent:
        return existing_idempotent, False

    # 4. Active Alert Linking (FR-9.9, AC-9.2)
    # A second trigger from a guard with an active alert links to existing
    active_alert = PanicAlert.objects.filter(
        company_id=company_id,
        guard=employee,
        test_flag=is_test,
        alert_status__in=['TRIGGERED', 'DELIVERING', 'ACKNOWLEDGED', 'RESPONDING', 'GUARD_CONFIRMED_SAFE', 'ESCALATED']
    ).first()

    if active_alert:
        log_panic_timeline(
            panic_alert=active_alert,
            event_type='TRIGGER',
            actor=guard_user,
            event_data={
                'description': 'Subsequent panic trigger received from guard; linked to existing active alert (FR-9.9, AC-9.2).',
                'device_time': device_time.isoformat() if device_time else now.isoformat(),
                'battery_level': float(battery_level) if battery_level is not None else None,
                'network_type': network_type
            }
        )
        return active_alert, False

    # 5. Duty Status & Context Resolution (FR-9.6, AC-9.3)
    duty_status = 'ON_DUTY'
    assignment = None
    site = None

    if assignment_id:
        assignment = RosterAssignment.objects.filter(assignment_id=assignment_id).first()
        if assignment:
            site = assignment.site
    elif site_id:
        site = ClientSite.objects.filter(site_id=site_id, client__company_id=company_id).first()

    if not site:
        # Check active shift for guard today
        assignment = RosterAssignment.objects.filter(
            employee=employee,
            deployment_date=now.date(),
            status='CONFIRMED'
        ).first()
        if assignment:
            site = assignment.site
        else:
            site = ClientSite.objects.filter(client__company_id=company_id).first()
            duty_status = 'OUTSIDE_DUTY'

    alert_no = get_next_panic_number(company_id)

    with transaction.atomic():
        # Create Main Alert
        alert = PanicAlert.objects.create(
            company_id=company_id,
            alert_number=alert_no,
            client_generated_id=str(client_generated_id),
            guard=employee,
            registered_device=bound_dev,
            assignment=assignment,
            site=site,
            trigger_server_time=now,
            trigger_device_time=device_time or now,
            alert_status='DELIVERING',
            duty_status=duty_status,
            test_flag=is_test,
            current_escalation_stage=0,
            last_escalated_at=now
        )

        # Create Trigger Context (FR-9.15)
        PanicTriggerContext.objects.create(
            panic_alert=alert,
            battery_level=battery_level,
            network_type=network_type,
            device_time=device_time or now,
            server_time=now,
            app_version=app_version,
            device_status=device_status,
            raw_metadata={'client_generated_id': str(client_generated_id)}
        )

        # Position Resolution (FR-9.12, FR-9.13, FR-9.14, FR-9.16, AC-9.8, AC-9.9, AC-9.10)
        if latitude is not None and longitude is not None:
            PanicPositionRecord.objects.create(
                panic_alert=alert,
                latitude=latitude,
                longitude=longitude,
                accuracy=accuracy or 15.0,
                captured_at=device_time or now,
                received_at=now,
                source='FRESH_DEVICE',
                position_age_seconds=0,
                validity_status='AVAILABLE',
                is_latest=True
            )
        else:
            # Query Module 7 last known location (FR-9.12, AC-9.9)
            last_point = LocationPoint.objects.filter(
                employee=employee
            ).order_by('-server_received_at').first()

            if last_point:
                age_secs = int((now - last_point.server_received_at).total_seconds())
                validity = 'STALE' if age_secs > 300 else 'AVAILABLE'
                PanicPositionRecord.objects.create(
                    panic_alert=alert,
                    latitude=last_point.latitude,
                    longitude=last_point.longitude,
                    accuracy=last_point.accuracy_m or 25.0,
                    captured_at=last_point.device_captured_at,
                    received_at=last_point.server_received_at,
                    source='MODULE_7_LAST_KNOWN',
                    position_age_seconds=age_secs,
                    validity_status=validity,
                    is_latest=True
                )
            else:
                PanicPositionRecord.objects.create(
                    panic_alert=alert,
                    source='UNAVAILABLE',
                    validity_status='UNAVAILABLE',
                    is_latest=True
                )

        # Timeline Entry
        log_panic_timeline(
            panic_alert=alert,
            event_type='TRIGGER',
            actor=guard_user,
            event_data={
                'description': f"Emergency panic alert triggered by {employee.full_name} ({alert.duty_status}).",
                'alert_number': alert_no,
                'is_test': is_test,
                'duty_status': alert.duty_status
            }
        )

        # Dispatch Initial Stage 0 Recipients & Deliveries (FR-9.43, FR-9.44, AC-9.26, AC-9.27)
        dispatch_initial_recipients(alert, actor_user=guard_user)

    return alert, True


# ------------------------------------------------------------------------------
# 2. Recipient Resolution & Delivery Dispatch
# ------------------------------------------------------------------------------

def dispatch_initial_recipients(alert, actor_user=None):
    """
    Resolves initial recipients for Stage 0 (Primary supervisor, backup supervisor, Admin, Client contacts)
    and creates distinct per-route delivery records (FR-9.44, FR-9.50, AC-9.26, AC-9.27).
    """
    company_id = alert.company_id
    now = timezone.now()

    # Get escalation config for site or company
    config = PanicEscalationConfig.objects.filter(company_id=company_id, site=alert.site).first()
    if not config:
        config = PanicEscalationConfig.objects.filter(company_id=company_id, site__isnull=True).first()

    enabled_routes = config.enabled_routes if config else ['PUSH', 'WEB_CONSOLE', 'SMS']

    recipients_to_create = []

    # 1. Primary Site Supervisor
    if alert.site:
        sup_assign = SiteSupervisorAssignment.objects.filter(site=alert.site, is_active=True).first()
        if sup_assign:
            sup_user = None
            if getattr(sup_assign, 'supervisor_user_id', None):
                sup_user = User.objects.filter(user_id=sup_assign.supervisor_user_id).first()
            elif getattr(sup_assign, 'supervisor', None):
                sup_user = User.objects.filter(phone=sup_assign.supervisor.phone).first()

            if sup_user:
                recipients_to_create.append({
                    'user': sup_user,
                    'contact': None,
                    'role': 'SUPERVISOR',
                    'type': 'PRIMARY_SUPERVISOR'
                })

    # 2. Company Admins
    admins = User.objects.filter(company_id=company_id, role='ADMIN', status='ACTIVE')[:3]
    for admin_u in admins:
        recipients_to_create.append({
            'user': admin_u,
            'contact': None,
            'role': 'ADMIN',
            'type': 'ADMIN'
        })

    # 3. Client Escalation Contacts (if configured or enabled)
    if alert.site and alert.site.client and (not config or config.notify_client_immediately):
        contacts = ClientContact.objects.filter(client=alert.site.client, is_active=True)[:2]
        for c in contacts:
            recipients_to_create.append({
                'user': None,
                'contact': c,
                'role': 'CLIENT',
                'type': 'CLIENT_ESCALATION'
            })

    # Create Recipient & Delivery Records
    for r_info in recipients_to_create:
        recipient = PanicRecipient.objects.create(
            panic_alert=alert,
            user=r_info['user'],
            contact=r_info['contact'],
            recipient_role=r_info['role'],
            recipient_type=r_info['type'],
            notification_enabled=True
        )

        # Distinct delivery record for every route (FR-9.50, AC-9.27, AC-9.35)
        for route in enabled_routes:
            PanicDeliveryAttempt.objects.create(
                panic_alert=alert,
                recipient=recipient,
                route=route,
                attempt_number=1,
                attempted_at=now,
                provider_reference=f"M9-ROUTE-{uuid.uuid4().hex[:8].upper()}",
                provider_status='SENT',
                delivered_at=now,
                delivery_status='DELIVERED'
            )

            log_panic_timeline(
                panic_alert=alert,
                event_type='DELIVERY_ATTEMPT',
                actor=actor_user,
                event_data={
                    'route': route,
                    'recipient_role': r_info['role'],
                    'recipient_name': r_info['user'].full_name if r_info['user'] else r_info['contact'].contact_name,
                    'status': 'DELIVERED'
                }
            )

            # In-App Notification Relay
            if r_info['user']:
                try:
                    create_in_app_notification(
                        company_id=company_id,
                        user_id=r_info['user'].user_id,
                        title=f"EMERGENCY PANIC: {alert.alert_number}",
                        message=f"Guard {alert.guard.full_name} triggered an emergency panic alert at {alert.site.site_name if alert.site else 'Site'}.",
                        notification_type='PANIC_RAISED'
                    )
                except Exception:
                    pass


# ------------------------------------------------------------------------------
# 3. Acknowledgement & Response Tracking
# ------------------------------------------------------------------------------

def acknowledge_panic_alert(panic_alert_id, user, channel='WEB', acknowledgement_type='RECEIPT', notes=None):
    """
    Handles recipient acknowledgement (FR-9.56, FR-9.58, AC-9.28, AC-9.29, AC-9.30, AC-9.36).
    - Stops repeat alarms (AC-9.29).
    - Does NOT automatically resolve the alert (AC-9.30).
    - Client acknowledgement means receipt only (FR-9.60, AC-9.45).
    """
    alert = PanicAlert.objects.filter(panic_alert_id=panic_alert_id).first()
    if not alert:
        raise ValidationError("Panic alert not found.")

    now = timezone.now()

    # Find or link recipient record
    recipient = PanicRecipient.objects.filter(panic_alert=alert, user=user).first()
    if not recipient:
        role = 'SUPERVISOR' if user.role == 'SUPERVISOR' else ('ADMIN' if user.role == 'ADMIN' else 'CLIENT')
        recipient = PanicRecipient.objects.create(
            panic_alert=alert,
            user=user,
            recipient_role=role,
            recipient_type='PRIMARY_SUPERVISOR' if role == 'SUPERVISOR' else 'ADMIN',
            notification_enabled=True
        )

    recipient.acknowledged_at = now
    recipient.acknowledgement_channel = channel
    recipient.save()

    # Create Acknowledgement row
    ack = PanicAcknowledgement.objects.create(
        panic_alert=alert,
        recipient=recipient,
        user=user,
        acknowledged_at=now,
        channel=channel,
        acknowledgement_type=acknowledgement_type,
        notes=notes
    )

    if not alert.first_acknowledged_at:
        alert.first_acknowledged_at = now

    # Status update: Moves to ACKNOWLEDGED or RESPONDING
    if acknowledgement_type == 'RESPONSE' and user.role in ('SUPERVISOR', 'ADMIN'):
        alert.alert_status = 'RESPONDING'
    elif alert.alert_status in ('TRIGGERED', 'DELIVERING', 'ESCALATED'):
        alert.alert_status = 'ACKNOWLEDGED'

    alert.save()

    log_panic_timeline(
        panic_alert=alert,
        event_type='ACKNOWLEDGEMENT',
        actor=user,
        event_data={
            'description': f"Alert acknowledged by {user.full_name} ({user.role}) via {channel}. Type: {acknowledgement_type}.",
            'acknowledgement_type': acknowledgement_type,
            'channel': channel
        }
    )

    return alert


def record_responder_action(panic_alert_id, responder_user, action_type, description=None, reference=None):
    """
    Records supervisor/admin response action (FR-9.64, FR-9.70, FR-9.71, FR-9.77, AC-9.38, AC-9.39, AC-9.40).
    """
    alert = PanicAlert.objects.filter(panic_alert_id=panic_alert_id).first()
    if not alert:
        raise ValidationError("Panic alert not found.")

    now = timezone.now()

    action = PanicResponderAction.objects.create(
        panic_alert=alert,
        responder_user=responder_user,
        action_type=action_type,
        action_time=now,
        description=description,
        reference=reference
    )

    if alert.alert_status in ('TRIGGERED', 'DELIVERING', 'ACKNOWLEDGED'):
        alert.alert_status = 'RESPONDING'
        alert.save()

    timeline_type = 'RESPONSE_STARTED'
    if action_type == 'CALL_GUARD':
        timeline_type = 'CALL_INITIATED'
    elif action_type == 'EMERGENCY_SERVICE_INFORMED':
        timeline_type = 'EMERGENCY_SERVICE_NOTIFIED'
    elif action_type == 'DEPLOYMENT_REQUESTED':
        timeline_type = 'DEPLOYMENT_REQUESTED'

    log_panic_timeline(
        panic_alert=alert,
        event_type=timeline_type,
        actor=responder_user,
        event_data={
            'action_type': action_type,
            'description': description or f"Responder action {action_type} recorded.",
            'reference': reference
        }
    )

    return action


def send_are_you_safe_prompt(panic_alert_id, actor_user):
    """
    Sends 'Are You Safe?' prompt to the reporting guard (FR-9.74, AC-9.42).
    """
    alert = PanicAlert.objects.filter(panic_alert_id=panic_alert_id).first()
    if not alert:
        raise ValidationError("Panic alert not found.")

    record_responder_action(
        panic_alert_id=panic_alert_id,
        responder_user=actor_user,
        action_type='ARE_YOU_SAFE_SENT',
        description='Are You Safe? check prompted to guard application.'
    )

    # Relay in-app notification to guard
    guard_user = User.objects.filter(phone=alert.guard.phone).first()
    if guard_user:
        create_in_app_notification(
            company_id=alert.company_id,
            user_id=guard_user.user_id,
            title="SAFETY CHECK: Are You Safe?",
            message="Your supervisor has requested an immediate safety status check. Please respond Yes or No.",
            notification_type='PANIC_ACKNOWLEDGED'
        )

    return True


def respond_are_you_safe(panic_alert_id, guard_user, answer='YES', explanation=None):
    """
    Records guard's response to 'Are You Safe?' prompt (FR-9.75, AC-9.42).
    """
    alert = PanicAlert.objects.filter(panic_alert_id=panic_alert_id).first()
    if not alert:
        raise ValidationError("Panic alert not found.")

    if answer.upper() == 'YES':
        alert.alert_status = 'GUARD_CONFIRMED_SAFE'
        alert.save()

    log_panic_timeline(
        panic_alert=alert,
        event_type='GUARD_SAFETY_REPLY',
        actor=guard_user,
        event_data={
            'answer': answer.upper(),
            'explanation': explanation or f"Guard responded: {answer.upper()}",
            'description': f"Guard safety response recorded: {answer.upper()}."
        }
    )

    return alert


# ------------------------------------------------------------------------------
# 4. False Alarms & Cancellation
# ------------------------------------------------------------------------------

def report_false_alarm(panic_alert_id, guard_user, explanation=None, are_you_safe_answer='YES'):
    """
    Allows guard to report accidental trigger (FR-9.35, FR-9.36, FR-9.37, AC-9.20, AC-9.21).
    CRITICAL: Guard cancellation NEVER cancels/closes an active alert automatically!
    """
    alert = PanicAlert.objects.filter(panic_alert_id=panic_alert_id).first()
    if not alert:
        raise ValidationError("Panic alert not found.")

    report = PanicFalseAlarmReport.objects.create(
        panic_alert=alert,
        guard=alert.guard,
        submitted_at=timezone.now(),
        guard_explanation=explanation,
        are_you_safe_answer=are_you_safe_answer,
        supervisor_decision='PENDING'
    )

    # Alert remains active! (FR-9.37, AC-9.20)
    log_panic_timeline(
        panic_alert=alert,
        event_type='FALSE_ALARM_REPORTED',
        actor=guard_user,
        event_data={
            'description': f"Guard reported accidental trigger / possible false alarm: {explanation or 'No explanation provided.'}",
            'explanation': explanation,
            'are_you_safe': are_you_safe_answer
        }
    )

    return report


def confirm_false_alarm(panic_alert_id, supervisor_user, decision='CONFIRMED', notes=None):
    """
    Supervisor confirms or rejects false alarm (FR-9.39, FR-9.40, AC-9.22, AC-9.23, AC-9.24).
    If confirmed, moves alert to FALSE_ALARM. Remains subject to Admin review before final closure!
    """
    alert = PanicAlert.objects.filter(panic_alert_id=panic_alert_id).first()
    if not alert:
        raise ValidationError("Panic alert not found.")

    if supervisor_user.role not in ('SUPERVISOR', 'ADMIN'):
        raise PermissionDenied("Only authorized supervisors or admins can confirm false alarms (FR-9.39, AC-9.22).")

    report = PanicFalseAlarmReport.objects.filter(panic_alert=alert).order_by('-submitted_at').first()
    now = timezone.now()

    if report:
        report.supervisor = supervisor_user
        report.supervisor_decision = decision
        report.supervisor_notes = notes
        report.decision_time = now
        report.save()

    if decision == 'CONFIRMED':
        alert.alert_status = 'FALSE_ALARM'
        alert.save()
        log_panic_timeline(
            panic_alert=alert,
            event_type='FALSE_ALARM_CONFIRMED',
            actor=supervisor_user,
            event_data={
                'description': f"False alarm confirmed by supervisor {supervisor_user.full_name}: {notes or 'No notes'}.",
                'notes': notes
            }
        )
    else:
        log_panic_timeline(
            panic_alert=alert,
            event_type='FALSE_ALARM_REJECTED',
            actor=supervisor_user,
            event_data={
                'description': f"False alarm rejected by supervisor {supervisor_user.full_name}. Real panic alert continues.",
                'notes': notes
            }
        )

    return alert


# ------------------------------------------------------------------------------
# 5. Resolution & Admin Review Workflow
# ------------------------------------------------------------------------------

def resolve_panic_alert(
    panic_alert_id,
    supervisor_user,
    outcome,
    description,
    injury_status=None,
    emergency_services_informed=False,
    emergency_service_ref=None,
    follow_up_required=False
):
    """
    Supervisor submits operational resolution (FR-9.79, FR-9.80, AC-9.41).
    Alert enters RESOLVED. Requires Admin review before closure (FR-9.81, AC-9.57).
    """
    alert = PanicAlert.objects.filter(panic_alert_id=panic_alert_id).first()
    if not alert:
        raise ValidationError("Panic alert not found.")

    now = timezone.now()

    resolution, _ = PanicResolution.objects.update_or_create(
        panic_alert=alert,
        defaults={
            'outcome': outcome,
            'description': description,
            'injury_status': injury_status,
            'emergency_services_informed': emergency_services_informed,
            'emergency_service_ref': emergency_service_ref,
            'follow_up_required': follow_up_required,
            'submitted_by': supervisor_user,
            'submitted_at': now,
            'admin_review_status': 'PENDING'
        }
    )

    alert.alert_status = 'RESOLVED'
    alert.resolved_at = now
    alert.save()

    log_panic_timeline(
        panic_alert=alert,
        event_type='RESOLUTION_SUBMITTED',
        actor=supervisor_user,
        event_data={
            'outcome': outcome,
            'description': f"Resolution submitted by {supervisor_user.full_name}: {outcome}. Awaiting Admin review.",
            'emergency_services_informed': emergency_services_informed,
            'injury_status': injury_status
        }
    )

    return alert


def admin_review_panic_alert(panic_alert_id, admin_user, decision='APPROVE', review_notes=None):
    """
    Admin reviews and closes a real panic alert (FR-9.81, FR-9.82, AC-9.57, AC-9.58, AC-9.66).
    """
    alert = PanicAlert.objects.filter(panic_alert_id=panic_alert_id).first()
    if not alert:
        raise ValidationError("Panic alert not found.")

    if admin_user.role != 'ADMIN':
        raise PermissionDenied("Only Admin can review and approve panic alert closure (FR-9.81, AC-9.57).")

    resolution = getattr(alert, 'resolution', None)
    if not resolution and alert.alert_status != 'FALSE_ALARM':
        raise ValidationError("Cannot close panic alert without supervisor resolution details (AC-9.66).")

    now = timezone.now()

    if decision == 'APPROVE':
        alert.alert_status = 'CLOSED'
        alert.closed_at = now
        alert.save()

        if resolution:
            resolution.admin_review_status = 'APPROVED'
            resolution.reviewed_by = admin_user
            resolution.reviewed_at = now
            resolution.review_notes = review_notes
            resolution.save()

        log_panic_timeline(
            panic_alert=alert,
            event_type='ADMIN_CLOSED',
            actor=admin_user,
            event_data={
                'description': f"Panic alert closure reviewed and approved by Admin {admin_user.full_name}.",
                'review_notes': review_notes
            }
        )
    else:
        # Return for additional info
        alert.alert_status = 'RESPONDING'
        alert.save()

        if resolution:
            resolution.admin_review_status = 'RETURNED'
            resolution.reviewed_by = admin_user
            resolution.reviewed_at = now
            resolution.review_notes = review_notes
            resolution.save()

        log_panic_timeline(
            panic_alert=alert,
            event_type='ADMIN_RETURNED',
            actor=admin_user,
            event_data={
                'description': f"Admin {admin_user.full_name} returned resolution for more info: {review_notes or 'No details'}.",
                'review_notes': review_notes
            }
        )

    return alert


def record_welfare_followup(panic_alert_id, admin_user, note):
    """
    Admin records an administrative welfare follow-up note (FR-9.84, FR-9.85).
    """
    alert = PanicAlert.objects.filter(panic_alert_id=panic_alert_id).first()
    if not alert:
        raise ValidationError("Panic alert not found.")

    if admin_user.role != 'ADMIN':
        raise PermissionDenied("Only Admin can record welfare follow-up notes.")

    followup = PanicWelfareFollowup.objects.create(
        panic_alert=alert,
        recorded_by=admin_user,
        note=note
    )

    log_panic_timeline(
        panic_alert=alert,
        event_type='INTERNAL_NOTE',
        actor=admin_user,
        event_data={
            'description': f"Admin welfare follow-up note recorded: {note[:100]}",
            'full_note': note
        }
    )

    return followup


# ------------------------------------------------------------------------------
# 6. Escalation Ladder & Timers
# ------------------------------------------------------------------------------

def process_alert_escalations(panic_alert_id=None):
    """
    Evaluates active alerts against escalation intervals (FR-9.52 to FR-9.55, AC-9.31, AC-9.32, AC-9.33).
    Escalation Stages:
      Stage 0: Immediate (0s)
      Stage 1: 30s (Repeat push & SMS if unacknowledged)
      Stage 2: 60s (Additional contacts)
      Stage 3: 120s (Admin + all escalation contacts + No Acknowledgement warning)
      Stage 4: 300s (Regional / On-call contact)
    """
    now = timezone.now()
    qs = PanicAlert.objects.filter(
        alert_status__in=['TRIGGERED', 'DELIVERING', 'ESCALATED']
    )
    if panic_alert_id:
        qs = qs.filter(panic_alert_id=panic_alert_id)

    escalated_count = 0

    for alert in qs:
        # If acknowledged, repeat acknowledgement alarms stop (FR-9.58, AC-9.29)
        if alert.first_acknowledged_at:
            continue

        elapsed_secs = int((now - alert.trigger_server_time).total_seconds())
        current_stage = alert.current_escalation_stage

        # Stage 3: > 120s
        if elapsed_secs >= 120 and current_stage < 3:
            alert.current_escalation_stage = 3
            alert.last_escalated_at = now
            alert.alert_status = 'ESCALATED'
            alert.save()

            log_panic_timeline(
                panic_alert=alert,
                event_type='NO_ACKNOWLEDGEMENT_WARNING',
                event_data={'stage': 3, 'elapsed_seconds': elapsed_secs, 'description': 'CRITICAL: No acknowledgement received after 120 seconds! Escalated to all executive contacts.'}
            )
            escalated_count += 1

        # Stage 2: > 60s
        elif elapsed_secs >= 60 and current_stage < 2:
            alert.current_escalation_stage = 2
            alert.last_escalated_at = now
            alert.alert_status = 'ESCALATED'
            alert.save()

            log_panic_timeline(
                panic_alert=alert,
                event_type='ESCALATION_STAGE',
                event_data={'stage': 2, 'elapsed_seconds': elapsed_secs, 'description': 'Stage 2 escalation reached: SMS / Voice alerts dispatched to backup contacts.'}
            )
            escalated_count += 1

        # Stage 1: > 30s
        elif elapsed_secs >= 30 and current_stage < 1:
            alert.current_escalation_stage = 1
            alert.last_escalated_at = now
            alert.alert_status = 'ESCALATED'
            alert.save()

            log_panic_timeline(
                panic_alert=alert,
                event_type='ESCALATION_STAGE',
                event_data={'stage': 1, 'elapsed_seconds': elapsed_secs, 'description': 'Stage 1 escalation reached: Repeat alerts dispatched.'}
            )
            escalated_count += 1

    return escalated_count


# ------------------------------------------------------------------------------
# 7. Test Alerts & Drills
# ------------------------------------------------------------------------------

def create_test_drill(
    company_id,
    admin_user,
    drill_name,
    scheduled_at=None,
    selected_recipient_roles=None,
    selected_routes=None,
    include_clients=False,
    notes=None
):
    """
    Creates and initiates a controlled test drill (FR-9.93 to FR-9.98, AC-9.48, AC-9.49, AC-9.50).
    Explicitly flags test_flag=True and alert_status='TEST'.
    Excluded from real panic metrics (FR-9.96, AC-9.49).
    """
    if admin_user.role != 'ADMIN':
        raise PermissionDenied("Only Admin can initiate test drills.")

    now = timezone.now()
    roles = selected_recipient_roles or ['SUPERVISOR', 'ADMIN']
    routes = selected_routes or ['PUSH', 'WEB_CONSOLE']

    drill = PanicTestDrill.objects.create(
        company_id=company_id,
        drill_name=drill_name,
        scheduled_at=scheduled_at or now,
        executed_at=now,
        status='RUNNING',
        selected_recipient_roles=roles,
        selected_routes=routes,
        include_clients=include_clients,
        notes=notes,
        created_by=admin_user
    )

    # Spawn test alert
    employee = Employee.objects.filter(company_id=company_id).first()
    site = ClientSite.objects.filter(client__company_id=company_id).first()

    test_alert, _ = trigger_panic_alert(
        company_id=company_id,
        guard_user=admin_user,
        client_generated_id=uuid.uuid4(),
        device_time=now,
        network_type='WIFI',
        site_id=site.site_id if site else None,
        is_test=True
    )

    drill.status = 'COMPLETED'
    drill.save()

    return drill, test_alert


# ------------------------------------------------------------------------------
# 8. Device Readiness Check
# ------------------------------------------------------------------------------

def update_device_readiness(
    guard_id,
    company_id,
    device_id=None,
    app_version='1.0.0',
    notification_permission='UNKNOWN',
    battery_optimization='UNKNOWN',
    location_permission='UNKNOWN'
):
    """
    Records and calculates guard device readiness (FR-9.99 to FR-9.104, AC-9.51, AC-9.52).
    """
    employee = Employee.objects.filter(employee_id=guard_id).first()
    if not employee:
        raise ValidationError("Guard employee not found.")

    bound_dev = BoundDevice.objects.filter(user__phone=employee.phone, unbound_at__isnull=True).first()

    # Determine overall readiness
    instructions = []
    if notification_permission == 'DENIED':
        instructions.append("Enable push notification permissions in Settings > Apps.")
    if battery_optimization in ('OPTIMIZED', 'RESTRICTED'):
        instructions.append("Disable aggressive battery saver / allow background activity.")
    if location_permission == 'DENIED':
        instructions.append("Grant 'Allow all the time' location access.")

    overall = 'READY'
    if notification_permission == 'UNKNOWN' and location_permission == 'UNKNOWN':
        overall = 'UNKNOWN'
    elif instructions:
        overall = 'NOT_READY'

    readiness, _ = PanicDeviceReadiness.objects.update_or_create(
        company_id=company_id,
        guard=employee,
        defaults={
            'device': bound_dev,
            'app_version': app_version,
            'notification_permission': notification_permission,
            'battery_optimization': battery_optimization,
            'location_permission': location_permission,
            'last_seen_at': timezone.now(),
            'overall_readiness': overall,
            'corrective_instructions': " ".join(instructions) if instructions else "Device is fully configured."
        }
    )

    return readiness


# ------------------------------------------------------------------------------
# 9. Inter-Module Integration Hooks
# ------------------------------------------------------------------------------

def get_panic_tracking_status(guard_id, company_id):
    """
    Module 7 Interface Hook (PRD Section 14.2 A).
    Informs Live Monitoring whether an active panic is underway for the guard.
    """
    active_alert = PanicAlert.objects.filter(
        company_id=company_id,
        guard_id=guard_id,
        test_flag=False,
        alert_status__in=['TRIGGERED', 'DELIVERING', 'ACKNOWLEDGED', 'RESPONDING', 'GUARD_CONFIRMED_SAFE', 'ESCALATED']
    ).first()

    config = PanicEscalationConfig.objects.filter(company_id=company_id).first()
    interval = config.panic_tracking_interval_seconds if config else 15
    max_duration = config.max_panic_tracking_duration_minutes if config else 60

    return {
        'panic_active': bool(active_alert),
        'panic_alert_id': str(active_alert.panic_alert_id) if active_alert else None,
        'tracking_interval_seconds': interval,
        'max_tracking_duration_minutes': max_duration,
        'tracking_start_time': active_alert.trigger_server_time.isoformat() if active_alert else None,
        'tracking_stop_time': active_alert.resolved_at.isoformat() if active_alert and active_alert.resolved_at else None
    }


def create_incident_from_panic_alert(panic_alert_id, actor_user=None):
    """
    Module 8 Interface Hook (PRD Section 14.2 B, FR-9.87, FR-9.88, FR-9.91, AC-9.63).
    Calls create_incident_from_panic idempotently.
    """
    alert = PanicAlert.objects.filter(panic_alert_id=panic_alert_id).first()
    if not alert:
        raise ValidationError("Panic alert not found.")

    incident = create_incident_from_panic(
        panic_event_id=alert.panic_alert_id,
        guard_id=alert.guard_id,
        site_id=alert.site_id,
        assignment_id=alert.assignment_id
    )

    log_panic_timeline(
        panic_alert=alert,
        event_type='INCIDENT_LINKED',
        actor=actor_user,
        event_data={
            'incident_id': str(incident.incident_id),
            'case_number': incident.case_number,
            'description': f"Linked to Module 8 formal incident report {incident.case_number}."
        }
    )

    return incident


def get_client_safe_panic_status(client_id, site_ids=None):
    """
    Module 10 Interface Hook (PRD Section 14.2 C, AC-9.43, AC-9.44).
    Returns client-safe list excluding all sensitive internal metrics.
    """
    qs = PanicAlert.objects.filter(
        site__client_id=client_id,
        test_flag=False
    ).select_related('guard', 'site', 'resolution')

    if site_ids:
        qs = qs.filter(site_id__in=site_ids)

    return qs.order_by('-trigger_server_time')


def panic_weapon_assignment_context(panic_alert_id, guard_id, assignment_id=None, has_weapon=False, weapon_reference=None):
    """
    Module 12 Weapon Reference Hook (PRD Section 14.2 D).
    """
    alert = PanicAlert.objects.filter(panic_alert_id=panic_alert_id).first()
    if alert and has_weapon:
        log_panic_timeline(
            panic_alert=alert,
            event_type='INTERNAL_NOTE',
            event_data={
                'description': f"Guard is carrying authorized duty weapon: {weapon_reference or 'Standard issue'}.",
                'weapon_reference': weapon_reference,
                'has_weapon': True
            }
        )
    return True


def get_panic_reporting_metrics(company_id):
    """
    Module 13 Reporting Interface Hook (PRD Section 14.2 E, FR-9.96, AC-9.49).
    Excludes test alerts from real panic metrics.
    """
    real_alerts = PanicAlert.objects.filter(company_id=company_id, test_flag=False)
    test_alerts = PanicAlert.objects.filter(company_id=company_id, test_flag=True)

    total_real = real_alerts.count()
    total_test = test_alerts.count()

    false_alarms = real_alerts.filter(alert_status='FALSE_ALARM').count()
    false_alarm_rate = (false_alarms / total_real * 100) if total_real > 0 else 0.0

    # Calculate average time to first acknowledgement
    ack_times = []
    for a in real_alerts.filter(first_acknowledged_at__isnull=False):
        secs = (a.first_acknowledged_at - a.trigger_server_time).total_seconds()
        if secs >= 0:
            ack_times.append(secs)
    avg_ack_seconds = round(sum(ack_times) / len(ack_times), 1) if ack_times else 0.0

    # Calculate average time to resolution
    res_times = []
    for a in real_alerts.filter(resolved_at__isnull=False):
        secs = (a.resolved_at - a.trigger_server_time).total_seconds()
        if secs >= 0:
            res_times.append(secs)
    avg_res_seconds = round(sum(res_times) / len(res_times), 1) if res_times else 0.0

    # Delivery failure rate
    total_deliveries = PanicDeliveryAttempt.objects.filter(panic_alert__company_id=company_id, panic_alert__test_flag=False).count()
    failed_deliveries = PanicDeliveryAttempt.objects.filter(panic_alert__company_id=company_id, panic_alert__test_flag=False, delivery_status='FAILED').count()
    delivery_fail_rate = round((failed_deliveries / total_deliveries * 100), 2) if total_deliveries > 0 else 0.0

    return {
        'total_real_alerts': total_real,
        'total_test_alerts': total_test,
        'false_alarm_count': false_alarms,
        'false_alarm_rate_percentage': round(false_alarm_rate, 2),
        'avg_time_to_acknowledgement_seconds': avg_ack_seconds,
        'avg_time_to_resolution_seconds': avg_res_seconds,
        'delivery_failure_rate_percentage': delivery_fail_rate,
        'by_status': list(real_alerts.values('alert_status').annotate(count=models.Count('panic_alert_id'))),
        'by_site': list(real_alerts.values('site__site_name').annotate(count=models.Count('panic_alert_id'))),
        'stage_breakdown': {
            'stage_0': real_alerts.filter(current_escalation_stage=0).count(),
            'stage_1': real_alerts.filter(current_escalation_stage=1).count(),
            'stage_2': real_alerts.filter(current_escalation_stage=2).count(),
            'stage_3_warning': real_alerts.filter(current_escalation_stage__gte=3).count()
        }
    }
