import uuid
from django.db import models
from foundation.models import Company, User
from master_data.models import Client, ClientSite
from guard_management.models import Employee
from deployment_roster.models import RosterAssignment


class IncidentCategory(models.Model):
    SHARING_POLICIES = (
        ('AUTOMATIC_AFTER_REVIEW', 'Automatic After Review'),
        ('EXPLICIT_ONLY', 'Explicit Approval Only'),
        ('NEVER', 'Never Share With Client'),
    )
    SEVERITY_LEVELS = (
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    )

    category_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='company_id', related_name='incident_categories')
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50)
    description = models.TextField(null=True, blank=True)
    active = models.BooleanField(default=True)
    sensitive = models.BooleanField(default=False)
    sharing_policy = models.CharField(max_length=30, choices=SHARING_POLICIES, default='EXPLICIT_ONLY')
    default_severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS, default='MEDIUM')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'incident_categories'
        unique_together = (('company', 'code'),)

    def __str__(self):
        return f"{self.name} ({self.code})"


class GuardRequestType(models.Model):
    request_type_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='company_id', related_name='guard_request_types')
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50)
    description = models.TextField(null=True, blank=True)
    active = models.BooleanField(default=True)
    cost_related = models.BooleanField(default=False)
    admin_approval_required = models.BooleanField(default=False)
    default_response_hours = models.IntegerField(default=4)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'guard_request_types'
        unique_together = (('company', 'code'),)

    def __str__(self):
        return f"{self.name} ({self.code})"


class ResolutionOutcome(models.Model):
    outcome_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='company_id', related_name='resolution_outcomes')
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50)
    description = models.TextField(null=True, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'resolution_outcomes'
        unique_together = (('company', 'code'),)

    def __str__(self):
        return self.name


class CaseNumberSequence(models.Model):
    sequence_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='company_id')
    record_type = models.CharField(max_length=30)
    prefix = models.CharField(max_length=10)
    current_year = models.IntegerField()
    last_number = models.IntegerField(default=0)
    last_generated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'case_number_sequences'
        unique_together = (('company', 'record_type', 'current_year'),)


