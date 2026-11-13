import csv
import io
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError, PermissionDenied, NotFound

from guard_management.models import (
    Employee, EmployeeDocument, EmployeeTraining, EmployeeCheck,
    LeaveRequest, GuardStatusHistory, GuardDisciplinaryRecord,
    GuardIdCard, ProfileChangeRequest
)
from guard_management.serializers import (
    EmployeeListSerializer, EmployeeDetailSerializer, EmployeeDocumentSerializer,
    EmployeeTrainingSerializer, EmployeeCheckSerializer, LeaveRequestSerializer,
    GuardStatusHistorySerializer, GuardDisciplinaryRecordSerializer,
    GuardIdCardSerializer, ProfileChangeRequestSerializer
)
from guard_management import services
from foundation.services.scope_service import HasCapabilityAndScope
from master_data.models import ClientSite, SiteSupervisorAssignment


# ==============================================================================
# 1. GUARD DASHBOARD & LIST
# ==============================================================================

class GuardDashboardView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'guard.view_profile'

    def get(self, request):
        user = request.user
        qs = Employee.objects.filter(company_id=user.company_id)

        # Metric counts
        total = qs.count()
        applicants = qs.filter(lifecycle_status='applicant').count()
        under_verification = qs.filter(lifecycle_status='under_verification').count()
        approved = qs.filter(lifecycle_status='approved').count()
        active = qs.filter(lifecycle_status='active').count()
        on_leave = qs.filter(lifecycle_status='on_leave').count()
        suspended = qs.filter(lifecycle_status='suspended').count()
        resigned = qs.filter(lifecycle_status='resigned').count()
        terminated = qs.filter(lifecycle_status='terminated').count()

        # Non-deployable count among active guards
        active_guards = qs.filter(lifecycle_status='active')
        non_deployable = 0
        for g in active_guards:
            dep = services.is_guard_deployable_on_date(g.employee_id)
            if not dep['deployable']:
                non_deployable += 1

        return Response({
            'total_guards': total,
            'applicants': applicants,
            'under_verification': under_verification,
            'approved': approved,
            'active': active,
            'on_leave': on_leave,
            'suspended': suspended,
            'resigned': resigned,
            'terminated': terminated,
            'non_deployable_active': non_deployable
        })


class GuardListView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'guard.view_profile'

    def get(self, request):
        user = request.user
        qs = Employee.objects.filter(company_id=user.company_id)

        # Scoping per role:
        # SUPERVISOR: guards assigned to supervisor's sites (AC-36)
        if user.role == 'SUPERVISOR':
            assigned_site_ids = SiteSupervisorAssignment.objects.filter(
                supervisor_user_id=user.user_id, is_active=True
            ).values_list('site_id', flat=True)
            # Find guards associated with supervisor sites or reporting directly
            qs = qs.filter(reporting_supervisor_id=user.user_id)

        # GUARD: own record only (AC-30)
        elif user.role == 'GUARD':
            if not user.guard_profile_id:
                return Response([])
            qs = qs.filter(employee_id=user.guard_profile_id)

        # CLIENT: Denied direct access (AC-37)
        elif user.role == 'CLIENT':
            raise PermissionDenied("Clients do not have direct access to guard management (AC-37).")

        # Filters
        status_param = request.query_params.get('status')
        if status_param:
            qs = qs.filter(lifecycle_status=status_param)

        search_param = request.query_params.get('search')
        if search_param:
            qs = qs.filter(
                first_name__icontains=search_param
            ) | qs.filter(
                employee_code__icontains=search_param
            )

        return Response(EmployeeListSerializer(qs, many=True).data)

    def post(self, request):
        if request.user.role != 'ADMIN':
            raise PermissionDenied("Only Admin may register new guards.")
        emp = services.register_guard(request.user.company_id, request.data, request.user, request=request)
        return Response(EmployeeDetailSerializer(emp, context={'request': request}).data, status=status.HTTP_201_CREATED)


