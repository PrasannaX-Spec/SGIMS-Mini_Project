import csv
from datetime import datetime, date
from django.http import HttpResponse
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from foundation.services.scope_service import HasCapabilityAndScope, ScopedQuerySetMixin
from guard_management.models import Employee

from attendance.models import (
    AttendancePeriod,
    AttendanceRecord,
    AttendanceCapture,
    AttendanceFlag,
    AttendanceRegularisation,
    AttendanceHandover,
)
from attendance import services
from attendance.serializers import (
    AttendanceRecordListSerializer,
    AttendanceRecordDetailSerializer,
    AttendancePeriodSerializer,
    AttendanceRegularisationSerializer,
    ClientSafeAttendanceSerializer,
)


class AttendanceDashboardView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'attendance.read'

    def get(self, request):
        company_id = request.user.company_id
        site_id = request.query_params.get('site_id')
        duty_date_str = request.query_params.get('date', date.today().isoformat())

        try:
            target_date = datetime.strptime(duty_date_str, '%Y-%m-%d').date()
        except ValueError:
            target_date = date.today()

        qs = AttendanceRecord.objects.filter(company_id=company_id, duty_date=target_date)
        if site_id:
            qs = qs.filter(site_id=site_id)

        metrics = qs.aggregate(
            scheduled_count=Count('attendance_id'),
            in_progress_count=Count('attendance_id', filter=Q(status='in_progress')),
            completed_count=Count('attendance_id', filter=Q(status='completed')),
            late_count=Count('attendance_id', filter=Q(status='late')),
            absent_count=Count('attendance_id', filter=Q(status='absent')),
            pending_approval_count=Count('attendance_id', filter=Q(status='pending_approval')),
            approved_count=Count('attendance_id', filter=Q(status='approved')),
            rejected_count=Count('attendance_id', filter=Q(status='rejected')),
            no_checkout_count=Count('attendance_id', filter=Q(status='no_checkout')),
            flagged_count=Count('attendance_id', filter=Q(flags__resolved_at__isnull=True), distinct=True)
        )

        checked_in = metrics['in_progress_count'] + metrics['completed_count'] + metrics['late_count'] + metrics['pending_approval_count'] + metrics['approved_count']
        sched = metrics['scheduled_count'] or 1
        coverage_pct = round((checked_in / sched) * 100.0, 1)

        return Response({
            'date': str(target_date),
            'scheduled_count': metrics['scheduled_count'],
            'checked_in_count': checked_in,
            'late_count': metrics['late_count'],
            'absent_count': metrics['absent_count'],
            'pending_approval_count': metrics['pending_approval_count'],
            'approved_count': metrics['approved_count'],
            'no_checkout_count': metrics['no_checkout_count'],
            'flagged_count': metrics['flagged_count'],
            'coverage_percentage': min(100.0, coverage_pct)
        })


class AttendanceRecordListView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'attendance.read'

    def get(self, request):
        company_id = request.user.company_id
        qs = AttendanceRecord.objects.filter(company_id=company_id).select_related(
            'employee', 'site', 'shift'
        ).prefetch_related('flags').order_by('-duty_date', 'scheduled_start')

        site_id = request.query_params.get('site_id')
        if site_id:
            qs = qs.filter(site_id=site_id)

        duty_date = request.query_params.get('date')
        if duty_date:
            qs = qs.filter(duty_date=duty_date)

        status_param = request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)

        has_flags = request.query_params.get('has_flags')
        if has_flags == 'true':
            qs = qs.filter(flags__resolved_at__isnull=True).distinct()

        serializer = AttendanceRecordListSerializer(qs[:100], many=True)
        return Response({'results': serializer.data})


