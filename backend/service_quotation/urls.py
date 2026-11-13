from django.urls import path
from . import views

urlpatterns = [
    # Service Requests
    path('requests/', views.ServiceRequestListView.as_view(), name='service-request-list'),
    path('requests/<uuid:request_id>/', views.ServiceRequestDetailView.as_view(), name='service-request-detail'),
    path('requests/<uuid:request_id>/withdraw/', views.ServiceRequestWithdrawView.as_view(), name='service-request-withdraw'),
    path('requests/<uuid:request_id>/clarify/', views.ServiceRequestClarifyView.as_view(), name='service-request-clarify'),
    path('requests/<uuid:request_id>/survey/', views.ServiceSiteSurveyView.as_view(), name='service-request-survey'),

    # Quotations
    path('quotes/', views.QuotationListView.as_view(), name='quotation-list'),
    path('quotes/create/', views.QuotationCreateView.as_view(), name='quotation-create'),
    path('quotes/<uuid:quotation_id>/', views.QuotationDetailView.as_view(), name='quotation-detail'),
    path('quotes/<uuid:quotation_id>/revise/', views.QuotationReviseView.as_view(), name='quotation-revise'),
    path('quotes/versions/<uuid:version_id>/send/', views.QuotationSendView.as_view(), name='quotation-send'),
    path('quotes/versions/<uuid:version_id>/accept/', views.QuotationAcceptView.as_view(), name='quotation-accept'),
    path('quotes/versions/<uuid:version_id>/reject/', views.QuotationRejectView.as_view(), name='quotation-reject'),
    path('quotes/versions/<uuid:version_id>/counter/', views.QuotationCounterView.as_view(), name='quotation-counter'),
    path('quotes/versions/<uuid:version_id>/convert/', views.QuotationConvertView.as_view(), name='quotation-convert'),
]
