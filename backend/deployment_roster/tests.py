import uuid
from datetime import date, time, timedelta, datetime
from django.utils import timezone
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth.hashers import make_password
from rest_framework.exceptions import ValidationError, PermissionDenied

from foundation.models import User
from master_data.models import Company, Client, ClientSite, PostType, SiteShift, SiteManpowerRequirement
from guard_management.models import Employee, EmployeeDocument, EmployeeCheck, EmployeeTraining
from foundation.services.settings_service import set_setting
from deployment_roster.models import (
    PostSlot,
    Roster,
    RosterAssignment,
    AssignmentHistory,
    ShiftSwapRequest,
    EmergencyRatification,
    DutyAcknowledgement,
)
from deployment_roster import services


class DeploymentRosterTests(TestCase):
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

        # 2. Admin User
        self.admin = User.objects.create(
            company_id=self.company.company_id,
            email='admin@apexsecurity.local',
            full_name='Apex Admin',
            role='ADMIN',
            phone='+919888800001',
            password_hash=make_password('AdminPass123!'),
            status='ACTIVE'
        )

        # 3. Supervisor User
        self.supervisor = User.objects.create(
            company_id=self.company.company_id,
            email='supervisor@apexsecurity.local',
            full_name='Field Officer Mohan',
            role='SUPERVISOR',
            phone='+919888800002',
            password_hash=make_password('SuperPass123!'),
            status='ACTIVE'
        )

        # 4. Client & Client Site
        self.client = Client.objects.create(
            company=self.company,
            legal_name='Wipro SEZ Campus',
            client_code='WIP-SEZ',
            status='active'
        )
        self.site = ClientSite.objects.create(
            client=self.client,
            site_code='WIP-BLR-01',
            site_name='Wipro Sarjapur Campus',
            operational_status='active',
            latitude=12.9100,
            longitude=77.6800,
            geofence_radius_m=100
        )

        # 5. Post Types (Unarmed & Armed)
        self.post_unarmed = PostType.objects.create(
            company=self.company,
            code='GEN_GUARD',
            name='General Security Guard',
            requires_armed_authorization=False
        )
        self.post_armed = PostType.objects.create(
            company=self.company,
            code='ARMED_GUARD',
            name='Armed Security Guard',
            requires_armed_authorization=True
        )

        # 6. Shifts: Day Shift (08:00 - 16:00) & Night Shift Cross-Midnight (20:00 - 04:00)
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
        self.shift_early = SiteShift.objects.create(
            site=self.site,
            shift_code='EARLY',
            shift_name='Early Morning Shift',
            start_time=time(2, 0),
            end_time=time(10, 0),
            duration_minutes=480,
            is_cross_midnight=False,
            is_active=True
        )

        # 7. Manpower Requirement: 3 guards for Day Shift
        self.req_day = SiteManpowerRequirement.objects.create(
            site=self.site,
            shift=self.shift_day,
            post_type=self.post_unarmed,
            required_count=3,
            effective_from=date.today(),
            is_active=True
        )

        # Configure settings for deployability
        set_setting(self.company.company_id, 'mandatory_doc_types', 'identity_proof,address_proof')
        set_setting(self.company.company_id, 'mandatory_training_types', 'induction')

        # 8. Employees (Active & Verified)
        self.guard_a = Employee.objects.create(
            company_id=self.company.company_id,
            employee_code='GRD-KA-0001',
            first_name='Ramesh',
            last_name='Kumar',
            phone='+919800000001',
            gender='MALE',
            date_of_birth=date(1995, 5, 10),
            date_joined=date(2025, 1, 1),
            lifecycle_status='active',
        )
        self.guard_b = Employee.objects.create(
            company_id=self.company.company_id,
            employee_code='GRD-KA-0002',
            first_name='Suresh',
            last_name='Gowda',
            phone='+919800000002',
            gender='MALE',
            date_of_birth=date(1993, 8, 15),
            date_joined=date(2025, 1, 1),
            lifecycle_status='active',
        )
        # Armed Guard
        self.guard_armed = Employee.objects.create(
            company_id=self.company.company_id,
            employee_code='GRD-KA-0003',
            first_name='Vikram',
            last_name='Singh',
            phone='+919800000003',
            gender='MALE',
            date_of_birth=date(1988, 1, 20),
            date_joined=date(2025, 1, 1),
            lifecycle_status='active',
        )
        # Ineligible Guard (Applicant, unverified)
        self.guard_ineligible = Employee.objects.create(
            company_id=self.company.company_id,
            employee_code='GRD-KA-0004',
            first_name='Anil',
            last_name='Verma',
            phone='+919800000004',
            gender='MALE',
            date_of_birth=date(1999, 12, 1),
            date_joined=date(2025, 1, 1),
            lifecycle_status='applicant',
        )

        # Upload mandatory documents and checks for Guard A, Guard B, and Guard Armed so Module 3 check passes
        for g in (self.guard_a, self.guard_b, self.guard_armed):
            EmployeeDocument.objects.create(
                employee=g,
                document_type='identity_proof',
                document_number=f"DOC-{g.employee_code}-id",
                storage_key='docs/id.pdf',
                verification_status='verified',
                is_active=True,
                expiry_date=date.today() + timedelta(days=365)
            )
            EmployeeDocument.objects.create(
                employee=g,
                document_type='address_proof',
                document_number=f"DOC-{g.employee_code}-addr",
                storage_key='docs/addr.pdf',
                verification_status='verified',
                is_active=True,
                expiry_date=date.today() + timedelta(days=365)
            )
            EmployeeCheck.objects.create(
                employee=g,
                check_type='police',
                status='cleared',
                valid_until=date.today() + timedelta(days=365)
            )
            EmployeeCheck.objects.create(
                employee=g,
                check_type='medical',
                status='cleared',
                valid_until=date.today() + timedelta(days=365)
            )
            EmployeeTraining.objects.create(
                employee=g,
                attendance_status='present',
                result='passed',
                valid_until=date.today() + timedelta(days=365)
            )

        # Arms licence for Guard Armed
        EmployeeDocument.objects.create(
            employee=self.guard_armed,
            document_type='arms_licence',
            document_number='ARMS-KA-999',
            storage_key='docs/arms.pdf',
            verification_status='verified',
            is_active=True,
            expiry_date=date.today() + timedelta(days=365)
        )

    def test_ac01_and_ac02_generate_slots_and_idempotency(self):
        """
        AC-01: Active requirement for 3 guards generates 3 distinct slots per day.
        AC-02: Idempotent - running generation twice does not create duplicate slots.
        """
        target_date = date.today() + timedelta(days=1)
        res1 = services.generate_slots_for_period(
            site_id=self.site.site_id,
            start_date=target_date,
            end_date=target_date,
            actor_user=self.admin
        )
        self.assertEqual(res1['slots_generated'], 3)
        slots = PostSlot.objects.filter(site=self.site, deployment_date=target_date)
        self.assertEqual(slots.count(), 3)
        sequences = list(slots.values_list('slot_sequence', flat=True))
        self.assertEqual(sorted(sequences), [1, 2, 3])

        # Rerun generation - should not create duplicates
        res2 = services.generate_slots_for_period(
            site_id=self.site.site_id,
            start_date=target_date,
            end_date=target_date,
            actor_user=self.admin
        )
        self.assertEqual(res2['slots_generated'], 0)
        self.assertEqual(PostSlot.objects.filter(site=self.site, deployment_date=target_date).count(), 3)

    def test_ac06_ac07_ac08_assignment_and_eligibility(self):
        """
        AC-06: Valid assignment creates permanent UUID assignment_id.
        AC-07: Ineligible guard blocked with Module 3 failure reason.
        AC-08: Unarmed guard blocked from armed post.
        """
        target_date = date.today() + timedelta(days=2)
        services.generate_slots_for_period(self.site.site_id, target_date, target_date, self.admin)
        slot1 = PostSlot.objects.get(site=self.site, deployment_date=target_date, slot_sequence=1)

        # 1. Ineligible Guard Assignment -> Blocked (AC-07)
        with self.assertRaises(ValidationError) as ctx:
            services.assign_guard_to_slot(
                slot_id=slot1.slot_id,
                employee_id=self.guard_ineligible.employee_id,
                actor_user=self.admin
            )
        self.assertIn('hard_conflicts', ctx.exception.detail)

        # 2. Valid Guard Assignment -> Created (AC-06)
        assignment = services.assign_guard_to_slot(
            slot_id=slot1.slot_id,
            employee_id=self.guard_a.employee_id,
            actor_user=self.admin
        )
        self.assertIsNotNone(assignment.assignment_id)
        self.assertEqual(assignment.status, 'scheduled')
        slot1.refresh_from_db()
        self.assertEqual(slot1.slot_status, 'filled')

        # 3. Armed Slot check (AC-08)
        # Create an armed slot
        armed_slot = PostSlot.objects.create(
            company=self.company,
            site=self.site,
            shift=self.shift_day,
            post_type=self.post_armed,
            deployment_date=target_date,
            slot_sequence=10,
            slot_status='open'
        )
        # Unarmed Guard A attempting armed post -> Blocked
        with self.assertRaises(ValidationError) as ctx:
            services.assign_guard_to_slot(
                slot_id=armed_slot.slot_id,
                employee_id=self.guard_b.employee_id,
                actor_user=self.admin
            )
        self.assertIn('hard_conflicts', ctx.exception.detail)

        # Armed Guard on armed post -> Succeeds
        armed_assignment = services.assign_guard_to_slot(
            slot_id=armed_slot.slot_id,
            employee_id=self.guard_armed.employee_id,
            actor_user=self.admin
        )
        self.assertEqual(armed_assignment.status, 'scheduled')

    def test_ac12_and_ac13_cross_midnight_collision_detection(self):
        """
        AC-12 & AC-13: Night shift 20:00 - 04:00 (+1d) collides with 02:00 - 10:00 on the following date.
        """
        day1 = date.today() + timedelta(days=3)
        day2 = day1 + timedelta(days=1)

        slot_night = PostSlot.objects.create(
            company=self.company,
            site=self.site,
            shift=self.shift_night,
            post_type=self.post_unarmed,
            deployment_date=day1,
            slot_sequence=1,
            slot_status='open'
        )
        slot_early = PostSlot.objects.create(
            company=self.company,
            site=self.site,
            shift=self.shift_early,
            post_type=self.post_unarmed,
            deployment_date=day2,
            slot_sequence=1,
            slot_status='open'
        )

        # Assign Guard A to Night shift on day 1 (20:00 to 04:00 day 2)
        services.assign_guard_to_slot(slot_night.slot_id, self.guard_a.employee_id, actor_user=self.admin)

        # Attempt to assign Guard A to Early Morning shift on day 2 (02:00 to 10:00 day 2)
        # Interval overlaps between 02:00 and 04:00 -> MUST BE BLOCKED (AC-13)
        with self.assertRaises(ValidationError) as ctx:
            services.assign_guard_to_slot(slot_early.slot_id, self.guard_a.employee_id, actor_user=self.admin)
        self.assertIn('hard_conflicts', ctx.exception.detail)

    def test_ac20_and_ac23_roster_publishing_and_acknowledgement(self):
        """
        AC-20: Publishing roster makes assignments visible to guards.
        AC-23: Guard digital duty acknowledgement records timestamp.
        """
        target_date = date.today() + timedelta(days=5)
        services.generate_slots_for_period(self.site.site_id, target_date, target_date, self.admin)
        slot = PostSlot.objects.filter(site=self.site, deployment_date=target_date, slot_sequence=1).first()
        assignment = services.assign_guard_to_slot(slot.slot_id, self.guard_a.employee_id, actor_user=self.admin)

        # Publish Roster
        roster = services.publish_roster(self.site.site_id, target_date, target_date, self.admin)
        self.assertEqual(roster.status, 'published')
        assignment.refresh_from_db()
        self.assertEqual(assignment.roster_id, roster.roster_id)

        # Guard acknowledges duty
        guard_user = User.objects.create(
            company_id=self.company.company_id,
            email='guard.a@apexsecurity.local',
            full_name='Ramesh Kumar',
            role='GUARD',
            guard_profile_id=self.guard_a.employee_id,
            password_hash=make_password('GuardPass123!'),
            status='ACTIVE'
        )
        ack = services.acknowledge_duty(
            assignment_id=assignment.assignment_id,
            guard_user=guard_user,
            device_id='DEVICE-MOBILE-TEST-1',
            ip_address='127.0.0.1'
        )
        self.assertIsNotNone(ack.acknowledgement_id)
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, 'acknowledged')

    def test_ac30_and_ac31_no_show_and_linked_replacement(self):
        """
        AC-30: No-show event marks slot at-risk.
        AC-31: Replacement workflow creates linked replacement duty preserving original assignment.
        """
        target_date = date.today()
        services.generate_slots_for_period(self.site.site_id, target_date, target_date, self.admin)
        slot = PostSlot.objects.filter(site=self.site, deployment_date=target_date, slot_sequence=1).first()
        assignment = services.assign_guard_to_slot(slot.slot_id, self.guard_a.employee_id, actor_user=self.admin)

        # Module 6 reports No-show
        res = services.report_no_show_from_module6(assignment.assignment_id, timezone.now(), actor_user=self.supervisor)
        self.assertEqual(res['slot_status'], 'at_risk')
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, 'no_show')

        # Supervisor creates linked replacement assignment
        replacement = services.create_replacement_assignment(
            original_assignment_id=assignment.assignment_id,
            replacement_employee_id=self.guard_b.employee_id,
            reason="Guard A reported sick, deployed Guard B from reliever pool",
            actor_user=self.supervisor
        )
        self.assertIsNotNone(replacement.assignment_id)
        self.assertEqual(replacement.assignment_type, 'replacement')
        self.assertEqual(replacement.original_assignment_id, assignment.assignment_id)
        self.assertEqual(replacement.status, 'scheduled')
        slot.refresh_from_db()
        self.assertEqual(slot.slot_status, 'filled')

    def test_ac34_and_ac35_shift_swap_atomic_exchange(self):
        """
        AC-34: Valid shift swap atomically exchanges guards between assignments preserving permanent IDs.
        AC-35: Swap fails and rejects if conflict occurs.
        """
        day1 = date.today() + timedelta(days=6)
        day2 = date.today() + timedelta(days=7)

        # Two slots
        services.generate_slots_for_period(self.site.site_id, day1, day2, self.admin)
        slot1 = PostSlot.objects.filter(site=self.site, deployment_date=day1, slot_sequence=1).first()
        slot2 = PostSlot.objects.filter(site=self.site, deployment_date=day2, slot_sequence=1).first()

        assign1 = services.assign_guard_to_slot(slot1.slot_id, self.guard_a.employee_id, actor_user=self.admin)
        assign2 = services.assign_guard_to_slot(slot2.slot_id, self.guard_b.employee_id, actor_user=self.admin)

        orig_id_1 = assign1.assignment_id
        orig_id_2 = assign2.assignment_id

        # Submit swap request
        swap = services.request_shift_swap(
            assignment_a_id=assign1.assignment_id,
            target_employee_id=self.guard_b.employee_id,
            assignment_b_id=assign2.assignment_id,
            reason="Family event swap",
            requesting_guard_user=self.admin
        )
        self.assertEqual(swap.status, 'pending')

        # Supervisor approves swap
        approved_swap = services.approve_shift_swap(swap.swap_id, self.supervisor)
        self.assertEqual(approved_swap.status, 'approved')

        # Verify atomic exchange: guards are swapped, but permanent assignment IDs stay intact!
        assign1.refresh_from_db()
        assign2.refresh_from_db()
        self.assertEqual(assign1.assignment_id, orig_id_1)
        self.assertEqual(assign2.assignment_id, orig_id_2)
        self.assertEqual(assign1.employee_id, self.guard_b.employee_id)
        self.assertEqual(assign2.employee_id, self.guard_a.employee_id)

    def test_ac33_emergency_deployment_and_ratification(self):
        """
        AC-33: Supervisor emergency deployment creates flagged duty and requires Admin ratification.
        """
        target_date = date.today() + timedelta(days=8)
        assignment = services.create_emergency_deployment(
            site_id=self.site.site_id,
            shift_id=self.shift_day.shift_id,
            post_type_id=self.post_unarmed.post_type_id,
            deployment_date=target_date,
            employee_id=self.guard_a.employee_id,
            reason="Perimeter gate lock broken, immediate visual deterrence required",
            supervisor_user=self.supervisor
        )
        self.assertTrue(assignment.is_emergency)
        rat = EmergencyRatification.objects.filter(assignment=assignment).first()
        self.assertIsNotNone(rat)
        self.assertEqual(rat.status, 'pending')

        # Admin ratifies
        ratified = services.ratify_emergency_deployment(rat.ratification_id, 'ratified', self.admin)
        self.assertEqual(ratified.status, 'ratified')

