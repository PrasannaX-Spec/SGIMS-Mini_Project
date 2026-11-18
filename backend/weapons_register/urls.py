from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    WeaponDashboardView, WeaponViewSet, WeaponRevealSerialView,
    WeaponRelabelQRView, WeaponLicenceViewSet, WeaponIssueView,
    WeaponConfirmIssueView, WeaponReturnView, WeaponHandoverView,
    AmmunitionLotViewSet, AmmunitionLedgerViewSet, AmmunitionStockCountView,
    ApproveAmmunitionAdjustmentView, WeaponDiscrepancyViewSet,
    GuardWeaponBlockViewSet, WeaponRecoveryViewSet, DailyCustodySheetView,
    WeaponMaintenanceLogViewSet, MissingWeaponReportView,
    ExportWeaponRegisterView, Module13ReportingView
)

router = DefaultRouter()
router.register(r'records', WeaponViewSet, basename='weapon')
router.register(r'licences', WeaponLicenceViewSet, basename='weapon-licence')
router.register(r'ammo-lots', AmmunitionLotViewSet, basename='ammunition-lot')
router.register(r'ammo-ledger', AmmunitionLedgerViewSet, basename='ammunition-ledger')
router.register(r'discrepancies', WeaponDiscrepancyViewSet, basename='weapon-discrepancy')
router.register(r'blocks', GuardWeaponBlockViewSet, basename='guard-weapon-block')
router.register(r'recoveries', WeaponRecoveryViewSet, basename='weapon-recovery')
router.register(r'maintenance', WeaponMaintenanceLogViewSet, basename='weapon-maintenance')

urlpatterns = [
    # Dashboard & Reporting
    path('dashboard/', WeaponDashboardView.as_view(), name='weapon-dashboard'),
    path('reporting/module13/', Module13ReportingView.as_view(), name='module13-reporting'),
    path('export/', ExportWeaponRegisterView.as_view(), name='export-weapon-register'),

    # Actions on specific weapons
    path('records/<uuid:weapon_id>/reveal-serial/', WeaponRevealSerialView.as_view(), name='weapon-reveal-serial'),
    path('records/<uuid:weapon_id>/relabel-qr/', WeaponRelabelQRView.as_view(), name='weapon-relabel-qr'),

    # Issue, Return, Handover Transfers
    path('transfers/issue/', WeaponIssueView.as_view(), name='weapon-issue'),
    path('transfers/<uuid:transfer_id>/confirm-issue/', WeaponConfirmIssueView.as_view(), name='weapon-confirm-issue'),
    path('transfers/return/', WeaponReturnView.as_view(), name='weapon-return'),
    path('transfers/handover/', WeaponHandoverView.as_view(), name='weapon-handover'),

    # Ammunition Counts & Adjustments
    path('ammo/stock-count/', AmmunitionStockCountView.as_view(), name='ammunition-stock-count'),
    path('ammo/stock-count/<uuid:count_id>/approve/', ApproveAmmunitionAdjustmentView.as_view(), name='approve-ammunition-adjustment'),

    # Daily Custody Sheet & Missing Report
    path('custody-sheet/', DailyCustodySheetView.as_view(), name='daily-custody-sheet'),
    path('missing-stolen-report/', MissingWeaponReportView.as_view(), name='missing-stolen-report'),

    # ViewSet routes
    path('', include(router.urls)),
]
