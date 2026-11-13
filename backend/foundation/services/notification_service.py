import uuid
import logging
from datetime import timedelta
from django.utils import timezone
from foundation.models import (
    NotificationType, Notification, NotificationDelivery,
    NotificationPreference, PushToken, User
)
from foundation.resources import translate

logger = logging.getLogger(__name__)

# Starter Notification Type Registry from PRD §5D Table
STARTER_NOTIFICATION_TYPES = [
    {
        'code': 'PASSWORD_CHANGED',
        'title_key': 'notif.PASSWORD_CHANGED.title',
        'body_key': 'notif.PASSWORD_CHANGED.body',
        'recipient_rule': 'USER_ONLY',
        'channels': ['IN', 'PUSH'],
        'priority': 'NORMAL',
    },
    {
        'code': 'ACCOUNT_LOCKED',
        'title_key': 'notif.ACCOUNT_LOCKED.title',
        'body_key': 'notif.ACCOUNT_LOCKED.body',
        'recipient_rule': 'ALL_ADMINS',
        'channels': ['IN', 'WEB'],
        'priority': 'NORMAL',
    },
    {
        'code': 'DEVICE_CHANGE_REQUESTED',
        'title_key': 'notif.DEVICE_CHANGE_REQUESTED.title',
        'body_key': 'notif.DEVICE_CHANGE_REQUESTED.body',
        'recipient_rule': 'ALL_ADMINS',
        'channels': ['IN', 'WEB', 'PUSH'],
        'priority': 'HIGH',
    },
    {
        'code': 'DEVICE_CHANGE_DECIDED',
        'title_key': 'notif.DEVICE_CHANGE_DECIDED.title',
        'body_key': 'notif.DEVICE_CHANGE_DECIDED.body',
        'recipient_rule': 'SUPERVISOR_OF_GUARD',
        'channels': ['IN', 'PUSH'],
        'priority': 'NORMAL',
    },
    {
        'code': 'POLICY_UPDATED',
        'title_key': 'notif.POLICY_UPDATED.title',
        'body_key': 'notif.POLICY_UPDATED.body',
        'recipient_rule': 'ALL_ACTIVE_USERS',
        'channels': ['IN', 'PUSH'],
        'priority': 'NORMAL',
    },
    {
        'code': 'NOTIFICATION_DELIVERY_FAILED',
        'title_key': 'notif.NOTIFICATION_DELIVERY_FAILED.title',
        'body_key': 'notif.NOTIFICATION_DELIVERY_FAILED.body',
        'recipient_rule': 'ALL_ADMINS',
        'channels': ['IN', 'WEB', 'PUSH'],
        'priority': 'HIGH',
    },
    {
        'code': 'PANIC_RAISED',
        'title_key': 'notif.PANIC_RAISED.title',
        'body_key': 'notif.PANIC_RAISED.body',
        'recipient_rule': 'IN_SCOPE_SUPERVISORS_AND_ADMINS',
        'channels': ['IN', 'WEB', 'PUSH', 'SMS'],
        'priority': 'CRITICAL',
    },
    {
        'code': 'PANIC_ESCALATED',
        'title_key': 'notif.PANIC_ESCALATED.title',
        'body_key': 'notif.PANIC_ESCALATED.body',
        'recipient_rule': 'ALL_ADMINS',
        'channels': ['IN', 'WEB', 'PUSH', 'SMS'],
        'priority': 'CRITICAL',
    },
    {
        'code': 'PANIC_ACKNOWLEDGED',
        'title_key': 'notif.PANIC_ACKNOWLEDGED.title',
        'body_key': 'notif.PANIC_ACKNOWLEDGED.body',
        'recipient_rule': 'GUARD_ONLY',
        'channels': ['IN', 'PUSH'],
        'priority': 'HIGH',
    },
    {
        'code': 'PANIC_RESOLVED',
        'title_key': 'notif.PANIC_RESOLVED.title',
        'body_key': 'notif.PANIC_RESOLVED.body',
        'recipient_rule': 'GUARD_SUPERVISOR_AND_ADMINS',
        'channels': ['IN', 'WEB', 'PUSH'],
        'priority': 'HIGH',
    },
    {
        'code': 'INCIDENT_REPORTED',
        'title_key': 'notif.INCIDENT_REPORTED.title',
        'body_key': 'notif.INCIDENT_REPORTED.body',
        'recipient_rule': 'IN_SCOPE_SUPERVISORS_AND_ADMINS',
        'channels': ['IN', 'WEB', 'PUSH'],
        'priority': 'HIGH',
    },
    {
        'code': 'ATTENDANCE_PENDING_APPROVAL',
        'title_key': 'notif.ATTENDANCE_PENDING_APPROVAL.title',
        'body_key': 'notif.ATTENDANCE_PENDING_APPROVAL.body',
        'recipient_rule': 'IN_SCOPE_SUPERVISORS',
        'channels': ['IN', 'WEB', 'PUSH'],
        'priority': 'NORMAL',
    },
]


