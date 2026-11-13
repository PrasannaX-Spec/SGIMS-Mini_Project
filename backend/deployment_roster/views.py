import csv
import io
from datetime import date, datetime, timedelta
from django.http import HttpResponse
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError, PermissionDenied, NotFound

from foundation.services.scope_service import HasCapabilityAndScope
from master_data.models import ClientSite, SiteSupervisorAssignment
from guard_management.models import Employee
from .models import (
    PostSlot,
    Roster,
    RosterAssignment,
    ShiftSwapRequest,
    EmergencyRatification,
    DutyAcknowledgement,
)
from .serializers import (
    PostSlotSerializer,
    RosterAssignmentSerializer,
    RosterSerializer,
    ShiftSwapRequestSerializer,
    EmergencyRatificationSerializer,
)
from . import services


class SlotGenerationView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'roster.manage'

    def post(self, request):
        site_id = request.data.get('site_id')
        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')

        if not site_id or not start_date or not end_date:
            return Response({'error': 'site_id, start_date, and end_date are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = services.generate_slots_for_period(site_id, start_date, end_date, request.user, request=request)
            return Response(result, status=status.HTTP_201_CREATED)
        except (ValidationError, ClientSite.DoesNotExist) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class SlotListView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'roster.view'

    def get(self, request):
        user = request.user
        role = getattr(user, 'role', '').lower()
        company_id = user.company_id

        qs = PostSlot.objects.filter(company_id=company_id)

        # Supervisor site scoping (FR-5.57, AC-37)
        if role == 'supervisor':
            assigned_site_ids = SiteSupervisorAssignment.objects.filter(
                supervisor_user_id=user.user_id,
                is_active=True
            ).values_list('site_id', flat=True)
            qs = qs.filter(site_id__in=assigned_site_ids)

        site_id = request.query_params.get('site_id')
        if site_id:
            qs = qs.filter(site_id=site_id)

        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        if start_date:
            qs = qs.filter(deployment_date__gte=start_date)
        if end_date:
            qs = qs.filter(deployment_date__lte=end_date)

        slot_status = request.query_params.get('status')
        if slot_status:
            qs = qs.filter(slot_status=slot_status)

        qs = qs.order_by('deployment_date', 'shift__start_time', 'slot_sequence')
        serializer = PostSlotSerializer(qs, many=True)
        return Response(serializer.data)


class SlotAssignmentView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'roster.manage'

    def post(self, request):
        slot_id = request.data.get('slot_id')
        employee_id = request.data.get('employee_id')
        assignment_type = request.data.get('assignment_type', 'regular')
        soft_override_reason = request.data.get('soft_override_reason')

        if not slot_id or not employee_id:
            return Response({'error': 'slot_id and employee_id are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            assignment = services.assign_guard_to_slot(
                slot_id=slot_id,
                employee_id=employee_id,
                assignment_type=assignment_type,
                soft_override_reason=soft_override_reason,
                actor_user=request.user,
                request=request
            )
            serializer = RosterAssignmentSerializer(assignment)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except (ValidationError, PostSlot.DoesNotExist, Employee.DoesNotExist) as e:
            if isinstance(e, ValidationError):
                return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class AssignmentDetailView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'roster.view'

    def get(self, request, assignment_id):
        try:
            assignment = RosterAssignment.objects.get(assignment_id=assignment_id)
            serializer = RosterAssignmentSerializer(assignment)
            return Response(serializer.data)
        except RosterAssignment.DoesNotExist:
            raise NotFound("Assignment not found.")

    def delete(self, request, assignment_id):
        # Cancel future assignment (AC-25)
        reason = request.data.get('reason') or request.query_params.get('reason')
        if not reason:
            return Response({'error': 'A mandatory cancellation reason is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            assignment = services.cancel_future_assignment(assignment_id, reason, request.user, request=request)
            return Response({'status': 'cancelled', 'assignment_id': str(assignment.assignment_id)})
        except (ValidationError, RosterAssignment.DoesNotExist) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class AssignmentLockedOverrideView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'roster.manage'

    def post(self, request, assignment_id):
        new_guard_id = request.data.get('employee_id')
        reason = request.data.get('reason')
        try:
            assignment = services.edit_locked_assignment(assignment_id, new_guard_id, reason, request.user, request=request)
            serializer = RosterAssignmentSerializer(assignment)
            return Response(serializer.data)
        except (ValidationError, PermissionDenied, RosterAssignment.DoesNotExist, Employee.DoesNotExist) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class DutyAcknowledgementView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'roster.view'

    def post(self, request, assignment_id):
        device_id = request.headers.get('X-Device-Id') or request.data.get('device_id')
        ip_addr = request.META.get('REMOTE_ADDR')

        try:
            ack = services.acknowledge_duty(assignment_id, request.user, device_id=device_id, ip_address=ip_addr)
            return Response({
                'status': 'acknowledged',
                'acknowledgement_id': str(ack.acknowledgement_id),
                'acknowledged_at': ack.acknowledged_at
            })
        except (PermissionDenied, RosterAssignment.DoesNotExist) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class AssignmentConflictValidationView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'roster.view'

    def post(self, request):
        slot_id = request.data.get('slot_id')
        employee_id = request.data.get('employee_id')

        if not slot_id or not employee_id:
            return Response({'error': 'slot_id and employee_id are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            slot = PostSlot.objects.get(slot_id=slot_id)
            start_dt, end_dt = services.calculate_shift_interval(slot.deployment_date, slot.shift.start_time, slot.shift.end_time)
            result = services.check_assignment_conflicts(
                employee_id=employee_id,
                start_dt=start_dt,
                end_dt=end_dt,
                post_type_id=slot.post_type_id,
                deployment_date=slot.deployment_date
            )
            return Response(result)
        except (PostSlot.DoesNotExist, Employee.DoesNotExist) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class RosterPublishView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'roster.manage'

    def post(self, request):
        site_id = request.data.get('site_id')
        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')

        if not site_id or not start_date or not end_date:
            return Response({'error': 'site_id, start_date, and end_date are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            roster = services.publish_roster(site_id, start_date, end_date, request.user, request=request)
            serializer = RosterSerializer(roster)
            return Response(serializer.data)
        except (ValidationError, ClientSite.DoesNotExist) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ReplacementAssignmentView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'roster.manage'

    def post(self, request):
        original_assignment_id = request.data.get('original_assignment_id')
        replacement_employee_id = request.data.get('replacement_employee_id')
        reason = request.data.get('reason')

        if not original_assignment_id or not replacement_employee_id or not reason:
            return Response({'error': 'original_assignment_id, replacement_employee_id, and reason are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            replacement = services.create_replacement_assignment(
                original_assignment_id=original_assignment_id,
                replacement_employee_id=replacement_employee_id,
                reason=reason,
                actor_user=request.user,
                request=request
            )
            serializer = RosterAssignmentSerializer(replacement)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except (ValidationError, RosterAssignment.DoesNotExist, Employee.DoesNotExist) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ShiftSwapRequestView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'roster.view'

    def get(self, request):
        user = request.user
        role = getattr(user, 'role', '').lower()

        qs = ShiftSwapRequest.objects.filter(company_id=user.company_id)
        if role == 'guard' and user.guard_profile_id:
            qs = qs.filter(
                Q(requesting_employee_id=user.guard_profile_id) |
                Q(target_employee_id=user.guard_profile_id)
            )
        elif role == 'supervisor':
            assigned_sites = SiteSupervisorAssignment.objects.filter(
                supervisor_user_id=user.user_id,
                is_active=True
            ).values_list('site_id', flat=True)
            qs = qs.filter(site_id__in=assigned_sites)

        qs = qs.order_by('-created_at')
        serializer = ShiftSwapRequestSerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request):
        assignment_a_id = request.data.get('assignment_a_id')
        target_employee_id = request.data.get('target_employee_id')
        assignment_b_id = request.data.get('assignment_b_id')
        reason = request.data.get('reason', '')

        if not assignment_a_id or not target_employee_id or not assignment_b_id:
            return Response({'error': 'assignment_a_id, target_employee_id, and assignment_b_id are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            swap = services.request_shift_swap(
                assignment_a_id=assignment_a_id,
                target_employee_id=target_employee_id,
                assignment_b_id=assignment_b_id,
                reason=reason,
                requesting_guard_user=request.user
            )
            serializer = ShiftSwapRequestSerializer(swap)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except (ValidationError, RosterAssignment.DoesNotExist, Employee.DoesNotExist) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ShiftSwapDecideView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'roster.manage'

    def post(self, request, swap_id):
        decision = request.data.get('decision', 'approved')
        if decision == 'approved':
            try:
                swap = services.approve_shift_swap(swap_id, request.user, request=request)
                serializer = ShiftSwapRequestSerializer(swap)
                return Response(serializer.data)
            except (ValidationError, ShiftSwapRequest.DoesNotExist) as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        else:
            try:
                swap = ShiftSwapRequest.objects.get(swap_id=swap_id)
                swap.status = 'rejected'
                swap.reviewed_by_user_id = request.user.user_id
                swap.reviewed_at = datetime.now()
                swap.save()
                return Response({'status': 'rejected'})
            except ShiftSwapRequest.DoesNotExist:
                raise NotFound("Swap request not found.")


class EmergencyDeploymentView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'roster.manage'

    def post(self, request):
        site_id = request.data.get('site_id')
        shift_id = request.data.get('shift_id')
        post_type_id = request.data.get('post_type_id')
        deployment_date = request.data.get('deployment_date')
        employee_id = request.data.get('employee_id')
        reason = request.data.get('reason')

        if not site_id or not shift_id or not post_type_id or not deployment_date or not employee_id or not reason:
            return Response({'error': 'All emergency deployment fields are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            assignment = services.create_emergency_deployment(
                site_id=site_id,
                shift_id=shift_id,
                post_type_id=post_type_id,
                deployment_date=deployment_date,
                employee_id=employee_id,
                reason=reason,
                supervisor_user=request.user,
                request=request
            )
            serializer = RosterAssignmentSerializer(assignment)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except (ValidationError, ClientSite.DoesNotExist, Employee.DoesNotExist) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class EmergencyRatificationView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'roster.manage'

    def get(self, request):
        qs = EmergencyRatification.objects.filter(
            assignment__company_id=request.user.company_id
        ).order_by('-created_at')
        serializer = EmergencyRatificationSerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request, ratification_id):
        decision = request.data.get('decision')
        try:
            rat = services.ratify_emergency_deployment(ratification_id, decision, request.user, request=request)
            serializer = EmergencyRatificationSerializer(rat)
            return Response(serializer.data)
        except (ValidationError, EmergencyRatification.DoesNotExist) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class CoverageDashboardView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'reports.view'

    def get(self, request):
        user = request.user
        role = getattr(user, 'role', '').lower()
        company_id = user.company_id
        today = date.today()

        qs = PostSlot.objects.filter(company_id=company_id)
        if role == 'supervisor':
            assigned_sites = SiteSupervisorAssignment.objects.filter(
                supervisor_user_id=user.user_id,
                is_active=True
            ).values_list('site_id', flat=True)
            qs = qs.filter(site_id__in=assigned_sites)

        # Filters
        site_id = request.query_params.get('site_id')
        if site_id:
            qs = qs.filter(site_id=site_id)

        # Today metrics
        today_slots = qs.filter(deployment_date=today)
        today_total = today_slots.count()
        today_filled = today_slots.filter(slot_status='filled').count()
        today_vacant = today_slots.filter(slot_status='open').count()
        today_at_risk = today_slots.filter(slot_status='at_risk').count()

        # Next 7 days
        next7 = qs.filter(deployment_date__gte=today, deployment_date__lte=today + timedelta(days=7))
        next7_total = next7.count()
        next7_filled = next7.filter(slot_status='filled').count()
        next7_vacant = next7.filter(slot_status='open').count()
        next7_at_risk = next7.filter(slot_status='at_risk').count()

        # Unacknowledged assignments today
        unacknowledged = RosterAssignment.objects.filter(
            company_id=company_id,
            deployment_date=today,
            status='scheduled'
        ).count()

        return Response({
            'today': {
                'total_required': today_total,
                'filled': today_filled,
                'vacant': today_vacant,
                'at_risk': today_at_risk,
                'unacknowledged': unacknowledged,
            },
            'next_7_days': {
                'total_required': next7_total,
                'filled': next7_filled,
                'vacant': next7_vacant,
                'at_risk': next7_at_risk,
            }
        })


class CoverageExportView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'reports.export'

    def get(self, request):
        user = request.user
        start_date = request.query_params.get('start_date') or str(date.today())
        end_date = request.query_params.get('end_date') or str(date.today() + timedelta(days=7))

        slots = PostSlot.objects.filter(
            company_id=user.company_id,
            deployment_date__gte=start_date,
            deployment_date__lte=end_date
        ).select_related('site', 'shift', 'post_type')

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Deployment Date', 'Site Code', 'Site Name', 'Shift', 'Post Type', 'Sequence', 'Slot Status', 'Assigned Guard'])

        for s in slots:
            assign = s.assignments.filter(status__in=['scheduled', 'acknowledged', 'completed']).first()
            writer.writerow([
                s.deployment_date,
                s.site.site_code,
                s.site.site_name,
                s.shift.shift_name,
                s.post_type.name,
                s.slot_sequence,
                s.slot_status,
                assign.employee.full_name if assign else 'VACANT'
            ])

        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="roster_coverage_{start_date}_to_{end_date}.csv"'
        return response


class GuardDutiesView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'roster.view'

    def get(self, request):
        user = request.user
        role = getattr(user, 'role', '').lower()

        if role == 'guard':
            if not user.guard_profile_id:
                return Response([])
            employee_id = user.guard_profile_id
        else:
            employee_id = request.query_params.get('employee_id')
            if not employee_id:
                return Response({'error': 'employee_id query param is required.'}, status=status.HTTP_400_BAD_REQUEST)

        today = date.today()
        upcoming = RosterAssignment.objects.filter(
            employee_id=employee_id,
            deployment_date__gte=today,
            status__in=['scheduled', 'acknowledged', 'completed']
        ).order_by('deployment_date', 'start_time')

        serializer = RosterAssignmentSerializer(upcoming, many=True)
        return Response(serializer.data)

