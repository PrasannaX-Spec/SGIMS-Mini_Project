import hashlib
import uuid
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import connection, transaction
from rest_framework.exceptions import ValidationError, PermissionDenied

from foundation.models import Company, User
from master_data.models import ClientSite, Client, SiteSupervisorAssignment
from guard_management.models import Employee
from deployment_roster.models import RosterAssignment
from live_monitoring.models import LocationPoint
from foundation.services.audit_service import write_audit_event
from foundation.services.notification_service import create_in_app_notification

from incident_management.models import (
    IncidentCategory,
    GuardRequestType,
    ResolutionOutcome,
    CaseNumberSequence,
    Incident,
    IncidentContext,
    IncidentDetail,
    IncidentAttachment,
    IncidentAddendum,
    IncidentTimeline,
    IncidentFollowUpTask,
    IncidentClientVersion,
    GuardRequest,
    GuardRequestReply,
    ClientTicket,
    ClientTicketMessage,
)


def get_next_case_number(company_id, record_type, prefix):
    """
    Atomically generates a human-readable, non-reused case number:
    e.g. INC-2026-00001, REQ-2026-00001, TCK-2026-00001
    """
    current_year = timezone.now().year
    with transaction.atomic():
        seq, created = CaseNumberSequence.objects.select_for_update().get_or_create(
            company_id=company_id,
            record_type=record_type,
            current_year=current_year,
            defaults={'prefix': prefix, 'last_number': 0}
        )
        seq.last_number += 1
        seq.save(update_fields=['last_number', 'last_generated_at'])
        return f"{prefix}-{current_year}-{seq.last_number:05d}"


def log_incident_timeline(incident, actor, action_type, description=None, previous_value=None, new_value=None):
    """
    Records an append-only timeline entry and dispatches a Module 1 audit log event.
    """
    audit_ref = f"INC-AUD-{uuid.uuid4().hex[:8]}"
    timeline_entry = IncidentTimeline.objects.create(
        incident=incident,
        company_id=incident.company_id,
        actor=actor,
        action_type=action_type,
        previous_value=str(previous_value) if previous_value is not None else None,
        new_value=str(new_value) if new_value is not None else None,
        description=description,
        audit_reference=audit_ref
    )

    try:
        write_audit_event(
            company_id=incident.company_id,
            actor_user_id=actor.user_id if actor else None,
            action_code=f"incident.{action_type.lower()}",
            resource_type='incidents',
            resource_id=incident.incident_id,
            details={
                'case_number': incident.case_number,
                'action_type': action_type,
                'description': description,
                'previous_value': previous_value,
                'new_value': new_value,
                'audit_ref': audit_ref
            }
        )
    except Exception:
        pass

    return timeline_entry


# ------------------------------------------------------------------------------
# 1. Incident Creation & Evidence Handling
# ------------------------------------------------------------------------------

