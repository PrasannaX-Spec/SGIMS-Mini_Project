import uuid
from django.db import models
from master_data.models import Company, ClientSite, PostType, SiteShift, SiteManpowerRequirement
from guard_management.models import Employee


class PostSlot(models.Model):
    STATUS_CHOICES = (
        ('open', 'Open'),
        ('filled', 'Filled'),
        ('at_risk', 'At Risk'),
        ('cancelled', 'Cancelled'),
    )

    slot_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    company = models.ForeignKey(Company, on_delete=models.RESTRICT, db_column='company_id', related_name='post_slots')
    site = models.ForeignKey(ClientSite, on_delete=models.RESTRICT, db_column='site_id', related_name='post_slots')
    requirement = models.ForeignKey(SiteManpowerRequirement, on_delete=models.SET_NULL, null=True, blank=True, db_column='requirement_id', related_name='post_slots')
    post_type = models.ForeignKey(PostType, on_delete=models.RESTRICT, db_column='post_type_id', related_name='post_slots')
    shift = models.ForeignKey(SiteShift, on_delete=models.RESTRICT, db_column='shift_id', related_name='post_slots')
    deployment_date = models.DateField()
    slot_sequence = models.IntegerField()
    slot_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'post_slots'
        unique_together = (('site', 'shift', 'post_type', 'deployment_date', 'slot_sequence'),)


class Roster(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('locked', 'Locked'),
    )

    roster_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    company = models.ForeignKey(Company, on_delete=models.RESTRICT, db_column='company_id', related_name='rosters')
    site = models.ForeignKey(ClientSite, on_delete=models.RESTRICT, db_column='site_id', related_name='rosters')
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    published_by = models.UUIDField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'rosters'


class RosterAssignment(models.Model):
    TYPE_CHOICES = (
        ('regular', 'Regular'),
        ('reliever', 'Reliever'),
        ('replacement', 'Replacement'),
        ('overtime', 'Overtime'),
        ('standby', 'Standby'),
    )
    STATUS_CHOICES = (
        ('scheduled', 'Scheduled'),
        ('acknowledged', 'Acknowledged'),
        ('completed', 'Completed'),
        ('no_show', 'No Show'),
        ('cancelled', 'Cancelled'),
    )

    assignment_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    company = models.ForeignKey(Company, on_delete=models.RESTRICT, db_column='company_id', related_name='roster_assignments')
    slot = models.ForeignKey(PostSlot, on_delete=models.RESTRICT, db_column='slot_id', related_name='assignments')
    roster = models.ForeignKey(Roster, on_delete=models.SET_NULL, null=True, blank=True, db_column='roster_id', related_name='assignments')
    employee = models.ForeignKey(Employee, on_delete=models.RESTRICT, db_column='employee_id', related_name='roster_assignments')
    site = models.ForeignKey(ClientSite, on_delete=models.RESTRICT, db_column='site_id', related_name='roster_assignments')
    shift = models.ForeignKey(SiteShift, on_delete=models.RESTRICT, db_column='shift_id', related_name='roster_assignments')
    post_type = models.ForeignKey(PostType, on_delete=models.RESTRICT, db_column='post_type_id', related_name='roster_assignments')
    deployment_date = models.DateField()
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    assignment_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='regular')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    is_emergency = models.BooleanField(default=False)
    original_assignment = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, db_column='original_assignment_id', related_name='replacements')
    created_by_user_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'roster_assignments'


class AssignmentHistory(models.Model):
    history_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    assignment = models.ForeignKey(RosterAssignment, on_delete=models.CASCADE, db_column='assignment_id', related_name='history')
    action = models.CharField(max_length=30)
    previous_values = models.JSONField(null=True, blank=True)
    new_values = models.JSONField(null=True, blank=True)
    actor_user_id = models.UUIDField(null=True, blank=True)
    reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'assignment_history'


class ShiftSwapRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    )

    swap_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    company = models.ForeignKey(Company, on_delete=models.RESTRICT, db_column='company_id', related_name='shift_swaps')
    site = models.ForeignKey(ClientSite, on_delete=models.RESTRICT, db_column='site_id', related_name='shift_swaps')
    requesting_employee = models.ForeignKey(Employee, on_delete=models.RESTRICT, db_column='requesting_employee_id', related_name='swap_requests_made')
    target_employee = models.ForeignKey(Employee, on_delete=models.RESTRICT, db_column='target_employee_id', related_name='swap_requests_received')
    assignment_a = models.ForeignKey(RosterAssignment, on_delete=models.RESTRICT, db_column='assignment_a_id', related_name='swap_as_a')
    assignment_b = models.ForeignKey(RosterAssignment, on_delete=models.RESTRICT, db_column='assignment_b_id', related_name='swap_as_b')
    reason = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reviewed_by_user_id = models.UUIDField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'shift_swap_requests'


class EmergencyRatification(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('ratified', 'Ratified'),
        ('rejected', 'Rejected'),
        ('overdue', 'Overdue'),
    )

    ratification_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    assignment = models.ForeignKey(RosterAssignment, on_delete=models.CASCADE, db_column='assignment_id', related_name='ratifications')
    supervisor_user_id = models.UUIDField()
    admin_user_id = models.UUIDField(null=True, blank=True)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    deadline = models.DateTimeField()
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'emergency_ratifications'


class DutyAcknowledgement(models.Model):
    acknowledgement_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    assignment = models.OneToOneField(RosterAssignment, on_delete=models.CASCADE, db_column='assignment_id', related_name='acknowledgement')
    employee = models.ForeignKey(Employee, on_delete=models.RESTRICT, db_column='employee_id', related_name='duty_acknowledgements')
    acknowledged_at = models.DateTimeField(auto_now_add=True)
    device_id = models.CharField(max_length=100, null=True, blank=True)
    ip_address = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'duty_acknowledgements'


class OvertimeRecord(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )

    overtime_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    assignment = models.ForeignKey(RosterAssignment, on_delete=models.CASCADE, db_column='assignment_id', related_name='overtime_records')
    threshold_type = models.CharField(max_length=20)
    flagged_hours = models.DecimalField(max_digits=4, decimal_places=2)
    approval_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    approved_by_user_id = models.UUIDField(null=True, blank=True)
    reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'overtime_records'


class RelieverPoolMembership(models.Model):
    membership_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    company = models.ForeignKey(Company, on_delete=models.RESTRICT, db_column='company_id', related_name='reliever_memberships')
    employee = models.ForeignKey(Employee, on_delete=models.RESTRICT, db_column='employee_id', related_name='reliever_memberships')
    pool_type = models.CharField(max_length=20, default='reliever')
    effective_start = models.DateField()
    effective_end = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'reliever_pool_memberships'

