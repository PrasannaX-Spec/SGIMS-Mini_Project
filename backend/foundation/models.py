import uuid
from django.db import models


class Company(models.Model):
    company_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_name = models.CharField(max_length=200)
    trade_name = models.CharField(max_length=200, null=True, blank=True)
    registration_no = models.CharField(max_length=100, unique=True, null=True, blank=True)
    gstin = models.CharField(max_length=15, unique=True, null=True, blank=True)
    pan = models.CharField(max_length=10, null=True, blank=True)
    email = models.EmailField(max_length=254, null=True, blank=True)
    phone = models.CharField(max_length=30, null=True, blank=True)
    address_line1 = models.CharField(max_length=200, null=True, blank=True)
    address_line2 = models.CharField(max_length=200, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    state_code = models.CharField(max_length=10, null=True, blank=True)
    postal_code = models.CharField(max_length=20, null=True, blank=True)
    country_code = models.CharField(max_length=2, default='IN')
    time_zone = models.CharField(max_length=50, default='Asia/Kolkata')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'companies'
        managed = False

    def __str__(self):
        return self.legal_name


class User(models.Model):
    ROLE_CHOICES = (
        ('ADMIN', 'Admin'),
        ('SUPERVISOR', 'Supervisor'),
        ('GUARD', 'Guard'),
        ('CLIENT', 'Client'),
    )
    STATUS_CHOICES = (
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
    )

    user_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.RESTRICT, db_column='company_id', related_name='users')
    branch_id = models.UUIDField(null=True, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='GUARD')
    full_name = models.CharField(max_length=160)
    email = models.CharField(max_length=254, null=True, blank=True)
    phone = models.CharField(max_length=30, null=True, blank=True)
    password_hash = models.TextField()
    must_change_password = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    failed_attempts = models.IntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    last_login_at = models.DateTimeField(null=True, blank=True)
    guard_profile_id = models.UUIDField(null=True, blank=True)
    client_company_id = models.UUIDField(null=True, blank=True)
    contact_phone = models.CharField(max_length=30, null=True, blank=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)
    deactivated_by = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, db_column='deactivated_by', related_name='deactivated_users')
    deactivation_reason = models.TextField(null=True, blank=True)
    version = models.IntegerField(default=1)
    created_by = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, db_column='created_by', related_name='created_users')
    updated_by = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, db_column='updated_by', related_name='updated_users')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'app_users'
        managed = False

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    @property
    def is_active(self):
        return self.status == 'ACTIVE'

    def __str__(self):
        return f"{self.full_name} ({self.role})"


class ScopeGrant(models.Model):
    SCOPE_TYPES = (
        ('ALL', 'All'),
        ('SITE', 'Site'),
        ('GUARD', 'Guard'),
        ('COMPANY', 'Company'),
        ('OWN_PROFILE', 'Own Profile'),
    )

    grant_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.RESTRICT, db_column='company_id')
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='user_id', related_name='scope_grants')
    scope_type = models.CharField(max_length=20, choices=SCOPE_TYPES)
    target_id = models.UUIDField(null=True, blank=True)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, db_column='created_by', related_name='+')

    class Meta:
        db_table = 'scope_grants'
        managed = False


class UserSession(models.Model):
    PLATFORMS = (
        ('WEB', 'Web'),
        ('ANDROID', 'Android'),
    )
    REVOKED_REASONS = (
        ('LOGOUT', 'Logout'),
        ('LOGOUT_ALL', 'Logout All Devices'),
        ('PASSWORD_CHANGE', 'Password Changed'),
        ('DEACTIVATED', 'User Deactivated'),
        ('DEVICE_CHANGE', 'Device Change Approved'),
        ('ROLE_CHANGE', 'Role Changed'),
        ('TOKEN_REUSE', 'Refresh Token Reused'),
        ('EXPIRED_BY_ADMIN', 'Session Expired by Admin'),
        ('IDLE_TIMEOUT', 'Idle Timeout'),
    )

    session_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.RESTRICT, db_column='company_id')
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='user_id', related_name='sessions')
    platform = models.CharField(max_length=20, choices=PLATFORMS)
    device_id = models.TextField(null=True, blank=True)
    ip_address = models.CharField(max_length=45)
    user_agent = models.TextField(null=True, blank=True)
    session_token_hash = models.TextField()
    refresh_token_hash = models.TextField(null=True, blank=True)
    issued_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_reason = models.CharField(max_length=30, choices=REVOKED_REASONS, null=True, blank=True)

    class Meta:
        db_table = 'user_sessions'
        managed = False


