from datetime import datetime, date
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound

from foundation.services.scope_service import HasCapabilityAndScope
from foundation.models import User
from master_data.models import Client, ClientSite
from incident_management.models import ClientTicket, ClientTicketMessage
from client_portal.models import (
    ClientUserSiteAccess,
    ClientPortalConfiguration,
    ClientNotificationPreference,
    ClientAnnouncement
)
from client_portal.serializers import (
    ClientUserSiteAccessSerializer,
    ClientPortalConfigurationSerializer,
    ClientNotificationPreferenceSerializer,
    ClientAnnouncementSerializer
)
from client_portal import services


class ClientDashboardView(APIView):
    """
    Main dashboard overview for client portal (FR-10.25 to FR-10.41, AC-10.11 to AC-10.13).
    """
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'client_portal.view'

    def get(self, request):
        data = services.build_client_dashboard(request.user)
        services.log_usage_event(request.user.company_id, request.user.user_id, 'LOGIN')
        return Response(data, status=status.HTTP_200_OK)


class ClientSitesListView(APIView):
    """
    Permitted sites list and site switcher for the client (FR-10.36, AC-10.5).
    """
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'client_portal.view'

    def get(self, request):
        sites = services.get_client_permitted_sites(request.user)
        results = []
        for s in sites:
            results.append({
                'site_id': str(s.site_id),
                'site_name': s.site_name,
                'site_code': s.site_code,
                'status': s.operational_status,
                'address': s.address_line1 or '',
                'city': s.city or '',
            })
        return Response(results, status=status.HTTP_200_OK)


class ClientDeploymentView(APIView):
    """
    Current and next-shift deployment for a specific permitted site (FR-10.42 to FR-10.57).
    """
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'client_portal.view'

    def get(self, request):
        site_id = request.query_params.get('site_id')
        if not site_id:
            permitted = services.get_client_permitted_sites(request.user).first()
            if not permitted:
                return Response({'detail': 'No permitted sites found.'}, status=status.HTTP_404_NOT_FOUND)
            site_id = permitted.site_id

        data = services.get_site_deployment(request.user, site_id)
        return Response(data, status=status.HTTP_200_OK)


class ClientGuardSafeCardView(APIView):
    """
    Client-safe guard card (FR-10.43, AC-10.21).
    Strictly sanitized: No phone, no coordinates, no battery/device info.
    """
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'client_portal.view'

    def get(self, request, guard_id):
        card = services.get_client_safe_guard_card(request.user, guard_id)
        return Response(card, status=status.HTTP_200_OK)


class ClientReportPostIssueView(APIView):
    """
    Report an issue with a post or guard (FR-10.61 to FR-10.63).
    Complaints about a named guard route to Admin only.
    """
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'client_portal.raise_ticket'

    def post(self, request):
        site_id = request.data.get('site_id')
        if not site_id:
            raise ValidationError("site_id is required.")

        category = request.data.get('category', 'OBSERVED_ISSUE')
        description = request.data.get('description')
        if not description:
            raise ValidationError("description is required.")

        shift_id = request.data.get('shift_id')
        named_guard_id = request.data.get('named_guard_id')
        attachment_ref = request.data.get('attachment_ref')

        ticket = services.report_post_issue(
            user=request.user,
            site_id=site_id,
            shift_id=shift_id,
            category=category,
            description=description,
            named_guard_id=named_guard_id,
            attachment_ref=attachment_ref
        )

        return Response({
            'message': 'Post issue reported successfully.',
            'ticket_id': str(ticket.ticket_id),
            'ticket_number': ticket.ticket_number,
            'is_admin_only': ticket.is_admin_only,
            'status': ticket.status
        }, status=status.HTTP_201_CREATED)


class ClientAttendanceTodayView(APIView):
    """
    Today So Far provisional attendance view (FR-10.64 to FR-10.67, AC-10.22).
    Labeled explicitly: 'Not Yet Approved', provisional = True.
    """
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'client_portal.view'

    def get(self, request):
        site_id = request.query_params.get('site_id')
        data = services.get_today_so_far_attendance(request.user, site_id)
        return Response(data, status=status.HTTP_200_OK)


