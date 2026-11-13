import hashlib
import logging
from django.utils import timezone
from rest_framework import authentication
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework_simplejwt.tokens import AccessToken
from foundation.models import User, UserSession
from foundation.resources import translate

logger = logging.getLogger(__name__)

ALLOWED_PASSWORD_CHANGE_PATHS = (
    '/api/auth/change-password/',
    '/api/auth/logout/',
    '/api/legal/terms/',
    '/api/legal/privacy/',
    '/terms',
    '/privacy'
)


class SessionAndJWTAuthentication(authentication.BaseAuthentication):
    """
    Unified Authentication supporting:
    1. Web: HttpOnly Session Cookie or X-Session-Token header
    2. Mobile: Bearer JWT Access Token
    (FR-1.16, FR-1.17, FR-1.21)
    """
    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')
        session_token = request.COOKIES.get('sec_session') or request.headers.get('X-Session-Token')

        # 1. Try Bearer JWT first if present
        if auth_header and auth_header.startswith('Bearer '):
            token_str = auth_header.split(' ')[1].strip()
            return self._authenticate_jwt(request, token_str)

        # 2. Try Web Session token
        if session_token:
            return self._authenticate_session_token(request, session_token)

        return None

    def _authenticate_jwt(self, request, token_str):
        try:
            token = AccessToken(token_str)
            user_id = token.get('user_id')
            if not user_id:
                return None

            user = User.objects.filter(user_id=user_id).first()
            if not user:
                raise AuthenticationFailed(translate('auth.sign_in_failed'))

            if user.status != 'ACTIVE':
                raise AuthenticationFailed(translate('auth.account_inactive'), code='ACCOUNT_INACTIVE')

            if user.must_change_password:
                path = request.path
                is_allowed = any(path.startswith(p) for p in ALLOWED_PASSWORD_CHANGE_PATHS)
                if not is_allowed:
                    raise PermissionDenied(
                        detail=translate('auth.password_change_required'),
                        code='PASSWORD_CHANGE_REQUIRED'
                    )

            # Find matching active session for user
            session = UserSession.objects.filter(
                user=user,
                platform='ANDROID',
                revoked_at__isnull=True,
                expires_at__gt=timezone.now()
            ).order_by('-issued_at').first()

            if not session:
                raise AuthenticationFailed(translate('auth.session_revoked'), code='SESSION_REVOKED')

            request.current_session = session
            request.current_session_id = session.session_id
            return (user, None)

        except Exception as e:
            raise AuthenticationFailed(str(e))

    def _authenticate_session_token(self, request, raw_token):
        token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
        session = UserSession.objects.filter(
            session_token_hash=token_hash,
            platform='WEB',
            revoked_at__isnull=True
        ).select_related('user', 'company').first()

        if not session:
            raise AuthenticationFailed(translate('auth.session_revoked'), code='SESSION_REVOKED')

        if session.expires_at < timezone.now():
            session.revoked_at = timezone.now()
            session.revoked_reason = 'IDLE_TIMEOUT'
            session.save()
            raise AuthenticationFailed(translate('auth.session_revoked'), code='SESSION_EXPIRED')

        user = session.user
        if user.status != 'ACTIVE':
            raise AuthenticationFailed(translate('auth.account_inactive'), code='ACCOUNT_INACTIVE')

        # Check must_change_password (FR-1.11, AC-7)
        if user.must_change_password:
            path = request.path
            is_allowed = any(path.startswith(p) for p in ALLOWED_PASSWORD_CHANGE_PATHS)
            if not is_allowed:
                raise PermissionDenied(
                    detail=translate('auth.password_change_required'),
                    code='PASSWORD_CHANGE_REQUIRED'
                )

        # Update last_seen_at
        session.last_seen_at = timezone.now()
        session.save(update_fields=['last_seen_at'])

        request.current_session = session
        request.current_session_id = session.session_id
        return (user, None)

    def authenticate_header(self, request):
        return 'Bearer realm="api"'
