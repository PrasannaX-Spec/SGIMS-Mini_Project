import uuid
from django.db import models
from foundation.models import User, Company
from master_data.models import ClientSite, SiteShift
from guard_management.models import Employee
from deployment_roster.models import RosterAssignment


class AttendancePeriod(models.Model):
    STATUS_CHOICES = (
        ('open', 'Open'),
        ('locked', 'Locked'),
        ('reopened', 'Reopened'),
    )

    period_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='company_id', related_name='attendance_periods')
    site = models.ForeignKey(ClientSite, null=True, blank=True, on_delete=models.CASCADE, db_column='site_id', related_name='attendance_periods')
    period_name = models.CharField(max_length=50)
    start_date = models.DateField()
    end_date = models.DateField()
    cut_off_day = models.IntegerField(default=25)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    closed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, db_column='closed_by', related_name='closed_periods')
    closed_at = models.DateTimeField(null=True, blank=True)
    reopened_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, db_column='reopened_by', related_name='reopened_periods')
    reopened_at = models.DateTimeField(null=True, blank=True)
    reopen_reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'attendance_periods'

    def __str__(self):
        return f"{self.period_name} ({self.status.upper()})"


class AttendanceRecord(models.Model):
    STATUS_CHOICES = (
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('late', 'Late'),
        ('absent', 'Absent'),
        ('no_checkout', 'No Check-out'),
        ('pending_approval', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('corrected', 'Corrected'),
    )

    attendance_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='company_id', related_name='attendance_records')
    assignment = models.ForeignKey(RosterAssignment, null=True, blank=True, on_delete=models.SET_NULL, db_column='assignment_id', related_name='attendance_records')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, db_column='employee_id', related_name='attendance_records')
    site = models.ForeignKey(ClientSite, on_delete=models.CASCADE, db_column='site_id', related_name='attendance_records')
    shift = models.ForeignKey(SiteShift, on_delete=models.CASCADE, db_column='shift_id', related_name='attendance_records')
    duty_date = models.DateField()
    scheduled_start = models.DateTimeField()
    scheduled_end = models.DateTimeField()
    actual_check_in = models.DateTimeField(null=True, blank=True)
    actual_check_out = models.DateTimeField(null=True, blank=True)
    late_minutes = models.IntegerField(default=0)
    early_exit_minutes = models.IntegerField(default=0)
    worked_minutes = models.IntegerField(default=0)
    regular_minutes = models.IntegerField(default=0)
    overtime_minutes = models.IntegerField(default=0)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='scheduled')
    is_manual = models.BooleanField(default=False)
    is_offline = models.BooleanField(default=False)
    is_unscheduled = models.BooleanField(default=False)
    period = models.ForeignKey(AttendancePeriod, null=True, blank=True, on_delete=models.SET_NULL, db_column='period_id', related_name='records')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'attendance_records'

    def __str__(self):
        return f"Attendance {self.employee.employee_code} @ {self.site.site_name} on {self.duty_date} ({self.status})"


class AttendanceCapture(models.Model):
    CAPTURE_TYPE_CHOICES = (
        ('CHECK_IN', 'Check In'),
        ('CHECK_OUT', 'Check Out'),
    )
    GEOFENCE_OUTCOME_CHOICES = (
        ('valid', 'Valid'),
        ('outside_with_reason', 'Outside with Reason'),
        ('blocked', 'Blocked'),
    )
    SYNC_STATE_CHOICES = (
        ('pending', 'Pending'),
        ('uploading', 'Uploading'),
        ('synced', 'Synced'),
        ('failed', 'Failed'),
    )

    capture_id = models.UUIDField(primary_key=True, editable=False)  # Client generated
    attendance = models.ForeignKey(AttendanceRecord, null=True, blank=True, on_delete=models.CASCADE, db_column='attendance_id', related_name='captures')
    assignment = models.ForeignKey(RosterAssignment, null=True, blank=True, on_delete=models.SET_NULL, db_column='assignment_id', related_name='attendance_captures')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, db_column='employee_id', related_name='attendance_captures')
    capture_type = models.CharField(max_length=20, choices=CAPTURE_TYPE_CHOICES)
    device_time = models.DateTimeField()
    server_received_time = models.DateTimeField(auto_now_add=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    gps_accuracy = models.DecimalField(max_digits=6, decimal_places=2)
    distance_meters = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    geofence_outcome = models.CharField(max_length=30, choices=GEOFENCE_OUTCOME_CHOICES, default='valid')
    outside_reason = models.TextField(null=True, blank=True)
    device_id = models.CharField(max_length=100)
    app_version = models.CharField(max_length=50)
    battery_level = models.IntegerField(null=True, blank=True)
    network_type = models.CharField(max_length=30, null=True, blank=True)
    mock_location_detected = models.BooleanField(default=False)
    photo_storage_key = models.TextField()
    photo_hash = models.CharField(max_length=64)
    sync_state = models.CharField(max_length=20, choices=SYNC_STATE_CHOICES, default='synced')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'attendance_captures'

    def __str__(self):
        return f"{self.capture_type} by {self.employee.employee_code} at {self.device_time}"


class AttendanceEvidence(models.Model):
    EVIDENCE_TYPE_CHOICES = (
        ('photo', 'Photograph'),
        ('gps', 'GPS Coordinates'),
        ('device_metadata', 'Device Metadata'),
    )

    evidence_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attendance = models.ForeignKey(AttendanceRecord, on_delete=models.CASCADE, db_column='attendance_id', related_name='evidence')
    capture = models.ForeignKey(AttendanceCapture, on_delete=models.CASCADE, db_column='capture_id', related_name='evidence')
    evidence_type = models.CharField(max_length=30, choices=EVIDENCE_TYPE_CHOICES)
    storage_reference = models.TextField()
    hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'attendance_evidence'


class AttendanceFlag(models.Model):
    SEVERITY_CHOICES = (
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    )

    flag_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attendance = models.ForeignKey(AttendanceRecord, on_delete=models.CASCADE, db_column='attendance_id', related_name='flags')
    flag_type = models.CharField(max_length=50)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='MEDIUM')
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution = models.TextField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'attendance_flags'

    def __str__(self):
        return f"[{self.severity}] {self.flag_type}: {self.description}"


