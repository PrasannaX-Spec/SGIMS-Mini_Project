import uuid
from django.db import models
from foundation.models import Company, User, ConsentRecord
from master_data.models import ClientSite, SiteShift
from guard_management.models import Employee
from deployment_roster.models import RosterAssignment
from attendance.models import AttendanceRecord


class MonitoringDuty(models.Model):
    TRACKING_STATES = (
        ('ACTIVE', 'Active Tracking'),
        ('NOT_TRACKED', 'Not Tracked (No Consent/Unavailable)'),
        ('STOPPED', 'Stopped'),
    )

    duty_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='company_id', related_name='monitoring_duties')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, db_column='employee_id', related_name='monitoring_duties')
    assignment = models.ForeignKey(RosterAssignment, on_delete=models.CASCADE, db_column='assignment_id', related_name='monitoring_duties')
    site = models.ForeignKey(ClientSite, on_delete=models.RESTRICT, db_column='site_id', related_name='monitoring_duties')
    shift = models.ForeignKey(SiteShift, on_delete=models.RESTRICT, db_column='shift_id', related_name='monitoring_duties')
    attendance_record = models.ForeignKey(AttendanceRecord, on_delete=models.SET_NULL, null=True, blank=True, db_column='attendance_record_id', related_name='monitoring_duties')
    duty_start_at = models.DateTimeField()
    duty_end_at = models.DateTimeField(null=True, blank=True)
    tracking_start_at = models.DateTimeField(null=True, blank=True)
    tracking_end_at = models.DateTimeField(null=True, blank=True)
    consent_record = models.ForeignKey(ConsentRecord, on_delete=models.SET_NULL, null=True, blank=True, db_column='consent_record_id')
    consent_policy_version = models.CharField(max_length=50, null=True, blank=True)
    tracking_state = models.CharField(max_length=20, choices=TRACKING_STATES, default='ACTIVE')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'monitoring_duties'
        unique_together = (('company', 'assignment'),)

    def __str__(self):
        return f"Duty {self.duty_id} - {self.employee.full_name} ({self.tracking_state})"


class LocationPoint(models.Model):
    CHARGING_STATES = (
        ('CHARGING', 'Charging'),
        ('NOT_CHARGING', 'Not Charging'),
        ('UNKNOWN', 'Unknown'),
    )

    point_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='company_id', related_name='location_points')
    duty = models.ForeignKey(MonitoringDuty, on_delete=models.CASCADE, db_column='duty_id', related_name='location_points')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, db_column='employee_id', related_name='location_points')
    assignment = models.ForeignKey(RosterAssignment, on_delete=models.CASCADE, db_column='assignment_id', related_name='location_points')
    client_generated_id = models.UUIDField()
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    accuracy_m = models.DecimalField(max_digits=8, decimal_places=2)
    device_captured_at = models.DateTimeField()
    server_received_at = models.DateTimeField(auto_now_add=True)
    mock_location = models.BooleanField(default=False)
    battery_percent = models.IntegerField(null=True, blank=True)
    charging_state = models.CharField(max_length=20, choices=CHARGING_STATES, null=True, blank=True)
    network_type = models.CharField(max_length=20, null=True, blank=True)
    app_version = models.CharField(max_length=50, null=True, blank=True)
    location_permission = models.CharField(max_length=30, null=True, blank=True)
    battery_optimization_state = models.CharField(max_length=30, null=True, blank=True)
    sequence_number = models.IntegerField(null=True, blank=True)
    accepted = models.BooleanField(default=True)
    rejection_reason = models.TextField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'location_points'
        unique_together = (('company', 'employee', 'client_generated_id'),)


