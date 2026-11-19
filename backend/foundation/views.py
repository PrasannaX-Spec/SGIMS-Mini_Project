import csv
import io
import uuid
import secrets
from datetime import datetime, date, timedelta
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from django.db.models import Q
from django.contrib.auth.hashers import make_password
from rest_framework import status, viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.exceptions import PermissionDenied, NotFound, ValidationError

from foundation.models import (
    User, Company, ScopeGrant, UserSession, BoundDevice,
    DeviceChangeRequest, LoginAttempt, OneTimeToken, Notification,
    NotificationDelivery, NotificationPreference, PushToken,
    AuditEvent, ConsentRecord, SystemSetting
)
from foundation.serializers import (
    UserListSerializer, UserDetailSerializer, ScopeGrantSerializer,
    LoginAttemptSerializer, DeviceChangeRequestSerializer,
    NotificationSerializer, NotificationDeliverySerializer,
    AuditEventSerializer, ConsentRecordSerializer
)
from foundation.resources import translate
from foundation.services.settings_service import (
    get_setting, set_setting, SETTING_DEFINITIONS
)
from foundation.services.audit_service import (
    write_audit_event, export_audit_csv
)
from foundation.services.scope_service import (
    HasCapabilityAndScope, ScopedQuerySetMixin,
    invalidate_user_scope_cache
)
from foundation.services.auth_service import (
    authenticate_user, change_user_password, revoke_all_user_sessions,
    admin_reset_password, admin_reset_guard_device_binding,
    validate_password_strength, normalize_identifier
)
from foundation.services.notification_service import send_notification
from foundation.services.consent_service import (
    record_consent, has_current_consent, needs_reconsent
)


# ==============================================================================
# AUTHENTICATION VIEWS (W1, W2, W3, M1, M2, M3)
# ==============================================================================

