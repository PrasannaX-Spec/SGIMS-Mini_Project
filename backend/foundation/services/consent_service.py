import logging
from django.utils import timezone
from foundation.models import ConsentRecord, User
from foundation.services.settings_service import get_setting
from foundation.services.audit_service import write_audit_event

logger = logging.getLogger(__name__)


def has_current_consent(user: User, item: str) -> bool:
    """
    Checks if the user has active, current consent for an item on the current policy version.
    (FR-1.80, FR-1.81, Section 10 Interface, AC-52)
    """
    if not user or not user.is_authenticated:
        return False

    current_version = get_setting('current_policy_version', user.company_id)

    latest_record = ConsentRecord.objects.filter(
        user=user,
        item=item
    ).order_by('-recorded_at').first()

    if not latest_record:
        return False

    if latest_record.policy_version != str(current_version):
        return False

    return latest_record.decision == 'GRANTED'


def record_consent(
    user: User,
    item: str,
    decision: str,
    device_id: str = None,
    app_version: str = None,
    ip_address: str = None,
    request=None
):
    """
    Appends a new consent record. Records are immutable and append-only.
    (FR-1.79, FR-1.82, AC-50)
    """
    if decision == 'ACCEPTED':
        decision = 'GRANTED'
    elif decision in ('DECLINED', 'REJECTED'):
        decision = 'DENIED'

    if decision not in ('GRANTED', 'DENIED', 'WITHDRAWN'):
        raise ValueError(f"Invalid consent decision: {decision}")

    if item not in ('TERMS_PRIVACY', 'LOCATION', 'CAMERA', 'NOTIFICATIONS'):
        raise ValueError(f"Invalid consent item: {item}")

    current_version = get_setting('current_policy_version', user.company_id)

    record = ConsentRecord.objects.create(
        company=user.company,
        user=user,
        item=item,
        decision=decision,
        policy_version=str(current_version),
        device_id=device_id or (getattr(request, 'device_id', None) if request else None),
        app_version=app_version,
        ip_address=ip_address or (request.META.get('REMOTE_ADDR') if request else None)
    )

    # Audit event (consent.granted / consent.withdrawn)
    action_code = 'consent.granted' if decision == 'GRANTED' else 'consent.withdrawn'
    write_audit_event(
        action_code=action_code,
        actor_user=user,
        module='foundation',
        record_type='ConsentRecord',
        record_id=str(record.consent_id),
        new_values={'item': item, 'decision': decision, 'policy_version': str(current_version)},
        result='SUCCESS',
        company_id=user.company_id,
        request=request
    )

    return record


def needs_reconsent(user: User) -> bool:
    """
    Returns True if user has not yet consented to the current policy version for TERMS_PRIVACY.
    (FR-1.81, AC-51)
    """
    return not has_current_consent(user, 'TERMS_PRIVACY')

