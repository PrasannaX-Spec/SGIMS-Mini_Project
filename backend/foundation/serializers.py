import pytz
from rest_framework import serializers
from foundation.models import (
    User, Company, ScopeGrant, UserSession, BoundDevice,
    DeviceChangeRequest, LoginAttempt, Notification, NotificationDelivery,
    NotificationPreference, AuditEvent, ConsentRecord, SystemSetting
)

IST = pytz.timezone('Asia/Kolkata')


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ['company_id', 'legal_name', 'trade_name', 'time_zone', 'is_active']


class UserListSerializer(serializers.ModelSerializer):
    has_warning = serializers.SerializerMethodField()
    last_login_ist = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'user_id', 'full_name', 'role', 'email', 'phone',
            'status', 'must_change_password', 'failed_attempts',
            'locked_until', 'last_login_at', 'last_login_ist',
            'guard_profile_id', 'client_company_id', 'has_warning',
            'created_at', 'version'
        ]

    def get_has_warning(self, obj):
        # Warning flag: guard or client missing linked profile/company (FR-1.40, FR-1.48)
        if obj.role == 'GUARD' and not obj.guard_profile_id:
            return True
        if obj.role == 'CLIENT' and not obj.client_company_id:
            return True
        return False

    def get_last_login_ist(self, obj):
        if obj.last_login_at:
            return obj.last_login_at.astimezone(IST).strftime('%d/%m/%Y %H:%M')
        return None


class UserDetailSerializer(serializers.ModelSerializer):
    last_login_ist = serializers.SerializerMethodField()
    bound_device = serializers.SerializerMethodField()
    notification_preferences = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'user_id', 'company_id', 'full_name', 'role', 'email', 'phone',
            'contact_phone', 'status', 'must_change_password',
            'failed_attempts', 'locked_until', 'last_login_at', 'last_login_ist',
            'guard_profile_id', 'client_company_id', 'bound_device',
            'notification_preferences', 'deactivated_at', 'deactivation_reason',
            'created_at', 'updated_at', 'version'
        ]

    def get_last_login_ist(self, obj):
        if obj.last_login_at:
            return obj.last_login_at.astimezone(IST).strftime('%d/%m/%Y %H:%M')
        return None

    def get_bound_device(self, obj):
        if obj.role == 'GUARD':
            device = BoundDevice.objects.filter(user=obj, unbound_at__isnull=True).first()
            if device:
                return {
                    'device_id': device.device_id,
                    'model': device.model,
                    'os_version': device.os_version,
                    'app_version': device.app_version,
                    'bound_at': device.bound_at.astimezone(IST).strftime('%d/%m/%Y %H:%M')
                }
        return None

    def get_notification_preferences(self, obj):
        pref = NotificationPreference.objects.filter(user=obj).first()
        if pref:
            return {
                'push_normal': pref.push_normal,
                'browser_notifications': pref.browser_notifications
            }
        return {'push_normal': True, 'browser_notifications': False}


class ScopeGrantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScopeGrant
        fields = ['grant_id', 'scope_type', 'target_id', 'effective_from', 'effective_to', 'created_at']


class LoginAttemptSerializer(serializers.ModelSerializer):
    attempted_at_ist = serializers.SerializerMethodField()

    class Meta:
        model = LoginAttempt
        fields = [
            'attempt_id', 'identifier_entered', 'result', 'platform',
            'ip_address', 'device_model', 'app_version', 'attempted_at', 'attempted_at_ist'
        ]

    def get_attempted_at_ist(self, obj):
        return obj.attempted_at.astimezone(IST).strftime('%d/%m/%Y %H:%M:%S')


class DeviceChangeRequestSerializer(serializers.ModelSerializer):
    guard_name = serializers.CharField(source='user.full_name', read_only=True)
    guard_phone = serializers.CharField(source='user.phone', read_only=True)
    requested_at_ist = serializers.SerializerMethodField()
    last_attempt_at_ist = serializers.SerializerMethodField()

    class Meta:
        model = DeviceChangeRequest
        fields = [
            'request_id', 'user_id', 'guard_name', 'guard_phone',
            'new_device_id', 'new_model', 'new_os_version', 'new_app_version',
            'status', 'requested_at', 'requested_at_ist',
            'last_attempt_at', 'last_attempt_at_ist',
            'decided_by', 'decided_at', 'decision_note'
        ]

    def get_requested_at_ist(self, obj):
        return obj.requested_at.astimezone(IST).strftime('%d/%m/%Y %H:%M')

    def get_last_attempt_at_ist(self, obj):
        return obj.last_attempt_at.astimezone(IST).strftime('%d/%m/%Y %H:%M')


class NotificationSerializer(serializers.ModelSerializer):
    created_at_ist = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            'notification_id', 'type_code', 'subject', 'message',
            'related_record_type', 'related_record_id', 'read_at',
            'created_at', 'created_at_ist'
        ]

    def get_created_at_ist(self, obj):
        return obj.created_at.astimezone(IST).strftime('%d/%m/%Y %H:%M')


class NotificationDeliverySerializer(serializers.ModelSerializer):
    recipient_name = serializers.CharField(source='notification.user.full_name', read_only=True)
    type_code = serializers.CharField(source='notification.type_code', read_only=True)
    last_attempt_ist = serializers.SerializerMethodField()

    class Meta:
        model = NotificationDelivery
        fields = [
            'delivery_id', 'type_code', 'recipient_name', 'channel',
            'status', 'attempts', 'last_attempt_at', 'last_attempt_ist', 'failure_reason'
        ]

    def get_last_attempt_ist(self, obj):
        if obj.last_attempt_at:
            return obj.last_attempt_at.astimezone(IST).strftime('%d/%m/%Y %H:%M')
        return None


class AuditEventSerializer(serializers.ModelSerializer):
    occurred_at_ist = serializers.SerializerMethodField()
    occurred_at_utc = serializers.SerializerMethodField()

    class Meta:
        model = AuditEvent
        fields = [
            'id', 'occurred_at_utc', 'occurred_at_ist', 'actor_role', 'actor_name',
            'action_code', 'module', 'record_type', 'record_id',
            'result', 'old_values', 'new_values', 'reason',
            'ip_address', 'device_id', 'user_agent'
        ]

    def get_occurred_at_ist(self, obj):
        return obj.occurred_at.astimezone(IST).strftime('%d/%m/%Y %H:%M:%S')

    def get_occurred_at_utc(self, obj):
        return obj.occurred_at.strftime('%Y-%m-%d %H:%M:%S UTC')


class ConsentRecordSerializer(serializers.ModelSerializer):
    recorded_at_ist = serializers.SerializerMethodField()

    class Meta:
        model = ConsentRecord
        fields = ['consent_id', 'item', 'decision', 'policy_version', 'recorded_at', 'recorded_at_ist']

    def get_recorded_at_ist(self, obj):
        return obj.recorded_at.astimezone(IST).strftime('%d/%m/%Y %H:%M')