class ClientAttendanceApprovedView(APIView):
    """
    Approved attendance records grouped by day and site (FR-10.68 to FR-10.73, AC-10.23 to AC-10.25).
    """
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'client_portal.view'

    def get(self, request):
        site_id = request.query_params.get('site_id')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        data = services.get_approved_attendance(request.user, site_id, start_date, end_date)
        return Response(data, status=status.HTTP_200_OK)


class ClientAttendanceMonthlyDownloadView(APIView):
    """
    Download monthly attendance CSV for LOCKED periods only (FR-10.74, AC-10.26 to AC-10.28).
    Logs download through Module 1.
    """
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'client_portal.download_document'

    def get(self, request):
        site_id = request.query_params.get('site_id')
        month = request.query_params.get('month')
        year = request.query_params.get('year')

        if not site_id or not month or not year:
            raise ValidationError("site_id, month, and year are required parameters.")

        try:
            month = int(month)
            year = int(year)
        except ValueError:
            raise ValidationError("month and year must be integers.")

        csv_data, filename = services.download_monthly_attendance_sheet(
            user=request.user,
            site_id=site_id,
            month=month,
            year=year,
            file_format='csv'
        )

        response = HttpResponse(csv_data, content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class ClientAttendanceQueryView(APIView):
    """
    Raise query on an attendance line, creating a Module 8 ticket (FR-10.77, FR-10.78, AC-10.31).
    """
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'client_portal.raise_ticket'

    def post(self, request):
        attendance_record_id = request.data.get('attendance_record_id')
        site_id = request.data.get('site_id')
        reason = request.data.get('reason')
        attachment_ref = request.data.get('attachment_ref')

        if not attendance_record_id or not site_id or not reason:
            raise ValidationError("attendance_record_id, site_id, and reason are required.")

        ticket = services.create_attendance_query(
            user=request.user,
            attendance_record_id=attendance_record_id,
            site_id=site_id,
            reason=reason,
            attachment_ref=attachment_ref
        )

        return Response({
            'message': 'Attendance query submitted successfully.',
            'ticket_id': str(ticket.ticket_id),
            'ticket_number': ticket.ticket_number,
            'status': ticket.status
        }, status=status.HTTP_201_CREATED)


class ClientSharedIncidentsListView(APIView):
    """
    Client-shared approved incidents list (FR-10.83 to FR-10.90, AC-10.33 to AC-10.36).
    """
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'client_portal.view'

    def get(self, request):
        site_id = request.query_params.get('site_id')
        status_filter = request.query_params.get('status')
        data = services.get_client_shared_incidents(request.user, site_id, status_filter)
        return Response(data, status=status.HTTP_200_OK)


class ClientSharedIncidentCommentView(APIView):
    """
    Comment on a shared incident (FR-10.91, FR-10.92, AC-10.37).
    """
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'client_portal.raise_ticket'

    def post(self, request, version_id):
        comment = request.data.get('comment')
        if not comment:
            raise ValidationError("Comment text is required.")

        result = services.add_client_incident_comment(request.user, version_id, comment)
        return Response(result, status=status.HTTP_201_CREATED)


class ClientPanicStatusView(APIView):
    """
    Client-safe emergency status (FR-10.93 to FR-10.104, AC-10.38, AC-10.39, AC-10.43).
    """
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'client_portal.view'

    def get(self, request):
        panic_id = request.query_params.get('panic_alert_id')
        status_data = services.get_client_safe_panic_status(request.user, panic_id)
        if not status_data:
            return Response({'active_panic': False, 'message': 'No active emergency at your sites.'}, status=status.HTTP_200_OK)
        return Response({'active_panic': True, **status_data}, status=status.HTTP_200_OK)


class ClientPanicAcknowledgeView(APIView):
    """
    Acknowledge emergency notice through Module 9 interface (FR-10.102, AC-10.40).
    """
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'client_portal.view'

    def post(self, request, panic_id):
        result = services.acknowledge_panic_alert(request.user, panic_id)
        return Response(result, status=status.HTTP_200_OK)


class ClientDocumentsListView(APIView):
    """
    Approved documents list (FR-10.123 to FR-10.130, AC-10.50, AC-10.52).
    """
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'client_portal.view'

    def get(self, request):
        docs = services.get_client_documents(request.user)
        return Response(docs, status=status.HTTP_200_OK)


class ClientInvoicesListView(APIView):
    """
    Invoices list controlled by configuration flag until Module 11 is available (FR-10.105 to FR-10.115, AC-10.44).
    """
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'client_portal.view'

    def get(self, request):
        client_id = request.user.client_company_id if request.user.role == 'CLIENT' else None
        config = services.get_or_create_portal_config(request.user.company_id, client_id) if client_id else None

        if not config or not config.invoices_enabled:
            return Response({
                'status': 'NOT_AVAILABLE_YET',
                'message': 'Invoices will be available once the Billing & Invoicing module (Module 11) is activated.',
                'invoices': []
            }, status=status.HTTP_200_OK)

        # When enabled, return issued invoices from Module 11
        from billing_invoices.models import ClientInvoice
        from billing_invoices.serializers import ClientInvoiceListSerializer

        qs = ClientInvoice.objects.filter(
            company_id=request.user.company_id,
            client_id=client_id,
            status__in=['SENT', 'PARTIALLY_PAID', 'PAID', 'CANCELLED']
        ).order_by('-invoice_date')

        return Response({
            'status': 'ENABLED',
            'invoices': ClientInvoiceListSerializer(qs, many=True).data
        }, status=status.HTTP_200_OK)


class ClientTicketsListView(APIView):
    """
    Client tickets list and creation (FR-10.131 to FR-10.138, AC-10.53 to AC-10.57).
    """
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'client_portal.view'

    def get(self, request):
        permitted_sites = services.get_client_permitted_sites(request.user)
        client_id = request.user.client_company_id if request.user.role == 'CLIENT' else None

        qs = ClientTicket.objects.filter(
            company_id=request.user.company_id,
            site__in=permitted_sites
        )
        if client_id:
            qs = qs.filter(client_id=client_id)

        results = []
        for t in qs.order_by('-created_at')[:50]:
            results.append({
                'ticket_id': str(t.ticket_id),
                'ticket_number': t.ticket_number,
                'site_id': str(t.site_id),
                'site_name': t.site.site_name,
                'ticket_type': t.ticket_type,
                'title': t.title,
                'description': t.description,
                'status': t.status,
                'created_at': t.created_at.isoformat(),
                'resolved_at': t.resolved_at.isoformat() if t.resolved_at else None,
            })
        return Response(results, status=status.HTTP_200_OK)

    def post(self, request):
        site_id = request.data.get('site_id')
        title = request.data.get('title')
        description = request.data.get('description')
        ticket_type = request.data.get('ticket_type', 'QUERY')

        if not site_id or not title or not description:
            raise ValidationError("site_id, title, and description are required.")

        services.validate_client_site_access(request.user, site_id)
        client = Client.objects.get(client_id=request.user.client_company_id)
        site = ClientSite.objects.get(site_id=site_id)

        ticket_num = f"TICK-{timezone.now().year}-{str(services.uuid.uuid4())[:6].upper()}"
        ticket = ClientTicket.objects.create(
            company_id=request.user.company_id,
            ticket_number=ticket_num,
            client_generated_id=services.uuid.uuid4(),
            client=client,
            site=site,
            ticket_type=ticket_type,
            title=title,
            description=description,
            status='OPEN'
        )

        ClientTicketMessage.objects.create(
            ticket=ticket,
            company_id=request.user.company_id,
            actor=request.user,
            message=description,
            visibility='CLIENT_VISIBLE'
        )

        services.log_usage_event(request.user.company_id, request.user.user_id, 'TICKET_RAISED', related_record_id=ticket.ticket_id)

        return Response({
            'message': 'Ticket created successfully.',
            'ticket_id': str(ticket.ticket_id),
            'ticket_number': ticket.ticket_number,
            'status': ticket.status
        }, status=status.HTTP_201_CREATED)


class ClientTicketDetailView(APIView):
    """
    Client ticket conversation thread (FR-10.133, FR-10.137, AC-10.54, AC-10.55).
    INTERNAL notes are strictly filtered out!
    """
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'client_portal.view'

    def get(self, request, ticket_id):
        ticket = ClientTicket.objects.filter(ticket_id=ticket_id, company_id=request.user.company_id).first()
        if not ticket:
            raise NotFound("Ticket not found.")

        services.validate_client_site_access(request.user, ticket.site_id)

        # Internal notes are strictly excluded (FR-10.137, AC-10.54)
        messages = ClientTicketMessage.objects.filter(
            ticket=ticket,
            visibility='CLIENT_VISIBLE'
        ).order_by('created_at')

        msg_list = []
        for m in messages:
            msg_list.append({
                'message_id': str(m.message_id),
                'actor_id': str(m.actor_id),
                'actor_name': m.actor.full_name,
                'is_client_actor': m.actor.role == 'CLIENT',
                'message': m.message,
                'attachment_reference': m.attachment_reference,
                'created_at': m.created_at.isoformat(),
            })

        return Response({
            'ticket_id': str(ticket.ticket_id),
            'ticket_number': ticket.ticket_number,
            'site_id': str(ticket.site_id),
            'site_name': ticket.site.site_name,
            'ticket_type': ticket.ticket_type,
            'title': ticket.title,
            'description': ticket.description,
            'status': ticket.status,
            'created_at': ticket.created_at.isoformat(),
            'messages': msg_list
        }, status=status.HTTP_200_OK)

    def post(self, request, ticket_id):
        ticket = ClientTicket.objects.filter(ticket_id=ticket_id, company_id=request.user.company_id).first()
        if not ticket:
            raise NotFound("Ticket not found.")

        services.validate_client_site_access(request.user, ticket.site_id)

        action = request.data.get('action', 'reply')
        if action == 'reopen':
            # Check reopening window (FR-10.136, AC-10.57)
            if ticket.status not in ['RESOLVED', 'CLOSED']:
                raise ValidationError("Only resolved or closed tickets can be reopened.")
            ticket.status = 'REOPENED'
            ticket.reopened_count += 1
            ticket.reopened_at = timezone.now()
            ticket.reopen_reason = request.data.get('reason', 'Reopened by client')
            ticket.save()

            ClientTicketMessage.objects.create(
                ticket=ticket,
                company_id=request.user.company_id,
                actor=request.user,
                message=f"[Ticket Reopened] Reason: {ticket.reopen_reason}",
                visibility='CLIENT_VISIBLE'
            )
            return Response({'status': ticket.status, 'message': 'Ticket reopened successfully.'}, status=status.HTTP_200_OK)

        message_text = request.data.get('message')
        if not message_text:
            raise ValidationError("message is required.")

        attachment_ref = request.data.get('attachment_reference')

        msg = ClientTicketMessage.objects.create(
            ticket=ticket,
            company_id=request.user.company_id,
            actor=request.user,
            message=message_text,
            visibility='CLIENT_VISIBLE',
            attachment_reference=attachment_ref
        )

        return Response({
            'message_id': str(msg.message_id),
            'message': msg.message,
            'created_at': msg.created_at.isoformat()
        }, status=status.HTTP_201_CREATED)


class ClientAgencyContactView(APIView):
    """
    Agency official contact information (FR-10.139 to FR-10.143).
    """
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'client_portal.view'

    def get(self, request):
        company = request.user.company
        return Response({
            'agency_name': company.legal_name,
            'control_room_phone': '+91 80 2555 0100',
            'emergency_helpline': '112',
            'support_email': company.email or 'support@securityagency.local',
            'office_hours': 'Monday to Saturday: 09:00 AM - 07:00 PM IST (Control Room: 24/7)',
            'address': f"{company.address_line1 or ''}, {company.city or ''}, {company.state_code or ''}",
        }, status=status.HTTP_200_OK)


class ClientNotificationPreferencesView(APIView):
    """
    Manage client notification preferences (FR-10.144 to FR-10.150, AC-10.58 to AC-10.60).
    Panic notifications CANNOT be disabled.
    """
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'client_portal.view'

    def get(self, request):
        prefs = ClientNotificationPreference.objects.filter(client_user=request.user)
        categories = ['DEPLOYMENT', 'ATTENDANCE', 'INCIDENT', 'BILLING', 'TICKET', 'GENERAL', 'ANNOUNCEMENT']
        results = []
        for cat in categories:
            pref = prefs.filter(notification_category=cat).first()
            results.append({
                'notification_category': cat,
                'enabled': pref.enabled if pref else True,
                'quiet_hours_start': pref.quiet_hours_start.strftime('%H:%M') if pref and pref.quiet_hours_start else None,
                'quiet_hours_end': pref.quiet_hours_end.strftime('%H:%M') if pref and pref.quiet_hours_end else None,
                'can_be_disabled': cat != 'PANIC',
            })
        return Response(results, status=status.HTTP_200_OK)

    def put(self, request):
        updates = request.data.get('preferences', [])
        for item in updates:
            cat = item.get('notification_category')
            if not cat:
                continue
            if cat == 'PANIC' and item.get('enabled') is False:
                continue # Cannot disable panic notices (FR-10.146)

            ClientNotificationPreference.objects.update_or_create(
                company_id=request.user.company_id,
                client_user=request.user,
                notification_category=cat,
                defaults={
                    'enabled': item.get('enabled', True),
                    'quiet_hours_start': item.get('quiet_hours_start') or None,
                    'quiet_hours_end': item.get('quiet_hours_end') or None,
                }
            )
        return Response({'message': 'Preferences updated successfully.'}, status=status.HTTP_200_OK)


# ==============================================================================
# Admin Portal Management & Preview Views
# ==============================================================================

class AdminClientUsersListView(APIView):
    """
    Admin views client users, linked organization, last login, and permitted sites (FR-10.151 to FR-10.153).
    """
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'client_portal.configure'

    def get(self, request):
        users = User.objects.filter(company_id=request.user.company_id, role='CLIENT').order_by('full_name')
        results = []
        for u in users:
            client_org = Client.objects.filter(client_id=u.client_company_id).first() if u.client_company_id else None
            restrictions = ClientUserSiteAccess.objects.filter(client_user=u, is_active=True)
            mode = restrictions.first().access_mode if restrictions.exists() else 'ALL_SITES'
            selected_site_names = list(restrictions.filter(access_mode='SELECTED_SITES', site__isnull=False).values_list('site__site_name', flat=True))

            results.append({
                'user_id': str(u.user_id),
                'full_name': u.full_name,
                'email': u.email,
                'status': u.status,
                'client_company_id': str(u.client_company_id) if u.client_company_id else None,
                'client_company_name': (client_org.client_name if client_org else 'Unlinked'),
                'last_login_at': u.last_login_at.isoformat() if u.last_login_at else None,
                'access_mode': mode,
                'permitted_sites_count': len(selected_site_names) if mode == 'SELECTED_SITES' else 'All Company Sites',
                'selected_sites': selected_site_names
            })
        return Response(results, status=status.HTTP_200_OK)


class AdminClientSiteAccessConfigView(APIView):
    """
    Admin configures site access restrictions for a client user (FR-10.154, AC-10.66).
    """
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'client_portal.configure'

    def get(self, request, user_id):
        target_user = User.objects.filter(user_id=user_id, role='CLIENT').first()
        if not target_user:
            raise NotFound("Client user not found.")

        sites = ClientSite.objects.filter(client_id=target_user.client_company_id)
        restrictions = ClientUserSiteAccess.objects.filter(client_user=target_user, is_active=True)
        mode = restrictions.first().access_mode if restrictions.exists() else 'ALL_SITES'
        selected_ids = list(restrictions.filter(access_mode='SELECTED_SITES').values_list('site_id', flat=True))

        return Response({
            'user_id': str(target_user.user_id),
            'full_name': target_user.full_name,
            'access_mode': mode,
            'selected_site_ids': [str(s) for s in selected_ids if s],
            'available_sites': [
                {'site_id': str(s.site_id), 'site_name': s.site_name, 'site_code': s.site_code}
                for s in sites
            ]
        }, status=status.HTTP_200_OK)

    def post(self, request, user_id):
        target_user = User.objects.filter(user_id=user_id, role='CLIENT').first()
        if not target_user:
            raise NotFound("Client user not found.")

        access_mode = request.data.get('access_mode', 'ALL_SITES')
        site_ids = request.data.get('site_ids', [])

        # Reset active restrictions for user
        ClientUserSiteAccess.objects.filter(client_user=target_user).delete()

        if access_mode == 'ALL_SITES':
            ClientUserSiteAccess.objects.create(
                company_id=request.user.company_id,
                client_user=target_user,
                access_mode='ALL_SITES',
                site=None,
                is_active=True,
                created_by=request.user
            )
        else:
            for s_id in site_ids:
                site = ClientSite.objects.filter(site_id=s_id, client_id=target_user.client_company_id).first()
                if site:
                    ClientUserSiteAccess.objects.create(
                        company_id=request.user.company_id,
                        client_user=target_user,
                        access_mode='SELECTED_SITES',
                        site=site,
                        is_active=True,
                        created_by=request.user
                    )

        return Response({'message': 'Site access configuration saved successfully.'}, status=status.HTTP_200_OK)


class AdminClientPortalConfigView(APIView):
    """
    Admin configures portal visibility per client organization (FR-10.157 to FR-10.161).
    """
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'client_portal.configure'

    def get(self, request):
        client_id = request.query_params.get('client_id')
        if not client_id:
            clients = Client.objects.filter(company_id=request.user.company_id)
            client_id = clients.first().client_id if clients.exists() else None

        if not client_id:
            return Response({'detail': 'No client organization available.'}, status=status.HTTP_404_NOT_FOUND)

        config = services.get_or_create_portal_config(request.user.company_id, client_id)
        serializer = ClientPortalConfigurationSerializer(config)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request):
        client_id = request.data.get('client_id')
        if not client_id:
            raise ValidationError("client_id is required.")

        config = services.get_or_create_portal_config(request.user.company_id, client_id)
        serializer = ClientPortalConfigurationSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)

        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminClientPreviewView(APIView):
    """
    Admin previews portal as selected client user without password (FR-10.155, AC-10.64, AC-10.65).
    """
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'client_portal.preview'

    def get(self, request):
        client_user_id = request.query_params.get('client_user_id')
        if not client_user_id:
            raise ValidationError("client_user_id parameter is required.")

        preview_data = services.admin_client_preview(request.user, client_user_id)
        return Response(preview_data, status=status.HTTP_200_OK)


class AdminPortalUsageView(APIView):
    """
    Real portal usage counts and metrics (FR-10.162, FR-10.163, AC-10.67).
    No fabricated statistics.
    """
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'client_portal.configure'

    def get(self, request):
        days = int(request.query_params.get('days', 30))
        metrics = services.get_real_portal_usage_metrics(request.user.company_id, days)
        return Response(metrics, status=status.HTTP_200_OK)


class AdminAnnouncementsView(APIView):
    """
    Admin manages announcements targeting clients (FR-10.166 to FR-10.169).
    """
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'client_portal.configure'

    def get(self, request):
        announcements = ClientAnnouncement.objects.filter(company_id=request.user.company_id)
        serializer = ClientAnnouncementSerializer(announcements, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = ClientAnnouncementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(company=request.user.company, created_by=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
