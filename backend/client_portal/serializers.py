from rest_framework import serializers
from client_portal.models import (
    ClientUserSiteAccess,
    ClientPortalConfiguration,
    ClientNotificationPreference,
    ClientDocumentAccessLog,
    ClientPortalUsageEvent,
    ClientAnnouncement
)
from master_data.models import ClientSite, Client
from foundation.models import User


class ClientUserSiteAccessSerializer(serializers.ModelSerializer):
    site_name = serializers.CharField(source='site.site_name', read_only=True)
    user_email = serializers.CharField(source='client_user.email', read_only=True)
    user_name = serializers.CharField(source='client_user.full_name', read_only=True)

    class Meta:
        model = ClientUserSiteAccess
        fields = [
            'access_id',
            'company_id',
            'client_user_id',
            'user_name',
            'user_email',
            'access_mode',
            'site_id',
            'site_name',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['access_id', 'created_at', 'updated_at']


class ClientPortalConfigurationSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.client_name', read_only=True)

    class Meta:
        model = ClientPortalConfiguration
        fields = [
            'configuration_id',
            'company_id',
            'client_id',
            'client_name',
            'future_roster_visibility',
            'incident_sharing_default',
            'retention_window_days',
            'checkin_photo_visibility',
            'invoices_enabled',
            'requests_enabled',
            'documents_enabled',
            'announcements_enabled',
            'enabled_sections',
            'updated_at',
        ]
        read_only_fields = ['configuration_id', 'updated_at']


class ClientNotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientNotificationPreference
        fields = [
            'preference_id',
            'notification_category',
            'enabled',
            'quiet_hours_start',
            'quiet_hours_end',
            'frequency_limit',
            'updated_at',
        ]
        read_only_fields = ['preference_id', 'updated_at']

    def validate(self, attrs):
        category = attrs.get('notification_category')
        enabled = attrs.get('enabled')
        if category == 'PANIC' and enabled is False:
            raise serializers.ValidationError("Emergency panic alerts cannot be disabled.")
        return attrs


class ClientDocumentAccessLogSerializer(serializers.ModelSerializer):
    site_name = serializers.CharField(source='site.site_name', read_only=True, default=None)
    user_name = serializers.CharField(source='client_user.full_name', read_only=True)

    class Meta:
        model = ClientDocumentAccessLog
        fields = [
            'download_log_id',
            'company_id',
            'client_user_id',
            'user_name',
            'document_id',
            'source_module',
            'site_id',
            'site_name',
            'requested_at',
            'result',
            'file_type',
            'access_reference',
        ]
        read_only_fields = ['download_log_id', 'requested_at']


class ClientPortalUsageEventSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='client_user.full_name', read_only=True, default='Anonymous')

    class Meta:
        model = ClientPortalUsageEvent
        fields = [
            'usage_event_id',
            'company_id',
            'client_user_id',
            'user_name',
            'event_type',
            'related_record_id',
            'occurred_at',
            'source',
        ]
        read_only_fields = ['usage_event_id', 'occurred_at']


class ClientAnnouncementSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='target_client.client_name', read_only=True, default='All Clients')

    class Meta:
        model = ClientAnnouncement
        fields = [
            'announcement_id',
            'company_id',
            'target_client_id',
            'client_name',
            'title',
            'message',
            'starts_at',
            'ends_at',
            'status',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['announcement_id', 'created_at', 'updated_at']


# Client-Safe DTO Serializers (Strictly Sanitized - Zero coordinates, phone numbers, or internal flags)
class ClientSafeGuardCardSerializer(serializers.Serializer):
    guard_id = serializers.UUIDField()
    name = serializers.CharField()
    photo_url = serializers.CharField(allow_null=True)
    employee_code = serializers.CharField()
    post = serializers.CharField(allow_null=True)
    shift_timing = serializers.CharField(allow_null=True)
    status_word = serializers.CharField()
    last_updated_time = serializers.DateTimeField(allow_null=True)
    is_replacement = serializers.BooleanField(default=False)
    replacement_time = serializers.DateTimeField(allow_null=True)


class ClientSafeDeploymentSerializer(serializers.Serializer):
    site_id = serializers.UUIDField()
    site_name = serializers.CharField()
    current_date = serializers.DateField()
    current_shift_name = serializers.CharField(allow_null=True)
    required_guards = serializers.IntegerField(default=0)
    assigned_guards = serializers.IntegerField(default=0)
    confirmed_on_duty = serializers.IntegerField(default=0)
    shortfall = serializers.IntegerField(default=0)
    shortfall_status = serializers.CharField()
    current_shift_guards = ClientSafeGuardCardSerializer(many=True)
    next_shift_guards = ClientSafeGuardCardSerializer(many=True)
    last_updated_at = serializers.DateTimeField()


class ClientAttendanceQueryCreateSerializer(serializers.Serializer):
    attendance_record_id = serializers.UUIDField()
    site_id = serializers.UUIDField()
    reason = serializers.CharField(max_length=1000)
    attachment_ref = serializers.CharField(max_length=255, required=False, allow_null=True)


class ClientPostIssueCreateSerializer(serializers.Serializer):
    site_id = serializers.UUIDField()
    shift_id = serializers.UUIDField(required=False, allow_null=True)
    category = serializers.CharField(max_length=50, default='POST_DISPUTE')
    description = serializers.CharField(max_length=2000)
    named_guard_id = serializers.UUIDField(required=False, allow_null=True)
    attachment_ref = serializers.CharField(max_length=255, required=False, allow_null=True)
