import csv
from datetime import datetime, timedelta
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Q, Count, Avg
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError

from foundation.services.scope_service import HasCapabilityAndScope, ScopedQuerySetMixin
from foundation.models import User
from master_data.models import ClientSite, Client
from incident_management.models import (
    IncidentCategory,
    GuardRequestType,
    ResolutionOutcome,
    Incident,
    IncidentAttachment,
    IncidentFollowUpTask,
    IncidentClientVersion,
    GuardRequest,
    ClientTicket,
    ClientTicketMessage
)
from incident_management.serializers import (
    IncidentCategorySerializer,
    GuardRequestTypeSerializer,
    ResolutionOutcomeSerializer,
    IncidentListSerializer,
    IncidentDetailResponseSerializer,
    IncidentAttachmentSerializer,
    IncidentFollowUpTaskSerializer,
    IncidentClientVersionSerializer,
    GuardRequestSerializer,
    ClientTicketSerializer,
    ClientTicketMessageSerializer
)
from incident_management import services


class UnifiedInboxView(APIView):
    """
    Unified Inbox for Admin & Supervisors displaying Incidents,
    Guard Requests, and Client Tickets in one single pane of glass.
    """
    required_capability = 'incidents.inbox_view'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        company_id = user.company_id
        record_type = request.query_params.get('record_type', 'ALL').upper()
        site_id = request.query_params.get('site_id')
        status_param = request.query_params.get('status')
        severity_param = request.query_params.get('severity')
        search_query = request.query_params.get('search')
        is_overdue_only = request.query_params.get('overdue') == 'true'

        incidents_data = []
        requests_data = []
        tickets_data = []

        # 1. Incidents
        if record_type in ('ALL', 'INCIDENT'):
            qs = Incident.objects.filter(company_id=company_id).select_related(
                'current_category', 'site', 'guard', 'supervisor'
            )
            if user.role == 'SUPERVISOR':
                # Site scope restriction
                assigned_sites = user.site_assignments.filter(is_active=True).values_list('site_id', flat=True)
                qs = qs.filter(site_id__in=assigned_sites)
            elif user.role == 'GUARD':
                qs = qs.filter(guard__phone=user.phone)
            elif user.role == 'CLIENT':
                return Response({'detail': 'Clients access shared incidents via Module 10 endpoint.'}, status=403)

            if site_id:
                qs = qs.filter(site_id=site_id)
            if status_param:
                qs = qs.filter(status=status_param)
            if severity_param:
                qs = qs.filter(current_severity=severity_param)
            if search_query:
                qs = qs.filter(Q(case_number__icontains=search_query) | Q(description__icontains=search_query))

            incidents_data = IncidentListSerializer(qs.order_by('-occurred_at')[:50], many=True).data
            if is_overdue_only:
                incidents_data = [i for i in incidents_data if i.get('is_overdue')]

        # 2. Guard Requests
        if record_type in ('ALL', 'REQUEST') and user.role in ('ADMIN', 'SUPER_ADMIN', 'SUPERVISOR', 'GUARD'):
            req_qs = GuardRequest.objects.filter(company_id=company_id).select_related('request_type', 'guard', 'site')
            if user.role == 'SUPERVISOR':
                assigned_sites = user.site_assignments.filter(is_active=True).values_list('site_id', flat=True)
                req_qs = req_qs.filter(site_id__in=assigned_sites)
            elif user.role == 'GUARD':
                req_qs = req_qs.filter(guard__phone=user.phone)

            if site_id:
                req_qs = req_qs.filter(site_id=site_id)
            if status_param:
                req_qs = req_qs.filter(status=status_param)
            if search_query:
                req_qs = req_qs.filter(Q(request_number__icontains=search_query) | Q(description__icontains=search_query))

            requests_data = GuardRequestSerializer(req_qs.order_by('-created_at')[:50], many=True).data

        # 3. Client Tickets
        if record_type in ('ALL', 'TICKET') and user.role in ('ADMIN', 'SUPER_ADMIN', 'SUPERVISOR'):
            tck_qs = ClientTicket.objects.filter(company_id=company_id).select_related('client', 'site', 'named_guard')
            if user.role == 'SUPERVISOR':
                # Supervisors cannot view complaints regarding named guards assigned to Admin only
                assigned_sites = user.site_assignments.filter(is_active=True).values_list('site_id', flat=True)
                tck_qs = tck_qs.filter(site_id__in=assigned_sites, is_admin_only=False)

            if site_id:
                tck_qs = tck_qs.filter(site_id=site_id)
            if status_param:
                tck_qs = tck_qs.filter(status=status_param)
            if search_query:
                tck_qs = tck_qs.filter(Q(ticket_number__icontains=search_query) | Q(title__icontains=search_query))

            tickets_data = ClientTicketSerializer(tck_qs.order_by('-created_at')[:50], many=True, context={'request': request}).data

        return Response({
            'incidents': incidents_data,
            'requests': requests_data,
            'tickets': tickets_data,
            'counts': {
                'incidents': len(incidents_data),
                'requests': len(requests_data),
                'tickets': len(tickets_data)
            }
        })