class Heartbeat(models.Model):
    CHARGING_STATES = (
        ('CHARGING', 'Charging'),
        ('NOT_CHARGING', 'Not Charging'),
        ('UNKNOWN', 'Unknown'),
    )

    heartbeat_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='company_id', related_name='heartbeats')
    duty = models.ForeignKey(MonitoringDuty, on_delete=models.CASCADE, db_column='duty_id', related_name='heartbeats')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, db_column='employee_id', related_name='heartbeats')
    client_generated_id = models.UUIDField()
    captured_at = models.DateTimeField()
    received_at = models.DateTimeField(auto_now_add=True)
    battery_percent = models.IntegerField(null=True, blank=True)
    charging_state = models.CharField(max_length=20, choices=CHARGING_STATES, null=True, blank=True)
    network_type = models.CharField(max_length=20, null=True, blank=True)
    app_version = models.CharField(max_length=50, null=True, blank=True)
    permission_state = models.CharField(max_length=30, null=True, blank=True)
    sequence_number = models.IntegerField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'heartbeats'
        unique_together = (('company', 'employee', 'client_generated_id'),)


class GuardMonitoringStatus(models.Model):
    PRIMARY_STATUSES = (
        ('not_started', 'Not Started'),
        ('on_duty_at_site', 'On Duty at Site'),
        ('on_duty_outside_site', 'On Duty Outside Site'),
        ('stale', 'Low Signal or Stale'),
        ('no_contact', 'No Contact'),
        ('off_duty', 'Off Duty'),
        ('not_tracked', 'Not Tracked'),
    )

    status_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='company_id', related_name='monitoring_statuses')
    duty = models.OneToOneField(MonitoringDuty, on_delete=models.CASCADE, db_column='duty_id', related_name='monitoring_status')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, db_column='employee_id', related_name='monitoring_statuses')
    assignment = models.ForeignKey(RosterAssignment, on_delete=models.CASCADE, db_column='assignment_id', related_name='monitoring_statuses')
    site = models.ForeignKey(ClientSite, on_delete=models.RESTRICT, db_column='site_id', related_name='monitoring_statuses')
    primary_status = models.CharField(max_length=30, choices=PRIMARY_STATUSES, default='on_duty_at_site')
    has_active_alert = models.BooleanField(default=False)
    display_status = models.CharField(max_length=50, default='On Duty at Site')
    consecutive_outside_count = models.IntegerField(default=0)
    last_location_point = models.ForeignKey(LocationPoint, on_delete=models.SET_NULL, null=True, blank=True, db_column='last_location_point_id')
    last_heartbeat = models.ForeignKey(Heartbeat, on_delete=models.SET_NULL, null=True, blank=True, db_column='last_heartbeat_id')
    last_communication_at = models.DateTimeField(null=True, blank=True)
    status_calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'guard_monitoring_statuses'


class MonitoringStatusHistory(models.Model):
    history_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='company_id', related_name='monitoring_status_histories')
    duty = models.ForeignKey(MonitoringDuty, on_delete=models.CASCADE, db_column='duty_id', related_name='status_histories')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, db_column='employee_id', related_name='monitoring_status_histories')
    previous_status = models.CharField(max_length=30, null=True, blank=True)
    new_status = models.CharField(max_length=30)
    trigger_type = models.CharField(max_length=50)
    related_location = models.ForeignKey(LocationPoint, on_delete=models.SET_NULL, null=True, blank=True, db_column='related_location_id')
    changed_at = models.DateTimeField()
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'monitoring_status_history'


class AlertRule(models.Model):
    SEVERITIES = (
        ('NORMAL', 'Normal'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    )

    rule_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='company_id', related_name='alert_rules')
    rule_name = models.CharField(max_length=100)
    rule_code = models.CharField(max_length=50)
    enabled = models.BooleanField(default=True)
    threshold_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    threshold_unit = models.CharField(max_length=30, null=True, blank=True)
    severity = models.CharField(max_length=20, choices=SEVERITIES, default='NORMAL')
    recipient_policy = models.CharField(max_length=50, default='PRIMARY_SUPERVISOR')
    cooldown_seconds = models.IntegerField(default=900)
    escalation_policy = models.JSONField(null=True, blank=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, db_column='updated_by')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'alert_rules'
        unique_together = (('company', 'rule_code'),)


