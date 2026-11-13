import uuid
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError, PermissionDenied, NotFound

from foundation.services.scope_service import HasCapabilityAndScope
from .models import (
    ServiceRequest,
    ServiceSiteSurvey,
    Quotation,
    QuotationVersion,
)
from .serializers import (
    ServiceRequestSerializer,
    ServiceSiteSurveySerializer,
    QuotationSerializer,
    QuotationVersionSerializer,
)
from . import services


class ServiceRequestListView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'service_request.view'

    def get(self, request):
        user = request.user
        role = getattr(user, 'role', '').lower()

        if role == 'client':
            if not user.client_company_id:
                return Response([], status=status.HTTP_200_OK)
            qs = ServiceRequest.objects.filter(client_id=user.client_company_id)
        else:
            qs = ServiceRequest.objects.filter(company_id=user.company_id)

        req_status = request.query_params.get('status')
        if req_status:
            qs = qs.filter(status=req_status)

        qs = qs.order_by('-created_at')
        serializer = ServiceRequestSerializer(qs, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request):
        user = request.user
        role = getattr(user, 'role', '').lower()

        if role == 'client':
            if not user.client_company_id:
                raise PermissionDenied("Client user has no associated client company.")
            client_id = user.client_company_id
        else:
            client_id = request.data.get('client_id')
            if not client_id:
                raise ValidationError({"client_id": "Client ID is required for administrative request creation."})

        try:
            req_obj = services.create_service_request(client_id, request.data, user, request=request)
            serializer = ServiceRequestSerializer(req_obj, context={'request': request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except (ValueError, ValidationError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ServiceRequestDetailView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'service_request.view'

    def get_object(self, request_id, user):
        try:
            req_obj = ServiceRequest.objects.get(request_id=request_id)
        except ServiceRequest.DoesNotExist:
            raise NotFound("Service request not found.")

        role = getattr(user, 'role', '').lower()
        if role == 'client' and str(req_obj.client_id) != str(user.client_company_id):
            raise PermissionDenied("You do not have access to this service request.")
        elif role != 'client' and str(req_obj.company_id) != str(user.company_id):
            raise PermissionDenied("You do not have access to this service request.")

        return req_obj

    def get(self, request, request_id):
        req_obj = self.get_object(request_id, request.user)
        serializer = ServiceRequestSerializer(req_obj, context={'request': request})
        return Response(serializer.data)


class ServiceRequestWithdrawView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'service_request.raise'

    def post(self, request, request_id):
        try:
            req_obj = services.withdraw_service_request(request_id, request.user, request=request)
            serializer = ServiceRequestSerializer(req_obj, context={'request': request})
            return Response(serializer.data)
        except (ValueError, PermissionDenied) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ServiceRequestClarifyView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'service_request.view'

    def post(self, request, request_id):
        question = request.data.get('message') or request.data.get('question')
        if not question or not str(question).strip():
            return Response({'error': 'Clarification question/message is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            comment = services.request_service_clarification(request_id, question, request.user, request=request)
            return Response({'status': 'clarification_sent', 'comment_id': str(comment.comment_id)}, status=status.HTTP_201_CREATED)
        except (ValueError, NotFound, PermissionDenied) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ServiceSiteSurveyView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'quotation.manage'

    def post(self, request, request_id):
        try:
            req_obj = ServiceRequest.objects.get(request_id=request_id, company_id=request.user.company_id)
        except ServiceRequest.DoesNotExist:
            raise NotFound("Service request not found.")

        survey_date = request.data.get('survey_date')
        visited_by = request.data.get('visited_by')
        assigned_supervisor_id = request.data.get('assigned_supervisor_id')
        findings = request.data.get('findings')
        notes = request.data.get('notes', '')

        if not survey_date or not visited_by or not findings:
            return Response({'error': 'survey_date, visited_by, and findings are required.'}, status=status.HTTP_400_BAD_REQUEST)

        survey = ServiceSiteSurvey.objects.create(
            request=req_obj,
            survey_date=survey_date,
            visited_by=visited_by,
            assigned_supervisor_id=assigned_supervisor_id,
            findings=findings,
            notes=notes
        )

        req_obj.status = 'survey_scheduled'
        req_obj.save(update_fields=['status', 'updated_at'])

        serializer = ServiceSiteSurveySerializer(survey)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class QuotationListView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'service_request.view'

    def get(self, request):
        user = request.user
        role = getattr(user, 'role', '').lower()

        if role == 'client':
            if not user.client_company_id:
                return Response([])
            qs = Quotation.objects.filter(client_id=user.client_company_id)
        else:
            qs = Quotation.objects.filter(company_id=user.company_id)

        req_id = request.query_params.get('request_id')
        if req_id:
            qs = qs.filter(request_id=req_id)

        qs = qs.order_by('-created_at')
        serializer = QuotationSerializer(qs, many=True, context={'request': request})
        return Response(serializer.data)


class QuotationDetailView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'service_request.view'

    def get(self, request, quotation_id):
        user = request.user
        try:
            q_obj = Quotation.objects.get(quotation_id=quotation_id)
        except Quotation.DoesNotExist:
            raise NotFound("Quotation not found.")

        role = getattr(user, 'role', '').lower()
        if role == 'client' and str(q_obj.client_id) != str(user.client_company_id):
            raise PermissionDenied("You do not have access to this quotation.")
        elif role != 'client' and str(q_obj.company_id) != str(user.company_id):
            raise PermissionDenied("You do not have access to this quotation.")

        serializer = QuotationSerializer(q_obj, context={'request': request})
        return Response(serializer.data)


class QuotationCreateView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'quotation.manage'

    def post(self, request):
        request_id = request.data.get('request_id')
        if not request_id:
            return Response({'error': 'request_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            quotation, version = services.create_quotation(request_id, request.data, request.user, request=request)
            serializer = QuotationSerializer(quotation, context={'request': request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except (ValueError, ValidationError, NotFound) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class QuotationSendView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'quotation.manage'

    def post(self, request, version_id):
        try:
            version = services.send_quotation(version_id, request.user, request=request)
            serializer = QuotationVersionSerializer(version, context={'request': request})
            return Response(serializer.data)
        except (ValueError, NotFound, PermissionDenied) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class QuotationReviseView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'quotation.manage'

    def post(self, request, quotation_id):
        try:
            new_version = services.revise_quotation(quotation_id, request.data, request.user, request=request)
            serializer = QuotationVersionSerializer(new_version, context={'request': request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except (ValueError, NotFound, PermissionDenied) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class QuotationAcceptView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'quotation.decide'

    def post(self, request, version_id):
        confirmation_checked = request.data.get('confirmation_checked', False)
        try:
            version = services.accept_quotation(version_id, confirmation_checked, request.user, request=request)
            acceptance = version.acceptances.order_by('-accepted_at').first()
            return Response({
                'status': 'accepted',
                'acceptance_id': str(acceptance.acceptance_id) if acceptance else None,
                'accepted_at': acceptance.accepted_at if acceptance else None,
            })
        except (ValueError, NotFound, PermissionDenied, ValidationError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class QuotationRejectView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'quotation.decide'

    def post(self, request, version_id):
        reason_category = request.data.get('reason_category', 'OTHER')
        comments = request.data.get('comments', '')
        try:
            version = services.reject_quotation(version_id, reason_category, comments, request.user, request=request)
            return Response({'status': 'rejected', 'version_id': str(version.quotation_version_id)})
        except (ValueError, NotFound, PermissionDenied) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class QuotationCounterView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'quotation.decide'

    def post(self, request, version_id):
        comment = request.data.get('comment', '')
        try:
            counter = services.counter_quotation(version_id, comment, request.data, request.user, request=request)
            return Response({
                'status': 'countered',
                'counter_id': str(counter.counter_id),
                'negotiation_round': counter.negotiation_round,
            }, status=status.HTTP_201_CREATED)
        except (ValueError, NotFound, PermissionDenied) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class QuotationConvertView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'quotation.manage'

    def post(self, request, version_id):
        try:
            conversion = services.create_draft_setup_from_accepted_quote(version_id, request.user, request=request)
            return Response({
                'status': conversion.conversion_status,
                'conversion_reference': conversion.conversion_reference,
                'site_id': str(conversion.module2_site_id) if conversion.module2_site_id else None,
                'agreement_id': str(conversion.module2_agreement_id) if conversion.module2_agreement_id else None,
                'generated_records': conversion.generated_records,
            })
        except (ValueError, NotFound, PermissionDenied) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
