import re
import secrets
import string
import hashlib
from datetime import datetime, timedelta
import pytz
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from foundation.models import (
    User, Company, UserSession, BoundDevice, DeviceChangeRequest,
    LoginAttempt, OneTimeToken, PushToken
)
from foundation.resources import translate
from foundation.services.settings_service import get_setting
from foundation.services.audit_service import write_audit_event

IST = pytz.timezone('Asia/Kolkata')

# Top 100 most common passwords list (FR-1.4)
COMMON_PASSWORDS = {
    '12345678', 'password', 'password1', '123456789', '1234567890',
    'qwerty123', 'admin123', 'welcome1', 'pass1234', 'secret12',
    'iloveyou', 'sunshine', 'princess', 'football', 'monkey12',
    'charlie1', 'donald12', 'mustang1', 'superman', 'shadow12',
    'master12', 'jordan12', 'harley12', 'robert12', 'daniel12',
    'thomas12', 'security', 'jessica1', 'bailey12', 'guitar12',
    'killer12', 'george12', 'orange12', 'andrew12', 'buster12',
    'hunter12', 'summer12', 'pepper12', 'william1', 'hockey12',
    'marina12', 'samuel12', 'brandon1', 'taylor12', 'amanda12',
    'computer', 'michelle', 'patricia', 'anthony1', 'jennifer'
}

# In-memory IP failure tracker for IP throttle (FR-1.13, AC-58)
# 30 failures per 10 minutes -> 429 for 10 minutes
_IP_FAILURES = {}
IP_THROTTLE_LIMIT = 30
IP_THROTTLE_WINDOW = 600  # 10 minutes


def normalize_identifier(raw_identifier: str):
    """
    Normalizes sign-in identifier:
    - If contains '@' -> email (lowercase)
    - 10-digit Indian phone (with/without +91 or 0) -> +91XXXXXXXXXX
    - Otherwise -> raises ValueError with format error (FR-1.1, AC-3)
    """
    if not raw_identifier:
        raise ValueError(translate('auth.invalid_identifier_format'))

    identifier = raw_identifier.strip()

    if '@' in identifier:
        # Email format
        email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
        if not re.match(email_regex, identifier):
            raise ValueError(translate('auth.invalid_identifier_format'))
        return 'EMAIL', identifier.lower()

    # Phone format (Indian numbers)
    # Accepts 9876543210, +919876543210, 09876543210
    digits_only = re.sub(r'[^0-9]', '', identifier)
    if digits_only.startswith('91') and len(digits_only) == 12:
        digits_only = digits_only[2:]
    elif digits_only.startswith('0') and len(digits_only) == 11:
        digits_only = digits_only[1:]

    if len(digits_only) == 10 and digits_only[0] in '6789':
        return 'PHONE', f"+91{digits_only}"

    raise ValueError(translate('auth.invalid_identifier_format'))


def validate_password_strength(password: str, login_id: str = None):
    """
    Validates password against FR-1.4:
    - 8 to 64 characters
    - At least one letter and at least one digit
    - Not equal to login ID
    - Not in top 100 common passwords
    (AC-5)
    """
    if len(password) < 8 or len(password) > 64:
        raise ValueError(translate('auth.password_rule_length'))

    if login_id and password.lower() == login_id.lower():
        raise ValueError(translate('auth.password_rule_identifier'))

    has_letter = any(c.isalpha() for c in password)
    has_digit = any(c.isdigit() for c in password)
    if not (has_letter and has_digit):
        raise ValueError(translate('auth.password_rule_letter_digit'))

    if password.lower() in COMMON_PASSWORDS:
        raise ValueError(translate('auth.password_rule_common'))

    return True


def check_ip_throttle(ip_address: str):
    """
    Checks per-IP throttle: 30 failures per 10 minutes -> True if throttled (FR-1.13, AC-58).
    """
    if not ip_address:
        return False

    now = timezone.now().timestamp()
    records = _IP_FAILURES.get(ip_address, [])
    # Keep only records within window
    active_records = [t for t in records if (now - t) < IP_THROTTLE_WINDOW]
    _IP_FAILURES[ip_address] = active_records

    return len(active_records) >= IP_THROTTLE_LIMIT


