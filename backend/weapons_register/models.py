import uuid
from django.db import models


class WeaponLocation(models.Model):
    LOCATION_TYPES = [
        ('ARMOURY', 'Armoury'),
        ('SITE_STORAGE', 'Site Storage'),
        ('GUARD_CUSTODY', 'In Custody of a Guard'),
        ('MAINTENANCE', 'With Maintenance'),
        ('AUTHORITY', 'With Authority'),
        ('UNKNOWN', 'Unknown'),
    ]

    location_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField()
    location_type = models.CharField(max_length=30, choices=LOCATION_TYPES)
    site_id = models.UUIDField(null=True, blank=True)
    name = models.CharField(max_length=150)
    description = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=20, default='ACTIVE')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'security_erp"."weapon_locations'

    def __str__(self):
        return f"{self.name} ({self.location_type})"


class WeaponLicence(models.Model):
    HOLDER_TYPES = [
        ('AGENCY', 'Agency'),
        ('NAMED_PERSON', 'Named Person'),
    ]
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('EXPIRING_SOON', 'Expiring Soon'),
        ('EXPIRED', 'Expired'),
        ('SUSPENDED', 'Suspended'),
        ('REVOKED', 'Revoked'),
    ]

    licence_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField()
    licence_number = models.CharField(max_length=100)
    licence_type = models.CharField(max_length=100)
    issuing_authority = models.CharField(max_length=200)
    holder_type = models.CharField(max_length=30, choices=HOLDER_TYPES, default='AGENCY')
    holder_name = models.CharField(max_length=200, null=True, blank=True)
    valid_from = models.DateField()
    valid_until = models.DateField()
    document_reference = models.CharField(max_length=500, null=True, blank=True)
    quantity_limit_enabled = models.BooleanField(default=False)
    quantity_limit = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    created_by = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'security_erp"."weapon_licences'

    def __str__(self):
        return f"{self.licence_number} - {self.issuing_authority}"


class Weapon(models.Model):
    STATUS_CHOICES = [
        ('IN_STORAGE', 'In Storage'),
        ('ISSUED', 'Issued'),
        ('IN_MAINTENANCE', 'In Maintenance'),
        ('DEPOSITED_WITH_AUTHORITY', 'Deposited with Authority'),
        ('MISSING', 'Missing'),
        ('LOST_OR_STOLEN', 'Lost or Stolen'),
        ('RETIRED_OR_DISPOSED', 'Retired or Disposed'),
    ]

    weapon_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField()
    asset_id = models.CharField(max_length=50, unique=True)
    weapon_type = models.CharField(max_length=100)
    make = models.CharField(max_length=100)
    model = models.CharField(max_length=100)
    calibre = models.CharField(max_length=100)
    serial_number = models.CharField(max_length=100)
    manufacture_year = models.IntegerField(null=True, blank=True)
    acquisition_date = models.DateField()
    supplier = models.CharField(max_length=200, null=True, blank=True)
    status = models.CharField(max_length=40, choices=STATUS_CHOICES, default='IN_STORAGE')
    current_location_id = models.UUIDField(null=True, blank=True)
    current_custody_id = models.UUIDField(null=True, blank=True)
    photo_url = models.CharField(max_length=500, null=True, blank=True)
    qr_relabel_count = models.IntegerField(default=0)
    qr_last_relabeled_at = models.DateTimeField(null=True, blank=True)
    status_reason = models.TextField(null=True, blank=True)
    status_updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    created_by = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'security_erp"."weapons'

    def __str__(self):
        return f"{self.asset_id} ({self.weapon_type} - {self.make} {self.model})"

    def masked_serial_number(self):
        if not self.serial_number or len(self.serial_number) < 4:
            return "***"
        return f"***{self.serial_number[-4:]}"


class WeaponLicenceAssociation(models.Model):
    association_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    weapon_id = models.UUIDField()
    licence_id = models.UUIDField()
    effective_from = models.DateField(auto_now_add=True)
    effective_to = models.DateField(null=True, blank=True)
    is_current = models.BooleanField(default=True)
    created_by = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'security_erp"."weapon_licence_associations'


class WeaponSerialRevealLog(models.Model):
    reveal_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField()
    weapon_id = models.UUIDField()
    revealed_by = models.UUIDField()
    revealed_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField()
    site_id = models.UUIDField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'security_erp"."weapon_serial_reveal_logs'


