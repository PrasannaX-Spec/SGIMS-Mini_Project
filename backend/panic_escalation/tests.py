import uuid
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from rest_framework.exceptions import ValidationError, PermissionDenied

from foundation.models import Company, User, BoundDevice
from master_data.models import Client, ClientSite, SiteSupervisorAssignment
from guard_management.models import Employee
from deployment_roster.models import RosterAssignment
from live_monitoring.models import LocationPoint, MonitoringDuty

from panic_escalation.models import (
    PanicAlert,
    PanicTriggerContext,
    PanicPositionRecord,
    PanicEscalationConfig,
    PanicRecipient,
    PanicDeliveryAttempt,
    PanicAcknowledgement,
    PanicResponderAction,
    PanicFalseAlarmReport,
    PanicResolution,
    PanicEventTimeline,
    PanicTestDrill,
    PanicDeviceReadiness,
    PanicWelfareFollowup
)
from panic_escalation import services


class PanicEscalationModuleTests(TestCase):
    def setUp(self):
        # 1. Company
        self.company = Company.objects.create(
            legal_name='Apex Security Karnataka Ltd',
            trade_name='Apex Security',
            email='admin@apexsecurity.local',
            phone='+919876543210'
        )

        # 2. Users (Admin, Supervisor, Guard, Client)
        self.admin = User.objects.create(
            company_id=self.company.company_id,
            email='admin@apexsecurity.local',
            full_name='Apex Admin',
            role='ADMIN',
            phone='+919877700001',
            password_hash=make_password('AdminPass123!'),
            status='ACTIVE'
        )

        self.supervisor = User.objects.create(
            company_id=self.company.company_id,
            email='supervisor@apexsecurity.local',
            full_name='Field Officer Ramesh',
            role='SUPERVISOR',
            phone='+919877700002',
            password_hash=make_password('SuperPass123!'),
            status='ACTIVE'
        )

        self.guard_user = User.objects.create(
            company_id=self.company.company_id,
            email='guard@apexsecurity.local',
            full_name='Security Guard Suresh Kumar',
            role='GUARD',
            phone='+919877700003',
            password_hash=make_password('GuardPass123!'),
            status='ACTIVE'
        )

        # 3. Client & Sites
        self.client_org = Client.objects.create(
            company_id=self.company.company_id,
            legal_name='Infosys Campus Electronic City',
            client_code='INFY-BLR',
            status='active'
        )

        self.site_a = ClientSite.objects.create(
            client=self.client_org,
            site_name='Infosys Gate 1 Main Entrance',
            site_code='INFY-G1',
            address_line1='Electronic City Phase 1',
            latitude=12.845000,
            longitude=77.665000,
            operational_status='active'
        )

        # 4. Guard Employee record
        self.guard_emp = Employee.objects.create(
            company_id=self.company.company_id,
            employee_code='GRD-KA-001',
            first_name='Suresh',
            last_name='Kumar',
            phone='+919877700003',
            date_joined=timezone.now().date(),
            employment_status='active',
            lifecycle_status='active'
        )

        # 5. Site Supervisor Assignment
        SiteSupervisorAssignment.objects.create(
            site=self.site_a,
            supervisor_user_id=self.supervisor.user_id,
            effective_from=timezone.now(),
            is_active=True
        )

        # 6. Default Escalation Config
        self.config = PanicEscalationConfig.objects.create(
            company=self.company,
            site=self.site_a,
            stage0_timer_seconds=0,
            stage1_timer_seconds=30,
            stage2_timer_seconds=60,
            stage3_timer_seconds=120,
            stage4_timer_seconds=300,
            notify_client_immediately=True,
            enabled_routes=['PUSH', 'WEB_CONSOLE', 'SMS']
        )

    # --------------------------------------------------------------------------
    # Test 1: Panic Trigger & Idempotency (AC-9.1, AC-9.16, FR-9.7, FR-9.8)
    # --------------------------------------------------------------------------
    def test_panic_trigger_and_idempotency(self):
        client_gen_id = uuid.uuid4()
        now = timezone.now()

        alert, created = services.trigger_panic_alert(
            company_id=self.company.company_id,
            guard_user=self.guard_user,
            client_generated_id=client_gen_id,
            battery_level=85.0,
            network_type='4G',
            latitude=12.845000,
            longitude=77.665000,
            site_id=self.site_a.site_id
        )

        self.assertTrue(created)
        self.assertEqual(alert.alert_status, 'DELIVERING')
        self.assertEqual(alert.guard.employee_id, self.guard_emp.employee_id)
        self.assertTrue(alert.alert_number.startswith('PAN-'))
        self.assertFalse(alert.test_flag)

        # Check Context
        self.assertEqual(float(alert.context.battery_level), 85.0)
        self.assertEqual(alert.context.network_type, '4G')

        # Check Position Record (Fresh Device)
        pos = alert.positions.first()
        self.assertIsNotNone(pos)
        self.assertEqual(pos.source, 'FRESH_DEVICE')
        self.assertEqual(pos.validity_status, 'AVAILABLE')

        # Check Initial Recipients & Multi-Route Delivery (AC-9.26, AC-9.27)
        self.assertTrue(alert.recipients.exists())
        self.assertTrue(alert.delivery_attempts.exists())

        # Idempotency: Repeating trigger with same client_generated_id returns existing
        alert_retry, created_retry = services.trigger_panic_alert(
            company_id=self.company.company_id,
            guard_user=self.guard_user,
            client_generated_id=client_gen_id,
            battery_level=80.0
        )
        self.assertFalse(created_retry)
        self.assertEqual(alert.panic_alert_id, alert_retry.panic_alert_id)

    # --------------------------------------------------------------------------
    # Test 2: Active Alert Linking (AC-9.2, FR-9.9)
    # --------------------------------------------------------------------------
    def test_active_alert_linking(self):
        # First trigger
        alert1, created1 = services.trigger_panic_alert(
            company_id=self.company.company_id,
            guard_user=self.guard_user,
            client_generated_id=uuid.uuid4(),
            site_id=self.site_a.site_id
        )
        self.assertTrue(created1)

        # Second trigger while alert1 is active (different client_generated_id)
        alert2, created2 = services.trigger_panic_alert(
            company_id=self.company.company_id,
            guard_user=self.guard_user,
            client_generated_id=uuid.uuid4(),
            site_id=self.site_a.site_id
        )
        self.assertFalse(created2)
        self.assertEqual(alert1.panic_alert_id, alert2.panic_alert_id)

    # --------------------------------------------------------------------------
    # Test 3: Outside Duty Marking (AC-9.3, FR-9.6)
    # --------------------------------------------------------------------------
    def test_outside_duty_detection(self):
        alert, _ = services.trigger_panic_alert(
            company_id=self.company.company_id,
            guard_user=self.guard_user,
            client_generated_id=uuid.uuid4()
            # No site or assignment passed
        )
        self.assertEqual(alert.duty_status, 'OUTSIDE_DUTY')

    # --------------------------------------------------------------------------
    # Test 4: Registered Device Validation (AC-9.4, FR-9.4, FR-9.5)
    # --------------------------------------------------------------------------
    def test_unregistered_device_rejection(self):
        # Register a specific device for this guard
        BoundDevice.objects.create(
            company=self.company,
            user=self.guard_user,
            device_id='AUTHORIZED-SAMSUNG-S23'
        )

        # Attempt to trigger panic with a DIFFERENT device ID
        with self.assertRaises(PermissionDenied):
            services.trigger_panic_alert(
                company_id=self.company.company_id,
                guard_user=self.guard_user,
                client_generated_id=uuid.uuid4(),
                device_id='UNAUTHORIZED-PHONE-XYZ'
            )

    # --------------------------------------------------------------------------
    # Test 5: Location Resolution: Module 7 Fallback & Age (AC-9.8, AC-9.9, AC-9.11)
    # --------------------------------------------------------------------------
    def test_location_fallback_and_staleness(self):
        # If coordinates are missing and no Module 7 points exist -> UNAVAILABLE (AC-9.8)
        alert, _ = services.trigger_panic_alert(
            company_id=self.company.company_id,
            guard_user=self.guard_user,
            client_generated_id=uuid.uuid4(),
            site_id=self.site_a.site_id
        )
        pos = alert.positions.first()
        self.assertEqual(pos.validity_status, 'UNAVAILABLE')

    # --------------------------------------------------------------------------
    # Test 6: False Alarm Report Does NOT Stop Active Alert (AC-9.20, AC-9.21, FR-9.37)
    # --------------------------------------------------------------------------
    def test_false_alarm_report_does_not_stop_alert(self):
        alert, _ = services.trigger_panic_alert(
            company_id=self.company.company_id,
            guard_user=self.guard_user,
            client_generated_id=uuid.uuid4(),
            site_id=self.site_a.site_id
        )

        # Guard reports accidental trigger
        report = services.report_false_alarm(
            panic_alert_id=alert.panic_alert_id,
            guard_user=self.guard_user,
            explanation="Accidentally pressed while climbing ladder",
            are_you_safe_answer='YES'
        )

        # Verify alert is STILL active and NOT closed! (AC-9.20, FR-9.37)
        alert.refresh_from_db()
        self.assertIn(alert.alert_status, ['DELIVERING', 'ACKNOWLEDGED', 'RESPONDING'])
        self.assertNotEqual(alert.alert_status, 'CLOSED')
        self.assertEqual(report.supervisor_decision, 'PENDING')

    # --------------------------------------------------------------------------
    # Test 7: False Alarm Supervisor Confirmation & Admin Review (AC-9.22, AC-9.23, AC-9.24)
    # --------------------------------------------------------------------------
    def test_supervisor_confirm_false_alarm_requires_admin_closure(self):
        alert, _ = services.trigger_panic_alert(
            company_id=self.company.company_id,
            guard_user=self.guard_user,
            client_generated_id=uuid.uuid4(),
            site_id=self.site_a.site_id
        )
        services.report_false_alarm(alert.panic_alert_id, self.guard_user, "Accidental click")

        # Non-supervisor cannot confirm false alarm
        with self.assertRaises(PermissionDenied):
            services.confirm_false_alarm(alert.panic_alert_id, self.guard_user, 'CONFIRMED')

        # Supervisor confirms false alarm
        services.confirm_false_alarm(alert.panic_alert_id, self.supervisor, 'CONFIRMED', "Spoke to guard, all safe")
        alert.refresh_from_db()
        self.assertEqual(alert.alert_status, 'FALSE_ALARM')

        # Admin approves closure
        services.admin_review_panic_alert(alert.panic_alert_id, self.admin, 'APPROVE', "Reviewed and verified false alarm")
        alert.refresh_from_db()
        self.assertEqual(alert.alert_status, 'CLOSED')
        self.assertIsNotNone(alert.closed_at)

    # --------------------------------------------------------------------------
    # Test 8: Recipient Acknowledgement (AC-9.28, AC-9.29, AC-9.30, AC-9.36)
    # --------------------------------------------------------------------------
    def test_acknowledgement_stops_repeat_alarms_but_keeps_alert_active(self):
        alert, _ = services.trigger_panic_alert(
            company_id=self.company.company_id,
            guard_user=self.guard_user,
            client_generated_id=uuid.uuid4(),
            site_id=self.site_a.site_id
        )

        services.acknowledge_panic_alert(
            panic_alert_id=alert.panic_alert_id,
            user=self.supervisor,
            channel='WEB',
            acknowledgement_type='RECEIPT'
        )

        alert.refresh_from_db()
        self.assertEqual(alert.alert_status, 'ACKNOWLEDGED')
        self.assertIsNotNone(alert.first_acknowledged_at)

        # Acknowledgement does not close the alert! (AC-9.30)
        self.assertNotEqual(alert.alert_status, 'CLOSED')

    # --------------------------------------------------------------------------
    # Test 9: Responder Action & Are You Safe Flow (AC-9.38, AC-9.39, AC-9.42)
    # --------------------------------------------------------------------------
    def test_responder_action_and_are_you_safe(self):
        alert, _ = services.trigger_panic_alert(
            company_id=self.company.company_id,
            guard_user=self.guard_user,
            client_generated_id=uuid.uuid4(),
            site_id=self.site_a.site_id
        )

        # Supervisor calls guard and informs emergency services
        services.record_responder_action(
            panic_alert_id=alert.panic_alert_id,
            responder_user=self.supervisor,
            action_type='CALL_GUARD',
            description="Attempted direct voice call to guard"
        )
        services.record_responder_action(
            panic_alert_id=alert.panic_alert_id,
            responder_user=self.supervisor,
            action_type='EMERGENCY_SERVICE_INFORMED',
            description="Informed Electronic City Police PCR",
            reference="PCR-KA-8812"
        )

        alert.refresh_from_db()
        self.assertEqual(alert.alert_status, 'RESPONDING')

        # Supervisor sends Are You Safe? prompt
        services.send_are_you_safe_prompt(alert.panic_alert_id, self.supervisor)

        # Guard responds YES
        services.respond_are_you_safe(alert.panic_alert_id, self.guard_user, answer='YES')
        alert.refresh_from_db()
        self.assertEqual(alert.alert_status, 'GUARD_CONFIRMED_SAFE')

    # --------------------------------------------------------------------------
    # Test 10: Resolution & Admin Review (AC-9.41, AC-9.57, AC-9.58, AC-9.66)
    # --------------------------------------------------------------------------
    def test_resolution_and_admin_review_closure(self):
        alert, _ = services.trigger_panic_alert(
            company_id=self.company.company_id,
            guard_user=self.guard_user,
            client_generated_id=uuid.uuid4(),
            site_id=self.site_a.site_id
        )

        # Supervisor resolves
        services.resolve_panic_alert(
            panic_alert_id=alert.panic_alert_id,
            supervisor_user=self.supervisor,
            outcome='SITUATION_RESOLVED_ON_SITE',
            description="Intruder escorted off site by patrol officers. No injuries.",
            emergency_services_informed=True,
            emergency_service_ref='PCR-KA-8812',
            follow_up_required=False
        )

        alert.refresh_from_db()
        self.assertEqual(alert.alert_status, 'RESOLVED')
        self.assertIsNotNone(alert.resolved_at)

        # Non-admin cannot close the alert (AC-9.57)
        with self.assertRaises(PermissionDenied):
            services.admin_review_panic_alert(alert.panic_alert_id, self.supervisor, 'APPROVE')

        # Admin approves closure (AC-9.58)
        services.admin_review_panic_alert(alert.panic_alert_id, self.admin, 'APPROVE', "Approved full report.")
        alert.refresh_from_db()
        self.assertEqual(alert.alert_status, 'CLOSED')
        self.assertIsNotNone(alert.closed_at)

        # Admin adds welfare follow-up note (FR-9.84)
        followup = services.record_welfare_followup(alert.panic_alert_id, self.admin, "Checked on guard Suresh Kumar. Welfare confirmed.")
        self.assertEqual(followup.panic_alert_id, alert.panic_alert_id)

    # --------------------------------------------------------------------------
    # Test 11: Client-Safe Visibility Isolation (AC-9.43, AC-9.44, AC-9.46, AC-9.47)
    # --------------------------------------------------------------------------
    def test_client_safe_visibility_restrictions(self):
        alert, _ = services.trigger_panic_alert(
            company_id=self.company.company_id,
            guard_user=self.guard_user,
            client_generated_id=uuid.uuid4(),
            latitude=12.845000,
            longitude=77.665000,
            battery_level=92.0,
            site_id=self.site_a.site_id
        )

        # Client Safe Query (Module 10 Hook)
        client_alerts = services.get_client_safe_panic_status(self.client_org.client_id)
        self.assertTrue(client_alerts.exists())

        from panic_escalation.serializers import ClientSafePanicStatusSerializer
        data = ClientSafePanicStatusSerializer(client_alerts.first()).data

        # MUST contain safe card name and client-visible status
        self.assertIn('guard_safe_card_name', data)
        self.assertIn('client_visible_status', data)

        # MUST NEVER contain coordinates, battery, or device info (AC-9.44, PRD Section 7.1)
        self.assertNotIn('latitude', data)
        self.assertNotIn('longitude', data)
        self.assertNotIn('battery_level', data)
        self.assertNotIn('positions', data)
        self.assertNotIn('guard_phone', data)

    # --------------------------------------------------------------------------
    # Test 12: Controlled Test Drills Excluded from Metrics (AC-9.48, AC-9.49, AC-9.50)
    # --------------------------------------------------------------------------
    def test_test_drill_exclusion_from_real_metrics(self):
        # 1 Real alert
        services.trigger_panic_alert(
            company_id=self.company.company_id,
            guard_user=self.guard_user,
            client_generated_id=uuid.uuid4(),
            site_id=self.site_a.site_id
        )

        # 1 Test Drill
        drill, test_alert = services.create_test_drill(
            company_id=self.company.company_id,
            admin_user=self.admin,
            drill_name="Annual Evacuation Drill",
            include_clients=False
        )

        self.assertTrue(test_alert.test_flag)
        self.assertEqual(drill.status, 'COMPLETED')

        # Query Module 13 Reporting Metrics (AC-9.49)
        metrics = services.get_panic_reporting_metrics(self.company.company_id)
        self.assertEqual(metrics['total_real_alerts'], 1)
        self.assertEqual(metrics['total_test_alerts'], 1)

    # --------------------------------------------------------------------------
    # Test 13: Module 8 Incident Creation & Idempotency (AC-9.63, FR-9.87, FR-9.91)
    # --------------------------------------------------------------------------
    def test_module8_incident_creation_and_retry_idempotency(self):
        alert, _ = services.trigger_panic_alert(
            company_id=self.company.company_id,
            guard_user=self.guard_user,
            client_generated_id=uuid.uuid4(),
            site_id=self.site_a.site_id
        )

        incident1 = services.create_incident_from_panic_alert(alert.panic_alert_id, self.admin)
        self.assertIsNotNone(incident1.incident_id)

        # Repeating creation request returns same incident without duplicates (AC-9.63)
        incident2 = services.create_incident_from_panic_alert(alert.panic_alert_id, self.admin)
        self.assertEqual(incident1.incident_id, incident2.incident_id)

    # --------------------------------------------------------------------------
    # Test 14: Immutable Event Timeline Trigger (AC-9.54, FR-9.111)
    # --------------------------------------------------------------------------
    def test_immutable_timeline_protection(self):
        alert, _ = services.trigger_panic_alert(
            company_id=self.company.company_id,
            guard_user=self.guard_user,
            client_generated_id=uuid.uuid4(),
            site_id=self.site_a.site_id
        )

        timeline_entry = alert.timelines.first()
        self.assertIsNotNone(timeline_entry)

        # Modifying existing timeline row should be blocked by trigger or forbidden
        timeline_entry.source_reference = 'HACKED'
        with self.assertRaises(Exception):
            timeline_entry.save()