class BoundDevice(models.Model):
    UNBOUND_REASONS = (
        ('CHANGE_APPROVED', 'Change Approved'),
        ('ADMIN_RESET', 'Admin Reset'),
    )

    bound_device_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.RESTRICT, db_column='company_id')
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='user_id', related_name='bound_devices')
    device_id = models.TextField()
    model = models.TextField(null=True, blank=True)
    os_version = models.TextField(null=True, blank=True)
    app_version = models.TextField(null=True, blank=True)
    bound_at = models.DateTimeField(auto_now_add=True)
    unbound_at = models.DateTimeField(null=True, blank=True)
    unbound_reason = models.CharField(max_length=30, choices=UNBOUND_REASONS, null=True, blank=True)

    class Meta:
        db_table = 'bound_devices'
        managed = False


class DeviceChangeRequest(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('EXPIRED', 'Expired'),
        ('SUPERSEDED', 'Superseded'),
    )

    request_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.RESTRICT, db_column='company_id')
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='user_id', related_name='device_change_requests')
    new_device_id = models.TextField()
    new_model = models.TextField(null=True, blank=True)
    new_os_version = models.TextField(null=True, blank=True)
    new_app_version = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    requested_at = models.DateTimeField(auto_now_add=True)
    last_attempt_at = models.DateTimeField(auto_now=True)
    decided_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, db_column='decided_by', related_name='+')
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'device_change_requests'
        managed = False


class LoginAttempt(models.Model):
    RESULTS = (
        ('SUCCESS', 'Success'),
        ('WRONG_PASSWORD', 'Wrong Password'),
        ('LOCKED', 'Locked'),
        ('INACTIVE', 'Inactive'),
        ('NOT_LINKED', 'Not Linked'),
        ('WRONG_PLATFORM', 'Wrong Platform'),
        ('DEVICE_PENDING', 'Device Pending'),
        ('FORMAT_ERROR', 'Format Error'),
        ('RATE_LIMITED', 'Rate Limited'),
    )

    attempt_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, null=True, blank=True, on_delete=models.SET_NULL, db_column='company_id')
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, db_column='user_id', related_name='login_attempts')
    identifier_entered = models.TextField(null=True, blank=True)
    result = models.CharField(max_length=30, choices=RESULTS)
    platform = models.CharField(max_length=20, null=True, blank=True)
    ip_address = models.CharField(max_length=45, null=True, blank=True)
    device_id = models.TextField(null=True, blank=True)
    device_model = models.TextField(null=True, blank=True)
    app_version = models.TextField(null=True, blank=True)
    attempted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'login_attempts'
        managed = False


class OneTimeToken(models.Model):
    PURPOSES = (
        ('RESET', 'Password Reset'),
        ('INVITE', 'User Invite'),
    )

    token_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.RESTRICT, db_column='company_id')
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='user_id', related_name='one_time_tokens')
    purpose = models.CharField(max_length=20, choices=PURPOSES)
    token_hash = models.TextField()
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'one_time_tokens'
        managed = False


class NotificationType(models.Model):
    PRIORITIES = (
        ('NORMAL', 'Normal'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    )

    type_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=80, unique=True)
    title_key = models.CharField(max_length=120)
    body_key = models.CharField(max_length=120)
    recipient_rule = models.CharField(max_length=80)
    channels = models.JSONField(default=list)
    priority = models.CharField(max_length=20, choices=PRIORITIES, default='NORMAL')
    related_record_type = models.CharField(max_length=80, null=True, blank=True)

    class Meta:
        db_table = 'notification_types'
        managed = False

    def __str__(self):
        return f"{self.code} ({self.priority})"


