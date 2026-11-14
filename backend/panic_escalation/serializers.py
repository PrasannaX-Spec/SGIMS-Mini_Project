from rest_framework import serializers
from panic_escalation.models import (
    PanicAlert,
    PanicTriggerContext,
    PanicPositionRecord,
    PanicEscalationConfig,
    PanicRecipient,
    PanicDeliveryAttempt,
    PanicAcknowledgement,
    PanicResponderAction,
    PanicFalseAlarmReport,
    PanicResolution,
    PanicEventTimeline,
    PanicTestDrill,
    PanicDeviceReadiness,
    PanicWelfareFollowup
)


class PanicTriggerContextSerializer(serializers.ModelSerializer):
    class Meta:
        model = PanicTriggerContext
        fields = '__all__'


class PanicPositionRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = PanicPositionRecord
        fields = '__all__'


class PanicDeliveryAttemptSerializer(serializers.ModelSerializer):
    recipient_name = serializers.SerializerMethodField()

    class Meta:
        model = PanicDeliveryAttempt
        fields = '__all__'

    def get_recipient_name(self, obj):
        if obj.recipient:
            if obj.recipient.user:
                return obj.recipient.user.full_name
            if obj.recipient.contact:
                return obj.recipient.contact.contact_name
        return 'Unknown'


class PanicAcknowledgementSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.full_name', read_only=True)

    class Meta:
        model = PanicAcknowledgement
        fields = '__all__'


class PanicRecipientSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    delivery_attempts = PanicDeliveryAttemptSerializer(many=True, read_only=True)

    class Meta:
        model = PanicRecipient
        fields = '__all__'

    def get_name(self, obj):
        if obj.user:
            return obj.user.full_name
        if obj.contact:
            return obj.contact.contact_name
        return 'System Contact'


class PanicResponderActionSerializer(serializers.ModelSerializer):
    responder_name = serializers.CharField(source='responder_user.full_name', read_only=True)

    class Meta:
        model = PanicResponderAction
        fields = '__all__'


class PanicFalseAlarmReportSerializer(serializers.ModelSerializer):
    guard_name = serializers.CharField(source='guard.full_name', read_only=True)
    supervisor_name = serializers.CharField(source='supervisor.full_name', read_only=True)

    class Meta:
        model = PanicFalseAlarmReport
        fields = '__all__'


class PanicResolutionSerializer(serializers.ModelSerializer):
    submitted_by_name = serializers.CharField(source='submitted_by.full_name', read_only=True)
    reviewed_by_name = serializers.CharField(source='reviewed_by.full_name', read_only=True)

    class Meta:
        model = PanicResolution
        fields = '__all__'


class PanicEventTimelineSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source='actor.full_name', read_only=True)

    class Meta:
        model = PanicEventTimeline
        fields = '__all__'


class PanicWelfareFollowupSerializer(serializers.ModelSerializer):
    recorded_by_name = serializers.CharField(source='recorded_by.full_name', read_only=True)

    class Meta:
        model = PanicWelfareFollowup
        fields = '__all__'


class PanicEscalationConfigSerializer(serializers.ModelSerializer):
    site_name = serializers.CharField(source='site.site_name', read_only=True)

    class Meta:
        model = PanicEscalationConfig
        fields = '__all__'


class PanicTestDrillSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)

    class Meta:
        model = PanicTestDrill
        fields = '__all__'


class PanicDeviceReadinessSerializer(serializers.ModelSerializer):
    guard_name = serializers.CharField(source='guard.full_name', read_only=True)
    guard_code = serializers.CharField(source='guard.employee_code', read_only=True)

    class Meta:
        model = PanicDeviceReadiness
        fields = '__all__'


