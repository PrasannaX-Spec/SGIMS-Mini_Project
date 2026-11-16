from decimal import Decimal
from rest_framework import serializers
from .models import (
    InvoiceSettings,
    ClientBillingSettings,
    ClientInvoice,
    InvoiceLine,
    ClientPayment,
    ClientPaymentDeduction,
    InvoiceAttendanceAnnexure,
    InvoiceQueryLink,
    InvoiceReminder
)


class InvoiceSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceSettings
        fields = [
            'settings_id',
            'company_id',
            'invoice_prefix',
            'number_format',
            'financial_year_start_month',
            'financial_year_start_day',
            'next_sequence',
            'default_tax_label',
            'default_tax_percentage',
            'rounding_method',
            'rounding_level',
            'default_payment_terms_days',
            'bank_name',
            'account_number',
            'ifsc_code',
            'branch_name',
            'default_notes',
            'second_admin_approval_required',
            'second_admin_approval_threshold',
            'negative_line_approval_threshold',
            'effective_from',
            'effective_to',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['settings_id', 'created_at', 'updated_at']


class ClientBillingSettingsSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(read_only=True, required=False)
    site_name = serializers.CharField(read_only=True, required=False)

    class Meta:
        model = ClientBillingSettings
        fields = [
            'settings_id',
            'company_id',
            'client_id',
            'client_name',
            'site_id',
            'site_name',
            'billing_basis',
            'billing_unit',
            'proration_method',
            'invoice_grouping',
            'payment_terms_days',
            'po_wo_number',
            'po_wo_validity_start',
            'po_wo_validity_end',
            'billing_contact_id',
            'tax_override_enabled',
            'tax_label',
            'tax_percentage',
            'tax_inclusive',
            'overtime_billable',
            'extra_duty_billable',
            'manual_attendance_confirmation',
            'is_active',
            'effective_from',
            'effective_to',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['settings_id', 'created_at', 'updated_at']


class InvoiceLineSerializer(serializers.ModelSerializer):
    site_name = serializers.CharField(read_only=True, required=False)
    post_type_name = serializers.CharField(read_only=True, required=False)

    class Meta:
        model = InvoiceLine
        fields = [
            'invoice_line_id',
            'invoice_id',
            'site_id',
            'site_name',
            'post_type_id',
            'post_type_name',
            'shift_id',
            'description',
            'source_type',
            'source_reference',
            'quantity',
            'unit',
            'unit_rate',
            'tax_rate',
            'line_amount',
            'effective_rate_start',
            'effective_rate_end',
            'requirement_version',
            'manual_reason',
            'client_visible_description',
            'is_negative',
            'created_at'
        ]
        read_only_fields = ['invoice_line_id', 'created_at']


class ClientPaymentDeductionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientPaymentDeduction
        fields = [
            'deduction_id',
            'payment_id',
            'invoice_id',
            'deduction_type',
            'amount',
            'reason',
            'notes',
            'created_at'
        ]
        read_only_fields = ['deduction_id', 'created_at']


class ClientPaymentSerializer(serializers.ModelSerializer):
    deductions = ClientPaymentDeductionSerializer(many=True, read_only=True)
    created_by_name = serializers.CharField(read_only=True, required=False)

    class Meta:
        model = ClientPayment
        fields = [
            'client_payment_id',
            'company_id',
            'client_id',
            'invoice_id',
            'payment_date',
            'amount',
            'payment_method',
            'reference_no',
            'notes',
            'status',
            'reversal_reason',
            'reversed_at',
            'reversed_by',
            'unallocated_amount',
            'created_by',
            'created_by_name',
            'created_at',
            'deductions'
        ]
        read_only_fields = ['client_payment_id', 'created_at']


class InvoiceAttendanceAnnexureSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceAttendanceAnnexure
        fields = [
            'annexure_id',
            'invoice_id',
            'site_id',
            'duty_date',
            'shift_id',
            'shift_name',
            'post_slot_id',
            'post_type_id',
            'post_type_name',
            'guard_id',
            'guard_name',
            'coverage_status',
            'is_manual',
            'regular_minutes',
            'overtime_minutes',
            'is_billed',
            'deduction_applied',
            'created_at'
        ]
        read_only_fields = ['annexure_id', 'created_at']


class ClientInvoiceListSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(read_only=True, required=False)
    client_code = serializers.CharField(read_only=True, required=False)

    class Meta:
        model = ClientInvoice
        fields = [
            'invoice_id',
            'company_id',
            'client_id',
            'client_name',
            'client_code',
            'draft_reference',
            'invoice_no',
            'invoice_date',
            'due_date',
            'period_start',
            'period_end',
            'invoice_type',
            'subtotal',
            'taxable_amount',
            'tax_amount',
            'total_amount',
            'paid_amount',
            'deduction_amount',
            'outstanding_amount',
            'status',
            'overdue_flag',
            'under_query_flag',
            'source_changed',
            'created_at'
        ]


class ClientInvoiceDetailSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(read_only=True, required=False)
    client_gstin = serializers.CharField(read_only=True, required=False)
    client_pan = serializers.CharField(read_only=True, required=False)
    client_address = serializers.CharField(read_only=True, required=False)
    company_name = serializers.CharField(read_only=True, required=False)
    company_gstin = serializers.CharField(read_only=True, required=False)
    company_address = serializers.CharField(read_only=True, required=False)
    lines = InvoiceLineSerializer(many=True, read_only=True)
    payments = ClientPaymentSerializer(many=True, read_only=True)
    total_in_words = serializers.CharField(read_only=True, required=False)

    class Meta:
        model = ClientInvoice
        fields = [
            'invoice_id',
            'company_id',
            'company_name',
            'company_gstin',
            'company_address',
            'client_id',
            'client_name',
            'client_gstin',
            'client_pan',
            'client_address',
            'contract_id',
            'site_id',
            'draft_reference',
            'invoice_no',
            'invoice_date',
            'due_date',
            'period_start',
            'period_end',
            'invoice_type',
            'subtotal',
            'taxable_amount',
            'discount_amount',
            'tax_amount',
            'total_amount',
            'paid_amount',
            'deduction_amount',
            'outstanding_amount',
            'status',
            'overdue_flag',
            'under_query_flag',
            'pdf_file_reference',
            'pdf_hash',
            'source_snapshot',
            'source_changed',
            'source_change_details',
            'cancelled_reason',
            'client_visible_cancellation_reason',
            'replacement_invoice_id',
            'original_invoice_id',
            'is_unlocked_period_override',
            'unlocked_period_reason',
            'pending_attendance_count',
            'internal_notes',
            'notes',
            'annexure_file_reference',
            'annexure_hash',
            'created_by',
            'approved_by',
            'approved_at',
            'issued_by',
            'issued_at',
            'cancelled_by',
            'cancelled_at',
            'created_at',
            'lines',
            'payments',
            'total_in_words'
        ]

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        request = self.context.get('request')
        user = getattr(request, 'user', None)

        # Sanitize for Client role (PRD 2.4, 6.14, AC-11.63)
        if user and getattr(user, 'role', '') == 'CLIENT':
            ret.pop('internal_notes', None)
            ret.pop('source_snapshot', None)
            ret.pop('source_change_details', None)
            ret.pop('is_unlocked_period_override', None)
            ret.pop('unlocked_period_reason', None)
            ret.pop('pending_attendance_count', None)
            ret.pop('approved_by', None)
            ret.pop('created_by', None)
            # Hide internal cancellation reason if client-visible reason is set
            ret['cancelled_reason'] = instance.client_visible_cancellation_reason or 'Invoice cancelled by administration.'
            # Filter internal manual reasons from lines
            for line in ret.get('lines', []):
                line.pop('manual_reason', None)
                if line.get('client_visible_description'):
                    line['description'] = line['client_visible_description']
        return ret


class ManualLineCreateSerializer(serializers.Serializer):
    description = serializers.CharField(max_length=255)
    site_id = serializers.UUIDField(required=False, allow_null=True)
    quantity = serializers.DecimalField(max_digits=12, decimal_places=2, default=Decimal('1.00'))
    unit = serializers.CharField(max_length=30, default='MANUAL')
    unit_rate = serializers.DecimalField(max_digits=12, decimal_places=2)
    tax_rate = serializers.DecimalField(max_digits=5, decimal_places=2, default=Decimal('18.00'))
    manual_reason = serializers.CharField(required=True)
    client_visible_description = serializers.CharField(required=False, allow_blank=True)
    is_negative = serializers.BooleanField(default=False)

    def validate(self, data):
        if data.get('is_negative') and not data.get('manual_reason'):
            raise serializers.ValidationError({"manual_reason": "A reason is mandatory for negative adjustments (PRD 6.5, AC-11.28)."})
        return data


class PaymentRecordRequestSerializer(serializers.Serializer):
    payment_date = serializers.DateField(required=True)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    payment_method = serializers.ChoiceField(choices=['BANK_TRANSFER', 'CHEQUE', 'CASH', 'OTHER'])
    reference_no = serializers.CharField(max_length=100, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    tds_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=Decimal('0.00'))
    other_deduction_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=Decimal('0.00'))
    other_deduction_reason = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        other_deduction = data.get('other_deduction_amount') or Decimal('0.00')
        if other_deduction > 0 and not data.get('other_deduction_reason'):
            raise serializers.ValidationError({"other_deduction_reason": "Reason is mandatory when recording other client deductions (PRD 6.11, AC-11.52)."})
        return data


class PaymentReversalSerializer(serializers.Serializer):
    reversal_reason = serializers.CharField(required=True)


class InvoiceCancelRequestSerializer(serializers.Serializer):
    cancelled_reason = serializers.CharField(required=True)
    client_visible_cancellation_reason = serializers.CharField(required=False, allow_blank=True)


class InvoiceQueryCreateSerializer(serializers.Serializer):
    query_category = serializers.CharField(max_length=50, default='INVOICE_QUERY')
    query_description = serializers.CharField(required=True)
