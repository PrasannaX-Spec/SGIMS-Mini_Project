from rest_framework import serializers
from incident_management.models import (
    IncidentCategory,
    GuardRequestType,
    ResolutionOutcome,
    Incident,
    IncidentContext,
    IncidentDetail,
    IncidentAttachment,
    IncidentAddendum,
    IncidentTimeline,
    IncidentFollowUpTask,
    IncidentClientVersion,
    GuardRequest,
    GuardRequestReply,
    ClientTicket,
    ClientTicketMessage,
)


class IncidentCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = IncidentCategory
        fields = '__all__'


class GuardRequestTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = GuardRequestType
        fields = '__all__'


class ResolutionOutcomeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResolutionOutcome
        fields = '__all__'


class IncidentAttachmentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.full_name', read_only=True)

    class Meta:
        model = IncidentAttachment
        fields = '__all__'


class IncidentContextSerializer(serializers.ModelSerializer):
    site_name = serializers.CharField(source='site.site_name', read_only=True)
    guard_name = serializers.CharField(source='guard.full_name', read_only=True)
    supervisor_name = serializers.CharField(source='supervisor.full_name', read_only=True)

    class Meta:
        model = IncidentContext
        fields = '__all__'


class IncidentDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = IncidentDetail
        fields = '__all__'


class IncidentAddendumSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.full_name', read_only=True)

    class Meta:
        model = IncidentAddendum
        fields = '__all__'


class IncidentTimelineSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source='actor.full_name', read_only=True)

    class Meta:
        model = IncidentTimeline
        fields = '__all__'


class IncidentFollowUpTaskSerializer(serializers.ModelSerializer):
    assigned_to_name = serializers.CharField(source='assigned_to.full_name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)

    class Meta:
        model = IncidentFollowUpTask
        fields = '__all__'


class IncidentClientVersionSerializer(serializers.ModelSerializer):
    approved_by_name = serializers.CharField(source='approved_by.full_name', read_only=True)

    class Meta:
        model = IncidentClientVersion
        fields = '__all__'


class IncidentListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='current_category.name', read_only=True)
    site_name = serializers.CharField(source='site.site_name', read_only=True)
    guard_name = serializers.CharField(source='guard.full_name', read_only=True)
    supervisor_name = serializers.CharField(source='supervisor.full_name', read_only=True)
    attachment_count = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = Incident
        fields = [
            'incident_id',
            'case_number',
            'client_generated_id',
            'site_id',
            'site_name',
            'guard_id',
            'guard_name',
            'supervisor_id',
            'supervisor_name',
            'current_category_id',
            'category_name',
            'current_severity',
            'original_severity',
            'status',
            'verification_state',
            'is_sensitive',
            'occurred_at',
            'submitted_at',
            'created_at',
            'attachment_count',
            'is_overdue',
        ]

    def get_attachment_count(self, obj):
        return obj.attachments.count()

    def get_is_overdue(self, obj):
        # High/Critical unacknowledged > 30m / 15m or open past target
        from django.utils import timezone
        from datetime import timedelta
        if obj.status == 'REPORTED':
            limit_minutes = 15 if obj.current_severity == 'CRITICAL' else (30 if obj.current_severity == 'HIGH' else 120)
            return timezone.now() > (obj.submitted_at + timedelta(minutes=limit_minutes))
        return False


class IncidentDetailResponseSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='current_category.name', read_only=True)
    original_category_name = serializers.CharField(source='original_category.name', read_only=True)
    site_name = serializers.CharField(source='site.site_name', read_only=True)
    client_name = serializers.CharField(source='site.client.name', read_only=True)
    guard_name = serializers.CharField(source='guard.full_name', read_only=True)
    guard_code = serializers.CharField(source='guard.employee_code', read_only=True)
    supervisor_name = serializers.CharField(source='supervisor.full_name', read_only=True)
    context = IncidentContextSerializer(read_only=True)
    details = IncidentDetailSerializer(read_only=True)
    attachments = IncidentAttachmentSerializer(many=True, read_only=True)
    addendums = IncidentAddendumSerializer(many=True, read_only=True)
    timeline = IncidentTimelineSerializer(many=True, read_only=True)
    follow_up_tasks = IncidentFollowUpTaskSerializer(many=True, read_only=True)
    latest_client_version = serializers.SerializerMethodField()

    class Meta:
        model = Incident
        fields = '__all__'

    def get_latest_client_version(self, obj):
        v = obj.client_versions.order_by('-created_at').first()
        if v:
            return IncidentClientVersionSerializer(v).data
        return None


class GuardRequestReplySerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source='actor.full_name', read_only=True)

    class Meta:
        model = GuardRequestReply
        fields = '__all__'


class GuardRequestSerializer(serializers.ModelSerializer):
    request_type_name = serializers.CharField(source='request_type.name', read_only=True)
    guard_name = serializers.CharField(source='guard.full_name', read_only=True)
    site_name = serializers.CharField(source='site.site_name', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.full_name', read_only=True)
    replies = GuardRequestReplySerializer(many=True, read_only=True)

    class Meta:
        model = GuardRequest
        fields = '__all__'


class ClientTicketMessageSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source='actor.full_name', read_only=True)

    class Meta:
        model = ClientTicketMessage
        fields = '__all__'


class ClientTicketSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.name', read_only=True)
    site_name = serializers.CharField(source='site.site_name', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.full_name', read_only=True)
    named_guard_name = serializers.CharField(source='named_guard.full_name', read_only=True)
    messages = serializers.SerializerMethodField()

    class Meta:
        model = ClientTicket
        fields = '__all__'

    def get_messages(self, obj):
        # Filter internal messages if requested by client
        request = self.context.get('request')
        is_client = request and hasattr(request.user, 'role') and request.user.role == 'CLIENT'
        qs = obj.messages.all().order_by('created_at')
        if is_client:
            qs = qs.filter(visibility='CLIENT_VISIBLE')
        return ClientTicketMessageSerializer(qs, many=True).data
