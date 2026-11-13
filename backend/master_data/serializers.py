from rest_framework import serializers
from master_data.models import (
    Company, Client, ClientContact, ClientSite, SiteGeofence,
    SiteSupervisorAssignment, PostType, ShiftTemplate, SiteShift,
    SiteManpowerRequirement, ServiceAgreement, ClientBillingRate
)


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = '__all__'


class ClientContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientContact
        fields = '__all__'


class ClientSerializer(serializers.ModelSerializer):
    contacts = ClientContactSerializer(many=True, read_only=True)
    sites_count = serializers.SerializerMethodField()

    class Meta:
        model = Client
        fields = '__all__'

    def get_sites_count(self, obj):
        return obj.sites.count()


class SiteGeofenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteGeofence
        fields = '__all__'


class SiteSupervisorAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteSupervisorAssignment
        fields = '__all__'


class SiteShiftSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteShift
        fields = '__all__'


class SiteManpowerRequirementSerializer(serializers.ModelSerializer):
    shift_name = serializers.CharField(source='shift.shift_name', read_only=True)
    post_type_name = serializers.CharField(source='post_type.name', read_only=True)

    class Meta:
        model = SiteManpowerRequirement
        fields = '__all__'


class ClientSiteSerializer(serializers.ModelSerializer):
    active_geofence = serializers.SerializerMethodField()
    primary_supervisor = serializers.SerializerMethodField()
    client_name = serializers.CharField(source='client.legal_name', read_only=True)

    class Meta:
        model = ClientSite
        fields = '__all__'

    def get_active_geofence(self, obj):
        gf = obj.geofences.filter(is_active=True).order_by('-version').first()
        if gf:
            return SiteGeofenceSerializer(gf).data
        return None

    def get_primary_supervisor(self, obj):
        sup = obj.supervisor_assignments.filter(role_type='primary', is_active=True).first()
        if sup:
            return SiteSupervisorAssignmentSerializer(sup).data
        return None


class PostTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostType
        fields = '__all__'


class ShiftTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShiftTemplate
        fields = '__all__'


class ServiceAgreementSerializer(serializers.ModelSerializer):
    client_code = serializers.CharField(source='client.client_code', read_only=True)
    site_code = serializers.CharField(source='site.site_code', read_only=True, allow_null=True)

    class Meta:
        model = ServiceAgreement
        fields = '__all__'


class ClientBillingRateSerializer(serializers.ModelSerializer):
    post_type_name = serializers.CharField(source='post_type.name', read_only=True)
    client_code = serializers.CharField(source='client.client_code', read_only=True)
    site_code = serializers.CharField(source='site.site_code', read_only=True, allow_null=True)

    class Meta:
        model = ClientBillingRate
        fields = '__all__'

