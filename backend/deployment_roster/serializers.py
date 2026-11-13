import uuid
from rest_framework import serializers
from .models import (
    PostSlot,
    Roster,
    RosterAssignment,
    AssignmentHistory,
    ShiftSwapRequest,
    EmergencyRatification,
    DutyAcknowledgement,
    OvertimeRecord,
    RelieverPoolMembership,
)


class PostSlotSerializer(serializers.ModelSerializer):
    site_name = serializers.ReadOnlyField(source='site.site_name')
    shift_name = serializers.ReadOnlyField(source='shift.shift_name')
    shift_start = serializers.ReadOnlyField(source='shift.start_time')
    shift_end = serializers.ReadOnlyField(source='shift.end_time')
    post_type_name = serializers.ReadOnlyField(source='post_type.name')
    requires_armed = serializers.ReadOnlyField(source='post_type.requires_armed_authorization')
    active_assignment = serializers.SerializerMethodField()

    class Meta:
        model = PostSlot
        fields = [
            'slot_id',
            'company',
            'site',
            'site_name',
            'requirement',
            'post_type',
            'post_type_name',
            'requires_armed',
            'shift',
            'shift_name',
            'shift_start',
            'shift_end',
            'deployment_date',
            'slot_sequence',
            'slot_status',
            'active_assignment',
            'created_at',
        ]
        read_only_fields = ['slot_id', 'created_at']

    def get_active_assignment(self, obj):
        assign = obj.assignments.filter(status__in=['scheduled', 'acknowledged', 'completed']).first()
        if not assign:
            return None
        return {
            'assignment_id': str(assign.assignment_id),
            'employee_id': str(assign.employee.employee_id),
            'guard_name': assign.employee.full_name,
            'employee_code': assign.employee.employee_code,
            'assignment_type': assign.assignment_type,
            'status': assign.status,
            'is_emergency': assign.is_emergency
        }


class AssignmentHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = AssignmentHistory
        fields = [
            'history_id',
            'action',
            'previous_values',
            'new_values',
            'actor_user_id',
            'reason',
            'created_at',
        ]


class RosterAssignmentSerializer(serializers.ModelSerializer):
    guard_name = serializers.ReadOnlyField(source='employee.full_name')
    employee_code = serializers.ReadOnlyField(source='employee.employee_code')
    site_name = serializers.ReadOnlyField(source='site.site_name')
    shift_name = serializers.ReadOnlyField(source='shift.shift_name')
    post_type_name = serializers.ReadOnlyField(source='post_type.name')
    history = AssignmentHistorySerializer(many=True, read_only=True)

    class Meta:
        model = RosterAssignment
        fields = [
            'assignment_id',
            'slot',
            'roster',
            'employee',
            'guard_name',
            'employee_code',
            'site',
            'site_name',
            'shift',
            'shift_name',
            'post_type',
            'post_type_name',
            'deployment_date',
            'start_time',
            'end_time',
            'assignment_type',
            'status',
            'is_emergency',
            'original_assignment',
            'history',
            'created_at',
        ]
        read_only_fields = ['assignment_id', 'created_at']


class RosterSerializer(serializers.ModelSerializer):
    site_name = serializers.ReadOnlyField(source='site.site_name')

    class Meta:
        model = Roster
        fields = [
            'roster_id',
            'company',
            'site',
            'site_name',
            'start_date',
            'end_date',
            'status',
            'published_by',
            'published_at',
            'created_at',
        ]
        read_only_fields = ['roster_id', 'created_at']


class ShiftSwapRequestSerializer(serializers.ModelSerializer):
    site_name = serializers.ReadOnlyField(source='site.site_name')
    requesting_guard_name = serializers.ReadOnlyField(source='requesting_employee.full_name')
    target_guard_name = serializers.ReadOnlyField(source='target_employee.full_name')

    class Meta:
        model = ShiftSwapRequest
        fields = [
            'swap_id',
            'site',
            'site_name',
            'requesting_employee',
            'requesting_guard_name',
            'target_employee',
            'target_guard_name',
            'assignment_a',
            'assignment_b',
            'reason',
            'status',
            'reviewed_by_user_id',
            'reviewed_at',
            'created_at',
        ]
        read_only_fields = ['swap_id', 'status', 'reviewed_by_user_id', 'reviewed_at', 'created_at']


class EmergencyRatificationSerializer(serializers.ModelSerializer):
    guard_name = serializers.ReadOnlyField(source='assignment.employee.full_name')
    site_name = serializers.ReadOnlyField(source='assignment.site.site_name')
    shift_name = serializers.ReadOnlyField(source='assignment.shift.shift_name')
    deployment_date = serializers.ReadOnlyField(source='assignment.deployment_date')

    class Meta:
        model = EmergencyRatification
        fields = [
            'ratification_id',
            'assignment',
            'guard_name',
            'site_name',
            'shift_name',
            'deployment_date',
            'supervisor_user_id',
            'admin_user_id',
            'reason',
            'status',
            'deadline',
            'reviewed_at',
            'created_at',
        ]
        read_only_fields = ['ratification_id', 'deadline', 'created_at']

