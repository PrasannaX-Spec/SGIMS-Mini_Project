import uuid
from django.db import models
from foundation.models import Company, User, BoundDevice
from master_data.models import ClientSite, ClientContact
from guard_management.models import Employee
from deployment_roster.models import RosterAssignment


class PanicAlert(models.Model):
    STATUS_CHOICES = (
        ('TRIGGERED', 'Triggered'),
        ('DELIVERING', 'Delivering'),
        ('ACKNOWLEDGED', 'Acknowledged'),
        ('RESPONDING', 'Responding'),
        ('GUARD_CONFIRMED_SAFE', 'Guard Confirmed Safe'),
        ('ESCALATED', 'Escalated'),
        ('RESOLVED', 'Resolved'),
        ('FALSE_ALARM', 'False Alarm'),
        ('TEST', 'Test Alert / Drill'),
        ('FAILED_TO_DELIVER', 'Failed to Deliver'),
        ('CLOSED', 'Closed'),
    )
    DUTY_STATUS_CHOICES = (
        ('ON_DUTY', 'On Duty'),
        ('OUTSIDE_DUTY', 'Outside Duty'),
    )

    panic_alert_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.RESTRICT, db_column='company_id', related_name='panic_alerts')
    alert_number = models.CharField(max_length=50, unique=True)
    client_generated_id = models.CharField(max_length=100)
    guard = models.ForeignKey(Employee, on_delete=models.RESTRICT, db_column='guard_id', related_name='panic_alerts')
    registered_device = models.ForeignKey(BoundDevice, on_delete=models.SET_NULL, null=True, blank=True, db_column='registered_device_id')
    assignment = models.ForeignKey(RosterAssignment, on_delete=models.SET_NULL, null=True, blank=True, db_column='assignment_id')
    site = models.ForeignKey(ClientSite, on_delete=models.SET_NULL, null=True, blank=True, db_column='site_id', related_name='panic_alerts')
    trigger_server_time = models.DateTimeField(auto_now_add=True)
    trigger_device_time = models.DateTimeField(null=True, blank=True)
    alert_status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='TRIGGERED')
    duty_status = models.CharField(max_length=20, choices=DUTY_STATUS_CHOICES, default='ON_DUTY')
    test_flag = models.BooleanField(default=False)
    current_escalation_stage = models.IntegerField(default=0)
    last_escalated_at = models.DateTimeField(null=True, blank=True)
    first_acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'panic_alerts'
        ordering = ['-trigger_server_time']

    def __str__(self):
        return f"{self.alert_number} - {self.guard.full_name} ({self.alert_status})"


class PanicTriggerContext(models.Model):
    context_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    panic_alert = models.OneToOneField(PanicAlert, on_delete=models.CASCADE, db_column='panic_alert_id', related_name='context')
    battery_level = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    network_type = models.CharField(max_length=40, null=True, blank=True)
    device_time = models.DateTimeField(null=True, blank=True)
    server_time = models.DateTimeField(auto_now_add=True)
    app_version = models.CharField(max_length=50, null=True, blank=True)
    device_status = models.CharField(max_length=50, null=True, blank=True)
    raw_metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        managed = False
        db_table = 'panic_trigger_contexts'


class PanicPositionRecord(models.Model):
    SOURCE_CHOICES = (
        ('FRESH_DEVICE', 'Fresh Device Request'),
        ('MODULE_7_LAST_KNOWN', 'Module 7 Last Known Position'),
        ('UNAVAILABLE', 'Unavailable'),
        ('MANUAL', 'Manual Entry'),
    )
    VALIDITY_CHOICES = (
        ('AVAILABLE', 'Available'),
        ('STALE', 'Stale Position'),
        ('UNAVAILABLE', 'Unavailable'),
        ('INVALID', 'Invalid'),
    )

    position_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    panic_alert = models.ForeignKey(PanicAlert, on_delete=models.CASCADE, db_column='panic_alert_id', related_name='positions')
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    accuracy = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    captured_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)
    source = models.CharField(max_length=30, choices=SOURCE_CHOICES, default='FRESH_DEVICE')
    position_age_seconds = models.IntegerField(null=True, blank=True)
    validity_status = models.CharField(max_length=20, choices=VALIDITY_CHOICES, default='AVAILABLE')
    is_latest = models.BooleanField(default=True)

    class Meta:
        managed = False
        db_table = 'panic_position_records'
        ordering = ['-received_at']


