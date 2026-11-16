from django.urls import path
from . import views

urlpatterns = [
    # Dashboard & Settings
    path('dashboard/', views.BillingDashboardMetricsView.as_view(), name='billing-dashboard'),
    path('settings/company/', views.InvoiceSettingsView.as_view(), name='billing-company-settings'),
    path('settings/clients/', views.ClientBillingSettingsListView.as_view(), name='billing-client-settings-list'),
    path('settings/clients/<uuid:pk>/', views.ClientBillingSettingsDetailView.as_view(), name='billing-client-settings-detail'),

    # Billing Runs & Previews
    path('run/', views.BillingRunView.as_view(), name='billing-run'),
    path('preview/', views.BillingPreviewView.as_view(), name='billing-preview'),

    # Invoices
    path('invoices/', views.ClientInvoiceListView.as_view(), name='billing-invoices-list'),
    path('invoices/<uuid:pk>/', views.ClientInvoiceDetailView.as_view(), name='billing-invoices-detail'),
    path('invoices/<uuid:pk>/lines/manual/', views.ManualLineCreateView.as_view(), name='billing-invoice-manual-line'),
    path('invoices/<uuid:pk>/issue/', views.InvoiceIssueView.as_view(), name='billing-invoice-issue'),
    path('invoices/<uuid:pk>/cancel/', views.InvoiceCancelView.as_view(), name='billing-invoice-cancel'),
    path('invoices/<uuid:pk>/replacement/', views.InvoiceReplacementCreateView.as_view(), name='billing-invoice-replacement'),
    path('invoices/<uuid:pk>/annexure/', views.InvoiceAnnexureView.as_view(), name='billing-invoice-annexure'),
    path('invoices/<uuid:pk>/query/', views.InvoiceQueryRaiseView.as_view(), name='billing-invoice-query'),

    # Payments & Receivables
    path('invoices/<uuid:pk>/payments/', views.PaymentRecordView.as_view(), name='billing-record-payment'),
    path('payments/<uuid:pk>/reverse/', views.PaymentReversalView.as_view(), name='billing-payment-reverse'),
    path('receivables/ageing/', views.ReceivablesAgeingView.as_view(), name='billing-receivables-ageing'),

    # CSV Exports
    path('exports/invoices/', views.InvoiceExportCSVView.as_view(), name='billing-export-invoices'),
    path('exports/payments/', views.PaymentExportCSVView.as_view(), name='billing-export-payments'),
]