class SignInView(APIView):
    """
    Sign-in endpoint for web and mobile (FR-1.1 to FR-1.28, AC-1, AC-2, AC-3, AC-4, AC-15).
    """
    permission_classes = [AllowAny]
    authentication_classes = []
    required_capability = 'foundation.legal.read'  # Accessible without prior login

    def post(self, request):
        identifier = request.data.get('identifier') or request.data.get('email')
        password = request.data.get('password')
        platform = request.data.get('platform', 'WEB').upper()
        device_id = request.data.get('device_id')
        device_model = request.data.get('device_model')
        os_version = request.data.get('os_version')
        app_version = request.data.get('app_version')

        if not identifier or not password:
            return Response({
                'detail': translate('auth.sign_in_failed'),
                'code': 'SIGN_IN_FAILED'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Authenticate
        try:
            auth_result = authenticate_user(
                raw_identifier=identifier,
                password=password,
                platform=platform,
                device_id=device_id,
                device_model=device_model,
                os_version=os_version,
                app_version=app_version,
                ip_address=getattr(request, 'client_ip', None),
                user_agent=getattr(request, 'user_agent_str', None),
                request=request
            )
        except ValueError as e:
            return Response({
                'detail': str(e),
                'code': 'FORMAT_ERROR'
            }, status=status.HTTP_400_BAD_REQUEST)

        user = auth_result['user']
        response_data = {
            'user': UserDetailSerializer(user).data,
            'must_change_password': user.must_change_password,
            'platform': platform
        }

        if platform == 'WEB':
            # Set HttpOnly, Secure, SameSite Cookie (FR-1.17)
            response = Response(response_data, status=status.HTTP_200_OK)
            response.set_cookie(
                key='sec_session',
                value=auth_result['session_token'],
                httponly=True,
                secure=False,  # Set to True in production with HTTPS
                samesite='Lax',
                max_age=12 * 3600
            )
            return response
        else:
            # Mobile JWT tokens (FR-1.16)
            response_data['access_token'] = auth_result['access_token']
            response_data['refresh_token'] = auth_result['refresh_token']
            response_data['session_id'] = str(auth_result['session'].session_id)
            return Response(response_data, status=status.HTTP_200_OK)


class SignOutView(APIView):
    """
    Logout ends the current session on the server and removes push token (FR-1.19, AC-18).
    """
    permission_classes = [IsAuthenticated]
    required_capability = 'foundation.profile.self_manage'

    def post(self, request):
        session = getattr(request, 'current_session', None)
        if session:
            session.revoked_at = timezone.now()
            session.revoked_reason = 'LOGOUT'
            session.save()

            # Remove push token for this session (FR-1.19)
            PushToken.objects.filter(session=session).update(removed_at=timezone.now())

            write_audit_event(
                action_code='auth.session.revoked',
                actor_user=request.user,
                record_type='UserSession',
                record_id=str(session.session_id),
                reason='User signed out',
                result='SUCCESS',
                company_id=request.user.company_id,
                request=request
            )

        response = Response({'detail': 'Signed out successfully.'}, status=status.HTTP_200_OK)
        response.delete_cookie('sec_session')
        return response


class SignOutAllView(APIView):
    """
    Logout from all devices revokes all sessions for the user (FR-1.20, AC-19).
    """
    permission_classes = [IsAuthenticated]
    required_capability = 'foundation.profile.self_manage'

    def post(self, request):
        revoke_all_user_sessions(request.user, reason='LOGOUT_ALL', request=request)
        response = Response({'detail': 'Signed out from all devices.'}, status=status.HTTP_200_OK)
        response.delete_cookie('sec_session')
        return response


class ChangePasswordView(APIView):
    """
    Self change password endpoint (FR-1.7, FR-1.11, AC-5, AC-7).
    """
    permission_classes = [IsAuthenticated]
    required_capability = 'foundation.profile.self_manage'

    def post(self, request):
        current_password = request.data.get('current_password')
        new_password = request.data.get('new_password')
        confirm_password = request.data.get('confirm_password')

        if not current_password or not new_password:
            return Response({'detail': 'Current and new password are required.'}, status=status.HTTP_400_BAD_REQUEST)

        if new_password != confirm_password:
            return Response({'detail': 'New password and confirmation do not match.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            change_user_password(request.user, current_password, new_password, request=request)
            return Response({'detail': 'Password changed successfully.'}, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response({'detail': str(e), 'code': 'PASSWORD_RULE_FAILED'}, status=status.HTTP_400_BAD_REQUEST)


class ForgotPasswordView(APIView):
    """
    Forgot password for web users (FR-1.8, AC-12).
    Always returns identical confirmation text.
    """
    permission_classes = [AllowAny]
    authentication_classes = []
    required_capability = 'foundation.legal.read'

    def post(self, request):
        email = request.data.get('email', '').strip().lower()
        if not email or '@' not in email:
            return Response({
                'detail': translate('auth.forgot_password_confirmation')
            }, status=status.HTTP_200_OK)

        user = User.objects.filter(email__iexact=email, status='ACTIVE').first()
        if user and user.role in ('ADMIN', 'SUPERVISOR'):
            reset_mins = get_setting('password_reset_link_minutes', user.company_id)
            token_raw = secrets.token_urlsafe(32)
            token_hash = make_password(token_raw)

            # Invalidate older tokens for this user (FR-1.9)
            OneTimeToken.objects.filter(user=user, purpose='RESET', used_at__isnull=True).update(used_at=timezone.now())

            OneTimeToken.objects.create(
                company=user.company,
                user=user,
                purpose='RESET',
                token_hash=token_hash,
                expires_at=timezone.now() + timedelta(minutes=reset_mins)
            )

            write_audit_event(
                action_code='auth.password.reset',
                actor_user=user,
                record_type='User',
                record_id=str(user.user_id),
                reason=f"Password reset link generated (valid {reset_mins} mins)",
                result='SUCCESS',
                company_id=user.company_id,
                request=request
            )

        # Always return identical confirmation message (FR-1.8, AC-12)
        return Response({
            'detail': translate('auth.forgot_password_confirmation')
        }, status=status.HTTP_200_OK)


class ResetPasswordView(APIView):
    """
    Set password from reset link or invite link (FR-1.8, FR-1.9, FR-1.44, AC-13, AC-14, AC-60).
    """
    permission_classes = [AllowAny]
    authentication_classes = []
    required_capability = 'foundation.legal.read'

    def post(self, request):
        token_str = request.data.get('token')
        new_password = request.data.get('new_password')
        confirm_password = request.data.get('confirm_password')

        if not token_str or not new_password:
            return Response({'detail': 'Token and new password are required.'}, status=status.HTTP_400_BAD_REQUEST)

        if new_password != confirm_password:
            return Response({'detail': 'Passwords do not match.'}, status=status.HTTP_400_BAD_REQUEST)

        # Find valid token
        valid_token = None
        for tok in OneTimeToken.objects.filter(used_at__isnull=True, expires_at__gt=timezone.now()):
            from django.contrib.auth.hashers import check_password
            if check_password(token_str, tok.token_hash):
                valid_token = tok
                break

        if not valid_token:
            return Response({
                'detail': translate('auth.reset_link_invalid'),
                'code': 'INVALID_TOKEN'
            }, status=status.HTTP_400_BAD_REQUEST)

        user = valid_token.user
        login_id = user.email or user.phone
        try:
            validate_password_strength(new_password, login_id)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        user.password_hash = make_password(new_password)
        user.must_change_password = False
        user.failed_attempts = 0
        user.locked_until = None
        user.save()

        # Mark token as used (FR-1.9, AC-13)
        valid_token.used_at = timezone.now()
        valid_token.save()

        # Revoke all sessions (FR-1.9, AC-14)
        revoke_all_user_sessions(user, reason='PASSWORD_CHANGE', request=request)

        write_audit_event(
            action_code='auth.password.reset',
            actor_user=user,
            record_type='User',
            record_id=str(user.user_id),
            reason=f"Password successfully reset using {valid_token.purpose} token",
            old_values={'password': 'changed'},
            new_values={'password': 'changed'},
            result='SUCCESS',
            company_id=user.company_id,
            request=request
        )

        return Response({'detail': 'Password set successfully. Please sign in.'}, status=status.HTTP_200_OK)


class MyProfileView(APIView):
    """
    Self-profile view and edit (FR-1.50, AC-63).
    Only contact_phone and notification_preferences can be updated.
    Name, role, login ID, scope, status cannot be edited here.
    """
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'foundation.profile.self_manage'

    def get(self, request):
        return Response(UserDetailSerializer(request.user).data)

    def patch(self, request):
        user = request.user
        contact_phone = request.data.get('contact_phone')
        push_normal = request.data.get('push_normal')
        browser_notifications = request.data.get('browser_notifications')

        old_vals = {}
        new_vals = {}

        if contact_phone is not None:
            old_vals['contact_phone'] = user.contact_phone
            user.contact_phone = contact_phone
            new_vals['contact_phone'] = contact_phone
            user.save(update_fields=['contact_phone'])

        # Notification Preferences
        pref, _ = NotificationPreference.objects.get_or_create(user=user)
        if push_normal is not None:
            old_vals['push_normal'] = pref.push_normal
            pref.push_normal = bool(push_normal)
            new_vals['push_normal'] = pref.push_normal

        if browser_notifications is not None:
            old_vals['browser_notifications'] = pref.browser_notifications
            pref.browser_notifications = bool(browser_notifications)
            new_vals['browser_notifications'] = pref.browser_notifications

        pref.save()

        if new_vals:
            write_audit_event(
                action_code='user.edited',
                actor_user=user,
                record_type='User',
                record_id=str(user.user_id),
                old_values=old_vals,
                new_values=new_vals,
                reason='User updated own profile fields',
                result='SUCCESS',
                company_id=user.company_id,
                request=request
            )

        return Response(UserDetailSerializer(user).data)


# ==============================================================================
# USER MANAGEMENT VIEWS (Admin, W5, W6, W7)
# ==============================================================================

class UserViewSet(viewsets.ModelViewSet):
    """
    Admin User Management CRUD (FR-1.43 to FR-1.51, AC-34, AC-36, AC-37, AC-38).
    """
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'foundation.user.view'
    serializer_class = UserListSerializer
    lookup_field = 'user_id'

    def get_queryset(self):
        qs = User.objects.filter(company_id=self.request.user.company_id).order_by('-created_at')

        role_filter = self.request.query_params.get('role')
        if role_filter:
            qs = qs.filter(role=role_filter)

        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)

        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(full_name__icontains=search) |
                Q(email__icontains=search) |
                Q(phone__icontains=search)
            )

        return qs

    def get_serializer_class(self):
        if self.action in ('retrieve', 'create', 'update', 'partial_update'):
            return UserDetailSerializer
        return UserListSerializer

    def create(self, request, *args, **kwargs):
        self.required_capability = 'foundation.user.create_edit'
        self.check_permissions(request)

        data = request.data
        role = data.get('role')
        full_name = data.get('full_name')
        email = data.get('email', '').strip().lower() or None
        phone = data.get('phone', '').strip() or None
        delivery_method = data.get('delivery_method', 'temporary_password')
        guard_profile_id = data.get('guard_profile_id')
        client_company_id = data.get('client_company_id')

        if not full_name or not role:
            return Response({'detail': 'Full name and role are required.'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate role & login ID rules (FR-1.2)
        if role == 'GUARD':
            if not phone:
                return Response({'detail': 'Mobile phone number is required for Guard accounts.'}, status=status.HTTP_400_BAD_REQUEST)
            try:
                _, normalized_phone = normalize_identifier(phone)
                phone = normalized_phone
            except ValueError as e:
                return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        else:
            if not email:
                return Response({'detail': f'Email address is required for {role} accounts.'}, status=status.HTTP_400_BAD_REQUEST)
            try:
                _, normalized_email = normalize_identifier(email)
                email = normalized_email
            except ValueError as e:
                return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # Check uniqueness (FR-1.3)
        if email and User.objects.filter(email__iexact=email).exists():
            return Response({'detail': translate('user.duplicate_email')}, status=status.HTTP_400_BAD_REQUEST)
        if phone and User.objects.filter(phone=phone).exists():
            return Response({'detail': translate('user.duplicate_phone')}, status=status.HTTP_400_BAD_REQUEST)

        # Initial password
        temp_password = None
        if delivery_method == 'temporary_password' or role == 'GUARD':
            temp_password = f"Sec@{secrets.token_hex(4)}9"
            password_hash = make_password(temp_password)
            must_change = True
        else:
            temp_password = None
            password_hash = make_password(secrets.token_urlsafe(20))
            must_change = True

        user = User.objects.create(
            company=request.user.company,
            role=role,
            full_name=full_name,
            email=email,
            phone=phone,
            password_hash=password_hash,
            must_change_password=must_change,
            status='ACTIVE',
            guard_profile_id=guard_profile_id,
            client_company_id=client_company_id,
            created_by=request.user
        )

        # Scope assignment
        if role == 'ADMIN':
            ScopeGrant.objects.create(company=user.company, user=user, scope_type='ALL', effective_from=date.today())
        elif role == 'GUARD':
            ScopeGrant.objects.create(company=user.company, user=user, scope_type='OWN_PROFILE', effective_from=date.today())
        elif role == 'CLIENT' and client_company_id:
            ScopeGrant.objects.create(company=user.company, user=user, scope_type='COMPANY', target_id=client_company_id, effective_from=date.today())

        # If invite method
        invite_token = None
        if delivery_method == 'invite' and email:
            raw_token = secrets.token_urlsafe(32)
            OneTimeToken.objects.create(
                company=user.company,
                user=user,
                purpose='INVITE',
                token_hash=make_password(raw_token),
                expires_at=timezone.now() + timedelta(hours=72)
            )
            invite_token = raw_token

        write_audit_event(
            action_code='user.created',
            actor_user=request.user,
            record_type='User',
            record_id=str(user.user_id),
            new_values={'full_name': full_name, 'role': role, 'email': email, 'phone': phone},
            result='SUCCESS',
            company_id=user.company_id,
            request=request
        )

        resp_data = UserDetailSerializer(user).data
        if temp_password:
            resp_data['temporary_password'] = temp_password  # Shown once (FR-1.10, AC-64)
        if invite_token:
            resp_data['invite_token'] = invite_token

        return Response(resp_data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        self.required_capability = 'foundation.user.create_edit'
        self.check_permissions(request)

        user = self.get_object()
        data = request.data

        old_vals = {}
        new_vals = {}

        if 'full_name' in data and data['full_name'] != user.full_name:
            old_vals['full_name'] = user.full_name
            user.full_name = data['full_name']
            new_vals['full_name'] = user.full_name

        if 'email' in data:
            new_email = data['email'].strip().lower() or None
            if new_email != user.email:
                if new_email and User.objects.filter(email__iexact=new_email).exclude(user_id=user.user_id).exists():
                    return Response({'detail': translate('user.duplicate_email')}, status=status.HTTP_400_BAD_REQUEST)
                old_vals['email'] = user.email
                user.email = new_email
                new_vals['email'] = new_email
                # Changing login ID revokes sessions (FR-1.45, AC-14)
                revoke_all_user_sessions(user, reason='ROLE_CHANGE', request=request)

        if 'phone' in data:
            new_phone = data['phone'].strip() or None
            if new_phone:
                _, norm_phone = normalize_identifier(new_phone)
                new_phone = norm_phone
            if new_phone != user.phone:
                if new_phone and User.objects.filter(phone=new_phone).exclude(user_id=user.user_id).exists():
                    return Response({'detail': translate('user.duplicate_phone')}, status=status.HTTP_400_BAD_REQUEST)
                old_vals['phone'] = user.phone
                user.phone = new_phone
                new_vals['phone'] = new_phone
                revoke_all_user_sessions(user, reason='ROLE_CHANGE', request=request)

        if 'role' in data and data['role'] != user.role:
            # Role can change only between Admin and Supervisor (FR-1.30)
            if user.role not in ('ADMIN', 'SUPERVISOR') or data['role'] not in ('ADMIN', 'SUPERVISOR'):
                return Response({'detail': 'Role changes are only permitted between Admin and Supervisor.'}, status=status.HTTP_400_BAD_REQUEST)

            # Prevent demoting self or leaving 0 Admins (FR-1.47, AC-36)
            if user.user_id == request.user.user_id:
                return Response({'detail': translate('user.self_deactivate_prevented')}, status=status.HTTP_400_BAD_REQUEST)

            active_admins = User.objects.filter(company_id=user.company_id, role='ADMIN', status='ACTIVE').exclude(user_id=user.user_id)
            if not active_admins.exists():
                return Response({'detail': translate('user.min_admin_prevented')}, status=status.HTTP_400_BAD_REQUEST)

            old_vals['role'] = user.role
            user.role = data['role']
            new_vals['role'] = user.role
            revoke_all_user_sessions(user, reason='ROLE_CHANGE', request=request)

        user.version += 1
        user.updated_by = request.user
        user.save()

        if new_vals:
            write_audit_event(
                action_code='user.edited',
                actor_user=request.user,
                record_type='User',
                record_id=str(user.user_id),
                old_values=old_vals,
                new_values=new_vals,
                result='SUCCESS',
                company_id=user.company_id,
                request=request
            )

        return Response(UserDetailSerializer(user).data)

    def destroy(self, request, *args, **kwargs):
        # NO delete endpoint (FR-1.46, AC-37)
        raise PermissionDenied("User deletion is forbidden. Use deactivate instead.")


# Additional User actions
class UserDeactivateView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'foundation.user.manage'

    def post(self, request, user_id):
        user = User.objects.filter(user_id=user_id, company_id=request.user.company_id).first()
        if not user:
            raise NotFound()

        # Prevent deactivating self (FR-1.47, AC-36)
        if user.user_id == request.user.user_id:
            return Response({'detail': translate('user.self_deactivate_prevented')}, status=status.HTTP_400_BAD_REQUEST)

        # Prevent leaving 0 Admins (FR-1.47, AC-36)
        if user.role == 'ADMIN':
            active_admins = User.objects.filter(company_id=user.company_id, role='ADMIN', status='ACTIVE').exclude(user_id=user.user_id)
            if not active_admins.exists():
                return Response({'detail': translate('user.min_admin_prevented')}, status=status.HTTP_400_BAD_REQUEST)

        reason = request.data.get('reason', '').strip()
        if not reason:
            return Response({'detail': translate('user.deactivation_reason_required')}, status=status.HTTP_400_BAD_REQUEST)

        user.status = 'INACTIVE'
        user.deactivated_at = timezone.now()
        user.deactivated_by = request.user
        user.deactivation_reason = reason
        user.save()

        # Revoke all sessions (FR-1.21, AC-20)
        revoke_all_user_sessions(user, reason='DEACTIVATED', request=request)

        # Audit event
        write_audit_event(
            action_code='user.deactivated',
            actor_user=request.user,
            record_type='User',
            record_id=str(user.user_id),
            reason=reason,
            result='SUCCESS',
            company_id=user.company_id,
            request=request
        )

        return Response({'detail': translate('user.deactivated_success')}, status=status.HTTP_200_OK)


class UserReactivateView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'foundation.user.manage'

    def post(self, request, user_id):
        user = User.objects.filter(user_id=user_id, company_id=request.user.company_id).first()
        if not user:
            raise NotFound()

        user.status = 'ACTIVE'
        user.deactivated_at = None
        user.deactivated_by = None
        user.deactivation_reason = None
        user.save()

        write_audit_event(
            action_code='user.reactivated',
            actor_user=request.user,
            record_type='User',
            record_id=str(user.user_id),
            result='SUCCESS',
            company_id=user.company_id,
            request=request
        )

        return Response({'detail': translate('user.reactivated_success')}, status=status.HTTP_200_OK)


class UserAdminResetPasswordView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'foundation.user.manage'

    def post(self, request, user_id):
        user = User.objects.filter(user_id=user_id, company_id=request.user.company_id).first()
        if not user:
            raise NotFound()

        temp_password = admin_reset_password(request.user, user, request=request)
        return Response({
            'detail': 'Temporary password issued.',
            'temporary_password': temp_password  # Shown once (FR-1.10, AC-64)
        }, status=status.HTTP_200_OK)


class UserUnlockView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'foundation.user.manage'

    def post(self, request, user_id):
        user = User.objects.filter(user_id=user_id, company_id=request.user.company_id).first()
        if not user:
            raise NotFound()

        user.failed_attempts = 0
        user.locked_until = None
        user.save()

        write_audit_event(
            action_code='auth.unlock',
            actor_user=request.user,
            record_type='User',
            record_id=str(user.user_id),
            reason='Admin unlocked account',
            result='SUCCESS',
            company_id=user.company_id,
            request=request
        )

        return Response({'detail': 'Account unlocked successfully.'}, status=status.HTTP_200_OK)


class UserResetDeviceView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'foundation.user.manage'

    def post(self, request, user_id):
        user = User.objects.filter(user_id=user_id, company_id=request.user.company_id, role='GUARD').first()
        if not user:
            raise NotFound()

        reason = request.data.get('reason', '').strip()
        if not reason:
            return Response({'detail': 'A reason for resetting device binding is mandatory.'}, status=status.HTTP_400_BAD_REQUEST)

        temp_password = admin_reset_guard_device_binding(request.user, user, reason, request=request)
        return Response({
            'detail': translate('device.binding_reset'),
            'temporary_password': temp_password
        }, status=status.HTTP_200_OK)


class UserLoginHistoryView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'foundation.login_history.view'

    def get(self, request, user_id):
        user = User.objects.filter(user_id=user_id, company_id=request.user.company_id).first()
        if not user:
            raise NotFound()

        attempts = LoginAttempt.objects.filter(user=user).order_by('-attempted_at')[:100]
        return Response(LoginAttemptSerializer(attempts, many=True).data)


# ==============================================================================
# DEVICE CHANGE REQUESTS VIEWS (Admin, W8)
# ==============================================================================

class DeviceChangeRequestViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'foundation.device.decide'
    serializer_class = DeviceChangeRequestSerializer
    lookup_field = 'request_id'

    def get_queryset(self):
        qs = DeviceChangeRequest.objects.filter(company_id=self.request.user.company_id).select_related('user').order_by('-requested_at')
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs


class DeviceChangeApproveView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'foundation.device.decide'

    def post(self, request, request_id):
        dcr = DeviceChangeRequest.objects.filter(request_id=request_id, company_id=request.user.company_id).first()
        if not dcr:
            raise NotFound()

        if dcr.status != 'PENDING':
            return Response({'detail': f'Request is already {dcr.status}.'}, status=status.HTTP_400_BAD_REQUEST)

        # 1. Approve DCR
        dcr.status = 'APPROVED'
        dcr.decided_by = request.user
        dcr.decided_at = timezone.now()
        dcr.save()

        # 2. Revoke old device sessions and unbind old device
        BoundDevice.objects.filter(user=dcr.user, unbound_at__isnull=True).update(
            unbound_at=timezone.now(),
            unbound_reason='CHANGE_APPROVED'
        )
        revoke_all_user_sessions(dcr.user, reason='DEVICE_CHANGE', request=request)

        # 3. Bind new device
        BoundDevice.objects.create(
            company=dcr.company,
            user=dcr.user,
            device_id=dcr.new_device_id,
            model=dcr.new_model,
            os_version=dcr.new_os_version,
            app_version=dcr.new_app_version
        )

        # 4. Audit
        write_audit_event(
            action_code='device.change.approved',
            actor_user=request.user,
            record_type='DeviceChangeRequest',
            record_id=str(dcr.request_id),
            result='SUCCESS',
            company_id=dcr.company_id,
            request=request
        )

        # 5. Notify supervisor
        send_notification(
            type_code='DEVICE_CHANGE_DECIDED',
            recipient_hint=None,
            params={'decision': 'approved', 'guard_name': dcr.user.full_name},
            company_id=dcr.company_id
        )

        return Response({'detail': translate('device.approved')}, status=status.HTTP_200_OK)


class DeviceChangeRejectView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'foundation.device.decide'

    def post(self, request, request_id):
        dcr = DeviceChangeRequest.objects.filter(request_id=request_id, company_id=request.user.company_id).first()
        if not dcr:
            raise NotFound()

        if dcr.status != 'PENDING':
            return Response({'detail': f'Request is already {dcr.status}.'}, status=status.HTTP_400_BAD_REQUEST)

        note = request.data.get('decision_note', '').strip()
        if not note:
            return Response({'detail': translate('device.rejection_note_required')}, status=status.HTTP_400_BAD_REQUEST)

        dcr.status = 'REJECTED'
        dcr.decided_by = request.user
        dcr.decided_at = timezone.now()
        dcr.decision_note = note
        dcr.save()

        write_audit_event(
            action_code='device.change.rejected',
            actor_user=request.user,
            record_type='DeviceChangeRequest',
            record_id=str(dcr.request_id),
            reason=note,
            result='SUCCESS',
            company_id=dcr.company_id,
            request=request
        )

        # Notify supervisor
        send_notification(
            type_code='DEVICE_CHANGE_DECIDED',
            recipient_hint=None,
            params={'decision': 'rejected', 'guard_name': dcr.user.full_name},
            company_id=dcr.company_id
        )

        return Response({'detail': translate('device.rejected')}, status=status.HTTP_200_OK)


# ==============================================================================
# NOTIFICATIONS VIEWS (W9, M6, W15)
# ==============================================================================

class NotificationListView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'foundation.notification.read'

    def get(self, request):
        notifs = Notification.objects.filter(user=request.user).order_by('-created_at')[:50]
        unread_count = Notification.objects.filter(user=request.user, read_at__isnull=True).count()
        return Response({
            'unread_count': unread_count,
            'notifications': NotificationSerializer(notifs, many=True).data
        })


class NotificationMarkReadView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'foundation.notification.read'

    def post(self, request, notification_id):
        notif = Notification.objects.filter(notification_id=notification_id, user=request.user).first()
        if not notif:
            raise NotFound()
        notif.read_at = timezone.now()
        notif.save(update_fields=['read_at'])
        return Response({'detail': 'Notification marked as read.'})


class NotificationMarkAllReadView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'foundation.notification.read'

    def post(self, request):
        Notification.objects.filter(user=request.user, read_at__isnull=True).update(read_at=timezone.now())
        return Response({'detail': 'All notifications marked as read.'})


class NotificationDeliveryLogView(APIView):
    """
    Delivery log for Admins (W15, FR-1.60).
    """
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'foundation.audit.view'

    def get(self, request):
        deliveries = NotificationDelivery.objects.select_related('notification__user').order_by('-last_attempt_at')[:100]
        return Response(NotificationDeliverySerializer(deliveries, many=True).data)


# ==============================================================================
# AUDIT LOG VIEWS (Admin, W11)
# ==============================================================================

class AuditLogListView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'foundation.audit.view'

    def get(self, request):
        qs = AuditEvent.objects.filter(company_id=request.user.company_id).order_by('-occurred_at')

        action = request.query_params.get('action')
        if action:
            qs = qs.filter(action_code=action)

        record_type = request.query_params.get('record_type')
        if record_type:
            qs = qs.filter(record_type=record_type)

        record_id = request.query_params.get('record_id')
        if record_id:
            qs = qs.filter(record_id=record_id)

        user_filter = request.query_params.get('user_id')
        if user_filter:
            qs = qs.filter(actor_user_id=user_filter)

        events = qs[:100]
        return Response({
            'total_count': qs.count(),
            'events': AuditEventSerializer(events, many=True).data
        })


class AuditLogExportCSVView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'foundation.audit.view'

    def get(self, request):
        qs = AuditEvent.objects.filter(company_id=request.user.company_id).order_by('-occurred_at')

        csv_content, capped, total = export_audit_csv(qs, request.user)
        response = HttpResponse(csv_content, content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="audit_export_{date.today().isoformat()}.csv"'
        if capped:
            response['X-Export-Capped'] = 'true'
            response['X-Total-Rows'] = str(total)
        return response


# ==============================================================================
# SYSTEM SETTINGS VIEWS (Admin, W12)
# ==============================================================================

class SystemSettingsView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'foundation.settings.manage'

    def get(self, request):
        company_id = request.user.company_id
        items = []
        for key, defn in SETTING_DEFINITIONS.items():
            curr_val = get_setting(key, company_id)
            items.append({
                'key': key,
                'label': defn['label'],
                'current_value': curr_val,
                'default_value': defn['default'],
                'min': defn.get('min'),
                'max': defn.get('max'),
                'type': defn['type'].__name__,
                'used_by': defn.get('used_by')
            })
        return Response({'settings': items})

    def post(self, request):
        company_id = request.user.company_id
        updates = request.data.get('settings', {})
        reason = request.data.get('reason', 'Updated via System Settings screen')

        errors = {}
        for key, raw_val in updates.items():
            try:
                set_setting(company_id, key, raw_val, user=request.user, reason=reason)
            except Exception as e:
                errors[key] = str(e)

        if errors:
            return Response({'errors': errors}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'detail': translate('settings.saved_success')})


# ==============================================================================
# LEGAL & CONSENT VIEWS (W13, W14, M4, M5)
# ==============================================================================

class TermsAndConditionsView(APIView):
    permission_classes = [AllowAny]
    required_capability = 'foundation.legal.read'

    def get(self, request):
        version = get_setting('current_policy_version')
        return Response({
            'version': str(version),
            'effective_date': '2026-11-11',
            'status': 'DRAFT FOR LEGAL REVIEW',
            'sections': [
                {'title': '1. Who runs the system', 'content': 'Security Agency ERP System for Karnataka, India.'},
                {'title': '2. Accounts and credentials', 'content': 'Credentials must not be shared. Guards are restricted to one bound phone.'},
                {'title': '3. Acceptable use', 'content': 'The system is strictly for legitimate security agency operations.'},
                {'title': '4. Duties of guards', 'content': 'Honest check-in, patrol scan completion, and real-time incident reporting.'},
                {'title': '5. Panic and alerts', 'content': 'Emergency panic buttons are for operational alerts, not a substitute for police 112.'}
            ]
        })


class PrivacyPolicyView(APIView):
    permission_classes = [AllowAny]
    required_capability = 'foundation.legal.read'

    def get(self, request):
        version = get_setting('current_policy_version')
        return Response({
            'version': str(version),
            'effective_date': '2026-11-11',
            'status': 'DRAFT FOR LEGAL REVIEW',
            'sections': [
                {'title': '1. Data Controller', 'content': 'Security Agency Management.'},
                {'title': '2. Data collected', 'content': 'Name, contact number, duty attendance timestamps, GPS location during shift hours only.'},
                {'title': '3. Location tracking notice', 'content': 'Location is collected during active duty hours only (from check-in to check-out).'},
                {'title': '4. Retention', 'content': 'Attendance and audit data retained in accordance with statutory requirements.'}
            ]
        })


class ConsentSubmitView(APIView):
    permission_classes = [IsAuthenticated]
    required_capability = 'foundation.profile.self_manage'

    def post(self, request):
        item = request.data.get('item')
        decision = request.data.get('decision')
        device_id = request.data.get('device_id')
        app_version = request.data.get('app_version')

        if not item or not decision:
            return Response({'detail': 'Item and decision are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            record_consent(
                user=request.user,
                item=item,
                decision=decision,
                device_id=device_id,
                app_version=app_version,
                request=request
            )
            return Response({'detail': 'Consent decision recorded.'}, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ConsentStatusView(APIView):
    permission_classes = [IsAuthenticated]
    required_capability = 'foundation.profile.self_manage'

    def get(self, request):
        user = request.user
        items = ['TERMS_PRIVACY', 'LOCATION', 'CAMERA', 'NOTIFICATIONS']
        status_map = {item: has_current_consent(user, item) for item in items}
        return Response({
            'needs_reconsent': needs_reconsent(user),
            'consent_status': status_map
        })
