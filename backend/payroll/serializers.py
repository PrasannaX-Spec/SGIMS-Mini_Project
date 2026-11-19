from rest_framework import serializers
from .models import (
    SalaryComponent, SalaryStructure, SalaryStructureLine,
    GuardSalaryAssignment, MinimumWage, PaidDayRuleSet,
    WeeklyOffCalendar, StatutoryRuleSet, Advance,
    AdvanceLedgerEntry, ManualDeduction, PayrollRun,
    PayrollResult, PayrollResultLine, Payslip,
    PaymentRecord, FinalSettlement, StatutoryPayment
)


class SalaryComponentSerializer(serializers.ModelSerializer):
    company_id = serializers.UUIDField(read_only=True)
    created_by = serializers.UUIDField(read_only=True)

    class Meta:
        model = SalaryComponent
        fields = '__all__'


class SalaryStructureLineSerializer(serializers.ModelSerializer):
    component_code = serializers.CharField(source='component.component_code', read_only=True)
    component_name = serializers.CharField(source='component.component_name', read_only=True)
    component_type = serializers.CharField(source='component.component_type', read_only=True)
    component_id = serializers.UUIDField(write_only=True, required=False)

    class Meta:
        model = SalaryStructureLine
        fields = '__all__'


class SalaryStructureSerializer(serializers.ModelSerializer):
    company_id = serializers.UUIDField(read_only=True)
    created_by = serializers.UUIDField(read_only=True)
    lines = SalaryStructureLineSerializer(many=True, read_only=True)

    class Meta:
        model = SalaryStructure
        fields = '__all__'


class GuardSalaryAssignmentSerializer(serializers.ModelSerializer):
    company_id = serializers.UUIDField(read_only=True)
    prepared_by = serializers.UUIDField(read_only=True)
    approved_by = serializers.UUIDField(read_only=True)
    structure_name = serializers.CharField(source='structure.name', read_only=True)

    class Meta:
        model = GuardSalaryAssignment
        fields = '__all__'

    def to_internal_value(self, data):
        data = data.copy()
        if 'structure_id' in data and 'structure' not in data:
            data['structure'] = data['structure_id']
        return super().to_internal_value(data)


class MinimumWageSerializer(serializers.ModelSerializer):
    company_id = serializers.UUIDField(read_only=True)
    approved_by = serializers.UUIDField(read_only=True)

    class Meta:
        model = MinimumWage
        fields = '__all__'


class PaidDayRuleSetSerializer(serializers.ModelSerializer):
    company_id = serializers.UUIDField(read_only=True)
    approved_by = serializers.UUIDField(read_only=True)

    class Meta:
        model = PaidDayRuleSet
        fields = '__all__'


class WeeklyOffCalendarSerializer(serializers.ModelSerializer):
    company_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = WeeklyOffCalendar
        fields = '__all__'


class StatutoryRuleSetSerializer(serializers.ModelSerializer):
    company_id = serializers.UUIDField(read_only=True)
    prepared_by = serializers.UUIDField(read_only=True)
    approved_by = serializers.UUIDField(read_only=True)

    class Meta:
        model = StatutoryRuleSet
        fields = '__all__'


class AdvanceLedgerEntrySerializer(serializers.ModelSerializer):
    created_by = serializers.UUIDField(read_only=True)
    approved_by = serializers.UUIDField(read_only=True)

    class Meta:
        model = AdvanceLedgerEntry
        fields = '__all__'


class AdvanceSerializer(serializers.ModelSerializer):
    company_id = serializers.UUIDField(read_only=True)
    created_by = serializers.UUIDField(read_only=True)
    approved_by = serializers.UUIDField(read_only=True)
    ledger_entries = AdvanceLedgerEntrySerializer(many=True, read_only=True)
    current_balance = serializers.SerializerMethodField()

    class Meta:
        model = Advance
        fields = '__all__'

    def get_current_balance(self, obj):
        entries = obj.ledger_entries.all()
        issued = sum(e.amount for e in entries if e.entry_type == 'ISSUE')
        recovered = sum(e.amount for e in entries if e.entry_type in ('RECOVERY', 'WRITE_OFF'))
        adjusted = sum(e.amount for e in entries if e.entry_type == 'ADJUSTMENT')
        return max(0, issued - recovered + adjusted)


class ManualDeductionSerializer(serializers.ModelSerializer):
    company_id = serializers.UUIDField(read_only=True)
    prepared_by = serializers.UUIDField(read_only=True)
    approved_by = serializers.UUIDField(read_only=True)

    class Meta:
        model = ManualDeduction
        fields = '__all__'


class PayrollResultLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayrollResultLine
        fields = '__all__'


class PayrollResultSerializer(serializers.ModelSerializer):
    lines = PayrollResultLineSerializer(many=True, read_only=True)

    class Meta:
        model = PayrollResult
        fields = '__all__'


class PayrollRunSerializer(serializers.ModelSerializer):
    company_id = serializers.UUIDField(read_only=True)
    prepared_by = serializers.UUIDField(read_only=True)
    approved_by = serializers.UUIDField(read_only=True)
    results_count = serializers.IntegerField(source='results.count', read_only=True)

    class Meta:
        model = PayrollRun
        fields = '__all__'


class PayslipSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payslip
        fields = '__all__'


class PaymentRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentRecord
        fields = '__all__'


class FinalSettlementSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinalSettlement
        fields = '__all__'


class StatutoryPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = StatutoryPayment
        fields = '__all__'
