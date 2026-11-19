import uuid
from decimal import Decimal
from django.db import models


class SalaryComponent(models.Model):
    """
    Catalog of earnings, recurring deductions, and employer contributions (PRD 6.1, Entity 1).
    """
    TYPE_CHOICES = [
        ('EARNING', 'Earning'),
        ('RECURRING_DEDUCTION', 'Recurring Deduction'),
        ('EMPLOYER_CONTRIBUTION', 'Employer Contribution'),
    ]
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
    ]

    component_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField()
    component_code = models.CharField(max_length=50)
    component_name = models.CharField(max_length=150)
    component_type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    wage_base_flags = models.JSONField(default=dict)
    proration_enabled = models.BooleanField(default=True)
    classification = models.CharField(max_length=100, blank=True, null=True)
    display_order = models.IntegerField(default=1)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='ACTIVE')
    created_by = models.UUIDField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'security_erp"."payroll_salary_components'
        ordering = ['display_order', 'component_code']

    def __str__(self):
        return f"{self.component_code} - {self.component_name} ({self.component_type})"


class SalaryStructure(models.Model):
    """
    Versioned container of salary structure lines (PRD 6.1, Entity 2).
    """
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('ACTIVE', 'Active'),
        ('SUPERSEDED', 'Superseded'),
    ]

    structure_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField()
    name = models.CharField(max_length=150)
    version = models.IntegerField(default=1)
    effective_from = models.DateField()
    effective_to = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='ACTIVE')
    change_reason = models.TextField()
    created_by = models.UUIDField(blank=True, null=True)
    approved_by = models.UUIDField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'security_erp"."payroll_salary_structures'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} (v{self.version}) - {self.status}"


class SalaryStructureLine(models.Model):
    """
    Individual component line item in a structure (PRD 6.1, Entity 3).
    """
    CALC_CHOICES = [
        ('FIXED', 'Fixed Amount'),
        ('PERCENTAGE_OF_BASIC', 'Percentage of Basic'),
        ('FORMULA', 'Formula Calculation'),
    ]

    line_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    structure = models.ForeignKey(SalaryStructure, on_delete=models.CASCADE, related_name='lines', db_column='structure_id')
    component = models.ForeignKey(SalaryComponent, on_delete=models.RESTRICT, db_column='component_id')
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    calculation_type = models.CharField(max_length=50, choices=CALC_CHOICES, default='FIXED')
    effective_from = models.DateField()
    effective_to = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'security_erp"."payroll_salary_structure_lines'
        ordering = ['component__display_order', 'created_at']


class GuardSalaryAssignment(models.Model):
    """
    Effective-dated assignment of salary structure to a guard (PRD 6.1, Entity 4).
    """
    PAY_BASIS_CHOICES = [
        ('MONTHLY', 'Monthly'),
        ('DAILY', 'Daily'),
        ('HOURLY', 'Hourly'),
    ]
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PENDING_APPROVAL', 'Pending Approval'),
        ('ACTIVE', 'Active'),
        ('SUPERSEDED', 'Superseded'),
    ]

    assignment_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField()
    guard_id = models.UUIDField()
    structure = models.ForeignKey(SalaryStructure, on_delete=models.RESTRICT, db_column='structure_id')
    pay_basis = models.CharField(max_length=30, choices=PAY_BASIS_CHOICES, default='MONTHLY')
    effective_from = models.DateField()
    effective_to = models.DateField(blank=True, null=True)
    reason = models.TextField()
    prepared_by = models.UUIDField(blank=True, null=True)
    approved_by = models.UUIDField(blank=True, null=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='ACTIVE')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'security_erp"."payroll_guard_salary_assignments'
        ordering = ['-effective_from']


class MinimumWage(models.Model):
    """
    Configurable minimum wage rate tables per state/zone/skill (PRD 6.2, Entity 5).
    """
    record_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField()
    state = models.CharField(max_length=100)
    zone = models.CharField(max_length=100, blank=True, null=True)
    skill_category = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    pay_basis = models.CharField(max_length=30, default='DAILY')
    effective_from = models.DateField()
    effective_to = models.DateField(blank=True, null=True)
    source_document = models.TextField(blank=True, null=True)
    approved_by = models.UUIDField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'security_erp"."payroll_minimum_wages'
        ordering = ['state', 'skill_category', '-effective_from']