class MonitoringAlert(models.Model):
    SEVERITIES = (
        ('NORMAL', 'Normal'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    )
    STATES = (
        ('RAISED', 'Raised'),
        ('ACKNOWLEDGED', 'Acknowledged'),
        ('RESOLVED', 'Resolved'),
        ('AUTO_RESOLVED', 'Auto Resolved'),
        ('DISMISSED', 'Dismissed (False Alarm)'),
    )

    alert_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='company_id', related_name='monitoring_alerts')
    duty = models.ForeignKey(MonitoringDuty, on_delete=models.CASCADE, db_column='duty_id', related_name='monitoring_alerts')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, db_column='employee_id', related_name='monitoring_alerts')
    site = models.ForeignKey(ClientSite, on_delete=models.RESTRICT, db_column='site_id', related_name='monitoring_alerts')
    alert_rule = models.ForeignKey(AlertRule, on_delete=models.SET_NULL, null=True, blank=True, db_column='alert_rule_id', related_name='monitoring_alerts')
    alert_type = models.CharField(max_length=50)
    severity = models.CharField(max_length=20, choices=SEVERITIES, default='NORMAL')
    state = models.CharField(max_length=30, choices=STATES, default='RAISED')
    trigger_value = models.TextField(null=True, blank=True)
    raised_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, db_column='acknowledged_by', related_name='acknowledged_alerts')
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, db_column='resolved_by', related_name='resolved_alerts')
    resolution_note = models.TextField(null=True, blank=True)
    dismissal_reason = models.TextField(null=True, blank=True)
    escalation_level = models.IntegerField(default=0)
    last_escalated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'monitoring_alerts'


class SupervisorPing(models.Model):
    DELIVERY_STATES = (
        ('PENDING', 'Pending Delivery'),
        ('DELIVERED', 'Delivered'),
        ('FAILED', 'Delivery Failed'),
        ('UNKNOWN', 'Unknown'),
    )
    RESPONSE_STATES = (
        ('PENDING', 'Pending Response'),
        ('RESPONDED', 'Responded'),
        ('NO_RESPONSE', 'No Response'),
    )

    ping_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='company_id', related_name='supervisor_pings')
    duty = models.ForeignKey(MonitoringDuty, on_delete=models.CASCADE, db_column='duty_id', related_name='supervisor_pings')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, db_column='employee_id', related_name='supervisor_pings')
    supervisor = models.ForeignKey(User, on_delete=models.RESTRICT, db_column='supervisor_id', related_name='sent_pings')
    sent_at = models.DateTimeField(auto_now_add=True)
    delivery_state = models.CharField(max_length=20, choices=DELIVERY_STATES, default='PENDING')
    response_state = models.CharField(max_length=20, choices=RESPONSE_STATES, default='PENDING')
    responded_at = models.DateTimeField(null=True, blank=True)
    response_value = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'supervisor_pings'


class OutageGroup(models.Model):
    GROUP_STATES = (
        ('ACTIVE', 'Active Outage'),
        ('RESOLVED', 'Resolved'),
    )

    group_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='company_id', related_name='outage_groups')
    site = models.ForeignKey(ClientSite, on_delete=models.SET_NULL, null=True, blank=True, db_column='site_id', related_name='outage_groups')
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    suspected_cause = models.TextField(null=True, blank=True)
    affected_guard_count = models.IntegerField(default=0)
    group_state = models.CharField(max_length=20, choices=GROUP_STATES, default='ACTIVE')

    class Meta:
        managed = False
        db_table = 'outage_groups'


class TrackingConfiguration(models.Model):
    config_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.OneToOneField(Company, on_delete=models.CASCADE, db_column='company_id', related_name='tracking_configuration')
    normal_interval_mins = models.IntegerField(default=5)
    moving_interval_mins = models.IntegerField(default=2)
    low_battery_interval_mins = models.IntegerField(default=10)
    stale_threshold_mins = models.IntegerField(default=10)
    no_contact_threshold_mins = models.IntegerField(default=20)
    geofence_debounce_count = models.IntegerField(default=3)
    low_accuracy_threshold_meters = models.DecimalField(max_digits=8, decimal_places=2, default=50.0)
    post_shift_cutoff_mins = models.IntegerField(default=30)
    raw_retention_days = models.IntegerField(default=30)
    max_local_buffer_size = models.IntegerField(default=1000)
    max_upload_batch_size = models.IntegerField(default=50)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, db_column='updated_by')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'tracking_configurations'
