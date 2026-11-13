from rest_framework import serializers
from attendance.models import (
    AttendancePeriod,
    AttendanceRecord,
    AttendanceCapture,
    AttendanceEvidence,
    AttendanceFlag,
    AttendanceRevision,
    AttendanceRegularisation,
    AttendanceApproval,
    AttendancePeriodException,
    AttendanceHandover,
    ManualAttendanceCounter,
)


class AttendanceFlagSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceFlag
        fields = '__all__'


class AttendanceEvidenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceEvidence
        fields = '__all__'


class AttendanceCaptureSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceCapture
        fields = '__all__'


class AttendanceRevisionSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source='actor.full_name', read_only=True)

    class Meta:
        model = AttendanceRevision
        fields = '__all__'


class AttendanceRecordListSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_code = serializers.CharField(source='employee.employee_code', read_only=True)
    site_name = serializers.CharField(source='site.site_name', read_only=True)
    shift_name = serializers.CharField(source='shift.shift_name', read_only=True)
    flags_count = serializers.SerializerMethodField()

    class Meta:
        model = AttendanceRecord
        fields = [
            'attendance_id', 'assignment_id', 'employee_id', 'employee_name', 'employee_code',
            'site_id', 'site_name', 'shift_id', 'shift_name', 'duty_date',
            'scheduled_start', 'scheduled_end', 'actual_check_in', 'actual_check_out',
            'late_minutes', 'early_exit_minutes', 'worked_minutes', 'regular_minutes', 'overtime_minutes',
            'status', 'is_manual', 'is_offline', 'is_unscheduled', 'flags_count', 'created_at'
        ]

    def get_flags_count(self, obj):
        return obj.flags.count()


class AttendanceRecordDetailSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_code = serializers.CharField(source='employee.employee_code', read_only=True)
    site_name = serializers.CharField(source='site.site_name', read_only=True)
    shift_name = serializers.CharField(source='shift.shift_name', read_only=True)
    flags = AttendanceFlagSerializer(many=True, read_only=True)
    captures = AttendanceCaptureSerializer(many=True, read_only=True)
    evidence = AttendanceEvidenceSerializer(many=True, read_only=True)
    revisions = AttendanceRevisionSerializer(many=True, read_only=True)

    class Meta:
        model = AttendanceRecord
        fields = '__all__'


class AttendancePeriodSerializer(serializers.ModelSerializer):
    closed_by_name = serializers.CharField(source='closed_by.full_name', read_only=True)

    class Meta:
        model = AttendancePeriod
        fields = '__all__'


class AttendanceRegularisationSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_code = serializers.CharField(source='employee.employee_code', read_only=True)
    site_name = serializers.CharField(source='site.site_name', read_only=True)
    shift_name = serializers.CharField(source='shift.shift_name', read_only=True)

    class Meta:
        model = AttendanceRegularisation
        fields = '__all__'


class ClientSafeAttendanceSerializer(serializers.ModelSerializer):
    """
    Sanitized attendance view for Module 10 (FR-6.70 to FR-6.72, AC-51 to AC-54).
    Omits exact GPS coordinates, GPS accuracy, battery, network, device ID, and internal fraud flags.
    """
    guard_name = serializers.CharField(source='employee.full_name', read_only=True)
    guard_code = serializers.CharField(source='employee.employee_code', read_only=True)
    site_name = serializers.CharField(source='site.site_name', read_only=True)
    shift_name = serializers.CharField(source='shift.shift_name', read_only=True)

    class Meta:
        model = AttendanceRecord
        fields = [
            'attendance_id', 'duty_date', 'guard_name', 'guard_code',
            'site_name', 'shift_name', 'actual_check_in', 'actual_check_out',
            'worked_minutes', 'status', 'is_manual', 'is_offline'
        ]