class Incident(models.Model):
    STATUS_CHOICES = (
        ('REPORTED', 'Reported'),
        ('ACKNOWLEDGED', 'Acknowledged'),
        ('IN_PROGRESS', 'In Progress'),
        ('ESCALATED', 'Escalated'),
        ('RESOLVED', 'Resolved'),
        ('CLOSED', 'Closed'),
        ('REOPENED', 'Reopened'),
        ('REJECTED_AS_INVALID', 'Rejected as Invalid'),
    )
    SEVERITY_CHOICES = (
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    )
    VERIFICATION_CHOICES = (
        ('REPORTED_NOT_VERIFIED', 'Reported by guard, not yet verified'),
        ('SUPERVISOR_REVIEWED', 'Supervisor Reviewed'),
        ('REJECTED_AS_INVALID', 'Rejected as Invalid'),
    )

    incident_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='company_id', related_name='incidents')
    case_number = models.CharField(max_length=60)
    client_generated_id = models.UUIDField()
    guard = models.ForeignKey(Employee, on_delete=models.RESTRICT, db_column='guard_id', related_name='reported_incidents')
    assignment = models.ForeignKey(RosterAssignment, on_delete=models.SET_NULL, null=True, blank=True, db_column='assignment_id', related_name='incidents')
    site = models.ForeignKey(ClientSite, on_delete=models.RESTRICT, db_column='site_id', related_name='incidents')
    supervisor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, db_column='supervisor_id', related_name='supervised_incidents')
    category = models.ForeignKey(IncidentCategory, on_delete=models.RESTRICT, db_column='category_id', related_name='incidents')
    original_category = models.ForeignKey(IncidentCategory, on_delete=models.RESTRICT, db_column='original_category_id', related_name='originally_categorized_incidents')
    current_category = models.ForeignKey(IncidentCategory, on_delete=models.RESTRICT, db_column='current_category_id', related_name='currently_categorized_incidents')
    original_severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    current_severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    description = models.TextField()  # Immutable original report
    occurred_at = models.DateTimeField()
    device_time = models.DateTimeField()
    submitted_at = models.DateTimeField(auto_now_add=True)
    server_received_at = models.DateTimeField(auto_now_add=True)
    reported_outside_duty = models.BooleanField(default=False)
    verification_state = models.CharField(max_length=40, choices=VERIFICATION_CHOICES, default='REPORTED_NOT_VERIFIED')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='REPORTED')
    is_sensitive = models.BooleanField(default=False)
    linked_case = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, db_column='linked_case_id', related_name='linked_reports')
    resolution_outcome = models.ForeignKey(ResolutionOutcome, on_delete=models.SET_NULL, null=True, blank=True, db_column='resolution_outcome_id')
    resolution_note = models.TextField(null=True, blank=True)
    resolution_action_taken = models.TextField(null=True, blank=True)
    follow_up_required = models.BooleanField(default=False)
    follow_up_due_at = models.DateTimeField(null=True, blank=True)
    admin_reviewed = models.BooleanField(default=False)
    admin_reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, db_column='admin_reviewed_by', related_name='reviewed_incidents')
    admin_reviewed_at = models.DateTimeField(null=True, blank=True)
    reopen_reason = models.TextField(null=True, blank=True)
    rejection_reason = models.TextField(null=True, blank=True)
    escalation_reason = models.TextField(null=True, blank=True)
    escalated_at = models.DateTimeField(null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    panic_event_reference = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'incidents'
        unique_together = (('company', 'case_number'), ('company', 'guard', 'client_generated_id'))

    def __str__(self):
        return f"{self.case_number} - {self.category.name} ({self.status})"


class IncidentContext(models.Model):
    context_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    incident = models.OneToOneField(Incident, on_delete=models.CASCADE, db_column='incident_id', related_name='context')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='company_id')
    site = models.ForeignKey(ClientSite, on_delete=models.RESTRICT, db_column='site_id')
    assignment = models.ForeignKey(RosterAssignment, on_delete=models.SET_NULL, null=True, blank=True, db_column='assignment_id')
    guard = models.ForeignKey(Employee, on_delete=models.RESTRICT, db_column='guard_id')
    supervisor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, db_column='supervisor_id')
    server_time = models.DateTimeField(auto_now_add=True)
    device_time = models.DateTimeField(null=True, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    accuracy_m = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    position_captured_at = models.DateTimeField(null=True, blank=True)
    position_age_seconds = models.IntegerField(null=True, blank=True)
    position_source = models.CharField(max_length=50, null=True, blank=True)
    location_label = models.CharField(max_length=100, default='Evidence context, not a precise fix')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'incident_contexts'


class IncidentDetail(models.Model):
    detail_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    incident = models.OneToOneField(Incident, on_delete=models.CASCADE, db_column='incident_id', related_name='details')
    people_involved = models.TextField(null=True, blank=True)
    vehicle_numbers = models.TextField(null=True, blank=True)
    witnesses = models.TextField(null=True, blank=True)
    injuries = models.TextField(null=True, blank=True)
    police_informed = models.BooleanField(default=False)
    police_reference = models.CharField(max_length=100, null=True, blank=True)
    property_damage = models.TextField(null=True, blank=True)
    action_taken = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'incident_details'


class IncidentAttachment(models.Model):
    SOURCE_TYPES = (
        ('GUARD_CAPTURED', 'Guard Captured (In-App Camera)'),
        ('SUPERVISOR_ADDED', 'Supervisor Added'),
        ('CLIENT_SUPPLIED', 'Client Supplied'),
    )
    MEDIA_TYPES = (
        ('PHOTO', 'Photo'),
        ('VIDEO', 'Video'),
    )
    VERIFICATION_STATES = (
        ('PENDING', 'Pending Verification'),
        ('VERIFIED', 'Verified Hash Match'),
        ('FAILED_VERIFICATION', 'Failed Hash Verification'),
    )
    UPLOAD_STATES = (
        ('PENDING', 'Pending Upload'),
        ('UPLOADING', 'Uploading'),
        ('SYNCED', 'Synced'),
        ('FAILED', 'Failed Upload'),
    )

    attachment_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, db_column='incident_id', related_name='attachments')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='company_id')
    uploaded_by = models.ForeignKey(User, on_delete=models.RESTRICT, db_column='uploaded_by')
    source_type = models.CharField(max_length=30, choices=SOURCE_TYPES)
    media_type = models.CharField(max_length=20, choices=MEDIA_TYPES)
    file_reference = models.TextField()
    thumbnail_reference = models.TextField(null=True, blank=True)
    original_file_name = models.CharField(max_length=255, null=True, blank=True)
    file_size_bytes = models.BigIntegerField()
    duration_seconds = models.IntegerField(null=True, blank=True)
    original_hash = models.CharField(max_length=64)  # SHA-256
    uploaded_hash = models.CharField(max_length=64, null=True, blank=True)
    verification_state = models.CharField(max_length=30, choices=VERIFICATION_STATES, default='PENDING')
    upload_state = models.CharField(max_length=30, choices=UPLOAD_STATES, default='PENDING')
    captured_at = models.DateTimeField(null=True, blank=True)
    uploaded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'incident_attachments'