def sync_notification_types_to_db():
    """
    Loads starter notification types into database table notification_types.
    (FR-1.53)
    """
    for entry in STARTER_NOTIFICATION_TYPES:
        NotificationType.objects.update_or_create(
            code=entry['code'],
            defaults={
                'title_key': entry['title_key'],
                'body_key': entry['body_key'],
                'recipient_rule': entry['recipient_rule'],
                'channels': entry['channels'],
                'priority': entry['priority'],
            }
        )


def sms_sender_hook(phone: str, message: str, notification_id: str):
    """
    SMS sender hook interface (FR-1.56).
    v1 ships a no-op implementation returning 'not_configured'.
    """
    logger.info(f"[SMS Hook] Attempted SMS to {phone[-3:] if phone else 'N/A'}: {message[:20]}... Status: not_configured")
    return 'NOT_CONFIGURED'


def resolve_recipients(type_def: NotificationType, recipient_hint, company_id, related_record_type=None, related_record_id=None):
    """
    Resolves recipient user IDs based on recipient_rule and scope grants.
    Excludes inactive users and users who lack scope over related record (FR-1.66, AC-44).
    """
    from foundation.services.scope_service import is_in_scope

    rule = type_def.recipient_rule
    user_qs = User.objects.filter(company_id=company_id, status='ACTIVE')

    recipients = []

    if recipient_hint:
        if isinstance(recipient_hint, list):
            recipients = list(user_qs.filter(user_id__in=recipient_hint))
        else:
            recipients = list(user_qs.filter(user_id=recipient_hint))
    elif rule == 'ALL_ADMINS':
        recipients = list(user_qs.filter(role='ADMIN'))
    elif rule == 'ALL_ACTIVE_USERS':
        recipients = list(user_qs)
    elif rule in ('IN_SCOPE_SUPERVISORS', 'IN_SCOPE_SUPERVISORS_AND_ADMINS'):
        admins = list(user_qs.filter(role='ADMIN')) if 'ADMINS' in rule else []
        supervisors = list(user_qs.filter(role='SUPERVISOR'))

        # Check scope over related record if specified
        valid_supervisors = []
        for s in supervisors:
            if related_record_type and related_record_id:
                if is_in_scope(s, related_record_type, related_record_id):
                    valid_supervisors.append(s)
            else:
                valid_supervisors.append(s)

        recipients = admins + valid_supervisors
    else:
        recipients = list(user_qs.filter(role='ADMIN'))

    # Final check: exclude inactive users (FR-1.66)
    return [u for u in recipients if u.status == 'ACTIVE']


