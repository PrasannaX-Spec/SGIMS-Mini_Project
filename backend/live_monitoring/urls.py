from django.urls import path
from . import views

urlpatterns = [
    # Duties
    path('duties/start/', views.StartMonitoringDutyView.as_view(), name='monitoring-duty-start'),
    path('duties/stop/', views.StopMonitoringDutyView.as_view(), name='monitoring-duty-stop'),

    # Telemetry Ingestion
    path('locations/batch/', views.LocationBatchIngestView.as_view(), name='monitoring-locations-batch'),
    path('heartbeats/', views.HeartbeatIngestView.as_view(), name='monitoring-heartbeats'),

    # Console Views
    path('live-map/', views.LiveMonitoringMapView.as_view(), name='monitoring-live-map'),
    path('status-board/', views.MonitoringStatusBoardView.as_view(), name='monitoring-status-board'),
    path('guards/<uuid:guard_id>/detail/', views.GuardDetailView.as_view(), name='monitoring-guard-detail'),
    path('guards/<uuid:guard_id>/trail/', views.GuardDutyTrailView.as_view(), name='monitoring-guard-trail'),
    path('guards/<uuid:guard_id>/historical-trail/', views.GuardHistoricalTrailView.as_view(), name='monitoring-historical-trail'),
    path('sites/<uuid:site_id>/overview/', views.SiteOverviewView.as_view(), name='monitoring-site-overview'),

    # Alerts Lifecycle
    path('alerts/', views.MonitoringAlertListView.as_view(), name='monitoring-alerts-list'),
    path('alerts/<uuid:alert_id>/acknowledge/', views.MonitoringAlertAcknowledgeView.as_view(), name='monitoring-alert-acknowledge'),
    path('alerts/<uuid:alert_id>/resolve/', views.MonitoringAlertResolveView.as_view(), name='monitoring-alert-resolve'),
    path('alerts/<uuid:alert_id>/dismiss/', views.MonitoringAlertDismissView.as_view(), name='monitoring-alert-dismiss'),

    # Supervisor Ping
    path('pings/send/', views.SupervisorPingSendView.as_view(), name='monitoring-ping-send'),
    path('pings/<uuid:ping_id>/respond/', views.SupervisorPingRespondView.as_view(), name='monitoring-ping-respond'),

    # Configurations
    path('config/', views.TrackingConfigView.as_view(), name='monitoring-config'),

    # Module 10 Client Safe View
    path('client-safe/', views.ClientSafeMonitoringView.as_view(), name='monitoring-client-safe'),

    # Downstream Module Queries (Module 9, Module 8)
    path('query/last-known-position/', views.LastKnownPositionQueryView.as_view(), name='monitoring-query-last-position'),
    path('query/position-at-time/', views.PositionAtTimeQueryView.as_view(), name='monitoring-query-position-at-time'),
]

