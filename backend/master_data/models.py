import uuid
from django.db import models


class Company(models.Model):
    company_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    legal_name = models.CharField(max_length=200)
    trade_name = models.CharField(max_length=200, null=True, blank=True)
    registration_no = models.CharField(max_length=100, null=True, blank=True)
    gstin = models.CharField(max_length=15, null=True, blank=True)
    pan = models.CharField(max_length=10, null=True, blank=True)
    email = models.CharField(max_length=254, null=True, blank=True)
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
    district = models.CharField(max_length=100, null=True, blank=True)
    psara_number = models.CharField(max_length=100, null=True, blank=True)
    psara_validity = models.DateField(null=True, blank=True)
    logo_url = models.TextField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'companies'


class Client(models.Model):
    client_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    company = models.ForeignKey(Company, on_delete=models.RESTRICT, db_column='company_id', related_name='clients')
    client_code = models.CharField(max_length=40)
    legal_name = models.CharField(max_length=200)
    display_name = models.CharField(max_length=200, null=True, blank=True)
    client_type = models.CharField(max_length=30, default='corporate')
    gstin = models.CharField(max_length=15, null=True, blank=True)
    pan = models.CharField(max_length=10, null=True, blank=True)
    billing_email = models.CharField(max_length=254, null=True, blank=True)
    billing_phone = models.CharField(max_length=30, null=True, blank=True)
    billing_address = models.JSONField(null=True, blank=True)
    payment_terms_days = models.IntegerField(default=30)
    status = models.CharField(max_length=20, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'clients'


class ClientContact(models.Model):
    contact_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, db_column='client_id', related_name='contacts')
    contact_name = models.CharField(max_length=160)
    designation = models.CharField(max_length=100, null=True, blank=True)
    email = models.CharField(max_length=254, null=True, blank=True)
    phone = models.CharField(max_length=30)
    contact_type = models.CharField(max_length=40, default='general')
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    contact_role = models.CharField(max_length=30, default='general')
    is_active = models.BooleanField(default=True)

    class Meta:
        managed = False
        db_table = 'client_contacts'


class ClientSite(models.Model):
    site_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    client = models.ForeignKey(Client, on_delete=models.RESTRICT, db_column='client_id', related_name='sites')
    branch_id = models.UUIDField(null=True, blank=True)
    site_code = models.CharField(max_length=40)
    site_name = models.CharField(max_length=180)
    site_type = models.CharField(max_length=40, null=True, blank=True)
    address_line1 = models.CharField(max_length=200, default='N/A')
    address_line2 = models.CharField(max_length=200, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    state_code = models.CharField(max_length=10, default='KA')
    postal_code = models.CharField(max_length=20, null=True, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    geofence_radius_m = models.IntegerField(null=True, blank=True)
    site_contact_name = models.CharField(max_length=160, null=True, blank=True)
    site_contact_phone = models.CharField(max_length=30, null=True, blank=True)
    operational_status = models.CharField(max_length=20, default='planned')
    created_at = models.DateTimeField(auto_now_add=True)
    district = models.CharField(max_length=100, null=True, blank=True)
    guard_instructions = models.TextField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'client_sites'


class SiteGeofence(models.Model):
    geofence_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    site = models.ForeignKey(ClientSite, on_delete=models.RESTRICT, db_column='site_id', related_name='geofences')
    version = models.IntegerField(default=1)
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    radius_meters = models.DecimalField(max_digits=8, decimal_places=2)
    is_active = models.BooleanField(default=True)
    effective_from = models.DateTimeField()
    effective_to = models.DateTimeField(null=True, blank=True)
    reason_for_change = models.TextField(null=True, blank=True)
    created_by_user_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'site_geofences'


class SiteSupervisorAssignment(models.Model):
    assignment_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    site = models.ForeignKey(ClientSite, on_delete=models.RESTRICT, db_column='site_id', related_name='supervisor_assignments')
    supervisor_user_id = models.UUIDField()
    role_type = models.CharField(max_length=20, default='primary')
    effective_from = models.DateTimeField()
    effective_to = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    assignment_reason = models.TextField(null=True, blank=True)
    assigned_by_user_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'site_supervisor_assignments'


class PostType(models.Model):
    post_type_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    company = models.ForeignKey(Company, on_delete=models.RESTRICT, db_column='company_id', related_name='post_types')
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=100)
    requires_armed_authorization = models.BooleanField(default=False)
    description = models.TextField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'post_types'


class ShiftTemplate(models.Model):
    template_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    company = models.ForeignKey(Company, on_delete=models.RESTRICT, db_column='company_id', related_name='shift_templates')
    template_code = models.CharField(max_length=30)
    template_name = models.CharField(max_length=100)
    start_time = models.TimeField()
    end_time = models.TimeField()
    duration_minutes = models.IntegerField()
    is_cross_midnight = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'shift_templates'


class SiteShift(models.Model):
    shift_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    site = models.ForeignKey(ClientSite, on_delete=models.RESTRICT, db_column='site_id', related_name='shifts')
    shift_code = models.CharField(max_length=30)
    shift_name = models.CharField(max_length=100)
    start_time = models.TimeField()
    end_time = models.TimeField()
    duration_minutes = models.IntegerField()
    is_cross_midnight = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'site_shifts'


class SiteManpowerRequirement(models.Model):
    requirement_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    site = models.ForeignKey(ClientSite, on_delete=models.RESTRICT, db_column='site_id', related_name='manpower_requirements')
    shift = models.ForeignKey(SiteShift, on_delete=models.RESTRICT, db_column='shift_id')
    post_type = models.ForeignKey(PostType, on_delete=models.RESTRICT, db_column='post_type_id')
    required_count = models.IntegerField()
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    version = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_by_user_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'site_manpower_requirements'


class ServiceAgreement(models.Model):
    agreement_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    client = models.ForeignKey(Client, on_delete=models.RESTRICT, db_column='client_id', related_name='agreements')
    site = models.ForeignKey(ClientSite, on_delete=models.RESTRICT, db_column='site_id', null=True, blank=True, related_name='agreements')
    agreement_reference = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    document_path = models.TextField(null=True, blank=True)
    document_filename = models.CharField(max_length=255, null=True, blank=True)
    document_mime_type = models.CharField(max_length=100, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(null=True, blank=True)
    created_by_user_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'service_agreements'


class ClientBillingRate(models.Model):
    rate_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    client = models.ForeignKey(Client, on_delete=models.RESTRICT, db_column='client_id', related_name='billing_rates')
    site = models.ForeignKey(ClientSite, on_delete=models.RESTRICT, db_column='site_id', null=True, blank=True, related_name='billing_rates')
    post_type = models.ForeignKey(PostType, on_delete=models.RESTRICT, db_column='post_type_id')
    rate_type = models.CharField(max_length=20, default='hourly')
    rate_amount = models.DecimalField(max_digits=12, decimal_places=2)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    version = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_by_user_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'client_billing_rates'