class PanicEscalationConfig(models.Model):
    config_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.RESTRICT, db_column='company_id', related_name='panic_configs')
    site = models.ForeignKey(ClientSite, on_delete=models.CASCADE, null=True, blank=True, db_column='site_id', related_name='panic_config')
    stage0_timer_seconds = models.IntegerField(default=0)
    stage1_timer_seconds = models.IntegerField(default=30)
    stage2_timer_seconds = models.IntegerField(default=60)
    stage3_timer_seconds = models.IntegerField(default=120)
    stage4_timer_seconds = models.IntegerField(default=300)
    notify_client_immediately = models.BooleanField(default=False)
    enabled_routes = models.JSONField(default=list)
    on_call_contact_name = models.CharField(max_length=150, null=True, blank=True)
    on_call_contact_phone = models.CharField(max_length=30, null=True, blank=True)
    emergency_number_to_display = models.CharField(max_length=20, default='112')
    panic_tracking_interval_seconds = models.IntegerField(default=15)
    max_panic_tracking_duration_minutes = models.IntegerField(default=60)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'panic_escalation_configs'


class PanicRecipient(models.Model):
    ROLE_CHOICES = (
        ('ADMIN', 'Admin'),
        ('SUPERVISOR', 'Supervisor'),
        ('CLIENT', 'Client'),
        ('ADDITIONAL_CONTACT', 'Additional Contact'),
    )
    TYPE_CHOICES = (
        ('PRIMARY_SUPERVISOR', 'Primary Supervisor'),
        ('BACKUP_SUPERVISOR', 'Backup Supervisor'),
        ('ADMIN', 'Admin'),
        ('CLIENT_ESCALATION', 'Client Escalation Contact'),
        ('ADDITIONAL_CONTACT', 'Additional Contact'),
        ('ON_CALL', 'On-Call Contact'),
    )
    CHANNEL_CHOICES = (
        ('APP', 'Mobile App'),
        ('WEB', 'Web Console'),
        ('SMS_LINK', 'SMS Secure Link'),
    )

    recipient_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    panic_alert = models.ForeignKey(PanicAlert, on_delete=models.CASCADE, db_column='panic_alert_id', related_name='recipients')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, db_column='user_id')
    contact = models.ForeignKey(ClientContact, on_delete=models.SET_NULL, null=True, blank=True, db_column='contact_id')
    recipient_role = models.CharField(max_length=30, choices=ROLE_CHOICES)
    recipient_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    notification_enabled = models.BooleanField(default=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledgement_channel = models.CharField(max_length=30, choices=CHANNEL_CHOICES, null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'panic_recipients'


class PanicDeliveryAttempt(models.Model):
    ROUTE_CHOICES = (
        ('PUSH', 'Push Notification'),
        ('WEB_CONSOLE', 'Web Console Alarm'),
        ('SMS', 'SMS Alert'),
        ('VOICE', 'Automated Voice Call'),
        ('DEVICE_SMS_FALLBACK', 'Device SMS Fallback'),
    )
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('ATTEMPTED', 'Attempted'),
        ('DELIVERED', 'Delivered'),
        ('FAILED', 'Failed'),
        ('UNKNOWN', 'Unknown'),
    )

    delivery_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    panic_alert = models.ForeignKey(PanicAlert, on_delete=models.CASCADE, db_column='panic_alert_id', related_name='delivery_attempts')
    recipient = models.ForeignKey(PanicRecipient, on_delete=models.CASCADE, db_column='recipient_id', related_name='delivery_attempts')
    route = models.CharField(max_length=30, choices=ROUTE_CHOICES)
    attempt_number = models.IntegerField(default=1)
    attempted_at = models.DateTimeField(auto_now_add=True)
    provider_reference = models.CharField(max_length=150, null=True, blank=True)
    provider_status = models.CharField(max_length=100, null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(null=True, blank=True)
    delivery_status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='PENDING')

    class Meta:
        managed = False
        db_table = 'panic_delivery_attempts'
        ordering = ['attempted_at']


class PanicAcknowledgement(models.Model):
    CHANNEL_CHOICES = (
        ('APP', 'Mobile App'),
        ('WEB', 'Web Console'),
        ('SMS_LINK', 'SMS Secure Link'),
    )
    TYPE_CHOICES = (
        ('RECEIPT', 'Receipt Acknowledged (Not Responding)'),
        ('RESPONSE', 'Response Acknowledged (Responding)'),
    )

    acknowledgement_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    panic_alert = models.ForeignKey(PanicAlert, on_delete=models.CASCADE, db_column='panic_alert_id', related_name='acknowledgements')
    recipient = models.ForeignKey(PanicRecipient, on_delete=models.CASCADE, db_column='recipient_id', related_name='acknowledgements')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, db_column='user_id')
    acknowledged_at = models.DateTimeField(auto_now_add=True)
    channel = models.CharField(max_length=30, choices=CHANNEL_CHOICES)
    acknowledgement_type = models.CharField(max_length=30, choices=TYPE_CHOICES, default='RECEIPT')
    notes = models.TextField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'panic_acknowledgements'