class AttendanceRevision(models.Model):
    revision_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attendance = models.ForeignKey(AttendanceRecord, on_delete=models.CASCADE, db_column='attendance_id', related_name='revisions')
    revision_number = models.IntegerField(default=1)
    previous_values = models.JSONField()
    new_values = models.JSONField()
    reason = models.TextField()
    actor = models.ForeignKey(User, on_delete=models.CASCADE, db_column='actor_id', related_name='attendance_revisions')
    correction_size_minutes = models.IntegerField(default=0)
    requires_admin_approval = models.BooleanField(default=False)
    approval_status = models.CharField(max_length=20, default='approved')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'attendance_revisions'


class AttendanceRegularisation(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )

    request_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, db_column='employee_id', related_name='regularisations')
    attendance = models.ForeignKey(AttendanceRecord, null=True, blank=True, on_delete=models.SET_NULL, db_column='attendance_id', related_name='regularisations')
    assignment = models.ForeignKey(RosterAssignment, null=True, blank=True, on_delete=models.SET_NULL, db_column='assignment_id', related_name='regularisations')
    site = models.ForeignKey(ClientSite, on_delete=models.CASCADE, db_column='site_id', related_name='regularisations')
    shift = models.ForeignKey(SiteShift, on_delete=models.CASCADE, db_column='shift_id', related_name='regularisations')
    duty_date = models.DateField()
    claimed_check_in = models.DateTimeField()
    claimed_check_out = models.DateTimeField()
    reason = models.TextField()
    photo_storage_key = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reviewed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, db_column='reviewed_by', related_name='reviewed_regularisations')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'attendance_regularisations'


class AttendanceApproval(models.Model):
    ACTION_CHOICES = (
        ('approve', 'Approve'),
        ('reject', 'Reject'),
        ('correct', 'Correct'),
        ('mark_absent', 'Mark Absent'),
        ('request_explanation', 'Request Explanation'),
    )

    approval_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attendance = models.ForeignKey(AttendanceRecord, on_delete=models.CASCADE, db_column='attendance_id', related_name='approvals')
    actor = models.ForeignKey(User, on_delete=models.CASCADE, db_column='actor_id', related_name='attendance_approvals')
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    reason = models.TextField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'attendance_approvals'


class AttendancePeriodException(models.Model):
    exception_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    period = models.ForeignKey(AttendancePeriod, on_delete=models.CASCADE, db_column='period_id', related_name='exceptions')
    attendance = models.ForeignKey(AttendanceRecord, on_delete=models.CASCADE, db_column='attendance_id', related_name='period_exceptions')
    exception_type = models.CharField(max_length=50, default='PENDING_APPROVAL')
    reason = models.TextField()
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, db_column='created_by', related_name='period_exceptions')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'attendance_period_exceptions'


class AttendanceHandover(models.Model):
    handover_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    outgoing_attendance = models.ForeignKey(AttendanceRecord, on_delete=models.CASCADE, db_column='outgoing_attendance_id', related_name='outgoing_handovers')
    incoming_attendance = models.ForeignKey(AttendanceRecord, null=True, blank=True, on_delete=models.SET_NULL, db_column='incoming_attendance_id', related_name='incoming_handovers')
    incoming_employee_code = models.CharField(max_length=50)
    site = models.ForeignKey(ClientSite, on_delete=models.CASCADE, db_column='site_id', related_name='handovers')
    handover_time = models.DateTimeField()
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'attendance_handovers'


class ManualAttendanceCounter(models.Model):
    counter_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, db_column='employee_id', related_name='manual_counters')
    period_month = models.CharField(max_length=7)  # 'YYYY-MM'
    count = models.IntegerField(default=0)
    configured_limit = models.IntegerField(default=3)
    alert_status = models.CharField(max_length=20, default='normal')

    class Meta:
        managed = False
        db_table = 'manual_attendance_counters'