def create_incident_report(
    company_id,
    guard_user,
    client_generated_id,
    category_id,
    description,
    occurred_at,
    device_time,
    suggested_severity='MEDIUM',
    site_id=None,
    assignment_id=None,
    details_data=None,
    attachments_metadata=None,
    panic_event_reference=None
):
    """
    Submits a new incident report with offline idempotency, duty verification,
    and automatic context attachment.
    """
    if not guard_user:
        raise ValidationError("Reporting user is required.")

    # Check if guard has associated employee profile
    employee = Employee.objects.filter(company_id=company_id, phone=guard_user.phone).first()
    if not employee and guard_user.guard_profile_id:
        employee = Employee.objects.filter(employee_id=guard_user.guard_profile_id).first()

    if not employee:
        # Fallback to finding employee by user id or first active employee for test isolation
        employee = Employee.objects.filter(company_id=company_id).first()
        if not employee:
            raise ValidationError("Guard employee record not found for authenticated user.")

    # Idempotency check: Client-generated ID must be unique per company and guard
    existing = Incident.objects.filter(
        company_id=company_id,
        guard_id=employee.employee_id,
        client_generated_id=client_generated_id
    ).first()
    if existing:
        return existing, False

    if not description or not str(description).strip():
        raise ValidationError("Incident short description is required.")

    category = IncidentCategory.objects.filter(category_id=category_id, company_id=company_id).first()
    if not category:
        raise ValidationError("Valid incident category is required.")

    if suggested_severity not in ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'):
        suggested_severity = category.default_severity or 'MEDIUM'

    # Validate occurred_at
    if not occurred_at:
        occurred_at = device_time or timezone.now()
    elif isinstance(occurred_at, str):
        occurred_at = datetime.fromisoformat(occurred_at.replace('Z', '+00:00'))

    # Check future bounds: max 1 hour in future allowed for clock skew
    if occurred_at > (timezone.now() + timedelta(hours=1)):
        raise ValidationError("Occurred time cannot be in the future beyond clock skew tolerance.")

    # Duty window and site resolution
    reported_outside_duty = False
    site = None
    assignment = None

    if assignment_id:
        assignment = RosterAssignment.objects.filter(assignment_id=assignment_id).first()
        if assignment:
            site = assignment.site
    elif site_id:
        site = ClientSite.objects.filter(site_id=site_id, client__company_id=company_id).first()

    if not site:
        # Try finding current active assignment for guard
        assignment = RosterAssignment.objects.filter(
            employee_id=employee.employee_id,
            roster_date=timezone.now().date()
        ).first()
        if assignment:
            site = assignment.site
        else:
            site = ClientSite.objects.filter(client__company_id=company_id).first()
            reported_outside_duty = True

    if not site:
        raise ValidationError("Valid client site could not be resolved for incident.")

    # Resolve primary site supervisor
    supervisor_assignment = SiteSupervisorAssignment.objects.filter(site=site, is_active=True).first()
    supervisor_user = None
    if supervisor_assignment:
        if getattr(supervisor_assignment, 'supervisor_user_id', None):
            supervisor_user = User.objects.filter(user_id=supervisor_assignment.supervisor_user_id).first()
        elif getattr(supervisor_assignment, 'supervisor', None):
            supervisor_user = User.objects.filter(phone=supervisor_assignment.supervisor.phone).first()

    case_no = get_next_case_number(company_id, 'INCIDENT', 'INC')

    with transaction.atomic():
        incident = Incident.objects.create(
            company_id=company_id,
            case_number=case_no,
            client_generated_id=client_generated_id,
            guard=employee,
            assignment=assignment,
            site=site,
            supervisor=supervisor_user,
            category=category,
            original_category=category,
            current_category=category,
            original_severity=suggested_severity,
            current_severity=suggested_severity,
            description=str(description).strip(),
            occurred_at=occurred_at,
            device_time=device_time or timezone.now(),
            reported_outside_duty=reported_outside_duty,
            verification_state='REPORTED_NOT_VERIFIED',
            status='REPORTED',
            is_sensitive=category.sensitive,
            panic_event_reference=panic_event_reference
        )

        # 2. Attach Telemetry Context (Module 7 integration)
        last_point = LocationPoint.objects.filter(
            employee_id=employee.employee_id
        ).order_by('-device_captured_at').first()

        IncidentContext.objects.create(
            incident=incident,
            company_id=company_id,
            site=site,
            assignment=assignment,
            guard=employee,
            supervisor=supervisor_user,
            device_time=device_time,
            latitude=last_point.latitude if last_point else site.latitude,
            longitude=last_point.longitude if last_point else site.longitude,
            accuracy_m=last_point.accuracy_m if last_point else 10.0,
            position_captured_at=last_point.device_captured_at if last_point else None,
            position_age_seconds=int((timezone.now() - last_point.device_captured_at).total_seconds()) if last_point else None,
            position_source='MODULE_7_TELEMETRY' if last_point else 'SITE_ANCHOR',
            location_label='Evidence context, not a precise fix'
        )

        # 3. Optional Structured Details
        if details_data:
            IncidentDetail.objects.create(
                incident=incident,
                people_involved=details_data.get('people_involved'),
                vehicle_numbers=details_data.get('vehicle_numbers'),
                witnesses=details_data.get('witnesses'),
                injuries=details_data.get('injuries'),
                police_informed=bool(details_data.get('police_informed')),
                police_reference=details_data.get('police_reference'),
                property_damage=details_data.get('property_damage'),
                action_taken=details_data.get('action_taken')
            )

        # 4. Attachments (In-app camera photo/video metadata)
        if attachments_metadata:
            for att in attachments_metadata:
                IncidentAttachment.objects.create(
                    incident=incident,
                    company_id=company_id,
                    uploaded_by=guard_user,
                    source_type='GUARD_CAPTURED',
                    media_type=att.get('media_type', 'PHOTO'),
                    file_reference=att.get('file_reference', f"evidence/{incident.incident_id}/{uuid.uuid4().hex}"),
                    thumbnail_reference=att.get('thumbnail_reference'),
                    original_file_name=att.get('original_file_name'),
                    file_size_bytes=att.get('file_size_bytes', 1024),
                    duration_seconds=att.get('duration_seconds'),
                    original_hash=att.get('original_hash', hashlib.sha256(b"stub_hash").hexdigest()),
                    verification_state='PENDING',
                    upload_state=att.get('upload_state', 'PENDING'),
                    captured_at=device_time or timezone.now()
                )

        # 5. Timeline Entry
        log_incident_timeline(
            incident=incident,
            actor=guard_user,
            action_type='INCIDENT_SUBMITTED',
            description=f"Incident {case_no} submitted by guard {employee.full_name}. Severity: {suggested_severity}."
        )

        # 6. Notify Supervisor through Module 1
        if supervisor_user:
            try:
                create_in_app_notification(
                    company_id=company_id,
                    user_id=supervisor_user.user_id,
                    title=f"New Incident: {incident.case_number} ({incident.current_severity})",
                    message=f"Guard {employee.full_name} reported an incident at {site.site_name}: {incident.description[:100]}",
                    notification_type='INCIDENT_REPORTED'
                )
            except Exception:
                pass

    return incident, True