class PanicResponderAction(models.Model):
    ACTION_CHOICES = (
        ('CALL_GUARD', 'Called Guard'),
        ('RESPONSE_STARTED', 'Response Started'),
        ('HELP_REQUESTED', 'Help Requested from Admin'),
        ('EMERGENCY_SERVICE_INFORMED', 'Emergency Service Informed'),
        ('DEPLOYMENT_REQUESTED', 'Emergency Deployment Requested'),
        ('ARE_YOU_SAFE_SENT', 'Are You Safe Prompt Sent'),
        ('GUARD_SAFETY_RESPONSE', 'Guard Safety Response Received'),
        ('NOTE_ADDED', 'Internal Note Added'),
        ('OTHER', 'Other Action'),
    )

    responder_action_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    panic_alert = models.ForeignKey(PanicAlert, on_delete=models.CASCADE, db_column='panic_alert_id', related_name='responder_actions')
    responder_user = models.ForeignKey(User, on_delete=models.RESTRICT, db_column='responder_user_id')
    action_type = models.CharField(max_length=40, choices=ACTION_CHOICES)
    action_time = models.DateTimeField(auto_now_add=True)
    description = models.TextField(null=True, blank=True)
    reference = models.CharField(max_length=150, null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'panic_responder_actions'
        ordering = ['action_time']


class PanicFalseAlarmReport(models.Model):
    DECISION_CHOICES = (
        ('PENDING', 'Pending Supervisor Confirmation'),
        ('CONFIRMED', 'Confirmed False Alarm'),
        ('REJECTED', 'Rejected (Real Panic Alert Continues)'),
    )

    false_alarm_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    panic_alert = models.ForeignKey(PanicAlert, on_delete=models.CASCADE, db_column='panic_alert_id', related_name='false_alarm_reports')
    guard = models.ForeignKey(Employee, on_delete=models.RESTRICT, db_column='guard_id')
    submitted_at = models.DateTimeField(auto_now_add=True)
    guard_explanation = models.TextField(null=True, blank=True)
    are_you_safe_answer = models.CharField(max_length=10, default='YES')
    supervisor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, db_column='supervisor_id')
    supervisor_decision = models.CharField(max_length=30, choices=DECISION_CHOICES, default='PENDING')
    supervisor_notes = models.TextField(null=True, blank=True)
    decision_time = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'panic_false_alarm_reports'


class PanicResolution(models.Model):
    OUTCOME_CHOICES = (
        ('SITUATION_RESOLVED_ON_SITE', 'Situation Resolved On Site'),
        ('POLICE_INTERVENED', 'Police Intervened'),
        ('MEDICAL_ATTENTION_GIVEN', 'Medical Attention Given'),
        ('INTRUDER_APPREHENDED', 'Intruder Apprehended'),
        ('FALSE_ALARM_VERIFIED', 'False Alarm Verified'),
        ('GUARD_RELIEVED_SAFELY', 'Guard Relieved Safely'),
        ('OTHER', 'Other Outcome'),
    )
    ADMIN_REVIEW_CHOICES = (
        ('PENDING', 'Pending Admin Review'),
        ('APPROVED', 'Approved by Admin (Closed)'),
        ('RETURNED', 'Returned for More Information'),
    )

    resolution_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    panic_alert = models.OneToOneField(PanicAlert, on_delete=models.CASCADE, db_column='panic_alert_id', related_name='resolution')
    outcome = models.CharField(max_length=50, choices=OUTCOME_CHOICES)
    description = models.TextField()
    injury_status = models.TextField(null=True, blank=True)
    emergency_services_informed = models.BooleanField(default=False)
    emergency_service_ref = models.CharField(max_length=150, null=True, blank=True)
    follow_up_required = models.BooleanField(default=False)
    submitted_by = models.ForeignKey(User, on_delete=models.RESTRICT, db_column='submitted_by')
    submitted_at = models.DateTimeField(auto_now_add=True)
    admin_review_status = models.CharField(max_length=30, choices=ADMIN_REVIEW_CHOICES, default='PENDING')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, db_column='reviewed_by', related_name='reviewed_panic_resolutions')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'panic_resolutions'


