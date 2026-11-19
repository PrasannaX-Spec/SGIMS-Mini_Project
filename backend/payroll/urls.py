from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    PayrollDashboardView, PayrollPreRunChecklistView,
    SalaryComponentViewSet, SalaryStructureViewSet,
    GuardSalaryAssignmentViewSet, BulkSalaryAssignmentView,
    MinimumWageViewSet, PaidDayRuleViewSet, WeeklyOffCalendarViewSet,
    StatutoryRuleSetViewSet, StatutoryRuleApproveView,
    AdvanceViewSet, ManualDeductionViewSet, PayrollRunViewSet,
    PayrollRunCalculateView, PayrollRunApproveView,
    PayrollRunReleaseView, PayrollRunCancelView,
    PayrollRunExportBankFileView, PayrollResultViewSet,
    PayslipViewSet, PaymentRecordViewSet, PaymentReversalView,
    FinalSettlementViewSet, FinalSettlementSecondApproveView,
    StatutoryPaymentViewSet, PayrollReportView
)

router = DefaultRouter()
router.register(r'components', SalaryComponentViewSet, basename='salary-components')
router.register(r'structures', SalaryStructureViewSet, basename='salary-structures')
router.register(r'assignments', GuardSalaryAssignmentViewSet, basename='guard-assignments')
router.register(r'minimum-wages', MinimumWageViewSet, basename='minimum-wages')
router.register(r'paid-day-rules', PaidDayRuleViewSet, basename='paid-day-rules')
router.register(r'calendars', WeeklyOffCalendarViewSet, basename='weekly-off-calendars')
router.register(r'statutory-rules', StatutoryRuleSetViewSet, basename='statutory-rules')
router.register(r'advances', AdvanceViewSet, basename='payroll-advances')
router.register(r'deductions', ManualDeductionViewSet, basename='manual-deductions')
router.register(r'runs', PayrollRunViewSet, basename='payroll-runs')
router.register(r'results', PayrollResultViewSet, basename='payroll-results')
router.register(r'payslips', PayslipViewSet, basename='payroll-payslips')
router.register(r'payments', PaymentRecordViewSet, basename='payroll-payments')
router.register(r'final-settlements', FinalSettlementViewSet, basename='final-settlements')
router.register(r'statutory-payments', StatutoryPaymentViewSet, basename='statutory-payments')

urlpatterns = [
    # Dashboard & Checklist
    path('dashboard/', PayrollDashboardView.as_view(), name='payroll-dashboard'),
    path('checklist/', PayrollPreRunChecklistView.as_view(), name='payroll-checklist'),

    # Actions
    path('assignments/bulk/', BulkSalaryAssignmentView.as_view(), name='bulk-salary-assignment'),
    path('statutory-rules/<uuid:pk>/approve/', StatutoryRuleApproveView.as_view(), name='statutory-rule-approve'),
    path('runs/<uuid:pk>/calculate/', PayrollRunCalculateView.as_view(), name='payroll-run-calculate'),
    path('runs/<uuid:pk>/approve/', PayrollRunApproveView.as_view(), name='payroll-run-approve'),
    path('runs/<uuid:pk>/release/', PayrollRunReleaseView.as_view(), name='payroll-run-release'),
    path('runs/<uuid:pk>/cancel/', PayrollRunCancelView.as_view(), name='payroll-run-cancel'),
    path('runs/<uuid:pk>/export-bank-file/', PayrollRunExportBankFileView.as_view(), name='payroll-run-bank-file'),
    path('payments/<uuid:pk>/reverse/', PaymentReversalView.as_view(), name='payment-reverse'),
    path('final-settlements/<uuid:pk>/second-approve/', FinalSettlementSecondApproveView.as_view(), name='final-settlement-second-approve'),
    path('reports/', PayrollReportView.as_view(), name='payroll-reports'),

    # Router URLs
    path('', include(router.urls)),
]