class WeaponTransfer(models.Model):
    TRANSFER_TYPES = [
        ('ISSUE', 'Issue'),
        ('RETURN', 'Return'),
        ('HANDOVER', 'Guard-to-Guard Handover'),
        ('LOCATION_TRANSFER', 'Location Transfer'),
        ('MAINTENANCE_TRANSFER', 'Maintenance Transfer'),
        ('AUTHORITY_DEPOSIT', 'Deposit with Authority'),
        ('AUTHORITY_RETURN', 'Return from Authority'),
    ]
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('ISSUE_PENDING', 'Issue Pending'),
        ('RETURN_PENDING', 'Return Pending'),
        ('HANDOVER_PENDING', 'Handover Pending'),
        ('COMPLETED', 'Completed'),
        ('DISCREPANCY', 'Discrepancy'),
        ('EXPIRED_PENDING', 'Expired Pending'),
        ('RECOVERY_REQUIRED', 'Recovery Required'),
        ('REVERSED', 'Reversed'),
    ]

    transfer_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client_generated_id = models.CharField(max_length=100)
    company_id = models.UUIDField()
    weapon_id = models.UUIDField()
    transfer_type = models.CharField(max_length=40, choices=TRANSFER_TYPES)
    from_custodian_type = models.CharField(max_length=30)
    from_custodian_id = models.UUIDField()
    to_custodian_type = models.CharField(max_length=30)
    to_custodian_id = models.UUIDField()
    site_id = models.UUIDField(null=True, blank=True)
    assignment_id = models.UUIDField(null=True, blank=True)
    attendance_id = models.UUIDField(null=True, blank=True)
    handover_id = models.UUIDField(null=True, blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='PENDING')
    condition_before = models.CharField(max_length=100, default='GOOD')
    condition_after = models.CharField(max_length=100, null=True, blank=True)
    rounds_issued = models.IntegerField(default=0)
    rounds_returned = models.IntegerField(default=0)
    rounds_expended = models.IntegerField(default=0)
    client_timestamp = models.DateTimeField(null=True, blank=True)
    server_timestamp = models.DateTimeField(auto_now_add=True)
    sync_timestamp = models.DateTimeField(null=True, blank=True)
    issuer_id = models.UUIDField(null=True, blank=True)
    guard_confirmation_id = models.UUIDField(null=True, blank=True)
    guard_confirmed_at = models.DateTimeField(null=True, blank=True)
    receiver_confirmation_id = models.UUIDField(null=True, blank=True)
    receiver_confirmed_at = models.DateTimeField(null=True, blank=True)
    is_emergency = models.BooleanField(default=False)
    emergency_reason = models.TextField(null=True, blank=True)
    emergency_ratified_by = models.UUIDField(null=True, blank=True)
    emergency_ratified_at = models.DateTimeField(null=True, blank=True)
    emergency_ratified_status = models.CharField(max_length=20, default='NONE')
    is_offline = models.BooleanField(default=False)
    reason = models.TextField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'security_erp"."weapon_transfers'


class WeaponCustodyRecord(models.Model):
    custody_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    weapon_id = models.UUIDField()
    custodian_type = models.CharField(max_length=30)
    custodian_id = models.UUIDField()
    start_transfer_id = models.UUIDField(null=True, blank=True)
    start_time = models.DateTimeField(auto_now_add=True)
    end_transfer_id = models.UUIDField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    is_current = models.BooleanField(default=True)
    ammunition_rounds = models.IntegerField(default=0)
    site_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'security_erp"."weapon_custody_records'


class AmmunitionLot(models.Model):
    STATUS_CHOICES = [
        ('AVAILABLE', 'Available'),
        ('PARTIALLY_ISSUED', 'Partially Issued'),
        ('FULLY_ISSUED', 'Fully Issued'),
        ('IN_CUSTODY', 'In Custody'),
        ('DISCREPANCY', 'Discrepancy'),
        ('DISPOSED', 'Disposed'),
        ('CLOSED', 'Closed'),
    ]

    lot_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField()
    ammunition_type = models.CharField(max_length=100)
    lot_number = models.CharField(max_length=100)
    received_date = models.DateField(null=True, blank=True)
    source_reference = models.CharField(max_length=200, null=True, blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='AVAILABLE')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'security_erp"."ammunition_lots'

    def __str__(self):
        return f"{self.ammunition_type} (Lot {self.lot_number})"


