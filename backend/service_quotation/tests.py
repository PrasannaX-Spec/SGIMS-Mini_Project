import uuid
from decimal import Decimal
from datetime import date, timedelta
from django.test import TestCase, Client as HttpClient
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from foundation.models import User
from django.contrib.auth.hashers import make_password
from master_data.models import Company, Client as ClientModel, ClientSite, PostType, SiteShift, ServiceAgreement, ClientBillingRate, SiteManpowerRequirement
from service_quotation.models import (
    ServiceRequest,
    ServiceRequestLine,
    Quotation,
    QuotationVersion,
    QuotationLine,
    QuotationAcceptance,
    QuotationCounter,
    QuotationConversion,
)
from service_quotation import services


class ServiceQuotationTests(TestCase):
    def setUp(self):
        # Create test company
        self.company = Company.objects.create(
            legal_name='Apex Security Karnataka Ltd',
            trade_name='Apex Security',
            pan='ABCDE1234F',
            gstin='29ABCDE1234F1Z5',
            state_code='KA',
            is_active=True
        )

        # Create admin user
        self.admin_user = User.objects.create(
            company_id=self.company.company_id,
            email='admin@apexsecurity.com',
            full_name='Apex Admin',
            role='ADMIN',
            phone='+919888800001',
            password_hash=make_password('TestPass123!'),
            status='ACTIVE'
        )

        # Create client company
        self.client_company = ClientModel.objects.create(
            company=self.company,
            legal_name='Infosys Limited Bangalore Campus',
            client_code='INF-BLR',
            status='active'
        )

        # Create client user
        self.client_user = User.objects.create(
            company_id=self.company.company_id,
            client_company_id=self.client_company.client_id,
            email='procurement@infosys.com',
            full_name='Infosys Manager',
            role='CLIENT',
            phone='+919888800002',
            password_hash=make_password('ClientPass123!'),
            status='ACTIVE'
        )

        # Create Post types
        self.post_unarmed = PostType.objects.create(
            post_type_id=uuid.uuid4(),
            company=self.company,
            code='GEN_GUARD',
            name='General Security Guard',
            requires_armed_authorization=False
        )
        self.post_armed = PostType.objects.create(
            post_type_id=uuid.uuid4(),
            company=self.company,
            code='ARMED_GUARD',
            name='Armed Security Guard',
            requires_armed_authorization=True
        )

        self.http_client = HttpClient()

    def test_ac01_and_ac08_create_service_request_with_armed_defaulting(self):
        """
        AC-01: Service request creation with manpower lines.
        AC-08: Post type is_armed defaults armed_required on lines.
        """
        req_data = {
            'service_purpose': 'office',
            'start_date': str(date.today() + timedelta(days=7)),
            'duration_type': 'ongoing',
            'site_contact_name': 'Ramesh Kumar',
            'site_contact_phone': '+919876543210',
            'new_site_name': 'Infosys Electronics City Gate 3',
            'new_site_address': 'Electronic City Phase 1, Bangalore',
            'lines': [
                {
                    'post_type_id': str(self.post_unarmed.post_type_id),
                    'guard_count': 4,
                    'shift_information': 'Day Shift 8hr',
                    'hours_per_day': 8.0,
                    'working_days': ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'],
                },
                {
                    'post_type_id': str(self.post_armed.post_type_id),
                    'guard_count': 1,
                    'shift_information': 'Night Shift 12hr',
                    'hours_per_day': 12.0,
                    'working_days': ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'],
                }
            ]
        }

        req_obj = services.create_service_request(
            client_id=self.client_company.client_id,
            data=req_data,
            actor_user=self.client_user
        )

        self.assertIsNotNone(req_obj.request_id)
        self.assertTrue(req_obj.request_reference.startswith('SR-'))
        self.assertEqual(req_obj.status, 'submitted')
        lines = list(req_obj.lines.all().order_by('guard_count'))
        self.assertEqual(len(lines), 2)
        # Verify armed defaulting
        armed_line = [l for l in lines if l.post_type_id == self.post_armed.post_type_id][0]
        unarmed_line = [l for l in lines if l.post_type_id == self.post_unarmed.post_type_id][0]
        self.assertTrue(armed_line.armed_required)
        self.assertFalse(unarmed_line.armed_required)

    def test_ac11_ac12_idempotent_duplicate_request_prevention(self):
        """
        AC-11 & AC-12: Duplicate requests with same submission_reference return existing request.
        """
        req_data = {
            'submission_reference': 'SUB-APP-MOBILE-TEST-12345',
            'service_purpose': 'event',
            'start_date': str(date.today() + timedelta(days=5)),
            'site_contact_name': 'Suresh Babu',
            'site_contact_phone': '+919999988888',
            'new_site_name': 'Annual Tech Symposium',
            'lines': [
                {
                    'post_type_id': str(self.post_unarmed.post_type_id),
                    'guard_count': 2,
                    'shift_information': '8hr',
                    'hours_per_day': 8.0,
                    'working_days': ['MON'],
                }
            ]
        }

        req1 = services.create_service_request(self.client_company.client_id, req_data, self.client_user)
        req2 = services.create_service_request(self.client_company.client_id, req_data, self.client_user)

        self.assertEqual(req1.request_id, req2.request_id)
        self.assertEqual(ServiceRequest.objects.filter(submission_reference='SUB-APP-MOBILE-TEST-12345').count(), 1)

    def test_ac14_clarification_and_ac15_withdrawal(self):
        """
        AC-14: Admin clarification moves status to awaiting_client.
        AC-15: Client withdrawal cancels unaccepted request.
        """
        req_data = {
            'service_purpose': 'office',
            'start_date': str(date.today() + timedelta(days=10)),
            'site_contact_name': 'Meera Sen',
            'site_contact_phone': '+919777766666',
            'new_site_name': 'Whitefield Annex',
            'lines': [
                {
                    'post_type_id': str(self.post_unarmed.post_type_id),
                    'guard_count': 1,
                    'shift_information': 'General',
                    'hours_per_day': 8.0,
                    'working_days': ['MON'],
                }
            ]
        }
        req_obj = services.create_service_request(self.client_company.client_id, req_data, self.client_user)

        # Clarification
        comment = services.request_service_clarification(
            req_obj.request_id,
            "Please confirm if parking area needs coverage.",
            self.admin_user
        )
        req_obj.refresh_from_db()
        self.assertEqual(req_obj.status, 'awaiting_client')
        self.assertTrue(comment.is_clarification_request)

        # Withdrawal
        withdrawn_req = services.withdraw_service_request(req_obj.request_id, self.client_user)
        self.assertEqual(withdrawn_req.status, 'withdrawn')

    def test_ac16_to_ac30_quotation_lifecycle_counters_and_acceptance(self):
        """
        AC-16 to AC-30:
        - Manual rate entry (NUMERIC 14,2)
        - Send quotation (becomes immutable)
        - Client counter proposal with round tracking (max 3 rounds)
        - Quotation revision incrementing version
        - Click-to-accept with IP and device metadata
        """
        # Create request first
        req_data = {
            'service_purpose': 'office',
            'start_date': str(date.today() + timedelta(days=14)),
            'site_contact_name': 'Vijay Patil',
            'site_contact_phone': '+919555544444',
            'new_site_name': 'Apex Tech Park Tower A',
            'new_site_address': 'Outer Ring Road, Bellandur, Bangalore',
            'new_site_latitude': 12.9279,
            'new_site_longitude': 77.6771,
            'lines': [
                {
                    'post_type_id': str(self.post_unarmed.post_type_id),
                    'guard_count': 3,
                    'shift_information': '8hr Shift',
                    'hours_per_day': 8.0,
                    'working_days': ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'],
                }
            ]
        }
        req_obj = services.create_service_request(self.client_company.client_id, req_data, self.client_user)

        # Create Quotation V1
        q_data = {
            'quotation_date': str(date.today()),
            'validity_days': 15,
            'payment_terms': 'Net 30 days',
            'tax_note': 'Applicable taxes extra',
            'internal_notes': 'Strictly confidential margin note',
            'lines': [
                {
                    'post_type_id': str(self.post_unarmed.post_type_id),
                    'shift_hours': 8.0,
                    'headcount': 3,
                    'billing_unit': 'per_guard_per_month',
                    'unit_rate': 28500.00,
                    'line_total': 85500.00,
                }
            ]
        }
        quotation, v1 = services.create_quotation(req_obj.request_id, q_data, self.admin_user)
        self.assertEqual(quotation.current_version, 1)
        self.assertEqual(v1.status, 'draft')
        self.assertEqual(Decimal(str(v1.subtotal)), Decimal('85500.00'))

        # Send Quotation V1
        v1_sent = services.send_quotation(v1.quotation_version_id, self.admin_user)
        self.assertEqual(v1_sent.status, 'sent')

        # Client Counter-proposes (Round 1)
        counter1 = services.counter_quotation(
            v1.quotation_version_id,
            comment="Can we do ₹26,000 per guard for 3 guards?",
            proposed_data={'proposed_rate': 26000.00, 'proposed_guard_count': 3},
            actor_user=self.client_user
        )
        self.assertEqual(counter1.negotiation_round, 1)
        req_obj.refresh_from_db()
        self.assertEqual(req_obj.status, 'countered')

        # Admin revises to Quotation V2
        q2_data = {
            'lines': [
                {
                    'post_type_id': str(self.post_unarmed.post_type_id),
                    'shift_hours': 8.0,
                    'headcount': 3,
                    'billing_unit': 'per_guard_per_month',
                    'unit_rate': 27000.00,
                    'line_total': 81000.00,
                }
            ],
            'payment_terms': 'Net 15 days',
            'tax_note': 'Applicable taxes extra',
        }
        v2 = services.revise_quotation(quotation.quotation_id, q2_data, self.admin_user)
        self.assertEqual(v2.version_number, 2)
        v1.refresh_from_db()
        self.assertEqual(v1.status, 'superseded')

        # Send V2
        v2_sent = services.send_quotation(v2.quotation_version_id, self.admin_user)
        self.assertEqual(v2_sent.status, 'sent')

        # Test acceptance requires confirmation checkbox
        with self.assertRaises((ValueError, ValidationError)):
            services.accept_quotation(v2.quotation_version_id, False, self.client_user)

        # Client accepts V2
        class MockReq:
            headers = {}
            META = {'REMOTE_ADDR': '192.168.1.100', 'HTTP_USER_AGENT': 'Mozilla/5.0 Chrome/120'}
        accepted_version = services.accept_quotation(
            v2.quotation_version_id,
            confirmation_checked=True,
            actor_user=self.client_user,
            request=MockReq()
        )
        self.assertEqual(accepted_version.status, 'accepted')
        acceptance = accepted_version.acceptances.first()
        self.assertIsNotNone(acceptance)
        self.assertEqual(acceptance.ip_address, '192.168.1.100')
        self.assertTrue(acceptance.confirmation_value)

        # AC-31 to AC-36: Conversion to Module 2 Draft Master Records
        conversion = services.create_draft_setup_from_accepted_quote(
            v2.quotation_version_id,
            actor_user=self.admin_user
        )
        self.assertEqual(conversion.conversion_status, 'completed')
        self.assertIsNotNone(conversion.module2_site_id)
        self.assertIsNotNone(conversion.module2_agreement_id)

        # Verify created Module 2 draft site
        draft_site = ClientSite.objects.get(site_id=conversion.module2_site_id)
        self.assertEqual(draft_site.site_name, 'Apex Tech Park Tower A')
        self.assertEqual(draft_site.operational_status, 'planned')  # Must remain planned until admin activates

        # Verify draft agreement
        draft_agreement = ServiceAgreement.objects.get(agreement_id=conversion.module2_agreement_id)
        self.assertTrue(draft_agreement.is_active)

        # Verify billing rate record
        rates = ClientBillingRate.objects.filter(site=draft_site)
        self.assertEqual(rates.count(), 1)
        self.assertEqual(Decimal(str(rates[0].rate_amount)), Decimal('27000.00'))

        # Verify manpower requirement record
        reqs = SiteManpowerRequirement.objects.filter(site=draft_site)
        self.assertEqual(reqs.count(), 1)
        self.assertEqual(reqs[0].required_count, 3)

        # Safe retry conversion returns existing conversion without duplicates
        retry_conv = services.create_draft_setup_from_accepted_quote(v2.quotation_version_id, self.admin_user)
        self.assertEqual(retry_conv.conversion_id, conversion.conversion_id)
        self.assertEqual(ClientSite.objects.filter(site_name='Apex Tech Park Tower A').count(), 1)
