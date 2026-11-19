from rest_framework import serializers
from .models import (
    ReportDefinition, MetricDefinition, MetricDefinitionVersion,
    SummarySnapshot, SavedFilterPreset, ReportGenerationRecord,
    ClientMonthlySummary, ReportReconciliation
)


class ReportDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportDefinition
        fields = [
            'report_id', 'company_id', 'report_number', 'code', 'name',
            'description', 'category', 'audience', 'sensitivity',
            'export_formats', 'is_enabled', 'created_at', 'updated_at'
        ]


class MetricDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MetricDefinition
        fields = [
            'metric_id', 'company_id', 'name', 'definition', 'formula',
            'numerator_desc', 'denominator_desc', 'source_module',
            'source_fields', 'period_basis', 'inclusion_rules',
            'exclusion_rules', 'manual_offline_handling', 'unit',
            'rounding_rule', 'visibility', 'current_version', 'is_active',
            'created_at', 'updated_at'
        ]


class MetricDefinitionVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MetricDefinitionVersion
        fields = [
            'version_id', 'metric_id', 'version_number', 'effective_date',
            'changed_by_user_id', 'definition_snapshot', 'change_reason', 'created_at'
        ]


class SavedFilterPresetSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedFilterPreset
        fields = [
            'preset_id', 'company_id', 'user_id', 'report_code',
            'name', 'filter_params', 'created_at', 'updated_at'
        ]
        read_only_fields = ['preset_id', 'company_id', 'user_id', 'created_at', 'updated_at']


class ReportGenerationRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportGenerationRecord
        fields = [
            'job_id', 'company_id', 'user_id', 'report_code',
            'filters', 'status', 'as_of_time', 'definition_versions',
            'content_hash', 'row_count', 'file_format', 'file_path',
            'file_size_bytes', 'error_message', 'bulk_reason',
            'expires_at', 'created_at', 'completed_at'
        ]


class ClientMonthlySummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientMonthlySummary
        fields = [
            'summary_id', 'company_id', 'client_id', 'period_month',
            'period_year', 'version_number', 'status', 'previous_version_id',
            'summary_data', 'content_hash', 'generated_by_user_id',
            'released_by_user_id', 'released_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['summary_id', 'company_id', 'version_number', 'content_hash', 'created_at', 'updated_at']


class ReportReconciliationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportReconciliation
        fields = [
            'reconciliation_id', 'company_id', 'metric_id', 'period_start',
            'period_end', 'expected_value', 'calculated_value', 'status',
            'details', 'checked_at', 'resolved_at'
        ]