class AmmunitionLedger(models.Model):
    ENTRY_TYPES = [
        ('RECEIVED', 'Received'),
        ('TRANSFERRED', 'Transferred'),
        ('ISSUED', 'Issued to Guard'),
        ('RETURNED', 'Returned by Guard'),
        ('EXPENDED', 'Expended in Incident'),
        ('DISPOSED', 'Disposed'),
        ('ADJUSTED', 'Stock Adjustment'),
        ('REVERSED', 'Reversal'),
    ]

    ledger_entry_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client_generated_id = models.CharField(max_length=100, null=True, blank=True)
    company_id = models.UUIDField()
    lot_id = models.UUIDField()
    ammunition_type = models.CharField(max_length=100)
    entry_type = models.CharField(max_length=30, choices=ENTRY_TYPES)
    source_location_id = models.UUIDField(null=True, blank=True)
    destination_location_id = models.UUIDField(null=True, blank=True)
    weapon_id = models.UUIDField(null=True, blank=True)
    guard_id = models.UUIDField(null=True, blank=True)
    transfer_id = models.UUIDField(null=True, blank=True)
    incident_id = models.UUIDField(null=True, blank=True)
    quantity = models.IntegerField()
    reversal_reference_id = models.UUIDField(null=True, blank=True)
    reason = models.TextField(null=True, blank=True)
    approved_by = models.UUIDField(null=True, blank=True)
    actor_id = models.UUIDField(null=True, blank=True)
    server_timestamp = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'security_erp"."ammunition_ledger'


class AmmunitionStockCount(models.Model):
    count_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField()
    location_id = models.UUIDField()
    lot_id = models.UUIDField()
    ledger_quantity = models.IntegerField()
    physical_quantity = models.IntegerField()
    variance = models.IntegerField()
    reason = models.TextField(null=True, blank=True)
    counted_by = models.UUIDField()
    counted_at = models.DateTimeField(auto_now_add=True)
    adjustment_status = models.CharField(max_length=30, default='NOT_REQUIRED')
    adjustment_approved_by = models.UUIDField(null=True, blank=True)
    adjustment_approved_at = models.DateTimeField(null=True, blank=True)
    adjustment_ledger_entry_id = models.UUIDField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'security_erp"."ammunition_stock_counts'


class WeaponDiscrepancy(models.Model):
    DISCREPANCY_TYPES = [
        ('IDENTITY', 'Weapon Identity Mismatch'),
        ('ROUNDS', 'Ammunition Count Mismatch'),
        ('CONDITION', 'Condition Mismatch / Damage'),
        ('LOCATION', 'Location Discrepancy'),
        ('CUSTODY', 'Custody Conflict'),
        ('OFFLINE_CONFLICT', 'Offline Sync Conflict'),
        ('OTHER', 'Other Discrepancy'),
    ]
    STATUS_CHOICES = [
        ('OPEN', 'Open'),
        ('UNDER_REVIEW', 'Under Review'),
        ('RESOLVED', 'Resolved'),
    ]

    discrepancy_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField()
    weapon_id = models.UUIDField(null=True, blank=True)
    transfer_id = models.UUIDField(null=True, blank=True)
    ledger_entry_id = models.UUIDField(null=True, blank=True)
    guard_id = models.UUIDField(null=True, blank=True)
    site_id = models.UUIDField(null=True, blank=True)
    discrepancy_type = models.CharField(max_length=40, choices=DISCREPANCY_TYPES)
    expected_value = models.JSONField(default=dict)
    reported_value = models.JSONField(default=dict)
    recount_value = models.JSONField(null=True, blank=True)
    explanation = models.TextField(null=True, blank=True)
    outcome = models.TextField(null=True, blank=True)
    incident_id = models.UUIDField(null=True, blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='OPEN')
    is_blocking = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.UUIDField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'security_erp"."weapon_discrepancies'


class GuardWeaponBlock(models.Model):
    STATUS_CHOICES = [
        ('ACTIVE', 'Active Block'),
        ('REVERSED', 'Reversed'),
    ]

    block_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField()
    guard_id = models.UUIDField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    reason = models.TextField()
    created_by = models.UUIDField()
    created_at = models.DateTimeField(auto_now_add=True)
    reversed_by = models.UUIDField(null=True, blank=True)
    reversal_reason = models.TextField(null=True, blank=True)
    reversed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'security_erp"."guard_weapon_blocks'


