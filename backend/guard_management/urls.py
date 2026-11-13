from django.urls import path
from guard_management import views

urlpatterns = [
    # Dashboard & Guard CRUD
    path('dashboard/', views.GuardDashboardView.as_view(), name='guard-dashboard'),
    path('', views.GuardListView.as_view(), name='guard-list'),
    path('<uuid:employee_id>/', views.GuardDetailView.as_view(), name='guard-detail'),

    # Lifecycle Status Transition
    path('<uuid:employee_id>/status/', views.GuardStatusChangeView.as_view(), name='guard-status-change'),

    # Documents & Verification
    path('<uuid:employee_id>/documents/', views.GuardDocumentUploadView.as_view(), name='guard-document-upload'),
    path('documents/<uuid:document_id>/verify/', views.GuardDocumentVerifyView.as_view(), name='guard-document-verify'),

    # Training & Checks
    path('<uuid:employee_id>/training/', views.GuardTrainingCreateView.as_view(), name='guard-training-create'),
    path('<uuid:employee_id>/checks/', views.GuardCheckCreateView.as_view(), name='guard-check-create'),

    # Sensitive Bank Details
    path('<uuid:employee_id>/bank/', views.GuardBankUpdateView.as_view(), name='guard-bank-update'),
    path('<uuid:employee_id>/reveal-bank/', views.GuardBankRevealView.as_view(), name='guard-bank-reveal'),

    # Account Linking
    path('<uuid:employee_id>/create-account/', views.GuardAccountCreateView.as_view(), name='guard-account-create'),

    # Deployability Evaluation
    path('<uuid:employee_id>/deployability/', views.GuardDeployabilityCheckView.as_view(), name='guard-deployability-check'),

    # Leave & Unavailability
    path('<uuid:employee_id>/unavailability/', views.GuardUnavailabilityView.as_view(), name='guard-unavailability-request'),
    path('unavailability/<uuid:leave_id>/decide/', views.GuardUnavailabilityDecideView.as_view(), name='guard-unavailability-decide'),

    # Disciplinary & ID Card
    path('<uuid:employee_id>/disciplinary/', views.GuardDisciplinaryCreateView.as_view(), name='guard-disciplinary-create'),
    path('<uuid:employee_id>/id-card/', views.GuardIdCardGenerateView.as_view(), name='guard-id-card-generate'),
]

