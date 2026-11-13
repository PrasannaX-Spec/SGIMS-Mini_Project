from datetime import datetime, date, timedelta
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError

from foundation.services.scope_service import HasCapabilityAndScope, ScopedQuerySetMixin
from foundation.services.audit_service import write_audit_event
from master_data.models import ClientSite, SiteSupervisorAssignment
from guard_management.models import Employee
from deployment_roster.models import RosterAssignment

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
from live_monitoring.serializers import (
    GuardMonitoringStatusSerializer,
    LocationPointSerializer,
    HeartbeatSerializer,
    MonitoringAlertSerializer,
    SupervisorPingSerializer,
    TrackingConfigurationSerializer,
    MonitoringStatusHistorySerializer
)
from live_monitoring import services


class StartMonitoringDutyView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'attendance.capture'

    def post(self, request):
        assignment_id = request.data.get('assignment_id')
        attendance_record_id = request.data.get('attendance_record_id')
        if not assignment_id:
            return Response({'detail': 'assignment_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        duty = services.start_monitoring_duty(
            assignment_id=assignment_id,
            attendance_record_id=attendance_record_id,
            duty_start_at=timezone.now(),
            actor_user=request.user,
            request=request
        )
        return Response({
            'duty_id': str(duty.duty_id),
            'tracking_state': duty.tracking_state,
            'duty_start_at': duty.duty_start_at.isoformat()
        }, status=status.HTTP_201_CREATED)


class StopMonitoringDutyView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'attendance.capture'

    def post(self, request):
        duty_id = request.data.get('duty_id')
        reason = request.data.get('reason', 'CHECK_OUT')
        if not duty_id:
            return Response({'detail': 'duty_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        duty = services.stop_monitoring_duty(
            duty_id=duty_id,
            duty_end_at=timezone.now(),
            reason=reason,
            actor_user=request.user,
            request=request
        )
        return Response({
            'duty_id': str(duty.duty_id),
            'tracking_state': duty.tracking_state,
            'duty_end_at': duty.duty_end_at.isoformat() if duty.duty_end_at else None
        }, status=status.HTTP_200_OK)


class LocationBatchIngestView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'monitoring.ingest'

    def post(self, request):
        duty_id = request.data.get('duty_id')
        locations = request.data.get('locations', [])
        if not duty_id:
            return Response({'detail': 'duty_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        res = services.ingest_location_batch(
            duty_id=duty_id,
            locations_data=locations,
            actor_user=request.user,
            request=request
        )
        return Response(res, status=status.HTTP_200_OK)


class HeartbeatIngestView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'monitoring.ingest'

    def post(self, request):
        duty_id = request.data.get('duty_id')
        heartbeat_data = request.data.get('heartbeat', {})
        if not duty_id:
            return Response({'detail': 'duty_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        res = services.ingest_heartbeat(
            duty_id=duty_id,
            heartbeat_data=heartbeat_data,
            actor_user=request.user,
            request=request
        )
        return Response(res, status=status.HTTP_200_OK)


class LiveMonitoringMapView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'monitoring.view_live'

    def get(self, request):
        company_id = request.user.company_id
        # Run periodic recalculations to catch stale & no-contact transitions
        services.recalculate_duty_statuses(company_id=company_id)

        qs = GuardMonitoringStatus.objects.filter(
            company_id=company_id
        ).select_related('employee', 'site', 'duty', 'duty__shift', 'last_location_point', 'last_heartbeat')

        # Scope enforcement (Section 2.1, AC-7.41)
        if request.user.role == 'SUPERVISOR':
            assigned_sites = SiteSupervisorAssignment.objects.filter(
                supervisor_user_id=request.user.user_id, is_active=True
            ).values_list('site_id', flat=True)
            qs = qs.filter(site_id__in=assigned_sites)

        site_id = request.query_params.get('site_id')
        if site_id:
            qs = qs.filter(site_id=site_id)

        status_param = request.query_params.get('status')
        if status_param and status_param != 'ALL':
            qs = qs.filter(primary_status=status_param)

        has_alert = request.query_params.get('has_alert')
        if has_alert == 'true':
            qs = qs.filter(has_active_alert=True)

        serializer = GuardMonitoringStatusSerializer(qs[:200], many=True)
        return Response({'results': serializer.data})


class MonitoringStatusBoardView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'monitoring.view_live'

    def get(self, request):
        company_id = request.user.company_id
        services.recalculate_duty_statuses(company_id=company_id)

        qs = GuardMonitoringStatus.objects.filter(
            company_id=company_id
        ).select_related('employee', 'site', 'duty', 'duty__shift', 'last_location_point', 'last_heartbeat')

        if request.user.role == 'SUPERVISOR':
            assigned_sites = SiteSupervisorAssignment.objects.filter(
                supervisor_user_id=request.user.user_id, is_active=True
            ).values_list('site_id', flat=True)
            qs = qs.filter(site_id__in=assigned_sites)

        site_id = request.query_params.get('site_id')
        if site_id:
            qs = qs.filter(site_id=site_id)

        status_param = request.query_params.get('status')
        if status_param and status_param != 'ALL':
            qs = qs.filter(primary_status=status_param)

        search = request.query_params.get('search')
        if search:
            qs = qs.filter(
                employee__full_name__icontains=search
            ) | qs.filter(
                employee__employee_code__icontains=search
            )

        serializer = GuardMonitoringStatusSerializer(qs[:100], many=True)

        # Compute summary metrics for top cards
        all_for_co = GuardMonitoringStatus.objects.filter(company_id=company_id)
        if request.user.role == 'SUPERVISOR':
            all_for_co = all_for_co.filter(site_id__in=assigned_sites)

        metrics = {
            'total_monitored': all_for_co.exclude(primary_status='off_duty').count(),
            'on_duty_site': all_for_co.filter(primary_status='on_duty_at_site').count(),
            'on_duty_outside': all_for_co.filter(primary_status='on_duty_outside_site').count(),
            'stale_count': all_for_co.filter(primary_status='stale').count(),
            'no_contact_count': all_for_co.filter(primary_status='no_contact').count(),
            'active_alerts_count': all_for_co.filter(has_active_alert=True).count(),
        }

        return Response({
            'metrics': metrics,
            'results': serializer.data
        })


class GuardDetailView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'monitoring.view_live'

    def get(self, request, guard_id):
        company_id = request.user.company_id
        status_obj = GuardMonitoringStatus.objects.select_related(
            'employee', 'site', 'duty', 'duty__shift', 'last_location_point', 'last_heartbeat'
        ).filter(company_id=company_id, employee_id=guard_id).first()

        if not status_obj:
            return Response({'detail': 'Guard monitoring status not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Supervisor scope check
        if request.user.role == 'SUPERVISOR':
            assigned_sites = SiteSupervisorAssignment.objects.filter(
                supervisor_user_id=request.user.user_id, is_active=True
            ).values_list('site_id', flat=True)
            if status_obj.site_id not in assigned_sites:
                raise PermissionDenied("You do not have permission to view guards at this site.")

        status_data = GuardMonitoringStatusSerializer(status_obj).data

        # Recent alerts for this duty
        alerts = MonitoringAlert.objects.filter(
            duty=status_obj.duty
        ).order_by('-raised_at')[:5]
        alerts_data = MonitoringAlertSerializer(alerts, many=True).data

        # Status transition history
        history = MonitoringStatusHistory.objects.filter(
            duty=status_obj.duty
        ).order_by('-changed_at')[:10]
        history_data = MonitoringStatusHistorySerializer(history, many=True).data

        return Response({
            'status': status_data,
            'alerts': alerts_data,
            'history': history_data
        })


class GuardDutyTrailView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'monitoring.view_live'

    def get(self, request, guard_id):
        duty = MonitoringDuty.objects.filter(employee_id=guard_id).order_by('-created_at').first()
        if not duty:
            return Response({'results': []})

        if request.user.role == 'SUPERVISOR':
            assigned_sites = SiteSupervisorAssignment.objects.filter(
                supervisor_user_id=request.user.user_id, is_active=True
            ).values_list('site_id', flat=True)
            if duty.site_id not in assigned_sites:
                raise PermissionDenied("You do not have permission to view trails at this site.")

        pts = LocationPoint.objects.filter(
            duty=duty, accepted=True
        ).order_by('device_captured_at')[:500]

        return Response({
            'duty_id': str(duty.duty_id),
            'employee_id': str(guard_id),
            'points': LocationPointSerializer(pts, many=True).data
        })


class GuardHistoricalTrailView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'monitoring.historical_trail'

    def get(self, request, guard_id):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        if not start_date or not end_date:
            return Response({'detail': 'start_date and end_date are required.'}, status=status.HTTP_400_BAD_REQUEST)

        employee = Employee.objects.get(employee_id=guard_id)

        # Audit logging (FR-7.85, AC-7.45, AC-7.46)
        write_audit_event(
            action_code='monitoring.historical_trail.access',
            actor_user=request.user,
            record_type='LocationPoint',
            record_id=str(guard_id),
            reason=f"Historical trail accessed for {employee.full_name} ({start_date} to {end_date})",
            result='SUCCESS',
            company_id=request.user.company_id,
            ip_address=getattr(request, 'client_ip', None),
            user_agent=getattr(request, 'user_agent_str', None)
        )

        pts = LocationPoint.objects.filter(
            employee_id=guard_id,
            accepted=True,
            device_captured_at__date__gte=start_date,
            device_captured_at__date__lte=end_date
        ).order_by('device_captured_at')[:1000]

        return Response({
            'employee_id': str(guard_id),
            'employee_name': employee.full_name,
            'start_date': start_date,
            'end_date': end_date,
            'points': LocationPointSerializer(pts, many=True).data
        })


class SiteOverviewView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'monitoring.view_live'

    def get(self, request, site_id):
        site = ClientSite.objects.get(site_id=site_id)
        today = date.today()

        # Expected assignments today
        expected_slots = RosterAssignment.objects.filter(
            site_id=site_id, duty_date=today, status='PUBLISHED'
        ).select_related('employee', 'shift')

        # Monitored guards
        monitored = GuardMonitoringStatus.objects.filter(
            site_id=site_id
        ).select_related('employee')

        monitored_map = {m.employee_id: m for m in monitored}

        expected_list = []
        for a in expected_slots:
            stat = monitored_map.get(a.employee_id)
            expected_list.append({
                'employee_id': str(a.employee_id),
                'employee_name': a.employee.full_name,
                'employee_code': a.employee.employee_code,
                'shift_name': a.shift.shift_name,
                'start_time': a.start_time.isoformat(),
                'end_time': a.end_time.isoformat(),
                'status': stat.primary_status if stat else 'not_started',
                'display_status': stat.display_status if stat else 'Not Started'
            })

        return Response({
            'site_id': str(site_id),
            'site_name': site.site_name,
            'expected_count': len(expected_list),
            'on_duty_count': monitored.filter(primary_status='on_duty_at_site').count(),
            'guards': expected_list
        })


class MonitoringAlertListView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'monitoring.view_live'

    def get(self, request):
        company_id = request.user.company_id
        qs = MonitoringAlert.objects.filter(
            company_id=company_id
        ).select_related('employee', 'site', 'acknowledged_by', 'resolved_by').order_by('-raised_at')

        if request.user.role == 'SUPERVISOR':
            assigned_sites = SiteSupervisorAssignment.objects.filter(
                supervisor_user_id=request.user.user_id, is_active=True
            ).values_list('site_id', flat=True)
            qs = qs.filter(site_id__in=assigned_sites)

        state_param = request.query_params.get('state')
        if state_param:
            qs = qs.filter(state=state_param)

        serializer = MonitoringAlertSerializer(qs[:100], many=True)
        return Response({'results': serializer.data})


class MonitoringAlertAcknowledgeView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'monitoring.manage_alerts'

    def post(self, request, alert_id):
        alert = services.acknowledge_alert(alert_id, request.user, request=request)
        return Response(MonitoringAlertSerializer(alert).data, status=status.HTTP_200_OK)


class MonitoringAlertResolveView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'monitoring.manage_alerts'

    def post(self, request, alert_id):
        note = request.data.get('note', '')
        alert = services.resolve_alert(alert_id, note, request.user, request=request)
        return Response(MonitoringAlertSerializer(alert).data, status=status.HTTP_200_OK)


class MonitoringAlertDismissView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'monitoring.manage_alerts'

    def post(self, request, alert_id):
        reason = request.data.get('reason', '')
        alert = services.dismiss_alert_as_false_alarm(alert_id, reason, request.user, request=request)
        return Response(MonitoringAlertSerializer(alert).data, status=status.HTTP_200_OK)


class SupervisorPingSendView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'monitoring.manage_alerts'

    def post(self, request):
        duty_id = request.data.get('duty_id')
        if not duty_id:
            return Response({'detail': 'duty_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        ping = services.send_supervisor_ping(duty_id, request.user, request=request)
        return Response(SupervisorPingSerializer(ping).data, status=status.HTTP_201_CREATED)


class SupervisorPingRespondView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'monitoring.ping_respond'

    def post(self, request, ping_id):
        val = request.data.get('response', 'I am fine')
        ping = services.respond_to_ping(ping_id, val, request.user, request=request)
        return Response(SupervisorPingSerializer(ping).data, status=status.HTTP_200_OK)


class TrackingConfigView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'monitoring.config'

    def get(self, request):
        cfg, _ = TrackingConfiguration.objects.get_or_create(company_id=request.user.company_id)
        rules = AlertRule.objects.filter(company_id=request.user.company_id)
        return Response({
            'configuration': TrackingConfigurationSerializer(cfg).data,
            'rules': AlertRuleSerializer(rules, many=True).data
        })

    def put(self, request):
        cfg, _ = TrackingConfiguration.objects.get_or_create(company_id=request.user.company_id)
        serializer = TrackingConfigurationSerializer(cfg, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save(updated_by=request.user)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ClientSafeMonitoringView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'monitoring.client_safe'

    def get(self, request):
        site_id = request.query_params.get('site_id')
        client_co_id = getattr(request.user, 'client_company_id', None) or request.user.company_id
        results = services.get_client_safe_status(client_co_id, site_id=site_id)
        return Response({'results': results})


class LastKnownPositionQueryView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'monitoring.view_live'

    def get(self, request):
        employee_id = request.query_params.get('employee_id')
        duty_id = request.query_params.get('duty_id')
        if not employee_id:
            return Response({'detail': 'employee_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        res = services.get_last_known_position(employee_id, duty_id=duty_id)
        return Response(res, status=status.HTTP_200_OK)


class PositionAtTimeQueryView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'monitoring.view_live'

    def get(self, request):
        employee_id = request.query_params.get('employee_id')
        timestamp_str = request.query_params.get('timestamp')
        if not employee_id or not timestamp_str:
            return Response({'detail': 'employee_id and timestamp are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            target_time = datetime.fromisoformat(timestamp_str)
            if timezone.is_naive(target_time):
                target_time = timezone.make_aware(target_time, pytz.UTC)
        except Exception:
            return Response({'detail': 'Invalid timestamp format.'}, status=status.HTTP_400_BAD_REQUEST)

        res = services.get_guard_position_at_time(employee_id, target_time)
        return Response(res, status=status.HTTP_200_OK)
