from django.urls import path
from . import views

urlpatterns = [
    # Dashboard & List
    path('dashboard/', views.AttendanceDashboardView.as_view(), name='attendance-dashboard'),
    path('records/', views.AttendanceRecordListView.as_view(), name='attendance-record-list'),
    path('records/<uuid:attendance_id>/', views.AttendanceRecordDetailView.as_view(), name='attendance-record-detail'),

    # Captures
    path('check-in/', views.CheckInView.as_view(), name='attendance-check-in'),
    path('check-out/', views.CheckOutView.as_view(), name='attendance-check-out'),
    path('handover/', views.AttendanceHandoverView.as_view(), name='attendance-handover'),

    # Approvals & Actions
    path('records/<uuid:attendance_id>/approve/', views.AttendanceApproveView.as_view(), name='attendance-approve'),
    path('records/bulk-approve/', views.AttendanceBulkApproveView.as_view(), name='attendance-bulk-approve'),
    path('records/<uuid:attendance_id>/reject/', views.AttendanceRejectView.as_view(), name='attendance-reject'),
    path('records/<uuid:attendance_id>/correct/', views.AttendanceCorrectView.as_view(), name='attendance-correct'),
    path('records/<uuid:attendance_id>/mark-absent/', views.AttendanceMarkAbsentView.as_view(), name='attendance-mark-absent'),

    # Regularisation
    path('regularisations/', views.AttendanceRegularisationView.as_view(), name='attendance-regularisations'),
    path('regularisations/<uuid:request_id>/decide/', views.AttendanceRegularisationDecideView.as_view(), name='attendance-regularisation-decide'),

    # Period Closing & Locking
    path('periods/', views.AttendancePeriodView.as_view(), name='attendance-periods'),
    path('periods/<uuid:period_id>/reopen/', views.AttendancePeriodReopenView.as_view(), name='attendance-period-reopen'),

    # Export & Client Safe
    path('export/', views.AttendanceExportView.as_view(), name='attendance-export'),
    path('client-safe/', views.ClientSafeAttendanceView.as_view(), name='attendance-client-safe'),
]

