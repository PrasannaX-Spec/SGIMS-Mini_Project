from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError, PermissionDenied, NotFound

from master_data.models import (
    Company, Client, ClientContact, ClientSite, SiteGeofence,
    SiteSupervisorAssignment, PostType, ShiftTemplate, SiteShift,
    SiteManpowerRequirement, ServiceAgreement, ClientBillingRate
)
from master_data.serializers import (
    CompanySerializer, ClientSerializer, ClientContactSerializer,
    ClientSiteSerializer, SiteGeofenceSerializer, SiteSupervisorAssignmentSerializer,
    PostTypeSerializer, ShiftTemplateSerializer, SiteShiftSerializer,
    SiteManpowerRequirementSerializer, ServiceAgreementSerializer,
    ClientBillingRateSerializer
)
from master_data import services
from foundation.services.scope_service import HasCapabilityAndScope, ScopedQuerySetMixin
from foundation.models import User


# ==============================================================================
# 1. COMPANY PROFILE
# ==============================================================================

class CompanyProfileView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'master_data.manage'

    def get(self, request):
        company = services.get_company_profile(request.user.company_id)
        return Response(CompanySerializer(company).data)

    def put(self, request):
        company = services.update_company_profile(
            request.user.company_id, request.data, request.user, request=request
        )
        return Response(CompanySerializer(company).data)


# ==============================================================================
# 2. CLIENTS
# ==============================================================================

class ClientListView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'master_data.view_client'

    def get(self, request):
        user = request.user
        qs = Client.objects.filter(company_id=user.company_id)

        # Scoping: Client users see only their own linked company
        if user.role == 'CLIENT':
            if not user.client_company_id:
                return Response([])
            qs = qs.filter(client_id=user.client_company_id)

        # Filtering
        status_param = request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)

        search_param = request.query_params.get('search')
        if search_param:
            qs = qs.filter(legal_name__icontains=search_param)

        return Response(ClientSerializer(qs, many=True).data)

    def post(self, request):
        if request.user.role != 'ADMIN':
            raise PermissionDenied("Only Admin can create clients.")
        client = services.create_client(
            request.user.company_id, request.data, request.user, request=request
        )
        return Response(ClientSerializer(client).data, status=status.HTTP_201_CREATED)


class ClientDetailView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'master_data.view_client'

    def get(self, request, client_id):
        client = Client.objects.get(client_id=client_id, company_id=request.user.company_id)
        if request.user.role == 'CLIENT' and str(request.user.client_company_id) != str(client.client_id):
            raise PermissionDenied("Access to client company outside scope is denied.")
        return Response(ClientSerializer(client).data)

    def put(self, request, client_id):
        if request.user.role != 'ADMIN':
            raise PermissionDenied("Only Admin can modify clients.")
        client = services.update_client(client_id, request.data, request.user, request=request)
        return Response(ClientSerializer(client).data)


class ClientContactCreateView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'master_data.manage'

    def post(self, request, client_id):
        contact = services.add_client_contact(client_id, request.data, request.user, request=request)
        return Response(ClientContactSerializer(contact).data, status=status.HTTP_201_CREATED)


# ==============================================================================
# 3. SITES & GEOFENCES
# ==============================================================================

class SiteListView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'master_data.view_sites'

    def get(self, request):
        user = request.user
        qs = ClientSite.objects.filter(client__company_id=user.company_id)

        # Scoping per role:
        # SUPERVISOR: assigned sites only
        if user.role == 'SUPERVISOR':
            assigned_site_ids = SiteSupervisorAssignment.objects.filter(
                supervisor_user_id=user.user_id, is_active=True
            ).values_list('site_id', flat=True)
            qs = qs.filter(site_id__in=assigned_site_ids)

        # CLIENT: sites belonging to their own company
        elif user.role == 'CLIENT':
            if not user.client_company_id:
                return Response([])
            qs = qs.filter(client_id=user.client_company_id)

        # Filtering
        client_id_param = request.query_params.get('client_id')
        if client_id_param:
            qs = qs.filter(client_id=client_id_param)

        status_param = request.query_params.get('status')
        if status_param:
            qs = qs.filter(operational_status=status_param)

        return Response(ClientSiteSerializer(qs, many=True).data)

    def post(self, request):
        if request.user.role != 'ADMIN':
            raise PermissionDenied("Only Admin can create sites.")
        client_id = request.data.get('client_id')
        if not client_id:
            raise ValidationError({'client_id': 'Client ID is required.'})
        site = services.create_site(client_id, request.data, request.user, request=request)
        return Response(ClientSiteSerializer(site).data, status=status.HTTP_201_CREATED)


class SiteDetailView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'master_data.view_sites'

    def get(self, request, site_id):
        site = ClientSite.objects.get(site_id=site_id, client__company_id=request.user.company_id)
        user = request.user
        if user.role == 'SUPERVISOR':
            if not SiteSupervisorAssignment.objects.filter(site=site, supervisor_user_id=user.user_id, is_active=True).exists():
                raise PermissionDenied("Supervisor not assigned to this site.")
        elif user.role == 'CLIENT':
            if str(site.client_id) != str(user.client_company_id):
                raise PermissionDenied("Site outside client company scope.")
        return Response(ClientSiteSerializer(site).data)


class SiteGeofenceUpdateView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'master_data.manage'

    def post(self, request, site_id):
        lat = request.data.get('latitude')
        lon = request.data.get('longitude')
        radius = request.data.get('radius_meters')
        reason = request.data.get('reason_for_change')
        gf = services.update_site_geofence(site_id, lat, lon, radius, reason, request.user, request=request)
        return Response(SiteGeofenceSerializer(gf).data, status=status.HTTP_200_OK)