class IncidentAddendum(models.Model):
    addendum_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, db_column='incident_id', related_name='addendums')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='company_id')
    author = models.ForeignKey(User, on_delete=models.RESTRICT, db_column='author_id')
    content = models.TextField()
    client_generated_id = models.UUIDField()
    device_time = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sync_state = models.CharField(max_length=20, default='SYNCED')

    class Meta:
        managed = False
        db_table = 'incident_addendums'
        unique_together = (('incident', 'client_generated_id'),)


class IncidentTimeline(models.Model):
    timeline_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, db_column='incident_id', related_name='timeline')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='company_id')
    actor = models.ForeignKey(User, on_delete=models.RESTRICT, db_column='actor_id')
    action_type = models.CharField(max_length=50)
    previous_value = models.TextField(null=True, blank=True)
    new_value = models.TextField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    audit_reference = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'incident_timelines'


class IncidentFollowUpTask(models.Model):
    STATUS_CHOICES = (
        ('OPEN', 'Open'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    )

    task_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, db_column='incident_id', related_name='follow_up_tasks')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='company_id')
    assigned_to = models.ForeignKey(User, on_delete=models.RESTRICT, db_column='assigned_to', related_name='assigned_incident_tasks')
    created_by = models.ForeignKey(User, on_delete=models.RESTRICT, db_column='created_by', related_name='created_incident_tasks')
    description = models.TextField()
    due_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')
    completed_at = models.DateTimeField(null=True, blank=True)
    completion_note = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'incident_follow_up_tasks'


class IncidentClientVersion(models.Model):
    SHARING_STATES = (
        ('NOT_SHARED', 'Not Shared'),
        ('SHARED', 'Shared with Client'),
        ('WITHDRAWN', 'Withdrawn'),
    )
    CLIENT_STATUSES = (
        ('UNDER_REVIEW', 'Under Review'),
        ('INVESTIGATING', 'Investigation in Progress'),
        ('RESOLVED', 'Resolved'),
        ('CLOSED', 'Closed'),
    )

    version_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, db_column='incident_id', related_name='client_versions')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='company_id')
    client = models.ForeignKey(Client, on_delete=models.CASCADE, db_column='client_id', related_name='incident_shares')
    site = models.ForeignKey(ClientSite, on_delete=models.RESTRICT, db_column='site_id')
    title = models.CharField(max_length=255)
    category = models.CharField(max_length=100)
    occurred_at = models.DateTimeField()
    summary = models.TextField()
    actions_taken = models.TextField()
    status = models.CharField(max_length=30, choices=CLIENT_STATUSES, default='UNDER_REVIEW')
    approved_by = models.ForeignKey(User, on_delete=models.RESTRICT, db_column='approved_by')
    approved_at = models.DateTimeField(auto_now_add=True)
    sharing_state = models.CharField(max_length=20, choices=SHARING_STATES, default='SHARED')
    selected_attachment_ids = models.JSONField(default=list)
    version_number = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'incident_client_versions'


