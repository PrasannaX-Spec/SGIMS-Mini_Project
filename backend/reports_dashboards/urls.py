from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'presets', views.SavedFilterPresetViewSet, basename='preset')
router.register(r'client-summaries', views.ClientMonthlySummaryViewSet, basename='client-summary')

urlpatterns = [
    # Dashboards
    path('dashboard/admin/', views.AdminOverviewDashboardView.as_view(), name='admin-dashboard'),
    path('dashboard/supervisor/', views.SupervisorDashboardView.as_view(), name='supervisor-dashboard'),
    path('data-health/', views.DataHealthPanelView.as_view(), name='data-health'),

    # Metric Dictionary & Versions
    path('metrics/', views.MetricDictionaryListView.as_view(), name='metric-dictionary'),
    path('metrics/<str:metric_id>/versions/', views.MetricDefinitionVersionView.as_view(), name='metric-versions'),
    path('metrics/<str:metric_id>/propose-version/', views.MetricDefinitionVersionView.as_view(), name='propose-metric-version'),

    # Report Catalogue & Drill-Down Details
    path('catalogue/', views.ReportCatalogueListView.as_view(), name='report-catalogue'),
    path('detail/<str:report_code>/', views.ReportDetailView.as_view(), name='report-detail'),

    # Exports & Audit
    path('export/csv/', views.ReportExportCSVView.as_view(), name='export-csv'),
    path('export/pdf/', views.ReportExportPDFView.as_view(), name='export-pdf'),
    path('export-history/', views.ExportHistoryListView.as_view(), name='export-history'),

    # Reconciliation
    path('reconciliation/', views.ReportReconciliationView.as_view(), name='reconciliation'),

    # Client Monthly Summaries
    path('client-summaries/client-safe/', views.ClientSafeMonthlySummaryView.as_view(), name='client-safe-summaries'),
    path('client-summaries/<uuid:summary_id>/release/', views.ReleaseClientSummaryView.as_view(), name='release-client-summary'),

    # ViewSets
    path('', include(router.urls)),
]
