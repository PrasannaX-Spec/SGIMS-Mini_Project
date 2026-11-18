"""
URL configuration for Security Agency ERP.
"""
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

def api_root(request):
    return JsonResponse({
        "status": "online",
        "service": "Security Agency Management and Monitoring System (SGIMS) API",
        "version": "1.0",
        "frontend_url": "http://127.0.0.1:5173",
        "api_documentation": "/api/docs/",
        "message": "Backend API is running. Access the web console at http://127.0.0.1:5173 or interactive Swagger docs at /api/docs/."
    })

urlpatterns = [
    path('', api_root, name='api-root'),
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

    # Module 10 Client Portal API
    path('api/portal/', include('client_portal.urls')),

    # Module 11 Billing & Invoices API
    path('api/billing/', include('billing_invoices.urls')),

    # Module 12 Armed Guard and Weapons Register API
    path('api/weapons/', include('weapons_register.urls')),
]