class GuardRequest(models.Model):
    STATUS_CHOICES = (
        ('SUBMITTED', 'Submitted'),
        ('ACKNOWLEDGED', 'Acknowledged'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('IN_PROGRESS', 'In Progress'),
        ('FULFILLED', 'Fulfilled'),
        ('CANCELLED_BY_GUARD', 'Cancelled by Guard'),
    )

    request_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='company_id', related_name='guard_requests')
    request_number = models.CharField(max_length=60)
    client_generated_id = models.UUIDField()
    guard = models.ForeignKey(Employee, on_delete=models.RESTRICT, db_column='guard_id', related_name='submitted_requests')
    site = models.ForeignKey(ClientSite, on_delete=models.RESTRICT, db_column='site_id', related_name='guard_requests')
    assignment = models.ForeignKey(RosterAssignment, on_delete=models.SET_NULL, null=True, blank=True, db_column='assignment_id')
    request_type = models.ForeignKey(GuardRequestType, on_delete=models.RESTRICT, db_column='request_type_id')
    description = models.TextField()
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='SUBMITTED')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, db_column='assigned_to')
    cost_related = models.BooleanField(default=False)
    admin_approval_required = models.BooleanField(default=False)
    admin_approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, db_column='admin_approved_by', related_name='cost_approved_requests')
    admin_approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(null=True, blank=True)
    fulfillment_note = models.TextField(null=True, blank=True)
    response_due_at = models.DateTimeField(null=True, blank=True)
    module5_reference = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'guard_requests'
        unique_together = (('company', 'request_number'), ('company', 'guard', 'client_generated_id'))

    def __str__(self):
        return f"{self.request_number} - {self.request_type.name} ({self.status})"


class GuardRequestReply(models.Model):
    reply_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(GuardRequest, on_delete=models.CASCADE, db_column='request_id', related_name='replies')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='company_id')
    actor = models.ForeignKey(User, on_delete=models.RESTRICT, db_column='actor_id')
    message = models.TextField()
    visibility = models.CharField(max_length=20, default='GUARD_VISIBLE')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'guard_request_replies'


class ClientTicket(models.Model):
    TICKET_TYPES = (
        ('COMPLAINT', 'Client Service Complaint'),
        ('FEEDBACK', 'Service Feedback'),
        ('QUERY', 'General Query'),
        ('OBSERVED_ISSUE', 'Observed Site Issue'),
        ('EXTRA_GUARDS', 'Request Additional Guards'),
    )
    STATUS_CHOICES = (
        ('OPEN', 'Open'),
        ('ACKNOWLEDGED', 'Acknowledged'),
        ('IN_PROGRESS', 'In Progress'),
        ('WAITING_FOR_CLIENT', 'Waiting for Client'),
        ('RESOLVED', 'Resolved'),
        ('CLOSED', 'Closed'),
        ('REOPENED', 'Reopened'),
    )

    ticket_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='company_id', related_name='client_tickets')
    ticket_number = models.CharField(max_length=60)
    client_generated_id = models.UUIDField()
    client = models.ForeignKey(Client, on_delete=models.CASCADE, db_column='client_id', related_name='tickets')
    site = models.ForeignKey(ClientSite, on_delete=models.RESTRICT, db_column='site_id', related_name='tickets')
    ticket_type = models.CharField(max_length=30, choices=TICKET_TYPES)
    title = models.CharField(max_length=255)
    description = models.TextField()
    named_guard = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, db_column='named_guard_id', related_name='client_complaints')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='OPEN')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, db_column='assigned_to', related_name='assigned_client_tickets')
    is_admin_only = models.BooleanField(default=False)
    response_due_at = models.DateTimeField(null=True, blank=True)
    resolution_due_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_note = models.TextField(null=True, blank=True)
    reopened_count = models.IntegerField(default=0)
    reopened_at = models.DateTimeField(null=True, blank=True)
    reopen_reason = models.TextField(null=True, blank=True)
    module4_reference = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'client_tickets'
        unique_together = (('company', 'ticket_number'), ('company', 'client', 'client_generated_id'))

    def __str__(self):
        return f"{self.ticket_number} - {self.title} ({self.status})"


class ClientTicketMessage(models.Model):
    message_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(ClientTicket, on_delete=models.CASCADE, db_column='ticket_id', related_name='messages')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='company_id')
    actor = models.ForeignKey(User, on_delete=models.RESTRICT, db_column='actor_id')
    message = models.TextField()
    visibility = models.CharField(max_length=20, default='CLIENT_VISIBLE')
    attachment_reference = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'client_ticket_messages'
