from django.urls import path
from incident_management import views

urlpatterns = [
    # Unified Inbox
    path('inbox/', views.UnifiedInboxView.as_view(), name='unified-inbox'),

    # Incidents Core
    path('incidents/', views.IncidentCreateView.as_view(), name='incident-create'),
    path('incidents/<uuid:incident_id>/', views.IncidentDetailView.as_view(), name='incident-detail'),
    path('incidents/<uuid:incident_id>/addendum/', views.IncidentAddendumCreateView.as_view(), name='incident-addendum'),
    path('incidents/<uuid:incident_id>/acknowledge/', views.IncidentAcknowledgeView.as_view(), name='incident-acknowledge'),
    path('incidents/<uuid:incident_id>/classify/', views.IncidentClassificationUpdateView.as_view(), name='incident-classify'),
    path('incidents/<uuid:incident_id>/escalate/', views.IncidentEscalateView.as_view(), name='incident-escalate'),
    path('incidents/<uuid:incident_id>/resolve/', views.IncidentResolveView.as_view(), name='incident-resolve'),
    path('incidents/<uuid:incident_id>/close/', views.IncidentCloseView.as_view(), name='incident-close'),
    path('incidents/<uuid:incident_id>/reopen/', views.IncidentReopenView.as_view(), name='incident-reopen'),
    path('incidents/<uuid:incident_id>/reject/', views.IncidentRejectView.as_view(), name='incident-reject'),
    path('incidents/<uuid:incident_id>/link/', views.IncidentLinkView.as_view(), name='incident-link'),
    path('incidents/<uuid:incident_id>/client-share/', views.IncidentClientVersionView.as_view(), name='incident-client-share'),
    path('incidents/<uuid:incident_id>/tasks/', views.IncidentFollowUpTaskView.as_view(), name='incident-tasks'),

    # Attachments
    path('attachments/<uuid:attachment_id>/verify/', views.IncidentAttachmentVerifyView.as_view(), name='attachment-verify'),

    # Guard Requests
    path('requests/', views.GuardRequestListCreateView.as_view(), name='guard-request-list'),
    path('requests/<uuid:request_id>/action/', views.GuardRequestActionView.as_view(), name='guard-request-action'),

    # Client Tickets
    path('tickets/', views.ClientTicketListCreateView.as_view(), name='client-ticket-list'),
    path('tickets/<uuid:ticket_id>/message/', views.ClientTicketMessageView.as_view(), name='client-ticket-message'),

    # Taxonomies
    path('categories/', views.CategoryListView.as_view(), name='category-list'),
    path('request-types/', views.RequestTypeListView.as_view(), name='request-type-list'),
    path('outcomes/', views.ResolutionOutcomeListView.as_view(), name='outcome-list'),

    # Analytics & Exports
    path('aging-dashboard/', views.AgingDashboardView.as_view(), name='aging-dashboard'),
    path('export/csv/', views.ExportCSVMetadataView.as_view(), name='export-csv'),

    # Inter-Module Interfaces
    path('panic-intake/', views.PanicIncidentIntakeView.as_view(), name='panic-intake'),
    path('client-shared/', views.ClientSharedIncidentsView.as_view(), name='client-shared'),
    path('metrics/', views.IncidentMetricsQueryView.as_view(), name='incident-metrics'),
]
