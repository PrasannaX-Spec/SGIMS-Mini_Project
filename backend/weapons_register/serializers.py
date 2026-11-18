from rest_framework import serializers
from datetime import date
from .models import (
    WeaponLocation, WeaponLicence, Weapon, WeaponLicenceAssociation,
    WeaponSerialRevealLog, WeaponTransfer, WeaponCustodyRecord,
    AmmunitionLot, AmmunitionLedger, AmmunitionStockCount,
    WeaponDiscrepancy, GuardWeaponBlock, WeaponRecovery,
    WeaponMaintenanceLog, WeaponAlert
)


class WeaponLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = WeaponLocation
        fields = '__all__'


class WeaponLicenceSerializer(serializers.ModelSerializer):
    days_until_expiry = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()

    class Meta:
        model = WeaponLicence
        fields = '__all__'

    def get_days_until_expiry(self, obj):
        if obj.valid_until:
            delta = (obj.valid_until - date.today()).days
            return delta
        return None

    def get_is_expired(self, obj):
        if obj.valid_until:
            return obj.valid_until < date.today()
        return False


class WeaponSerializer(serializers.ModelSerializer):
    display_serial = serializers.SerializerMethodField()
    licence_details = serializers.SerializerMethodField()
    location_name = serializers.SerializerMethodField()
    custody_details = serializers.SerializerMethodField()

    class Meta:
        model = Weapon
        fields = [
            'weapon_id', 'company_id', 'asset_id', 'weapon_type', 'make',
            'model', 'calibre', 'serial_number', 'display_serial',
            'manufacture_year', 'acquisition_date', 'supplier', 'status',
            'current_location_id', 'location_name', 'current_custody_id',
            'custody_details', 'photo_url', 'qr_relabel_count',
            'qr_last_relabeled_at', 'status_reason', 'status_updated_at',
            'is_active', 'created_by', 'created_at', 'updated_at',
            'licence_details'
        ]

    def get_display_serial(self, obj):
        req = self.context.get('request')
        if req and req.user:
            # Full serial number is visible only to ADMIN / SUPER_ADMIN
            if req.user.role in ['ADMIN', 'SUPER_ADMIN']:
                return obj.serial_number
            # Check if Supervisor has an active reveal log for this session/day
            if req.user.role == 'SUPERVISOR':
                has_revealed = WeaponSerialRevealLog.objects.filter(
                    weapon_id=obj.weapon_id,
                    revealed_by=req.user.user_id,
                    revealed_at__date=date.today()
                ).exists()
                if has_revealed:
                    return obj.serial_number
        return obj.masked_serial_number()

    def get_licence_details(self, obj):
        current_assoc = WeaponLicenceAssociation.objects.filter(
            weapon_id=obj.weapon_id, is_current=True
        ).first()
        if current_assoc:
            licence = WeaponLicence.objects.filter(licence_id=current_assoc.licence_id).first()
            if licence:
                return {
                    'licence_id': str(licence.licence_id),
                    'licence_number': licence.licence_number,
                    'valid_until': str(licence.valid_until),
                    'is_expired': licence.valid_until < date.today(),
                    'holder_name': licence.holder_name or 'Agency'
                }
        return None

    def get_location_name(self, obj):
        if obj.current_location_id:
            loc = WeaponLocation.objects.filter(location_id=obj.current_location_id).first()
            if loc:
                return loc.name
        return None

    def get_custody_details(self, obj):
        custody = WeaponCustodyRecord.objects.filter(
            weapon_id=obj.weapon_id, is_current=True
        ).first()
        if custody:
            return {
                'custodian_type': custody.custodian_type,
                'custodian_id': str(custody.custodian_id),
                'ammunition_rounds': custody.ammunition_rounds,
                'start_time': custody.start_time.isoformat() if custody.start_time else None
            }
        return None


class WeaponCreateSerializer(serializers.ModelSerializer):
    serial_number_confirm = serializers.CharField(write_only=True)
    licence_id = serializers.UUIDField(required=False, write_only=True)

    class Meta:
        model = Weapon
        fields = [
            'weapon_type', 'make', 'model', 'calibre', 'serial_number',
            'serial_number_confirm', 'manufacture_year', 'acquisition_date',
            'supplier', 'status', 'current_location_id', 'photo_url', 'licence_id'
        ]

    def validate(self, attrs):
        s1 = attrs.get('serial_number')
        s2 = attrs.get('serial_number_confirm')
        if s1 != s2:
            raise serializers.ValidationError({"serial_number_confirm": "Serial number entries do not match."})

        company_id = self.context.get('company_id')
        if company_id and Weapon.objects.filter(company_id=company_id, serial_number=s1).exists():
            raise serializers.ValidationError({"serial_number": "A weapon with this serial number already exists in your company."})

        return attrs