class PaidDayRuleSet(models.Model):
    """
    Configurable month length, payable day mappings, and exception treatment (PRD 6.3, Entity 6).
    """
    MONTH_LENGTH_CHOICES = [
        ('CALENDAR_DAYS', 'Calendar Days (28/29/30/31)'),
        ('FIXED_26', 'Fixed 26 Days'),
        ('FIXED_30', 'Fixed 30 Days'),
    ]
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('ACTIVE', 'Active'),
        ('SUPERSEDED', 'Superseded'),
    ]

    rule_set_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField()
    name = models.CharField(max_length=150)
    month_length_rule = models.CharField(max_length=50, choices=MONTH_LENGTH_CHOICES, default='CALENDAR_DAYS')
    paid_day_mappings = models.JSONField(default=dict)
    half_day_treatment = models.CharField(max_length=50, default='HALF_RATE')
    manual_treatment = models.CharField(max_length=50, default='NORMAL_PAID')
    offline_treatment = models.CharField(max_length=50, default='NORMAL_PAID')
    late_early_treatment = models.CharField(max_length=50, default='NO_DEDUCTION')
    weekly_off_treatment = models.CharField(max_length=50, default='PAID_IF_ELIGIBLE')
    holiday_treatment = models.CharField(max_length=50, default='PAID_IF_ELIGIBLE')
    effective_from = models.DateField()
    effective_to = models.DateField(blank=True, null=True)
    version = models.IntegerField(default=1)
    approved_by = models.UUIDField(blank=True, null=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='ACTIVE')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'security_erp"."payroll_paid_day_rules'
        ordering = ['-effective_from']


class WeeklyOffCalendar(models.Model):
    """
    Weekly off and site-specific holiday schedules (PRD 8.8, Entity 6/7).
    """
    calendar_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField()
    site_id = models.UUIDField(blank=True, null=True)
    name = models.CharField(max_length=150)
    weekly_off_pattern = models.CharField(max_length=50, default='SUNDAY')
    holidays = models.JSONField(default=list)
    status = models.CharField(max_length=30, default='ACTIVE')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'security_erp"."payroll_weekly_off_calendars'


class StatutoryRuleSet(models.Model):
    """
    Versioned, dual-approved rules for PF, ESI, Professional Tax, LWF (PRD 6.5, Entity 7).
    """
    SCHEME_CHOICES = [
        ('PF', 'Provident Fund (EPF / EPS / EDLI)'),
        ('ESI', 'Employee State Insurance'),
        ('PROFESSIONAL_TAX', 'Professional Tax (PT)'),
        ('LABOUR_WELFARE_FUND', 'Labour Welfare Fund (LWF)'),
    ]
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('UNDER_REVIEW', 'Under Review'),
        ('APPROVED', 'Approved'),
        ('ACTIVE', 'Active'),
        ('SUPERSEDED', 'Superseded'),
    ]
    FREQ_CHOICES = [
        ('MONTHLY', 'Monthly'),
        ('HALF_YEARLY', 'Half Yearly'),
        ('ANNUAL', 'Annual'),
    ]

    rule_set_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField()
    scheme = models.CharField(max_length=50, choices=SCHEME_CHOICES)
    version = models.IntegerField(default=1)
    applicability = models.JSONField(default=dict)
    eligibility = models.JSONField(default=dict)
    wage_base_components = models.JSONField(default=list)
    employee_rate = models.DecimalField(max_digits=6, decimal_places=4, blank=True, null=True)
    employer_rate = models.DecimalField(max_digits=6, decimal_places=4, blank=True, null=True)
    contribution_splits = models.JSONField(default=dict)
    wage_floor = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    wage_ceiling = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    slabs = models.JSONField(default=list)
    frequency = models.CharField(max_length=30, choices=FREQ_CHOICES, default='MONTHLY')
    rounding_rule = models.CharField(max_length=50, default='NEAREST_RUPEE')
    rounding_level = models.CharField(max_length=50, default='EMPLOYEE_LEVEL')
    due_day = models.IntegerField(blank=True, null=True)
    source_document = models.TextField(blank=True, null=True)
    effective_from = models.DateField()
    effective_to = models.DateField(blank=True, null=True)
    prepared_by = models.UUIDField(blank=True, null=True)
    approved_by = models.UUIDField(blank=True, null=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='DRAFT')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'security_erp"."payroll_statutory_rule_sets'
        ordering = ['scheme', '-version']