class Notification(models.Model):
    notification_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.RESTRICT, db_column='company_id')
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='user_id', related_name='notifications')
    channel = models.CharField(max_length=20, default='in_app')
    type_code = models.CharField(max_length=80, db_column='event_type')
    params = models.JSONField(default=dict)
    subject = models.CharField(max_length=200, null=True, blank=True)
    message = models.TextField()
    related_record_type = models.CharField(max_length=80, null=True, blank=True)
    related_record_id = models.UUIDField(null=True, blank=True)
    dedupe_key = models.CharField(max_length=120, null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notifications'
        managed = False


class NotificationDelivery(models.Model):
    CHANNELS = (
        ('IN', 'In-App'),
        ('PUSH', 'Push Notification'),
        ('WEB', 'Web Notification'),
        ('SMS', 'SMS Fallback'),
    )
    STATUSES = (
        ('QUEUED', 'Queued'),
        ('SENT', 'Sent'),
        ('FAILED', 'Failed'),
        ('SKIPPED', 'Skipped'),
        ('NOT_CONFIGURED', 'Not Configured'),
    )

    delivery_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, db_column='notification_id', related_name='deliveries')
    channel = models.CharField(max_length=20, choices=CHANNELS)
    status = models.CharField(max_length=20, choices=STATUSES, default='QUEUED')
    attempts = models.IntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'notification_deliveries'
        managed = False


class PushToken(models.Model):
    token_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.RESTRICT, db_column='company_id')
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='user_id', related_name='push_tokens')
    session = models.ForeignKey(UserSession, null=True, blank=True, on_delete=models.CASCADE, db_column='session_id')
    token = models.TextField()
    registered_at = models.DateTimeField(auto_now_add=True)
    removed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'push_tokens'
        managed = False


class NotificationPreference(models.Model):
    preference_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, db_column='user_id', related_name='notification_preference')
    push_normal = models.BooleanField(default=True)
    browser_notifications = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'notification_preferences'
        managed = False


class AuditEvent(models.Model):
    RESULTS = (
        ('SUCCESS', 'Success'),
        ('FAILURE', 'Failure'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    occurred_at = models.DateTimeField(auto_now_add=True)
    company_id = models.UUIDField()
    actor_user_id = models.UUIDField(null=True, blank=True)
    actor_role = models.CharField(max_length=20)
    actor_name = models.CharField(max_length=160)
    action_code = models.CharField(max_length=80)
    module = models.CharField(max_length=50, default='foundation')
    record_type = models.CharField(max_length=80, null=True, blank=True)
    record_id = models.TextField(null=True, blank=True)
    result = models.CharField(max_length=20, choices=RESULTS)
    old_values = models.JSONField(null=True, blank=True)
    new_values = models.JSONField(null=True, blank=True)
    reason = models.TextField(null=True, blank=True)
    ip_address = models.CharField(max_length=45, null=True, blank=True)
    device_id = models.TextField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    request_id = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'audit_events'
        managed = False


class ConsentRecord(models.Model):
    ITEMS = (
        ('TERMS_PRIVACY', 'Terms and Privacy Policy'),
        ('LOCATION', 'Location Tracking'),
        ('CAMERA', 'Camera Access'),
        ('NOTIFICATIONS', 'Push Notifications'),
    )
    DECISIONS = (
        ('GRANTED', 'Granted'),
        ('DENIED', 'Denied'),
        ('WITHDRAWN', 'Withdrawn'),
    )

    consent_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.RESTRICT, db_column='company_id')
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='user_id', related_name='consent_records')
    item = models.CharField(max_length=30, choices=ITEMS)
    decision = models.CharField(max_length=20, choices=DECISIONS)
    policy_version = models.CharField(max_length=50)
    recorded_at = models.DateTimeField(auto_now_add=True)
    device_id = models.TextField(null=True, blank=True)
    app_version = models.TextField(null=True, blank=True)
    ip_address = models.CharField(max_length=45, null=True, blank=True)

    class Meta:
        db_table = 'consent_records'
        managed = False


class SystemSetting(models.Model):
    setting_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.RESTRICT, db_column='company_id')
    key = models.CharField(max_length=100)
    value = models.TextField()
    updated_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, db_column='updated_by', related_name='+')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'system_settings'
        managed = False
        unique_together = ('company', 'key')
