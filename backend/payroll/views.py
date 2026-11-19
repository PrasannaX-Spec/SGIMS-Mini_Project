import json
from decimal import Decimal
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, NotFound, ValidationError

from .models import (
    SalaryComponent, SalaryStructure, SalaryStructureLine,
    GuardSalaryAssignment, MinimumWage, PaidDayRuleSet,
    WeeklyOffCalendar, StatutoryRuleSet, Advance,
    AdvanceLedgerEntry, ManualDeduction, PayrollRun,
    PayrollResult, PayrollResultLine, Payslip,
    PaymentRecord, FinalSettlement, StatutoryPayment
)
from .serializers import (
    SalaryComponentSerializer, SalaryStructureSerializer, SalaryStructureLineSerializer,
    GuardSalaryAssignmentSerializer, MinimumWageSerializer, PaidDayRuleSetSerializer,
    WeeklyOffCalendarSerializer, StatutoryRuleSetSerializer, AdvanceSerializer,
    AdvanceLedgerEntrySerializer, ManualDeductionSerializer, PayrollRunSerializer,
    PayrollResultSerializer, PayrollResultLineSerializer, PayslipSerializer,
    PaymentRecordSerializer, FinalSettlementSerializer, StatutoryPaymentSerializer
)
from .services import (
    get_pre_run_checklist, calculate_payroll_run, approve_payroll_run,
    release_payroll_run, record_payment, reverse_payment,
    generate_bank_payment_file, get_payroll_dashboard_data
)


def check_admin_access(request):
    if getattr(request.user, 'role', None) not in ['ADMIN', 'SUPER_ADMIN']:
        raise PermissionDenied("Access restricted to authorized Administrators.")


# -----------------------------------------------------------------------------
# 1. DASHBOARD & CHECKLIST (PRD 10.1 Screen 1 & 11)
# -----------------------------------------------------------------------------
class PayrollDashboardView(APIView):
    permission_classes = [IsAuthenticated]
    required_capability = 'payroll.view_dashboard'

    def get(self, request):
        check_admin_access(request)
        data = get_payroll_dashboard_data(request.user.company_id)
        return Response(data)


class PayrollPreRunChecklistView(APIView):
    permission_classes = [IsAuthenticated]
    required_capability = 'payroll.view_checklist'

    def get(self, request):
        check_admin_access(request)
        period_start = request.query_params.get('period_start')
        period_end = request.query_params.get('period_end')
        if not period_start or not period_end:
            now = timezone.now().date()
            period_start = date(now.year, now.month, 1)
            next_month = date(now.year + (1 if now.month == 12 else 0), 1 if now.month == 12 else now.month + 1, 1)
            period_end = next_month - timezone.timedelta(days=1)

        checklist = get_pre_run_checklist(request.user.company_id, period_start, period_end)
        return Response(checklist)


# -----------------------------------------------------------------------------
# 2. SALARY COMPONENTS (PRD 6.1, Screen 2)
# -----------------------------------------------------------------------------
class SalaryComponentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    required_capability = 'payroll.manage_components'
    serializer_class = SalaryComponentSerializer

    def get_queryset(self):
        check_admin_access(self.request)
        return SalaryComponent.objects.filter(company_id=self.request.user.company_id)

    def perform_create(self, serializer):
        check_admin_access(self.request)
        serializer.save(
            company_id=self.request.user.company_id,
            created_by=self.request.user.user_id
        )

    def destroy(self, request, *args, **kwargs):
        check_admin_access(request)
        component = self.get_object()
        # AC14.2: Historical check
        used_in_structures = SalaryStructureLine.objects.filter(component=component).exists()
        used_in_results = PayrollResultLine.objects.filter(component_id=component.component_id).exists()
        if used_in_structures or used_in_results:
            raise ValidationError("Component cannot be deleted because it is used in historical salary structures or payroll runs (AC14.2). Deactivate it instead.")
        return super().destroy(request, *args, **kwargs)