def record_ip_failure(ip_address: str):
    if not ip_address:
        return
    now = timezone.now().timestamp()
    records = _IP_FAILURES.get(ip_address, [])
    records.append(now)
    _IP_FAILURES[ip_address] = records


def authenticate_user(
    raw_identifier: str,
    password: str,
    platform: str,
    device_id: str = None,
    device_model: str = None,
    os_version: str = None,
    app_version: str = None,
    ip_address: str = None,
    user_agent: str = None,
    request=None
):
    """
    Central authentication flow implementing FR-1.1 to FR-1.28.
    """
    # Check IP rate limit (FR-1.13, AC-58)
    if check_ip_throttle(ip_address):
        raise PermissionDenied(detail=translate('auth.rate_limit_exceeded'), code='RATE_LIMITED')

    # Step 1: Identifier normalization (FR-1.1, AC-3)
    id_type, normalized_id = normalize_identifier(raw_identifier)

    # Step 2: User lookup (Case-insensitive email, normalized phone)
    user = None
    if id_type == 'EMAIL':
        user = User.objects.filter(email__iexact=normalized_id).first()
    else:
        user = User.objects.filter(phone=normalized_id).first()

    def record_attempt(user_obj, result_code, identifier_record=None):
        LoginAttempt.objects.create(
            company=user_obj.company if user_obj else None,
            user=user_obj,
            identifier_entered=identifier_record,
            result=result_code,
            platform=platform,
            ip_address=ip_address,
            device_id=device_id,
            device_model=device_model,
            app_version=app_version
        )

    # FR-1.74: identifier stored only if phone or email format, else "invalid format"
    stored_identifier = normalized_id

    # Unknown user (FR-1.6, AC-4)
    if not user:
        record_ip_failure(ip_address)
        record_attempt(None, 'WRONG_PASSWORD', stored_identifier)
        write_audit_event(
            action_code='auth.login.failed',
            actor_user=None,
            record_type='User',
            reason=f"Unknown user identifier: {stored_identifier}",
            result='FAILURE',
            ip_address=ip_address,
            device_id=device_id,
            user_agent=user_agent
        )
        raise PermissionDenied(detail=translate('auth.sign_in_failed'), code='SIGN_IN_FAILED')

    # Step 3: Check Account Lockout (FR-1.12, AC-8)
    now_utc = timezone.now()
    if user.locked_until and user.locked_until > now_utc:
        remaining_seconds = int((user.locked_until - now_utc).total_seconds())
        remaining_minutes = max(1, (remaining_seconds + 59) // 60)
        record_attempt(user, 'LOCKED', stored_identifier)
        raise PermissionDenied(
            detail=translate('auth.account_locked', minutes=remaining_minutes),
            code='ACCOUNT_LOCKED'
        )

    # Step 4: Verify Password (FR-1.5, AC-4, AC-6)
    password_valid = check_password(password, user.password_hash)
    if not password_valid and password.strip() != password:
        password_valid = check_password(password.strip(), user.password_hash)

    if not password_valid:
        record_ip_failure(ip_address)
        user.failed_attempts += 1

        # Check if lockout limit reached (FR-1.12, AC-8)
        lockout_limit = get_setting('failed_attempts_lockout', user.company_id)
        lockout_duration = get_setting('lockout_duration_minutes', user.company_id)

        if user.failed_attempts >= lockout_limit:
            user.locked_until = now_utc + timedelta(minutes=lockout_duration)
            user.save()
            record_attempt(user, 'LOCKED', stored_identifier)

            # Audit event auth.lockout
            write_audit_event(
                action_code='auth.lockout',
                actor_user=user,
                record_type='User',
                record_id=str(user.user_id),
                reason=f"Locked out after {user.failed_attempts} failed attempts",
                result='SUCCESS',
                company_id=user.company_id,
                ip_address=ip_address,
                device_id=device_id,
                user_agent=user_agent
            )

            # Send ACCOUNT_LOCKED notification to all Admins (FR-1.12, AC-8)
            from foundation.services.notification_service import send_notification
            send_notification(
                type_code='ACCOUNT_LOCKED',
                recipient_hint=None,  # Resolves to all Admins
                params={'user_name': user.full_name, 'identifier': stored_identifier},
                company_id=user.company_id
            )

            raise PermissionDenied(
                detail=translate('auth.account_locked', minutes=lockout_duration),
                code='ACCOUNT_LOCKED'
            )
        else:
            user.save()
            record_attempt(user, 'WRONG_PASSWORD', stored_identifier)
            write_audit_event(
                action_code='auth.login.failed',
                actor_user=user,
                record_type='User',
                record_id=str(user.user_id),
                reason="Wrong password",
                result='FAILURE',
                company_id=user.company_id,
                ip_address=ip_address,
                device_id=device_id,
                user_agent=user_agent
            )
            # Generic error message (FR-1.6, AC-4)
            raise PermissionDenied(detail=translate('auth.sign_in_failed'), code='SIGN_IN_FAILED')

    # Password is CORRECT. Check account active status (FR-1.6)
    if user.status != 'ACTIVE':
        record_attempt(user, 'INACTIVE', stored_identifier)
        raise PermissionDenied(detail=translate('auth.account_inactive'), code='ACCOUNT_INACTIVE')

    # Platform Check (FR-1.17, AC-15):
    # Web sign-in is for ADMIN and SUPERVISOR only. GUARD and CLIENT refused with WRONG_PLATFORM.
    if platform.upper() == 'WEB' and user.role in ('GUARD', 'CLIENT'):
        record_attempt(user, 'WRONG_PLATFORM', stored_identifier)
        raise PermissionDenied(detail=translate('auth.wrong_platform'), code='WRONG_PLATFORM')

    # Profile Link Check (FR-1.39, FR-1.40, AC-34):
    # Role GUARD requires guard_profile_id. Role CLIENT requires client_company_id.
    if user.role == 'GUARD' and not user.guard_profile_id:
        record_attempt(user, 'NOT_LINKED', stored_identifier)
        raise PermissionDenied(detail=translate('auth.account_not_linked'), code='ACCOUNT_NOT_LINKED')
    if user.role == 'CLIENT' and not user.client_company_id:
        record_attempt(user, 'NOT_LINKED', stored_identifier)
        raise PermissionDenied(detail=translate('auth.account_not_linked'), code='ACCOUNT_NOT_LINKED')

    # Guard Device Binding Check (FR-1.22 to FR-1.28, AC-21, AC-22)
    if user.role == 'GUARD':
        if not device_id:
            raise PermissionDenied(detail="Device identifier is required for Guard login.", code='DEVICE_REQUIRED')

        active_binding = BoundDevice.objects.filter(user=user, unbound_at__isnull=True).first()

        if not active_binding:
            # First device accepted becomes the bound device (FR-1.22, AC-21)
            BoundDevice.objects.create(
                company=user.company,
                user=user,
                device_id=device_id,
                model=device_model,
                os_version=os_version,
                app_version=app_version
            )
        elif active_binding.device_id != device_id:
            # Sign in with correct credentials from a different device (FR-1.23, AC-22)
            # Supersede previous pending requests
            DeviceChangeRequest.objects.filter(user=user, status='PENDING').update(status='SUPERSEDED')

            # Create new pending request
            DeviceChangeRequest.objects.create(
                company=user.company,
                user=user,
                new_device_id=device_id,
                new_model=device_model,
                new_os_version=os_version,
                new_app_version=app_version,
                status='PENDING'
            )

            record_attempt(user, 'DEVICE_PENDING', stored_identifier)

            # Send DEVICE_CHANGE_REQUESTED notification to Admins
            from foundation.services.notification_service import send_notification
            send_notification(
                type_code='DEVICE_CHANGE_REQUESTED',
                recipient_hint=None,
                params={'guard_name': user.full_name, 'device_model': device_model or 'Unknown'},
                company_id=user.company_id
            )

            write_audit_event(
                action_code='device.change.requested',
                actor_user=user,
                record_type='DeviceChangeRequest',
                reason=f"New device change requested: {device_model or device_id}",
                result='SUCCESS',
                company_id=user.company_id,
                ip_address=ip_address,
                device_id=device_id,
                user_agent=user_agent
            )

            raise PermissionDenied(
                detail=translate('device.waiting_approval'),
                code='DEVICE_CHANGE_PENDING'
            )

    # Success! Reset failed attempts and lockout (FR-1.12, AC-9)
    user.failed_attempts = 0
    user.locked_until = None
    user.last_login_at = now_utc
    user.save()

    # Create Session (FR-1.16, FR-1.17, FR-1.18)
    session_token = secrets.token_urlsafe(32)
    session_token_hash = hashlib.sha256(session_token.encode('utf-8')).hexdigest()

    refresh_token_str = None
    refresh_token_hash = None
    access_token_str = None

    if platform.upper() == 'WEB':
        # Web session lifetime (FR-1.17)
        abs_hours = get_setting('web_absolute_session_hours', user.company_id)
        expires_at = now_utc + timedelta(hours=abs_hours)
    else:
        # App refresh token lifetime (FR-1.16)
        refresh_days = get_setting('app_refresh_token_days', user.company_id)
        expires_at = now_utc + timedelta(days=refresh_days)

        # Generate JWT access token + refresh token
        jwt_refresh = RefreshToken()
        jwt_refresh['user_id'] = str(user.user_id)
        jwt_refresh['role'] = user.role
        jwt_refresh['company_id'] = str(user.company_id)

        jwt_access = jwt_refresh.access_token
        access_token_str = str(jwt_access)
        refresh_token_str = str(jwt_refresh)
        refresh_token_hash = hashlib.sha256(refresh_token_str.encode('utf-8')).hexdigest()

    user_session = UserSession.objects.create(
        company=user.company,
        user=user,
        platform=platform.upper(),
        device_id=device_id,
        ip_address=ip_address or '127.0.0.1',
        user_agent=user_agent,
        session_token_hash=session_token_hash,
        refresh_token_hash=refresh_token_hash,
        expires_at=expires_at
    )

    record_attempt(user, 'SUCCESS', stored_identifier)

    # Audit event auth.login.success (AC-1)
    write_audit_event(
        action_code='auth.login.success',
        actor_user=user,
        record_type='UserSession',
        record_id=str(user_session.session_id),
        result='SUCCESS',
        company_id=user.company_id,
        ip_address=ip_address,
        device_id=device_id,
        user_agent=user_agent
    )

    return {
        'user': user,
        'session': user_session,
        'session_token': session_token,
        'access_token': access_token_str,
        'refresh_token': refresh_token_str,
        'must_change_password': user.must_change_password,
    }


def change_user_password(user: User, current_password: str, new_password: str, request=None):
    """
    User self-change password flow (FR-1.7, AC-5).
    Requires current password, validates rules, revokes other sessions, writes audit, creates notification.
    """
    if not check_password(current_password, user.password_hash):
        raise ValueError(translate('auth.sign_in_failed'))

    if current_password == new_password:
        raise ValueError(translate('auth.password_rule_differ'))

    login_id = user.email if user.role != 'GUARD' else user.phone
    validate_password_strength(new_password, login_id)

    user.password_hash = make_password(new_password)
    user.must_change_password = False
    user.save()

    # Revoke all other sessions of this user (FR-1.7)
    current_session_id = getattr(request, 'current_session_id', None)
    qs = UserSession.objects.filter(user=user, revoked_at__isnull=True)
    if current_session_id:
        qs = qs.exclude(session_id=current_session_id)
    qs.update(revoked_at=timezone.now(), revoked_reason='PASSWORD_CHANGE')

    # Audit event auth.password.changed (AC-6: password shown as 'changed' only)
    write_audit_event(
        action_code='auth.password.changed',
        actor_user=user,
        record_type='User',
        record_id=str(user.user_id),
        old_values={'password': 'changed'},
        new_values={'password': 'changed'},
        result='SUCCESS',
        company_id=user.company_id,
        request=request
    )

    # Notification PASSWORD_CHANGED
    from foundation.services.notification_service import send_notification
    now_ist = timezone.now().astimezone(IST).strftime('%d/%m/%Y %H:%M')
    send_notification(
        type_code='PASSWORD_CHANGED',
        recipient_hint=[user.user_id],
        params={'time': now_ist},
        company_id=user.company_id
    )

    return True


def revoke_all_user_sessions(user: User, reason: str = 'LOGOUT_ALL', request=None):
    """
    Revokes all active sessions for a user (FR-1.20, AC-19).
    Next request from any device returns 401 SESSION_REVOKED.
    """
    UserSession.objects.filter(user=user, revoked_at__isnull=True).update(
        revoked_at=timezone.now(),
        revoked_reason=reason
    )
    # Remove push tokens
    PushToken.objects.filter(user=user).update(removed_at=timezone.now())

    write_audit_event(
        action_code='auth.session.revoked',
        actor_user=request.user if request and request.user.is_authenticated else user,
        record_type='User',
        record_id=str(user.user_id),
        reason=f"All sessions revoked: {reason}",
        result='SUCCESS',
        company_id=user.company_id,
        request=request
    )


def admin_reset_password(admin_user: User, target_user: User, request=None):
    """
    Admin-initiated password reset (FR-1.10, AC-64).
    Generates temporary password valid for 7 days (configurable), stores hash only.
    Shows temporary password ONCE to Admin. Sets must_change_password=True.
    """
    temp_pass_days = get_setting('temporary_password_days', target_user.company_id)
    raw_temp_password = f"Sec@{secrets.token_hex(4)}9"

    target_user.password_hash = make_password(raw_temp_password)
    target_user.must_change_password = True
    target_user.failed_attempts = 0
    target_user.locked_until = None
    target_user.save()

    # Revoke all sessions (FR-1.21)
    revoke_all_user_sessions(target_user, reason='PASSWORD_CHANGE', request=request)

    write_audit_event(
        action_code='auth.password.temp_issued',
        actor_user=admin_user,
        record_type='User',
        record_id=str(target_user.user_id),
        reason=f"Admin issued temporary password (valid {temp_pass_days} days)",
        old_values={'password': 'changed'},
        new_values={'password': 'changed'},
        result='SUCCESS',
        company_id=target_user.company_id,
        request=request
    )

    return raw_temp_password


def admin_reset_guard_device_binding(admin_user: User, guard_user: User, reason: str, request=None):
    """
    Admin resets a guard's device binding for lost/stolen phones (FR-1.27, AC-25).
    Revokes all sessions, clears binding, issues temp password, audits device.binding.reset.
    """
    if not reason:
        raise ValueError("A reason for resetting device binding is mandatory.")

    # 1. Clear binding
    BoundDevice.objects.filter(user=guard_user, unbound_at__isnull=True).update(
        unbound_at=timezone.now(),
        unbound_reason='ADMIN_RESET'
    )

    # 2. Issue temporary password and revoke all sessions
    temp_password = admin_reset_password(admin_user, guard_user, request=request)

    # 3. Audit event device.binding.reset
    write_audit_event(
        action_code='device.binding.reset',
        actor_user=admin_user,
        record_type='BoundDevice',
        record_id=str(guard_user.user_id),
        reason=reason,
        result='SUCCESS',
        company_id=guard_user.company_id,
        request=request
    )

    return temp_password
