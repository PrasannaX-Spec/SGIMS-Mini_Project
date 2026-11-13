from django.urls import path, include
from rest_framework.routers import DefaultRouter
from foundation import views

router = DefaultRouter()
router.register(r'users', views.UserViewSet, basename='user')
router.register(r'device-change-requests', views.DeviceChangeRequestViewSet, basename='device-change-request')

urlpatterns = [
    # Auth
    path('auth/sign-in/', views.SignInView.as_view(), name='sign-in'),
    path('auth/logout/', views.SignOutView.as_view(), name='logout'),
    path('auth/logout-all/', views.SignOutAllView.as_view(), name='logout-all'),
    path('auth/change-password/', views.ChangePasswordView.as_view(), name='change-password'),
    path('auth/forgot-password/', views.ForgotPasswordView.as_view(), name='forgot-password'),
    path('auth/reset-password/', views.ResetPasswordView.as_view(), name='reset-password'),
    path('auth/me/', views.MyProfileView.as_view(), name='my-profile'),

    # User Management actions
    path('users/<uuid:user_id>/deactivate/', views.UserDeactivateView.as_view(), name='user-deactivate'),
    path('users/<uuid:user_id>/reactivate/', views.UserReactivateView.as_view(), name='user-reactivate'),
    path('users/<uuid:user_id>/reset-password/', views.UserAdminResetPasswordView.as_view(), name='user-admin-reset-password'),
    path('users/<uuid:user_id>/unlock/', views.UserUnlockView.as_view(), name='user-unlock'),
    path('users/<uuid:user_id>/reset-device/', views.UserResetDeviceView.as_view(), name='user-reset-device'),
    path('users/<uuid:user_id>/login-history/', views.UserLoginHistoryView.as_view(), name='user-login-history'),

    # Device change approval/rejection
    path('device-change-requests/<uuid:request_id>/approve/', views.DeviceChangeApproveView.as_view(), name='device-change-approve'),
    path('device-change-requests/<uuid:request_id>/reject/', views.DeviceChangeRejectView.as_view(), name='device-change-reject'),

    # Notifications
    path('notifications/', views.NotificationListView.as_view(), name='notification-list'),
    path('notifications/<uuid:notification_id>/read/', views.NotificationMarkReadView.as_view(), name='notification-read'),
    path('notifications/read-all/', views.NotificationMarkAllReadView.as_view(), name='notification-read-all'),
    path('notifications/deliveries/', views.NotificationDeliveryLogView.as_view(), name='notification-deliveries'),

    # Audit log
    path('audit-log/', views.AuditLogListView.as_view(), name='audit-log-list'),
    path('audit-log/export/', views.AuditLogExportCSVView.as_view(), name='audit-log-export'),

    # System settings
    path('settings/', views.SystemSettingsView.as_view(), name='system-settings'),

    # Legal & Consent
    path('legal/terms/', views.TermsAndConditionsView.as_view(), name='legal-terms'),
    path('legal/privacy/', views.PrivacyPolicyView.as_view(), name='legal-privacy'),
    path('consent/', views.ConsentSubmitView.as_view(), name='consent-submit'),
    path('consent/status/', views.ConsentStatusView.as_view(), name='consent-status'),

    # ViewSet routes
    path('', include(router.urls)),
]