# -----------------------------------------------------------------------------
# 3. SALARY STRUCTURES (PRD 6.1, Screen 3)
# -----------------------------------------------------------------------------
class SalaryStructureViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    required_capability = 'payroll.manage_structures'
    serializer_class = SalaryStructureSerializer

    def get_queryset(self):
        check_admin_access(self.request)
        return SalaryStructure.objects.filter(company_id=self.request.user.company_id).prefetch_related('lines__component')

    def create(self, request, *args, **kwargs):
        check_admin_access(request)
        data = request.data.copy()
        lines_data = data.pop('lines', [])

        structure = SalaryStructure.objects.create(
            company_id=request.user.company_id,
            name=data.get('name'),
            version=data.get('version', 1),
            effective_from=data.get('effective_from'),
            effective_to=data.get('effective_to'),
            status=data.get('status', 'ACTIVE'),
            change_reason=data.get('change_reason', 'Initial structure creation'),
            created_by=request.user.user_id
        )

        for line in lines_data:
            comp_id = line.get('component_id') or line.get('component')
            SalaryStructureLine.objects.create(
                structure=structure,
                component_id=comp_id,
                amount=Decimal(str(line.get('amount', 0))),
                calculation_type=line.get('calculation_type', 'FIXED'),
                effective_from=line.get('effective_from', structure.effective_from),
                effective_to=line.get('effective_to', structure.effective_to)
            )

        serializer = self.get_serializer(structure)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# -----------------------------------------------------------------------------
# 4. GUARD SALARY ASSIGNMENTS (PRD 6.1, Screen 3 & 4)
# -----------------------------------------------------------------------------
class GuardSalaryAssignmentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    required_capability = 'payroll.manage_assignments'
    serializer_class = GuardSalaryAssignmentSerializer

    def get_queryset(self):
        check_admin_access(self.request)
        qs = GuardSalaryAssignment.objects.filter(company_id=self.request.user.company_id).select_related('structure')
        guard_id = self.request.query_params.get('guard_id')
        if guard_id:
            qs = qs.filter(guard_id=guard_id)
        return qs

    def perform_create(self, serializer):
        check_admin_access(self.request)
        # AC14.4: Keep old assignment in history, don't overwrite
        serializer.save(
            company_id=self.request.user.company_id,
            prepared_by=self.request.user.user_id,
            approved_by=self.request.user.user_id
        )


class BulkSalaryAssignmentView(APIView):
    permission_classes = [IsAuthenticated]
    required_capability = 'payroll.manage_assignments'

    def post(self, request):
        check_admin_access(request)
        guard_ids = request.data.get('guard_ids', [])
        structure_id = request.data.get('structure_id')
        pay_basis = request.data.get('pay_basis', 'MONTHLY')
        effective_from = request.data.get('effective_from')
        reason = request.data.get('reason', 'Bulk assignment')

        if not guard_ids or not structure_id or not effective_from:
            raise ValidationError("guard_ids, structure_id, and effective_from are required.")

        created_count = 0
        for gid in guard_ids:
            GuardSalaryAssignment.objects.create(
                company_id=request.user.company_id,
                guard_id=gid,
                structure_id=structure_id,
                pay_basis=pay_basis,
                effective_from=effective_from,
                reason=reason,
                prepared_by=request.user.user_id,
                approved_by=request.user.user_id,
                status='ACTIVE'
            )
            created_count += 1

        return Response({"message": f"Successfully assigned structure to {created_count} guards."})


# -----------------------------------------------------------------------------
# 5. MINIMUM WAGES (PRD 6.2, Screen 5)
# -----------------------------------------------------------------------------
class MinimumWageViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    required_capability = 'payroll.manage_minimum_wages'
    serializer_class = MinimumWageSerializer

    def get_queryset(self):
        check_admin_access(self.request)
        return MinimumWage.objects.filter(company_id=self.request.user.company_id)

    def perform_create(self, serializer):
        check_admin_access(self.request)
        serializer.save(
            company_id=self.request.user.company_id,
            approved_by=self.request.user.user_id
        )