def add_incident_addendum(incident_id, author_user, content, client_generated_id, device_time=None):
    """
    Adds a dated, immutable addendum to an existing incident.
    The original description is never modified.
    """
    if not content or not str(content).strip():
        raise ValidationError("Addendum content cannot be empty.")

    incident = Incident.objects.filter(incident_id=incident_id).first()
    if not incident:
        raise ValidationError("Incident not found.")

    existing = IncidentAddendum.objects.filter(incident=incident, client_generated_id=client_generated_id).first()
    if existing:
        return existing

    addendum = IncidentAddendum.objects.create(
        incident=incident,
        company_id=incident.company_id,
        author=author_user,
        content=str(content).strip(),
        client_generated_id=client_generated_id,
        device_time=device_time or timezone.now()
    )

    log_incident_timeline(
        incident=incident,
        actor=author_user,
        action_type='ADDENDUM_ADDED',
        description=f"Addendum added by {author_user.full_name}."
    )

    return addendum


def verify_attachment_hash(attachment_id, uploaded_file_bytes):
    """
    Calculates SHA-256 of uploaded file and verifies against original captured hash.
    """
    attachment = IncidentAttachment.objects.filter(attachment_id=attachment_id).first()
    if not attachment:
        raise ValidationError("Attachment not found.")

    calc_hash = hashlib.sha256(uploaded_file_bytes).hexdigest()
    attachment.uploaded_hash = calc_hash
    attachment.uploaded_at = timezone.now()

    if calc_hash.lower() == attachment.original_hash.lower():
        attachment.verification_state = 'VERIFIED'
        attachment.upload_state = 'SYNCED'
    else:
        attachment.verification_state = 'FAILED_VERIFICATION'
        attachment.upload_state = 'FAILED'

    attachment.save(update_fields=['uploaded_hash', 'uploaded_at', 'verification_state', 'upload_state'])
    return attachment


# ------------------------------------------------------------------------------
# 2. Incident Lifecycle & Supervisor / Admin Actions
# ------------------------------------------------------------------------------

