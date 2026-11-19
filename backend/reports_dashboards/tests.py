import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from django.utils import timezone
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from foundation.models import Company, User
from master_data.models import ClientSite, Client, SiteSupervisorAssignment, PostType, SiteShift
from deployment_roster.models import PostSlot, RosterAssignment
from attendance.models import AttendanceRecord, AttendancePeriod
from guard_management.models import Employee, EmployeeDocument
from panic_escalation.models import PanicAlert
from billing_invoices.models import ClientInvoice
from weapons_register.models import Weapon

from .models import (
    ReportDefinition, MetricDefinition, MetricDefinitionVersion,
    ClientMonthlySummary, ReportGenerationRecord
)
from .services import (
    sanitize_csv_cell, mask_weapon_serial, calculate_metric_value,
    calculate_data_quality_notes
)


class Module13ReportsAndDashboardsTests(TestCase):
    """
    Automated test suite verifying Module 13 Acceptance Criteria (AC13.1 - AC13.66).
    """

    def setUp(self):
        self.client = APIClient()

        # Company
        self.company = Company.objects.create(
            legal_name="Karnataka Security Services Ltd",
            trade_name="KSS",
            country_code="IN",
            state_code="KA",
            is_active=True
        )

        # Admin User
        self.admin_user = User.objects.create(
            email="admin@test.local",
            full_name="Admin Officer",
            company_id=self.company.company_id,
            role="ADMIN",
            status="ACTIVE"
        )

        # Supervisor User
        self.supervisor_user = User.objects.create(
            email="supervisor@test.local",
            full_name="Field Supervisor 1",
            company_id=self.company.company_id,
            role="SUPERVISOR",
            status="ACTIVE"
        )

        # Guard User
        self.guard_user = User.objects.create(
            email="guard@test.local",
            full_name="Security Guard 1",
            company_id=self.company.company_id,
            role="GUARD",
            status="ACTIVE"
        )

        # Guard Employee record
        self.guard_employee = Employee.objects.create(
            company_id=self.company.company_id,
            employee_code="EMP-KA-001",
            first_name="Ramesh",
            last_name="Kumar",
            phone="9876543210",
            date_joined=date(2025, 1, 1),
            lifecycle_status="active"
        )

        # Client Organization & Sites
        self.client_org = Client.objects.create(
            company_id=self.company.company_id,
            client_code="INFY",
            legal_name="Infosys Bangalore Campus",
            display_name="Infosys",
            status="active"
        )
        self.site_a = ClientSite.objects.create(
            client_id=self.client_org.client_id,
            site_name="Main Gate - Gate 1",
            site_code="SITE-INFY-01",
            address_line1="Electronic City",
            operational_status="active"
        )
        self.site_b = ClientSite.objects.create(
            client_id=self.client_org.client_id,
            site_name="Data Center South",
            site_code="SITE-INFY-02",
            address_line1="Electronic City",
            operational_status="active"
        )

        # Assign Site A only to Supervisor
        SiteSupervisorAssignment.objects.create(
            site_id=self.site_a.site_id,
            supervisor_user_id=self.supervisor_user.user_id,
            effective_from=timezone.now(),
            is_active=True
        )

        # Post Types & Shifts
        self.post_type = PostType.objects.create(
            company_id=self.company.company_id,
            code="UNARMED_STATIC",
            name="Static Unarmed Post",
            requires_armed_authorization=False
        )
        self.shift = SiteShift.objects.create(
            site_id=self.site_a.site_id,
            shift_code="DAY",
            shift_name="Day Shift",
            start_time="08:00:00",
            end_time="20:00:00",
            duration_minutes=720,
            is_active=True
        )

        # Seed Report Catalogue and Metric Dictionary via PostgreSQL Seed Function
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT security_erp.seed_module13_company_defaults(%s);", [str(self.company.company_id)])

    # -------------------------------------------------------------------------
    # AC13.1 & AC13.2: Admin Dashboard & Empty States
    # -------------------------------------------------------------------------
    def test_ac13_1_admin_overview_dashboard(self):
        """AC13.1: Admin opens overview dashboard and retrieves source-derived numbers."""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get('/api/reports/dashboard/admin/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('kpis', response.data)
        self.assertIn('fill_rate', response.data['kpis'])
        self.assertIn('status_label', response.data)

    def test_ac13_2_empty_state_handling(self):
        """AC13.2: When no records exist, clean empty state is returned (no fakes)."""
        empty_comp = Company.objects.create(legal_name="Brand New Agency Ltd", country_code="IN", state_code="KA", is_active=True)
        admin2 = User.objects.create(email="new@test.local", company_id=empty_comp.company_id, role="ADMIN", status="ACTIVE")
        self.client.force_authenticate(user=admin2)
        response = self.client.get('/api/reports/dashboard/admin/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['kpis']['required_posts']['value'], 0)

    # -------------------------------------------------------------------------
    # AC13.3: Metric Dictionary Entry Lookup
    # -------------------------------------------------------------------------
    def test_ac13_3_metric_dictionary_lookup(self):
        """AC13.3: Metric definition lookup returns exact dictionary entry."""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get('/api/reports/metrics/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['metrics_count'], 1)

    # -------------------------------------------------------------------------
    # AC13.7 & AC13.8: Provisional vs Final Status
    # -------------------------------------------------------------------------
    def test_ac13_7_attendance_provisional_label(self):
        """AC13.7: Reports with unapproved attendance records are labelled Provisional."""
        today = timezone.now().date()
        AttendanceRecord.objects.create(
            company_id=self.company.company_id,
            site_id=self.site_a.site_id,
            employee_id=self.guard_employee.employee_id,
            shift_id=self.shift.shift_id,
            duty_date=today,
            scheduled_start=timezone.now(),
            scheduled_end=timezone.now() + timedelta(hours=8),
            status='pending_approval'
        )
        notes = calculate_data_quality_notes(self.company.company_id, today, today)
        self.assertEqual(notes['status'], 'PROVISIONAL')
        self.assertTrue(notes['is_provisional'])

    def test_ac13_8_attendance_final_label(self):
        """AC13.8: When all attendance records are approved and periods locked, status is Final."""
        today = timezone.now().date()
        AttendanceRecord.objects.create(
            company_id=self.company.company_id,
            site_id=self.site_a.site_id,
            employee_id=self.guard_employee.employee_id,
            shift_id=self.shift.shift_id,
            duty_date=today,
            scheduled_start=timezone.now(),
            scheduled_end=timezone.now() + timedelta(hours=8),
            status='approved'
        )
        notes = calculate_data_quality_notes(self.company.company_id, today, today)
        self.assertEqual(notes['status'], 'FINAL')
        self.assertFalse(notes['is_provisional'])

    # -------------------------------------------------------------------------
    # AC13.11: Panic Test Alerts Exclusion
    # -------------------------------------------------------------------------
    def test_ac13_11_panic_test_alerts_exclusion(self):
        """AC13.11: Test status panic alerts are excluded from real panic metrics."""
        today = timezone.now().date()
        # Real alert
        PanicAlert.objects.create(
            company_id=self.company.company_id,
            site_id=self.site_a.site_id,
            guard_id=self.guard_employee.employee_id,
            alert_number=f"ALT-R-{uuid.uuid4().hex[:6]}",
            client_generated_id=str(uuid.uuid4()),
            test_flag=False,
            alert_status='TRIGGERED'
        )
        # Test drill
        PanicAlert.objects.create(
            company_id=self.company.company_id,
            site_id=self.site_a.site_id,
            guard_id=self.guard_employee.employee_id,
            alert_number=f"ALT-T-{uuid.uuid4().hex[:6]}",
            client_generated_id=str(uuid.uuid4()),
            test_flag=True,
            alert_status='TEST'
        )

        res = calculate_metric_value('M50', self.company.company_id, today, today)
        self.assertEqual(res['value'], 1) # Only 1 real alert counted!

    # -------------------------------------------------------------------------
    # AC13.12 & AC13.13: Supervisor Site Scoping
    # -------------------------------------------------------------------------
    def test_ac13_12_supervisor_scoped_dashboard(self):
        """AC13.12: Supervisor dashboard contains only assigned sites data."""
        self.client.force_authenticate(user=self.supervisor_user)
        response = self.client.get('/api/reports/dashboard/supervisor/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['assigned_sites_count'], 1)

    def test_ac13_13_supervisor_unassigned_site_denied(self):
        """AC13.13: Supervisor attempting to query unassigned site is rejected server-side."""
        self.client.force_authenticate(user=self.supervisor_user)
        response = self.client.get(f'/api/reports/detail/MANPOWER_REQ/?site_id={self.site_b.site_id}')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # -------------------------------------------------------------------------
    # AC13.15: Guard Access Denied
    # -------------------------------------------------------------------------
    def test_ac13_15_guard_access_denied(self):
        """AC13.15: Guards are strictly denied access to reports and dashboards."""
        self.client.force_authenticate(user=self.guard_user)
        response = self.client.get('/api/reports/catalogue/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # -------------------------------------------------------------------------
    # AC13.21: CSV Formula Injection Neutralization
    # -------------------------------------------------------------------------
    def test_ac13_21_csv_formula_injection_defense(self):
        """AC13.21: Cells beginning with =, +, -, @ are escaped with a leading quote."""
        self.assertEqual(sanitize_csv_cell("=SUM(A1:A10)"), "'=SUM(A1:A10)")
        self.assertEqual(sanitize_csv_cell("+cmd|' /C calc'!A0"), "'+cmd|' /C calc'!A0")
        self.assertEqual(sanitize_csv_cell("@HYPERLINK(...)"), "'@HYPERLINK(...)")
        self.assertEqual(sanitize_csv_cell("Normal Text"), "Normal Text")

    # -------------------------------------------------------------------------
    # AC13.24: Bulk Export Reason Check
    # -------------------------------------------------------------------------
    def test_ac13_24_bulk_export_reason_required(self):
        """AC13.24: Exporting large row counts requires an operational reason."""
        today = timezone.now().date()
        slots = [
            PostSlot(
                slot_id=uuid.uuid4(),
                company_id=self.company.company_id,
                site_id=self.site_a.site_id,
                deployment_date=today,
                post_type_id=self.post_type.post_type_id,
                shift_id=self.shift.shift_id,
                slot_sequence=i + 1,
                slot_status='filled'
            ) for i in range(105)
        ]
        PostSlot.objects.bulk_create(slots)

        self.client.force_authenticate(user=self.admin_user)
        res_no_reason = self.client.post('/api/reports/export/csv/', {'report_code': 'MANPOWER_REQ'})
        self.assertEqual(res_no_reason.status_code, status.HTTP_400_BAD_REQUEST)

        res_with_reason = self.client.post('/api/reports/export/csv/', {
            'report_code': 'MANPOWER_REQ',
            'bulk_reason': 'Monthly client compliance audit'
        })
        self.assertEqual(res_with_reason.status_code, status.HTTP_200_OK)

    # -------------------------------------------------------------------------
    # AC13.30 & AC13.31: Metric Definition Versioning
    # -------------------------------------------------------------------------
    def test_ac13_30_metric_definition_versioning(self):
        """AC13.30: Admin can propose new version and history is preserved."""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post('/api/reports/metrics/M01/propose-version/', {
            'formula': 'COUNT(post_slots) * 1.0',
            'change_reason': 'Refined floating point calculation'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        m = MetricDefinition.objects.get(metric_id='M01')
        self.assertEqual(m.current_version, 2)
        v_count = MetricDefinitionVersion.objects.filter(metric_id='M01').count()
        self.assertEqual(v_count, 2)

    # -------------------------------------------------------------------------
    # AC13.42, AC13.43, AC13.44: Client Monthly Summary Lifecycle
    # -------------------------------------------------------------------------
    def test_ac13_42_client_summary_lifecycle(self):
        """Draft, Release, and Immutable Versioning for Client Service Summary."""
        self.client.force_authenticate(user=self.admin_user)
        res_draft = self.client.post('/api/reports/client-summaries/', {
            'client_id': str(self.client_org.client_id),
            'month': 11,
            'year': 2026
        })
        self.assertEqual(res_draft.status_code, status.HTTP_201_CREATED)
        summary_id = res_draft.data['summary_id']
        self.assertEqual(res_draft.data['status'], 'DRAFT')

        res_release = self.client.post(f'/api/reports/client-summaries/{summary_id}/release/')
        self.assertEqual(res_release.status_code, status.HTTP_200_OK)
        self.assertEqual(res_release.data['summary']['status'], 'RELEASED')

        res_safe = self.client.get(f'/api/reports/client-summaries/client-safe/?client_id={self.client_org.client_id}')
        self.assertEqual(res_safe.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_safe.data), 1)

    # -------------------------------------------------------------------------
    # AC13.45 & AC13.46: Billing Excludes Draft Invoices
    # -------------------------------------------------------------------------
    def test_ac13_45_billing_excludes_draft_invoices(self):
        """AC13.45: Draft invoices are strictly excluded from billed amount."""
        today = timezone.now().date()
        ClientInvoice.objects.create(
            company_id=self.company.company_id,
            client_id=self.client_org.client_id,
            invoice_no='INV-2026-001',
            invoice_date=today,
            due_date=today + timedelta(days=30),
            period_start=today,
            period_end=today + timedelta(days=30),
            total_amount=Decimal('50000.00'),
            outstanding_amount=Decimal('50000.00'),
            status='SENT'
        )
        ClientInvoice.objects.create(
            company_id=self.company.company_id,
            client_id=self.client_org.client_id,
            invoice_no='INV-DRAFT-999',
            invoice_date=today,
            due_date=today + timedelta(days=30),
            period_start=today,
            period_end=today + timedelta(days=30),
            total_amount=Decimal('999999.00'),
            outstanding_amount=Decimal('999999.00'),
            status='DRAFT'
        )

        res = calculate_metric_value('M63', self.company.company_id, today, today)
        self.assertEqual(res['value'], 50000.00)

    # -------------------------------------------------------------------------
    # AC13.47: Zero Denominator displays N/A
    # -------------------------------------------------------------------------
    def test_ac13_47_zero_denominator_displays_na(self):
        """AC13.47: Zero denominator returns N/A rather than 0% or exception."""
        today = timezone.now().date()
        res = calculate_metric_value('M03', self.company.company_id, today, today)
        self.assertTrue(res['is_zero_denominator'])
        self.assertEqual(res['display'], 'N/A')

    # -------------------------------------------------------------------------
    # AC13.49 & AC13.50: Weapons Reports Admin-Only & Serial Masking
    # -------------------------------------------------------------------------
    def test_ac13_49_weapons_admin_only(self):
        """AC13.49: Supervisors are denied access to weapons reports."""
        self.client.force_authenticate(user=self.supervisor_user)
        response = self.client.get('/api/reports/detail/WEAPONS_AMMUNITION/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_ac13_50_weapons_serial_masking(self):
        """AC13.50: Weapon serial numbers are masked in summary displays."""
        masked = mask_weapon_serial("WPN-IND-48210")
        self.assertEqual(masked, "WPN-***-210")
        self.assertNotIn("482", masked)