# -----------------------------------------------------------------------------
# 6. PAID-DAY RULES & CALENDARS (PRD 6.3, Screen 6)
# -----------------------------------------------------------------------------
class PaidDayRuleViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    required_capability = 'payroll.manage_paid_day_rules'
    serializer_class = PaidDayRuleSetSerializer

    def get_queryset(self):
        check_admin_access(self.request)
        return PaidDayRuleSet.objects.filter(company_id=self.request.user.company_id)

    def perform_create(self, serializer):
        check_admin_access(self.request)
        serializer.save(
            company_id=self.request.user.company_id,
            approved_by=self.request.user.user_id
        )


class WeeklyOffCalendarViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    required_capability = 'payroll.manage_calendars'
    serializer_class = WeeklyOffCalendarSerializer

    def get_queryset(self):
        check_admin_access(self.request)
        return WeeklyOffCalendar.objects.filter(company_id=self.request.user.company_id)

    def perform_create(self, serializer):
        check_admin_access(self.request)
        serializer.save(company_id=self.request.user.company_id)


# -----------------------------------------------------------------------------
# 7. STATUTORY RULE SETS (PRD 6.5, Screen 7)
# -----------------------------------------------------------------------------
class StatutoryRuleSetViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    required_capability = 'payroll.manage_statutory_rules'
    serializer_class = StatutoryRuleSetSerializer

    def get_queryset(self):
        check_admin_access(self.request)
        return StatutoryRuleSet.objects.filter(company_id=self.request.user.company_id)

    def perform_create(self, serializer):
        check_admin_access(self.request)
        serializer.save(
            company_id=self.request.user.company_id,
            prepared_by=self.request.user.user_id,
            status='DRAFT'
        )

    def update(self, request, *args, **kwargs):
        check_admin_access(request)
        # AC14.14: Editing an active rule creates a new version
        instance = self.get_object()
        if instance.status == 'ACTIVE':
            new_data = request.data.copy()
            new_data['version'] = instance.version + 1
            new_data['status'] = 'DRAFT'
            new_data['prepared_by'] = str(request.user.user_id)
            new_data['approved_by'] = None
            serializer = self.get_serializer(data=new_data)
            serializer.is_valid(raise_exception=True)
            new_instance = serializer.save(company_id=request.user.company_id)
            return Response(self.get_serializer(new_instance).data, status=status.HTTP_201_CREATED)
        return super().update(request, *args, **kwargs)


class StatutoryRuleApproveView(APIView):
    """
    AC14.16: Activation blocked until a second approver approves (Dual-Admin).
    """
    permission_classes = [IsAuthenticated]
    required_capability = 'payroll.manage_statutory_rules'

    def post(self, request, pk):
        check_admin_access(request)
        try:
            rule = StatutoryRuleSet.objects.get(rule_set_id=pk, company_id=request.user.company_id)
        except StatutoryRuleSet.DoesNotExist:
            raise NotFound("Statutory rule set not found.")

        # AC14.16: Segregation of Duties - Single preparer cannot activate rule alone
        if rule.prepared_by and str(rule.prepared_by) == str(request.user.user_id):
            raise PermissionDenied("Dual-Admin rule activation required: The preparer cannot be the sole approver for statutory activation (AC14.16).")

        # Deactivate previous active version of this scheme
        StatutoryRuleSet.objects.filter(
            company_id=request.user.company_id,
            scheme=rule.scheme,
            status='ACTIVE'
        ).update(status='SUPERSEDED')

        rule.status = 'ACTIVE'
        rule.approved_by = request.user.user_id
        rule.save()

        return Response({
            "message": f"Rule {rule.scheme} v{rule.version} activated successfully.",
            "rule_set_id": str(rule.rule_set_id),
            "status": rule.status
        })


