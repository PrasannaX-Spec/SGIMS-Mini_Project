import uuid
from decimal import Decimal
from django.db import models


class InvoiceSettings(models.Model):
    """
    Company-level invoice configuration (PRD 12.1, FR-11.1 to FR-11.14).
    """
    settings_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    company_id = models.UUIDField()
    invoice_prefix = models.CharField(max_length=30, default='INV')
    number_format = models.CharField(max_length=100, default='{PREFIX}/{FY}/{SEQ:04d}')
    financial_year_start_month = models.IntegerField(default=4)
    financial_year_start_day = models.IntegerField(default=1)
    next_sequence = models.IntegerField(default=1)
    default_tax_label = models.CharField(max_length=50, default='GST')
    default_tax_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('18.00'))
    rounding_method = models.CharField(
        max_length=30,
        choices=[
            ('ROUND_HALF_UP', 'Round Half Up'),
            ('ROUND_HALF_EVEN', 'Round Half Even (Bankers)'),
            ('CEILING', 'Ceiling'),
            ('FLOOR', 'Floor')
        ],
        default='ROUND_HALF_UP'
    )
    rounding_level = models.CharField(
        max_length=20,
        choices=[('TOTAL', 'Total Level'), ('LINE', 'Line Level')],
        default='TOTAL'
    )
    default_payment_terms_days = models.IntegerField(default=30)
    bank_name = models.CharField(max_length=150, blank=True, null=True)
    account_number = models.CharField(max_length=50, blank=True, null=True)
    ifsc_code = models.CharField(max_length=20, blank=True, null=True)
    branch_name = models.CharField(max_length=150, blank=True, null=True)
    default_notes = models.TextField(blank=True, null=True)
    second_admin_approval_required = models.BooleanField(default=False)
    second_admin_approval_threshold = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('50000.00'))
    negative_line_approval_threshold = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('5000.00'))
    effective_from = models.DateField()
    effective_to = models.DateField(blank=True, null=True)
    created_by = models.UUIDField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'security_erp"."invoice_settings'


class ClientBillingSettings(models.Model):
    """
    Client and site-level billing arrangements (PRD 12.2, FR-11.15 to FR-11.30).
    """
    BASIS_CHOICES = [
        ('FIXED_MONTHLY', 'Fixed Monthly Billing'),
        ('FIXED_MINUS_DEDUCTIONS', 'Fixed Monthly Minus Deductions'),
        ('ATTENDANCE_BASED', 'Attendance-Based Billing')
    ]
    UNIT_CHOICES = [
        ('PER_MONTH', 'Per Guard Per Month'),
        ('PER_DAY', 'Per Guard Per Day'),
        ('PER_SHIFT', 'Per Guard Per Shift')
    ]
    PRORATION_CHOICES = [
        ('CALENDAR_DAY', 'Calendar Day Proration'),
        ('DUTY_DAY', 'Actual Duty Day Proration'),
        ('FULL_MONTH', 'Full Month Billing')
    ]
    GROUPING_CHOICES = [
        ('ONE_PER_CLIENT', 'One Invoice Per Client (with Site Sections)'),
        ('ONE_PER_SITE', 'One Invoice Per Site')
    ]

    settings_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    company_id = models.UUIDField()
    client_id = models.UUIDField()
    site_id = models.UUIDField(blank=True, null=True)
    billing_basis = models.CharField(max_length=40, choices=BASIS_CHOICES, default='ATTENDANCE_BASED')
    billing_unit = models.CharField(max_length=30, choices=UNIT_CHOICES, default='PER_DAY')
    proration_method = models.CharField(max_length=30, choices=PRORATION_CHOICES, default='CALENDAR_DAY')
    invoice_grouping = models.CharField(max_length=30, choices=GROUPING_CHOICES, default='ONE_PER_CLIENT')
    payment_terms_days = models.IntegerField(default=30)
    po_wo_number = models.CharField(max_length=100, blank=True, null=True)
    po_wo_validity_start = models.DateField(blank=True, null=True)
    po_wo_validity_end = models.DateField(blank=True, null=True)
    billing_contact_id = models.UUIDField(blank=True, null=True)
    tax_override_enabled = models.BooleanField(default=False)
    tax_label = models.CharField(max_length=50, blank=True, null=True)
    tax_percentage = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    tax_inclusive = models.BooleanField(default=False)
    overtime_billable = models.BooleanField(default=False)
    extra_duty_billable = models.BooleanField(default=False)
    manual_attendance_confirmation = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    effective_from = models.DateField()
    effective_to = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'security_erp"."client_billing_settings'


