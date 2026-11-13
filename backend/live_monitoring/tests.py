import uuid
from datetime import date, time, timedelta, datetime
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from rest_framework.exceptions import ValidationError, PermissionDenied

from foundation.models import User, ConsentRecord, AuditEvent
from master_data.models import Company, Client, ClientSite, SiteShift, PostType, SiteSupervisorAssignment
from guard_management.models import Employee, EmployeeDocument, EmployeeCheck, EmployeeTraining
from deployment_roster.models import PostSlot, RosterAssignment
from attendance.models import AttendanceRecord

from live_monitoring.models import (
    MonitoringDuty,
    LocationPoint,
    Heartbeat,
    GuardMonitoringStatus,
    MonitoringStatusHistory,
    AlertRule,
    MonitoringAlert,
    SupervisorPing,
    TrackingConfiguration
)
from live_monitoring import services


class LiveMonitoringModuleTests(TestCase):
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

        # 2. Users (Admin & Supervisor)
        self.admin = User.objects.create(
            company_id=self.company.company_id,
            email='admin@apexmonitoring.local',
            full_name='Apex Admin',
            role='ADMIN',
            phone='+919877700001',
            password_hash=make_password('AdminPass123!'),
            status='ACTIVE'
        )

        self.supervisor = User.objects.create(
            company_id=self.company.company_id,
            email='supervisor@apexmonitoring.local',
            full_name='Field Officer Ramesh',
            role='SUPERVISOR',
            phone='+919877700002',
            password_hash=make_password('SuperPass123!'),
            status='ACTIVE'
        )

        # 3. Client & Client Sites (Coordinates: Lat 12.910000, Lon 77.680000, Radius: 100m)
        self.client = Client.objects.create(
            company=self.company,
            legal_name='Wipro SEZ',
            client_code='WIP-BLR',
            status='active'
        )
        self.site_a = ClientSite.objects.create(
            client=self.client,
            site_code='WIP-SARJ-01',
            site_name='Wipro Sarjapur Campus',
            operational_status='active',
            latitude=Decimal('12.910000'),
            longitude=Decimal('77.680000'),
            geofence_radius_m=100
        )
        self.site_b = ClientSite.objects.create(
            client=self.client,
            site_code='WIP-ELEC-02',
            site_name='Wipro Electronic City',
            operational_status='active',
            latitude=Decimal('12.850000'),
            longitude=Decimal('77.660000'),
            geofence_radius_m=100
        )

        # Supervisor assigned ONLY to site_a
        SiteSupervisorAssignment.objects.create(
            site=self.site_a,
            supervisor_user_id=self.supervisor.user_id,
            role_type='primary',
            effective_from=timezone.now(),
            is_active=True
        )

        # 4. Shifts
        self.shift = SiteShift.objects.create(
            site=self.site_a,
            shift_code='DAY',
            shift_name='Day Shift',
            start_time=time(8, 0),
            end_time=time(16, 0),
            duration_minutes=480,
            is_cross_midnight=False,
            is_active=True
        )

        # 5. Post Type & Post Slot
        self.post_type = PostType.objects.create(
            company=self.company,
            code='GEN_GUARD',
            name='General Security Guard'
        )

        self.slot_start = timezone.now() - timedelta(hours=2)
        self.slot_end = timezone.now() + timedelta(hours=6)

        self.slot = PostSlot.objects.create(
            company=self.company,
            site=self.site_a,
            shift=self.shift,
            post_type=self.post_type,
            deployment_date=date.today(),
            slot_sequence=1,
            slot_status='filled'
        )

        # 6. Guards
        self.guard_1 = Employee.objects.create(
            company_id=self.company.company_id,
            employee_code='GRD-701',
            first_name='Anand',
            last_name='Kumar',
            date_of_birth=date(1993, 4, 15),
            gender='MALE',
            phone='+919877710001',
            date_joined=date(2025, 1, 1),
            lifecycle_status='active'
        )
        self.guard_user_1 = User.objects.create(
            company_id=self.company.company_id,
            email='anand.kumar@apexmonitoring.local',
            full_name='Anand Kumar',
            role='GUARD',
            phone='+919877710001',
            guard_profile_id=self.guard_1.employee_id,
            status='ACTIVE'
        )

        self.guard_2 = Employee.objects.create(
            company_id=self.company.company_id,
            employee_code='GRD-702',
            first_name='Basavaraj',
            last_name='Patil',
            date_of_birth=date(1995, 7, 20),
            gender='MALE',
            phone='+919877710002',
            date_joined=date(2025, 1, 1),
            lifecycle_status='active'
        )
        self.guard_user_2 = User.objects.create(
            company_id=self.company.company_id,
            email='basavaraj@apexmonitoring.local',
            full_name='Basavaraj Patil',
            role='GUARD',
            phone='+919877710002',
            guard_profile_id=self.guard_2.employee_id,
            status='ACTIVE'
        )

        # Guard 1 grants location consent; Guard 2 does not grant consent
        self.consent_1 = ConsentRecord.objects.create(
            company_id=self.company.company_id,
            user=self.guard_user_1,
            item='LOCATION',
            decision='GRANTED',
            policy_version='v1.0'
        )

        # 7. Assignments & Attendance Records
        self.assignment_1 = RosterAssignment.objects.create(
            company=self.company,
            slot=self.slot,
            employee=self.guard_1,
            site=self.site_a,
            shift=self.shift,
            post_type=self.post_type,
            deployment_date=date.today(),
            start_time=self.slot_start,
            end_time=self.slot_end,
            status='scheduled'
        )

        self.att_record_1 = AttendanceRecord.objects.create(
            company_id=self.company.company_id,
            assignment=self.assignment_1,
            employee=self.guard_1,
            site=self.site_a,
            shift=self.shift,
            duty_date=date.today(),
            scheduled_start=self.slot_start,
            scheduled_end=self.slot_end,
            actual_check_in=timezone.now(),
            status='in_progress'
        )

        self.slot_2 = PostSlot.objects.create(
            company=self.company,
            site=self.site_a,
            shift=self.shift,
            post_type=self.post_type,
            deployment_date=date.today(),
            slot_sequence=2,
            slot_status='filled'
        )
        self.assignment_2 = RosterAssignment.objects.create(
            company=self.company,
            slot=self.slot_2,
            employee=self.guard_2,
            site=self.site_a,
            shift=self.shift,
            post_type=self.post_type,
            deployment_date=date.today(),
            start_time=self.slot_start,
            end_time=self.slot_end,
            status='scheduled'
        )
        self.att_record_2 = AttendanceRecord.objects.create(
            company_id=self.company.company_id,
            assignment=self.assignment_2,
            employee=self.guard_2,
            site=self.site_a,
            shift=self.shift,
            duty_date=date.today(),
            scheduled_start=self.slot_start,
            scheduled_end=self.slot_end,
            actual_check_in=timezone.now(),
            status='in_progress'
        )

        # 8. Alert Rules
        AlertRule.objects.get_or_create(
            company_id=self.company.company_id,
            rule_code='GEOFENCE_EXIT',
            defaults={'rule_name': 'Geofence Exit', 'severity': 'HIGH', 'cooldown_seconds': 900}
        )
        AlertRule.objects.get_or_create(
            company_id=self.company.company_id,
            rule_code='LOW_BATTERY',
            defaults={'rule_name': 'Low Battery', 'severity': 'NORMAL', 'cooldown_seconds': 1800}
        )
        AlertRule.objects.get_or_create(
            company_id=self.company.company_id,
            rule_code='NO_CONTACT',
            defaults={'rule_name': 'No Contact', 'severity': 'HIGH', 'cooldown_seconds': 1200}
        )
        AlertRule.objects.get_or_create(
            company_id=self.company.company_id,
            rule_code='PERMISSION_UNAVAILABLE',
            defaults={'rule_name': 'Permission Unavailable', 'severity': 'HIGH', 'cooldown_seconds': 3600}
        )
        AlertRule.objects.get_or_create(
            company_id=self.company.company_id,
            rule_code='MOCK_LOCATION_DETECTED',
            defaults={'rule_name': 'Mock Location Detected', 'severity': 'HIGH', 'cooldown_seconds': 3600}
        )

    # --------------------------------------------------------------------------
    # 1. Duty Start with and without Consent (AC-7.1, AC-7.2, AC-7.3)
    # --------------------------------------------------------------------------
    def test_ac1_duty_start_with_and_without_consent(self):
        # Guard 1: has consent -> ACTIVE tracking, on_duty_at_site
        duty_1 = services.start_monitoring_duty(
            assignment_id=self.assignment_1.assignment_id,
            attendance_record_id=self.att_record_1.attendance_id,
            actor_user=self.admin
        )
        self.assertEqual(duty_1.tracking_state, 'ACTIVE')
        stat_1 = GuardMonitoringStatus.objects.get(duty=duty_1)
        self.assertEqual(stat_1.primary_status, 'on_duty_at_site')
        self.assertEqual(stat_1.display_status, 'On Duty at Site')

        # Guard 2: no consent -> NOT_TRACKED, not_tracked status
        duty_2 = services.start_monitoring_duty(
            assignment_id=self.assignment_2.assignment_id,
            attendance_record_id=self.att_record_2.attendance_id,
            actor_user=self.admin
        )
        self.assertEqual(duty_2.tracking_state, 'NOT_TRACKED')
        stat_2 = GuardMonitoringStatus.objects.get(duty=duty_2)
        self.assertEqual(stat_2.primary_status, 'not_tracked')
        self.assertEqual(stat_2.display_status, 'Not Tracked')

    # --------------------------------------------------------------------------
    # 2. Duty Stop and Post-Shift Cutoff (AC-7.5, AC-7.6, AC-7.8)
    # --------------------------------------------------------------------------
    def test_ac2_duty_stop_and_window_rejection(self):
        duty = services.start_monitoring_duty(
            assignment_id=self.assignment_1.assignment_id,
            attendance_record_id=self.att_record_1.attendance_id,
            actor_user=self.admin
        )
        # Check out stops monitoring
        stop_time = timezone.now()
        services.stop_monitoring_duty(duty.duty_id, duty_end_at=stop_time, reason='CHECK_OUT')

        duty.refresh_from_db()
        self.assertEqual(duty.tracking_state, 'STOPPED')
        stat = GuardMonitoringStatus.objects.get(duty=duty)
        self.assertEqual(stat.primary_status, 'off_duty')

        # Attempt to upload point after duty stopped and cutoff exceeded raises ValidationError
        duty.duty_end_at = timezone.now() - timedelta(minutes=45)
        duty.save()

        with self.assertRaises(ValidationError):
            services.ingest_location_batch(
                duty_id=duty.duty_id,
                locations_data=[{
                    'client_generated_id': uuid.uuid4(),
                    'latitude': 12.910050,
                    'longitude': 77.680050,
                    'accuracy_m': 10.0,
                    'device_captured_at': timezone.now().isoformat()
                }]
            )

    # --------------------------------------------------------------------------
    # 3. Idempotent Ingestion & Out-of-Bounds Rejection (AC-7.9, AC-7.10, AC-7.12)
    # --------------------------------------------------------------------------
    def test_ac3_idempotent_ingestion_and_out_of_order(self):
        duty = services.start_monitoring_duty(
            assignment_id=self.assignment_1.assignment_id,
            attendance_record_id=self.att_record_1.attendance_id,
            actor_user=self.admin
        )
        client_uuid = uuid.uuid4()
        now_str = timezone.now().isoformat()

        batch_1 = [{
            'client_generated_id': client_uuid,
            'latitude': 12.910020,
            'longitude': 77.680020,
            'accuracy_m': 8.5,
            'device_captured_at': now_str
        }]

        # First upload accepted
        res_1 = services.ingest_location_batch(duty.duty_id, batch_1)
        self.assertEqual(res_1['accepted_count'], 1)
        self.assertEqual(res_1['duplicate_count'], 0)

        # Second upload with same client ID is recognized as duplicate (idempotent)
        res_2 = services.ingest_location_batch(duty.duty_id, batch_1)
        self.assertEqual(res_2['accepted_count'], 0)
        self.assertEqual(res_2['duplicate_count'], 1)

        # Malformed coordinates (Lat > 90) are rejected
        malformed_batch = [{
            'client_generated_id': uuid.uuid4(),
            'latitude': 99.999999,
            'longitude': 77.680000,
            'accuracy_m': 10.0,
            'device_captured_at': now_str
        }]
        res_3 = services.ingest_location_batch(duty.duty_id, malformed_batch)
        self.assertEqual(res_3['rejected_count'], 1)

    # --------------------------------------------------------------------------
    # 4. Accuracy-Aware Geofence & 3-Reading Debounce (AC-7.19, AC-7.20, AC-7.21, AC-7.27)
    # --------------------------------------------------------------------------
    def test_ac4_accuracy_aware_geofence_debounce_and_alert(self):
        duty = services.start_monitoring_duty(
            assignment_id=self.assignment_1.assignment_id,
            attendance_record_id=self.att_record_1.attendance_id,
            actor_user=self.admin
        )

        # 1. Point cleanly inside geofence (Site center: 12.9100, 77.6800, Radius: 100m)
        # Lat 12.9101, Lon 77.6801 is ~15m away
        res = services.ingest_location_batch(duty.duty_id, [{
            'client_generated_id': uuid.uuid4(),
            'latitude': 12.910100,
            'longitude': 77.680100,
            'accuracy_m': 10.0,
            'device_captured_at': timezone.now().isoformat()
        }])
        stat = GuardMonitoringStatus.objects.get(duty=duty)
        self.assertEqual(stat.primary_status, 'on_duty_at_site')

        # 2. Boundary uncertain reading (Distance 95m, Accuracy ±20m -> 95-20 < 100 < 95+20)
        # Does NOT flip status
        dist, boundary = services.classify_geofence_boundary(12.910800, 77.680000, 25.0, self.site_a)
        self.assertEqual(boundary, 'UNCERTAIN')

        # 3. 1st reading outside geofence (Lat 12.9150, Lon 77.6800 is ~550m away)
        services.ingest_location_batch(duty.duty_id, [{
            'client_generated_id': uuid.uuid4(),
            'latitude': 12.915000,
            'longitude': 77.680000,
            'accuracy_m': 10.0,
            'device_captured_at': timezone.now().isoformat()
        }])
        stat.refresh_from_db()
        self.assertEqual(stat.consecutive_outside_count, 1)
        self.assertEqual(stat.primary_status, 'on_duty_at_site')  # Debounce not yet reached!

        # 2nd reading outside
        services.ingest_location_batch(duty.duty_id, [{
            'client_generated_id': uuid.uuid4(),
            'latitude': 12.915100,
            'longitude': 77.680000,
            'accuracy_m': 10.0,
            'device_captured_at': timezone.now().isoformat()
        }])
        stat.refresh_from_db()
        self.assertEqual(stat.consecutive_outside_count, 2)
        self.assertEqual(stat.primary_status, 'on_duty_at_site')

        # 3rd reading outside -> Debounce target reached! Status flips & GEOFENCE_EXIT alert raised
        services.ingest_location_batch(duty.duty_id, [{
            'client_generated_id': uuid.uuid4(),
            'latitude': 12.915200,
            'longitude': 77.680000,
            'accuracy_m': 10.0,
            'device_captured_at': timezone.now().isoformat()
        }])
        stat.refresh_from_db()
        self.assertEqual(stat.consecutive_outside_count, 3)
        self.assertEqual(stat.primary_status, 'on_duty_outside_site')
        self.assertTrue(stat.has_active_alert)

        alert = MonitoringAlert.objects.filter(duty=duty, alert_type='GEOFENCE_EXIT', state='RAISED').first()
        self.assertIsNotNone(alert)
        self.assertEqual(alert.severity, 'HIGH')

        # 4. Guard returns inside site -> resets counter, flips status back to on_duty_at_site, auto-resolves alert
        services.ingest_location_batch(duty.duty_id, [{
            'client_generated_id': uuid.uuid4(),
            'latitude': 12.910010,
            'longitude': 77.680010,
            'accuracy_m': 5.0,
            'device_captured_at': timezone.now().isoformat()
        }])
        stat.refresh_from_db()
        self.assertEqual(stat.consecutive_outside_count, 0)
        self.assertEqual(stat.primary_status, 'on_duty_at_site')

        alert.refresh_from_db()
        self.assertEqual(alert.state, 'AUTO_RESOLVED')

    # --------------------------------------------------------------------------
    # 5. Heartbeat, Battery Alert, Stale & No Contact (AC-7.15, AC-7.22, AC-7.23)
    # --------------------------------------------------------------------------
    def test_ac5_heartbeat_battery_and_stale_no_contact(self):
        duty = services.start_monitoring_duty(
            assignment_id=self.assignment_1.assignment_id,
            attendance_record_id=self.att_record_1.attendance_id,
            actor_user=self.admin
        )

        # Ingest heartbeat with critical battery (12%)
        hb_res = services.ingest_heartbeat(duty.duty_id, {
            'client_generated_id': uuid.uuid4(),
            'captured_at': timezone.now().isoformat(),
            'battery_percent': 12,
            'network_type': '4G',
            'permission_state': 'GRANTED'
        })
        self.assertEqual(hb_res['status'], 'ACCEPTED')

        # Verify low battery alert created
        bat_alert = MonitoringAlert.objects.filter(duty=duty, alert_type='LOW_BATTERY', state='RAISED').first()
        self.assertIsNotNone(bat_alert)
        self.assertEqual(bat_alert.severity, 'NORMAL')

        # Simulate last communication 15 minutes ago -> Recalculate triggers STALE
        stat = GuardMonitoringStatus.objects.get(duty=duty)
        stat.last_communication_at = timezone.now() - timedelta(minutes=15)
        stat.save()

        services.recalculate_duty_statuses(company_id=self.company.company_id)
        stat.refresh_from_db()
        self.assertEqual(stat.primary_status, 'stale')
        self.assertEqual(stat.display_status, 'Low Signal or Stale')

        # Simulate last communication 25 minutes ago -> Recalculate triggers NO_CONTACT & alert
        stat.last_communication_at = timezone.now() - timedelta(minutes=25)
        stat.save()

        services.recalculate_duty_statuses(company_id=self.company.company_id)
        stat.refresh_from_db()
        self.assertEqual(stat.primary_status, 'no_contact')
        self.assertEqual(stat.display_status, 'No Contact')

        nc_alert = MonitoringAlert.objects.filter(duty=duty, alert_type='NO_CONTACT', state='RAISED').first()
        self.assertIsNotNone(nc_alert)

    # --------------------------------------------------------------------------
    # 6. Alert Lifecycle & Dismissal Validation (AC-7.30, AC-7.31, AC-7.32)
    # --------------------------------------------------------------------------
    def test_ac6_alert_lifecycle_and_false_alarm_dismissal(self):
        duty = services.start_monitoring_duty(
            assignment_id=self.assignment_1.assignment_id,
            attendance_record_id=self.att_record_1.attendance_id,
            actor_user=self.admin
        )
        alert = services.raise_monitoring_alert(duty, 'MOCK_LOCATION_DETECTED', 'HIGH', 'Test mock signal')

        # Acknowledge
        services.acknowledge_alert(alert.alert_id, self.supervisor)
        alert.refresh_from_db()
        self.assertEqual(alert.state, 'ACKNOWLEDGED')
        self.assertEqual(alert.acknowledged_by, self.supervisor)

        # Dismiss as false alarm without reason fails
        with self.assertRaises(ValidationError):
            services.dismiss_alert_as_false_alarm(alert.alert_id, '', self.supervisor)

        # Dismiss with mandatory reason succeeds
        services.dismiss_alert_as_false_alarm(alert.alert_id, 'False alarm confirmed after physical supervisor visit', self.supervisor)
        alert.refresh_from_db()
        self.assertEqual(alert.state, 'DISMISSED')
        self.assertIn('physical supervisor visit', alert.dismissal_reason)

    # --------------------------------------------------------------------------
    # 7. Supervisor Ping with 5-minute Cooldown (AC-7.37, AC-7.38, AC-7.40)
    # --------------------------------------------------------------------------
    def test_ac7_supervisor_ping_and_cooldown(self):
        duty = services.start_monitoring_duty(
            assignment_id=self.assignment_1.assignment_id,
            attendance_record_id=self.att_record_1.attendance_id,
            actor_user=self.admin
        )

        ping = services.send_supervisor_ping(duty.duty_id, self.supervisor)
        self.assertEqual(ping.delivery_state, 'DELIVERED')
        self.assertEqual(ping.response_state, 'PENDING')

        # Repeated ping within 5 minutes is rejected
        with self.assertRaises(ValidationError):
            services.send_supervisor_ping(duty.duty_id, self.supervisor)

        # Guard responds
        services.respond_to_ping(ping.ping_id, "I am fine and at the main gate")
        ping.refresh_from_db()
        self.assertEqual(ping.response_state, 'RESPONDED')
        self.assertEqual(ping.response_value, "I am fine and at the main gate")

    # --------------------------------------------------------------------------
    # 8. Privacy, Client-Safe & Downstream Module Interfaces (AC-7.41, AC-7.43, AC-7.45)
    # --------------------------------------------------------------------------
    def test_ac8_cross_module_and_privacy_queries(self):
        duty = services.start_monitoring_duty(
            assignment_id=self.assignment_1.assignment_id,
            attendance_record_id=self.att_record_1.attendance_id,
            actor_user=self.admin
        )
        now_time = timezone.now()
        services.ingest_location_batch(duty.duty_id, [{
            'client_generated_id': uuid.uuid4(),
            'latitude': 12.910010,
            'longitude': 77.680010,
            'accuracy_m': 12.0,
            'device_captured_at': now_time.isoformat()
        }])

        # Module 9 query: get_last_known_position
        pos_9 = services.get_last_known_position(self.guard_1.employee_id)
        self.assertEqual(pos_9['trust_flag'], 'TRUSTED')
        self.assertAlmostEqual(pos_9['latitude'], 12.910010, places=5)

        # Module 8 query: get_guard_position_at_time
        pos_8 = services.get_guard_position_at_time(self.guard_1.employee_id, now_time)
        self.assertTrue(pos_8['available'])
        self.assertEqual(pos_8['time_delta_seconds'], 0)

        # Module 10 query: get_client_safe_status
        client_res = services.get_client_safe_status(self.client.company_id, site_id=self.site_a.site_id)
        self.assertTrue(len(client_res) >= 1)
        safe_entry = client_res[0]
        self.assertEqual(safe_entry['client_safe_status'], 'On duty at site')
        # Crucial privacy assertion: coordinates, accuracy, battery, trails must NEVER be in client response!
        self.assertNotIn('latitude', safe_entry)
        self.assertNotIn('longitude', safe_entry)
        self.assertNotIn('accuracy_m', safe_entry)
        self.assertNotIn('battery_percent', safe_entry)
        self.assertNotIn('alerts', safe_entry)