class Advance(models.Model):
    """
    Guard advances and loans with ledger-backed recovery plan (PRD 6.6, Entity 11).
    """
    RECOVERY_CHOICES = [
        ('FIXED', 'Fixed Monthly Amount'),
        ('PERCENTAGE', 'Percentage of Net Earnings'),
    ]
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SUBMITTED', 'Submitted'),
        ('APPROVED', 'Approved'),
        ('ISSUED', 'Issued'),
        ('RECOVERING', 'Recovering'),
        ('RECOVERED', 'Recovered'),
        ('WRITTEN_OFF', 'Written Off'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled'),
    ]

    advance_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField()
    guard_id = models.UUIDField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    issue_date = models.DateField()
    reason = models.TextField()
    recovery_type = models.CharField(max_length=30, choices=RECOVERY_CHOICES, default='FIXED')
    recovery_value = models.DecimalField(max_digits=12, decimal_places=2)
    max_per_instalment = models.DecimalField(max_digits=12, decimal_places=2)
    interest_enabled = models.BooleanField(default=False)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='DRAFT')
    approved_by = models.UUIDField(blank=True, null=True)
    created_by = models.UUIDField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'security_erp"."payroll_advances'
        ordering = ['-issue_date']


class AdvanceLedgerEntry(models.Model):
    """
    Append-only ledger of advance issuances, recoveries, and adjustments (PRD 6.6, Entity 12).
    """
    ENTRY_TYPE_CHOICES = [
        ('ISSUE', 'Issue'),
        ('RECOVERY', 'Payroll Recovery'),
        ('ADJUSTMENT', 'Manual Adjustment'),
        ('WRITE_OFF', 'Write-Off'),
    ]

    entry_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    advance = models.ForeignKey(Advance, on_delete=models.RESTRICT, related_name='ledger_entries', db_column='advance_id')
    entry_type = models.CharField(max_length=30, choices=ENTRY_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    entry_date = models.DateField()
    payroll_run_id = models.UUIDField(blank=True, null=True)
    reason = models.TextField(blank=True, null=True)
    created_by = models.UUIDField(blank=True, null=True)
    approved_by = models.UUIDField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'security_erp"."payroll_advance_ledger'
        ordering = ['entry_date', 'created_at']


class ManualDeduction(models.Model):
    """
    Controlled manual deductions with mandatory justification and caps (PRD 6.6, Entity 13).
    """
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('APPLIED', 'Applied in Payroll'),
    ]
    ACK_CHOICES = [
        ('PENDING', 'Pending Acknowledgement'),
        ('ACCEPTED', 'Accepted by Guard'),
        ('DISPUTED', 'Disputed by Guard'),
    ]

    deduction_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField()
    guard_id = models.UUIDField()
    category = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.TextField()
    source_reference = models.CharField(max_length=100, blank=True, null=True)
    acknowledgement_required = models.BooleanField(default=False)
    acknowledgement_status = models.CharField(max_length=30, choices=ACK_CHOICES, default='PENDING')
    prepared_by = models.UUIDField(blank=True, null=True)
    approved_by = models.UUIDField(blank=True, null=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='DRAFT')
    applied_in_run_id = models.UUIDField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'security_erp"."payroll_manual_deductions'
        ordering = ['-created_at']


