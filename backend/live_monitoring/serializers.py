from rest_framework import serializers
from live_monitoring.models import (
    MonitoringDuty,
    LocationPoint,
    Heartbeat,
    GuardMonitoringStatus,
    MonitoringStatusHistory,
    AlertRule,
    MonitoringAlert,
    SupervisorPing,
    TrackingConfiguration
)


class LocationPointSerializer(serializers.ModelSerializer):
    class Meta:
        model = LocationPoint
        fields = '__all__'


class HeartbeatSerializer(serializers.ModelSerializer):
    class Meta:
        model = Heartbeat
        fields = '__all__'


class GuardMonitoringStatusSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_code = serializers.CharField(source='employee.employee_code', read_only=True)
    site_name = serializers.CharField(source='site.site_name', read_only=True)
    site_code = serializers.CharField(source='site.site_code', read_only=True)
    site_latitude = serializers.DecimalField(source='site.latitude', max_digits=10, decimal_places=7, read_only=True)
    site_longitude = serializers.DecimalField(source='site.longitude', max_digits=10, decimal_places=7, read_only=True)
    geofence_radius = serializers.SerializerMethodField()
    shift_name = serializers.CharField(source='duty.shift.shift_name', read_only=True)
    duty_start_at = serializers.DateTimeField(source='duty.duty_start_at', read_only=True)

    # Last position telemetry
    latitude = serializers.DecimalField(source='last_location_point.latitude', max_digits=10, decimal_places=7, read_only=True)
    longitude = serializers.DecimalField(source='last_location_point.longitude', max_digits=10, decimal_places=7, read_only=True)
    accuracy_m = serializers.DecimalField(source='last_location_point.accuracy_m', max_digits=8, decimal_places=2, read_only=True)
    last_captured_at = serializers.DateTimeField(source='last_location_point.device_captured_at', read_only=True)
    mock_location = serializers.BooleanField(source='last_location_point.mock_location', read_only=True)

    # Device health from heartbeat or location
    battery_percent = serializers.SerializerMethodField()
    network_type = serializers.SerializerMethodField()
    charging_state = serializers.SerializerMethodField()

    class Meta:
        model = GuardMonitoringStatus
        fields = [
            'status_id', 'duty_id', 'employee_id', 'employee_name', 'employee_code',
            'assignment_id', 'site_id', 'site_name', 'site_code', 'site_latitude', 'site_longitude',
            'geofence_radius', 'shift_name', 'duty_start_at', 'primary_status', 'has_active_alert',
            'display_status', 'consecutive_outside_count', 'latitude', 'longitude', 'accuracy_m',
            'last_captured_at', 'mock_location', 'battery_percent', 'network_type', 'charging_state',
            'last_communication_at', 'status_calculated_at'
        ]

    def get_geofence_radius(self, obj):
        if hasattr(obj.site, 'geofence') and obj.site.geofence and obj.site.geofence.radius_meters:
            return float(obj.site.geofence.radius_meters)
        return 100.0

    def get_battery_percent(self, obj):
        if obj.last_location_point and obj.last_location_point.battery_percent is not None:
            return obj.last_location_point.battery_percent
        if obj.last_heartbeat and obj.last_heartbeat.battery_percent is not None:
            return obj.last_heartbeat.battery_percent
        return None

    def get_network_type(self, obj):
        if obj.last_location_point and obj.last_location_point.network_type:
            return obj.last_location_point.network_type
        if obj.last_heartbeat and obj.last_heartbeat.network_type:
            return obj.last_heartbeat.network_type
        return None

    def get_charging_state(self, obj):
        if obj.last_location_point and obj.last_location_point.charging_state:
            return obj.last_location_point.charging_state
        if obj.last_heartbeat and obj.last_heartbeat.charging_state:
            return obj.last_heartbeat.charging_state
        return None


class MonitoringAlertSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_code = serializers.CharField(source='employee.employee_code', read_only=True)
    site_name = serializers.CharField(source='site.site_name', read_only=True)
    acknowledged_by_name = serializers.CharField(source='acknowledged_by.full_name', read_only=True)
    resolved_by_name = serializers.CharField(source='resolved_by.full_name', read_only=True)

    class Meta:
        model = MonitoringAlert
        fields = '__all__'


class SupervisorPingSerializer(serializers.ModelSerializer):
    supervisor_name = serializers.CharField(source='supervisor.full_name', read_only=True)
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)

    class Meta:
        model = SupervisorPing
        fields = '__all__'


class AlertRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = AlertRule
        fields = '__all__'


class TrackingConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrackingConfiguration
        fields = '__all__'


class MonitoringStatusHistorySerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)

    class Meta:
        model = MonitoringStatusHistory
        fields = '__all__'
