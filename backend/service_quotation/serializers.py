import uuid
from decimal import Decimal
from rest_framework import serializers
from .models import (
    ServiceRequest,
    ServiceRequestLine,
    ServiceRequestAttachment,
    ServiceRequestComment,
    ServiceSiteSurvey,
    Quotation,
    QuotationVersion,
    QuotationLine,
    QuotationAcceptance,
    QuotationCounter,
    QuotationConversion,
)
from master_data.models import ClientSite, PostType, Client


class ServiceRequestLineSerializer(serializers.ModelSerializer):
    post_type_name = serializers.ReadOnlyField(source='post_type.name')
    post_type_code = serializers.ReadOnlyField(source='post_type.code')

    class Meta:
        model = ServiceRequestLine
        fields = [
            'request_line_id',
            'post_type',
            'post_type_name',
            'post_type_code',
            'guard_count',
            'shift_information',
            'hours_per_day',
            'working_days',
            'armed_required',
        ]


class ServiceRequestAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceRequestAttachment
        fields = [
            'attachment_id',
            'file_name',
            'file_type',
            'storage_key',
            'file_size',
            'uploaded_by_user_id',
            'uploaded_at',
        ]
        read_only_fields = ['attachment_id', 'uploaded_at']


class ServiceRequestCommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceRequestComment
        fields = [
            'comment_id',
            'sender_user_id',
            'sender_role',
            'message',
            'is_clarification_request',
            'created_at',
        ]
        read_only_fields = ['comment_id', 'sender_user_id', 'sender_role', 'created_at']


class ServiceSiteSurveySerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceSiteSurvey
        fields = [
            'survey_id',
            'survey_date',
            'visited_by',
            'assigned_supervisor_id',
            'findings',
            'notes',
            'created_at',
        ]
        read_only_fields = ['survey_id', 'created_at']


class ServiceRequestSerializer(serializers.ModelSerializer):
    lines = ServiceRequestLineSerializer(many=True, required=False)
    attachments = ServiceRequestAttachmentSerializer(many=True, read_only=True)
    comments = ServiceRequestCommentSerializer(many=True, read_only=True)
    surveys = ServiceSiteSurveySerializer(many=True, read_only=True)
    client_name = serializers.ReadOnlyField(source='client.company_name')
    existing_site_name = serializers.ReadOnlyField(source='existing_site.site_name')

    class Meta:
        model = ServiceRequest
        fields = [
            'request_id',
            'company',
            'client',
            'client_name',
            'request_reference',
            'submission_reference',
            'existing_site',
            'existing_site_name',
            'new_site_name',
            'new_site_address',
            'new_site_latitude',
            'new_site_longitude',
            'service_purpose',
            'start_date',
            'duration_type',
            'end_date',
            'site_contact_name',
            'site_contact_phone',
            'special_requirements',
            'status',
            'assigned_owner_id',
            'created_by_user_id',
            'created_at',
            'updated_at',
            'lines',
            'attachments',
            'comments',
            'surveys',
        ]
        read_only_fields = [
            'request_id',
            'request_reference',
            'status',
            'created_by_user_id',
            'created_at',
            'updated_at',
        ]


class QuotationLineSerializer(serializers.ModelSerializer):
    post_type_name = serializers.ReadOnlyField(source='post_type.name')
    post_type_code = serializers.ReadOnlyField(source='post_type.code')

    class Meta:
        model = QuotationLine
        fields = [
            'quotation_line_id',
            'quotation_version',
            'post_type',
            'post_type_name',
            'post_type_code',
            'shift_hours',
            'headcount',
            'billing_unit',
            'unit_rate',
            'line_total',
        ]
        read_only_fields = ['quotation_line_id']


class QuotationAcceptanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuotationAcceptance
        fields = [
            'acceptance_id',
            'client_user_id',
            'accepted_at',
            'ip_address',
            'device_information',
            'agreed_text',
            'confirmation_value',
        ]
        read_only_fields = fields


class QuotationCounterSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuotationCounter
        fields = [
            'counter_id',
            'client_user_id',
            'comment',
            'proposed_guard_count',
            'proposed_rate',
            'proposed_start_date',
            'negotiation_round',
            'created_at',
        ]
        read_only_fields = ['counter_id', 'client_user_id', 'negotiation_round', 'created_at']


class QuotationConversionSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuotationConversion
        fields = [
            'conversion_id',
            'conversion_reference',
            'conversion_status',
            'module2_site_id',
            'module2_agreement_id',
            'generated_records',
            'started_at',
            'completed_at',
            'error_details',
        ]
        read_only_fields = fields


class QuotationVersionSerializer(serializers.ModelSerializer):
    lines = QuotationLineSerializer(many=True, read_only=True)
    acceptances = QuotationAcceptanceSerializer(many=True, read_only=True)
    counters = QuotationCounterSerializer(many=True, read_only=True)
    conversions = QuotationConversionSerializer(many=True, read_only=True)

    class Meta:
        model = QuotationVersion
        fields = [
            'quotation_version_id',
            'quotation',
            'version_number',
            'quotation_date',
            'validity_date',
            'subtotal',
            'tax_note',
            'payment_terms',
            'additional_terms',
            'internal_notes',
            'pdf_path',
            'status',
            'created_by_user_id',
            'created_at',
            'sent_at',
            'lines',
            'acceptances',
            'counters',
            'conversions',
        ]
        read_only_fields = [
            'quotation_version_id',
            'version_number',
            'subtotal',
            'pdf_path',
            'status',
            'created_by_user_id',
            'created_at',
            'sent_at',
        ]

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            user_role = getattr(request.user, 'role', '').lower()
            if user_role not in ('admin', 'super_admin'):
                ret.pop('internal_notes', None)
        return ret


class QuotationSerializer(serializers.ModelSerializer):
    versions = QuotationVersionSerializer(many=True, read_only=True)
    client_name = serializers.ReadOnlyField(source='client.company_name')
    request_reference = serializers.ReadOnlyField(source='request.request_reference')

    class Meta:
        model = Quotation
        fields = [
            'quotation_id',
            'company',
            'client',
            'client_name',
            'request',
            'request_reference',
            'quotation_no',
            'version_no',
            'current_version',
            'issue_date',
            'valid_until',
            'currency',
            'subtotal',
            'tax_amount',
            'total_amount',
            'status',
            'created_by',
            'created_at',
            'versions',
        ]
        read_only_fields = [
            'quotation_id',
            'quotation_no',
            'version_no',
            'current_version',
            'subtotal',
            'tax_amount',
            'total_amount',
            'status',
            'created_by',
            'created_at',
        ]