class SiteSupervisorAssignView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'master_data.manage'

    def post(self, request, site_id):
        sup_id = request.data.get('supervisor_user_id')
        role_type = request.data.get('role_type', 'primary')
        reason = request.data.get('assignment_reason')
        assign = services.assign_site_supervisor(site_id, sup_id, role_type, reason, request.user, request=request)
        return Response(SiteSupervisorAssignmentSerializer(assign).data, status=status.HTTP_200_OK)


# ==============================================================================
# 4. POST TYPES & SHIFTS
# ==============================================================================

class PostTypeListView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'master_data.view_sites'

    def get(self, request):
        pts = PostType.objects.filter(company_id=request.user.company_id)
        return Response(PostTypeSerializer(pts, many=True).data)

    def post(self, request):
        if request.user.role != 'ADMIN':
            raise PermissionDenied("Only Admin can manage post types.")
        code = request.data.get('code', '').strip().upper()
        name = request.data.get('name', '').strip()
        pt = PostType.objects.create(
            company=request.user.company,
            code=code,
            name=name,
            requires_armed_authorization=request.data.get('requires_armed_authorization', False),
            description=request.data.get('description')
        )
        return Response(PostTypeSerializer(pt).data, status=status.HTTP_201_CREATED)


class SiteShiftListView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'master_data.view_sites'

    def get(self, request, site_id):
        shifts = SiteShift.objects.filter(site_id=site_id, is_active=True)
        return Response(SiteShiftSerializer(shifts, many=True).data)

    def post(self, request, site_id):
        if request.user.role != 'ADMIN':
            raise PermissionDenied("Only Admin can create site shifts.")
        shift = services.create_site_shift(site_id, request.data, request.user, request=request)
        return Response(SiteShiftSerializer(shift).data, status=status.HTTP_201_CREATED)


# ==============================================================================
# 5. MANPOWER REQUIREMENTS
# ==============================================================================

class SiteManpowerRequirementListView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'master_data.view_sites'

    def get(self, request, site_id):
        reqs = SiteManpowerRequirement.objects.filter(site_id=site_id, is_active=True)
        return Response(SiteManpowerRequirementSerializer(reqs, many=True).data)

    def post(self, request, site_id):
        if request.user.role != 'ADMIN':
            raise PermissionDenied("Only Admin can set manpower requirements.")
        shift_id = request.data.get('shift_id')
        post_type_id = request.data.get('post_type_id')
        count = int(request.data.get('required_count', 0))
        effective_from = request.data.get('effective_from')
        req = services.set_manpower_requirement(
            site_id, shift_id, post_type_id, count, effective_from, request.user, request=request
        )
        return Response(SiteManpowerRequirementSerializer(req).data, status=status.HTTP_201_CREATED)


# ==============================================================================
# 6. SERVICE AGREEMENTS
# ==============================================================================

class ServiceAgreementListView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'master_data.view_client'

    def get(self, request):
        qs = ServiceAgreement.objects.filter(client__company_id=request.user.company_id, is_active=True)
        if request.user.role == 'CLIENT':
            qs = qs.filter(client_id=request.user.client_company_id)
        return Response(ServiceAgreementSerializer(qs, many=True).data)

    def post(self, request):
        if request.user.role != 'ADMIN':
            raise PermissionDenied("Only Admin can create service agreements.")
        client_id = request.data.get('client_id')
        agreement = services.create_service_agreement(client_id, request.data, request.user, request=request)
        return Response(ServiceAgreementSerializer(agreement).data, status=status.HTTP_201_CREATED)


# ==============================================================================
# 7. BILLING RATES
# ==============================================================================

class ClientBillingRateListView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'master_data.manage'

    def get(self, request):
        if request.user.role != 'ADMIN':
            raise PermissionDenied("Only Admin can view billing rates.")
        qs = ClientBillingRate.objects.filter(client__company_id=request.user.company_id, is_active=True)
        return Response(ClientBillingRateSerializer(qs, many=True).data)

    def post(self, request):
        if request.user.role != 'ADMIN':
            raise PermissionDenied("Only Admin can configure billing rates.")
        client_id = request.data.get('client_id')
        site_id = request.data.get('site_id')
        post_type_id = request.data.get('post_type_id')
        amount = request.data.get('rate_amount')
        rate_type = request.data.get('rate_type', 'hourly')
        eff_from = request.data.get('effective_from')
        rate = services.set_billing_rate(
            client_id, post_type_id, amount, rate_type, eff_from, request.user, site_id=site_id, request=request
        )
        return Response(ClientBillingRateSerializer(rate).data, status=status.HTTP_201_CREATED)


class BillingRateResolveView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'master_data.view_sites'

    def get(self, request):
        client_id = request.query_params.get('client_id')
        site_id = request.query_params.get('site_id')
        post_type_id = request.query_params.get('post_type_id')
        target_date = request.query_params.get('date')

        if not client_id or not post_type_id or not target_date:
            raise ValidationError({'detail': 'client_id, post_type_id, and date are required.'})

        rate, source = services.resolve_billing_rate(client_id, post_type_id, target_date, site_id=site_id)
        if not rate:
            return Response({'resolved': False, 'source': 'not_found', 'rate': None})

        return Response({
            'resolved': True,
            'source': source,
            'rate': ClientBillingRateSerializer(rate).data
        })


# ==============================================================================
# 8. CSV IMPORT
# ==============================================================================

class ClientCsvImportView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'master_data.manage'

    def post(self, request):
        csv_content = request.data.get('csv_content')
        if not csv_content:
            raise ValidationError({'csv_content': 'CSV text content is required.'})
        count = services.import_clients_csv(csv_content, request.user.company_id, request.user, request=request)
        return Response({'message': f'Successfully imported {count} clients.', 'imported_count': count})