class AttendanceRecordDetailView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'attendance.read'

    def get(self, request, attendance_id):
        try:
            record = AttendanceRecord.objects.select_related(
                'employee', 'site', 'shift', 'assignment'
            ).prefetch_related('flags', 'captures', 'evidence', 'revisions').get(attendance_id=attendance_id)
        except AttendanceRecord.DoesNotExist:
            return Response({'detail': 'Attendance record not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = AttendanceRecordDetailSerializer(record)
        return Response(serializer.data)


class CheckInView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'attendance.capture'

    def post(self, request):
        employee_id = request.data.get('employee_id')
        if not employee_id:
            if request.user.guard_profile_id:
                employee_id = request.user.guard_profile_id
            else:
                return Response({'detail': 'employee_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        attendance = services.record_check_in(
            employee_id=employee_id,
            data=request.data,
            actor_user=request.user,
            request=request
        )
        return Response(AttendanceRecordListSerializer(attendance).data, status=status.HTTP_201_CREATED)


class CheckOutView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'attendance.capture'

    def post(self, request):
        employee_id = request.data.get('employee_id')
        if not employee_id:
            if request.user.guard_profile_id:
                employee_id = request.user.guard_profile_id
            else:
                return Response({'detail': 'employee_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        attendance = services.record_check_out(
            employee_id=employee_id,
            data=request.data,
            actor_user=request.user,
            request=request
        )
        return Response(AttendanceRecordListSerializer(attendance).data, status=status.HTTP_200_OK)


class AttendanceApproveView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'attendance.approve'

    def post(self, request, attendance_id):
        attendance = services.approve_attendance(
            attendance_id=attendance_id,
            actor_user=request.user,
            request=request
        )
        return Response(AttendanceRecordListSerializer(attendance).data, status=status.HTTP_200_OK)


class AttendanceBulkApproveView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'attendance.approve'

    def post(self, request):
        site_id = request.data.get('site_id')
        duty_date = request.data.get('date', date.today().isoformat())
        if not site_id:
            return Response({'detail': 'site_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        res = services.bulk_approve_clean_attendance(
            site_id=site_id,
            duty_date=duty_date,
            actor_user=request.user,
            request=request
        )
        return Response(res, status=status.HTTP_200_OK)


class AttendanceRejectView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'attendance.approve'

    def post(self, request, attendance_id):
        reason = request.data.get('reason')
        attendance = services.reject_attendance(
            attendance_id=attendance_id,
            reason=reason,
            actor_user=request.user,
            request=request
        )
        return Response(AttendanceRecordListSerializer(attendance).data, status=status.HTTP_200_OK)


class AttendanceCorrectView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'attendance.correct'

    def post(self, request, attendance_id):
        attendance = services.correct_attendance(
            attendance_id=attendance_id,
            data=request.data,
            actor_user=request.user,
            request=request
        )
        return Response(AttendanceRecordListSerializer(attendance).data, status=status.HTTP_200_OK)


class AttendanceMarkAbsentView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'attendance.approve'

    def post(self, request, attendance_id):
        reason = request.data.get('reason', 'Supervisor marked absent')
        att = AttendanceRecord.objects.get(attendance_id=attendance_id)
        att.status = 'absent'
        att.save()
        return Response(AttendanceRecordListSerializer(att).data, status=status.HTTP_200_OK)


class AttendanceRegularisationView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'attendance.capture'

    def get(self, request):
        qs = AttendanceRegularisation.objects.filter(
            site__client__company_id=request.user.company_id
        ).select_related('employee', 'site', 'shift').order_by('-created_at')

        if request.user.role == 'GUARD' and request.user.guard_profile_id:
            qs = qs.filter(employee_id=request.user.guard_profile_id)

        serializer = AttendanceRegularisationSerializer(qs[:50], many=True)
        return Response({'results': serializer.data})

    def post(self, request):
        employee_id = request.data.get('employee_id') or request.user.guard_profile_id
        if not employee_id:
            return Response({'detail': 'employee_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        reg = services.submit_regularisation(
            employee_id=employee_id,
            data=request.data,
            actor_user=request.user
        )
        return Response(AttendanceRegularisationSerializer(reg).data, status=status.HTTP_201_CREATED)


class AttendanceRegularisationDecideView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'attendance.approve'

    def post(self, request, request_id):
        decision = request.data.get('decision')
        notes = request.data.get('notes', '')
        reg = services.decide_regularisation(
            request_id=request_id,
            decision=decision,
            decision_notes=notes,
            actor_user=request.user
        )
        return Response(AttendanceRegularisationSerializer(reg).data, status=status.HTTP_200_OK)


class AttendancePeriodView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'attendance.lock'

    def get(self, request):
        periods = AttendancePeriod.objects.filter(
            company_id=request.user.company_id
        ).select_related('closed_by').order_by('-start_date')
        serializer = AttendancePeriodSerializer(periods, many=True)
        return Response({'results': serializer.data})

    def post(self, request):
        period = services.close_attendance_period(
            company_id=request.user.company_id,
            data=request.data,
            actor_user=request.user
        )
        return Response(AttendancePeriodSerializer(period).data, status=status.HTTP_201_CREATED)


class AttendancePeriodReopenView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'attendance.lock'

    def post(self, request, period_id):
        reason = request.data.get('reason')
        period = services.reopen_attendance_period(
            period_id=period_id,
            reason=reason,
            actor_user=request.user
        )
        return Response(AttendancePeriodSerializer(period).data, status=status.HTTP_200_OK)


class AttendanceHandoverView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'attendance.capture'

    def post(self, request):
        outgoing_id = request.data.get('outgoing_attendance_id')
        incoming_code = request.data.get('incoming_employee_code')
        notes = request.data.get('notes', '')

        att = AttendanceRecord.objects.get(attendance_id=outgoing_id)
        handover = AttendanceHandover.objects.create(
            outgoing_attendance=att,
            incoming_employee_code=incoming_code,
            site=att.site,
            handover_time=timezone.now(),
            notes=notes
        )
        return Response({'handover_id': str(handover.handover_id), 'status': 'recorded'}, status=status.HTTP_201_CREATED)


class ClientSafeAttendanceView(APIView):
    """
    Sanitized attendance endpoint for Module 10 Client Portal (FR-6.70 to FR-6.72, AC-51 to AC-54).
    """
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'attendance.client_read'

    def get(self, request):
        site_id = request.query_params.get('site_id')
        duty_date = request.query_params.get('date', date.today().isoformat())

        qs = AttendanceRecord.objects.filter(
            duty_date=duty_date,
            status__in=['approved', 'completed', 'in_progress']
        ).select_related('employee', 'site', 'shift')

        if site_id:
            qs = qs.filter(site_id=site_id)

        serializer = ClientSafeAttendanceSerializer(qs, many=True)
        return Response({'results': serializer.data})


class AttendanceExportView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'attendance.export'

    def get(self, request):
        company_id = request.user.company_id
        site_id = request.query_params.get('site_id')
        start_date = request.query_params.get('start_date', date.today().isoformat())
        end_date = request.query_params.get('end_date', date.today().isoformat())

        qs = AttendanceRecord.objects.filter(
            company_id=company_id,
            duty_date__gte=start_date,
            duty_date__lte=end_date
        ).select_related('employee', 'site', 'shift').order_by('duty_date', 'scheduled_start')

        if site_id:
            qs = qs.filter(site_id=site_id)

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="attendance_{start_date}_to_{end_date}.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'Attendance ID', 'Date', 'Site Code', 'Site Name', 'Shift',
            'Employee Code', 'Employee Name', 'Scheduled Start', 'Scheduled End',
            'Actual Check In', 'Actual Check Out', 'Late Minutes', 'Early Exit Minutes',
            'Worked Minutes', 'Regular Minutes', 'Overtime Minutes', 'Status',
            'Is Manual', 'Is Offline'
        ])

        for r in qs:
            writer.writerow([
                str(r.attendance_id),
                str(r.duty_date),
                r.site.site_code,
                r.site.site_name,
                r.shift.shift_name,
                r.employee.employee_code,
                r.employee.full_name,
                r.scheduled_start.strftime('%Y-%m-%d %H:%M'),
                r.scheduled_end.strftime('%Y-%m-%d %H:%M'),
                r.actual_check_in.strftime('%Y-%m-%d %H:%M') if r.actual_check_in else '',
                r.actual_check_out.strftime('%Y-%m-%d %H:%M') if r.actual_check_out else '',
                r.late_minutes,
                r.early_exit_minutes,
                r.worked_minutes,
                r.regular_minutes,
                r.overtime_minutes,
                r.status,
                'Yes' if r.is_manual else 'No',
                'Yes' if r.is_offline else 'No'
            ])

        return response