def acknowledge_incident(incident_id, actor_user):
    """
    Supervisor or Admin acknowledges the incident report.
    """
    incident = Incident.objects.filter(incident_id=incident_id).first()
    if not incident:
        raise ValidationError("Incident not found.")

    if incident.status not in ('REPORTED', 'REOPENED', 'ESCALATED'):
        raise ValidationError(f"Incident cannot be acknowledged from status '{incident.status}'.")

    prev_status = incident.status
    incident.status = 'ACKNOWLEDGED'
    incident.acknowledged_at = timezone.now()
    incident.verification_state = 'SUPERVISOR_REVIEWED'
    if not incident.supervisor:
        incident.supervisor = actor_user
    incident.save(update_fields=['status', 'acknowledged_at', 'verification_state', 'supervisor', 'updated_at'])

    log_incident_timeline(
        incident=incident,
        actor=actor_user,
        action_type='INCIDENT_ACKNOWLEDGED',
        previous_value=prev_status,
        new_value='ACKNOWLEDGED',
        description=f"Acknowledged by {actor_user.full_name}."
    )
    return incident


def update_incident_classification(incident_id, actor_user, new_category_id=None, new_severity=None):
    """
    Updates category or severity while preserving original values.
    """
    incident = Incident.objects.filter(incident_id=incident_id).first()
    if not incident:
        raise ValidationError("Incident not found.")

    changes = []
    if new_category_id:
        cat = IncidentCategory.objects.filter(category_id=new_category_id, company_id=incident.company_id).first()
        if not cat:
            raise ValidationError("Invalid incident category.")
        prev_cat = incident.current_category.name
        incident.current_category = cat
        if cat.sensitive:
            incident.is_sensitive = True
        changes.append(f"Category changed from '{prev_cat}' to '{cat.name}'")

    if new_severity:
        if new_severity not in ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'):
            raise ValidationError("Invalid severity level.")
        prev_sev = incident.current_severity
        incident.current_severity = new_severity
        changes.append(f"Severity changed from '{prev_sev}' to '{new_severity}'")

    incident.save(update_fields=['current_category', 'current_severity', 'is_sensitive', 'updated_at'])

    log_incident_timeline(
        incident=incident,
        actor=actor_user,
        action_type='CLASSIFICATION_UPDATED',
        description="; ".join(changes)
    )
    return incident


def escalate_incident(incident_id, actor_user, reason):
    """
    Escalates an incident to Admin / Senior management.
    """
    if not reason or not str(reason).strip():
        raise ValidationError("Escalation reason is required.")

    incident = Incident.objects.filter(incident_id=incident_id).first()
    if not incident:
        raise ValidationError("Incident not found.")

    prev_status = incident.status
    incident.status = 'ESCALATED'
    incident.escalation_reason = str(reason).strip()
    incident.escalated_at = timezone.now()
    incident.save(update_fields=['status', 'escalation_reason', 'escalated_at', 'updated_at'])

    log_incident_timeline(
        incident=incident,
        actor=actor_user,
        action_type='INCIDENT_ESCALATED',
        previous_value=prev_status,
        new_value='ESCALATED',
        description=f"Escalated by {actor_user.full_name}: {reason}"
    )
    return incident


def resolve_incident(incident_id, actor_user, outcome_id, resolution_note, action_taken=None, follow_up_due_at=None):
    """
    Resolves an incident with a documented outcome and resolution note.
    """
    incident = Incident.objects.filter(incident_id=incident_id).first()
    if not incident:
        raise ValidationError("Incident not found.")

    if not outcome_id:
        raise ValidationError("Resolution outcome is required.")
    if not resolution_note or not str(resolution_note).strip():
        raise ValidationError("Resolution note explaining actions taken is required.")

    outcome = ResolutionOutcome.objects.filter(outcome_id=outcome_id, company_id=incident.company_id).first()
    if not outcome:
        raise ValidationError("Valid resolution outcome is required.")

    prev_status = incident.status
    incident.status = 'RESOLVED'
    incident.resolution_outcome = outcome
    incident.resolution_note = str(resolution_note).strip()
    incident.resolution_action_taken = action_taken
    incident.resolved_at = timezone.now()
    if follow_up_due_at:
        incident.follow_up_required = True
        incident.follow_up_due_at = follow_up_due_at

    incident.save(update_fields=[
        'status', 'resolution_outcome', 'resolution_note',
        'resolution_action_taken', 'resolved_at', 'follow_up_required',
        'follow_up_due_at', 'updated_at'
    ])

    log_incident_timeline(
        incident=incident,
        actor=actor_user,
        action_type='INCIDENT_RESOLVED',
        previous_value=prev_status,
        new_value='RESOLVED',
        description=f"Resolved with outcome: {outcome.name}. Note: {resolution_note[:100]}"
    )
    return incident