class WeaponRecovery(models.Model):
    TRIGGER_REASONS = [
        ('SUSPENSION', 'Guard Suspended'),
        ('RESIGNATION', 'Guard Resigned'),
        ('TERMINATION', 'Guard Terminated'),
        ('NOT_DEPLOYABLE', 'Guard Not Deployable'),
        ('ARMS_DOCUMENT_EXPIRY', 'Guard Arms Document Expired'),
        ('DISCREPANCY', 'Custody Discrepancy'),
    ]
    STATUS_CHOICES = [
        ('RECOVERY_REQUIRED', 'Recovery Required'),
        ('IN_PROGRESS', 'Recovery In Progress'),
        ('CLOSED', 'Closed'),
    ]

    recovery_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField()
    guard_id = models.UUIDField()
    weapon_id = models.UUIDField()
    ammunition_rounds = models.IntegerField(default=0)
    trigger_reason = models.CharField(max_length=50, choices=TRIGGER_REASONS)
    trigger_timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='RECOVERY_REQUIRED')
    supervisor_id = models.UUIDField(null=True, blank=True)
    last_known_site_id = models.UUIDField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    return_transfer_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'security_erp"."weapon_recoveries'


class WeaponMaintenanceLog(models.Model):
    MAINTENANCE_TYPES = [
        ('INSPECTION', 'Periodic Inspection'),
        ('REPAIR', 'Repair & Service'),
        ('CLEANING', 'Armoury Cleaning'),
        ('TEST', 'Test Firing / Proof Test'),
        ('OTHER', 'Other Maintenance'),
    ]
    OUTCOME_CHOICES = [
        ('PASSED', 'Passed Inspection'),
        ('REPAIRED', 'Successfully Repaired'),
        ('FAILED', 'Failed Inspection'),
        ('PENDING_PARTS', 'Pending Parts'),
        ('UNSERVICEABLE', 'Unserviceable / Decommission Recommended'),
    ]

    maintenance_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    weapon_id = models.UUIDField()
    company_id = models.UUIDField()
    record_date = models.DateField(auto_now_add=True)
    maintenance_type = models.CharField(max_length=30, choices=MAINTENANCE_TYPES)
    done_by = models.CharField(max_length=150)
    outcome = models.CharField(max_length=50, choices=OUTCOME_CHOICES)
    next_due_date = models.DateField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    created_by = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'security_erp"."weapon_maintenance_logs'


class WeaponAlert(models.Model):
    ALERT_TYPES = [
        ('LICENCE_EXPIRY', 'Licence Expiry Alert'),
        ('OVERDUE_RETURN', 'Overdue Weapon Return Alert'),
        ('RECOVERY_REQUIRED', 'Weapon Recovery Required Alert'),
        ('DISCREPANCY', 'Weapon/Ammunition Discrepancy Alert'),
        ('MISSING_WEAPON', 'Missing Weapon Alert'),
        ('LOST_OR_STOLEN', 'Lost or Stolen Weapon Alert'),
        ('EXPENDITURE_DISCHARGE', 'Ammunition Expenditure / Discharge Alert'),
        ('EMERGENCY_RATIFICATION', 'Emergency Issue Ratification Pending'),
        ('MAINTENANCE_DUE', 'Weapon Maintenance Due Alert'),
    ]
    PRIORITY_CHOICES = [
        ('NORMAL', 'Normal'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    ]
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('ACKNOWLEDGED', 'Acknowledged'),
        ('RESOLVED', 'Resolved'),
    ]

    alert_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField()
    alert_type = models.CharField(max_length=40, choices=ALERT_TYPES)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES)
    related_entity_type = models.CharField(max_length=50)
    related_entity_id = models.UUIDField()
    recipient_role = models.CharField(max_length=30, null=True, blank=True)
    recipient_id = models.UUIDField(null=True, blank=True)
    site_id = models.UUIDField(null=True, blank=True)
    title = models.CharField(max_length=200)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    escalation_level = models.IntegerField(default=0)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.UUIDField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'security_erp"."weapon_alerts'
