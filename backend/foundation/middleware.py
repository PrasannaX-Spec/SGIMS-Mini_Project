import uuid
from django.utils import timezone
from django.http import JsonResponse
from foundation.models import UserSession
from foundation.resources import translate


class RequestContextMiddleware:
    """
    Populates request with request_id, client_ip, user_agent_str, device_id.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = request.headers.get('X-Request-Id') or str(uuid.uuid4())
        request.device_id = request.headers.get('X-Device-Id')

        # Client IP
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            request.client_ip = x_forwarded_for.split(',')[0].strip()
        else:
            request.client_ip = request.META.get('REMOTE_ADDR')

        request.user_agent_str = request.META.get('HTTP_USER_AGENT', '')

        response = self.get_response(request)
        response['X-Request-Id'] = request.request_id
        return response


class SessionValidationMiddleware:
    """
    Per-request session & access validation middleware:
    - Enforces FR-1.21: deactivating a user or revoking session takes effect on NEXT request.
    - Enforces FR-1.11: while must_change_password is set, blocks every request except
      change password, logout, and legal pages with HTTP 403 PASSWORD_CHANGE_REQUIRED.
    (AC-7, AC-14, AC-19, AC-20)
    """
    ALLOWED_PASSWORD_CHANGE_PATHS = (
        '/api/auth/change-password/',
        '/api/auth/logout/',
        '/api/legal/terms/',
        '/api/legal/privacy/',
        '/terms',
        '/privacy'
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)

        if user and getattr(user, 'is_authenticated', False):
            # Check user status (FR-1.21, AC-20)
            if user.status != 'ACTIVE':
                return JsonResponse({
                    'detail': translate('auth.account_inactive'),
                    'code': 'ACCOUNT_INACTIVE'
                }, status=401)

            # Check session revocation (FR-1.20, AC-19)
            session = getattr(request, 'current_session', None)
            if session:
                if session.revoked_at is not None:
                    return JsonResponse({
                        'detail': translate('auth.session_revoked'),
                        'code': 'SESSION_REVOKED'
                    }, status=401)

                if session.expires_at and session.expires_at < timezone.now():
                    session.revoked_at = timezone.now()
                    session.revoked_reason = 'IDLE_TIMEOUT'
                    session.save()
                    return JsonResponse({
                        'detail': translate('auth.session_revoked'),
                        'code': 'SESSION_EXPIRED'
                    }, status=401)

            # Check must_change_password (FR-1.11, AC-7)
            if user.must_change_password:
                path = request.path
                is_allowed = any(path.startswith(p) for p in self.ALLOWED_PASSWORD_CHANGE_PATHS)
                if not is_allowed:
                    return JsonResponse({
                        'detail': translate('auth.password_change_required'),
                        'code': 'PASSWORD_CHANGE_REQUIRED'
                    }, status=403)

        return self.get_response(request)