class GuardDetailView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'guard.view_profile'

    def get(self, request, employee_id):
        user = request.user
        emp = Employee.objects.get(employee_id=employee_id, company_id=user.company_id)

        if user.role == 'GUARD' and str(user.guard_profile_id) != str(emp.employee_id):
            raise PermissionDenied("Guards may only access their own profile (AC-30).")

        if user.role == 'SUPERVISOR':
            # Supervisors see only permitted non-sensitive fields (AC-26, AC-29)
            if emp.reporting_supervisor_id and str(emp.reporting_supervisor_id) != str(user.user_id):
                raise PermissionDenied("Supervisor access restricted to assigned scope (AC-36).")

        return Response(EmployeeDetailSerializer(emp, context={'request': request}).data)

    def patch(self, request, employee_id):
        user = request.user
        emp = Employee.objects.get(employee_id=employee_id, company_id=user.company_id)

        if user.role != 'ADMIN':
            raise PermissionDenied("Only Admin may directly update guard profiles.")

        allowed_fields = [
            'first_name', 'last_name', 'father_guardian_name', 'phone', 'email',
            'blood_group', 'marital_status', 'height_cm', 'weight_kg',
            'qualification', 'experience_summary', 'is_ex_serviceman',
            'reference_photo_url', 'home_district', 'preferred_work_area',
            'post_type_id', 'reporting_supervisor_id'
        ]
        for field in allowed_fields:
            if field in request.data:
                setattr(emp, field, request.data[field])

        emp.save()
        return Response(EmployeeDetailSerializer(emp, context={'request': request}).data)


# ==============================================================================
# 2. STATUS TRANSITION (AC-06 to AC-10)
# ==============================================================================

class GuardStatusChangeView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'guard.manage'

    def post(self, request, employee_id):
        new_status = request.data.get('status')
        reason = request.data.get('reason')
        emp = services.change_guard_status(employee_id, new_status, reason, request.user, request=request)
        return Response(EmployeeDetailSerializer(emp, context={'request': request}).data)


# ==============================================================================
# 3. DOCUMENTS & VERIFICATION (AC-18 to AC-22)
# ==============================================================================

class GuardDocumentUploadView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'guard.manage'

    def post(self, request, employee_id):
        doc_type = request.data.get('document_type')
        storage_key = request.data.get('storage_key') or f"docs/{employee_id}/{doc_type}"
        filename = request.data.get('original_filename') or f"{doc_type}.pdf"
        doc = services.upload_guard_document(
            employee_id, doc_type, storage_key, filename, request.data, request.user, request=request
        )
        return Response(EmployeeDocumentSerializer(doc).data, status=status.HTTP_201_CREATED)


class GuardDocumentVerifyView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'guard.manage'

    def post(self, request, document_id):
        decision = request.data.get('decision')
        reason = request.data.get('rejection_reason')
        doc = services.verify_guard_document(document_id, decision, reason, request.user, request=request)
        return Response(EmployeeDocumentSerializer(doc).data)


# ==============================================================================
# 4. TRAINING & CHECKS
# ==============================================================================

class GuardTrainingCreateView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'guard.manage'

    def post(self, request, employee_id):
        emp = Employee.objects.get(employee_id=employee_id)
        training = EmployeeTraining.objects.create(
            employee=emp,
            attendance_status=request.data.get('attendance_status', 'present'),
            result=request.data.get('result', 'passed'),
            certificate_no=request.data.get('certificate_no'),
            completed_at=request.data.get('completed_at'),
            valid_until=request.data.get('valid_until')
        )
        return Response(EmployeeTrainingSerializer(training).data, status=status.HTTP_201_CREATED)