class InvoiceNumberSequence(models.Model):
    """
    Thread-safe sequential invoice number generator (PRD 12.9, FR-11.3).
    """
    sequence_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    company_id = models.UUIDField()
    series_code = models.CharField(max_length=50, default='DEFAULT')
    financial_year = models.CharField(max_length=20)
    last_number = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'security_erp"."invoice_number_sequences'
        unique_together = ('company_id', 'series_code', 'financial_year')


class ClientInvoice(models.Model):
    """
    Client Invoice Entity (PRD 12.3, Section 10).
    """
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PENDING_APPROVAL', 'Pending Second Admin Approval'),
        ('SENT', 'Sent (Issued)'),
        ('PARTIALLY_PAID', 'Partially Paid'),
        ('PAID', 'Fully Paid'),
        ('CANCELLED', 'Cancelled')
    ]

    invoice_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    company_id = models.UUIDField()
    client_id = models.UUIDField()
    contract_id = models.UUIDField(blank=True, null=True)
    site_id = models.UUIDField(blank=True, null=True)
    draft_reference = models.CharField(max_length=100, unique=True, blank=True, null=True)
    invoice_no = models.CharField(max_length=100, blank=True, null=True)
    invoice_date = models.DateField(blank=True, null=True)
    due_date = models.DateField(blank=True, null=True)
    period_start = models.DateField()
    period_end = models.DateField()
    invoice_type = models.CharField(max_length=50, default='service')
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    taxable_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    deduction_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    outstanding_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='DRAFT')
    overdue_flag = models.BooleanField(default=False)
    under_query_flag = models.BooleanField(default=False)
    pdf_file_reference = models.TextField(blank=True, null=True)
    pdf_hash = models.CharField(max_length=128, blank=True, null=True)
    source_snapshot = models.JSONField(default=dict)
    source_changed = models.BooleanField(default=False)
    source_change_details = models.JSONField(default=dict)
    cancelled_reason = models.TextField(blank=True, null=True)
    client_visible_cancellation_reason = models.TextField(blank=True, null=True)
    replacement_invoice_id = models.UUIDField(blank=True, null=True)
    original_invoice_id = models.UUIDField(blank=True, null=True)
    is_unlocked_period_override = models.BooleanField(default=False)
    unlocked_period_reason = models.TextField(blank=True, null=True)
    pending_attendance_count = models.IntegerField(default=0)
    internal_notes = models.TextField(blank=True, null=True)
    annexure_file_reference = models.TextField(blank=True, null=True)
    annexure_hash = models.CharField(max_length=128, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_by = models.UUIDField(blank=True, null=True)
    approved_by = models.UUIDField(blank=True, null=True)
    approved_at = models.DateTimeField(blank=True, null=True)
    issued_by = models.UUIDField(blank=True, null=True)
    issued_at = models.DateTimeField(blank=True, null=True)
    cancelled_by = models.UUIDField(blank=True, null=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'security_erp"."client_invoices'

    @property
    def is_issued(self):
        return self.status in ['SENT', 'PARTIALLY_PAID', 'PAID', 'CANCELLED']


class InvoiceLine(models.Model):
    """
    Individual billable, manual, or adjustment invoice line (PRD 12.4).
    """
    SOURCE_TYPES = [
        ('ATTENDANCE', 'Attendance Calculation'),
        ('MANUAL', 'Manual Charge/Adjustment'),
        ('EXTRA_DUTY', 'Classified Extra Duty'),
        ('DEDUCTION', 'Contractual Deduction')
    ]
    UNIT_TYPES = [
        ('PER_MONTH', 'Per Month'),
        ('PER_DAY', 'Per Day'),
        ('PER_SHIFT', 'Per Shift'),
        ('MANUAL', 'Manual Item')
    ]

    invoice_line_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    invoice_id = models.UUIDField()
    site_id = models.UUIDField(blank=True, null=True)
    post_type_id = models.UUIDField(blank=True, null=True)
    shift_id = models.UUIDField(blank=True, null=True)
    description = models.CharField(max_length=255)
    source_type = models.CharField(max_length=30, choices=SOURCE_TYPES, default='ATTENDANCE')
    source_reference = models.TextField(blank=True, null=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('1.00'))
    unit = models.CharField(max_length=30, choices=UNIT_TYPES, default='PER_DAY')
    unit_rate = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    line_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    effective_rate_start = models.DateField(blank=True, null=True)
    effective_rate_end = models.DateField(blank=True, null=True)
    requirement_version = models.IntegerField(blank=True, null=True)
    manual_reason = models.TextField(blank=True, null=True)
    client_visible_description = models.TextField(blank=True, null=True)
    is_negative = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'security_erp"."invoice_lines'


class ClientPayment(models.Model):
    """
    Client payment record (PRD 12.5, 6.11).
    """
    PAYMENT_MODES = [
        ('BANK_TRANSFER', 'Bank Transfer / NEFT / RTGS'),
        ('CHEQUE', 'Cheque'),
        ('CASH', 'Cash'),
        ('OTHER', 'Other Mode')
    ]
    PAYMENT_STATUS = [
        ('ACTIVE', 'Active'),
        ('REVERSED', 'Reversed')
    ]

    client_payment_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    company_id = models.UUIDField()
    client_id = models.UUIDField()
    invoice_id = models.UUIDField()
    payment_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=50, choices=PAYMENT_MODES)
    reference_no = models.CharField(max_length=100, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='ACTIVE')
    reversal_reason = models.TextField(blank=True, null=True)
    reversed_at = models.DateTimeField(blank=True, null=True)
    reversed_by = models.UUIDField(blank=True, null=True)
    unallocated_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    created_by = models.UUIDField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'security_erp"."client_payments'


class ClientPaymentDeduction(models.Model):
    """
    TDS and other client deductions recorded with payment (PRD 12.6).
    """
    DEDUCTION_TYPES = [
        ('TDS', 'Tax Deducted at Source (TDS)'),
        ('OTHER', 'Other Client Deduction')
    ]

    deduction_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    payment_id = models.UUIDField()
    invoice_id = models.UUIDField()
    deduction_type = models.CharField(max_length=20, choices=DEDUCTION_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'security_erp"."client_payment_deductions'


class InvoiceAttendanceAnnexure(models.Model):
    """
    Attendance annexure item reconciling invoice billed post quantities (PRD 12.8, 6.13).
    """
    COVERAGE_CHOICES = [
        ('COVERED', 'Covered and Approved'),
        ('UNCOVERED', 'Uncovered Vacancy'),
        ('EXTRA_DUTY', 'Extra Unplanned Duty'),
        ('REPLACEMENT', 'Replacement Reliever Duty')
    ]

    annexure_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    invoice_id = models.UUIDField()
    site_id = models.UUIDField()
    duty_date = models.DateField()
    shift_id = models.UUIDField(blank=True, null=True)
    shift_name = models.CharField(max_length=100, blank=True, null=True)
    post_slot_id = models.UUIDField(blank=True, null=True)
    post_type_id = models.UUIDField(blank=True, null=True)
    post_type_name = models.CharField(max_length=100, blank=True, null=True)
    guard_id = models.UUIDField(blank=True, null=True)
    guard_name = models.CharField(max_length=150, blank=True, null=True)
    coverage_status = models.CharField(max_length=30, choices=COVERAGE_CHOICES)
    is_manual = models.BooleanField(default=False)
    regular_minutes = models.IntegerField(default=0)
    overtime_minutes = models.IntegerField(default=0)
    is_billed = models.BooleanField(default=True)
    deduction_applied = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'security_erp"."invoice_attendance_annexures'


class InvoiceQueryLink(models.Model):
    """
    Module 8 ticket reference linked to an invoice (PRD 12.8, 6.14).
    """
    query_link_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    invoice_id = models.UUIDField()
    ticket_id = models.UUIDField()
    client_id = models.UUIDField()
    query_category = models.CharField(max_length=50, blank=True, null=True)
    status = models.CharField(max_length=30, default='OPEN')
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'security_erp"."invoice_query_links'


class InvoiceReminder(models.Model):
    """
    Payment reminder history (PRD 6.12, 11.10).
    """
    REMINDER_TYPES = [
        ('BEFORE_DUE', 'Upcoming Due Reminder'),
        ('DUE_DATE', 'Due Today Reminder'),
        ('OVERDUE', 'Overdue Follow-up Reminder')
    ]

    reminder_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    invoice_id = models.UUIDField()
    client_id = models.UUIDField()
    reminder_type = models.CharField(max_length=30, choices=REMINDER_TYPES)
    sent_at = models.DateTimeField(auto_now_add=True)
    sent_to_contact_id = models.UUIDField(blank=True, null=True)
    status = models.CharField(max_length=30, default='SENT')
    notes = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'security_erp"."invoice_reminders'