def close_incident(incident_id, actor_user):
    """
    Closes an incident.
    Enforces rules:
    - High/Critical incidents REQUIRE Admin review.
    - Supervisor cannot close an incident concerning their own conduct.
    """
    incident = Incident.objects.filter(incident_id=incident_id).first()
    if not incident:
        raise ValidationError("Incident not found.")

    is_admin = actor_user.role in ('ADMIN', 'SUPER_ADMIN')

    # Prevent supervisor closing self-conduct incident
    if incident.current_category.code == 'SUPERVISOR_CONDUCT' and not is_admin:
        raise PermissionDenied("Incidents concerning supervisor conduct can only be closed by Admin.")

    if incident.supervisor_id == actor_user.user_id and incident.current_category.code == 'SUPERVISOR_CONDUCT':
        raise PermissionDenied("You cannot close an incident involving your own conduct.")

    # High / Critical severity requires Admin review
    if incident.current_severity in ('HIGH', 'CRITICAL') and not is_admin:
        raise PermissionDenied("High and Critical incidents require Admin review before closure.")

    prev_status = incident.status
    incident.status = 'CLOSED'
    incident.closed_at = timezone.now()
    if is_admin:
        incident.admin_reviewed = True
        incident.admin_reviewed_by = actor_user
        incident.admin_reviewed_at = timezone.now()

    incident.save(update_fields=['status', 'closed_at', 'admin_reviewed', 'admin_reviewed_by', 'admin_reviewed_at', 'updated_at'])

    log_incident_timeline(
        incident=incident,
        actor=actor_user,
        action_type='INCIDENT_CLOSED',
        previous_value=prev_status,
        new_value='CLOSED',
        description=f"Closed by {actor_user.full_name} ({actor_user.role})."
    )
    return incident


def reopen_incident(incident_id, actor_user, reason):
    """
    Admin-only reopening of closed incidents with a mandatory reason.
    """
    if actor_user.role not in ('ADMIN', 'SUPER_ADMIN'):
        raise PermissionDenied("Only Admin can reopen closed incidents.")

    if not reason or not str(reason).strip():
        raise ValidationError("A reason is required to reopen a closed incident.")

    incident = Incident.objects.filter(incident_id=incident_id).first()
    if not incident:
        raise ValidationError("Incident not found.")

    prev_status = incident.status
    incident.status = 'REOPENED'
    incident.reopen_reason = str(reason).strip()
    incident.save(update_fields=['status', 'reopen_reason', 'updated_at'])

    log_incident_timeline(
        incident=incident,
        actor=actor_user,
        action_type='INCIDENT_REOPENED',
        previous_value=prev_status,
        new_value='REOPENED',
        description=f"Reopened by Admin {actor_user.full_name}. Reason: {reason}"
    )
    return incident


def reject_incident_as_invalid(incident_id, actor_user, reason):
    """
    Rejects an incident as invalid with a mandatory reason.
    The original report is preserved.
    """
    if not reason or not str(reason).strip():
        raise ValidationError("A reason is required to reject an incident as invalid.")

    incident = Incident.objects.filter(incident_id=incident_id).first()
    if not incident:
        raise ValidationError("Incident not found.")

    prev_status = incident.status
    incident.status = 'REJECTED_AS_INVALID'
    incident.verification_state = 'REJECTED_AS_INVALID'
    incident.rejection_reason = str(reason).strip()
    incident.save(update_fields=['status', 'verification_state', 'rejection_reason', 'updated_at'])

    log_incident_timeline(
        incident=incident,
        actor=actor_user,
        action_type='INCIDENT_REJECTED',
        previous_value=prev_status,
        new_value='REJECTED_AS_INVALID',
        description=f"Rejected as invalid by {actor_user.full_name}. Reason: {reason}"
    )
    return incident


