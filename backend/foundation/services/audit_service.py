import csv
import io
import uuid
import logging
from datetime import datetime
import pytz
from django.db import transaction
from django.utils import timezone
from foundation.models import AuditEvent, User
from foundation.resources import translate

logger = logging.getLogger(__name__)
IST = pytz.timezone('Asia/Kolkata')

SENSITIVE_FIELD_NAMES = {
    'password', 'password_hash', 'current_password', 'new_password',
    'temporary_password', 'token', 'token_hash', 'refresh_token',
    'access_token', 'reset_link', 'auth_token'
}


def sanitize_values(values_dict):
    """
    Strips sensitive fields such as passwords, hashes, tokens.
    Replaces them with 'changed' (FR-1.70).
    """
    if not isinstance(values_dict, dict):
        return values_dict

    sanitized = {}
    for k, v in values_dict.items():
        if k.lower() in SENSITIVE_FIELD_NAMES:
            sanitized[k] = "changed"
        elif isinstance(v, dict):
            sanitized[k] = sanitize_values(v)
        else:
            sanitized[k] = v
    return sanitized


def compute_changed_fields(old_dict, new_dict):
    """
    Compares two dictionaries and returns only the fields that changed.
    (FR-1.70)
    """
    if not old_dict or not new_dict:
        return old_dict, new_dict

    sanitized_old = sanitize_values(old_dict)
    sanitized_new = sanitize_values(new_dict)

    diff_old = {}
    diff_new = {}

    all_keys = set(sanitized_old.keys()).union(set(sanitized_new.keys()))
    for key in all_keys:
        val_old = sanitized_old.get(key)
        val_new = sanitized_new.get(key)
        if val_old != val_new:
            diff_old[key] = val_old
            diff_new[key] = val_new

    return diff_old, diff_new


def write_audit_event(
    action_code: str,
    actor_user=None,
    module: str = 'foundation',
    record_type: str = None,
    record_id: str = None,
    old_values: dict = None,
    new_values: dict = None,
    reason: str = None,
    result: str = 'SUCCESS',
    company_id=None,
    request=None,
    ip_address: str = None,
    device_id: str = None,
    user_agent: str = None,
    request_id: str = None
):
    """
    Writes an append-only audit event in the same transaction as the caller.
    If audit write fails, caller transaction rolls back (FR-1.69).
    """
    # Extract request metadata if available
    if request:
        if not ip_address:
            ip_address = getattr(request, 'client_ip', None) or request.META.get('REMOTE_ADDR')
        if not user_agent:
            user_agent = getattr(request, 'user_agent_str', None) or request.META.get('HTTP_USER_AGENT')
        if not request_id:
            request_id = getattr(request, 'request_id', None)
        if not device_id:
            device_id = request.headers.get('X-Device-Id') or getattr(request, 'device_id', None)

    # Actor details
    if actor_user:
        actor_user_id = actor_user.user_id if hasattr(actor_user, 'user_id') else actor_user.id
        actor_role = getattr(actor_user, 'role', 'SYSTEM')
        actor_name = getattr(actor_user, 'full_name', str(actor_user))
        if not company_id and hasattr(actor_user, 'company_id'):
            company_id = actor_user.company_id
    else:
        actor_user_id = None
        actor_role = 'SYSTEM'
        actor_name = 'System'

    if not company_id:
        # Fallback to first company
        from foundation.models import Company
        first_comp = Company.objects.first()
        company_id = first_comp.company_id if first_comp else uuid.uuid4()

    # Sanitize and compute changed values only (FR-1.70)
    cleaned_old = sanitize_values(old_values) if old_values else None
    cleaned_new = sanitize_values(new_values) if new_values else None

    if cleaned_old and cleaned_new:
        cleaned_old, cleaned_new = compute_changed_fields(cleaned_old, cleaned_new)

    try:
        # Create audit event
        audit_event = AuditEvent.objects.create(
            company_id=company_id,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            actor_name=actor_name,
            action_code=action_code,
            module=module,
            record_type=record_type,
            record_id=str(record_id) if record_id else None,
            result=result,
            old_values=cleaned_old,
            new_values=cleaned_new,
            reason=reason,
            ip_address=ip_address,
            device_id=device_id,
            user_agent=user_agent,
            request_id=request_id
        )
        return audit_event
    except Exception as e:
        logger.error(f"Audit log write failed for action {action_code}: {e}")
        # Failed sign-in events are written on a best-effort basis (FR-1.69)
        if action_code == 'auth.login.failed':
            return None
        # Otherwise re-raise to fail caller transaction
        raise e


def get_record_history(record_type: str, record_id: str, requesting_user):
    """
    Returns audit history for a specific record after applying scope checks.
    (FR-1.72 & Interface Spec §10)
    """
    from foundation.services.scope_service import is_in_scope

    if not is_in_scope(requesting_user, record_type, record_id):
        return AuditEvent.objects.none()

    return AuditEvent.objects.filter(
        company_id=requesting_user.company_id,
        record_type=record_type,
        record_id=str(record_id)
    ).order_by('-occurred_at')


def export_audit_csv(queryset, requesting_user):
    """
    Exports filtered audit events to CSV.
    Capped at 50,000 rows. Formats IST + UTC.
    Protects against formula injection by prefixing '=', '+', '-', '@' with a single quote.
    Audits the export event. (FR-1.73, AC-48, AC-55)
    """
    cap = 50000
    total_count = queryset.count()
    capped = total_count > cap

    events = queryset[:cap]

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "Event ID",
        "Time (UTC)",
        "Time (IST)",
        "Actor Role",
        "Actor Name",
        "Action Code",
        "Module",
        "Record Type",
        "Record ID",
        "Result",
        "IP Address",
        "Device ID",
        "Reason"
    ])

    def sanitize_csv_cell(val):
        if val is None:
            return ""
        s = str(val)
        if s.startswith(('=', '+', '-', '@')):
            return f"'{s}"
        return s

    for event in events:
        # Format timestamps (FR-1.90, AC-55)
        utc_str = event.occurred_at.strftime('%Y-%m-%d %H:%M:%S UTC')
        ist_dt = event.occurred_at.astimezone(IST)
        ist_str = ist_dt.strftime('%d/%m/%Y %H:%M:%S IST')

        writer.writerow([
            str(event.id),
            utc_str,
            ist_str,
            sanitize_csv_cell(event.actor_role),
            sanitize_csv_cell(event.actor_name),
            sanitize_csv_cell(event.action_code),
            sanitize_csv_cell(event.module),
            sanitize_csv_cell(event.record_type),
            sanitize_csv_cell(event.record_id),
            event.result,
            sanitize_csv_cell(event.ip_address),
            sanitize_csv_cell(event.device_id),
            sanitize_csv_cell(event.reason)
        ])

    # Audit the export event (FR-1.73)
    write_audit_event(
        action_code='audit.exported',
        actor_user=requesting_user,
        module='foundation',
        record_type='AuditEvent',
        reason=f"Exported {min(total_count, cap)} rows (total matching: {total_count})",
        result='SUCCESS',
        company_id=requesting_user.company_id
    )

    return output.getvalue(), capped, total_count

