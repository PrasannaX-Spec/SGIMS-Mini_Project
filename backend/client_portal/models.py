import uuid
from django.db import models
from foundation.models import Company, User
from master_data.models import Client, ClientSite


class ClientUserSiteAccess(models.Model):
    ACCESS_MODES = (
        ('ALL_SITES', 'All Company Sites'),
        ('SELECTED_SITES', 'Selected Sites'),
    )

    access_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.RESTRICT, db_column='company_id', related_name='client_site_accesses')
    client_user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='client_user_id', related_name='site_access_restrictions')
    access_mode = models.CharField(max_length=30, choices=ACCESS_MODES, default='ALL_SITES')
    site = models.ForeignKey(ClientSite, on_delete=models.CASCADE, null=True, blank=True, db_column='site_id', related_name='client_access_grants')
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, db_column='created_by', related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, db_column='updated_by', related_name='+')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'client_user_site_access'
        unique_together = ('client_user', 'site')

    def __str__(self):
        return f"{self.client_user.full_name} -> {self.access_mode} ({self.site_id or 'All'})"


class ClientPortalConfiguration(models.Model):
    SHARING_DEFAULTS = (
        ('EXPLICIT_APPROVAL', 'Explicit Approval Only'),
        ('ALL_RESOLVED', 'All Resolved Incidents'),
        ('CUSTOM', 'Custom Rule'),
    )

    configuration_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.RESTRICT, db_column='company_id', related_name='portal_configurations')
    client = models.OneToOneField(Client, on_delete=models.CASCADE, db_column='client_id', related_name='portal_configuration')
    future_roster_visibility = models.BooleanField(default=False)
    incident_sharing_default = models.CharField(max_length=50, choices=SHARING_DEFAULTS, default='EXPLICIT_APPROVAL')
    retention_window_days = models.IntegerField(default=365)
    checkin_photo_visibility = models.BooleanField(default=False)
    invoices_enabled = models.BooleanField(default=False)
    requests_enabled = models.BooleanField(default=True)
    documents_enabled = models.BooleanField(default=True)
    announcements_enabled = models.BooleanField(default=True)
    enabled_sections = models.JSONField(default=list)
    updated_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, db_column='updated_by', related_name='+')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'client_portal_configurations'

    def __str__(self):
        return f"Config for {self.client.client_name}"


class ClientNotificationPreference(models.Model):
    CATEGORIES = (
        ('DEPLOYMENT', 'Deployment & Shifts'),
        ('ATTENDANCE', 'Attendance Updates'),
        ('INCIDENT', 'Shared Incidents'),
        ('BILLING', 'Billing & Invoices'),
        ('TICKET', 'Ticket Responses'),
        ('GENERAL', 'General Service Information'),
        ('ANNOUNCEMENT', 'Company Announcements'),
        ('PANIC', 'Emergency Panic Notices'),
    )

    preference_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.RESTRICT, db_column='company_id', related_name='client_notification_preferences')
    client_user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='client_user_id', related_name='notification_preferences')
    notification_category = models.CharField(max_length=50, choices=CATEGORIES)
    enabled = models.BooleanField(default=True)
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)
    frequency_limit = models.IntegerField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'client_notification_preferences'
        unique_together = ('client_user', 'notification_category')

    def __str__(self):
        return f"{self.client_user.full_name} - {self.notification_category}: {self.enabled}"


class ClientDocumentAccessLog(models.Model):
    SOURCES = (
        ('MODULE_1', 'Module 1: Foundation Files'),
        ('MODULE_2', 'Module 2: Master Service Agreement'),
        ('MODULE_6', 'Module 6: Attendance Export'),
        ('MODULE_11', 'Module 11: Billing Invoices'),
    )
    RESULTS = (
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
    )
    FILE_TYPES = (
        ('PDF', 'PDF Document'),
        ('CSV', 'CSV Spreadsheet'),
        ('DOCX', 'Word Document'),
        ('XLSX', 'Excel Spreadsheet'),
        ('OTHER', 'Other File'),
    )

    download_log_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.RESTRICT, db_column='company_id', related_name='document_download_logs')
    client_user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='client_user_id', related_name='document_downloads')
    document_id = models.UUIDField()
    source_module = models.CharField(max_length=30, choices=SOURCES, default='MODULE_2')
    site = models.ForeignKey(ClientSite, on_delete=models.SET_NULL, null=True, blank=True, db_column='site_id', related_name='+')
    requested_at = models.DateTimeField(auto_now_add=True)
    result = models.CharField(max_length=20, choices=RESULTS, default='SUCCESS')
    file_type = models.CharField(max_length=20, choices=FILE_TYPES, default='PDF')
    access_reference = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'client_document_access_logs'
        ordering = ['-requested_at']

    def __str__(self):
        return f"{self.client_user.full_name} downloaded {self.document_id} ({self.result})"


class ClientPortalUsageEvent(models.Model):
    EVENT_TYPES = (
        ('FIRST_LOGIN', 'First Login'),
        ('LOGIN', 'Standard Login'),
        ('TICKET_RAISED', 'Ticket Raised'),
        ('DOCUMENT_DOWNLOAD', 'Document Download'),
        ('PREVIEW', 'Admin Preview Mode'),
        ('ATTENDANCE_QUERY', 'Attendance Query Submitted'),
        ('POST_ISSUE', 'Post Issue Reported'),
    )
    SOURCES = (
        ('MOBILE_APP', 'Client Mobile Application'),
        ('WEB_PORTAL', 'Web Console Client Portal'),
        ('ADMIN_PREVIEW', 'Admin Simulation Preview'),
    )

    usage_event_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.RESTRICT, db_column='company_id', related_name='portal_usage_events')
    client_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, db_column='client_user_id', related_name='portal_events')
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    related_record_id = models.UUIDField(null=True, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)
    source = models.CharField(max_length=30, choices=SOURCES, default='MOBILE_APP')

    class Meta:
        managed = False
        db_table = 'client_portal_usage_events'
        ordering = ['-occurred_at']

    def __str__(self):
        return f"{self.event_type} by {self.client_user_id} at {self.occurred_at}"


class ClientAnnouncement(models.Model):
    STATUS_CHOICES = (
        ('DRAFT', 'Draft'),
        ('SCHEDULED', 'Scheduled'),
        ('ACTIVE', 'Active'),
        ('EXPIRED', 'Expired'),
        ('CANCELLED', 'Cancelled'),
    )

    announcement_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.RESTRICT, db_column='company_id', related_name='client_announcements')
    target_client = models.ForeignKey(Client, on_delete=models.CASCADE, null=True, blank=True, db_column='target_client_id', related_name='announcements')
    title = models.CharField(max_length=200)
    message = models.TextField()
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, db_column='created_by', related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'client_announcements'
        ordering = ['-starts_at']

    def __str__(self):
        return self.title