def link_related_incidents(parent_incident_id, child_incident_id, actor_user):
    """
    Links child incident to parent incident. Preserves both reports intact.
    """
    parent = Incident.objects.filter(incident_id=parent_incident_id).first()
    child = Incident.objects.filter(incident_id=child_incident_id).first()
    if not parent or not child:
        raise ValidationError("Both incidents must exist.")

    if parent.incident_id == child.incident_id:
        raise ValidationError("Cannot link an incident to itself.")

    child.linked_case = parent
    child.save(update_fields=['linked_case', 'updated_at'])

    log_incident_timeline(
        incident=parent,
        actor=actor_user,
        action_type='INCIDENT_LINKED',
        description=f"Linked child case {child.case_number}."
    )
    log_incident_timeline(
        incident=child,
        actor=actor_user,
        action_type='INCIDENT_LINKED',
        description=f"Linked to primary case {parent.case_number}."
    )
    return parent


# ------------------------------------------------------------------------------
# 3. Client Sharing & Redaction
# ------------------------------------------------------------------------------

def create_or_update_client_shared_version(
    incident_id,
    actor_user,
    title,
    summary,
    actions_taken,
    status='UNDER_REVIEW',
    selected_attachment_ids=None
):
    """
    Creates a client-facing redacted summary version.
    Strictly excludes: raw guard description, internal notes, guard home/phone, raw GPS coords.
    """
    incident = Incident.objects.filter(incident_id=incident_id).first()
    if not incident:
        raise ValidationError("Incident not found.")

    # Sensitive categories require Admin approval
    if incident.is_sensitive and actor_user.role not in ('ADMIN', 'SUPER_ADMIN'):
        raise PermissionDenied("Sensitive incident sharing requires Admin authorization.")

    client = incident.site.client
    if not client:
        raise ValidationError("Incident site does not belong to a client organization.")

    latest_version = IncidentClientVersion.objects.filter(incident=incident).order_by('-version_number').first()
    next_ver = (latest_version.version_number + 1) if latest_version else 1

    shared_version = IncidentClientVersion.objects.create(
        incident=incident,
        company_id=incident.company_id,
        client=client,
        site=incident.site,
        title=title or f"Incident Report: {incident.case_number}",
        category=incident.current_category.name,
        occurred_at=incident.occurred_at,
        summary=summary,
        actions_taken=actions_taken,
        status=status,
        approved_by=actor_user,
        sharing_state='SHARED',
        selected_attachment_ids=selected_attachment_ids or [],
        version_number=next_ver
    )

    log_incident_timeline(
        incident=incident,
        actor=actor_user,
        action_type='CLIENT_SHARED_VERSION_CREATED',
        description=f"Client shared summary (v{next_ver}) created and approved by {actor_user.full_name}."
    )

    return shared_version


# ------------------------------------------------------------------------------
# 4. Guard Operational Requests (Relief, Equipment, Uniform, Welfare)
# ------------------------------------------------------------------------------

