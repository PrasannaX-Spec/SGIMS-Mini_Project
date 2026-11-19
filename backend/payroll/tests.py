import uuid
from decimal import Decimal
from datetime import date, timedelta
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from foundation.models import User, Company
from guard_management.models import Employee
from attendance.models import AttendancePeriod, AttendanceRecord
from master_data.models import Client, ClientSite, SiteShift
from .models import (
    SalaryComponent, SalaryStructure, SalaryStructureLine,
    GuardSalaryAssignment, MinimumWage, PaidDayRuleSet,
    StatutoryRuleSet, Advance, AdvanceLedgerEntry,
    ManualDeduction, PayrollRun, PayrollResult,
    PayrollResultLine, Payslip, PaymentRecord,
    FinalSettlement, StatutoryPayment
)
from .services import (
    calculate_payroll_run, approve_payroll_run, release_payroll_run,
    record_payment, reverse_payment, get_pre_run_checklist
)


class PayrollModuleTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.company = Company.objects.create(
            legal_name="Test Karnataka Security Services",
            trade_name="Test KSS",
            is_active=True
        )
        self.company_id = self.company.company_id

        # Preparer Admin
        self.admin_preparer = User.objects.create(
            email="preparer@testsecurity.local",
            full_name="Preparer Officer",
            company_id=self.company_id,
            role="ADMIN",
            status="ACTIVE"
        )
        self.preparer_id = self.admin_preparer.user_id

        # Approver Admin (Segregation of Duties)
        self.admin_approver = User.objects.create(
            email="approver@testsecurity.local",
            full_name="Approver Officer",
            company_id=self.company_id,
            role="ADMIN",
            status="ACTIVE"
        )
        self.approver_id = self.admin_approver.user_id

        # Guard User & Employee
        self.guard_user = User.objects.create(
            email="guard@testsecurity.local",
            full_name="Ramesh Kumar",
            company_id=self.company_id,
            role="GUARD",
            status="ACTIVE"
        )
        self.guard_user_id = self.guard_user.user_id

        self.employee = Employee.objects.create(
            employee_id=self.guard_user_id,
            company_id=self.company_id,
            employee_code="SEC-001",
            first_name="Ramesh",
            last_name="Kumar",
            date_joined=date(2026, 1, 1),
            employment_status="active",
            lifecycle_status="active",
            pan_number="ABCDE1234F",
            uan_number="100123456789",
            bank_details={"account_number": "1234567890", "ifsc": "SBIN0001234"}
        )

        # Second Guard
        self.guard2_user = User.objects.create(
            email="guard2@testsecurity.local",
            full_name="Suresh Patil",
            company_id=self.company_id,
            role="GUARD",
            status="ACTIVE"
        )
        self.guard2_id = self.guard2_user.user_id
        self.employee2 = Employee.objects.create(
            employee_id=self.guard2_id,
            company_id=self.company_id,
            employee_code="SEC-002",
            first_name="Suresh",
            last_name="Patil",
            date_joined=date(2026, 1, 1),
            employment_status="active",
            lifecycle_status="active"
        )

        # Supervisor
        self.supervisor_user = User.objects.create(
            email="sup@testsecurity.local",
            full_name="Field Supervisor",
            company_id=self.company_id,
            role="SUPERVISOR",
            status="ACTIVE"
        )
        self.supervisor_id = self.supervisor_user.user_id

        # Client
        self.client_user = User.objects.create(
            email="client@testsecurity.local",
            full_name="Client Rep",
            company_id=self.company_id,
            role="CLIENT",
            status="ACTIVE"
        )
        self.client_user_id = self.client_user.user_id

        # Client & Site
        self.client_org = Client.objects.create(
            company_id=self.company_id,
            client_code="CLI-001",
            legal_name="Test Client Corp",
            display_name="Client Corp",
            status="active"
        )
        self.site_a = ClientSite.objects.create(
            client_id=self.client_org.client_id,
            site_code="SITE-001",
            site_name="Bangalore HQ",
            operational_status="active"
        )
        self.shift_day = SiteShift.objects.create(
            site=self.site_a,
            shift_code="DAY-01",
            shift_name="General Day Shift",
            start_time="08:00:00",
            end_time="16:00:00",
            duration_minutes=480,
            is_active=True
        )

        # Seed Components
        self.comp_basic = SalaryComponent.objects.create(
            company_id=self.company_id,
            component_code="BASIC",
            component_name="Basic Pay",
            component_type="EARNING",
            wage_base_flags={"pf": True, "esi": True, "pt": True, "lwf": True},
            proration_enabled=True,
            display_order=1
        )
        self.comp_da = SalaryComponent.objects.create(
            company_id=self.company_id,
            component_code="DA",
            component_name="Dearness Allowance",
            component_type="EARNING",
            wage_base_flags={"pf": True, "esi": True, "pt": True, "lwf": True},
            proration_enabled=True,
            display_order=2
        )
        self.comp_hra = SalaryComponent.objects.create(
            company_id=self.company_id,
            component_code="HRA",
            component_name="House Rent Allowance",
            component_type="EARNING",
            wage_base_flags={"pf": False, "esi": True, "pt": True, "lwf": True},
            proration_enabled=True,
            display_order=3
        )

        # Standard Paid Day Rule Set (30 days)
        self.paid_day_rule = PaidDayRuleSet.objects.create(
            company_id=self.company_id,
            name="Karnataka Standard 30-Day Rule",
            month_length_rule="FIXED_30",
            effective_from=date(2026, 1, 1),
            status="ACTIVE"
        )

        # Standard Structure (Total ₹18,000 = Basic 10,000 + DA 5,000 + HRA 3,000)
        self.structure = SalaryStructure.objects.create(
            company_id=self.company_id,
            name="Standard Guard Structure 18K",
            version=1,
            effective_from=date(2026, 1, 1),
            status="ACTIVE",
            change_reason="Baseline structure"
        )
        SalaryStructureLine.objects.create(
            structure=self.structure, component=self.comp_basic, amount=Decimal('10000.00'), effective_from=date(2026, 1, 1)
        )
        SalaryStructureLine.objects.create(
            structure=self.structure, component=self.comp_da, amount=Decimal('5000.00'), effective_from=date(2026, 1, 1)
        )
        SalaryStructureLine.objects.create(
            structure=self.structure, component=self.comp_hra, amount=Decimal('3000.00'), effective_from=date(2026, 1, 1)
        )

        # Assign to Guard 1
        self.assignment = GuardSalaryAssignment.objects.create(
            company_id=self.company_id,
            guard_id=self.employee.employee_id,
            structure=self.structure,
            pay_basis="MONTHLY",
            effective_from=date(2026, 1, 1),
            reason="Initial assignment",
            prepared_by=self.preparer_id,
            approved_by=self.approver_id,
            status="ACTIVE"
        )

    # -------------------------------------------------------------------------
    # AC14.1 & AC14.2: Salary Component Creation & Historical Protection
    # -------------------------------------------------------------------------
    def test_ac14_1_create_salary_component(self):
        self.client.force_authenticate(user=self.admin_preparer)
        res = self.client.post('/api/payroll/components/', {
            "component_code": "UNIFORM_ALLOWANCE",
            "component_name": "Uniform Allowance",
            "component_type": "EARNING",
            "proration_enabled": False,
            "display_order": 6
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['component_code'], "UNIFORM_ALLOWANCE")

    def test_ac14_2_historical_component_cannot_be_deleted(self):
        self.client.force_authenticate(user=self.admin_preparer)
        # Attempt to delete self.comp_basic which is referenced in self.structure
        res = self.client.delete(f'/api/payroll/components/{self.comp_basic.component_id}/')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("historical", str(res.data).lower())

    # -------------------------------------------------------------------------
    # AC14.3 & AC14.4: Salary Structure Assignment & History
    # -------------------------------------------------------------------------
    def test_ac14_3_salary_assignment_effective_dates(self):
        self.assertIsNotNone(self.assignment.effective_from)
        self.assertEqual(self.assignment.status, 'ACTIVE')
        self.assertEqual(self.assignment.approved_by, self.approver_id)

    def test_ac14_4_salary_assignment_change_preserves_old(self):
        self.client.force_authenticate(user=self.admin_preparer)
        # Create second structure (20K)
        struct2 = SalaryStructure.objects.create(
            company_id=self.company_id,
            name="Senior Guard Structure 20K",
            effective_from=date(2026, 6, 1),
            change_reason="Revision"
        )
        res = self.client.post('/api/payroll/assignments/', {
            "guard_id": str(self.employee.employee_id),
            "structure_id": str(struct2.structure_id),
            "pay_basis": "MONTHLY",
            "effective_from": "2026-06-01",
            "reason": "Promotion to Senior Guard"
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        # Old assignment still exists in history
        old_asgn = GuardSalaryAssignment.objects.get(assignment_id=self.assignment.assignment_id)
        self.assertIsNotNone(old_asgn)

    # -------------------------------------------------------------------------
    # AC14.5: Mid-Month Salary Change
    # -------------------------------------------------------------------------
    def test_ac14_5_mid_month_salary_change(self):
        # Guard gets a salary hike effective Nov 16 (days 1-15 old rate, days 16-30 new rate)
        # Set old structure effective to Nov 15
        self.assignment.effective_to = date(2026, 11, 15)
        self.assignment.save()

        # Structure 2: Basic 20,000, DA 10,000 = 30,000 total
        struct_new = SalaryStructure.objects.create(
            company_id=self.company_id,
            name="Revised Structure 30K",
            effective_from=date(2026, 11, 16),
            change_reason="Hike"
        )
        SalaryStructureLine.objects.create(
            structure=struct_new, component=self.comp_basic, amount=Decimal('20000.00'), effective_from=date(2026, 11, 16)
        )
        SalaryStructureLine.objects.create(
            structure=struct_new, component=self.comp_da, amount=Decimal('10000.00'), effective_from=date(2026, 11, 16)
        )

        GuardSalaryAssignment.objects.create(
            company_id=self.company_id,
            guard_id=self.employee.employee_id,
            structure=struct_new,
            pay_basis="MONTHLY",
            effective_from=date(2026, 11, 16),
            effective_to=date(2026, 11, 30),
            reason="Mid-month hike",
            status="ACTIVE"
        )

        run = PayrollRun.objects.create(
            company_id=self.company_id,
            period_start=date(2026, 11, 1),
            period_end=date(2026, 11, 30),
            period_reference="2026-11",
            run_type="FINAL"
        )

        calc_res = calculate_payroll_run(run.run_id, self.company_id, self.preparer_id)
        # 15 days on 18K (18000 * 15 / 30 = 9000)
        # 15 days on 30K (30000 * 15 / 30 = 15000)
        # Total gross = 24,000.00
        self.assertEqual(calc_res['total_gross'], 24000.00)

    # -------------------------------------------------------------------------
    # AC14.6: Guard without Active Structure Flagged in Checklist
    # -------------------------------------------------------------------------
    def test_ac14_6_missing_structure_flagged_in_checklist(self):
        # self.employee2 has no GuardSalaryAssignment
        checklist = get_pre_run_checklist(self.company_id, date(2026, 11, 1), date(2026, 11, 30))
        self.assertGreater(checklist['missing_salary_structures_count'], 0)
        missing_ids = [m['guard_id'] for m in checklist['missing_salary_structures']]
        self.assertIn(str(self.employee2.employee_id), missing_ids)

    # -------------------------------------------------------------------------
    # AC14.7 & AC14.8: Minimum Wage Exception & Admin Override
    # -------------------------------------------------------------------------
    def test_ac14_7_and_ac14_8_minimum_wage_breach_and_override(self):
        # Create Locked attendance period so run is eligible for approval
        AttendancePeriod.objects.create(
            company_id=self.company_id,
            period_name="Nov 2026",
            start_date=date(2026, 11, 1),
            end_date=date(2026, 11, 30),
            status="locked"
        )
        # Minimum wage in Karnataka = ₹700/day
        MinimumWage.objects.create(
            company_id=self.company_id,
            state="Karnataka",
            skill_category="Security Guard",
            amount=Decimal('700.00'),
            pay_basis="DAILY",
            effective_from=date(2026, 1, 1)
        )
        # Structure pays 18,000 / 30 = ₹600/day (< 700 minimum wage)
        run = PayrollRun.objects.create(
            company_id=self.company_id,
            period_start=date(2026, 11, 1),
            period_end=date(2026, 11, 30),
            period_reference="2026-11",
            run_type="FINAL"
        )
        calc_res = calculate_payroll_run(run.run_id, self.company_id, self.preparer_id)
        self.assertEqual(calc_res['held_count'], 1)

        # Attempt to approve without override -> blocked (AC14.7)
        with self.assertRaises(Exception):
            approve_payroll_run(run.run_id, self.company_id, self.approver_id)

        # Approve with documented reason -> succeeds (AC14.8)
        app_res = approve_payroll_run(
            run.run_id, self.company_id, self.approver_id,
            force_override_reasons="Approved under grandfathered client contract rate pending annual revision."
        )
        self.assertEqual(app_res['status'], 'APPROVED')

    # -------------------------------------------------------------------------
    # AC14.9 & AC14.10: Locked vs Unlocked Attendance (Provisional vs Final)
    # -------------------------------------------------------------------------
    def test_ac14_10_unlocked_attendance_forces_provisional_run(self):
        # No locked period exists -> calculation forces run_type = PROVISIONAL
        run = PayrollRun.objects.create(
            company_id=self.company_id,
            period_start=date(2026, 11, 1),
            period_end=date(2026, 11, 30),
            period_reference="2026-11",
            run_type="FINAL"
        )
        calc = calculate_payroll_run(run.run_id, self.company_id, self.preparer_id)
        run.refresh_from_db()
        self.assertEqual(run.run_type, 'PROVISIONAL')

        # AC14.10: Provisional run CANNOT be approved!
        with self.assertRaises(Exception) as ctx:
            approve_payroll_run(run.run_id, self.company_id, self.approver_id)
        self.assertIn("provisional", str(ctx.exception).lower())

    def test_ac14_9_locked_attendance_allows_final_approval(self):
        # Create Locked attendance period
        AttendancePeriod.objects.create(
            company_id=self.company_id,
            period_name="Nov 2026",
            start_date=date(2026, 11, 1),
            end_date=date(2026, 11, 30),
            status="locked"
        )
        run = PayrollRun.objects.create(
            company_id=self.company_id,
            period_start=date(2026, 11, 1),
            period_end=date(2026, 11, 30),
            period_reference="2026-11",
            run_type="FINAL"
        )
        calculate_payroll_run(run.run_id, self.company_id, self.preparer_id)
        run.refresh_from_db()
        self.assertEqual(run.run_type, 'FINAL')
        app = approve_payroll_run(run.run_id, self.company_id, self.approver_id)
        self.assertEqual(app['status'], 'APPROVED')

    # -------------------------------------------------------------------------
    # AC14.11 & AC14.12: Overtime Calculation
    # -------------------------------------------------------------------------
    def test_ac14_12_approved_overtime_paid(self):
        # Add 120 mins approved overtime
        AttendanceRecord.objects.create(
            company_id=self.company_id,
            site=self.site_a,
            shift=self.shift_day,
            employee=self.employee,
            duty_date=date(2026, 11, 10),
            scheduled_start=timezone.now(),
            scheduled_end=timezone.now() + timedelta(hours=8),
            status="approved",
            regular_minutes=480,
            overtime_minutes=120
        )
        run = PayrollRun.objects.create(
            company_id=self.company_id,
            period_start=date(2026, 11, 1),
            period_end=date(2026, 11, 30),
            period_reference="2026-11",
            run_type="FINAL"
        )
        calc = calculate_payroll_run(run.run_id, self.company_id, self.preparer_id)
        ot_line = PayrollResultLine.objects.filter(code="OVERTIME").first()
        self.assertIsNotNone(ot_line)
        self.assertGreater(ot_line.amount, Decimal('0.00'))

    # -------------------------------------------------------------------------
    # AC14.13 & AC14.18: Statutory Calculation & Employer Contributions
    # -------------------------------------------------------------------------
    def test_ac14_13_and_ac14_18_statutory_and_employer_separation(self):
        # Configure PF Rule: 12% employee, 12% employer
        StatutoryRuleSet.objects.create(
            company_id=self.company_id,
            scheme="PF",
            version=1,
            wage_base_components=["BASIC", "DA"],
            employee_rate=Decimal('0.1200'),
            employer_rate=Decimal('0.1200'),
            effective_from=date(2026, 1, 1),
            status="ACTIVE"
        )
        run = PayrollRun.objects.create(
            company_id=self.company_id,
            period_start=date(2026, 11, 1),
            period_end=date(2026, 11, 30),
            period_reference="2026-11",
            run_type="FINAL"
        )
        calc = calculate_payroll_run(run.run_id, self.company_id, self.preparer_id)
        # Wage base = Basic 10,000 + DA 5,000 = 15,000
        # 12% of 15,000 = 1,800
        result = PayrollResult.objects.get(run=run, guard_id=self.employee.employee_id)
        self.assertEqual(result.employee_deductions, Decimal('1800.00'))
        self.assertEqual(result.employer_contributions, Decimal('1800.00'))
        # AC14.18: Net pay = 18000 - 1800 = 16,200. Employer contribution (1800) NOT deducted!
        self.assertEqual(result.net_pay, Decimal('16200.00'))

    # -------------------------------------------------------------------------
    # AC14.16: Dual-Admin Approval for Statutory Rule Sets
    # -------------------------------------------------------------------------
    def test_ac14_16_statutory_rule_single_preparer_activation_blocked(self):
        rule = StatutoryRuleSet.objects.create(
            company_id=self.company_id,
            scheme="ESI",
            version=1,
            employee_rate=Decimal('0.0075'),
            effective_from=date(2026, 1, 1),
            prepared_by=self.preparer_id,
            status="DRAFT"
        )
        # Preparer attempts to approve alone -> blocked (AC14.16)
        self.client.force_authenticate(user=self.admin_preparer)
        res = self.client.post(f'/api/payroll/statutory-rules/{rule.rule_set_id}/approve/')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # Different Admin approves -> succeeds
        self.client.force_authenticate(user=self.admin_approver)
        res2 = self.client.post(f'/api/payroll/statutory-rules/{rule.rule_set_id}/approve/')
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        rule.refresh_from_db()
        self.assertEqual(rule.status, 'ACTIVE')

    # -------------------------------------------------------------------------
    # AC14.28 & AC14.37: Advance Recovery & Net-Pay Zero Floor
    # -------------------------------------------------------------------------
    def test_ac14_28_and_ac14_37_net_pay_never_negative(self):
        # Issue an advance of ₹50,000 with monthly recovery of ₹25,000
        adv = Advance.objects.create(
            company_id=self.company_id,
            guard_id=self.employee.employee_id,
            amount=Decimal('50000.00'),
            issue_date=date(2026, 11, 1),
            reason="Medical emergency",
            recovery_type="FIXED",
            recovery_value=Decimal('25000.00'),
            max_per_instalment=Decimal('25000.00'),
            status="APPROVED",
            approved_by=self.approver_id
        )
        AdvanceLedgerEntry.objects.create(
            advance=adv,
            entry_type="ISSUE",
            amount=Decimal('50000.00'),
            entry_date=date(2026, 11, 1)
        )
        # Gross salary is 18,000. Planned recovery is 25,000.
        # Without zero floor, net pay would be 18000 - 25000 = -7000!
        run = PayrollRun.objects.create(
            company_id=self.company_id,
            period_start=date(2026, 11, 1),
            period_end=date(2026, 11, 30),
            period_reference="2026-11",
            run_type="FINAL"
        )
        calc = calculate_payroll_run(run.run_id, self.company_id, self.preparer_id)
        result = PayrollResult.objects.get(run=run, guard_id=self.employee.employee_id)
        # AC14.28 & AC14.37: Net pay is capped at zero floor (₹0.00) and recovery is ₹18,000
        self.assertEqual(result.net_pay, Decimal('0.00'))
        self.assertEqual(result.employee_deductions, Decimal('18000.00'))

    # -------------------------------------------------------------------------
    # AC14.29 & AC14.30: Segregation of Duties (Preparer cannot Approve)
    # -------------------------------------------------------------------------
    def test_ac14_29_preparer_cannot_approve_own_run(self):
        AttendancePeriod.objects.create(
            company_id=self.company_id,
            period_name="Nov 2026",
            start_date=date(2026, 11, 1),
            end_date=date(2026, 11, 30),
            status="locked"
        )
        run = PayrollRun.objects.create(
            company_id=self.company_id,
            period_start=date(2026, 11, 1),
            period_end=date(2026, 11, 30),
            period_reference="2026-11",
            run_type="FINAL"
        )
        calculate_payroll_run(run.run_id, self.company_id, self.preparer_id)

        # Preparer attempts to approve -> blocked (AC14.29)
        with self.assertRaises(Exception) as ctx:
            approve_payroll_run(run.run_id, self.company_id, self.preparer_id)
        self.assertIn("segregation", str(ctx.exception).lower())

        # Designated second admin approves -> succeeds (AC14.30)
        app = approve_payroll_run(run.run_id, self.company_id, self.approver_id)
        self.assertEqual(app['status'], 'APPROVED')

    # -------------------------------------------------------------------------
    # AC14.38 & AC14.39: Payslip Generation after Approval & Immutability
    # -------------------------------------------------------------------------
    def test_ac14_38_and_ac14_39_payslip_generation_and_hash(self):
        AttendancePeriod.objects.create(
            company_id=self.company_id,
            period_name="Nov 2026",
            start_date=date(2026, 11, 1),
            end_date=date(2026, 11, 30),
            status="locked"
        )
        run = PayrollRun.objects.create(
            company_id=self.company_id,
            period_start=date(2026, 11, 1),
            period_end=date(2026, 11, 30),
            period_reference="2026-11",
            run_type="FINAL"
        )
        calculate_payroll_run(run.run_id, self.company_id, self.preparer_id)
        approve_payroll_run(run.run_id, self.company_id, self.approver_id)

        # Release run -> generates payslips
        rel = release_payroll_run(run.run_id, self.company_id, self.approver_id)
        self.assertEqual(rel['status'], 'RELEASED')

        payslip = Payslip.objects.filter(run=run, guard_id=self.employee.employee_id).first()
        self.assertIsNotNone(payslip)
        self.assertTrue(payslip.payslip_number.startswith("PS-202611-"))
        self.assertIsNotNone(payslip.pdf_hash)

    # -------------------------------------------------------------------------
    # AC14.41 & AC14.42 & AC14.43 & AC14.44: Role-Based Payslip & Payroll Access
    # -------------------------------------------------------------------------
    def test_ac14_41_guard_views_own_payslip_and_denied_others(self):
        # Create a released payslip
        run = PayrollRun.objects.create(
            company_id=self.company_id,
            period_start=date(2026, 11, 1),
            period_end=date(2026, 11, 30),
            period_reference="2026-11",
            status="RELEASED",
            run_type="FINAL"
        )
        res1 = PayrollResult.objects.create(run=run, guard_id=self.employee.employee_id, net_pay=Decimal('18000.00'))
        res2 = PayrollResult.objects.create(run=run, guard_id=self.employee2.employee_id, net_pay=Decimal('15000.00'))
        ps1 = Payslip.objects.create(payslip_number="PS-001", guard_id=self.employee.employee_id, run=run, result=res1)
        ps2 = Payslip.objects.create(payslip_number="PS-002", guard_id=self.employee2.employee_id, run=run, result=res2)

        # Guard 1 logs in
        self.client.force_authenticate(user=self.guard_user)
        resp = self.client.get('/api/payroll/payslips/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Can only see their own payslip (AC14.41)
        slip_numbers = [s['payslip_number'] for s in resp.data.get('results', resp.data)]
        self.assertIn("PS-001", slip_numbers)
        self.assertNotIn("PS-002", slip_numbers)

    def test_ac14_43_supervisor_denied_financial_payroll(self):
        self.client.force_authenticate(user=self.supervisor_user)
        resp = self.client.get('/api/payroll/payslips/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_ac14_44_client_denied_payroll_access(self):
        self.client.force_authenticate(user=self.client_user)
        resp = self.client.get('/api/payroll/dashboard/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # -------------------------------------------------------------------------
    # AC14.48 & AC14.49 & AC14.51: Payments, Overpayment, Duplicate & Reversal
    # -------------------------------------------------------------------------
    def test_ac14_48_approver_cannot_record_payment_and_overpayment_rejected(self):
        run = PayrollRun.objects.create(
            company_id=self.company_id,
            period_start=date(2026, 11, 1),
            period_end=date(2026, 11, 30),
            period_reference="2026-11",
            status="RELEASED",
            run_type="FINAL",
            approved_by=self.approver_id
        )
        res = PayrollResult.objects.create(run=run, guard_id=self.employee.employee_id, net_pay=Decimal('18000.00'))

        # Approver attempts to record payment -> blocked (AC14.48)
        with self.assertRaises(Exception) as ctx:
            record_payment(run.run_id, res.result_id, self.employee.employee_id, 18000, "BANK_TRANSFER", "NEFT001", self.approver_id)
        self.assertIn("segregation", str(ctx.exception).lower())

        # Another recorder attempts overpayment (20,000 > 18,000) -> rejected (AC14.48)
        with self.assertRaises(Exception) as ctx2:
            record_payment(run.run_id, res.result_id, self.employee.employee_id, 20000, "BANK_TRANSFER", "NEFT001", self.preparer_id)
        self.assertIn("overpayment", str(ctx2.exception).lower())

        # Valid payment (18,000) -> succeeds
        p = record_payment(run.run_id, res.result_id, self.employee.employee_id, 18000, "BANK_TRANSFER", "NEFT001", self.preparer_id)
        self.assertEqual(p['status'], 'PAID')

        # AC14.49: Duplicate payment with same bank reference rejected
        with self.assertRaises(Exception) as ctx3:
            record_payment(run.run_id, res.result_id, self.employee.employee_id, 18000, "BANK_TRANSFER", "NEFT001", self.preparer_id)
        self.assertIn("duplicate", str(ctx3.exception).lower())

    def test_ac14_51_payment_reversal(self):
        run = PayrollRun.objects.create(
            company_id=self.company_id,
            period_start=date(2026, 11, 1),
            period_end=date(2026, 11, 30),
            period_reference="2026-11",
            status="RELEASED",
            run_type="FINAL",
            approved_by=self.approver_id
        )
        res = PayrollResult.objects.create(run=run, guard_id=self.employee.employee_id, net_pay=Decimal('18000.00'))
        pay = record_payment(run.run_id, res.result_id, self.employee.employee_id, 18000, "BANK_TRANSFER", "NEFT999", self.preparer_id)

        # Reverse payment with reason (AC14.51)
        rev = reverse_payment(pay['payment_id'], self.company_id, self.preparer_id, "Wrong bank account number credited.")
        self.assertEqual(rev['status'], 'REVERSED')
        self.assertEqual(rev['reversal_reason'], "Wrong bank account number credited.")