# -----------------------------------------------------------------------------
# 8. ADVANCES & MANUAL DEDUCTIONS (PRD 6.6, Screen 8 & 9)
# -----------------------------------------------------------------------------
class AdvanceViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    required_capability = 'payroll.manage_advances'
    serializer_class = AdvanceSerializer

    def get_queryset(self):
        # Admin sees all company advances, Guards see only their own
        if getattr(self.request.user, 'role', None) == 'GUARD':
            return Advance.objects.filter(guard_id=self.request.user.user_id).prefetch_related('ledger_entries')
        check_admin_access(self.request)
        return Advance.objects.filter(company_id=self.request.user.company_id).prefetch_related('ledger_entries')

    def perform_create(self, serializer):
        check_admin_access(self.request)
        advance = serializer.save(
            company_id=self.request.user.company_id,
            created_by=self.request.user.user_id,
            status='APPROVED'
        )
        # Create initial ISSUE ledger entry
        AdvanceLedgerEntry.objects.create(
            advance=advance,
            entry_type='ISSUE',
            amount=advance.amount,
            entry_date=advance.issue_date,
            reason="Initial advance issue",
            created_by=self.request.user.user_id,
            approved_by=self.request.user.user_id
        )


class ManualDeductionViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    required_capability = 'payroll.manage_deductions'
    serializer_class = ManualDeductionSerializer

    def get_queryset(self):
        check_admin_access(self.request)
        return ManualDeduction.objects.filter(company_id=self.request.user.company_id)

    def perform_create(self, serializer):
        check_admin_access(self.request)
        serializer.save(
            company_id=self.request.user.company_id,
            prepared_by=self.request.user.user_id,
            approved_by=self.request.user.user_id,
            status='APPROVED'
        )


# -----------------------------------------------------------------------------
# 9. PAYROLL RUNS & WORKFLOW (PRD 6.7, Screens 10, 12, 13)
# -----------------------------------------------------------------------------
class PayrollRunViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    required_capability = 'payroll.manage_runs'
    serializer_class = PayrollRunSerializer

    def get_queryset(self):
        check_admin_access(self.request)
        return PayrollRun.objects.filter(company_id=self.request.user.company_id).prefetch_related('results')

    def perform_create(self, serializer):
        check_admin_access(self.request)
        period_ref = serializer.validated_data.get('period_reference')
        # AC14.34: Duplicate active run check
        dup = PayrollRun.objects.filter(
            company_id=self.request.user.company_id,
            period_reference=period_ref
        ).exclude(status='CANCELLED').exists()
        if dup:
            raise ValidationError(f"An active payroll run already exists for period {period_ref} (AC14.34).")

        serializer.save(
            company_id=self.request.user.company_id,
            prepared_by=self.request.user.user_id,
            status='DRAFT'
        )


class PayrollRunCalculateView(APIView):
    permission_classes = [IsAuthenticated]
    required_capability = 'payroll.calculate_run'

    def post(self, request, pk):
        check_admin_access(request)
        result = calculate_payroll_run(pk, request.user.company_id, request.user.user_id)
        return Response(result)


class PayrollRunApproveView(APIView):
    permission_classes = [IsAuthenticated]
    required_capability = 'payroll.approve_run'

    def post(self, request, pk):
        check_admin_access(request)
        override_reason = request.data.get('override_reason')
        result = approve_payroll_run(pk, request.user.company_id, request.user.user_id, override_reason)
        return Response(result)


class PayrollRunReleaseView(APIView):
    permission_classes = [IsAuthenticated]
    required_capability = 'payroll.release_run'

    def post(self, request, pk):
        check_admin_access(request)
        result = release_payroll_run(pk, request.user.company_id, request.user.user_id)
        return Response(result)