class PanicAlertListSerializer(serializers.ModelSerializer):
    guard_name = serializers.CharField(source='guard.full_name', read_only=True)
    guard_code = serializers.CharField(source='guard.employee_code', read_only=True)
    site_name = serializers.CharField(source='site.site_name', read_only=True)
    site_code = serializers.CharField(source='site.site_code', read_only=True)
    latest_position = serializers.SerializerMethodField()
    battery_level = serializers.SerializerMethodField()
    network_type = serializers.SerializerMethodField()
    acknowledgement_count = serializers.SerializerMethodField()
    has_delivery_failure = serializers.SerializerMethodField()

    class Meta:
        model = PanicAlert
        fields = [
            'panic_alert_id', 'alert_number', 'client_generated_id', 'guard_id',
            'guard_name', 'guard_code', 'site_id', 'site_name', 'site_code',
            'trigger_server_time', 'trigger_device_time', 'alert_status', 'duty_status',
            'test_flag', 'current_escalation_stage', 'last_escalated_at',
            'first_acknowledged_at', 'resolved_at', 'closed_at',
            'latest_position', 'battery_level', 'network_type',
            'acknowledgement_count', 'has_delivery_failure', 'created_at', 'updated_at'
        ]

    def get_latest_position(self, obj):
        pos = obj.positions.filter(is_latest=True).first() or obj.positions.first()
        if pos:
            return {
                'latitude': float(pos.latitude) if pos.latitude else None,
                'longitude': float(pos.longitude) if pos.longitude else None,
                'accuracy': float(pos.accuracy) if pos.accuracy else None,
                'source': pos.source,
                'age_seconds': pos.position_age_seconds,
                'validity_status': pos.validity_status,
                'received_at': pos.received_at
            }
        return None

    def get_battery_level(self, obj):
        if hasattr(obj, 'context') and obj.context:
            return float(obj.context.battery_level) if obj.context.battery_level is not None else None
        return None

    def get_network_type(self, obj):
        if hasattr(obj, 'context') and obj.context:
            return obj.context.network_type
        return None

    def get_acknowledgement_count(self, obj):
        return obj.acknowledgements.count()

    def get_has_delivery_failure(self, obj):
        return obj.delivery_attempts.filter(delivery_status='FAILED').exists()


class PanicAlertDetailSerializer(serializers.ModelSerializer):
    guard_name = serializers.CharField(source='guard.full_name', read_only=True)
    guard_code = serializers.CharField(source='guard.employee_code', read_only=True)
    guard_phone = serializers.CharField(source='guard.phone', read_only=True)
    site_name = serializers.CharField(source='site.site_name', read_only=True)
    site_code = serializers.CharField(source='site.site_code', read_only=True)
    context = PanicTriggerContextSerializer(read_only=True)
    positions = PanicPositionRecordSerializer(many=True, read_only=True)
    recipients = PanicRecipientSerializer(many=True, read_only=True)
    delivery_attempts = PanicDeliveryAttemptSerializer(many=True, read_only=True)
    acknowledgements = PanicAcknowledgementSerializer(many=True, read_only=True)
    responder_actions = PanicResponderActionSerializer(many=True, read_only=True)
    false_alarm_reports = PanicFalseAlarmReportSerializer(many=True, read_only=True)
    resolution = PanicResolutionSerializer(read_only=True)
    timelines = PanicEventTimelineSerializer(many=True, read_only=True)
    welfare_followups = PanicWelfareFollowupSerializer(many=True, read_only=True)

    class Meta:
        model = PanicAlert
        fields = '__all__'


class ClientSafePanicStatusSerializer(serializers.ModelSerializer):
    """
    Module 10 & Client-safe interface (PRD Section 7.1, Section 14.2 C, AC-9.43, AC-9.44).
    STRICTLY excludes: exact coordinates, position trail, battery, device ID,
    guard phone number, internal notes, internal timeline, unapproved evidence.
    """
    site_name = serializers.CharField(source='site.site_name', read_only=True)
    guard_safe_card_name = serializers.SerializerMethodField()
    client_visible_status = serializers.SerializerMethodField()
    approved_summary = serializers.SerializerMethodField()
    client_acknowledged = serializers.SerializerMethodField()

    class Meta:
        model = PanicAlert
        fields = [
            'panic_alert_id', 'alert_number', 'site_id', 'site_name',
            'trigger_server_time', 'guard_safe_card_name', 'client_visible_status',
            'approved_summary', 'client_acknowledged'
        ]

    def get_guard_safe_card_name(self, obj):
        parts = [p for p in [obj.guard.first_name, obj.guard.last_name] if p]
        if parts:
            return f"Security Guard {parts[0][0]}. {parts[-1]}"
        return "Duty Security Officer"

    def get_client_visible_status(self, obj):
        if obj.alert_status in ('CLOSED', 'RESOLVED'):
            return 'RESOLVED'
        elif obj.alert_status in ('ACKNOWLEDGED', 'RESPONDING', 'GUARD_CONFIRMED_SAFE'):
            return 'ACKNOWLEDGED'
        return 'ACTIVE_EMERGENCY'

    def get_approved_summary(self, obj):
        if hasattr(obj, 'resolution') and obj.resolution and obj.resolution.admin_review_status == 'APPROVED':
            return obj.resolution.description
        return "Emergency incident is under active operational response and review."

    def get_client_acknowledged(self, obj):
        return obj.acknowledgements.filter(recipient__recipient_role='CLIENT').exists()
