import uuid
from django.db import models
from django.utils import timezone
from django.contrib.postgres.fields import ArrayField


class ReportDefinition(models.Model):
    report_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField()
    report_number = models.IntegerField()
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    category = models.CharField(max_length=50)
    audience = models.CharField(max_length=50)
    sensitivity = models.CharField(max_length=50, default='INTERNAL')
    export_formats = ArrayField(models.CharField(max_length=20), default=list)
    is_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = 'security_erp"."report_definitions'
        ordering = ['report_number']

    def __str__(self):
        return f"{self.report_number}. {self.name} ({self.code})"


class MetricDefinition(models.Model):
    metric_id = models.CharField(primary_key=True, max_length=10) # 'M01' - 'M81'
    company_id = models.UUIDField(blank=True, null=True)
    name = models.CharField(max_length=150)
    definition = models.TextField()
    formula = models.TextField()
    numerator_desc = models.TextField(blank=True, null=True)
    denominator_desc = models.TextField(blank=True, null=True)
    source_module = models.CharField(max_length=10)
    source_fields = models.TextField()
    period_basis = models.CharField(max_length=50)
    inclusion_rules = models.TextField(blank=True, null=True)
    exclusion_rules = models.TextField(blank=True, null=True)
    manual_offline_handling = models.TextField(blank=True, null=True)
    unit = models.CharField(max_length=50)
    rounding_rule = models.CharField(max_length=50, default='2_DECIMALS')
    visibility = models.CharField(max_length=50, default='ADMIN_SUPERVISOR')
    current_version = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = 'security_erp"."metric_definitions'
        ordering = ['metric_id']

    def __str__(self):
        return f"[{self.metric_id}] {self.name}"


class MetricDefinitionVersion(models.Model):
    version_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    metric_id = models.CharField(max_length=10)
    version_number = models.IntegerField()
    effective_date = models.DateField(default=timezone.now)
    changed_by_user_id = models.UUIDField(blank=True, null=True)
    definition_snapshot = models.JSONField()
    change_reason = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = 'security_erp"."metric_definition_versions'
        ordering = ['metric_id', '-version_number']


class SummarySnapshot(models.Model):
    summary_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField()
    metric_id = models.CharField(max_length=10)
    period_start = models.DateField()
    period_end = models.DateField()
    site_id = models.UUIDField(blank=True, null=True)
    client_id = models.UUIDField(blank=True, null=True)
    filters = models.JSONField(default=dict)
    calculated_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    data_quality_notes = models.JSONField(default=dict)
    as_of_time = models.DateTimeField(default=timezone.now)
    is_valid = models.BooleanField(default=True)
    definition_version = models.IntegerField(default=1)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = 'security_erp"."summary_snapshots'
        ordering = ['-as_of_time']


class SavedFilterPreset(models.Model):
    preset_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField()
    user_id = models.UUIDField()
    report_code = models.CharField(max_length=50)
    name = models.CharField(max_length=100)
    filter_params = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = 'security_erp"."saved_filter_presets'
        ordering = ['-updated_at']


class ReportGenerationRecord(models.Model):
    job_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField()
    user_id = models.UUIDField()
    report_code = models.CharField(max_length=50)
    filters = models.JSONField(default=dict)
    status = models.CharField(max_length=30, default='COMPLETED')
    as_of_time = models.DateTimeField(default=timezone.now)
    definition_versions = models.JSONField(default=dict)
    content_hash = models.CharField(max_length=64, blank=True, null=True)
    row_count = models.IntegerField(default=0)
    file_format = models.CharField(max_length=10)
    file_path = models.TextField(blank=True, null=True)
    file_size_bytes = models.BigIntegerField(default=0)
    error_message = models.TextField(blank=True, null=True)
    bulk_reason = models.TextField(blank=True, null=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'security_erp"."report_generation_records'
        ordering = ['-created_at']


class ClientMonthlySummary(models.Model):
    summary_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField()
    client_id = models.UUIDField()
    period_month = models.IntegerField()
    period_year = models.IntegerField()
    version_number = models.IntegerField(default=1)
    status = models.CharField(max_length=20, default='DRAFT')
    previous_version_id = models.UUIDField(blank=True, null=True)
    summary_data = models.JSONField(default=dict)
    content_hash = models.CharField(max_length=64, blank=True, null=True)
    generated_by_user_id = models.UUIDField(blank=True, null=True)
    released_by_user_id = models.UUIDField(blank=True, null=True)
    released_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = 'security_erp"."client_monthly_summaries'
        ordering = ['period_year', 'period_month', '-version_number']


class ReportReconciliation(models.Model):
    reconciliation_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField()
    metric_id = models.CharField(max_length=10)
    period_start = models.DateField()
    period_end = models.DateField()
    expected_value = models.DecimalField(max_digits=15, decimal_places=2)
    calculated_value = models.DecimalField(max_digits=15, decimal_places=2)
    status = models.CharField(max_length=20, default='MATCH')
    details = models.JSONField(default=dict)
    checked_at = models.DateTimeField(default=timezone.now)
    resolved_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'security_erp"."report_reconciliations'
        ordering = ['-checked_at']


class SummaryInvalidation(models.Model):
    invalidation_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField()
    source_module = models.CharField(max_length=50)
    source_record_id = models.CharField(max_length=100, blank=True, null=True)
    affected_periods = models.JSONField(default=list)
    invalidation_time = models.DateTimeField(default=timezone.now)
    is_processed = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = 'security_erp"."summary_invalidations'
        ordering = ['-invalidation_time']
