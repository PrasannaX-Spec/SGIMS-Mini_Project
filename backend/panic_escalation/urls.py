from django.urls import path
from panic_escalation import views

app_name = 'panic_escalation'

urlpatterns = [
    # 1. Panic Alerts Lifecycle
    path('alerts/', views.PanicAlertListCreateView.as_view(), name='alert-list-create'),
    path('alerts/<uuid:alert_id>/', views.PanicAlertDetailView.as_view(), name='alert-detail'),
    path('alerts/<uuid:alert_id>/acknowledge/', views.PanicAcknowledgeView.as_view(), name='alert-acknowledge'),
    path('alerts/<uuid:alert_id>/positions/', views.PanicPositionUpdateView.as_view(), name='alert-positions'),
    path('alerts/<uuid:alert_id>/actions/', views.PanicResponderActionView.as_view(), name='alert-actions'),
    path('alerts/<uuid:alert_id>/are-you-safe/', views.PanicAreYouSafePromptView.as_view(), name='alert-are-you-safe'),
    path('alerts/<uuid:alert_id>/respond-safe/', views.PanicAreYouSafeResponseView.as_view(), name='alert-respond-safe'),
    path('alerts/<uuid:alert_id>/false-alarm/', views.PanicFalseAlarmReportView.as_view(), name='alert-false-alarm'),
    path('alerts/<uuid:alert_id>/confirm-false-alarm/', views.PanicFalseAlarmConfirmView.as_view(), name='alert-confirm-false-alarm'),
    path('alerts/<uuid:alert_id>/resolve/', views.PanicResolveView.as_view(), name='alert-resolve'),
    path('alerts/<uuid:alert_id>/review/', views.PanicAdminReviewView.as_view(), name='alert-admin-review'),
    path('alerts/<uuid:alert_id>/welfare-followup/', views.PanicWelfareFollowupView.as_view(), name='alert-welfare-followup'),
    path('alerts/<uuid:alert_id>/timeline/', views.PanicTimelineView.as_view(), name='alert-timeline'),
    path('alerts/<uuid:alert_id>/link-incident/', views.PanicCreateIncidentLinkView.as_view(), name='alert-link-incident'),
    path('alerts/<uuid:alert_id>/report/', views.PanicReportExportView.as_view(), name='alert-report-export'),

    # 2. Configuration & Monitoring
    path('config/', views.PanicEscalationConfigView.as_view(), name='escalation-config'),
    path('delivery-monitoring/', views.PanicDeliveryMonitoringView.as_view(), name='delivery-monitoring'),
    path('device-readiness/', views.PanicDeviceReadinessView.as_view(), name='device-readiness'),
    path('drills/', views.PanicDrillListCreateView.as_view(), name='drills-list-create'),

    # 3. Inter-Module Interfaces (Module 10 Client, Module 13 Metrics)
    path('client-safe/', views.ClientSafePanicView.as_view(), name='client-safe-panic'),
    path('metrics/', views.PanicMetricsQueryView.as_view(), name='panic-metrics'),
]
