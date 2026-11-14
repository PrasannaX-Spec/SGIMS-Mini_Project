import uuid
import hashlib
from datetime import datetime, timedelta
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from rest_framework.exceptions import ValidationError, PermissionDenied

from foundation.models import Company, User
from master_data.models import Client, ClientSite, SiteSupervisorAssignment
from guard_management.models import Employee
from deployment_roster.models import RosterAssignment
from live_monitoring.models import LocationPoint, MonitoringDuty

from incident_management.models import (
    IncidentCategory,
    GuardRequestType,
    ResolutionOutcome,
    Incident,
    IncidentAttachment,
    IncidentAddendum,
    IncidentTimeline,
    IncidentClientVersion,
    GuardRequest,
    ClientTicket
)
from incident_management import services


class IncidentManagementModuleTests(TestCase):
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

        # 6. Starter Categories
        self.cat_theft = IncidentCategory.objects.create(
            company=self.company,
            name='Theft & Pilferage',
            code='THEFT',
            sensitive=False,
            sharing_policy='EXPLICIT_ONLY',
            default_severity='HIGH'
        )

        self.cat_supervisor_conduct = IncidentCategory.objects.create(
            company=self.company,
            name='Supervisor Conduct Issue',
            code='SUPERVISOR_CONDUCT',
            sensitive=True,
            sharing_policy='NEVER',
            default_severity='HIGH'
        )

        # 7. Starter Request Types & Outcomes
        self.req_type_relief = GuardRequestType.objects.create(
            company=self.company,
            name='Relief / Cover Replacement',
            code='RELIEF_COVER',
            cost_related=False,
            default_response_hours=1
        )
        self.req_type_uniform = GuardRequestType.objects.create(
            company=self.company,
            name='Uniform Replacement',
            code='UNIFORM_ISSUE',
            cost_related=True,
            admin_approval_required=True,
            default_response_hours=24
        )

        self.outcome_resolved = ResolutionOutcome.objects.create(
            company=self.company,
            name='Resolved - Action Completed',
            code='ACTION_COMPLETED'
        )

    # --------------------------------------------------------------------------
    # Test 1: Incident Creation, Idempotency & Initial Status (AC-8.1, AC-8.6, AC-8.8, AC-8.17)
    # --------------------------------------------------------------------------
    def test_incident_creation_and_idempotency(self):
        client_gen_id = uuid.uuid4()
        now = timezone.now()

        incident, created = services.create_incident_report(
            company_id=self.company.company_id,
            guard_user=self.guard_user,
            client_generated_id=client_gen_id,
            category_id=self.cat_theft.category_id,
            description="Copper wire theft attempt caught at North Perimeter fence.",
            occurred_at=now,
            device_time=now,
            suggested_severity='HIGH',
            site_id=self.site_a.site_id
        )

        self.assertTrue(created)
        self.assertEqual(incident.verification_state, 'REPORTED_NOT_VERIFIED')
        self.assertEqual(incident.status, 'REPORTED')
        self.assertTrue(incident.case_number.startswith('INC-'))
        self.assertEqual(incident.context.site_id, self.site_a.site_id)

        # Idempotency: repeating submission with same client_generated_id returns existing
        incident_retry, created_retry = services.create_incident_report(
            company_id=self.company.company_id,
            guard_user=self.guard_user,
            client_generated_id=client_gen_id,
            category_id=self.cat_theft.category_id,
            description="Copper wire theft attempt caught at North Perimeter fence.",
            occurred_at=now,
            device_time=now,
            suggested_severity='HIGH',
            site_id=self.site_a.site_id
        )

        self.assertFalse(created_retry)
        self.assertEqual(incident.incident_id, incident_retry.incident_id)

    # --------------------------------------------------------------------------
    # Test 2: Future Occurred Time Validation (AC-8.5)
    # --------------------------------------------------------------------------
    def test_occurred_time_future_validation(self):
        client_gen_id = uuid.uuid4()
        future_time = timezone.now() + timedelta(days=2)

        with self.assertRaises(ValidationError):
            services.create_incident_report(
                company_id=self.company.company_id,
                guard_user=self.guard_user,
                client_generated_id=client_gen_id,
                category_id=self.cat_theft.category_id,
                description="Future incident test",
                occurred_at=future_time,
                device_time=timezone.now(),
                site_id=self.site_a.site_id
            )

    # --------------------------------------------------------------------------
    # Test 3: SHA-256 Evidence Hash Verification (AC-8.9, AC-8.12, AC-8.13)
    # --------------------------------------------------------------------------
    def test_evidence_hash_verification(self):
        test_bytes = b"Sample Incident Photographic Evidence Captured In-App"
        correct_hash = hashlib.sha256(test_bytes).hexdigest()

        incident, _ = services.create_incident_report(
            company_id=self.company.company_id,
            guard_user=self.guard_user,
            client_generated_id=uuid.uuid4(),
            category_id=self.cat_theft.category_id,
            description="Broken lock found at warehouse gate.",
            occurred_at=timezone.now(),
            device_time=timezone.now(),
            site_id=self.site_a.site_id,
            attachments_metadata=[{
                'media_type': 'PHOTO',
                'file_reference': 'evidence/photo1.jpg',
                'file_size_bytes': len(test_bytes),
                'original_hash': correct_hash
            }]
        )

        att = incident.attachments.first()
        self.assertEqual(att.verification_state, 'PENDING')

        # 1. Successful verification
        verified_att = services.verify_attachment_hash(att.attachment_id, test_bytes)
        self.assertEqual(verified_att.verification_state, 'VERIFIED')
        self.assertEqual(verified_att.upload_state, 'SYNCED')

        # 2. Hash mismatch verification
        tampered_bytes = b"Altered or manipulated photo bytes"
        mismatch_att = services.verify_attachment_hash(att.attachment_id, tampered_bytes)
        self.assertEqual(mismatch_att.verification_state, 'FAILED_VERIFICATION')
        self.assertEqual(mismatch_att.upload_state, 'FAILED')

    # --------------------------------------------------------------------------
    # Test 4: Immutability and Append-Only Addendums (AC-8.21, AC-8.23, AC-8.24)
    # --------------------------------------------------------------------------
    def test_immutability_and_addendums(self):
        incident, _ = services.create_incident_report(
            company_id=self.company.company_id,
            guard_user=self.guard_user,
            client_generated_id=uuid.uuid4(),
            category_id=self.cat_theft.category_id,
            description="Initial original guard report.",
            occurred_at=timezone.now(),
            device_time=timezone.now(),
            site_id=self.site_a.site_id
        )

        original_text = incident.description

        # Guard adds addendum
        addendum = services.add_incident_addendum(
            incident_id=incident.incident_id,
            author_user=self.guard_user,
            content="Correction: Suspect was wearing a red jacket, not blue.",
            client_generated_id=uuid.uuid4()
        )

        incident.refresh_from_db()
        # Original text remains completely intact
        self.assertEqual(incident.description, original_text)
        # Addendum exists as separate record
        self.assertEqual(incident.addendums.count(), 1)
        self.assertEqual(addendum.author_id, self.guard_user.user_id)

    # --------------------------------------------------------------------------
    # Test 5: Supervisor Acknowledgement & Classification Preservation (AC-8.26, AC-8.29, AC-8.30)
    # --------------------------------------------------------------------------
    def test_supervisor_acknowledgement_and_classification(self):
        incident, _ = services.create_incident_report(
            company_id=self.company.company_id,
            guard_user=self.guard_user,
            client_generated_id=uuid.uuid4(),
            category_id=self.cat_theft.category_id,
            description="Perimeter alarm triggered.",
            occurred_at=timezone.now(),
            device_time=timezone.now(),
            suggested_severity='MEDIUM',
            site_id=self.site_a.site_id
        )

        # Supervisor acknowledges
        acked_incident = services.acknowledge_incident(incident.incident_id, self.supervisor)
        self.assertEqual(acked_incident.status, 'ACKNOWLEDGED')
        self.assertEqual(acked_incident.verification_state, 'SUPERVISOR_REVIEWED')

        # Supervisor updates severity to CRITICAL
        updated = services.update_incident_classification(
            incident_id=incident.incident_id,
            actor_user=self.supervisor,
            new_severity='CRITICAL'
        )

        self.assertEqual(updated.current_severity, 'CRITICAL')
        self.assertEqual(updated.original_severity, 'MEDIUM')  # Preserved

    # --------------------------------------------------------------------------
    # Test 6: Resolution Outcome and Note Validation (AC-8.31, AC-8.32)
    # --------------------------------------------------------------------------
    def test_incident_resolution_validation(self):
        incident, _ = services.create_incident_report(
            company_id=self.company.company_id,
            guard_user=self.guard_user,
            client_generated_id=uuid.uuid4(),
            category_id=self.cat_theft.category_id,
            description="Testing resolution validation",
            occurred_at=timezone.now(),
            device_time=timezone.now(),
            site_id=self.site_a.site_id
        )

        # Attempt to resolve without outcome -> must fail
        with self.assertRaises(ValidationError):
            services.resolve_incident(
                incident_id=incident.incident_id,
                actor_user=self.supervisor,
                outcome_id=None,
                resolution_note="Done"
            )

        # Attempt to resolve without resolution note -> must fail
        with self.assertRaises(ValidationError):
            services.resolve_incident(
                incident_id=incident.incident_id,
                actor_user=self.supervisor,
                outcome_id=self.outcome_resolved.outcome_id,
                resolution_note=""
            )

        # Valid resolution
        resolved = services.resolve_incident(
            incident_id=incident.incident_id,
            actor_user=self.supervisor,
            outcome_id=self.outcome_resolved.outcome_id,
            resolution_note="Perimeter fence repaired and guard patrol doubled."
        )
        self.assertEqual(resolved.status, 'RESOLVED')

    # --------------------------------------------------------------------------
    # Test 7: High/Critical Closure Requires Admin Review (AC-8.33)
    # --------------------------------------------------------------------------
    def test_high_critical_incident_requires_admin_review(self):
        incident, _ = services.create_incident_report(
            company_id=self.company.company_id,
            guard_user=self.guard_user,
            client_generated_id=uuid.uuid4(),
            category_id=self.cat_theft.category_id,
            description="High severity incident test",
            occurred_at=timezone.now(),
            device_time=timezone.now(),
            suggested_severity='HIGH',
            site_id=self.site_a.site_id
        )

        services.resolve_incident(
            incident_id=incident.incident_id,
            actor_user=self.supervisor,
            outcome_id=self.outcome_resolved.outcome_id,
            resolution_note="Resolved on site."
        )

        # Supervisor attempting to close High incident directly must be BLOCKED
        with self.assertRaises(PermissionDenied):
            services.close_incident(incident.incident_id, self.supervisor)

        # Admin closing High incident succeeds
        closed = services.close_incident(incident.incident_id, self.admin)
        self.assertEqual(closed.status, 'CLOSED')
        self.assertTrue(closed.admin_reviewed)

    # --------------------------------------------------------------------------
    # Test 8: Supervisor Self-Conduct Closure Protection (AC-8.34)
    # --------------------------------------------------------------------------
    def test_supervisor_self_conduct_closure_protection(self):
        incident, _ = services.create_incident_report(
            company_id=self.company.company_id,
            guard_user=self.guard_user,
            client_generated_id=uuid.uuid4(),
            category_id=self.cat_supervisor_conduct.category_id,
            description="Supervisor arrived late and left site uninspected.",
            occurred_at=timezone.now(),
            device_time=timezone.now(),
            suggested_severity='HIGH',
            site_id=self.site_a.site_id
        )
        incident.supervisor = self.supervisor
        incident.save()

        # Implicated supervisor attempting to close self-conduct case must be DENIED
        with self.assertRaises(PermissionDenied):
            services.close_incident(incident.incident_id, self.supervisor)

    # --------------------------------------------------------------------------
    # Test 9: Admin Reopen Closed Incident Requires Reason (AC-8.37)
    # --------------------------------------------------------------------------
    def test_admin_reopen_requires_reason(self):
        incident, _ = services.create_incident_report(
            company_id=self.company.company_id,
            guard_user=self.guard_user,
            client_generated_id=uuid.uuid4(),
            category_id=self.cat_theft.category_id,
            description="Incident to be closed and reopened",
            occurred_at=timezone.now(),
            device_time=timezone.now(),
            suggested_severity='LOW',
            site_id=self.site_a.site_id
        )

        services.close_incident(incident.incident_id, self.admin)

        # Reopen with empty reason -> must fail
        with self.assertRaises(ValidationError):
            services.reopen_incident(incident.incident_id, self.admin, "")

        # Valid reopen
        reopened = services.reopen_incident(
            incident.incident_id, self.admin, "New CCTV footage retrieved showing accomplice."
        )
        self.assertEqual(reopened.status, 'REOPENED')

    # --------------------------------------------------------------------------
    # Test 10: Client Shared Incident Redaction (AC-8.44, AC-8.47, AC-8.48)
    # --------------------------------------------------------------------------
    def test_client_shared_version_redaction(self):
        incident, _ = services.create_incident_report(
            company_id=self.company.company_id,
            guard_user=self.guard_user,
            client_generated_id=uuid.uuid4(),
            category_id=self.cat_theft.category_id,
            description="INTERNAL RAW: Guard Ramesh suspected internal cleaner Ravi. Cleaner confessed on site.",
            occurred_at=timezone.now(),
            device_time=timezone.now(),
            suggested_severity='HIGH',
            site_id=self.site_a.site_id
        )

        client_ver = services.create_or_update_client_shared_version(
            incident_id=incident.incident_id,
            actor_user=self.supervisor,
            title="Unauthorized Entry at North Gate",
            summary="An unauthorized person entered via Gate 2 and was escorted out by security.",
            actions_taken="Facility gate lock reinforced and extra guard deployed.",
            status='RESOLVED'
        )

        self.assertEqual(client_ver.title, "Unauthorized Entry at North Gate")
        self.assertNotIn("Ramesh", client_ver.summary)
        self.assertNotIn("INTERNAL RAW", client_ver.summary)
        self.assertEqual(client_ver.sharing_state, 'SHARED')

    # --------------------------------------------------------------------------
    # Test 11: Guard Operational Requests & Cost Approval (AC-8.51, AC-8.54, AC-8.55)
    # --------------------------------------------------------------------------
    def test_guard_operational_requests(self):
        # 1. Non-cost relief request
        req1, created1 = services.create_guard_request(
            company_id=self.company.company_id,
            guard_user=self.guard_user,
            client_generated_id=uuid.uuid4(),
            request_type_id=self.req_type_relief.request_type_id,
            description="Need 1 hour sudden relief due to stomach pain.",
            site_id=self.site_a.site_id
        )
        self.assertTrue(created1)
        self.assertEqual(req1.status, 'SUBMITTED')

        # Supervisor can approve relief
        approved_req1 = services.update_guard_request_status(req1.request_id, self.supervisor, 'APPROVED')
        self.assertEqual(approved_req1.status, 'APPROVED')

        # 2. Cost-related uniform request
        req2, _ = services.create_guard_request(
            company_id=self.company.company_id,
            guard_user=self.guard_user,
            client_generated_id=uuid.uuid4(),
            request_type_id=self.req_type_uniform.request_type_id,
            description="Safety boots torn during duty.",
            site_id=self.site_a.site_id
        )

        # Supervisor approving cost-related request -> must be DENIED
        with self.assertRaises(PermissionDenied):
            services.update_guard_request_status(req2.request_id, self.supervisor, 'APPROVED')

        # Admin approving cost-related request -> SUCCEEDS
        approved_req2 = services.update_guard_request_status(req2.request_id, self.admin, 'APPROVED')
        self.assertEqual(approved_req2.status, 'APPROVED')
        self.assertEqual(approved_req2.admin_approved_by, self.admin)

    # --------------------------------------------------------------------------
    # Test 12: Client Complaints About Named Guard Shielded to Admin Only (AC-8.41)
    # --------------------------------------------------------------------------
    def test_client_ticket_named_guard_isolation(self):
        ticket, created = services.create_client_ticket(
            company_id=self.company.company_id,
            client_user=self.admin,  # Proxy client user
            client_generated_id=uuid.uuid4(),
            site_id=self.site_a.site_id,
            ticket_type='COMPLAINT',
            title='Guard sleeping on duty at night',
            description='Guard was found sleeping at reception desk at 2:00 AM.',
            named_guard_id=self.guard_emp.employee_id
        )

        self.assertTrue(created)
        # Automatically routed to Admin only
        self.assertTrue(ticket.is_admin_only)

    # --------------------------------------------------------------------------
    # Test 13: Module 9 Panic Event Intake (FR-8.18, 12.1)
    # --------------------------------------------------------------------------
    def test_panic_intake_creates_incident(self):
        panic_uuid = uuid.uuid4()
        panic_incident = services.create_incident_from_panic(
            panic_event_id=panic_uuid,
            guard_id=self.guard_emp.employee_id,
            site_id=self.site_a.site_id
        )

        self.assertIsNotNone(panic_incident)
        self.assertEqual(panic_incident.current_severity, 'CRITICAL')
        self.assertEqual(panic_incident.panic_event_reference, panic_uuid)
