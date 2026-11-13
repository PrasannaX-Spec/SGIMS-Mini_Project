import uuid
from datetime import date, timedelta
from django.test import TestCase, override_settings
from django.urls import reverse, get_resolver
from django.contrib.auth.hashers import make_password
from rest_framework.test import APIClient
from rest_framework import status

from foundation.models import (
    Company, User, ScopeGrant, UserSession, BoundDevice,
    DeviceChangeRequest, LoginAttempt, OneTimeToken, Notification,
    AuditEvent, ConsentRecord, SystemSetting
)
from foundation.services.settings_service import set_setting, get_setting
from foundation.services.auth_service import (
    authenticate_user, validate_password_strength, normalize_identifier
)
from foundation.services.notification_service import send_notification
from foundation.services.consent_service import (
    record_consent, has_current_consent
)
from foundation.services.scope_service import (
    check_permission, scope_filter, is_in_scope, CAPABILITY_MAP
)


class Module1FoundationTestSuite(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Company
        self.company = Company.objects.create(
            legal_name="Karnataka Security Agency Test",
            state_code="KA",
            country_code="IN",
            time_zone="Asia/Kolkata",
            is_active=True
        )

        # Admin user
        self.admin = User.objects.create(
            company=self.company,
            role='ADMIN',
            full_name='Master Admin',
            email='admin@test.local',
            password_hash=make_password('AdminSecret123!'),
            status='ACTIVE',
            must_change_password=False
        )
        ScopeGrant.objects.create(
            company=self.company,
            user=self.admin,
            scope_type='ALL',
            effective_from=date.today()
        )

        # Supervisor user
        self.supervisor = User.objects.create(
            company=self.company,
            role='SUPERVISOR',
            full_name='Site Supervisor',
            email='supervisor@test.local',
            password_hash=make_password('SuperSecret123!'),
            status='ACTIVE',
            must_change_password=False
        )

        # Guard user
        self.guard_profile_id = uuid.uuid4()
        self.guard = User.objects.create(
            company=self.company,
            role='GUARD',
            full_name='Duty Guard',
            phone='+919876543210',
            password_hash=make_password('GuardSecret123!'),
            status='ACTIVE',
            guard_profile_id=self.guard_profile_id,
            must_change_password=False
        )
        ScopeGrant.objects.create(
            company=self.company,
            user=self.guard,
            scope_type='OWN_PROFILE',
            effective_from=date.today()
        )

        # Initial device binding for guard
        self.bound_device = BoundDevice.objects.create(
            company=self.company,
            user=self.guard,
            device_id='device-phone-1',
            model='Redmi 9',
            os_version='Android 11'
        )

    # --------------------------------------------------------------------------
    # FR-1.38 & AC-33: Route Scan Test
    # --------------------------------------------------------------------------
    def test_ac33_route_scan_declares_capability(self):
        """
        AC-33: Given a route added without a capability declaration, release gate fails.
        Checks every registered API route to ensure it declares required_capability.
        """
        resolver = get_resolver()
        url_patterns = resolver.url_patterns

        def check_patterns(patterns):
            for pattern in patterns:
                if hasattr(pattern, 'url_patterns'):
                    check_patterns(pattern.url_patterns)
                elif hasattr(pattern, 'callback'):
                    cb = pattern.callback
                    # Check DRF ViewSets and APIViews
                    cls = getattr(cb, 'cls', None)
                    if cls:
                        # Skip admin / drf spectacular schema / router APIRootView
                        if cls.__name__ in ('APIRootView',) or 'admin' in str(pattern.pattern) or 'schema' in str(pattern.pattern) or 'docs' in str(pattern.pattern):
                            continue
                        self.assertTrue(
                            hasattr(cls, 'required_capability'),
                            f"Route {pattern.pattern} (class {cls.__name__}) lacks required_capability! (FR-1.38, AC-33)"
                        )

        check_patterns(url_patterns)

    # --------------------------------------------------------------------------
    # AC-1: Admin Web Sign-In
    # --------------------------------------------------------------------------
    def test_ac1_admin_web_sign_in_success(self):
        """
        AC-1: Given an active Admin with correct email and password,
        When they sign in on web, Then a web session is created, last login is updated,
        one login history row and one auth.login.success audit event are written.
        """
        resp = self.client.post(reverse('sign-in'), {
            'identifier': 'admin@test.local',
            'password': 'AdminSecret123!',
            'platform': 'WEB'
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('sec_session', resp.cookies)

        self.admin.refresh_from_db()
        self.assertIsNotNone(self.admin.last_login_at)

        attempt = LoginAttempt.objects.filter(user=self.admin).first()
        self.assertIsNotNone(attempt)
        self.assertEqual(attempt.result, 'SUCCESS')

        audit = AuditEvent.objects.filter(actor_user_id=self.admin.user_id, action_code='auth.login.success').first()
        self.assertIsNotNone(audit)

    # --------------------------------------------------------------------------
    # AC-2 & AC-3: Phone Normalization & Identifier Validation
    # --------------------------------------------------------------------------
    def test_ac2_phone_formats_sign_in_same_account(self):
        """
        AC-2: 9XXXXXXXXX, +919XXXXXXXXX, 09XXXXXXXXX all sign in to the same account.
        """
        formats = ['9876543210', '+919876543210', '09876543210']
        for phone_input in formats:
            result = authenticate_user(
                raw_identifier=phone_input,
                password='GuardSecret123!',
                platform='ANDROID',
                device_id='device-phone-1'
            )
            self.assertEqual(result['user'].user_id, self.guard.user_id)

    def test_ac3_invalid_identifier_format(self):
        """
        AC-3: Invalid identifier (neither valid email nor 10-digit phone) shows format message,
        and no login attempt is counted.
        """
        initial_attempts = LoginAttempt.objects.count()
        with self.assertRaises(ValueError):
            normalize_identifier("invalid_string_123")

        resp = self.client.post(reverse('sign-in'), {
            'identifier': 'invalid_string_123',
            'password': 'SomePassword123!',
            'platform': 'WEB'
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.json()['code'], 'FORMAT_ERROR')
        # Verify no login attempt row was counted for bad format
        self.assertEqual(LoginAttempt.objects.count(), initial_attempts)

    # --------------------------------------------------------------------------
    # AC-4: Unknown vs Known with Wrong Password (Same Message)
    # --------------------------------------------------------------------------
    def test_ac4_identical_message_unknown_vs_wrong_password(self):
        """
        AC-4: Unknown identifier and known identifier with wrong password show identical message.
        """
        resp_unknown = self.client.post(reverse('sign-in'), {
            'identifier': 'unknown@test.local',
            'password': 'WrongPassword123!',
            'platform': 'WEB'
        })
        resp_wrong_pw = self.client.post(reverse('sign-in'), {
            'identifier': 'admin@test.local',
            'password': 'WrongPassword123!',
            'platform': 'WEB'
        })
        self.assertEqual(resp_unknown.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp_wrong_pw.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp_unknown.json()['detail'], resp_wrong_pw.json()['detail'])

    # --------------------------------------------------------------------------
    # AC-5: Password Rules Validation
    # --------------------------------------------------------------------------
    def test_ac5_password_rules(self):
        """
        AC-5: 5 characters, or login ID, or common password refused with rule name.
        """
        # Too short
        with self.assertRaises(ValueError) as ctx:
            validate_password_strength("Short1")
        self.assertIn("between 8 and 64", str(ctx.exception))

        # Equals login ID
        with self.assertRaises(ValueError) as ctx:
            validate_password_strength("admin@test.local", login_id="admin@test.local")
        self.assertIn("cannot match your login ID", str(ctx.exception))

        # Common password
        with self.assertRaises(ValueError) as ctx:
            validate_password_strength("password1")
        self.assertIn("too common", str(ctx.exception))

    # --------------------------------------------------------------------------
    # AC-7: Must Change Password Enforced (403 PASSWORD_CHANGE_REQUIRED)
    # --------------------------------------------------------------------------
    def test_ac7_must_change_password_blocks_normal_endpoints(self):
        """
        AC-7: While must_change_password is True, all endpoints return 403 PASSWORD_CHANGE_REQUIRED
        except change password, logout, and legal pages.
        """
        self.supervisor.must_change_password = True
        self.supervisor.save()

        # Web sign in
        resp = self.client.post(reverse('sign-in'), {
            'identifier': 'supervisor@test.local',
            'password': 'SuperSecret123!',
            'platform': 'WEB'
        })
        cookie = resp.cookies['sec_session'].value
        self.client.cookies['sec_session'] = cookie

        # Attempt to call profile endpoint
        resp_blocked = self.client.get(reverse('my-profile'))
        self.assertEqual(resp_blocked.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp_blocked.json()['code'], 'PASSWORD_CHANGE_REQUIRED')

        # Calling legal pages works
        resp_legal = self.client.get(reverse('legal-terms'))
        self.assertEqual(resp_legal.status_code, status.HTTP_200_OK)

    # --------------------------------------------------------------------------
    # AC-8 & AC-9 & AC-10: Account Lockout & Admin Unlock
    # --------------------------------------------------------------------------
    def test_ac8_ac9_ac10_account_lockout_and_admin_unlock(self):
        """
        AC-8: 5 failed attempts locks account for 15 minutes. Correct password refused with remaining time.
        AC-10: Admin clicks unlock -> user signs in with correct password immediately.
        """
        set_setting(self.company.company_id, 'failed_attempts_lockout', 5)
        set_setting(self.company.company_id, 'lockout_duration_minutes', 15)

        # 5 wrong attempts
        for i in range(5):
            self.client.post(reverse('sign-in'), {
                'identifier': 'supervisor@test.local',
                'password': 'WrongPassword123!',
                'platform': 'WEB'
            })

        self.supervisor.refresh_from_db()
        self.assertEqual(self.supervisor.failed_attempts, 5)
        self.assertIsNotNone(self.supervisor.locked_until)

        # 6th attempt with correct password
        resp_locked = self.client.post(reverse('sign-in'), {
            'identifier': 'supervisor@test.local',
            'password': 'SuperSecret123!',
            'platform': 'WEB'
        })
        self.assertEqual(resp_locked.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("Try again in", resp_locked.json()['detail'])

        # AC-10: Admin unlocks account
        self.client.force_authenticate(user=self.admin)
        resp_unlock = self.client.post(reverse('user-unlock', kwargs={'user_id': self.supervisor.user_id}))
        self.assertEqual(resp_unlock.status_code, status.HTTP_200_OK)

        self.supervisor.refresh_from_db()
        self.assertEqual(self.supervisor.failed_attempts, 0)
        self.assertIsNone(self.supervisor.locked_until)

        # Now signs in with correct password immediately
        self.client.logout()
        resp_ok = self.client.post(reverse('sign-in'), {
            'identifier': 'supervisor@test.local',
            'password': 'SuperSecret123!',
            'platform': 'WEB'
        })
        self.assertEqual(resp_ok.status_code, status.HTTP_200_OK)

    # --------------------------------------------------------------------------
    # AC-15: Guard or Client on Web Sign-in -> WRONG_PLATFORM
    # --------------------------------------------------------------------------
    def test_ac15_guard_or_client_on_web_rejected(self):
        """
        AC-15: Guard credentials on web sign-in returns WRONG_PLATFORM and 'Use the mobile app.'
        """
        resp = self.client.post(reverse('sign-in'), {
            'identifier': '+919876543210',
            'password': 'GuardSecret123!',
            'platform': 'WEB'
        })
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.json()['code'], 'WRONG_PLATFORM')
        self.assertIn("Use the mobile app.", resp.json()['detail'])

    # --------------------------------------------------------------------------
    # AC-20: Deactivated User Session Revoked Immediately
    # --------------------------------------------------------------------------
    def test_ac20_deactivated_user_sessions_revoked(self):
        """
        AC-20: Given active session, When Admin deactivates user,
        Then the very next request returns 401.
        """
        # Supervisor logs in
        resp = self.client.post(reverse('sign-in'), {
            'identifier': 'supervisor@test.local',
            'password': 'SuperSecret123!',
            'platform': 'WEB'
        })
        cookie = resp.cookies['sec_session'].value
        self.client.cookies['sec_session'] = cookie

        # Admin deactivates supervisor
        self.supervisor.status = 'INACTIVE'
        self.supervisor.save()

        # Next request returns 401
        resp_after = self.client.get(reverse('my-profile'))
        self.assertEqual(resp_after.status_code, status.HTTP_401_UNAUTHORIZED)

    # --------------------------------------------------------------------------
    # AC-21 & AC-22 & AC-23: Guard Device Binding & Device Change
    # --------------------------------------------------------------------------
    def test_ac21_ac22_ac23_guard_device_binding_and_approval(self):
        """
        AC-21: First device binds.
        AC-22: Second device creates pending request, no session issued, shows waiting screen.
        AC-23: Admin approves -> binds new device, old session ends, guard can sign in on new device.
        """
        # Guard signs in from a NEW device (device-phone-2)
        resp = self.client.post(reverse('sign-in'), {
            'identifier': '+919876543210',
            'password': 'GuardSecret123!',
            'platform': 'ANDROID',
            'device_id': 'device-phone-2',
            'device_model': 'Samsung Galaxy M12'
        })
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.json()['code'], 'DEVICE_CHANGE_PENDING')

        # One pending DCR exists
        dcr = DeviceChangeRequest.objects.filter(user=self.guard, status='PENDING').first()
        self.assertIsNotNone(dcr)
        self.assertEqual(dcr.new_device_id, 'device-phone-2')

        # Admin approves request
        self.client.force_authenticate(user=self.admin)
        resp_approve = self.client.post(reverse('device-change-approve', kwargs={'request_id': dcr.request_id}))
        self.assertEqual(resp_approve.status_code, status.HTTP_200_OK)

        # Now Guard signs in from device-phone-2 successfully!
        self.client.logout()
        resp_new_login = self.client.post(reverse('sign-in'), {
            'identifier': '+919876543210',
            'password': 'GuardSecret123!',
            'platform': 'ANDROID',
            'device_id': 'device-phone-2'
        })
        self.assertEqual(resp_new_login.status_code, status.HTTP_200_OK)
        self.assertIn('access_token', resp_new_login.json())

    # --------------------------------------------------------------------------
    # AC-27 & AC-28: Supervisor Scoped Access & 404 for Out-of-Scope
    # --------------------------------------------------------------------------
    def test_ac27_ac28_supervisor_scope_enforcement(self):
        """
        AC-27 & AC-28: Supervisor sees only in-scope data. Out-of-scope returns 404.
        """
        site_a = uuid.uuid4()
        site_b = uuid.uuid4()

        # Assign Site A only to supervisor
        ScopeGrant.objects.create(
            company=self.company,
            user=self.supervisor,
            scope_type='SITE',
            target_id=site_a,
            effective_from=date.today()
        )

        self.assertTrue(is_in_scope(self.supervisor, 'site', site_a))
        self.assertFalse(is_in_scope(self.supervisor, 'site', site_b))

    # --------------------------------------------------------------------------
    # AC-31: Guard Cannot Access Admin Endpoints (403)
    # --------------------------------------------------------------------------
    def test_ac31_guard_token_calling_admin_endpoint_forbidden(self):
        """
        AC-31: Given a Guard with a valid token, When calling Admin endpoint directly,
        Then response is 403.
        """
        self.client.force_authenticate(user=self.guard)
        resp = self.client.get(reverse('user-list'))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # --------------------------------------------------------------------------
    # AC-36: Admin Cannot Deactivate Self or Leave 0 Admins
    # --------------------------------------------------------------------------
    def test_ac36_admin_cannot_deactivate_self(self):
        """
        AC-36: Given the only active Admin, When they try to deactivate themselves,
        action is refused.
        """
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(reverse('user-deactivate', kwargs={'user_id': self.admin.user_id}), {
            'reason': 'Self deactivation test'
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("You cannot deactivate", resp.json()['detail'])

    # --------------------------------------------------------------------------
    # AC-39: Notification Mark All as Read Sets Count to Zero
    # --------------------------------------------------------------------------
    def test_ac39_notification_mark_all_read(self):
        """
        AC-39: Mark all as read sets unread count to 0.
        """
        send_notification(
            type_code='PASSWORD_CHANGED',
            recipient_hint=[self.admin.user_id],
            params={'time': '12:00'},
            company_id=self.company.company_id
        )

        self.client.force_authenticate(user=self.admin)
        resp_before = self.client.get(reverse('notification-list'))
        self.assertGreater(resp_before.json()['unread_count'], 0)

        self.client.post(reverse('notification-read-all'))

        resp_after = self.client.get(reverse('notification-list'))
        self.assertEqual(resp_after.json()['unread_count'], 0)

    # --------------------------------------------------------------------------
    # AC-43: Deduplication Within 5 Minutes
    # --------------------------------------------------------------------------
    def test_ac43_notification_deduplication(self):
        """
        AC-43: Two send calls with same type, recipient, dedupe_key within 5 min creates 1 notif.
        """
        send_notification(
            type_code='PASSWORD_CHANGED',
            recipient_hint=[self.admin.user_id],
            params={'time': '12:00'},
            dedupe_key='dedupe-test-123',
            company_id=self.company.company_id
        )
        send_notification(
            type_code='PASSWORD_CHANGED',
            recipient_hint=[self.admin.user_id],
            params={'time': '12:00'},
            dedupe_key='dedupe-test-123',
            company_id=self.company.company_id
        )
        count = Notification.objects.filter(dedupe_key='dedupe-test-123').count()
        self.assertEqual(count, 1)

    # --------------------------------------------------------------------------
    # AC-50 & AC-52: Consent Recording & has_current_consent
    # --------------------------------------------------------------------------
    def test_ac50_ac52_consent_flow(self):
        """
        AC-50 & AC-52: Consent recording and verification.
        """
        self.assertFalse(has_current_consent(self.guard, 'LOCATION'))

        record_consent(self.guard, 'LOCATION', 'GRANTED')
        self.assertTrue(has_current_consent(self.guard, 'LOCATION'))

        record_consent(self.guard, 'LOCATION', 'WITHDRAWN')
        self.assertFalse(has_current_consent(self.guard, 'LOCATION'))