class PayrollRunCancelView(APIView):
    permission_classes = [IsAuthenticated]
    required_capability = 'payroll.cancel_run'

    def post(self, request, pk):
        check_admin_access(request)
        reason = request.data.get('reason')
        if not reason:
            raise ValidationError("Cancellation reason is mandatory.")
        try:
            run = PayrollRun.objects.get(run_id=pk, company_id=request.user.company_id)
        except PayrollRun.DoesNotExist:
            raise NotFound("Payroll run not found.")

        if run.status in ['PAID', 'CLOSED']:
            raise ValidationError(f"Cannot cancel a {run.status} payroll run.")

        run.status = 'CANCELLED'
        run.cancellation_reason = reason
        run.save()
        return Response({"message": f"Run {run.period_reference} has been cancelled."})


class PayrollRunExportBankFileView(APIView):
    permission_classes = [IsAuthenticated]
    required_capability = 'payroll.export_bank_file'

    def get(self, request, pk):
        check_admin_access(request)
        csv_content = generate_bank_payment_file(pk, request.user.company_id)
        response = HttpResponse(csv_content, content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="bank_payout_run_{pk}.csv"'
        return response


# -----------------------------------------------------------------------------
# 10. PAYROLL RESULTS (PRD 6.7, Entity 9)
# -----------------------------------------------------------------------------
class PayrollResultViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    required_capability = 'payroll.view_results'
    serializer_class = PayrollResultSerializer

    def get_queryset(self):
        check_admin_access(self.request)
        qs = PayrollResult.objects.filter(run__company_id=self.request.user.company_id).prefetch_related('lines')
        run_id = self.request.query_params.get('run_id')
        if run_id:
            qs = qs.filter(run_id=run_id)
        return qs


# -----------------------------------------------------------------------------
# 11. PAYSLIPS (PRD 6.8, Screens 15, 19, 20)
# -----------------------------------------------------------------------------
class PayslipViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    required_capability = 'payroll.view_payslips'
    serializer_class = PayslipSerializer

    def get_queryset(self):
        user = self.request.user
        # AC14.41, AC14.42: Guard can only view their own payslips
        if getattr(user, 'role', None) == 'GUARD':
            return Payslip.objects.filter(guard_id=user.user_id, is_latest=True).select_related('run', 'result')
        
        # AC14.44: Client denied
        if getattr(user, 'role', None) == 'CLIENT':
            raise PermissionDenied("Clients have no payroll access (AC14.44).")

        # AC14.43: Supervisor denied financial figures
        if getattr(user, 'role', None) == 'SUPERVISOR':
            raise PermissionDenied("Supervisors do not have access to financial payslip records (AC14.43).")

        check_admin_access(self.request)
        qs = Payslip.objects.filter(run__company_id=user.company_id).select_related('run', 'result')
        run_id = self.request.query_params.get('run_id')
        guard_id = self.request.query_params.get('guard_id')
        if run_id:
            qs = qs.filter(run_id=run_id)
        if guard_id:
            qs = qs.filter(guard_id=guard_id)
        return qs


# -----------------------------------------------------------------------------
# 12. PAYMENT RECORDS (PRD 6.9, Screen 14)
# -----------------------------------------------------------------------------
class PaymentRecordViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    required_capability = 'payroll.record_payments'
    serializer_class = PaymentRecordSerializer

    def get_queryset(self):
        check_admin_access(self.request)
        qs = PaymentRecord.objects.filter(run__company_id=self.request.user.company_id)
        run_id = self.request.query_params.get('run_id')
        if run_id:
            qs = qs.filter(run_id=run_id)
        return qs

    def create(self, request, *args, **kwargs):
        check_admin_access(request)
        run_id = request.data.get('run_id')
        result_id = request.data.get('result_id')
        guard_id = request.data.get('guard_id')
        amount = request.data.get('amount')
        mode = request.data.get('mode', 'BANK_TRANSFER')
        bank_reference = request.data.get('bank_reference')
        witness = request.data.get('witness_or_acknowledgement')

        res = record_payment(
            run_id=run_id,
            result_id=result_id,
            guard_id=guard_id,
            amount=amount,
            mode=mode,
            bank_reference=bank_reference,
            recorder_id=request.user.user_id,
            witness=witness
        )
        return Response(res, status=status.HTTP_201_CREATED)


class PaymentReversalView(APIView):
    permission_classes = [IsAuthenticated]
    required_capability = 'payroll.record_payments'

    def post(self, request, pk):
        check_admin_access(request)
        reason = request.data.get('reversal_reason')
        res = reverse_payment(pk, request.user.company_id, request.user.user_id, reason)
        return Response(res)


# -----------------------------------------------------------------------------
# 13. FULL & FINAL SETTLEMENT (PRD 6.10, Screen 16)
# -----------------------------------------------------------------------------
class FinalSettlementViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    required_capability = 'payroll.manage_final_settlement'
    serializer_class = FinalSettlementSerializer

    def get_queryset(self):
        check_admin_access(self.request)
        return FinalSettlement.objects.filter(company_id=self.request.user.company_id)

    def perform_create(self, serializer):
        check_admin_access(self.request)
        serializer.save(
            company_id=self.request.user.company_id,
            approver_one=self.request.user.user_id,
            status='UNDER_REVIEW'
        )


class FinalSettlementSecondApproveView(APIView):
    """
    AC14.54: Final settlement requires two designated approvals.
    """
    permission_classes = [IsAuthenticated]
    required_capability = 'payroll.manage_final_settlement'

    def post(self, request, pk):
        check_admin_access(request)
        try:
            settlement = FinalSettlement.objects.get(settlement_id=pk, company_id=request.user.company_id)
        except FinalSettlement.DoesNotExist:
            raise NotFound("Final settlement record not found.")

        if settlement.approver_one and str(settlement.approver_one) == str(request.user.user_id):
            raise PermissionDenied("Segregation of duties violation: First approver cannot be the second approver for full and final settlement (AC14.54).")

        settlement.approver_two = request.user.user_id
        settlement.status = 'APPROVED'
        settlement.save()
        return Response({"message": "Full and final settlement fully approved by dual admins.", "status": settlement.status})


# -----------------------------------------------------------------------------
# 14. STATUTORY PAYMENTS & TRACKER (PRD 6.11, Screen 17)
# -----------------------------------------------------------------------------
class StatutoryPaymentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    required_capability = 'payroll.manage_statutory_payments'
    serializer_class = StatutoryPaymentSerializer

    def get_queryset(self):
        check_admin_access(self.request)
        return StatutoryPayment.objects.filter(company_id=self.request.user.company_id)

    def perform_create(self, serializer):
        check_admin_access(self.request)
        serializer.save(
            company_id=self.request.user.company_id,
            paid_by=self.request.user.user_id
        )


# -----------------------------------------------------------------------------
# 15. PAYROLL REPORTS & REGISTERS (PRD 6.12, Screen 18, AC14.66)
# -----------------------------------------------------------------------------
class PayrollReportView(APIView):
    permission_classes = [IsAuthenticated]
    required_capability = 'payroll.view_reports'

    def get(self, request):
        check_admin_access(request)
        period_ref = request.query_params.get('period_reference')
        runs = PayrollRun.objects.filter(company_id=request.user.company_id)
        if period_ref:
            runs = runs.filter(period_reference=period_ref)

        summary = []
        for r in runs:
            res = r.results.all()
            summary.append({
                "run_id": str(r.run_id),
                "period_reference": r.period_reference,
                "status": r.status,
                "run_type": r.run_type,
                "guards_count": res.count(),
                "total_gross": float(sum(x.gross_earnings for x in res)),
                "total_deductions": float(sum(x.employee_deductions for x in res)),
                "total_net": float(sum(x.net_pay for x in res)),
                "total_employer_contributions": float(sum(x.employer_contributions for x in res))
            })

        return Response({"reports": summary})