class PayrollRun(models.Model):
    """
    Payroll processing run for an agency period (PRD 6.7, Entity 8).
    """
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('CALCULATED', 'Calculated'),
        ('UNDER_REVIEW', 'Under Review'),
        ('APPROVED', 'Approved & Frozen'),
        ('RELEASED', 'Released for Payment'),
        ('PAID', 'Fully Paid'),
        ('PARTIALLY_PAID', 'Partially Paid'),
        ('CLOSED', 'Closed'),
        ('CANCELLED', 'Cancelled'),
    ]
    TYPE_CHOICES = [
        ('FINAL', 'Final Run (Requires Locked Attendance)'),
        ('PROVISIONAL', 'Provisional Run (Unlocked Attendance)'),
        ('SUPPLEMENTARY', 'Supplementary Run (Corrections/Arrears)'),
    ]

    run_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField()
    period_start = models.DateField()
    period_end = models.DateField()
    period_reference = models.CharField(max_length=50)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='DRAFT')
    run_type = models.CharField(max_length=30, choices=TYPE_CHOICES, default='FINAL')
    prepared_by = models.UUIDField(blank=True, null=True)
    approved_by = models.UUIDField(blank=True, null=True)
    approved_at = models.DateTimeField(blank=True, null=True)
    result_hash = models.CharField(max_length=128, blank=True, null=True)
    version = models.IntegerField(default=1)
    cancellation_reason = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'security_erp"."payroll_runs'
        ordering = ['-period_start', '-version']

    def __str__(self):
        return f"Payroll Run {self.period_reference} ({self.run_type}) - {self.status}"


class PayrollResult(models.Model):
    """
    Per-guard calculation breakdown in a payroll run (PRD 6.7, Entity 9).
    """
    result_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(PayrollRun, on_delete=models.CASCADE, related_name='results', db_column='run_id')
    guard_id = models.UUIDField()
    salary_assignment_id = models.UUIDField(blank=True, null=True)
    paid_days = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    regular_minutes = models.IntegerField(default=0)
    overtime_minutes = models.IntegerField(default=0)
    gross_earnings = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    employee_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    employer_contributions = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    net_pay = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    is_held = models.BooleanField(default=False)
    hold_reason = models.TextField(blank=True, null=True)
    calculation_details = models.JSONField(default=dict)
    rule_versions = models.JSONField(default=dict)
    result_hash = models.CharField(max_length=128, blank=True, null=True)
    version = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'security_erp"."payroll_results'
        ordering = ['run', 'guard_id']


class PayrollResultLine(models.Model):
    """
    Itemized lines (components, statutory, deductions, OT) behind a guard result (PRD 6.7, Entity 10).
    """
    LINE_TYPE_CHOICES = [
        ('EARNING', 'Earning Component'),
        ('STATUTORY_DEDUCTION', 'Employee Statutory Contribution'),
        ('RECURRING_DEDUCTION', 'Recurring Deduction'),
        ('MANUAL_DEDUCTION', 'Approved Manual Deduction'),
        ('ADVANCE_RECOVERY', 'Advance Recovery'),
        ('EMPLOYER_CONTRIBUTION', 'Employer Contribution (Separate)'),
        ('ADJUSTMENT', 'Arrears / Adjustment'),
    ]

    line_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    result = models.ForeignKey(PayrollResult, on_delete=models.CASCADE, related_name='lines', db_column='result_id')
    component_id = models.UUIDField(blank=True, null=True)
    line_type = models.CharField(max_length=50, choices=LINE_TYPE_CHOICES)
    code = models.CharField(max_length=50)
    description = models.CharField(max_length=150)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.TextField(blank=True, null=True)
    source_reference = models.CharField(max_length=100, blank=True, null=True)
    formula_reference = models.TextField(blank=True, null=True)
    rule_version = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'security_erp"."payroll_result_lines'
        ordering = ['result', 'line_type', 'code']


