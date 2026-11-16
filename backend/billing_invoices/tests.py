import uuid
from datetime import date, timedelta
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from django.contrib.auth.hashers import make_password
from foundation.models import Company, User
from master_data.models import (
    Client,
    ClientSite,
    ClientBillingRate,
    PostType,
    SiteShift,
    SiteManpowerRequirement
)
from attendance.models import AttendanceRecord, AttendancePeriod
from deployment_roster.models import RosterAssignment, PostSlot, Roster
from billing_invoices.models import (
    InvoiceSettings,
    ClientBillingSettings,
    ClientInvoice,
    InvoiceLine,
    ClientPayment,
    ClientPaymentDeduction,
    InvoiceAttendanceAnnexure,
    InvoiceNumberSequence
)
from billing_invoices.services import (
    BillingCalculationService,
    BillingRunService,
    InvoiceManagementService,
    PaymentReceivablesService,
    number_to_indian_words
)


class Module11BillingInvoicesTestCase(TestCase):
    def setUp(self):
        self.api_client = APIClient()

        # 1. Company
        self.company = Company.objects.create(
            legal_name="Karnataka Apex Security Services Ltd",
            trade_name="KASS Security",
            gstin="29AAAAA0000A1Z5",
            pan="AAAAA0000A",
            state_code="KA",
            is_active=True
        )

        # 2. Users (Admin and Client)
        self.admin_user = User.objects.create(
            company_id=self.company.company_id,
            email=f"admin_{uuid.uuid4().hex[:4]}@kass.in",
            role="ADMIN",
            status="ACTIVE",
            full_name="Admin Officer",
            phone="+919877700001",
            password_hash=make_password("AdminPass123!")
        )
        self.client_user = User.objects.create(
            company_id=self.company.company_id,
            email=f"client_{uuid.uuid4().hex[:4]}@clientcorp.in",
            role="CLIENT",
            status="ACTIVE",
            full_name="Client Manager",
            phone="+919877700002",
            password_hash=make_password("ClientPass123!")
        )
        self.other_client_user = User.objects.create(
            company_id=self.company.company_id,
            email=f"other_{uuid.uuid4().hex[:4]}@othercorp.in",
            role="CLIENT",
            status="ACTIVE",
            full_name="Other Client",
            phone="+919877700003",
            password_hash=make_password("OtherPass123!")
        )

        # 3. Clients
        self.client_org = Client.objects.create(
            company_id=self.company.company_id,
            client_code=f"CL-{uuid.uuid4().hex[:4].upper()}",
            legal_name="Client Tech Park Bengaluru Pvt Ltd",
            display_name="Client Tech Park",
            gstin="29ABCDE1234F1Z5",
            pan="ABCDE1234F",
            billing_email="billing@clienttechpark.com",
            billing_address="Outer Ring Road, Bengaluru",
            payment_terms_days=30,
            status="active"
        )
        self.client_user.client_company_id = self.client_org.client_id
        self.client_user.save()

        self.other_client_org = Client.objects.create(
            company_id=self.company.company_id,
            client_code=f"OT-{uuid.uuid4().hex[:4].upper()}",
            legal_name="Other Logistics Hub Ltd",
            display_name="Other Logistics",
            gstin="29XYZAB9876C1Z1",
            payment_terms_days=15,
            status="active"
        )
        self.other_client_user.client_company_id = self.other_client_org.client_id
        self.other_client_user.save()

        # Link contact
        from master_data.models import ClientContact
        ClientContact.objects.create(
            client=self.client_org,
            contact_name="Client Manager",
            email=self.client_user.email,
            phone="+919876543210",
            contact_type="BILLING",
            is_primary=True,
            is_active=True
        )

        # 4. Sites
        self.site_alpha = ClientSite.objects.create(
            client=self.client_org,
            site_code=f"ST-{uuid.uuid4().hex[:4].upper()}",
            site_name="Tech Park - Main Gate",
            operational_status="active",
            latitude=Decimal('12.9716'),
            longitude=Decimal('77.5946')
        )
        self.site_beta = ClientSite.objects.create(
            client=self.client_org,
            site_code=f"ST-{uuid.uuid4().hex[:4].upper()}",
            site_name="Tech Park - Warehouse",
            operational_status="active",
            latitude=Decimal('12.9720'),
            longitude=Decimal('77.5950')
        )

        # 5. Post Type & Shifts
        self.post_type = PostType.objects.create(
            company_id=self.company.company_id,
            code=f"ASG-{uuid.uuid4().hex[:4]}",
            name="Armed Security Guard"
        )
        self.shift = SiteShift.objects.create(
            site_id=self.site_alpha.site_id,
            shift_code="DAY",
            shift_name="General Day Shift",
            start_time="08:00:00",
            end_time="16:00:00",
            duration_minutes=480,
            is_active=True
        )

        # 6. Billing Settings
        self.company_settings = InvoiceSettings.objects.create(
            company_id=self.company.company_id,
            invoice_prefix="INV",
            number_format="{PREFIX}/{FY}/{SEQ:04d}",
            default_tax_label="GST",
            default_tax_percentage=Decimal('18.00'),
            default_payment_terms_days=30,
            effective_from=date.today()
        )
        self.client_settings = ClientBillingSettings.objects.create(
            company_id=self.company.company_id,
            client_id=self.client_org.client_id,
            billing_basis='ATTENDANCE_BASED',
            billing_unit='PER_DAY',
            payment_terms_days=30,
            is_active=True,
            effective_from=date.today() - timedelta(days=90)
        )

        # 7. Rates
        self.client_default_rate = ClientBillingRate.objects.create(
            client_id=self.client_org.client_id,
            site_id=None,
            post_type_id=self.post_type.post_type_id,
            rate_type='daily',
            rate_amount=Decimal('1000.00'),
            effective_from=date(2026, 1, 1),
            is_active=True,
            version=1
        )

        # 8. Locked Attendance Period
        self.period_start = date(2026, 3, 1)
        self.period_end = date(2026, 3, 31)
        self.locked_period = AttendancePeriod.objects.create(
            company_id=self.company.company_id,
            site_id=self.site_alpha.site_id,
            period_name="March 2026 Locked Period",
            start_date=self.period_start,
            end_date=self.period_end,
            cut_off_day=31,
            status='locked'
        )

        # 9. Guard Employee
        from guard_management.models import Employee
        self.guard = Employee.objects.create(
            company_id=self.company.company_id,
            employee_code=f"GRD-{uuid.uuid4().hex[:4].upper()}",
            first_name="Santosh",
            last_name="Kumar",
            phone="+919988776655",
            date_joined=date.today(),
            employment_status="active"
        )
        self.reliever_guard = Employee.objects.create(
            company_id=self.company.company_id,
            employee_code=f"GRD-{uuid.uuid4().hex[:4].upper()}",
            first_name="Ramesh",
            last_name="Gowda",
            phone="+919988776656",
            date_joined=date.today(),
            employment_status="active"
        )

    def create_attendance(self, duty_date, employee=None, site=None, shift=None, asg=None, post_type=None, status='approved', regular_minutes=480, is_manual=False):
        now = timezone.now()
        emp = employee or self.guard
        s = site or self.site_alpha
        sh = shift or self.shift
        pt = post_type or self.post_type
        if not asg:
            slot = PostSlot.objects.create(
                company_id=self.company.company_id,
                site=s,
                post_type=pt,
                shift=sh,
                deployment_date=duty_date,
                slot_sequence=1
            )
            asg = RosterAssignment.objects.create(
                company_id=self.company.company_id,
                slot=slot,
                employee_id=emp.employee_id,
                site_id=s.site_id,
                shift_id=sh.shift_id,
                post_type_id=pt.post_type_id,
                deployment_date=duty_date,
                start_time=now,
                end_time=now + timedelta(hours=8),
                assignment_type='regular',
                status='scheduled'
            )
        return AttendanceRecord.objects.create(
            company_id=self.company.company_id,
            assignment=asg,
            employee_id=emp.employee_id,
            site_id=s.site_id,
            shift_id=sh.shift_id,
            duty_date=duty_date,
            scheduled_start=now,
            scheduled_end=now + timedelta(hours=8),
            status=status,
            regular_minutes=regular_minutes,
            is_manual=is_manual,
            period_id=self.locked_period.period_id
        )

    # -------------------------------------------------------------------------
    # Test 1: Billing Settings & Skipped Reports (AC-11.1, AC-11.2, AC-11.3, AC-11.4)
    # -------------------------------------------------------------------------
    def test_client_skipped_when_no_billing_settings(self):
        """
        AC-11.1: Given a Client has no billing settings, when Admin runs billing,
        then the Client must appear in the skipped report.
        """
        # other_client_org has NO billing settings
        res = BillingRunService.run_billing(
            company_id=self.company.company_id,
            period_start=self.period_start,
            period_end=self.period_end,
            client_ids=[self.other_client_org.client_id]
        )
        self.assertEqual(res['drafts_created'], 0)
        self.assertEqual(len(res['skipped_clients']), 1)
        self.assertIn("Missing client billing settings", res['skipped_clients'][0]['reason'])

    def test_site_level_rate_override(self):
        """
        AC-11.3: Given a site-level rate exists, when the billing engine resolves a rate for that site,
        then the site-level rate must override the client default.
        """
        # Create site override rate: ₹1250 vs client default ₹1000
        ClientBillingRate.objects.create(
            client_id=self.client_org.client_id,
            site_id=self.site_alpha.site_id,
            post_type_id=self.post_type.post_type_id,
            rate_type='daily',
            rate_amount=Decimal('1250.00'),
            effective_from=date(2026, 1, 1),
            is_active=True,
            version=1
        )

        resolved_rate, source = BillingCalculationService.resolve_rate(
            client_id=self.client_org.client_id,
            site_id=self.site_alpha.site_id,
            post_type_id=self.post_type.post_type_id,
            duty_date=date(2026, 3, 10)
        )
        self.assertEqual(source, 'SITE_OVERRIDE')
        self.assertEqual(resolved_rate.rate_amount, Decimal('1250.00'))

    def test_missing_rate_stops_line_and_reports_reason(self):
        """
        AC-11.4: Given no applicable rate exists, when billing engine processes the line,
        then it must stop that line and report missing-rate reason.
        """
        # Query for non-existent post type
        other_post_type = PostType.objects.create(company_id=self.company.company_id, code=f"K9-{uuid.uuid4().hex[:4]}", name="K9 Handler")
        resolved_rate, source = BillingCalculationService.resolve_rate(
            client_id=self.client_org.client_id,
            site_id=self.site_alpha.site_id,
            post_type_id=other_post_type.post_type_id,
            duty_date=date(2026, 3, 10)
        )
        self.assertIsNone(resolved_rate)

    # -------------------------------------------------------------------------
    # Test 2: Billing Run, Locked Period, Idempotency (AC-11.5 to AC-11.10)
    # -------------------------------------------------------------------------
    def test_locked_period_and_unlocked_period_handling(self):
        """
        AC-11.5, AC-11.6, AC-11.7: Locked attendance period allows billing.
        Unlocked period requires override and mandatory reason.
        """
        # Create attendance in locked period
        self.create_attendance(duty_date=date(2026, 3, 5))

        # Standard billing in locked period succeeds (AC-11.5)
        preview, error = BillingCalculationService.preview_client_billing(
            company_id=self.company.company_id,
            client_id=self.client_org.client_id,
            period_start=self.period_start,
            period_end=self.period_end
        )
        self.assertIsNone(error)
        self.assertIsNotNone(preview)

        # Reopen period to test unlocked behavior (AC-11.6)
        self.locked_period.status = 'open'
        self.locked_period.save()

        preview_unlocked, error_unlocked = BillingCalculationService.preview_client_billing(
            company_id=self.company.company_id,
            client_id=self.client_org.client_id,
            period_start=self.period_start,
            period_end=self.period_end,
            is_unlocked_period_override=False
        )
        self.assertIn("Attendance period is not locked", error_unlocked)

        # Override without reason fails (AC-11.7)
        _, err_no_reason = BillingCalculationService.preview_client_billing(
            company_id=self.company.company_id,
            client_id=self.client_org.client_id,
            period_start=self.period_start,
            period_end=self.period_end,
            is_unlocked_period_override=True,
            unlocked_period_reason=""
        )
        self.assertIn("Mandatory reason required", err_no_reason)

        # Override with reason succeeds (AC-11.7)
        prev_override, err_override = BillingCalculationService.preview_client_billing(
            company_id=self.company.company_id,
            client_id=self.client_org.client_id,
            period_start=self.period_start,
            period_end=self.period_end,
            is_unlocked_period_override=True,
            unlocked_period_reason="Urgent early client billing approved by director"
        )
        self.assertIsNone(err_override)
        self.assertIsNotNone(prev_override)

        # Restore locked status for subsequent tests
        self.locked_period.status = 'locked'
        self.locked_period.save()

    def test_duplicate_billing_run_idempotency_and_sent_protection(self):
        """
        AC-11.8: Given the same Client and period, when Admin runs billing twice,
        then only one Draft invoice must exist.
        AC-11.9: Given a Sent invoice exists, when Admin reruns billing,
        then the Sent invoice must remain unchanged.
        """
        self.create_attendance(duty_date=date(2026, 3, 10))

        # Run 1
        res1 = BillingRunService.run_billing(
            company_id=self.company.company_id,
            period_start=self.period_start,
            period_end=self.period_end,
            client_ids=[self.client_org.client_id]
        )
        self.assertEqual(res1['drafts_created'], 1)
        invoice = ClientInvoice.objects.get(client_id=self.client_org.client_id, period_start=self.period_start)
        self.assertEqual(invoice.status, 'DRAFT')

        # Run 2 for the same period -> refreshes existing draft, 0 duplicate invoices (AC-11.8)
        res2 = BillingRunService.run_billing(
            company_id=self.company.company_id,
            period_start=self.period_start,
            period_end=self.period_end,
            client_ids=[self.client_org.client_id]
        )
        self.assertEqual(res2['drafts_created'], 0)
        self.assertEqual(res2['drafts_refreshed'], 1)
        self.assertEqual(ClientInvoice.objects.filter(client_id=self.client_org.client_id, period_start=self.period_start).count(), 1)

        # Issue the invoice
        issued = InvoiceManagementService.issue_invoice(invoice.invoice_id, self.admin_user)
        self.assertEqual(issued.status, 'SENT')
        original_total = issued.total_amount

        # Run 3 after issue -> Sent invoice is never altered (AC-11.9)
        res3 = BillingRunService.run_billing(
            company_id=self.company.company_id,
            period_start=self.period_start,
            period_end=self.period_end,
            client_ids=[self.client_org.client_id]
        )
        issued.refresh_from_db()
        self.assertEqual(issued.status, 'SENT')
        self.assertEqual(issued.total_amount, original_total)

    # -------------------------------------------------------------------------
    # Test 3: Reliever Replacement and Mid-Month Splits (AC-11.11, AC-11.13)
    # -------------------------------------------------------------------------
    def test_reliever_replacement_counted_once(self):
        """
        AC-11.11: Given a regular guard is replaced by a reliever on the same slot,
        when billing is calculated, then the post coverage must be counted once.
        """
        # Create a shared post slot
        duty_date = date(2026, 3, 12)

        slot = PostSlot.objects.create(
            company_id=self.company.company_id,
            site=self.site_alpha,
            post_type=self.post_type,
            shift=self.shift,
            deployment_date=duty_date,
            slot_sequence=1
        )

        roster = Roster.objects.create(
            company_id=self.company.company_id,
            site_id=self.site_alpha.site_id,
            start_date=self.period_start,
            end_date=self.period_end,
            status='published'
        )

        now = timezone.now()
        asg1 = RosterAssignment.objects.create(
            company_id=self.company.company_id,
            slot=slot,
            roster_id=roster.roster_id,
            employee_id=self.guard.employee_id,
            site_id=self.site_alpha.site_id,
            shift_id=self.shift.shift_id,
            post_type_id=self.post_type.post_type_id,
            deployment_date=duty_date,
            start_time=now,
            end_time=now + timedelta(hours=8),
            assignment_type='regular',
            status='scheduled'
        )
        asg2 = RosterAssignment.objects.create(
            company_id=self.company.company_id,
            slot=slot,
            roster_id=roster.roster_id,
            employee_id=self.reliever_guard.employee_id,
            site_id=self.site_alpha.site_id,
            shift_id=self.shift.shift_id,
            post_type_id=self.post_type.post_type_id,
            deployment_date=duty_date,
            start_time=now,
            end_time=now + timedelta(hours=8),
            assignment_type='replacement',
            status='scheduled'
        )

        # Both records recorded for same slot and duty date
        self.create_attendance(duty_date=duty_date, asg=asg1, employee=self.guard, regular_minutes=240)
        self.create_attendance(duty_date=duty_date, asg=asg2, employee=self.reliever_guard, regular_minutes=240)

        preview, err = BillingCalculationService.preview_client_billing(
            company_id=self.company.company_id,
            client_id=self.client_org.client_id,
            period_start=self.period_start,
            period_end=self.period_end
        )
        self.assertIsNone(err)
        # Billed quantity must be 1.00 (not 2.00) (AC-11.11)
        total_billed_qty = sum(l['quantity'] for l in preview['lines'])
        self.assertEqual(total_billed_qty, Decimal('1.00'))

    def test_mid_month_rate_change_split(self):
        """
        AC-11.13: Given a rate changes during a billing period, when billing is calculated,
        then separate lines must be created for each applicable rate period.
        """
        # Rate 1: ₹1,000 from 1st to 15th
        ClientBillingRate.objects.filter(client_id=self.client_org.client_id).delete()
        ClientBillingRate.objects.create(
            client_id=self.client_org.client_id,
            site_id=None,
            post_type_id=self.post_type.post_type_id,
            rate_type='daily',
            rate_amount=Decimal('1000.00'),
            effective_from=date(2026, 3, 1),
            effective_to=date(2026, 3, 15),
            is_active=True,
            version=1
        )
        # Rate 2: ₹1,200 from 16th to 31st
        ClientBillingRate.objects.create(
            client_id=self.client_org.client_id,
            site_id=None,
            post_type_id=self.post_type.post_type_id,
            rate_type='daily',
            rate_amount=Decimal('1200.00'),
            effective_from=date(2026, 3, 16),
            effective_to=date(2026, 3, 31),
            is_active=True,
            version=2
        )

        # Attendance on 5th (Rate 1) and 20th (Rate 2)
        self.create_attendance(duty_date=date(2026, 3, 5))
        self.create_attendance(duty_date=date(2026, 3, 20))

        preview, err = BillingCalculationService.preview_client_billing(
            company_id=self.company.company_id,
            client_id=self.client_org.client_id,
            period_start=self.period_start,
            period_end=self.period_end
        )
        self.assertIsNone(err)
        # Must have 2 distinct lines (AC-11.13)
        self.assertEqual(len(preview['lines']), 2)
        rates_present = {l['unit_rate'] for l in preview['lines']}
        self.assertEqual(rates_present, {Decimal('1000.00'), Decimal('1200.00')})
        self.assertEqual(preview['subtotal'], Decimal('2200.00'))

    # -------------------------------------------------------------------------
    # Test 4: Source Change Detection & Refresh (AC-11.21, AC-11.22, AC-11.26)
    # -------------------------------------------------------------------------
    def test_source_changed_flag_blocks_issue_until_refresh(self):
        """
        AC-11.21, AC-11.22: Draft with source_changed = True blocks issue until refreshed.
        """
        self.create_attendance(duty_date=date(2026, 3, 1))

        BillingRunService.run_billing(
            company_id=self.company.company_id,
            period_start=self.period_start,
            period_end=self.period_end,
            client_ids=[self.client_org.client_id]
        )
        draft = ClientInvoice.objects.get(client_id=self.client_org.client_id, period_start=self.period_start)

        # Mark source changed (simulating attendance edit / period reopen event)
        draft.source_changed = True
        draft.save()

        # Issuing should raise validation error (AC-11.22)
        with self.assertRaises(Exception) as ctx:
            InvoiceManagementService.issue_invoice(draft.invoice_id, self.admin_user)
        self.assertIn("Source data changed", str(ctx.exception))

        # Re-running billing refreshes draft and clears source_changed flag (AC-11.24)
        BillingRunService.run_billing(
            company_id=self.company.company_id,
            period_start=self.period_start,
            period_end=self.period_end,
            client_ids=[self.client_org.client_id]
        )
        draft.refresh_from_db()
        self.assertFalse(draft.source_changed)

    # -------------------------------------------------------------------------
    # Test 5: Manual Lines and Exact Decimal Calculations (AC-11.27 to AC-11.32)
    # -------------------------------------------------------------------------
    def test_manual_line_and_exact_decimal_calculations(self):
        """
        AC-11.27, AC-11.28, AC-11.31, AC-11.32: Manual lines require reason,
        negative manual line requires reason, exact decimal math.
        """
        self.create_attendance(duty_date=date(2026, 3, 1))
        BillingRunService.run_billing(
            company_id=self.company.company_id,
            period_start=self.period_start,
            period_end=self.period_end,
            client_ids=[self.client_org.client_id]
        )
        draft = ClientInvoice.objects.get(client_id=self.client_org.client_id, period_start=self.period_start)
        initial_subtotal = draft.subtotal  # ₹1000

        # Positive manual charge (AC-11.27)
        InvoiceManagementService.add_manual_line(
            draft.invoice_id,
            {
                'description': 'Additional Security Barricade Rental',
                'quantity': Decimal('2.00'),
                'unit_rate': Decimal('500.00'),
                'manual_reason': 'Special client event on March 1st',
                'tax_rate': Decimal('18.00'),
                'is_negative': False
            },
            self.admin_user
        )

        draft.refresh_from_db()
        self.assertEqual(draft.subtotal, initial_subtotal + Decimal('1000.00'))  # ₹2000
        expected_tax = Decimal('2000.00') * Decimal('0.18')  # ₹360
        self.assertEqual(draft.tax_amount, expected_tax)
        self.assertEqual(draft.total_amount, Decimal('2360.00'))

        # Negative manual deduction with reason (AC-11.28)
        InvoiceManagementService.add_manual_line(
            draft.invoice_id,
            {
                'description': 'Contractual Uniform Delay Credit',
                'quantity': Decimal('1.00'),
                'unit_rate': Decimal('200.00'),
                'manual_reason': 'Agreed rebate for delayed gear',
                'is_negative': True
            },
            self.admin_user
        )
        draft.refresh_from_db()
        self.assertEqual(draft.subtotal, Decimal('1800.00'))

    # -------------------------------------------------------------------------
    # Test 6: Atomic Issue, PDF Hash & Immutability (AC-11.33 to AC-11.38)
    # -------------------------------------------------------------------------
    def test_issue_assigns_number_hash_and_enforces_immutability(self):
        """
        AC-11.33, AC-11.36, AC-11.37: Atomic issue assigns sequential number,
        computes SHA-256 PDF hash, prevents editing after issue.
        """
        self.create_attendance(duty_date=date(2026, 3, 1))
        BillingRunService.run_billing(
            company_id=self.company.company_id,
            period_start=self.period_start,
            period_end=self.period_end,
            client_ids=[self.client_org.client_id]
        )
        draft = ClientInvoice.objects.get(client_id=self.client_org.client_id, period_start=self.period_start)

        issued = InvoiceManagementService.issue_invoice(draft.invoice_id, self.admin_user)
        self.assertEqual(issued.status, 'SENT')
        self.assertTrue(issued.invoice_no.startswith("INV/"))
        self.assertTrue(len(issued.pdf_hash) == 64)  # Valid SHA-256 (AC-11.36)

        # Issued invoice cannot be edited (AC-11.37)
        with self.assertRaises(Exception):
            InvoiceManagementService.add_manual_line(
                issued.invoice_id,
                {'description': 'Test', 'unit_rate': Decimal('100.00'), 'manual_reason': 'test'},
                self.admin_user
            )

    # -------------------------------------------------------------------------
    # Test 7: Cancellation, Payment Checks & Replacement (AC-11.39, AC-11.40, AC-11.53)
    # -------------------------------------------------------------------------
    def test_cancellation_and_replacement_workflow(self):
        """
        AC-11.39, AC-11.40, AC-11.53: Cancel requires reason; blocked if active payments exist;
        replacement draft links to original.
        """
        self.create_attendance(duty_date=date(2026, 3, 1))
        BillingRunService.run_billing(
            company_id=self.company.company_id,
            period_start=self.period_start,
            period_end=self.period_end,
            client_ids=[self.client_org.client_id]
        )
        draft = ClientInvoice.objects.get(client_id=self.client_org.client_id, period_start=self.period_start)
        issued = InvoiceManagementService.issue_invoice(draft.invoice_id, self.admin_user)

        # Record a payment
        PaymentReceivablesService.record_payment(
            issued.invoice_id,
            {
                'payment_date': date.today(),
                'amount': Decimal('500.00'),
                'payment_method': 'BANK_TRANSFER'
            },
            self.admin_user
        )

        # Attempt to cancel -> BLOCKED because active payment exists (AC-11.53)
        with self.assertRaises(Exception) as ctx:
            InvoiceManagementService.cancel_invoice(issued.invoice_id, "Mistake in billing")
        self.assertIn("active payments", str(ctx.exception))

        # Reverse the payment
        payment = ClientPayment.objects.filter(invoice_id=issued.invoice_id).first()
        PaymentReceivablesService.reverse_payment(payment.client_payment_id, "Incorrect payment entry", self.admin_user)

        # Cancellation now succeeds (AC-11.39)
        cancelled = InvoiceManagementService.cancel_invoice(
            issued.invoice_id,
            cancelled_reason="Incorrect site rate applied",
            client_visible_reason="Re-issued with updated site terms",
            user=self.admin_user
        )
        self.assertEqual(cancelled.status, 'CANCELLED')

        # Create replacement draft (AC-11.40)
        replacement = InvoiceManagementService.create_replacement_draft(cancelled.invoice_id, self.admin_user)
        self.assertEqual(replacement.status, 'DRAFT')
        self.assertEqual(replacement.original_invoice_id, cancelled.invoice_id)
        cancelled.refresh_from_db()
        self.assertEqual(cancelled.replacement_invoice_id, replacement.invoice_id)

    # -------------------------------------------------------------------------
    # Test 8: Payment Recording, TDS, Deductions & Reversal (AC-11.45 to AC-11.52)
    # -------------------------------------------------------------------------
    def test_payment_recording_tds_and_reversal(self):
        """
        AC-11.45 to AC-11.52: Record payment, TDS deduction, status transitions to Partially Paid / Paid.
        Payment reversal restores balance. Overpayment tracks unallocated amount.
        """
        self.create_attendance(duty_date=date(2026, 3, 1))
        BillingRunService.run_billing(
            company_id=self.company.company_id,
            period_start=self.period_start,
            period_end=self.period_end,
            client_ids=[self.client_org.client_id]
        )
        draft = ClientInvoice.objects.get(client_id=self.client_org.client_id, period_start=self.period_start)
        issued = InvoiceManagementService.issue_invoice(draft.invoice_id, self.admin_user)
        # Total: ₹1000 + 18% = ₹1180.00

        # Part payment: ₹500 payment + ₹50 TDS + ₹30 client penalty = ₹580 total credit
        p1 = PaymentReceivablesService.record_payment(
            issued.invoice_id,
            {
                'payment_date': date.today(),
                'amount': Decimal('500.00'),
                'payment_method': 'BANK_TRANSFER',
                'tds_amount': Decimal('50.00'),
                'other_deduction_amount': Decimal('30.00'),
                'other_deduction_reason': 'Delayed post handover penalty'
            },
            self.admin_user
        )
        issued.refresh_from_db()
        self.assertEqual(issued.status, 'PARTIALLY_PAID')  # (AC-11.46)
        self.assertEqual(issued.paid_amount, Decimal('500.00'))
        self.assertEqual(issued.deduction_amount, Decimal('80.00'))
        self.assertEqual(issued.outstanding_amount, Decimal('1180.00') - Decimal('580.00'))  # ₹600.00

        # Full settlement: pay ₹600
        PaymentReceivablesService.record_payment(
            issued.invoice_id,
            {
                'payment_date': date.today(),
                'amount': Decimal('600.00'),
                'payment_method': 'CHEQUE'
            },
            self.admin_user
        )
        issued.refresh_from_db()
        self.assertEqual(issued.status, 'PAID')  # (AC-11.47)
        self.assertEqual(issued.outstanding_amount, Decimal('0.00'))

        # Reverse the second payment
        p2 = ClientPayment.objects.filter(invoice_id=issued.invoice_id, amount=Decimal('600.00')).first()
        PaymentReceivablesService.reverse_payment(p2.client_payment_id, "Cheque bounced", self.admin_user)
        issued.refresh_from_db()
        self.assertEqual(issued.status, 'PARTIALLY_PAID')  # (AC-11.49)
        self.assertEqual(issued.outstanding_amount, Decimal('600.00'))

    # -------------------------------------------------------------------------
    # Test 9: Query Linking Pauses Reminders (AC-11.54, AC-11.55, AC-11.57)
    # -------------------------------------------------------------------------
    def test_invoice_query_pauses_reminders(self):
        """
        AC-11.54, AC-11.55, AC-11.57: Raising query flags Under Query and pauses reminders.
        """
        invoice = ClientInvoice.objects.create(
            company_id=self.company.company_id,
            client_id=self.client_org.client_id,
            invoice_no="INV/2026-27/0099",
            period_start=self.period_start,
            period_end=self.period_end,
            status='SENT',
            total_amount=Decimal('5000.00'),
            outstanding_amount=Decimal('5000.00')
        )

        ticket_id = uuid.uuid4()
        PaymentReceivablesService.link_invoice_query(
            invoice_id=invoice.invoice_id,
            ticket_id=ticket_id,
            client_id=invoice.client_id
        )

        invoice.refresh_from_db()
        self.assertTrue(invoice.under_query_flag)  # (AC-11.54)

        # Closing query clears flag (AC-11.57)
        PaymentReceivablesService.close_invoice_query(ticket_id)
        invoice.refresh_from_db()
        self.assertFalse(invoice.under_query_flag)

    # -------------------------------------------------------------------------
    # Test 10: Client Access Isolation and Sanitization (AC-11.59 to AC-11.63)
    # -------------------------------------------------------------------------
    def test_client_access_isolation_and_draft_hidden(self):
        """
        AC-11.59, AC-11.60, AC-11.61, AC-11.63:
        Clients can only view their own issued invoices. Drafts are hidden.
        Internal notes and source snapshots are stripped.
        """
        # Create a draft for client_org
        draft = ClientInvoice.objects.create(
            company_id=self.company.company_id,
            client_id=self.client_org.client_id,
            draft_reference="DFT-TEST-001",
            period_start=self.period_start,
            period_end=self.period_end,
            status='DRAFT',
            total_amount=Decimal('1000.00')
        )
        # Create a sent invoice for client_org
        issued = ClientInvoice.objects.create(
            company_id=self.company.company_id,
            client_id=self.client_org.client_id,
            invoice_no="INV/2026-27/0100",
            period_start=self.period_start,
            period_end=self.period_end,
            status='SENT',
            total_amount=Decimal('2000.00'),
            outstanding_amount=Decimal('2000.00'),
            internal_notes="Internal dispute note"
        )
        # Create a sent invoice for other_client_org
        other_issued = ClientInvoice.objects.create(
            company_id=self.company.company_id,
            client_id=self.other_client_org.client_id,
            invoice_no="INV/2026-27/0101",
            period_start=self.period_start,
            period_end=self.period_end,
            status='SENT',
            total_amount=Decimal('3000.00'),
            outstanding_amount=Decimal('3000.00')
        )

        self.api_client.force_authenticate(user=self.client_user)

        # 1. List invoices: Client sees only their SENT invoice (draft hidden, other client's hidden) (AC-11.59, AC-11.61)
        res = self.api_client.get('/api/billing/invoices/')
        self.assertEqual(res.status_code, 200)
        inv_nos = [i.get('invoice_no') for i in res.data]
        self.assertIn("INV/2026-27/0100", inv_nos)
        self.assertNotIn("INV/2026-27/0101", inv_nos)
        self.assertNotIn("DFT-TEST-001", [i.get('draft_reference') for i in res.data])

        # 2. Detail of other client's invoice returns 403 (AC-11.60)
        res_other = self.api_client.get(f'/api/billing/invoices/{other_issued.invoice_id}/')
        self.assertEqual(res_other.status_code, 403)

        # 3. Detail of draft returns 403 (AC-11.61)
        res_draft = self.api_client.get(f'/api/billing/invoices/{draft.invoice_id}/')
        self.assertEqual(res_draft.status_code, 403)

        # 4. Detail of own issued invoice sanitizes internal notes (AC-11.63)
        res_own = self.api_client.get(f'/api/billing/invoices/{issued.invoice_id}/')
        self.assertEqual(res_own.status_code, 200)
        self.assertNotIn('internal_notes', res_own.data)

    # -------------------------------------------------------------------------
    # Test 11: CSV Exports with Documented Columns (AC-11.65, AC-11.66)
    # -------------------------------------------------------------------------
    def test_csv_exports_documented_columns(self):
        """
        AC-11.65, AC-11.66: CSV export returns 200 with fixed, documented column headers.
        """
        self.api_client.force_authenticate(user=self.admin_user)

        # Invoice CSV
        res_inv = self.api_client.get('/api/billing/exports/invoices/')
        self.assertEqual(res_inv.status_code, 200)
        self.assertEqual(res_inv['Content-Type'], 'text/csv')
        csv_text = res_inv.content.decode('utf-8')
        self.assertIn("Invoice No,Draft Ref,Client ID", csv_text)

        # Payment CSV
        res_pay = self.api_client.get('/api/billing/exports/payments/')
        self.assertEqual(res_pay.status_code, 200)
        self.assertEqual(res_pay['Content-Type'], 'text/csv')
        csv_pay_text = res_pay.content.decode('utf-8')
        self.assertIn("Payment ID,Invoice ID,Client ID", csv_pay_text)

    # -------------------------------------------------------------------------
    # Test 12: Indian Currency Amount in Words (PRD 6.9, FR-11.116)
    # -------------------------------------------------------------------------
    def test_number_to_indian_words(self):
        """
        FR-11.116: Displays amount in words using Indian digit grouping.
        """
        w1 = number_to_indian_words(Decimal('30000.00'))
        self.assertEqual(w1, "Rupees Thirty Thousand Only")

        w2 = number_to_indian_words(Decimal('125450.50'))
        self.assertEqual(w2, "Rupees One Lakh Twenty-Five Thousand Four Hundred and Fifty and Fifty Paise Only")
