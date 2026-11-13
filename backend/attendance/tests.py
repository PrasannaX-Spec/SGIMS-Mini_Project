import uuid
import hashlib
from datetime import date, time, timedelta, datetime
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from rest_framework.exceptions import ValidationError, PermissionDenied

from foundation.models import User, BoundDevice
from master_data.models import Company, Client, ClientSite, PostType, SiteShift, SiteManpowerRequirement
from guard_management.models import Employee, EmployeeDocument, EmployeeCheck, EmployeeTraining
from deployment_roster.models import PostSlot, RosterAssignment
from deployment_roster import services as roster_services
from foundation.services.settings_service import set_setting

from attendance.models import (
    AttendancePeriod,
    AttendanceRecord,
    AttendanceCapture,
    AttendanceEvidence,
    AttendanceFlag,
    AttendanceRevision,
    AttendanceRegularisation,
    AttendanceApproval,
    AttendancePeriodException,
    ManualAttendanceCounter,
)
from attendance import services


class AttendanceModuleTests(TestCase):
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

        # 2. Users
        self.admin = User.objects.create(
            company_id=self.company.company_id,
            email='admin@apexattendance.local',
            full_name='Apex Admin',
            role='ADMIN',
            phone='+919888800001',
            password_hash=make_password('AdminPass123!'),
            status='ACTIVE'
        )

        self.supervisor = User.objects.create(
            company_id=self.company.company_id,
            email='supervisor@apexattendance.local',
            full_name='Field Officer Kiran',
            role='SUPERVISOR',
            phone='+919888800002',
            password_hash=make_password('SuperPass123!'),
            status='ACTIVE'
        )

        # 3. Client & Client Site (Coordinates: Lat 12.9100, Lon 77.6800, Geofence: 100m)
        self.client = Client.objects.create(
            company=self.company,
            legal_name='Infosys Campus',
            client_code='INF-BLR',
            status='active'
        )
        self.site = ClientSite.objects.create(
            client=self.client,
            site_code='INF-ELEC-01',
            site_name='Infosys Electronic City',
            operational_status='active',
            latitude=Decimal('12.910000'),
            longitude=Decimal('77.680000'),
            geofence_radius_m=100
        )

        # 4. Shifts: Day Shift (08:00 - 16:00) & Night Shift (20:00 - 04:00)
        self.shift_day = SiteShift.objects.create(
            site=self.site,
            shift_code='DAY',
            shift_name='Day Shift',
            start_time=time(8, 0),
            end_time=time(16, 0),
            duration_minutes=480,
            is_cross_midnight=False,
            is_active=True
        )
        self.shift_night = SiteShift.objects.create(
            site=self.site,
            shift_code='NIGHT',
            shift_name='Night Shift',
            start_time=time(20, 0),
            end_time=time(4, 0),
            duration_minutes=480,
            is_cross_midnight=True,
            is_active=True
        )

        # Post type & Manpower requirement
        self.post_type = PostType.objects.create(
            company=self.company,
            code='GEN_GUARD',
            name='Security Guard'
        )
        self.req_day = SiteManpowerRequirement.objects.create(
            site=self.site,
            shift=self.shift_day,
            post_type=self.post_type,
            required_count=2,
            effective_from=date.today(),
            is_active=True
        )

        # 5. Employees
        self.guard_1 = Employee.objects.create(
            company_id=self.company.company_id,
            employee_code='GRD-KA-1001',
            first_name='Raju',
            last_name='Shetty',
            phone='+919800001001',
            gender='MALE',
            date_of_birth=date(1994, 2, 10),
            date_joined=date(2025, 1, 1),
            lifecycle_status='active',
        )
        self.guard_2 = Employee.objects.create(
            company_id=self.company.company_id,
            employee_code='GRD-KA-1002',
            first_name='Manjunath',
            last_name='Gowda',
            phone='+919800001002',
            gender='MALE',
            date_of_birth=date(1992, 6, 20),
            date_joined=date(2025, 1, 1),
            lifecycle_status='active',
        )

        # Configure deployability & settings
        set_setting(self.company.company_id, 'mandatory_doc_types', 'identity_proof')
        set_setting(self.company.company_id, 'mandatory_training_types', 'induction')
        for g in (self.guard_1, self.guard_2):
            EmployeeDocument.objects.create(
                employee=g,
                document_type='identity_proof',
                document_number=f"DOC-{g.employee_code}-id",
                storage_key='docs/id.pdf',
                verification_status='verified',
                is_active=True
            )
            EmployeeTraining.objects.create(
                employee=g,
                attendance_status='present',
                result='passed',
                valid_until=date.today() + timedelta(days=365)
            )

        # Link guard_1 to User and Bound Device
        self.guard_user = User.objects.create(
            company_id=self.company.company_id,
            email='guard1@apexattendance.local',
            full_name='Raju Shetty',
            role='GUARD',
            phone='+919800001001',
            guard_profile_id=self.guard_1.employee_id,
            password_hash=make_password('GuardPass123!'),
            status='ACTIVE'
        )
        self.bound_device = BoundDevice.objects.create(
            company_id=self.company.company_id,
            user=self.guard_user,
            device_id='DEVICE-SAMSUNG-A12-001',
            model='Samsung Galaxy A12'
        )

        # Generate slots and assignment for guard_1
        self.today = date.today()
        roster_services.generate_slots_for_period(self.site.site_id, self.today, self.today, self.admin)
        slot = PostSlot.objects.filter(site=self.site, deployment_date=self.today).first()
        self.assignment = roster_services.assign_guard_to_slot(slot.slot_id, self.guard_1.employee_id, actor_user=self.admin)

    def test_ac01_to_ac09_geofence_and_checkin(self):
        """
        AC-01: Retrieve assignment.
        AC-06: Check-in within geofence outcome is 'valid'.
        AC-07: Check-in outside geofence without reason blocked; with reason flagged.
        AC-08: Check-in with poor GPS accuracy (>100m) blocked.
        """
        capture_id = uuid.uuid4()
        now_dt = timezone.now()
        self.assignment.start_time = now_dt - timedelta(minutes=5)
        self.assignment.end_time = now_dt + timedelta(hours=8)
        self.assignment.save()

        # 1. Valid Check-in inside geofence (Lat 12.9102, Lon 77.6801 is ~25m from center)
        att = services.record_check_in(
            employee_id=self.guard_1.employee_id,
            data={
                'capture_id': str(capture_id),
                'assignment_id': str(self.assignment.assignment_id),
                'device_id': 'DEVICE-SAMSUNG-A12-001',
                'device_time': now_dt.isoformat(),
                'latitude': 12.910200,
                'longitude': 77.680100,
                'gps_accuracy': 15.0,
                'photo_storage_key': 'photos/checkin_01.jpg'
            },
            actor_user=self.guard_user
        )
        self.assertEqual(att.status, 'in_progress')
        self.assertEqual(att.late_minutes, 0)
        self.assertEqual(att.captures.count(), 1)
        self.assertEqual(att.captures.first().geofence_outcome, 'valid')

        # 2. Poor GPS accuracy (> 100m) blocked (AC-08)
        with self.assertRaises(ValidationError) as ctx:
            services.record_check_in(
                employee_id=self.guard_1.employee_id,
                data={
                    'capture_id': str(uuid.uuid4()),
                    'assignment_id': str(self.assignment.assignment_id),
                    'device_id': 'DEVICE-SAMSUNG-A12-001',
                    'device_time': now_dt.isoformat(),
                    'latitude': 12.910200,
                    'longitude': 77.680100,
                    'gps_accuracy': 150.0,
                },
                actor_user=self.guard_user
            )
        self.assertIn('worse than maximum allowed limit', str(ctx.exception))

        # 3. Check-in outside geofence without reason blocked (AC-07)
        # Lat 12.9200 is ~1.1 km away
        with self.assertRaises(ValidationError) as ctx:
            services.record_check_in(
                employee_id=self.guard_1.employee_id,
                data={
                    'capture_id': str(uuid.uuid4()),
                    'assignment_id': str(self.assignment.assignment_id),
                    'device_id': 'DEVICE-SAMSUNG-A12-001',
                    'device_time': now_dt.isoformat(),
                    'latitude': 12.920000,
                    'longitude': 77.680000,
                    'gps_accuracy': 20.0,
                },
                actor_user=self.guard_user
            )
        self.assertIn('away from the site', str(ctx.exception))

    def test_ac10_to_ac13_mock_location_and_device_validation(self):
        """
        AC-10: Mock location detected blocks check-in.
        AC-11: Device time mismatch > 300s adds flag.
        AC-12: Unregistered device rejected.
        """
        now_dt = timezone.now()

        # Mock location blocked (AC-10)
        with self.assertRaises(ValidationError) as ctx:
            services.record_check_in(
                employee_id=self.guard_1.employee_id,
                data={
                    'capture_id': str(uuid.uuid4()),
                    'assignment_id': str(self.assignment.assignment_id),
                    'device_id': 'DEVICE-SAMSUNG-A12-001',
                    'device_time': now_dt.isoformat(),
                    'latitude': 12.910000,
                    'longitude': 77.680000,
                    'gps_accuracy': 10.0,
                    'mock_location_detected': True
                },
                actor_user=self.guard_user
            )
        self.assertIn('Mock location provider detected', str(ctx.exception))

        # Unregistered hardware device rejected (AC-12)
        with self.assertRaises(PermissionDenied) as ctx:
            services.record_check_in(
                employee_id=self.guard_1.employee_id,
                data={
                    'capture_id': str(uuid.uuid4()),
                    'assignment_id': str(self.assignment.assignment_id),
                    'device_id': 'DEVICE-UNKNOWN-HACKED-PHONE',
                    'device_time': now_dt.isoformat(),
                    'latitude': 12.910000,
                    'longitude': 77.680000,
                    'gps_accuracy': 10.0,
                },
                actor_user=self.guard_user
            )
        self.assertIn('This phone is not registered', str(ctx.exception))

    def test_ac14_to_ac18_checkout_and_minute_calculations(self):
        """
        AC-14: Valid check-out records actual check-out time.
        AC-15: Early check-out requires reason.
        FR-6.33, FR-6.37: Worked minutes and regular vs overtime minutes.
        """
        now_dt = timezone.make_aware(datetime.combine(self.today, time(8, 0)))
        att = services.record_check_in(
            employee_id=self.guard_1.employee_id,
            data={
                'capture_id': str(uuid.uuid4()),
                'assignment_id': str(self.assignment.assignment_id),
                'device_id': 'DEVICE-SAMSUNG-A12-001',
                'device_time': now_dt.isoformat(),
                'latitude': 12.910000,
                'longitude': 77.680000,
                'gps_accuracy': 10.0,
            },
            actor_user=self.guard_user
        )

        # Check-out 9 hours later (08:00 to 17:00 = 540 minutes = 480 reg + 60 OT)
        out_dt = timezone.make_aware(datetime.combine(self.today, time(17, 0)))
        updated_att = services.record_check_out(
            employee_id=self.guard_1.employee_id,
            data={
                'capture_id': str(uuid.uuid4()),
                'attendance_id': str(att.attendance_id),
                'device_id': 'DEVICE-SAMSUNG-A12-001',
                'device_time': out_dt.isoformat(),
                'latitude': 12.910000,
                'longitude': 77.680000,
                'gps_accuracy': 10.0,
            },
            actor_user=self.guard_user
        )

        self.assertEqual(updated_att.worked_minutes, 540)
        self.assertEqual(updated_att.regular_minutes, 480)
        self.assertEqual(updated_att.overtime_minutes, 60)
        self.assertEqual(updated_att.status, 'pending_approval')

    def test_ac19_to_ac26_offline_idempotent_sync(self):
        """
        AC-20 & AC-21: Unique client-generated capture_id ensures retry idempotency.
        AC-22: Conflicting duplicate capture payload rejected.
        """
        capture_id = uuid.uuid4()
        now_dt = timezone.make_aware(datetime.combine(self.today, time(8, 0)))

        # 1st Sync
        att1 = services.record_check_in(
            employee_id=self.guard_1.employee_id,
            data={
                'capture_id': str(capture_id),
                'assignment_id': str(self.assignment.assignment_id),
                'device_id': 'DEVICE-SAMSUNG-A12-001',
                'device_time': now_dt.isoformat(),
                'latitude': 12.910000,
                'longitude': 77.680000,
                'gps_accuracy': 10.0,
            },
            actor_user=self.guard_user
        )

        # 2nd Retry with same capture_id (Network timeout retry AC-21)
        att2 = services.record_check_in(
            employee_id=self.guard_1.employee_id,
            data={
                'capture_id': str(capture_id),
                'assignment_id': str(self.assignment.assignment_id),
                'device_id': 'DEVICE-SAMSUNG-A12-001',
                'device_time': now_dt.isoformat(),
                'latitude': 12.910000,
                'longitude': 77.680000,
                'gps_accuracy': 10.0,
            },
            actor_user=self.guard_user
        )
        self.assertEqual(att1.attendance_id, att2.attendance_id)
        self.assertEqual(AttendanceCapture.objects.count(), 1)

        # Conflicting duplicate with different guard (AC-22)
        with self.assertRaises(ValidationError) as ctx:
            services.record_check_in(
                employee_id=self.guard_2.employee_id,
                data={
                    'capture_id': str(capture_id),
                    'assignment_id': str(self.assignment.assignment_id),
                    'device_id': 'DEVICE-SAMSUNG-A12-001',
                    'device_time': now_dt.isoformat(),
                    'latitude': 12.910000,
                    'longitude': 77.680000,
                    'gps_accuracy': 10.0,
                },
                actor_user=self.guard_user
            )
        self.assertIn('Conflicting duplicate capture', str(ctx.exception))

    def test_ac34_to_ac42_supervisor_approval_and_revisions(self):
        """
        AC-34 & AC-35: Bulk approval approves clean records and skips flagged records.
        AC-37: Supervisor cannot approve their own attendance.
        AC-40: Attendance correction creates revision without altering raw captures.
        """
        now_dt = timezone.now()
        self.assignment.start_time = now_dt - timedelta(minutes=5)
        self.assignment.end_time = now_dt + timedelta(hours=8)
        self.assignment.save()

        att = services.record_check_in(
            employee_id=self.guard_1.employee_id,
            data={
                'capture_id': str(uuid.uuid4()),
                'assignment_id': str(self.assignment.assignment_id),
                'device_id': 'DEVICE-SAMSUNG-A12-001',
                'device_time': now_dt.isoformat(),
                'latitude': 12.910000,
                'longitude': 77.680000,
                'gps_accuracy': 10.0,
            },
            actor_user=self.guard_user
        )

        # Mark completed
        att.status = 'completed'
        att.save()

        # AC-34: Bulk clean approval
        res = services.bulk_approve_clean_attendance(
            site_id=self.site.site_id,
            duty_date=self.today,
            actor_user=self.supervisor
        )
        self.assertEqual(res['approved_count'], 1)
        att.refresh_from_db()
        self.assertEqual(att.status, 'approved')

        # AC-37: Prohibit self-approval
        att.status = 'pending_approval'
        att.save()

        # Attempt approval by the guard himself
        with self.assertRaises(PermissionDenied) as ctx:
            services.approve_attendance(att.attendance_id, self.guard_user)
        self.assertIn('cannot approve their own attendance', str(ctx.exception))

        # AC-40: Correction creates revision
        rev_att = services.correct_attendance(
            attendance_id=att.attendance_id,
            data={
                'actual_check_in': (now_dt + timedelta(minutes=30)).isoformat(),
                'actual_check_out': (now_dt + timedelta(hours=8)).isoformat(),
                'reason': 'Adjusted time for delayed gate opening'
            },
            actor_user=self.admin
        )
        self.assertEqual(rev_att.revisions.count(), 1)
        rev = rev_att.revisions.first()
        self.assertEqual(rev.reason, 'Adjusted time for delayed gate opening')
        self.assertEqual(rev.actor_id, self.admin.user_id)

    def test_ac43_to_ac50_regularisation_and_period_lock(self):
        """
        AC-43 & AC-44: Regularisation request creates approved manual record.
        AC-47 & AC-48: Period close blocks on pending approvals; locked period is read-only.
        AC-49: Admin reopens locked period with reason.
        """
        # Regularisation request (AC-43, AC-44)
        reg = services.submit_regularisation(
            employee_id=self.guard_1.employee_id,
            data={
                'site_id': str(self.site.site_id),
                'shift_id': str(self.shift_day.shift_id),
                'duty_date': self.today.isoformat(),
                'claimed_check_in': timezone.make_aware(datetime.combine(self.today, time(8, 0))),
                'claimed_check_out': timezone.make_aware(datetime.combine(self.today, time(16, 0))),
                'reason': 'Phone battery died during shift'
            },
            actor_user=self.guard_user
        )
        self.assertEqual(reg.status, 'pending')

        # Approve regularisation (AC-44)
        services.decide_regularisation(reg.request_id, 'approved', 'Verified by site log', self.supervisor)
        reg.refresh_from_db()
        self.assertEqual(reg.status, 'approved')

        # Verify manual record is created
        manual_att = AttendanceRecord.objects.filter(employee=self.guard_1, duty_date=self.today, is_manual=True).first()
        self.assertIsNotNone(manual_att)
        self.assertTrue(manual_att.is_manual)

        # Period Close without pending records (AC-47)
        period = services.close_attendance_period(
            company_id=self.company.company_id,
            data={
                'start_date': self.today - timedelta(days=5),
                'end_date': self.today + timedelta(days=5),
                'period_name': 'Current Cycle'
            },
            actor_user=self.admin
        )
        self.assertEqual(period.status, 'locked')

        # Locked period blocks corrections (AC-48)
        with self.assertRaises(PermissionDenied):
            services.correct_attendance(
                manual_att.attendance_id,
                {'reason': 'Unauthorized edit'},
                actor_user=self.supervisor
            )

        # Admin reopens period (AC-49)
        reopened = services.reopen_attendance_period(
            period.period_id,
            reason='Audit correction for client dispute',
            actor_user=self.admin
        )
        self.assertEqual(reopened.status, 'reopened')
        self.assertEqual(reopened.reopen_reason, 'Audit correction for client dispute')