class WeaponTransferSerializer(serializers.ModelSerializer):
    weapon_asset_id = serializers.SerializerMethodField()
    weapon_type = serializers.SerializerMethodField()

    class Meta:
        model = WeaponTransfer
        fields = '__all__'

    def get_weapon_asset_id(self, obj):
        w = Weapon.objects.filter(weapon_id=obj.weapon_id).first()
        return w.asset_id if w else None

    def get_weapon_type(self, obj):
        w = Weapon.objects.filter(weapon_id=obj.weapon_id).first()
        return w.weapon_type if w else None


class WeaponCustodyRecordSerializer(serializers.ModelSerializer):
    weapon_asset_id = serializers.SerializerMethodField()
    weapon_type = serializers.SerializerMethodField()
    masked_serial = serializers.SerializerMethodField()

    class Meta:
        model = WeaponCustodyRecord
        fields = '__all__'

    def get_weapon_asset_id(self, obj):
        w = Weapon.objects.filter(weapon_id=obj.weapon_id).first()
        return w.asset_id if w else None

    def get_weapon_type(self, obj):
        w = Weapon.objects.filter(weapon_id=obj.weapon_id).first()
        return w.weapon_type if w else None

    def get_masked_serial(self, obj):
        w = Weapon.objects.filter(weapon_id=obj.weapon_id).first()
        return w.masked_serial_number() if w else None


class AmmunitionLotSerializer(serializers.ModelSerializer):
    current_stock = serializers.SerializerMethodField()

    class Meta:
        model = AmmunitionLot
        fields = '__all__'

    def get_current_stock(self, obj):
        # Derive stock from immutable ledger: Received + Returned + Adjusted - Issued - Expended - Disposed
        from django.db.models import Sum
        pos = AmmunitionLedger.objects.filter(
            lot_id=obj.lot_id,
            entry_type__in=['RECEIVED', 'RETURNED', 'ADJUSTED']
        ).aggregate(total=Sum('quantity'))['total'] or 0

        neg = AmmunitionLedger.objects.filter(
            lot_id=obj.lot_id,
            entry_type__in=['ISSUED', 'EXPENDED', 'DISPOSED']
        ).aggregate(total=Sum('quantity'))['total'] or 0

        return max(0, pos - neg)


class AmmunitionLedgerSerializer(serializers.ModelSerializer):
    class Meta:
        model = AmmunitionLedger
        fields = '__all__'


class AmmunitionStockCountSerializer(serializers.ModelSerializer):
    class Meta:
        model = AmmunitionStockCount
        fields = '__all__'


class WeaponDiscrepancySerializer(serializers.ModelSerializer):
    weapon_asset_id = serializers.SerializerMethodField()

    class Meta:
        model = WeaponDiscrepancy
        fields = '__all__'

    def get_weapon_asset_id(self, obj):
        if obj.weapon_id:
            w = Weapon.objects.filter(weapon_id=obj.weapon_id).first()
            return w.asset_id if w else None
        return None


class GuardWeaponBlockSerializer(serializers.ModelSerializer):
    class Meta:
        model = GuardWeaponBlock
        fields = '__all__'


class WeaponRecoverySerializer(serializers.ModelSerializer):
    weapon_asset_id = serializers.SerializerMethodField()

    class Meta:
        model = WeaponRecovery
        fields = '__all__'

    def get_weapon_asset_id(self, obj):
        w = Weapon.objects.filter(weapon_id=obj.weapon_id).first()
        return w.asset_id if w else None


class WeaponMaintenanceLogSerializer(serializers.ModelSerializer):
    weapon_asset_id = serializers.SerializerMethodField()

    class Meta:
        model = WeaponMaintenanceLog
        fields = '__all__'

    def get_weapon_asset_id(self, obj):
        w = Weapon.objects.filter(weapon_id=obj.weapon_id).first()
        return w.asset_id if w else None


class WeaponAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = WeaponAlert
        fields = '__all__'