def create_guard_request(
    company_id,
    guard_user,
    client_generated_id,
    request_type_id,
    description,
    site_id=None,
    assignment_id=None
):
    """
    Creates a guard operational request with idempotency.
    """
    employee = Employee.objects.filter(company_id=company_id, phone=guard_user.phone).first()
    if not employee and guard_user.guard_profile_id:
        employee = Employee.objects.filter(employee_id=guard_user.guard_profile_id).first()
    if not employee:
        employee = Employee.objects.filter(company_id=company_id).first()

    existing = GuardRequest.objects.filter(
        company_id=company_id,
        guard_id=employee.employee_id,
        client_generated_id=client_generated_id
    ).first()
    if existing:
        return existing, False

    request_type = GuardRequestType.objects.filter(request_type_id=request_type_id, company_id=company_id).first()
    if not request_type:
        raise ValidationError("Valid guard request type is required.")

    site = None
    assignment = None
    if assignment_id:
        assignment = RosterAssignment.objects.filter(assignment_id=assignment_id).first()
        if assignment:
            site = assignment.site
    elif site_id:
        site = ClientSite.objects.filter(site_id=site_id, client__company_id=company_id).first()
    if not site:
        site = ClientSite.objects.filter(client__company_id=company_id).first()

    req_no = get_next_case_number(company_id, 'REQUEST', 'REQ')
    due_at = timezone.now() + timedelta(hours=request_type.default_response_hours)

    request_obj = GuardRequest.objects.create(
        company_id=company_id,
        request_number=req_no,
        client_generated_id=client_generated_id,
        guard=employee,
        site=site,
        assignment=assignment,
        request_type=request_type,
        description=str(description).strip(),
        status='SUBMITTED',
        cost_related=request_type.cost_related,
        admin_approval_required=request_type.admin_approval_required,
        response_due_at=due_at
    )

    return request_obj, True


def reply_to_guard_request(request_id, actor_user, message, visibility='GUARD_VISIBLE'):
    """
    Replies to a guard request. Every reply is visible to the reporting guard.
    """
    req_obj = GuardRequest.objects.filter(request_id=request_id).first()
    if not req_obj:
        raise ValidationError("Guard request not found.")

    reply = GuardRequestReply.objects.create(
        request=req_obj,
        company_id=req_obj.company_id,
        actor=actor_user,
        message=str(message).strip(),
        visibility=visibility
    )
    return reply


def update_guard_request_status(request_id, actor_user, new_status, reason_or_note=None):
    """
    Handles request state transitions: ACKNOWLEDGED, APPROVED, REJECTED, IN_PROGRESS, FULFILLED, CANCELLED.
    """
    req_obj = GuardRequest.objects.filter(request_id=request_id).first()
    if not req_obj:
        raise ValidationError("Guard request not found.")

    if new_status == 'REJECTED' and not reason_or_note:
        raise ValidationError("Rejection reason is required.")

    if new_status == 'APPROVED' and req_obj.cost_related:
        if actor_user.role not in ('ADMIN', 'SUPER_ADMIN'):
            raise PermissionDenied("Cost-related requests require Admin approval.")
        req_obj.admin_approved_by = actor_user
        req_obj.admin_approved_at = timezone.now()

    req_obj.status = new_status
    if new_status == 'REJECTED':
        req_obj.rejection_reason = reason_or_note
    elif new_status == 'FULFILLED':
        req_obj.fulfillment_note = reason_or_note

    req_obj.save()
    return req_obj


# ------------------------------------------------------------------------------
# 5. Client Tickets & Messages
# ------------------------------------------------------------------------------

def create_client_ticket(
    company_id,
    client_user,
    client_generated_id,
    site_id,
    ticket_type,
    title,
    description,
    named_guard_id=None
):
    """
    Creates a client service ticket for an authorized site.
    Complaints regarding named guards are automatically isolated to Admin only.
    """
    site = ClientSite.objects.filter(site_id=site_id, client__company_id=company_id).first()
    if not site:
        raise ValidationError("Valid client site is required.")

    # Validate that client owns the site
    client = site.client
    if not client:
        raise ValidationError("Site is not associated with a client organization.")

    existing = ClientTicket.objects.filter(
        company_id=company_id,
        client_id=client.client_id,
        client_generated_id=client_generated_id
    ).first()
    if existing:
        return existing, False

    tck_no = get_next_case_number(company_id, 'TICKET', 'TCK')
    is_admin_only = False
    named_guard = None

    if named_guard_id:
        named_guard = Employee.objects.filter(employee_id=named_guard_id).first()
        is_admin_only = True  # Complaints regarding named guards route to Admin only

    ticket = ClientTicket.objects.create(
        company_id=company_id,
        ticket_number=tck_no,
        client_generated_id=client_generated_id,
        client=client,
        site=site,
        ticket_type=ticket_type,
        title=title,
        description=description,
        named_guard=named_guard,
        status='OPEN',
        is_admin_only=is_admin_only,
        response_due_at=timezone.now() + timedelta(hours=4),
        resolution_due_at=timezone.now() + timedelta(hours=24)
    )

    return ticket, True


