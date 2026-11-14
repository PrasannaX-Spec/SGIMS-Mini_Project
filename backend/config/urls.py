"""
URL configuration for Security Agency ERP.
"""
from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path('admin/', admin.site.urls),

    # OpenAPI schema & Swagger UI
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),

    # Module 1 Foundation API
    path('api/', include('foundation.urls')),

    # Module 2 Master Data API
    path('api/master/', include('master_data.urls')),

    # Module 3 Guard Management API
    path('api/guards/', include('guard_management.urls')),

    # Module 4 Service Request & Quotation API
    path('api/commercials/', include('service_quotation.urls')),

    # Module 5 Deployment & Roster API
    path('api/roster/', include('deployment_roster.urls')),

    # Module 6 Attendance API
    path('api/attendance/', include('attendance.urls')),

    # Module 7 Live Monitoring API
    path('api/monitoring/', include('live_monitoring.urls')),

    # Module 8 Incident and Request Management API
    path('api/incident-mgmt/', include('incident_management.urls')),

    # Module 9 Panic and Escalation API
    path('api/panic-escalation/', include('panic_escalation.urls')),
]
