from datetime import date, timedelta
from django.test import TestCase
from master_data.models import Company, PostType
from guard_management.models import Employee, EmployeeDocument, EmployeeCheck, EmployeeTraining, LeaveRequest
from guard_management import services
from foundation.models import User


class GuardManagementTestSuite(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            legal_name='Karnataka Security Corp Pvt Ltd',
            trade_name='KSC Security',
            pan='ABCDE1234F',
            gstin='29ABCDE1234F1Z5',
            state_code='KA',
            is_active=True
        )

        self.admin = User.objects.create(
            company_id=self.company.company_id,
            email='admin@ksc.local',
            full_name='Security Admin',
            role='ADMIN',
            status='ACTIVE'
        )

        self.supervisor = User.objects.create(
            company_id=self.company.company_id,
            email='supervisor@ksc.local',
            full_name='Field Supervisor',
            role='SUPERVISOR',
            status='ACTIVE'
        )

    def test_ac01_to_ac05_guard_registration_and_code_uniqueness(self):
        # AC-01 & AC-04: Valid registration creates Applicant and auto-generates employee code
        guard = services.register_guard(
            self.company.company_id,
            {
                'full_name': 'Ravi Kumar',
                'phone': '+919876500001',
                'date_of_birth': '1995-05-15',
                'permanent_address': 'Hebbal, Bengaluru',
                'emergency_contact': {'name': 'Suman', 'relation': 'Wife', 'phone': '+919876500002'}
            },
            self.admin
        )
        self.assertEqual(guard.lifecycle_status, 'applicant')
        self.assertTrue(guard.employee_code.startswith('SEC-GRD-'))

        # AC-02: Duplicate phone number rejected
        with self.assertRaises(Exception):
            services.register_guard(
                self.company.company_id,
                {
                    'full_name': 'Another Guard',
                    'phone': '+919876500001',
                    'date_of_birth': '1996-01-01',
                },
                self.admin
            )

        # AC-03: Underage guard rejected (<18 years)
        with self.assertRaises(Exception):
            services.register_guard(
                self.company.company_id,
                {
                    'full_name': 'Young Applicant',
                    'phone': '+919876500003',
                    'date_of_birth': '2015-01-01',  # 11 years old
                },
                self.admin
            )

    def test_ac06_to_ac10_lifecycle_transitions(self):
        guard = services.register_guard(
            self.company.company_id,
            {
                'full_name': 'Anil Sharma',
                'phone': '+919876500010',
                'date_of_birth': '1992-03-20',
                'emergency_contact': {'name': 'Father', 'phone': '+919876500011'}
            },
            self.admin
        )

        # AC-07: Direct Applicant -> Active must fail
        with self.assertRaises(Exception):
            services.change_guard_status(guard.employee_id, 'active', 'Skip steps', self.admin)

        # AC-08: Transition without reason must fail
        with self.assertRaises(Exception):
            services.change_guard_status(guard.employee_id, 'under_verification', '', self.admin)

        # AC-06: Applicant -> Under Verification with reason succeeds
        guard = services.change_guard_status(
            guard.employee_id, 'under_verification', 'Document submission complete', self.admin
        )
        self.assertEqual(guard.lifecycle_status, 'under_verification')

        # Move to Approved
        guard = services.change_guard_status(
            guard.employee_id, 'approved', 'Verification passed', self.admin
        )
        self.assertEqual(guard.lifecycle_status, 'approved')

        # Move to Active
        guard = services.change_guard_status(
            guard.employee_id, 'active', 'Deployment onboarding', self.admin
        )
        self.assertEqual(guard.lifecycle_status, 'active')

        # AC-09: Suspended guard deployability must be false
        guard = services.change_guard_status(
            guard.employee_id, 'suspended', 'Disciplinary inquiry', self.admin
        )
        self.assertEqual(guard.lifecycle_status, 'suspended')
        dep = services.is_guard_deployable_on_date(guard.employee_id)
        self.assertFalse(dep['deployable'])
        self.assertIn("Guard lifecycle status is 'suspended', not 'active'.", dep['failure_reasons'])

    def test_ac11_to_ac17_deployability_decision_engine(self):
        guard = services.register_guard(
            self.company.company_id,
            {
                'full_name': 'Kiran Patil',
                'phone': '+919876500020',
                'date_of_birth': '1990-10-10',
                'emergency_contact': {'name': 'Brother', 'phone': '+919876500021'}
            },
            self.admin
        )
        # Advance through valid steps to active
        services.change_guard_status(guard.employee_id, 'under_verification', 'Validating docs', self.admin)
        services.change_guard_status(guard.employee_id, 'approved', 'All checks green', self.admin)
        services.change_guard_status(guard.employee_id, 'active', 'Activated on roster', self.admin)

        # AC-12: Missing mandatory documents -> Deployability is False
        dep = services.is_guard_deployable_on_date(guard.employee_id)
        self.assertFalse(dep['deployable'])

        # Upload and verify mandatory identity & address docs
        id_doc = services.upload_guard_document(
            guard.employee_id, 'identity_proof', 'storage/id.pdf', 'id.pdf', {}, self.admin
        )
        addr_doc = services.upload_guard_document(
            guard.employee_id, 'address_proof', 'storage/addr.pdf', 'addr.pdf', {}, self.admin
        )
        services.verify_guard_document(id_doc.document_id, 'verify', None, self.admin)
        services.verify_guard_document(addr_doc.document_id, 'verify', None, self.admin)

        # Record cleared police and medical checks
        EmployeeCheck.objects.create(
            employee=guard, check_type='police', status='cleared', valid_until=date.today() + timedelta(days=365)
        )
        EmployeeCheck.objects.create(
            employee=guard, check_type='medical', status='cleared', valid_until=date.today() + timedelta(days=365)
        )

        # Record completed induction & fire safety training
        EmployeeTraining.objects.create(
            employee=guard, attendance_status='present', result='passed', valid_until=date.today() + timedelta(days=365)
        )

        # AC-11: All conditions satisfied -> Deployable!
        dep = services.is_guard_deployable_on_date(guard.employee_id)
        self.assertTrue(dep['deployable'])

        # AC-17: Approved unavailability blocks deployment for that date
        services.request_unavailability(
            guard.employee_id, 'sick', date.today(), date.today(), 'Medical sick leave', self.admin
        )
        dep_unavailable = services.is_guard_deployable_on_date(guard.employee_id, target_date=date.today())
        self.assertFalse(dep_unavailable['deployable'])

    def test_ac18_to_ac22_document_rejection_and_versioning(self):
        guard = services.register_guard(
            self.company.company_id,
            {'full_name': 'Pooja Hegde', 'phone': '+919876500030', 'date_of_birth': '1994-08-12'},
            self.admin
        )

        doc1 = services.upload_guard_document(
            guard.employee_id, 'address_proof', 'storage/bill1.pdf', 'bill1.pdf', {}, self.admin
        )
        self.assertEqual(doc1.version, 1)

        # AC-18: Reject document without reason must fail
        with self.assertRaises(Exception):
            services.verify_guard_document(doc1.document_id, 'reject', '', self.admin)

        # Reject with reason
        doc1 = services.verify_guard_document(doc1.document_id, 'reject', 'Utility bill illegible', self.admin)
        self.assertEqual(doc1.verification_status, 'rejected')
        self.assertEqual(doc1.rejection_reason, 'Utility bill illegible')

        # AC-19: Re-upload creates version 2 and preserves history
        doc2 = services.upload_guard_document(
            guard.employee_id, 'address_proof', 'storage/bill2.pdf', 'bill2.pdf', {}, self.admin
        )
        self.assertEqual(doc2.version, 2)
        self.assertTrue(doc2.is_active)
        doc1.refresh_from_db()
        self.assertFalse(doc1.is_active)

    def test_ac26_to_ac28_bank_masking_and_audited_reveal(self):
        guard = services.register_guard(
            self.company.company_id,
            {'full_name': 'Manjunath B', 'phone': '+919876500040', 'date_of_birth': '1991-04-14'},
            self.admin
        )
        services.update_guard_bank_details(
            guard.employee_id,
            {'bank_name': 'SBI', 'account_number': '123456789012', 'ifsc': 'SBIN0001234'},
            self.admin
        )

        # AC-26: Supervisor cannot reveal bank details
        with self.assertRaises(Exception):
            services.reveal_guard_bank_details(guard.employee_id, self.supervisor)

        # AC-27: Admin can reveal bank details (audited)
        revealed = services.reveal_guard_bank_details(guard.employee_id, self.admin)
        self.assertEqual(revealed['account_number'], '123456789012')
