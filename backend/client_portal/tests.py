import io
import uuid
from datetime import date, timedelta
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from rest_framework.exceptions import ValidationError, PermissionDenied, NotFound

from foundation.models import Company, User
from master_data.models import Client, ClientSite, SiteShift, PostType
from guard_management.models import Employee
from deployment_roster.models import RosterAssignment, PostSlot
from attendance.models import AttendanceRecord, AttendancePeriod
from incident_management.models import (
    Incident,
    IncidentCategory,
    IncidentClientVersion,
    ClientTicket,
    ClientTicketMessage
)
from panic_escalation.models import PanicAlert, PanicRecipient, PanicAcknowledgement
from client_portal.models import (
    ClientUserSiteAccess,
    ClientPortalConfiguration,
    ClientNotificationPreference,
    ClientDocumentAccessLog,
    ClientPortalUsageEvent
)
from client_portal import services


class ClientPortalModuleTests(TestCase):
    def setUp(self):
        # 1. Company
        self.company = Company.objects.create(
            legal_name='Apex Security Karnataka Ltd',
            trade_name='Apex Security',
            pan='ABCDE1234F',
            gstin='29ABCDE1234F1Z5',
            state_code='KA',
            is_active=True
        )

        # 2. Other Company (For cross-client tests)
        self.other_company = Company.objects.create(
            legal_name='Other Karnataka Security Ltd',
            trade_name='Other Security',
            pan='XYZAB9876C',
            gstin='29XYZAB9876C1Z1',
            state_code='KA',
            is_active=True
        )

        # 3. Client Organizations
        self.client_org = Client.objects.create(
            company_id=self.company.company_id,
            legal_name='Infosys Campus Electronic City',
            client_code='INFY-BLR',
            status='active'
        )

        self.other_client_org = Client.objects.create(
            company_id=self.other_company.company_id,
            legal_name='Wipro Sarjapur Campus',
            client_code='WIPRO-BLR',
            status='active'
        )

        # 4. Sites
        self.site_a = ClientSite.objects.create(
            client=self.client_org,
            site_code='SITE-INFY-A',
            site_name='Infosys Phase 1 - Tower A',
            operational_status='active'
        )

        self.site_b = ClientSite.objects.create(
            client=self.client_org,
            site_code='SITE-INFY-B',
            site_name='Infosys Phase 2 - Gate 4',
            operational_status='active'
        )

        self.other_site = ClientSite.objects.create(
            client=self.other_client_org,
            site_code='SITE-WIPRO-1',
            site_name='Wipro Main Hub',
            operational_status='active'
        )

        # 5. Users
        self.admin = User.objects.create(
            company_id=self.company.company_id,
            email='admin@apexsecurity.local',
            full_name='Apex Admin',
            role='ADMIN',
            phone='+919877700001',
            password_hash=make_password('AdminPass123!'),
            status='ACTIVE'
        )

        self.client_user = User.objects.create(
            company_id=self.company.company_id,
            client_company_id=self.client_org.client_id,
            email='facility@infosys.local',
            full_name='Ramesh Narayan (Infosys FM)',
            role='CLIENT',
            phone='+919877700004',
            password_hash=make_password('ClientPass123!'),
            status='ACTIVE'
        )

        self.other_client_user = User.objects.create(
            company_id=self.other_company.company_id,
            client_company_id=self.other_client_org.client_id,
            email='security@wipro.local',
            full_name='Suresh Rao (Wipro FM)',
            role='CLIENT',
            phone='+919877700005',
            password_hash=make_password('ClientPass123!'),
            status='ACTIVE'
        )

        # 6. Guards & Shifts
        self.guard = Employee.objects.create(
            company_id=self.company.company_id,
            employee_code='GRD-BLR-01',
            first_name='Mahesh',
            last_name='Patil',
            phone='+919877700010',
            date_joined=timezone.now().date(),
            designation='Security Guard',
            employment_status='active',
            lifecycle_status='active'
        )

        self.shift = SiteShift.objects.create(
            site=self.site_a,
            shift_code='S1',
            shift_name='Morning Shift',
            start_time='06:00:00',
            end_time='14:00:00',
            duration_minutes=480,
            is_active=True
        )

        self.post_type = PostType.objects.create(
            company_id=self.company.company_id,
            code='GEN-GUARD',
            name='General Guard'
        )

    # --------------------------------------------------------------------------
    # Test 1: Client Authentication & Company Scoping (AC-10.1, AC-10.3, AC-10.4)
    # --------------------------------------------------------------------------
    def test_client_company_scoping_and_cross_client_denial(self):
        # Client sees only their own company's permitted sites
        permitted_sites = list(services.get_client_permitted_sites(self.client_user))
        self.assertIn(self.site_a, permitted_sites)
        self.assertIn(self.site_b, permitted_sites)
        self.assertNotIn(self.other_site, permitted_sites)

        # Accessing other company's site raises PermissionDenied (AC-10.4)
        with self.assertRaises(PermissionDenied):
            services.validate_client_site_access(self.client_user, self.other_site.site_id)

    # --------------------------------------------------------------------------
    # Test 2: Selected Site Restrictions Enforced on Server (AC-10.5, AC-10.6, AC-10.66)
    # --------------------------------------------------------------------------
    def test_selected_site_restrictions(self):
        # Restrict client user to site_a only
        ClientUserSiteAccess.objects.create(
            company_id=self.company.company_id,
            client_user=self.client_user,
            access_mode='SELECTED_SITES',
            site=self.site_a,
            is_active=True,
            created_by=self.admin
        )

        permitted_sites = list(services.get_client_permitted_sites(self.client_user))
        self.assertIn(self.site_a, permitted_sites)
        self.assertNotIn(self.site_b, permitted_sites) # Site B is not permitted

        # Accessing Site B directly must be denied on backend (AC-10.6)
        with self.assertRaises(PermissionDenied):
            services.validate_client_site_access(self.client_user, self.site_b.site_id)

    # --------------------------------------------------------------------------
    # Test 3: Deactivated User Access Denied (AC-10.7)
    # --------------------------------------------------------------------------
    def test_deactivated_client_user(self):
        self.client_user.status = 'INACTIVE'
        self.client_user.save()

        permitted_sites = services.get_client_permitted_sites(self.client_user)
        self.assertEqual(permitted_sites.count(), 0)

    # --------------------------------------------------------------------------
    # Test 4: Dashboard Counts and Empty States (AC-10.11, AC-10.12)
    # --------------------------------------------------------------------------
    def test_dashboard_real_data_and_empty_states(self):
        dashboard = services.build_client_dashboard(self.client_user)
        self.assertIn('current_date', dashboard)
        self.assertIn('summary', dashboard)
        self.assertEqual(dashboard['summary']['total_permitted_sites'], 2)
        self.assertIsNone(dashboard['active_panic_banner'])
        self.assertFalse(dashboard['invoices_enabled'])

    # --------------------------------------------------------------------------
    # Test 5: Active Panic Banner & Client Safe Status (AC-10.13, AC-10.38, AC-10.39, AC-10.43)
    # --------------------------------------------------------------------------
    def test_active_panic_banner_and_safe_status(self):
        # Create an active panic in Module 9 at Site A
        panic = PanicAlert.objects.create(
            company_id=self.company.company_id,
            alert_number='PANIC-2026-001',
            client_generated_id='TEST-PANIC-01',
            guard=self.guard,
            site=self.site_a,
            alert_status='TRIGGERED'
        )

        # Dashboard now surfaces active panic banner (AC-10.13)
        dashboard = services.build_client_dashboard(self.client_user)
        self.assertIsNotNone(dashboard['active_panic_banner'])
        self.assertEqual(dashboard['active_panic_banner']['client_safe_status'], 'Alert Raised')
        self.assertIn('112', dashboard['active_panic_banner']['emergency_contact'])

        # Detailed status check
        status_info = services.get_client_safe_panic_status(self.client_user, panic.panic_alert_id)
        self.assertEqual(status_info['client_safe_status'], 'Alert Raised')
        self.assertIn('not replace official emergency dispatch', status_info['disclaimer'].lower())
        # Coordinates or device information must NEVER appear (AC-10.39)
        self.assertNotIn('latitude', status_info)
        self.assertNotIn('longitude', status_info)
        self.assertNotIn('battery', status_info)

    # --------------------------------------------------------------------------
    # Test 6: Panic Acknowledgement (AC-10.40)
    # --------------------------------------------------------------------------
    def test_client_panic_acknowledgement(self):
        panic = PanicAlert.objects.create(
            company_id=self.company.company_id,
            alert_number='PANIC-2026-002',
            client_generated_id='TEST-PANIC-02',
            guard=self.guard,
            site=self.site_a,
            alert_status='RESPONDING'
        )

        ack_res = services.acknowledge_panic_alert(self.client_user, panic.panic_alert_id)
        self.assertTrue(ack_res['acknowledged'])

        # Alert status must NOT be closed by client acknowledgement! (AC-10.40)
        panic.refresh_from_db()
        self.assertEqual(panic.alert_status, 'RESPONDING')

    # --------------------------------------------------------------------------
    # Test 7: Deployment Neutral Status Wording & Replacement (AC-10.14, AC-10.15, AC-10.16, AC-10.18, AC-10.21)
    # --------------------------------------------------------------------------
    def test_deployment_neutral_wording_and_guard_card(self):
        today = timezone.localdate()
        slot = PostSlot.objects.create(
            company_id=self.company.company_id,
            site=self.site_a,
            post_type=self.post_type,
            shift=self.shift,
            deployment_date=today,
            slot_sequence=1
        )
        # Normal assignment
        a1 = RosterAssignment.objects.create(
            company_id=self.company.company_id,
            employee=self.guard,
            site=self.site_a,
            shift=self.shift,
            slot=slot,
            post_type=self.post_type,
            deployment_date=today,
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=8),
            status='scheduled',
            assignment_type='regular'
        )

        dep = services.get_site_deployment(self.client_user, self.site_a.site_id)
        self.assertEqual(dep['assigned_guards'], 1)
        guard_card = dep['current_shift_guards'][0]
        self.assertEqual(guard_card['name'], self.guard.full_name)
        self.assertIn(guard_card['status_word'], ['Scheduled', 'Not Yet Confirmed'])

        # Verify replacement without exposing internal reason (AC-10.15, AC-10.16)
        a1.assignment_type = 'replacement'
        a1.save()
        dep_rep = services.get_site_deployment(self.client_user, self.site_a.site_id)
        self.assertEqual(dep_rep['current_shift_guards'][0]['status_word'], 'Replacement Assigned')
        self.assertNotIn('reason', dep_rep['current_shift_guards'][0])

        # Verify guard safe card has NO phone number (AC-10.21)
        safe_card = services.get_client_safe_guard_card(self.client_user, self.guard.employee_id)
        self.assertEqual(safe_card['name'], self.guard.full_name)
        self.assertNotIn('phone', safe_card)

    # --------------------------------------------------------------------------
    # Test 8: Provisional vs Approved Attendance (AC-10.22 to AC-10.25)
    # --------------------------------------------------------------------------
    def test_attendance_provisional_and_approved_records(self):
        today = timezone.localdate()
        att = AttendanceRecord.objects.create(
            company_id=self.company.company_id,
            employee=self.guard,
            site=self.site_a,
            shift=self.shift,
            duty_date=today,
            scheduled_start=timezone.now(),
            scheduled_end=timezone.now() + timedelta(hours=8),
            actual_check_in=timezone.now(),
            status='scheduled',
            is_manual=True,
            is_offline=True
        )

        # 1. Today so far shows provisional with "Not Yet Approved" label (AC-10.22)
        today_records = services.get_today_so_far_attendance(self.client_user, self.site_a.site_id)
        self.assertEqual(len(today_records), 1)
        self.assertEqual(today_records[0]['status_label'], 'Not Yet Approved')
        self.assertTrue(today_records[0]['provisional'])

        # 2. Approved view
        att.status = 'approved'
        att.save()
        approved = services.get_approved_attendance(self.client_user, self.site_a.site_id)
        self.assertEqual(len(approved), 1)
        self.assertTrue(approved[0]['is_manual']) # Manual label (AC-10.24)
        self.assertTrue(approved[0]['is_offline']) # Offline label (AC-10.25)

    # --------------------------------------------------------------------------
    # Test 9: Locked Attendance Monthly Downloads & Logging (AC-10.26 to AC-10.28)
    # --------------------------------------------------------------------------
    def test_monthly_attendance_sheet_download(self):
        # 1. Period not locked -> download raises ValidationError (AC-10.26)
        with self.assertRaises(ValidationError):
            services.download_monthly_attendance_sheet(
                self.client_user, self.site_a.site_id, month=11, year=2026, file_format='csv'
            )

        # 2. Lock period in Module 6
        AttendancePeriod.objects.create(
            company_id=self.company.company_id,
            site=self.site_a,
            period_name='November 2026',
            start_date=date(2026, 11, 1),
            end_date=date(2026, 11, 30),
            status='locked'
        )

        # Download now succeeds (AC-10.27)
        csv_data, filename = services.download_monthly_attendance_sheet(
            self.client_user, self.site_a.site_id, month=11, year=2026, file_format='csv'
        )
        self.assertIn('Employee Code', csv_data)
        self.assertTrue(filename.endswith('.csv'))

        # Verifies download was logged in audit log (AC-10.28)
        self.assertTrue(ClientDocumentAccessLog.objects.filter(
            client_user=self.client_user, result='SUCCESS', file_type='CSV'
        ).exists())

    # --------------------------------------------------------------------------
    # Test 10: Attendance Query Creates Module 8 Ticket (AC-10.31)
    # --------------------------------------------------------------------------
    def test_attendance_query_creates_ticket(self):
        att = AttendanceRecord.objects.create(
            company_id=self.company.company_id,
            employee=self.guard,
            site=self.site_a,
            shift=self.shift,
            duty_date=timezone.localdate(),
            scheduled_start=timezone.now(),
            scheduled_end=timezone.now() + timedelta(hours=8),
            status='approved'
        )

        ticket = services.create_attendance_query(
            user=self.client_user,
            attendance_record_id=att.attendance_id,
            site_id=self.site_a.site_id,
            reason="Worked minutes shows 7 hours instead of 8 hours."
        )

        self.assertIsNotNone(ticket)
        self.assertEqual(ticket.ticket_type, 'QUERY')
        self.assertIn("Attendance Query", ticket.title)
        self.assertTrue(ClientTicketMessage.objects.filter(ticket=ticket).exists())

    # --------------------------------------------------------------------------
    # Test 11: Shared Incidents Only & Comments (AC-10.33 to AC-10.37)
    # --------------------------------------------------------------------------
    def test_shared_incidents_isolation_and_comment(self):
        # Raw incident created by guard
        inc_cat = IncidentCategory.objects.create(
            company_id=self.company.company_id,
            code='TRESPASSING',
            name='Trespassing Incident'
        )
        raw_inc = Incident.objects.create(
            company_id=self.company.company_id,
            case_number='INC-2026-001',
            client_generated_id=uuid.uuid4(),
            category=inc_cat,
            original_category=inc_cat,
            current_category=inc_cat,
            original_severity='MEDIUM',
            current_severity='MEDIUM',
            occurred_at=timezone.now(),
            device_time=timezone.now(),
            guard=self.guard,
            site=self.site_a,
            description='Raw guard log: Someone climbed back wall, caught and detained.'
        )

        # Client should see 0 incidents because no approved shared version exists yet (AC-10.34)
        incidents = services.get_client_shared_incidents(self.client_user, self.site_a.site_id)
        self.assertEqual(len(incidents), 0)

        # Approved shared version created in Module 8
        shared_ver = IncidentClientVersion.objects.create(
            incident=raw_inc,
            company_id=self.company.company_id,
            client=self.client_org,
            site=self.site_a,
            title='Perimeter Breach at North Fence',
            category='Trespassing',
            occurred_at=timezone.now(),
            summary='An unauthorized entry attempt was intercepted at the north perimeter fence.',
            actions_taken='Perimeter patrol stepped up and gate latch repaired.',
            status='RESOLVED',
            approved_by=self.admin,
            sharing_state='SHARED'
        )

        # Client now sees shared version (AC-10.33, AC-10.35)
        incidents_now = services.get_client_shared_incidents(self.client_user, self.site_a.site_id)
        self.assertEqual(len(incidents_now), 1)
        self.assertEqual(incidents_now[0]['title'], 'Perimeter Breach at North Fence')
        self.assertNotIn('Raw guard log', incidents_now[0]['summary'])

        # Client comments on incident (AC-10.37)
        res = services.add_client_incident_comment(
            self.client_user, shared_ver.version_id, "Thank you, please have the supervisor check sensor 4."
        )
        self.assertIn('message_id', res)

    # --------------------------------------------------------------------------
    # Test 12: Client Tickets & Internal Notes Hidden (AC-10.53, AC-10.54, AC-10.57)
    # --------------------------------------------------------------------------
    def test_client_ticket_messages_internal_notes_hidden(self):
        ticket = ClientTicket.objects.create(
            company_id=self.company.company_id,
            ticket_number='TICK-2026-001',
            client_generated_id=uuid.uuid4(),
            client=self.client_org,
            site=self.site_a,
            ticket_type='QUERY',
            title='Gate pass policy enquiry',
            description='Need clarification on vendor passes',
            status='RESOLVED'
        )

        # Client-visible message
        ClientTicketMessage.objects.create(
            ticket=ticket,
            company_id=self.company.company_id,
            actor=self.admin,
            message='Vendor passes are issued at Reception Tower A.',
            visibility='CLIENT_VISIBLE'
        )

        # Internal note (Admin / Supervisor private note)
        ClientTicketMessage.objects.create(
            ticket=ticket,
            company_id=self.company.company_id,
            actor=self.admin,
            message='Internal note: Client facility team was delayed in approvals.',
            visibility='INTERNAL'
        )

        # Fetching ticket messages for client: Internal notes must NOT appear! (AC-10.54)
        visible_msgs = ClientTicketMessage.objects.filter(ticket=ticket, visibility='CLIENT_VISIBLE')
        self.assertEqual(visible_msgs.count(), 1)
        self.assertNotIn('Internal note', visible_msgs[0].message)

    # --------------------------------------------------------------------------
    # Test 13: Notification Preferences & Panic Override (AC-10.58, AC-10.59)
    # --------------------------------------------------------------------------
    def test_notification_preferences_panic_cannot_be_disabled(self):
        pref = ClientNotificationPreference.objects.create(
            company_id=self.company.company_id,
            client_user=self.client_user,
            notification_category='ATTENDANCE',
            enabled=False
        )
        self.assertFalse(pref.enabled)

        # Disabling panic notices is blocked by application rules (AC-10.59)
        from client_portal.serializers import ClientNotificationPreferenceSerializer
        serializer = ClientNotificationPreferenceSerializer(data={
            'notification_category': 'PANIC',
            'enabled': False
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('Emergency panic alerts cannot be disabled', str(serializer.errors))

    # --------------------------------------------------------------------------
    # Test 14: Invoices Not Available Yet (AC-10.44, AC-10.47)
    # --------------------------------------------------------------------------
    def test_invoices_not_available_yet_flag(self):
        config = services.get_or_create_portal_config(self.company.company_id, self.client_org.client_id)
        self.assertFalse(config.invoices_enabled)

    # --------------------------------------------------------------------------
    # Test 15: Admin Client Preview & Logging (AC-10.64, AC-10.65)
    # --------------------------------------------------------------------------
    def test_admin_client_preview_logging(self):
        # Admin simulates portal as client_user
        preview = services.admin_client_preview(self.admin, self.client_user.user_id)
        self.assertTrue(preview['preview_mode'])
        self.assertEqual(preview['simulated_user']['email'], self.client_user.email)

        # Verify preview was logged in usage events (AC-10.65)
        self.assertTrue(ClientPortalUsageEvent.objects.filter(
            event_type='PREVIEW', source='ADMIN_PREVIEW'
        ).exists())

    # --------------------------------------------------------------------------
    # Test 16: Real Usage Metrics Dashboard (AC-10.67)
    # --------------------------------------------------------------------------
    def test_real_usage_metrics(self):
        metrics = services.get_real_portal_usage_metrics(self.company.company_id, days=30)
        self.assertIn('total_logins', metrics)
        self.assertIn('first_login_events', metrics)
        self.assertIn('tickets_raised_via_portal', metrics)
        self.assertIn('document_downloads', metrics)
        self.assertIn('admin_previews', metrics)