class IncidentCreateView(APIView):
    """
    Guard incident submission endpoint (Mobile or Web).
    Enforces offline idempotency via client_generated_id.
    """
    required_capability = 'incidents.create'
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        data = request.data

        client_gen_id = data.get('client_generated_id')
        if not client_gen_id:
            return Response({'detail': 'client_generated_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        category_id = data.get('category_id')
        description = data.get('description')
        occurred_at = data.get('occurred_at')
        device_time = data.get('device_time')
        suggested_severity = data.get('suggested_severity', 'MEDIUM')
        site_id = data.get('site_id')
        assignment_id = data.get('assignment_id')
        details_data = data.get('details')
        attachments_metadata = data.get('attachments')

        incident, created = services.create_incident_report(
            company_id=user.company_id,
            guard_user=user,
            client_generated_id=client_gen_id,
            category_id=category_id,
            description=description,
            occurred_at=occurred_at,
            device_time=device_time,
            suggested_severity=suggested_severity,
            site_id=site_id,
            assignment_id=assignment_id,
            details_data=details_data,
            attachments_metadata=attachments_metadata
        )

        serializer = IncidentDetailResponseSerializer(incident)
        return Response({
            'created': created,
            'incident': serializer.data
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class IncidentDetailView(APIView):
    """
    Detailed investigation view of an incident.
    """
    required_capability = 'incidents.view'
    permission_classes = [IsAuthenticated]

    def get(self, request, incident_id):
        user = request.user
        incident = Incident.objects.filter(incident_id=incident_id, company_id=user.company_id).first()
        if not incident:
            return Response({'detail': 'Incident not found.'}, status=status.HTTP_404_NOT_FOUND)

        if user.role == 'CLIENT':
            raise PermissionDenied("Clients cannot view raw incident reports.")

        if user.role == 'SUPERVISOR':
            assigned_sites = user.site_assignments.filter(is_active=True).values_list('site_id', flat=True)
            if incident.site_id not in assigned_sites:
                raise PermissionDenied("Supervisor not authorized for this site.")

        serializer = IncidentDetailResponseSerializer(incident)
        return Response(serializer.data)


class IncidentAddendumCreateView(APIView):
    """
    Allows reporting guard or authorized investigator to append an immutable addendum.
    """
    required_capability = 'incidents.addendum_create'
    permission_classes = [IsAuthenticated]

    def post(self, request, incident_id):
        user = request.user
        content = request.data.get('content')
        client_gen_id = request.data.get('client_generated_id')
        device_time = request.data.get('device_time')

        if not content:
            return Response({'detail': 'Content is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if not client_gen_id:
            return Response({'detail': 'client_generated_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        addendum = services.add_incident_addendum(
            incident_id=incident_id,
            author_user=user,
            content=content,
            client_generated_id=client_gen_id,
            device_time=device_time
        )
        return Response({'detail': 'Addendum appended successfully.'}, status=status.HTTP_201_CREATED)


class IncidentAcknowledgeView(APIView):
    required_capability = 'incidents.acknowledge'
    permission_classes = [IsAuthenticated]

    def post(self, request, incident_id):
        incident = services.acknowledge_incident(incident_id, request.user)
        return Response({'detail': 'Incident acknowledged.', 'case_number': incident.case_number})


class IncidentClassificationUpdateView(APIView):
    required_capability = 'incidents.classify'
    permission_classes = [IsAuthenticated]

    def patch(self, request, incident_id):
        category_id = request.data.get('category_id')
        severity = request.data.get('severity')
        incident = services.update_incident_classification(
            incident_id=incident_id,
            actor_user=request.user,
            new_category_id=category_id,
            new_severity=severity
        )
        return Response({'detail': 'Classification updated.', 'case_number': incident.case_number})


class IncidentEscalateView(APIView):
    required_capability = 'incidents.escalate'
    permission_classes = [IsAuthenticated]

    def post(self, request, incident_id):
        reason = request.data.get('reason')
        if not reason:
            return Response({'detail': 'Escalation reason is required.'}, status=status.HTTP_400_BAD_REQUEST)
        incident = services.escalate_incident(incident_id, request.user, reason)
        return Response({'detail': 'Incident escalated.', 'case_number': incident.case_number})


class IncidentResolveView(APIView):
    required_capability = 'incidents.resolve'
    permission_classes = [IsAuthenticated]

    def post(self, request, incident_id):
        outcome_id = request.data.get('outcome_id')
        note = request.data.get('resolution_note')
        action_taken = request.data.get('action_taken')
        follow_up_due_at = request.data.get('follow_up_due_at')

        incident = services.resolve_incident(
            incident_id=incident_id,
            actor_user=request.user,
            outcome_id=outcome_id,
            resolution_note=note,
            action_taken=action_taken,
            follow_up_due_at=follow_up_due_at
        )
        return Response({'detail': 'Incident resolved successfully.', 'case_number': incident.case_number})


class IncidentCloseView(APIView):
    required_capability = 'incidents.close'
    permission_classes = [IsAuthenticated]

    def post(self, request, incident_id):
        incident = services.close_incident(incident_id, request.user)
        return Response({'detail': 'Incident closed successfully.', 'case_number': incident.case_number})


class IncidentReopenView(APIView):
    required_capability = 'incidents.reopen'
    permission_classes = [IsAuthenticated]

    def post(self, request, incident_id):
        reason = request.data.get('reason')
        incident = services.reopen_incident(incident_id, request.user, reason)
        return Response({'detail': 'Incident reopened.', 'case_number': incident.case_number})


class IncidentRejectView(APIView):
    required_capability = 'incidents.reject'
    permission_classes = [IsAuthenticated]

    def post(self, request, incident_id):
        reason = request.data.get('reason')
        incident = services.reject_incident_as_invalid(incident_id, request.user, reason)
        return Response({'detail': 'Incident marked as invalid.', 'case_number': incident.case_number})


class IncidentLinkView(APIView):
    required_capability = 'incidents.link'
    permission_classes = [IsAuthenticated]

    def post(self, request, incident_id):
        child_id = request.data.get('child_incident_id')
        services.link_related_incidents(incident_id, child_id, request.user)
        return Response({'detail': 'Incidents linked successfully.'})


class IncidentAttachmentVerifyView(APIView):
    required_capability = 'incidents.verify_attachment'
    permission_classes = [IsAuthenticated]

    def post(self, request, attachment_id):
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'detail': 'File object is required.'}, status=status.HTTP_400_BAD_REQUEST)
        file_bytes = file_obj.read()
        attachment = services.verify_attachment_hash(attachment_id, file_bytes)
        return Response({
            'attachment_id': attachment.attachment_id,
            'verification_state': attachment.verification_state,
            'uploaded_hash': attachment.uploaded_hash
        })


class IncidentClientVersionView(APIView):
    """
    Supervisor / Admin creates or updates an approved client-shared version.
    """
    required_capability = 'incidents.client_version'
    permission_classes = [IsAuthenticated]

    def post(self, request, incident_id):
        data = request.data
        title = data.get('title')
        summary = data.get('summary')
        actions_taken = data.get('actions_taken')
        client_status = data.get('status', 'UNDER_REVIEW')
        selected_attachments = data.get('selected_attachment_ids', [])

        if not summary:
            return Response({'detail': 'Approved summary is required.'}, status=status.HTTP_400_BAD_REQUEST)

        version = services.create_or_update_client_shared_version(
            incident_id=incident_id,
            actor_user=request.user,
            title=title,
            summary=summary,
            actions_taken=actions_taken,
            status=client_status,
            selected_attachment_ids=selected_attachments
        )
        return Response(IncidentClientVersionSerializer(version).data, status=status.HTTP_201_CREATED)


class IncidentFollowUpTaskView(APIView):
    required_capability = 'incidents.followup_task'
    permission_classes = [IsAuthenticated]

    def post(self, request, incident_id):
        incident = Incident.objects.filter(incident_id=incident_id).first()
        if not incident:
            return Response({'detail': 'Incident not found.'}, status=404)

        assigned_to_id = request.data.get('assigned_to')
        description = request.data.get('description')
        due_at = request.data.get('due_at')

        task = IncidentFollowUpTask.objects.create(
            incident=incident,
            company_id=incident.company_id,
            assigned_to_id=assigned_to_id,
            created_by=request.user,
            description=description,
            due_at=due_at
        )
        return Response(IncidentFollowUpTaskSerializer(task).data, status=201)


# ------------------------------------------------------------------------------
# Guard Requests
# ------------------------------------------------------------------------------

class GuardRequestListCreateView(APIView):
    required_capability = 'guard_requests.manage'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        qs = GuardRequest.objects.filter(company_id=user.company_id).select_related('request_type', 'guard', 'site')
        if user.role == 'GUARD':
            qs = qs.filter(guard__phone=user.phone)
        elif user.role == 'SUPERVISOR':
            assigned_sites = user.site_assignments.filter(is_active=True).values_list('site_id', flat=True)
            qs = qs.filter(site_id__in=assigned_sites)
        return Response(GuardRequestSerializer(qs.order_by('-created_at'), many=True).data)

    def post(self, request):
        user = request.user
        data = request.data
        client_gen_id = data.get('client_generated_id')
        req_type_id = data.get('request_type_id')
        desc = data.get('description')
        site_id = data.get('site_id')

        req_obj, created = services.create_guard_request(
            company_id=user.company_id,
            guard_user=user,
            client_generated_id=client_gen_id,
            request_type_id=req_type_id,
            description=desc,
            site_id=site_id
        )
        return Response(GuardRequestSerializer(req_obj).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class GuardRequestActionView(APIView):
    required_capability = 'guard_requests.action'
    permission_classes = [IsAuthenticated]

    def post(self, request, request_id):
        action = request.data.get('action')
        note = request.data.get('note')

        if action in ('APPROVE', 'APPROVED'):
            req_obj = services.update_guard_request_status(request_id, request.user, 'APPROVED')
        elif action in ('REJECT', 'REJECTED'):
            req_obj = services.update_guard_request_status(request_id, request.user, 'REJECTED', reason_or_note=note)
        elif action in ('FULFILL', 'FULFILLED'):
            req_obj = services.update_guard_request_status(request_id, request.user, 'FULFILLED', reason_or_note=note)
        elif action == 'REPLY':
            reply = services.reply_to_guard_request(request_id, request.user, note)
            return Response({'detail': 'Reply posted.'})
        else:
            return Response({'detail': 'Invalid action.'}, status=400)

        return Response(GuardRequestSerializer(req_obj).data)


# ------------------------------------------------------------------------------
# Client Tickets
# ------------------------------------------------------------------------------

class ClientTicketListCreateView(APIView):
    required_capability = 'client_tickets.manage'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        qs = ClientTicket.objects.filter(company_id=user.company_id).select_related('client', 'site')
        if user.role == 'CLIENT':
            # Retrieve client ID from user profile
            qs = qs.filter(client_id=user.client_company_id)
        elif user.role == 'SUPERVISOR':
            assigned_sites = user.site_assignments.filter(is_active=True).values_list('site_id', flat=True)
            qs = qs.filter(site_id__in=assigned_sites, is_admin_only=False)

        return Response(ClientTicketSerializer(qs.order_by('-created_at'), many=True, context={'request': request}).data)

    def post(self, request):
        user = request.user
        data = request.data
        client_gen_id = data.get('client_generated_id')
        site_id = data.get('site_id')
        ticket_type = data.get('ticket_type', 'QUERY')
        title = data.get('title')
        desc = data.get('description')
        named_guard_id = data.get('named_guard_id')

        ticket, created = services.create_client_ticket(
            company_id=user.company_id,
            client_user=user,
            client_generated_id=client_gen_id,
            site_id=site_id,
            ticket_type=ticket_type,
            title=title,
            description=desc,
            named_guard_id=named_guard_id
        )
        return Response(ClientTicketSerializer(ticket, context={'request': request}).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class ClientTicketMessageView(APIView):
    required_capability = 'client_tickets.message'
    permission_classes = [IsAuthenticated]

    def post(self, request, ticket_id):
        msg = request.data.get('message')
        visibility = request.data.get('visibility', 'CLIENT_VISIBLE')
        if request.user.role == 'CLIENT':
            visibility = 'CLIENT_VISIBLE'
        reply = services.reply_to_client_ticket(ticket_id, request.user, msg, visibility)
        return Response({'detail': 'Message sent.'})


# ------------------------------------------------------------------------------
# Taxonomies & Reporting
# ------------------------------------------------------------------------------

class CategoryListView(APIView):
    required_capability = 'incidents.categories_view'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cats = IncidentCategory.objects.filter(company_id=request.user.company_id, active=True).order_by('name')
        return Response(IncidentCategorySerializer(cats, many=True).data)


class RequestTypeListView(APIView):
    required_capability = 'guard_requests.types_view'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        types = GuardRequestType.objects.filter(company_id=request.user.company_id, active=True).order_by('name')
        return Response(GuardRequestTypeSerializer(types, many=True).data)


class ResolutionOutcomeListView(APIView):
    required_capability = 'incidents.outcomes_view'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        outcomes = ResolutionOutcome.objects.filter(company_id=request.user.company_id, active=True).order_by('name')
        return Response(ResolutionOutcomeSerializer(outcomes, many=True).data)


class AgingDashboardView(APIView):
    """
    Shows real aging & overdue statistics without fabricated metrics.
    """
    required_capability = 'incidents.aging_view'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company_id = request.user.company_id
        now = timezone.now()

        # Unacknowledged incidents older than 30 mins
        overdue_incidents = Incident.objects.filter(
            company_id=company_id,
            status='REPORTED',
            submitted_at__lt=now - timedelta(minutes=30)
        ).count()

        # Unresolved incidents older than 24 hours
        stale_investigations = Incident.objects.filter(
            company_id=company_id,
            status__in=['ACKNOWLEDGED', 'IN_PROGRESS', 'ESCALATED'],
            created_at__lt=now - timedelta(hours=24)
        ).count()

        # Overdue guard requests
        overdue_requests = GuardRequest.objects.filter(
            company_id=company_id,
            status='SUBMITTED',
            response_due_at__lt=now
        ).count()

        # Overdue client tickets
        overdue_tickets = ClientTicket.objects.filter(
            company_id=company_id,
            status__in=['OPEN', 'IN_PROGRESS'],
            resolution_due_at__lt=now
        ).count()

        return Response({
            'overdue_incidents_count': overdue_incidents,
            'stale_investigations_count': stale_investigations,
            'overdue_requests_count': overdue_requests,
            'overdue_tickets_count': overdue_tickets,
            'timestamp': now.isoformat()
        })


class ExportCSVMetadataView(APIView):
    required_capability = 'incidents.export'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="incidents_metadata_{datetime.now().strftime("%Y%m%d")}.csv"'
        writer = csv.writer(response)
        writer.writerow(['Case Number', 'Site', 'Guard', 'Category', 'Severity', 'Status', 'Occurred At', 'Submitted At'])

        qs = Incident.objects.filter(company_id=request.user.company_id).select_related('site', 'guard', 'current_category')
        for inc in qs:
            writer.writerow([
                inc.case_number,
                inc.site.site_name,
                inc.guard.full_name,
                inc.current_category.name,
                inc.current_severity,
                inc.status,
                inc.occurred_at.isoformat(),
                inc.submitted_at.isoformat()
            ])
        return response


# ------------------------------------------------------------------------------
# Inter-Module Interfaces (Module 9 Panic, Module 10 Client, Module 13 Metrics)
# ------------------------------------------------------------------------------

class PanicIncidentIntakeView(APIView):
    """
    Module 9 Interface: Creates incident from Panic Button trigger.
    """
    required_capability = 'panic.intake'
    permission_classes = [IsAuthenticated]

    def post(self, request):
        panic_id = request.data.get('panic_event_id')
        guard_id = request.data.get('guard_id')
        site_id = request.data.get('site_id')
        assignment_id = request.data.get('assignment_id')

        incident = services.create_incident_from_panic(
            panic_event_id=panic_id,
            guard_id=guard_id,
            site_id=site_id,
            assignment_id=assignment_id
        )
        return Response({
            'incident_id': incident.incident_id,
            'case_number': incident.case_number,
            'status': incident.status
        }, status=status.HTTP_201_CREATED)


class ClientSharedIncidentsView(APIView):
    """
    Module 10 Interface: Returns approved client-safe incident versions.
    """
    required_capability = 'client.incidents_view'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        qs = IncidentClientVersion.objects.filter(
            company_id=user.company_id,
            sharing_state='SHARED'
        ).select_related('site')

        if user.role == 'CLIENT' and user.client_company_id:
            qs = qs.filter(client_id=user.client_company_id)

        site_id = request.query_params.get('site_id')
        if site_id:
            qs = qs.filter(site_id=site_id)

        return Response(IncidentClientVersionSerializer(qs.order_by('-occurred_at'), many=True).data)


class IncidentMetricsQueryView(APIView):
    """
    Module 13 Interface: Analytical telemetry query.
    """
    required_capability = 'incidents.metrics_view'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company_id = request.user.company_id
        by_cat = Incident.objects.filter(company_id=company_id).values('current_category__name').annotate(count=Count('incident_id'))
        by_sev = Incident.objects.filter(company_id=company_id).values('current_severity').annotate(count=Count('incident_id'))
        by_status = Incident.objects.filter(company_id=company_id).values('status').annotate(count=Count('incident_id'))

        return Response({
            'total_incidents': Incident.objects.filter(company_id=company_id).count(),
            'by_category': list(by_cat),
            'by_severity': list(by_sev),
            'by_status': list(by_status)
        })
