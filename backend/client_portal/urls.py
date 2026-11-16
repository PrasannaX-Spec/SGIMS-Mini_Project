from django.urls import path
from client_portal import views

urlpatterns = [
    # Client Portal Main & Navigation
    path('dashboard/', views.ClientDashboardView.as_view(), name='portal-dashboard'),
    path('sites/', views.ClientSitesListView.as_view(), name='portal-sites'),

    # Deployment & Guard Status
    path('deployment/', views.ClientDeploymentView.as_view(), name='portal-deployment'),
    path('guards/<uuid:guard_id>/safe-card/', views.ClientGuardSafeCardView.as_view(), name='portal-guard-card'),
    path('report-post-issue/', views.ClientReportPostIssueView.as_view(), name='portal-report-post-issue'),

    # Attendance Views & Exports
    path('attendance/today/', views.ClientAttendanceTodayView.as_view(), name='portal-attendance-today'),
    path('attendance/approved/', views.ClientAttendanceApprovedView.as_view(), name='portal-attendance-approved'),
    path('attendance/monthly-download/', views.ClientAttendanceMonthlyDownloadView.as_view(), name='portal-attendance-download'),
    path('attendance/query/', views.ClientAttendanceQueryView.as_view(), name='portal-attendance-query'),

    # Shared Incidents & Emergencies
    path('incidents/', views.ClientSharedIncidentsListView.as_view(), name='portal-incidents'),
    path('incidents/<uuid:version_id>/comment/', views.ClientSharedIncidentCommentView.as_view(), name='portal-incident-comment'),
    path('panic/status/', views.ClientPanicStatusView.as_view(), name='portal-panic-status'),
    path('panic/<uuid:panic_id>/acknowledge/', views.ClientPanicAcknowledgeView.as_view(), name='portal-panic-acknowledge'),

    # Documents & Invoices
    path('documents/', views.ClientDocumentsListView.as_view(), name='portal-documents'),
    path('invoices/', views.ClientInvoicesListView.as_view(), name='portal-invoices'),

    # Tickets & Agency Contacts
    path('tickets/', views.ClientTicketsListView.as_view(), name='portal-tickets'),
    path('tickets/<uuid:ticket_id>/', views.ClientTicketDetailView.as_view(), name='portal-ticket-detail'),
    path('agency-contact/', views.ClientAgencyContactView.as_view(), name='portal-agency-contact'),
    path('preferences/', views.ClientNotificationPreferencesView.as_view(), name='portal-preferences'),

    # Admin Management & Preview
    path('admin/users/', views.AdminClientUsersListView.as_view(), name='admin-portal-users'),
    path('admin/users/<uuid:user_id>/site-access/', views.AdminClientSiteAccessConfigView.as_view(), name='admin-portal-site-access'),
    path('admin/configuration/', views.AdminClientPortalConfigView.as_view(), name='admin-portal-config'),
    path('admin/preview/', views.AdminClientPreviewView.as_view(), name='admin-portal-preview'),
    path('admin/usage/', views.AdminPortalUsageView.as_view(), name='admin-portal-usage'),
    path('admin/announcements/', views.AdminAnnouncementsView.as_view(), name='admin-portal-announcements'),
]
