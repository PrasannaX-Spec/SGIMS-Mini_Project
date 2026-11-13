from django.urls import path
from . import views

urlpatterns = [
    # Slots
    path('slots/generate/', views.SlotGenerationView.as_view(), name='roster-slot-generate'),
    path('slots/', views.SlotListView.as_view(), name='roster-slot-list'),
    path('slots/assign/', views.SlotAssignmentView.as_view(), name='roster-slot-assign'),

    # Assignments
    path('assignments/<uuid:assignment_id>/', views.AssignmentDetailView.as_view(), name='roster-assignment-detail'),
    path('assignments/<uuid:assignment_id>/override-lock/', views.AssignmentLockedOverrideView.as_view(), name='roster-assignment-override-lock'),
    path('assignments/<uuid:assignment_id>/acknowledge/', views.DutyAcknowledgementView.as_view(), name='roster-assignment-acknowledge'),
    path('validate/', views.AssignmentConflictValidationView.as_view(), name='roster-validate'),

    # Publishing
    path('publish/', views.RosterPublishView.as_view(), name='roster-publish'),

    # Replacements & Swaps
    path('replacements/', views.ReplacementAssignmentView.as_view(), name='roster-replacements'),
    path('swaps/', views.ShiftSwapRequestView.as_view(), name='roster-swaps'),
    path('swaps/<uuid:swap_id>/decide/', views.ShiftSwapDecideView.as_view(), name='roster-swap-decide'),

    # Emergency
    path('emergency/', views.EmergencyDeploymentView.as_view(), name='roster-emergency'),
    path('emergency/ratifications/', views.EmergencyRatificationView.as_view(), name='roster-emergency-ratification-list'),
    path('emergency/ratifications/<uuid:ratification_id>/', views.EmergencyRatificationView.as_view(), name='roster-emergency-ratify'),

    # Dashboard & Reporting
    path('coverage-dashboard/', views.CoverageDashboardView.as_view(), name='roster-coverage-dashboard'),
    path('coverage-export/', views.CoverageExportView.as_view(), name='roster-coverage-export'),
    path('my-duties/', views.GuardDutiesView.as_view(), name='roster-my-duties'),
]

