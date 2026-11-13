import uuid
from django.db import models
from django.contrib.postgres.fields import ArrayField
from master_data.models import Company, Client, ClientSite, PostType, ServiceAgreement


class ServiceRequest(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('awaiting_client', 'Awaiting Client'),
        ('survey_scheduled', 'Survey Scheduled'),
        ('quoted', 'Quoted'),
        ('countered', 'Countered'),
        ('revised', 'Revised'),
        ('accepted', 'Accepted'),
        ('rejected_by_client', 'Rejected by Client'),
        ('rejected_by_agency', 'Rejected by Agency'),
        ('expired', 'Expired'),
        ('withdrawn', 'Withdrawn'),
        ('converted', 'Converted'),
        ('cancelled', 'Cancelled'),
    )

    request_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    company = models.ForeignKey(Company, on_delete=models.RESTRICT, db_column='company_id', related_name='service_requests')
    client = models.ForeignKey(Client, on_delete=models.RESTRICT, db_column='client_id', related_name='service_requests')
    request_reference = models.CharField(max_length=50, unique=True)
    submission_reference = models.CharField(max_length=100, unique=True, null=True, blank=True)
    existing_site = models.ForeignKey(ClientSite, on_delete=models.SET_NULL, null=True, blank=True, db_column='existing_site_id', related_name='service_requests')
    new_site_name = models.CharField(max_length=180, null=True, blank=True)
    new_site_address = models.TextField(null=True, blank=True)
    new_site_latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    new_site_longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    service_purpose = models.CharField(max_length=30)
    start_date = models.DateField()
    duration_type = models.CharField(max_length=20, default='ongoing')
    end_date = models.DateField(null=True, blank=True)
    site_contact_name = models.CharField(max_length=160)
    site_contact_phone = models.CharField(max_length=30)
    special_requirements = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='draft')
    assigned_owner_id = models.UUIDField(null=True, blank=True)
    created_by_user_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'service_requests'


class ServiceRequestLine(models.Model):
    request_line_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE, db_column='request_id', related_name='lines')
    post_type = models.ForeignKey(PostType, on_delete=models.RESTRICT, db_column='post_type_id')
    guard_count = models.IntegerField()
    shift_information = models.CharField(max_length=100)
    hours_per_day = models.DecimalField(max_digits=4, decimal_places=1, default=8.0)
    working_days = ArrayField(models.CharField(max_length=20), default=list)
    armed_required = models.BooleanField(default=False)

    class Meta:
        managed = False
        db_table = 'service_request_lines'


class ServiceRequestAttachment(models.Model):
    attachment_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE, db_column='request_id', related_name='attachments')
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=100)
    storage_key = models.TextField()
    file_size = models.IntegerField()
    uploaded_by_user_id = models.UUIDField(null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'service_request_attachments'


class ServiceRequestComment(models.Model):
    comment_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE, db_column='request_id', related_name='comments')
    sender_user_id = models.UUIDField(null=True, blank=True)
    sender_role = models.CharField(max_length=20)
    message = models.TextField()
    is_clarification_request = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'service_request_comments'


class ServiceSiteSurvey(models.Model):
    survey_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE, db_column='request_id', related_name='surveys')
    survey_date = models.DateField()
    visited_by = models.CharField(max_length=160)
    assigned_supervisor_id = models.UUIDField(null=True, blank=True)
    findings = models.TextField()
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'service_site_surveys'


class Quotation(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('negotiation', 'Negotiation'),
        ('sent', 'Sent'),
        ('countered', 'Countered'),
        ('revised', 'Revised'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
        ('converted', 'Converted'),
    )

    quotation_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    company = models.ForeignKey(Company, on_delete=models.RESTRICT, db_column='company_id', related_name='quotations')
    client = models.ForeignKey(Client, on_delete=models.RESTRICT, db_column='client_id', related_name='quotations')
    request = models.ForeignKey(ServiceRequest, on_delete=models.RESTRICT, db_column='request_id', related_name='quotations', null=True, blank=True)
    quotation_no = models.CharField(max_length=50)
    version_no = models.IntegerField(default=1)
    current_version = models.IntegerField(default=1)
    issue_date = models.DateField()
    valid_until = models.DateField(null=True, blank=True)
    currency = models.CharField(max_length=3, default='INR')
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_by = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'quotations'


class QuotationVersion(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('superseded', 'Superseded'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
    )

    quotation_version_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    quotation = models.ForeignKey(Quotation, on_delete=models.RESTRICT, db_column='quotation_id', related_name='versions')
    version_number = models.IntegerField()
    quotation_date = models.DateField()
    validity_date = models.DateField()
    subtotal = models.DecimalField(max_digits=14, decimal_places=2)
    tax_note = models.CharField(max_length=50, default='Applicable taxes extra')
    payment_terms = models.TextField(null=True, blank=True)
    additional_terms = models.TextField(null=True, blank=True)
    internal_notes = models.TextField(null=True, blank=True)
    pdf_path = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_by_user_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'quotation_versions'


class QuotationLine(models.Model):
    quotation_line_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, db_column='quotation_id', related_name='lines')
    quotation_version = models.ForeignKey(QuotationVersion, on_delete=models.CASCADE, db_column='quotation_version_id', related_name='lines', null=True, blank=True)
    post_type = models.ForeignKey(PostType, on_delete=models.RESTRICT, db_column='post_type_id', null=True, blank=True)
    shift_hours = models.DecimalField(max_digits=4, decimal_places=1, default=8.0)
    headcount = models.IntegerField()
    billing_unit = models.CharField(max_length=30, default='per_guard_per_month')
    unit_rate = models.DecimalField(max_digits=12, decimal_places=2)
    line_total = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        managed = False
        db_table = 'quotation_lines'


class QuotationAcceptance(models.Model):
    acceptance_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    quotation_version = models.ForeignKey(QuotationVersion, on_delete=models.RESTRICT, db_column='quotation_version_id', related_name='acceptances')
    client_user_id = models.UUIDField()
    accepted_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.CharField(max_length=50, null=True, blank=True)
    device_information = models.TextField(null=True, blank=True)
    agreed_text = models.TextField()
    confirmation_value = models.BooleanField(default=True)

    class Meta:
        managed = False
        db_table = 'quotation_acceptances'


class QuotationCounter(models.Model):
    counter_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    quotation_version = models.ForeignKey(QuotationVersion, on_delete=models.RESTRICT, db_column='quotation_version_id', related_name='counters')
    client_user_id = models.UUIDField()
    comment = models.TextField()
    proposed_guard_count = models.IntegerField(null=True, blank=True)
    proposed_rate = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    proposed_start_date = models.DateField(null=True, blank=True)
    negotiation_round = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'quotation_counters'


class QuotationConversion(models.Model):
    conversion_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    quotation_version = models.ForeignKey(QuotationVersion, on_delete=models.RESTRICT, db_column='quotation_version_id', related_name='conversions')
    conversion_reference = models.CharField(max_length=60, unique=True)
    conversion_status = models.CharField(max_length=20, default='pending')
    module2_site_id = models.UUIDField(null=True, blank=True)
    module2_agreement_id = models.UUIDField(null=True, blank=True)
    generated_records = models.JSONField(default=dict)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_details = models.TextField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'quotation_conversions'