class PanicEventTimeline(models.Model):
    EVENT_CHOICES = (
        ('TRIGGER', 'Alert Triggered'),
        ('DELIVERY_ATTEMPT', 'Delivery Attempted'),
        ('DELIVERY_SUCCESS', 'Delivery Succeeded'),
        ('DELIVERY_FAILURE', 'Delivery Failed'),
        ('ACKNOWLEDGEMENT', 'Recipient Acknowledged'),
        ('ESCALATION_STAGE', 'Escalated to Stage'),
        ('NO_ACKNOWLEDGEMENT_WARNING', 'No Acknowledgement Warning'),
        ('RESPONSE_STARTED', 'Supervisor Response Started'),
        ('CALL_INITIATED', 'Guard Call Initiated'),
        ('EMERGENCY_SERVICE_NOTIFIED', 'Emergency Services Informed'),
        ('DEPLOYMENT_REQUESTED', 'Emergency Deployment Requested'),
        ('ARE_YOU_SAFE_SENT', 'Are You Safe Prompt Sent'),
        ('GUARD_SAFETY_REPLY', 'Guard Replied to Safety Prompt'),
        ('FALSE_ALARM_REPORTED', 'False Alarm Reported by Guard'),
        ('FALSE_ALARM_CONFIRMED', 'False Alarm Confirmed by Supervisor'),
        ('FALSE_ALARM_REJECTED', 'False Alarm Rejected'),
        ('STATUS_CHANGE', 'Status Changed'),
        ('INTERNAL_NOTE', 'Internal Note Added'),
        ('RESOLUTION_SUBMITTED', 'Resolution Submitted by Supervisor'),
        ('ADMIN_REVIEWED', 'Admin Review Completed'),
        ('ADMIN_CLOSED', 'Admin Approved and Closed'),
        ('ADMIN_RETURNED', 'Admin Returned for Information'),
        ('CORRECTION_ENTRY', 'Correction Note Recorded'),
        ('INCIDENT_LINKED', 'Linked to Module 8 Incident'),
    )

    event_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    panic_alert = models.ForeignKey(PanicAlert, on_delete=models.CASCADE, db_column='panic_alert_id', related_name='timelines')
    event_type = models.CharField(max_length=50, choices=EVENT_CHOICES)
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, db_column='actor_id')
    event_time = models.DateTimeField(auto_now_add=True)
    event_data = models.JSONField(default=dict, blank=True)
    source_reference = models.CharField(max_length=150, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'panic_event_timelines'
        ordering = ['event_time']


class PanicTestDrill(models.Model):
    STATUS_CHOICES = (
        ('SCHEDULED', 'Scheduled'),
        ('RUNNING', 'Running'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
    )

    drill_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.RESTRICT, db_column='company_id', related_name='panic_drills')
    drill_name = models.CharField(max_length=150)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    executed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='SCHEDULED')
    selected_recipient_roles = models.JSONField(default=list)
    selected_routes = models.JSONField(default=list)
    include_clients = models.BooleanField(default=False)
    notes = models.TextField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.RESTRICT, db_column='created_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'panic_test_drills'
        ordering = ['-created_at']


class PanicDeviceReadiness(models.Model):
    PERMISSION_CHOICES = (
        ('GRANTED', 'Granted'),
        ('DENIED', 'Denied'),
        ('UNKNOWN', 'Unknown'),
    )
    BATTERY_CHOICES = (
        ('OPTIMIZED', 'Optimized (Restricted Background)'),
        ('RESTRICTED', 'Restricted'),
        ('UNRESTRICTED', 'Unrestricted (Recommended)'),
        ('UNKNOWN', 'Unknown'),
    )
    OVERALL_CHOICES = (
        ('READY', 'Ready for Panic Alerts'),
        ('NOT_READY', 'Not Ready (Action Required)'),
        ('UNKNOWN', 'Unknown Readiness'),
    )

    readiness_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.RESTRICT, db_column='company_id')
    guard = models.ForeignKey(Employee, on_delete=models.CASCADE, db_column='guard_id', related_name='panic_readiness')
    device = models.ForeignKey(BoundDevice, on_delete=models.SET_NULL, null=True, blank=True, db_column='device_id')
    app_version = models.CharField(max_length=50, null=True, blank=True)
    notification_permission = models.CharField(max_length=20, choices=PERMISSION_CHOICES, default='UNKNOWN')
    battery_optimization = models.CharField(max_length=20, choices=BATTERY_CHOICES, default='UNKNOWN')
    location_permission = models.CharField(max_length=20, choices=PERMISSION_CHOICES, default='UNKNOWN')
    last_seen_at = models.DateTimeField(null=True, blank=True)
    overall_readiness = models.CharField(max_length=20, choices=OVERALL_CHOICES, default='UNKNOWN')
    corrective_instructions = models.TextField(null=True, blank=True)
    checked_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'panic_device_readiness'


class PanicWelfareFollowup(models.Model):
    followup_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    panic_alert = models.ForeignKey(PanicAlert, on_delete=models.CASCADE, db_column='panic_alert_id', related_name='welfare_followups')
    recorded_by = models.ForeignKey(User, on_delete=models.RESTRICT, db_column='recorded_by')
    followup_time = models.DateTimeField(auto_now_add=True)
    note = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'panic_welfare_followups'
        ordering = ['-followup_time']