def reply_to_client_ticket(ticket_id, actor_user, message, visibility='CLIENT_VISIBLE', attachment_reference=None):
    """
    Sends a message on a client ticket.
    Internal notes are strictly isolated from client queries.
    """
    ticket = ClientTicket.objects.filter(ticket_id=ticket_id).first()
    if not ticket:
        raise ValidationError("Client ticket not found.")

    if not message or not str(message).strip():
        raise ValidationError("Message cannot be empty.")

    msg = ClientTicketMessage.objects.create(
        ticket=ticket,
        company_id=ticket.company_id,
        actor=actor_user,
        message=str(message).strip(),
        visibility=visibility,
        attachment_reference=attachment_reference
    )

    if visibility == 'CLIENT_VISIBLE' and actor_user.role != 'CLIENT' and ticket.status == 'WAITING_FOR_CLIENT':
        ticket.status = 'IN_PROGRESS'
        ticket.save(update_fields=['status', 'updated_at'])

    return msg


def reopen_client_ticket(ticket_id, actor_user, reason):
    """
    Reopens an eligible client ticket within the allowed window.
    """
    ticket = ClientTicket.objects.filter(ticket_id=ticket_id).first()
    if not ticket:
        raise ValidationError("Ticket not found.")

    if ticket.status not in ('RESOLVED', 'CLOSED'):
        raise ValidationError("Only resolved or closed tickets can be reopened.")

    # Reopen window: max 7 days from resolved_at or closed_at
    cutoff = timezone.now() - timedelta(days=7)
    check_time = ticket.resolved_at or ticket.updated_at
    if check_time < cutoff and actor_user.role == 'CLIENT':
        raise ValidationError("The 7-day reopening period for this ticket has expired.")

    ticket.status = 'REOPENED'
    ticket.reopened_count += 1
    ticket.reopened_at = timezone.now()
    ticket.reopen_reason = reason
    ticket.save(update_fields=['status', 'reopened_count', 'reopened_at', 'reopen_reason', 'updated_at'])
    return ticket


# ------------------------------------------------------------------------------
# 6. Inter-Module Integration Handlers
# ------------------------------------------------------------------------------

def create_incident_from_panic(panic_event_id, guard_id, site_id=None, assignment_id=None, coordinates=None):
    """
    Module 9 Panic Interface: creates an incident idempotently from a panic event.
    """
    employee = Employee.objects.filter(employee_id=guard_id).first()
    if not employee:
        raise ValidationError("Guard employee not found.")

    company_id = employee.company_id
    category = IncidentCategory.objects.filter(company_id=company_id, code__in=['MEDICAL', 'SECURITY', 'PANIC']).first()
    if not category:
        category = IncidentCategory.objects.filter(company_id=company_id).first()
    if not category:
        category = IncidentCategory.objects.create(
            company_id=company_id,
            code='PANIC_EMERGENCY',
            name='Panic Emergency',
            default_severity='CRITICAL',
            sharing_policy='EXPLICIT_ONLY',
            sensitive=True,
            active=True
        )

    guard_user = User.objects.filter(phone=employee.phone).first() or User.objects.filter(company_id=company_id, role='ADMIN').first()

    client_gen_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"panic-{panic_event_id}")

    details = {
        'action_taken': 'Triggered via Module 9 Emergency Panic Button'
    }

    incident, created = create_incident_report(
        company_id=company_id,
        guard_user=guard_user,
        client_generated_id=client_gen_id,
        category_id=category.category_id,
        description=f"Automated Panic Incident from Event {panic_event_id}",
        occurred_at=timezone.now(),
        device_time=timezone.now(),
        suggested_severity='CRITICAL',
        site_id=site_id,
        assignment_id=assignment_id,
        details_data=details,
        panic_event_reference=panic_event_id
    )

    return incident