def send_notification(
    type_code: str,
    recipient_hint=None,
    params: dict = None,
    related_record_type: str = None,
    related_record_id: str = None,
    dedupe_key: str = None,
    company_id=None
):
    """
    One shared notification service (FR-1.52, FR-1.54, Section 10).
    Fast: creates in-app records and delivery rows, returns notification IDs.
    Applies deduplication within 5 minutes (FR-1.63, AC-43).
    """
    params = params or {}
    type_def = NotificationType.objects.filter(code=type_code).first()
    if not type_def:
        # Fallback to in-memory starter definitions if not yet synced
        fallback = next((t for t in STARTER_NOTIFICATION_TYPES if t['code'] == type_code), None)
        if not fallback:
            raise KeyError(f"Unknown notification type: {type_code}")
        type_def = NotificationType(
            code=fallback['code'],
            title_key=fallback['title_key'],
            body_key=fallback['body_key'],
            recipient_rule=fallback['recipient_rule'],
            channels=fallback['channels'],
            priority=fallback['priority']
        )

    if not company_id:
        from foundation.models import Company
        first_c = Company.objects.first()
        company_id = first_c.company_id if first_c else uuid.uuid4()

    recipients = resolve_recipients(
        type_def, recipient_hint, company_id,
        related_record_type=related_record_type,
        related_record_id=related_record_id
    )

    created_ids = []
    now = timezone.now()
    five_min_ago = now - timedelta(minutes=5)

    title_template = translate(type_def.title_key, **params)
    body_template = translate(type_def.body_key, **params)

    for user in recipients:
        # Deduplication check (FR-1.63, AC-43)
        if dedupe_key:
            existing = Notification.objects.filter(
                type_code=type_code,
                user=user,
                dedupe_key=dedupe_key,
                created_at__gte=five_min_ago
            ).first()
            if existing:
                continue

        # In-app notification record (ALWAYS created, FR-1.54, FR-1.55)
        notif = Notification.objects.create(
            company_id=company_id,
            user=user,
            channel='in_app',
            type_code=type_code,
            params=params,
            subject=title_template,
            message=body_template,
            related_record_type=related_record_type,
            related_record_id=related_record_id,
            dedupe_key=dedupe_key
        )
        created_ids.append(notif.notification_id)

        # In-App Delivery
        NotificationDelivery.objects.create(
            notification=notif,
            channel='IN',
            status='SENT',
            attempts=1,
            last_attempt_at=now
        )

        # Check preferences (FR-1.57, FR-1.58, AC-40)
        pref = NotificationPreference.objects.filter(user=user).first()
        push_allowed = True
        if type_def.priority == 'NORMAL':
            if pref and not pref.push_normal:
                push_allowed = False

        # Mobile Push Delivery
        if 'PUSH' in type_def.channels:
            push_tokens = PushToken.objects.filter(user=user, removed_at__isnull=True)
            if not push_allowed:
                NotificationDelivery.objects.create(
                    notification=notif,
                    channel='PUSH',
                    status='SKIPPED',
                    failure_reason='User disabled push for normal notifications'
                )
            elif not push_tokens.exists():
                NotificationDelivery.objects.create(
                    notification=notif,
                    channel='PUSH',
                    status='SKIPPED',
                    failure_reason='No registered push token'
                )
            else:
                NotificationDelivery.objects.create(
                    notification=notif,
                    channel='PUSH',
                    status='QUEUED',
                    attempts=0
                )

        # Web Notification Delivery
        if 'WEB' in type_def.channels:
            NotificationDelivery.objects.create(
                notification=notif,
                channel='WEB',
                status='SENT',
                attempts=1,
                last_attempt_at=now
            )

        # SMS Fallback Hook (for Critical, FR-1.56, FR-1.61)
        if 'SMS' in type_def.channels and type_def.priority == 'CRITICAL':
            sms_status = sms_sender_hook(user.phone, body_template, str(notif.notification_id))
            NotificationDelivery.objects.create(
                notification=notif,
                channel='SMS',
                status=sms_status,
                attempts=1,
                last_attempt_at=now,
                failure_reason='SMS provider not configured in v1'
            )

    return created_ids
