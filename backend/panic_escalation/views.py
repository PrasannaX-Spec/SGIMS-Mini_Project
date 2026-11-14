import io
import csv
from datetime import datetime
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import PermissionDenied, ValidationError

from panic_escalation import services
from panic_escalation.models import (
    PanicAlert,
    PanicEscalationConfig,
    PanicDeliveryAttempt,
    PanicDeviceReadiness,
    PanicTestDrill,
    PanicEventTimeline
)
from panic_escalation.serializers import (
    PanicAlertListSerializer,
    PanicAlertDetailSerializer,
    PanicEventTimelineSerializer,
    PanicDeliveryAttemptSerializer,
    PanicEscalationConfigSerializer,
    PanicDeviceReadinessSerializer,
    PanicTestDrillSerializer,
    ClientSafePanicStatusSerializer,
    PanicResponderActionSerializer,
    PanicFalseAlarmReportSerializer,
    PanicResolutionSerializer,
    PanicWelfareFollowupSerializer
)


class PanicAlertListCreateView(APIView):
    """
    Lists active panic alerts or triggers a new panic alert (W-01, M-01).
    """
    required_capability = 'panic.trigger'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        company_id = user.company_id
        is_active_only = request.query_params.get('active_only', 'false').lower() == 'true'
        site_id = request.query_params.get('site_id')
        status_param = request.query_params.get('status')
        test_flag = request.query_params.get('test_flag')

        qs = PanicAlert.objects.filter(company_id=company_id).select_related('guard', 'site')

        if is_active_only:
            qs = qs.filter(alert_status__in=['TRIGGERED', 'DELIVERING', 'ACKNOWLEDGED', 'RESPONDING', 'GUARD_CONFIRMED_SAFE', 'ESCALATED'])

        if site_id:
            qs = qs.filter(site_id=site_id)

        if status_param:
            qs = qs.filter(alert_status=status_param.upper())

        if test_flag is not None:
            qs = qs.filter(test_flag=(test_flag.lower() == 'true'))

        # Scope restrictions for Supervisors and Clients
        if user.role == 'SUPERVISOR':
            assigned_sites = user.site_assignments.filter(is_active=True).values_list('site_id', flat=True)
            qs = qs.filter(site_id__in=assigned_sites)
        elif user.role == 'CLIENT':
            return Response({'detail': 'Clients must use the client-safe panic interface (PRD Section 7.1).'}, status=403)
        elif user.role == 'GUARD':
            qs = qs.filter(guard__phone=user.phone)

        serializer = PanicAlertListSerializer(qs[:100], many=True)
        return Response(serializer.data)

    def post(self, request):
        user = request.user
        data = request.data
        client_gen_id = data.get('client_generated_id')

        if not client_gen_id:
            return Response({'detail': 'client_generated_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        alert, created = services.trigger_panic_alert(
            company_id=user.company_id,
            guard_user=user,
            client_generated_id=client_gen_id,
            device_id=data.get('device_id'),
            device_time=data.get('device_time'),
            battery_level=data.get('battery_level'),
            network_type=data.get('network_type', '4G'),
            app_version=data.get('app_version', '1.0.0'),
            device_status=data.get('device_status', 'ACTIVE'),
            latitude=data.get('latitude'),
            longitude=data.get('longitude'),
            accuracy=data.get('accuracy'),
            site_id=data.get('site_id'),
            assignment_id=data.get('assignment_id'),
            is_test=data.get('is_test', False)
        )

        serializer = PanicAlertDetailSerializer(alert)
        return Response({
            'created': created,
            'alert': serializer.data,
            'message': 'Alert received by the server. Notifications are being attempted.'
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class PanicAlertDetailView(APIView):
    """
    Detailed operational view of an active or historical panic alert (W-02).
    """
    required_capability = 'panic.view'
    permission_classes = [IsAuthenticated]

    def get(self, request, alert_id):
        user = request.user
        alert = PanicAlert.objects.filter(panic_alert_id=alert_id, company_id=user.company_id).first()
        if not alert:
            return Response({'detail': 'Panic alert not found.'}, status=status.HTTP_404_NOT_FOUND)

        if user.role == 'CLIENT':
            raise PermissionDenied("Clients cannot view internal panic alert details (PRD Section 7.1).")

        if user.role == 'SUPERVISOR':
            assigned_sites = user.site_assignments.filter(is_active=True).values_list('site_id', flat=True)
            if alert.site_id not in assigned_sites:
                raise PermissionDenied("Supervisor not authorized for this site.")

        serializer = PanicAlertDetailSerializer(alert)
        return Response(serializer.data)


class PanicAcknowledgeView(APIView):
    """
    Recipient acknowledgement endpoint (W-01, W-02, M-05).
    Stops repeat alarms; does not close the alert.
    """
    required_capability = 'panic.acknowledge'
    permission_classes = [IsAuthenticated]

    def post(self, request, alert_id):
        channel = request.data.get('channel', 'WEB')
        ack_type = request.data.get('acknowledgement_type', 'RECEIPT')
        notes = request.data.get('notes')

        alert = services.acknowledge_panic_alert(
            panic_alert_id=alert_id,
            user=request.user,
            channel=channel,
            acknowledgement_type=ack_type,
            notes=notes
        )
        return Response({
            'detail': f'Alert acknowledged ({ack_type}).',
            'alert_number': alert.alert_number,
            'status': alert.alert_status
        })


class PanicPositionUpdateView(APIView):
    """
    Panic-specific location breadcrumb stream (FR-9.19).
    """
    required_capability = 'panic.trigger'
    permission_classes = [IsAuthenticated]

    def post(self, request, alert_id):
        lat = request.data.get('latitude')
        lng = request.data.get('longitude')
        accuracy = request.data.get('accuracy')
        if lat is None or lng is None:
            return Response({'detail': 'Latitude and longitude are required.'}, status=400)

        pos = services.add_panic_position_update(alert_id, lat, lng, accuracy)
        return Response({'detail': 'Position update recorded.', 'position_id': pos.position_id})


class PanicResponderActionView(APIView):
    """
    Records supervisor/admin response action (W-02).
    """
    required_capability = 'panic.respond'
    permission_classes = [IsAuthenticated]

    def post(self, request, alert_id):
        action_type = request.data.get('action_type', 'RESPONSE_STARTED')
        description = request.data.get('description')
        reference = request.data.get('reference')

        action = services.record_responder_action(
            panic_alert_id=alert_id,
            responder_user=request.user,
            action_type=action_type,
            description=description,
            reference=reference
        )
        return Response(PanicResponderActionSerializer(action).data, status=status.HTTP_201_CREATED)


class PanicAreYouSafePromptView(APIView):
    """
    Supervisor sends 'Are You Safe?' prompt to guard (FR-9.74).
    """
    required_capability = 'panic.respond'
    permission_classes = [IsAuthenticated]

    def post(self, request, alert_id):
        services.send_are_you_safe_prompt(alert_id, request.user)
        return Response({'detail': 'Are You Safe prompt sent to guard.'})


class PanicAreYouSafeResponseView(APIView):
    """
    Guard responds to 'Are You Safe?' prompt (FR-9.75).
    """
    required_capability = 'panic.trigger'
    permission_classes = [IsAuthenticated]

    def post(self, request, alert_id):
        answer = request.data.get('answer', 'YES')
        explanation = request.data.get('explanation')
        alert = services.respond_are_you_safe(alert_id, request.user, answer, explanation)
        return Response({'detail': 'Safety status recorded.', 'status': alert.alert_status})


class PanicFalseAlarmReportView(APIView):
    """
    Guard reports accidental trigger (M-04).
    Alert remains active until verified by supervisor and admin.
    """
    required_capability = 'panic.trigger'
    permission_classes = [IsAuthenticated]

    def post(self, request, alert_id):
        explanation = request.data.get('explanation')
        are_you_safe = request.data.get('are_you_safe_answer', 'YES')
        report = services.report_false_alarm(alert_id, request.user, explanation, are_you_safe)
        return Response(PanicFalseAlarmReportSerializer(report).data, status=status.HTTP_201_CREATED)


class PanicFalseAlarmConfirmView(APIView):
    """
    Supervisor confirms or rejects false alarm (FR-9.39, AC-9.22).
    """
    required_capability = 'panic.confirm_false_alarm'
    permission_classes = [IsAuthenticated]

    def post(self, request, alert_id):
        decision = request.data.get('decision', 'CONFIRMED')
        notes = request.data.get('notes')
        alert = services.confirm_false_alarm(alert_id, request.user, decision, notes)
        return Response({'detail': f'False alarm {decision}.', 'status': alert.alert_status})


class PanicResolveView(APIView):
    """
    Supervisor submits resolution details (FR-9.79, AC-9.41).
    Awaiting mandatory Admin review before final closure.
    """
    required_capability = 'panic.resolve'
    permission_classes = [IsAuthenticated]

    def post(self, request, alert_id):
        outcome = request.data.get('outcome')
        description = request.data.get('description')
        injury_status = request.data.get('injury_status')
        emergency_services_informed = request.data.get('emergency_services_informed', False)
        emergency_service_ref = request.data.get('emergency_service_ref')
        follow_up_required = request.data.get('follow_up_required', False)

        if not outcome or not description:
            return Response({'detail': 'Outcome and description are required.'}, status=400)

        alert = services.resolve_panic_alert(
            panic_alert_id=alert_id,
            supervisor_user=request.user,
            outcome=outcome,
            description=description,
            injury_status=injury_status,
            emergency_services_informed=emergency_services_informed,
            emergency_service_ref=emergency_service_ref,
            follow_up_required=follow_up_required
        )
        return Response({'detail': 'Resolution submitted. Awaiting Admin review.', 'status': alert.alert_status})


class PanicAdminReviewView(APIView):
    """
    Admin reviews and closes or returns panic alert (W-08, FR-9.81, AC-9.57).
    """
    required_capability = 'panic.admin_review'
    permission_classes = [IsAuthenticated]

    def post(self, request, alert_id):
        decision = request.data.get('decision', 'APPROVE')
        notes = request.data.get('review_notes')

        alert = services.admin_review_panic_alert(alert_id, request.user, decision, notes)
        return Response({'detail': f'Admin review decision: {decision}.', 'status': alert.alert_status})


class PanicWelfareFollowupView(APIView):
    """
    Admin adds administrative welfare follow-up note (FR-9.84).
    """
    required_capability = 'panic.admin_review'
    permission_classes = [IsAuthenticated]

    def post(self, request, alert_id):
        note = request.data.get('note')
        if not note:
            return Response({'detail': 'Note content is required.'}, status=400)

        followup = services.record_welfare_followup(alert_id, request.user, note)
        return Response(PanicWelfareFollowupSerializer(followup).data, status=status.HTTP_201_CREATED)


class PanicTimelineView(APIView):
    """
    Immutable panic timeline history (W-03).
    """
    required_capability = 'panic.view'
    permission_classes = [IsAuthenticated]

    def get(self, request, alert_id):
        timelines = PanicEventTimeline.objects.filter(panic_alert_id=alert_id).order_by('event_time')
        return Response(PanicEventTimelineSerializer(timelines, many=True).data)


class PanicEscalationConfigView(APIView):
    """
    Site / Company escalation timer and delivery route configuration (W-04).
    """
    required_capability = 'panic.config'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company_id = request.user.company_id
        site_id = request.query_params.get('site_id')
        config = PanicEscalationConfig.objects.filter(company_id=company_id, site_id=site_id).first()
        if not config:
            config = PanicEscalationConfig.objects.filter(company_id=company_id, site__isnull=True).first()

        if not config:
            return Response({'detail': 'No configuration found.'}, status=404)
        return Response(PanicEscalationConfigSerializer(config).data)

    def put(self, request):
        company_id = request.user.company_id
        site_id = request.data.get('site_id')

        config, _ = PanicEscalationConfig.objects.update_or_create(
            company_id=company_id,
            site_id=site_id,
            defaults={
                'stage0_timer_seconds': request.data.get('stage0_timer_seconds', 0),
                'stage1_timer_seconds': request.data.get('stage1_timer_seconds', 30),
                'stage2_timer_seconds': request.data.get('stage2_timer_seconds', 60),
                'stage3_timer_seconds': request.data.get('stage3_timer_seconds', 120),
                'stage4_timer_seconds': request.data.get('stage4_timer_seconds', 300),
                'notify_client_immediately': request.data.get('notify_client_immediately', False),
                'enabled_routes': request.data.get('enabled_routes', ['PUSH', 'WEB_CONSOLE', 'SMS']),
                'on_call_contact_name': request.data.get('on_call_contact_name'),
                'on_call_contact_phone': request.data.get('on_call_contact_phone'),
                'emergency_number_to_display': request.data.get('emergency_number_to_display', '112')
            }
        )
        return Response(PanicEscalationConfigSerializer(config).data)


class PanicDeliveryMonitoringView(APIView):
    """
    Delivery route attempts and failure monitoring (W-05).
    """
    required_capability = 'panic.view'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company_id = request.user.company_id
        alert_id = request.query_params.get('alert_id')
        only_failed = request.query_params.get('only_failed', 'false').lower() == 'true'

        qs = PanicDeliveryAttempt.objects.filter(panic_alert__company_id=company_id).select_related('recipient', 'panic_alert')
        if alert_id:
            qs = qs.filter(panic_alert_id=alert_id)
        if only_failed:
            qs = qs.filter(delivery_status='FAILED')

        return Response(PanicDeliveryAttemptSerializer(qs.order_by('-attempted_at')[:100], many=True).data)


class PanicDeviceReadinessView(APIView):
    """
    Device readiness monitoring and testing (W-06, M-07).
    """
    required_capability = 'panic.readiness'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company_id = request.user.company_id
        only_not_ready = request.query_params.get('only_not_ready', 'false').lower() == 'true'

        qs = PanicDeviceReadiness.objects.filter(company_id=company_id).select_related('guard')
        if only_not_ready:
            qs = qs.filter(overall_readiness__in=['NOT_READY', 'UNKNOWN'])

        return Response(PanicDeviceReadinessSerializer(qs.order_by('guard__first_name'), many=True).data)

    def post(self, request):
        guard_id = request.data.get('guard_id')
        readiness = services.update_device_readiness(
            guard_id=guard_id,
            company_id=request.user.company_id,
            device_id=request.data.get('device_id'),
            app_version=request.data.get('app_version', '1.0.0'),
            notification_permission=request.data.get('notification_permission', 'UNKNOWN'),
            battery_optimization=request.data.get('battery_optimization', 'UNKNOWN'),
            location_permission=request.data.get('location_permission', 'UNKNOWN')
        )
        return Response(PanicDeviceReadinessSerializer(readiness).data)


class PanicDrillListCreateView(APIView):
    """
    Controlled test alerts and emergency drills (W-07, FR-9.93 to FR-9.98).
    """
    required_capability = 'panic.drills'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        drills = PanicTestDrill.objects.filter(company_id=request.user.company_id).order_by('-created_at')
        return Response(PanicTestDrillSerializer(drills, many=True).data)

    def post(self, request):
        drill, test_alert = services.create_test_drill(
            company_id=request.user.company_id,
            admin_user=request.user,
            drill_name=request.data.get('drill_name', f"Emergency Drill {datetime.now().strftime('%Y-%m-%d')}"),
            scheduled_at=request.data.get('scheduled_at'),
            selected_recipient_roles=request.data.get('selected_recipient_roles'),
            selected_routes=request.data.get('selected_routes'),
            include_clients=request.data.get('include_clients', False),
            notes=request.data.get('notes')
        )
        return Response({
            'drill': PanicTestDrillSerializer(drill).data,
            'test_alert_number': test_alert.alert_number
        }, status=status.HTTP_201_CREATED)


class PanicCreateIncidentLinkView(APIView):
    """
    Module 8 Integration: Generates formal incident report from panic alert.
    """
    required_capability = 'panic.link_incident'
    permission_classes = [IsAuthenticated]

    def post(self, request, alert_id):
        incident = services.create_incident_from_panic_alert(alert_id, request.user)
        return Response({
            'detail': 'Module 8 incident linked successfully.',
            'incident_id': str(incident.incident_id),
            'case_number': incident.case_number
        })


class ClientSafePanicView(APIView):
    """
    Module 10 Integration: Client-safe panic interface (PRD Section 14.2 C).
    """
    required_capability = 'client.panic_view'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        client_id = user.client_company_id if user.role == 'CLIENT' else request.query_params.get('client_id')
        if not client_id:
            return Response({'detail': 'Client organization context is required.'}, status=400)

        site_ids = request.query_params.getlist('site_ids')
        alerts = services.get_client_safe_panic_status(client_id, site_ids)
        return Response(ClientSafePanicStatusSerializer(alerts, many=True).data)


class PanicMetricsQueryView(APIView):
    """
    Module 13 Integration: Analytics and reporting telemetry (PRD Section 14.2 E).
    """
    required_capability = 'panic.metrics_view'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        metrics = services.get_panic_reporting_metrics(request.user.company_id)
        return Response(metrics)


class PanicReportExportView(APIView):
    """
    Generates structured PDF / CSV evidence export (W-09, FR-9.113, FR-9.114, FR-9.115).
    """
    required_capability = 'panic.view'
    permission_classes = [IsAuthenticated]

    def get(self, request, alert_id):
        alert = PanicAlert.objects.filter(panic_alert_id=alert_id, company_id=request.user.company_id).first()
        if not alert:
            return Response({'detail': 'Panic alert not found.'}, status=404)

        format_type = request.query_params.get('format', 'csv').lower()

        if format_type == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="panic_evidence_{alert.alert_number}.csv"'
            writer = csv.writer(response)

            writer.writerow(['PANIC INCIDENT EVIDENCE REPORT'])
            writer.writerow(['Alert Number', alert.alert_number])
            writer.writerow(['Guard', alert.guard.full_name, alert.guard.employee_code])
            writer.writerow(['Site', alert.site.site_name if alert.site else 'Outside Duty'])
            writer.writerow(['Status', alert.alert_status])
            writer.writerow(['Trigger Time (Server)', alert.trigger_server_time.isoformat()])
            writer.writerow(['Trigger Time (Device)', alert.trigger_device_time.isoformat() if alert.trigger_device_time else 'N/A'])
            writer.writerow([])

            writer.writerow(['POSITION BREADCRUMBS'])
            writer.writerow(['Captured At', 'Latitude', 'Longitude', 'Accuracy (m)', 'Source', 'Validity Status'])
            for p in alert.positions.all():
                writer.writerow([p.captured_at, p.latitude, p.longitude, p.accuracy, p.source, p.validity_status])
            writer.writerow([])

            writer.writerow(['DELIVERY ATTEMPTS'])
            writer.writerow(['Recipient', 'Role', 'Route', 'Attempted At', 'Status', 'Failure Reason'])
            for d in alert.delivery_attempts.all():
                name = d.recipient.user.full_name if d.recipient.user else (d.recipient.contact.contact_name if d.recipient.contact else 'System')
                writer.writerow([name, d.recipient.recipient_role, d.route, d.attempted_at, d.delivery_status, d.failure_reason])
            writer.writerow([])

            writer.writerow(['IMMUTABLE EVENT TIMELINE'])
            writer.writerow(['Event Time', 'Event Type', 'Actor', 'Details'])
            for t in alert.timelines.all().order_by('event_time'):
                actor_name = t.actor.full_name if t.actor else 'System'
                writer.writerow([t.event_time, t.event_type, actor_name, t.event_data.get('description', '')])

            return response

        # HTML / Printable evidence report
        html = f"""
        <html>
        <head><title>Panic Report {alert.alert_number}</title><style>body {{ font-family: sans-serif; padding: 20px; }} table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }} th, td {{ border: 1px solid #ccc; padding: 6px; text-align: left; }}</style></head>
        <body>
            <h2>KARNATAKA SECURITY SERVICES - PANIC INCIDENT EVIDENCE</h2>
            <p><strong>Alert Number:</strong> {alert.alert_number} | <strong>Status:</strong> {alert.alert_status}</p>
            <p><strong>Guard:</strong> {alert.guard.full_name} ({alert.guard.employee_code}) | <strong>Duty:</strong> {alert.duty_status}</p>
            <p><strong>Site:</strong> {alert.site.site_name if alert.site else 'N/A'} | <strong>Time:</strong> {alert.trigger_server_time}</p>
            <h3>Immutable Event Timeline</h3>
            <table>
                <tr><th>Time</th><th>Event</th><th>Actor</th><th>Details</th></tr>
                {''.join([f"<tr><td>{t.event_time}</td><td>{t.event_type}</td><td>{t.actor.full_name if t.actor else 'System'}</td><td>{t.event_data.get('description', '')}</td></tr>" for t in alert.timelines.all().order_by('event_time')])}
            </table>
        </body>
        </html>
        """
        return HttpResponse(html, content_type='text/html')