class Payslip(models.Model):
    """
    Immutable generated payslip with hash and revision history (PRD 6.8, Entity 15).
    """
    payslip_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payslip_number = models.CharField(max_length=100, unique=True)
    guard_id = models.UUIDField()
    run = models.ForeignKey(PayrollRun, on_delete=models.RESTRICT, db_column='run_id')
    result = models.ForeignKey(PayrollResult, on_delete=models.RESTRICT, db_column='result_id')
    version = models.IntegerField(default=1)
    pdf_reference = models.TextField(blank=True, null=True)
    pdf_hash = models.CharField(max_length=128, blank=True, null=True)
    released_at = models.DateTimeField(auto_now_add=True)
    previous_payslip_id = models.UUIDField(blank=True, null=True)
    is_latest = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'security_erp"."payroll_payslips'
        ordering = ['-released_at']


class PaymentRecord(models.Model):
    """
    External disbursement record with reconciliation, duplicate guards, and reversal (PRD 6.9, Entity 14).
    """
    MODE_CHOICES = [
        ('BANK_TRANSFER', 'Bank Transfer / NEFT / RTGS / IMPS'),
        ('CASH', 'Cash Disbursement'),
        ('CHEQUE', 'Cheque'),
        ('OTHER', 'Other Mode'),
    ]
    STATUS_CHOICES = [
        ('PENDING', 'Pending Confirmation'),
        ('PAID', 'Confirmed Paid'),
        ('FAILED', 'Failed / Returned'),
        ('HELD', 'Intentionally Held'),
        ('REVERSED', 'Reversed with Reason'),
    ]

    payment_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(PayrollRun, on_delete=models.RESTRICT, db_column='run_id')
    result = models.ForeignKey(PayrollResult, on_delete=models.RESTRICT, db_column='result_id')
    guard_id = models.UUIDField()
    payment_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    mode = models.CharField(max_length=30, choices=MODE_CHOICES, default='BANK_TRANSFER')
    bank_reference = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='PENDING')
    failure_reason = models.TextField(blank=True, null=True)
    reversal_reason = models.TextField(blank=True, null=True)
    reversal_of_payment_id = models.UUIDField(blank=True, null=True)
    witness_or_acknowledgement = models.TextField(blank=True, null=True)
    recorded_by = models.UUIDField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'security_erp"."payroll_payments'
        ordering = ['-payment_date', '-created_at']


class FinalSettlement(models.Model):
    """
    Full and final settlement for exiting guards with two-admin approval (PRD 6.10, Entity 17).
    """
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('UNDER_REVIEW', 'Under Review'),
        ('APPROVED', 'Approved by Dual Admins'),
        ('UNCLAIMED', 'Unclaimed / Contact Exhausted'),
        ('PAID', 'Settlement Paid'),
    ]

    settlement_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField()
    guard_id = models.UUIDField()
    exit_date = models.DateField()
    final_payable_days = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    final_pay = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    advance_balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    manual_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    manual_dues = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    settlement_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='DRAFT')
    approver_one = models.UUIDField(blank=True, null=True)
    approver_two = models.UUIDField(blank=True, null=True)
    unclaimed_reason = models.TextField(blank=True, null=True)
    contact_attempts = models.JSONField(default=list)
    statement_file = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'security_erp"."payroll_final_settlements'
        ordering = ['-exit_date']


class StatutoryPayment(models.Model):
    """
    Challan and statutory payment tracker for PF, ESI, PT, LWF (PRD 6.11, Entity 16).
    """
    SCHEME_CHOICES = [
        ('PF', 'Provident Fund (EPF / EPS / EDLI)'),
        ('ESI', 'Employee State Insurance'),
        ('PROFESSIONAL_TAX', 'Professional Tax (PT)'),
        ('LABOUR_WELFARE_FUND', 'Labour Welfare Fund (LWF)'),
    ]
    STATUS_CHOICES = [
        ('DUE', 'Payment Due'),
        ('PAID', 'Challan Paid'),
        ('OVERDUE', 'Payment Overdue'),
    ]

    record_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField()
    scheme = models.CharField(max_length=50, choices=SCHEME_CHOICES)
    period = models.CharField(max_length=50)
    payment_date = models.DateField(blank=True, null=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reference_number = models.CharField(max_length=100, blank=True, null=True)
    paid_by = models.UUIDField(blank=True, null=True)
    proof_file = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='DUE')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'security_erp"."payroll_statutory_payments'
        ordering = ['-created_at']