class GuardCheckCreateView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'guard.manage'

    def post(self, request, employee_id):
        emp = Employee.objects.get(employee_id=employee_id)
        check = EmployeeCheck.objects.create(
            employee=emp,
            check_type=request.data.get('check_type'),
            provider=request.data.get('provider'),
            requested_at=request.data.get('requested_at'),
            completed_at=request.data.get('completed_at'),
            valid_until=request.data.get('valid_until'),
            status=request.data.get('status', 'cleared'),
            result_reference=request.data.get('result_reference')
        )
        return Response(EmployeeCheckSerializer(check).data, status=status.HTTP_201_CREATED)


# ==============================================================================
# 5. BANK DETAILS & AUDITED REVEAL (AC-26, AC-27)
# ==============================================================================

class GuardBankUpdateView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'guard.manage'

    def put(self, request, employee_id):
        emp = services.update_guard_bank_details(employee_id, request.data, request.user, request=request)
        return Response({'message': 'Bank details updated successfully.'})


class GuardBankRevealView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'guard.manage'

    def post(self, request, employee_id):
        raw_bank = services.reveal_guard_bank_details(employee_id, request.user, request=request)
        return Response(raw_bank)


# ==============================================================================
# 6. ACCOUNT LINKING (AC-34, AC-35)
# ==============================================================================

class GuardAccountCreateView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'guard.manage'

    def post(self, request, employee_id):
        user, temp_pass = services.create_guard_login_account(employee_id, request.user, request=request)
        return Response({
            'message': 'Guard login account created successfully.',
            'phone': user.phone,
            'temporary_password': temp_pass
        }, status=status.HTTP_201_CREATED)


# ==============================================================================
# 7. DEPLOYABILITY EVALUATION (AC-11 to AC-17)
# ==============================================================================

class GuardDeployabilityCheckView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'guard.view_profile'

    def get(self, request, employee_id):
        target_date = request.query_params.get('date')
        post_type_id = request.query_params.get('post_type_id')
        res = services.is_guard_deployable_on_date(employee_id, target_date=target_date, post_type_id=post_type_id)
        return Response(res)


# ==============================================================================
# 8. UNAVAILABILITY (AC-31 to AC-33)
# ==============================================================================

class GuardUnavailabilityView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'guard.view_profile'

    def post(self, request, employee_id):
        leave = services.request_unavailability(
            employee_id,
            request.data.get('leave_type', 'leave'),
            request.data.get('start_date'),
            request.data.get('end_date'),
            request.data.get('reason'),
            request.user,
            request=request
        )
        return Response(LeaveRequestSerializer(leave).data, status=status.HTTP_201_CREATED)


class GuardUnavailabilityDecideView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'guard.manage'

    def post(self, request, leave_id):
        decision = request.data.get('decision')
        leave = services.decide_unavailability(leave_id, decision, request.user, request=request)
        return Response(LeaveRequestSerializer(leave).data)


# ==============================================================================
# 9. DISCIPLINARY & ID CARDS (AC-39)
# ==============================================================================

class GuardDisciplinaryCreateView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'guard.manage'

    def post(self, request, employee_id):
        emp = Employee.objects.get(employee_id=employee_id)
        record = GuardDisciplinaryRecord.objects.create(
            employee=emp,
            category=request.data.get('category', 'general'),
            incident_date=request.data.get('incident_date'),
            remarks=request.data.get('remarks'),
            is_visible_to_guard=request.data.get('is_visible_to_guard', False),
            created_by_user_id=request.user.user_id
        )
        return Response(GuardDisciplinaryRecordSerializer(record).data, status=status.HTTP_201_CREATED)


class GuardIdCardGenerateView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'guard.view_profile'

    def post(self, request, employee_id):
        emp = Employee.objects.get(employee_id=employee_id)
        card = GuardIdCard.objects.create(
            employee=emp,
            employee_code=emp.employee_code,
            valid_until=emp.date_joined + timedelta(days=365),
            qr_payload=emp.employee_code,  # Strictly employee code only (FR-3.125, AC-39)
            reissue_count=GuardIdCard.objects.filter(employee=emp).count() + 1
        )
        return Response(GuardIdCardSerializer(card).data, status=status.HTTP_201_CREATED)
