import uuid
from django.db import models
from master_data.models import Company, PostType


class Employee(models.Model):
    LIFECYCLE_STATUS_CHOICES = (
        ('applicant', 'Applicant'),
        ('under_verification', 'Under Verification'),
        ('approved', 'Approved'),
        ('active', 'Active'),
        ('on_leave', 'On Leave'),
        ('suspended', 'Suspended'),
        ('resigned', 'Resigned'),
        ('terminated', 'Terminated'),
    )

    employee_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    company = models.ForeignKey(Company, on_delete=models.RESTRICT, db_column='company_id', related_name='employees')
    branch_id = models.UUIDField(null=True, blank=True)
    applicant_id = models.UUIDField(null=True, blank=True, unique=True)
    employee_code = models.CharField(max_length=50)
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, null=True, blank=True)
    last_name = models.CharField(max_length=100, null=True, blank=True)
    father_guardian_name = models.CharField(max_length=160, null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=30, null=True, blank=True)
    phone = models.CharField(max_length=30)
    email = models.CharField(max_length=254, null=True, blank=True)
    address = models.JSONField(null=True, blank=True)
    emergency_contact = models.JSONField(null=True, blank=True)
    date_joined = models.DateField()
    employment_type = models.CharField(max_length=30, default='full_time')
    employment_status = models.CharField(max_length=30, default='active')
    lifecycle_status = models.CharField(max_length=30, choices=LIFECYCLE_STATUS_CHOICES, default='applicant')
    designation = models.CharField(max_length=100, null=True, blank=True)
    grade = models.CharField(max_length=50, null=True, blank=True)
    bank_details = models.JSONField(null=True, blank=True)
    id_card_no = models.CharField(max_length=60, null=True, blank=True)
    exit_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Extended Module 3 fields
    blood_group = models.CharField(max_length=10, null=True, blank=True)
    marital_status = models.CharField(max_length=20, null=True, blank=True)
    height_cm = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    weight_kg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    languages_known = models.JSONField(null=True, blank=True)
    qualification = models.CharField(max_length=100, null=True, blank=True)
    experience_summary = models.TextField(null=True, blank=True)
    is_ex_serviceman = models.BooleanField(default=False)
    reference_photo_url = models.TextField(null=True, blank=True)
    pan_number = models.CharField(max_length=10, null=True, blank=True)
    uan_number = models.CharField(max_length=20, null=True, blank=True)
    esi_number = models.CharField(max_length=20, null=True, blank=True)
    aadhaar_masked = models.CharField(max_length=20, null=True, blank=True)
    aadhaar_hash = models.CharField(max_length=64, null=True, blank=True)
    home_district = models.CharField(max_length=100, null=True, blank=True)
    preferred_work_area = models.CharField(max_length=100, null=True, blank=True)
    post_type = models.ForeignKey(PostType, on_delete=models.SET_NULL, null=True, blank=True, db_column='post_type_id')
    reporting_supervisor_id = models.UUIDField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'employees'

    @property
    def full_name(self):
        parts = [self.first_name, self.middle_name, self.last_name]
        return " ".join([p for p in parts if p]).strip()


class EmployeeDocument(models.Model):
    VERIFICATION_STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
    )

    document_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    employee = models.ForeignKey(Employee, on_delete=models.RESTRICT, db_column='employee_id', related_name='documents')
    document_type = models.CharField(max_length=60)
    storage_key = models.TextField()
    original_filename = models.CharField(max_length=255, null=True, blank=True)
    document_number = models.CharField(max_length=100, null=True, blank=True)
    masked_number = models.CharField(max_length=30, null=True, blank=True)
    number_hash = models.CharField(max_length=64, null=True, blank=True)
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    verification_status = models.CharField(max_length=20, choices=VERIFICATION_STATUS_CHOICES, default='pending')
    verified_by = models.UUIDField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    rejection_reason = models.TextField(null=True, blank=True)
    version = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'employee_documents'


class EmployeeTraining(models.Model):
    employee_training_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    employee = models.ForeignKey(Employee, on_delete=models.RESTRICT, db_column='employee_id', related_name='trainings')
    session_id = models.UUIDField(null=True, blank=True)
    attendance_status = models.CharField(max_length=20, default='present')
    result = models.CharField(max_length=20, default='passed')
    certificate_storage_key = models.TextField(null=True, blank=True)
    certificate_no = models.CharField(max_length=100, null=True, blank=True)
    completed_at = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'employee_training'


class EmployeeCheck(models.Model):
    CHECK_TYPE_CHOICES = (
        ('police', 'Police Verification'),
        ('background', 'Background Check'),
        ('medical', 'Medical Fitness'),
        ('other', 'Other'),
    )
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('cleared', 'Cleared'),
        ('failed', 'Failed'),
        ('expired', 'Expired'),
    )

    check_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    employee = models.ForeignKey(Employee, on_delete=models.RESTRICT, db_column='employee_id', related_name='checks')
    check_type = models.CharField(max_length=40, choices=CHECK_TYPE_CHOICES)
    provider = models.CharField(max_length=160, null=True, blank=True)
    requested_at = models.DateField(null=True, blank=True)
    completed_at = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    result_reference = models.TextField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'employee_checks'


class LeaveRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    )

    leave_request_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    employee = models.ForeignKey(Employee, on_delete=models.RESTRICT, db_column='employee_id', related_name='leaves')
    leave_type = models.CharField(max_length=50)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.UUIDField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'leave_requests'


class GuardStatusHistory(models.Model):
    history_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    employee = models.ForeignKey(Employee, on_delete=models.RESTRICT, db_column='employee_id', related_name='status_history')
    previous_status = models.CharField(max_length=30, null=True, blank=True)
    new_status = models.CharField(max_length=30)
    reason = models.TextField()
    changed_by_user_id = models.UUIDField(null=True, blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'guard_status_history'


class GuardDisciplinaryRecord(models.Model):
    record_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    employee = models.ForeignKey(Employee, on_delete=models.RESTRICT, db_column='employee_id', related_name='disciplinary_records')
    category = models.CharField(max_length=60)
    incident_date = models.DateField()
    remarks = models.TextField()
    is_visible_to_guard = models.BooleanField(default=False)
    created_by_user_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'guard_disciplinary_records'


class GuardIdCard(models.Model):
    card_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    employee = models.ForeignKey(Employee, on_delete=models.RESTRICT, db_column='employee_id', related_name='id_cards')
    employee_code = models.CharField(max_length=50)
    issued_at = models.DateTimeField(auto_now_add=True)
    valid_until = models.DateField(null=True, blank=True)
    reissue_count = models.IntegerField(default=0)
    qr_payload = models.TextField()
    pdf_path = models.TextField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'guard_id_cards'


class ProfileChangeRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )

    request_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    employee = models.ForeignKey(Employee, on_delete=models.RESTRICT, db_column='employee_id', related_name='change_requests')
    field_name = models.CharField(max_length=50)
    current_value = models.TextField(null=True, blank=True)
    proposed_value = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reviewed_by_user_id = models.UUIDField(null=True, blank=True)
    review_notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'profile_change_requests'
