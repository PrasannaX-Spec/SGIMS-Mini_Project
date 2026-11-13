from django.urls import path
from master_data import views

urlpatterns = [
    # Company Profile
    path('company/', views.CompanyProfileView.as_view(), name='master-company-profile'),

    # Clients
    path('clients/', views.ClientListView.as_view(), name='master-client-list'),
    path('clients/<uuid:client_id>/', views.ClientDetailView.as_view(), name='master-client-detail'),
    path('clients/<uuid:client_id>/contacts/', views.ClientContactCreateView.as_view(), name='master-client-contact-create'),
    path('clients/import-csv/', views.ClientCsvImportView.as_view(), name='master-client-csv-import'),

    # Sites
    path('sites/', views.SiteListView.as_view(), name='master-site-list'),
    path('sites/<uuid:site_id>/', views.SiteDetailView.as_view(), name='master-site-detail'),
    path('sites/<uuid:site_id>/geofence/', views.SiteGeofenceUpdateView.as_view(), name='master-site-geofence-update'),
    path('sites/<uuid:site_id>/supervisor/', views.SiteSupervisorAssignView.as_view(), name='master-site-supervisor-assign'),

    # Post types & Shifts
    path('post-types/', views.PostTypeListView.as_view(), name='master-post-type-list'),
    path('sites/<uuid:site_id>/shifts/', views.SiteShiftListView.as_view(), name='master-site-shift-list'),

    # Manpower requirements
    path('sites/<uuid:site_id>/requirements/', views.SiteManpowerRequirementListView.as_view(), name='master-site-requirement-list'),

    # Service agreements
    path('agreements/', views.ServiceAgreementListView.as_view(), name='master-agreement-list'),

    # Billing rates
    path('billing-rates/', views.ClientBillingRateListView.as_view(), name='master-billing-rate-list'),
    path('billing-rates/resolve/', views.BillingRateResolveView.as_view(), name='master-billing-rate-resolve'),
]

