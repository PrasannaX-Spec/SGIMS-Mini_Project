import csv
import io
import uuid
from datetime import date, datetime, timedelta
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from django.db.models import Sum, Q, Count
from rest_framework import status, viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, NotFound, ValidationError

from foundation.services.scope_service import HasCapabilityAndScope
from foundation.services.audit_service import write_audit_event
from master_data.models import SiteSupervisorAssignment

from .models import (
    WeaponLocation, WeaponLicence, Weapon, WeaponLicenceAssociation,
    WeaponSerialRevealLog, WeaponTransfer, WeaponCustodyRecord,
    AmmunitionLot, AmmunitionLedger, AmmunitionStockCount,
    WeaponDiscrepancy, GuardWeaponBlock, WeaponRecovery,
    WeaponMaintenanceLog, WeaponAlert
)
from .serializers import (
    WeaponLocationSerializer, WeaponLicenceSerializer, WeaponSerializer,
    WeaponCreateSerializer, WeaponTransferSerializer, WeaponCustodyRecordSerializer,
    AmmunitionLotSerializer, AmmunitionLedgerSerializer, AmmunitionStockCountSerializer,
    WeaponDiscrepancySerializer, GuardWeaponBlockSerializer, WeaponRecoverySerializer,
    WeaponMaintenanceLogSerializer, WeaponAlertSerializer
)
from .services import (
    generate_weapon_asset_id, calculate_ammunition_stock,
    validate_issue_eligibility, initiate_weapon_issue,
    confirm_weapon_issue_by_guard, process_weapon_return,
    process_guard_handover, report_missing_or_stolen_weapon,
    check_out_custody_validation, panic_custody_query
)


def get_supervisor_site_ids(user):
    """Returns list of site_ids assigned to this supervisor."""
    return list(
        SiteSupervisorAssignment.objects.filter(
            supervisor_user_id=user.user_id, is_active=True
        ).values_list('site_id', flat=True)
    )


# -----------------------------------------------------------------------------
# 1. WEAPON DASHBOARD (PRD Screen 1, FR-12.240)
# -----------------------------------------------------------------------------
class WeaponDashboardView(APIView):
    permission_classes = [IsAuthenticated]
    required_capability = 'weapons.view'

    def get(self, request):
        user = request.user
        if user.role == 'CLIENT':
            raise PermissionDenied("Clients have no access to weapon management.")

        company_id = user.company_id
        today = date.today()

        qs = Weapon.objects.filter(company_id=company_id, is_active=True)
        if user.role == 'SUPERVISOR':
            assigned_sites = get_supervisor_site_ids(user)
            # Supervisor sees weapons at assigned sites or armoury
            armoury_ids = WeaponLocation.objects.filter(
                company_id=company_id, location_type='ARMOURY'
            ).values_list('location_id', flat=True)
            site_loc_ids = WeaponLocation.objects.filter(
                site_id__in=assigned_sites
            ).values_list('location_id', flat=True)
            allowed_locs = list(armoury_ids) + list(site_loc_ids)
            qs = qs.filter(Q(current_location_id__in=allowed_locs) | Q(status='ISSUED'))

        total_weapons = qs.count()

        # By status
        status_counts = {}
        for s, _ in Weapon.STATUS_CHOICES:
            status_counts[s] = qs.filter(status=s).count()

        # Active custody count
        active_custody_count = WeaponCustodyRecord.objects.filter(
            weapon_id__in=qs.values_list('weapon_id', flat=True),
            is_current=True,
            custodian_type='GUARD'
        ).count()

        # Open discrepancies
        open_discrepancies = WeaponDiscrepancy.objects.filter(
            company_id=company_id, status__in=['OPEN', 'UNDER_REVIEW']
        ).count()

        # Expiring licences (within 60 days)
        expiring_licences = WeaponLicence.objects.filter(
            company_id=company_id,
            valid_until__gte=today,
            valid_until__lte=today + timedelta(days=60)
        ).count()

        # Expired licences
        expired_licences = WeaponLicence.objects.filter(
            company_id=company_id,
            valid_until__lt=today
        ).count()

        # Recovery Required count
        recovery_required = WeaponRecovery.objects.filter(
            company_id=company_id, status='RECOVERY_REQUIRED'
        ).count()

        # Pending confirmations
        pending_confirmations = WeaponTransfer.objects.filter(
            company_id=company_id, status__in=['ISSUE_PENDING', 'RETURN_PENDING', 'HANDOVER_PENDING']
        ).count()

        return Response({
            'total_weapons': total_weapons,
            'status_counts': status_counts,
            'active_custody_count': active_custody_count,
            'open_discrepancies': open_discrepancies,
            'expiring_licences': expiring_licences,
            'expired_licences': expired_licences,
            'recovery_required': recovery_required,
            'pending_confirmations': pending_confirmations,
        })


# -----------------------------------------------------------------------------
# 2. WEAPON MASTER VIEWSET (PRD Screens 2, 3, 4)
# -----------------------------------------------------------------------------
class WeaponViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = WeaponSerializer
    required_capability = 'weapons.manage'

    def get_queryset(self):
        user = self.request.user
        if user.role == 'CLIENT':
            raise PermissionDenied("Clients have no access to weapon register.")
        if user.role == 'GUARD':
            # Guards can only view weapon currently in their custody
            my_custody = WeaponCustodyRecord.objects.filter(
                custodian_type='GUARD', custodian_id=user.user_id, is_current=True
            ).values_list('weapon_id', flat=True)
            return Weapon.objects.filter(weapon_id__in=my_custody, is_active=True)

        qs = Weapon.objects.filter(company_id=user.company_id, is_active=True)
        if user.role == 'SUPERVISOR':
            assigned_sites = get_supervisor_site_ids(user)
            armoury_ids = WeaponLocation.objects.filter(
                company_id=user.company_id, location_type='ARMOURY'
            ).values_list('location_id', flat=True)
            site_loc_ids = WeaponLocation.objects.filter(
                site_id__in=assigned_sites
            ).values_list('location_id', flat=True)
            allowed_locs = list(armoury_ids) + list(site_loc_ids)
            qs = qs.filter(Q(current_location_id__in=allowed_locs) | Q(status='ISSUED'))

        status_param = self.request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)

        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(asset_id__icontains=search) |
                Q(make__icontains=search) |
                Q(model__icontains=search) |
                Q(calibre__icontains=search) |
                Q(serial_number__icontains=search)
            )

        return qs.order_by('-created_at')

    def create(self, request, *args, **kwargs):
        if request.user.role not in ['ADMIN', 'SUPER_ADMIN']:
            raise PermissionDenied("Only Admin may create new weapon records.")

        company_id = request.user.company_id
        ser = WeaponCreateSerializer(data=request.data, context={'company_id': company_id})
        ser.is_valid(raise_exception=True)

        data = ser.validated_data
        licence_id = data.pop('licence_id', None)
        data.pop('serial_number_confirm', None)

        asset_id = generate_weapon_asset_id(company_id)

        # Default to Central Armoury if location not provided
        loc_id = data.get('current_location_id')
        if not loc_id:
            armoury = WeaponLocation.objects.filter(company_id=company_id, location_type='ARMOURY').first()
            if armoury:
                loc_id = armoury.location_id
                data['current_location_id'] = loc_id

        weapon = Weapon.objects.create(
            company_id=company_id,
            asset_id=asset_id,
            created_by=request.user.user_id,
            status_reason="Initial registration into system",
            **data
        )

        # Link licence if provided
        if licence_id:
            WeaponLicenceAssociation.objects.create(
                weapon_id=weapon.weapon_id,
                licence_id=licence_id,
                created_by=request.user.user_id,
                is_current=True
            )

        # Create initial custody record in Location
        if loc_id:
            custody = WeaponCustodyRecord.objects.create(
                weapon_id=weapon.weapon_id,
                custodian_type='LOCATION',
                custodian_id=loc_id,
                is_current=True,
                ammunition_rounds=0
            )
            weapon.current_custody_id = custody.custody_id
            weapon.save()

        try:
            write_audit_event(
                action_code='WEAPON_CREATED',
                actor_user=request.user,
                company_id=company_id,
                module='weapons_register',
                entity_name='Weapon',
                entity_id=str(weapon.weapon_id),
                payload={'asset_id': weapon.asset_id, 'make': weapon.make, 'model': weapon.model}
            )
        except Exception:
            pass

        out_ser = WeaponSerializer(weapon, context={'request': request})
        return Response(out_ser.data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        # Physical deletion is strictly prohibited (FR-12.18, AC-12.4)
        raise ValidationError({"detail": "Physical deletion of weapon records is prohibited. Update status to 'RETIRED_OR_DISPOSED' instead."})


# -----------------------------------------------------------------------------
# 3. REVEAL SERIAL NUMBER VIEW (PRD 7.4, AC-12.68)
# -----------------------------------------------------------------------------
class WeaponRevealSerialView(APIView):
    permission_classes = [IsAuthenticated]
    required_capability = 'weapons.manage'

    def post(self, request, weapon_id):
        user = request.user
        if user.role not in ['ADMIN', 'SUPER_ADMIN', 'SUPERVISOR']:
            raise PermissionDenied("Access denied.")

        reason = request.data.get('reason')
        if not reason:
            raise ValidationError({"reason": "A mandatory reason is required to reveal the serial number."})

        weapon = Weapon.objects.filter(weapon_id=weapon_id, company_id=user.company_id).first()
        if not weapon:
            raise NotFound("Weapon not found.")

        # Log reveal event
        WeaponSerialRevealLog.objects.create(
            company_id=user.company_id,
            weapon_id=weapon.weapon_id,
            revealed_by=user.user_id,
            reason=reason
        )

        try:
            write_audit_event(
                action_code='WEAPON_SERIAL_REVEALED',
                actor_user=user,
                company_id=user.company_id,
                module='weapons_register',
                entity_name='Weapon',
                entity_id=str(weapon.weapon_id),
                payload={'asset_id': weapon.asset_id, 'reason': reason}
            )
        except Exception:
            pass

        return Response({
            'asset_id': weapon.asset_id,
            'serial_number': weapon.serial_number,
            'revealed_at': timezone.now().isoformat()
        })


# -----------------------------------------------------------------------------
# 4. QR RELABELING (PRD FR-12.56, FR-12.57)
# -----------------------------------------------------------------------------
class WeaponRelabelQRView(APIView):
    permission_classes = [IsAuthenticated]
    required_capability = 'weapons.manage'

    def post(self, request, weapon_id):
        if request.user.role not in ['ADMIN', 'SUPER_ADMIN']:
            raise PermissionDenied("Only Admin may request QR relabelling.")

        weapon = Weapon.objects.filter(weapon_id=weapon_id, company_id=request.user.company_id).first()
        if not weapon:
            raise NotFound("Weapon not found.")

        weapon.qr_relabel_count += 1
        weapon.qr_last_relabeled_at = timezone.now()
        weapon.save()

        try:
            write_audit_event(
                action_code='WEAPON_QR_RELABELED',
                actor_user=request.user,
                company_id=request.user.company_id,
                module='weapons_register',
                entity_name='Weapon',
                entity_id=str(weapon.weapon_id),
                payload={'asset_id': weapon.asset_id, 'new_count': weapon.qr_relabel_count}
            )
        except Exception:
            pass

        return Response({
            'asset_id': weapon.asset_id,
            'qr_relabel_count': weapon.qr_relabel_count,
            'message': 'Relabelling recorded successfully. Previous physical labels must be discarded.'
        })


# -----------------------------------------------------------------------------
# 5. WEAPON LICENCE VIEWSET (PRD Screen 5, 6, FR-12.20 to FR-12.32)
# -----------------------------------------------------------------------------
class WeaponLicenceViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = WeaponLicenceSerializer
    required_capability = 'weapons.manage'

    def get_queryset(self):
        user = self.request.user
        if user.role in ['CLIENT', 'GUARD']:
            raise PermissionDenied("Access denied.")
        if user.role == 'SUPERVISOR':
            # Supervisor can only view active licence validity dates, not documents
            return WeaponLicence.objects.filter(company_id=user.company_id).only(
                'licence_id', 'licence_number', 'valid_from', 'valid_until', 'status'
            ).order_by('valid_until')

        return WeaponLicence.objects.filter(company_id=user.company_id).order_by('valid_until')

    def create(self, request, *args, **kwargs):
        if request.user.role not in ['ADMIN', 'SUPER_ADMIN']:
            raise PermissionDenied("Only Admin may create licence records.")

        company_id = request.user.company_id
        ser = WeaponLicenceSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        licence = ser.save(company_id=company_id, created_by=request.user.user_id)

        try:
            write_audit_event(
                action_code='WEAPON_LICENCE_CREATED',
                actor_user=request.user,
                company_id=company_id,
                module='weapons_register',
                entity_name='WeaponLicence',
                entity_id=str(licence.licence_id),
                payload={'licence_number': licence.licence_number}
            )
        except Exception:
            pass

        return Response(WeaponLicenceSerializer(licence).data, status=status.HTTP_201_CREATED)


# -----------------------------------------------------------------------------
# 6. WEAPON ISSUE APIS (PRD Screen 18, 24, FR-12.100 to FR-12.110)
# -----------------------------------------------------------------------------
class WeaponIssueView(APIView):
    permission_classes = [IsAuthenticated]
    required_capability = 'weapons.issue_return'

    def post(self, request):
        user = request.user
        if user.role not in ['ADMIN', 'SUPER_ADMIN', 'SUPERVISOR']:
            raise PermissionDenied("You are not authorised to issue weapons.")

        weapon_id = request.data.get('weapon_id')
        guard_id = request.data.get('guard_id')
        site_id = request.data.get('site_id')
        condition = request.data.get('condition', 'GOOD')
        rounds = int(request.data.get('ammunition_count', 0))
        lot_id = request.data.get('lot_id')
        is_emergency = request.data.get('is_emergency', False)
        emergency_reason = request.data.get('emergency_reason', '')
        client_gen_id = request.data.get('client_generated_id')

        if not weapon_id or not guard_id:
            raise ValidationError({"detail": "weapon_id and guard_id are mandatory."})

        try:
            transfer = initiate_weapon_issue(
                issuer_user=user,
                weapon_id=weapon_id,
                guard_id=guard_id,
                site_id=site_id,
                condition=condition,
                ammunition_count=rounds,
                lot_id=lot_id,
                is_emergency=is_emergency,
                emergency_reason=emergency_reason,
                client_generated_id=client_gen_id
            )
            return Response(WeaponTransferSerializer(transfer).data, status=status.HTTP_201_CREATED)
        except ValueError as ex:
            return Response({"detail": str(ex)}, status=status.HTTP_400_BAD_REQUEST)


class WeaponConfirmIssueView(APIView):
    permission_classes = [IsAuthenticated]
    required_capability = 'weapons.view_own'

    def post(self, request, transfer_id):
        user = request.user
        reject_reason = request.data.get('reject_reason')
        bound_device_id = request.data.get('bound_device_id')

        try:
            transfer = confirm_weapon_issue_by_guard(
                guard_user=user,
                transfer_id=transfer_id,
                bound_device_id=bound_device_id,
                reject_reason=reject_reason
            )
            return Response(WeaponTransferSerializer(transfer).data, status=status.HTTP_200_OK)
        except ValueError as ex:
            return Response({"detail": str(ex)}, status=status.HTTP_400_BAD_REQUEST)


# -----------------------------------------------------------------------------
# 7. WEAPON RETURN APIS (PRD Screen 19, 25, FR-12.127 to FR-12.135)
# -----------------------------------------------------------------------------
class WeaponReturnView(APIView):
    permission_classes = [IsAuthenticated]
    required_capability = 'weapons.issue_return'

    def post(self, request):
        user = request.user
        if user.role not in ['ADMIN', 'SUPER_ADMIN', 'SUPERVISOR', 'GUARD']:
            raise PermissionDenied("Access denied.")

        weapon_id = request.data.get('weapon_id')
        condition = request.data.get('condition', 'GOOD')
        rounds_returned = int(request.data.get('rounds_returned', 0))
        rounds_expended = int(request.data.get('rounds_expended', 0))
        incident_id = request.data.get('incident_id')
        destination_location_id = request.data.get('destination_location_id')
        reason = request.data.get('reason', '')

        if not weapon_id:
            raise ValidationError({"weapon_id": "weapon_id is required."})

        try:
            transfer = process_weapon_return(
                actor_user=user,
                weapon_id=weapon_id,
                condition=condition,
                rounds_returned=rounds_returned,
                rounds_expended=rounds_expended,
                incident_id=incident_id,
                destination_location_id=destination_location_id,
                reason=reason
            )
            return Response(WeaponTransferSerializer(transfer).data, status=status.HTTP_200_OK)
        except ValueError as ex:
            return Response({"detail": str(ex)}, status=status.HTTP_400_BAD_REQUEST)


# -----------------------------------------------------------------------------
# 8. GUARD-TO-GUARD HANDOVER API (PRD Screen 20, 26, FR-12.118 to FR-12.126)
# -----------------------------------------------------------------------------
class WeaponHandoverView(APIView):
    permission_classes = [IsAuthenticated]
    required_capability = 'weapons.issue_return'

    def post(self, request):
        user = request.user
        incoming_guard_id = request.data.get('incoming_guard_id')
        weapon_id = request.data.get('weapon_id')
        rounds = int(request.data.get('ammunition_count', 0))
        condition = request.data.get('condition', 'GOOD')
        handover_ref = request.data.get('handover_ref')
        site_id = request.data.get('site_id')

        if not incoming_guard_id or not weapon_id:
            raise ValidationError({"detail": "incoming_guard_id and weapon_id are required."})

        try:
            transfer = process_guard_handover(
                outgoing_guard=user,
                incoming_guard_id=incoming_guard_id,
                weapon_id=weapon_id,
                ammunition_count=rounds,
                condition=condition,
                handover_ref=handover_ref,
                site_id=site_id
            )
            return Response(WeaponTransferSerializer(transfer).data, status=status.HTTP_200_OK)
        except ValueError as ex:
            return Response({"detail": str(ex)}, status=status.HTTP_400_BAD_REQUEST)


# -----------------------------------------------------------------------------
# 9. AMMUNITION MASTER & LEDGER (PRD Screens 7, 8, 9, FR-12.59 to FR-12.84)
# -----------------------------------------------------------------------------
class AmmunitionLotViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = AmmunitionLotSerializer
    required_capability = 'weapons.manage'

    def get_queryset(self):
        user = self.request.user
        if user.role == 'CLIENT':
            raise PermissionDenied("Access denied.")
        return AmmunitionLot.objects.filter(company_id=user.company_id).order_by('-created_at')

    def create(self, request, *args, **kwargs):
        if request.user.role not in ['ADMIN', 'SUPER_ADMIN']:
            raise PermissionDenied("Only Admin may create ammunition lots.")
        company_id = request.user.company_id
        ser = AmmunitionLotSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        lot = ser.save(company_id=company_id)
        return Response(AmmunitionLotSerializer(lot).data, status=status.HTTP_201_CREATED)


class AmmunitionLedgerViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = AmmunitionLedgerSerializer
    required_capability = 'weapons.manage'

    def get_queryset(self):
        user = self.request.user
        if user.role == 'CLIENT':
            raise PermissionDenied("Access denied.")
        return AmmunitionLedger.objects.filter(company_id=user.company_id).order_by('-server_timestamp')


class AmmunitionStockCountView(APIView):
    permission_classes = [IsAuthenticated]
    required_capability = 'weapons.issue_return'

    def post(self, request):
        user = request.user
        if user.role not in ['ADMIN', 'SUPER_ADMIN', 'SUPERVISOR']:
            raise PermissionDenied("Access denied.")

        company_id = user.company_id
        location_id = request.data.get('location_id')
        lot_id = request.data.get('lot_id')
        physical_qty = int(request.data.get('physical_quantity', 0))
        reason = request.data.get('reason', '')

        if not location_id or not lot_id:
            raise ValidationError({"detail": "location_id and lot_id are required."})

        # Calculate current ledger stock
        ledger_qty = calculate_ammunition_stock(company_id, lot_id=lot_id, location_id=location_id)
        variance = physical_qty - ledger_qty

        if variance != 0 and not reason:
            raise ValidationError({"reason": "A reason is mandatory whenever there is a variance between physical count and ledger stock."})

        adj_status = 'PENDING' if variance != 0 else 'NOT_REQUIRED'

        count_rec = AmmunitionStockCount.objects.create(
            company_id=company_id,
            location_id=location_id,
            lot_id=lot_id,
            ledger_quantity=ledger_qty,
            physical_quantity=physical_qty,
            variance=variance,
            reason=reason if variance != 0 else None,
            counted_by=user.user_id,
            adjustment_status=adj_status
        )

        return Response(AmmunitionStockCountSerializer(count_rec).data, status=status.HTTP_201_CREATED)


class ApproveAmmunitionAdjustmentView(APIView):
    permission_classes = [IsAuthenticated]
    required_capability = 'weapons.manage'

    def post(self, request, count_id):
        if request.user.role not in ['ADMIN', 'SUPER_ADMIN']:
            raise PermissionDenied("Only Admin may approve ammunition stock adjustments.")

        count_rec = AmmunitionStockCount.objects.filter(
            count_id=count_id, company_id=request.user.company_id
        ).first()
        if not count_rec or count_rec.adjustment_status != 'PENDING':
            raise NotFound("Pending stock count adjustment not found.")

        approve = request.data.get('approve', True)
        if not approve:
            count_rec.adjustment_status = 'REJECTED'
            count_rec.save()
            return Response({'status': 'REJECTED', 'message': 'Adjustment rejected.'})

        # Append ADJUSTED entry to immutable ledger
        lot = AmmunitionLot.objects.filter(lot_id=count_rec.lot_id).first()
        entry_qty = abs(count_rec.variance)

        ledger_entry = AmmunitionLedger.objects.create(
            client_generated_id=f"AMMO-ADJ-{count_rec.count_id}",
            company_id=count_rec.company_id,
            lot_id=count_rec.lot_id,
            ammunition_type=lot.ammunition_type if lot else 'Ammunition',
            entry_type='ADJUSTED' if count_rec.variance > 0 else 'DISPOSED',
            destination_location_id=count_rec.location_id if count_rec.variance > 0 else None,
            source_location_id=count_rec.location_id if count_rec.variance < 0 else None,
            quantity=entry_qty,
            reason=f"Approved physical count variance adjustment. Reason: {count_rec.reason}",
            approved_by=request.user.user_id,
            actor_id=request.user.user_id
        )

        count_rec.adjustment_status = 'APPROVED'
        count_rec.adjustment_approved_by = request.user.user_id
        count_rec.adjustment_approved_at = timezone.now()
        count_rec.adjustment_ledger_entry_id = ledger_entry.ledger_entry_id
        count_rec.save()

        return Response({'status': 'APPROVED', 'ledger_entry_id': str(ledger_entry.ledger_entry_id)})


# -----------------------------------------------------------------------------
# 10. DISCREPANCIES (PRD Screen 10, FR-12.146 to FR-12.156)
# -----------------------------------------------------------------------------
class WeaponDiscrepancyViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = WeaponDiscrepancySerializer
    required_capability = 'weapons.manage'

    def get_queryset(self):
        user = self.request.user
        if user.role == 'CLIENT':
            raise PermissionDenied("Access denied.")
        qs = WeaponDiscrepancy.objects.filter(company_id=user.company_id)
        if user.role == 'SUPERVISOR':
            assigned_sites = get_supervisor_site_ids(user)
            qs = qs.filter(site_id__in=assigned_sites)
        elif user.role == 'GUARD':
            qs = qs.filter(guard_id=user.user_id)
        return qs.order_by('-created_at')

    def partial_update(self, request, *args, **kwargs):
        if request.user.role not in ['ADMIN', 'SUPER_ADMIN']:
            raise PermissionDenied("Only Admin may resolve discrepancies.")

        instance = self.get_object()
        recount = request.data.get('recount_value')
        explanation = request.data.get('explanation')
        outcome = request.data.get('outcome')
        resolved = request.data.get('resolved', False)

        if recount is not None:
            instance.recount_value = recount
        if explanation:
            instance.explanation = explanation
        if outcome:
            instance.outcome = outcome
        if resolved:
            instance.status = 'RESOLVED'
            instance.resolved_at = timezone.now()
            instance.resolved_by = request.user.user_id

        instance.save()
        return Response(WeaponDiscrepancySerializer(instance).data)


# -----------------------------------------------------------------------------
# 11. GUARD WEAPON BLOCK LIST (PRD Screen 11, FR-12.180 to FR-12.182)
# -----------------------------------------------------------------------------
class GuardWeaponBlockViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = GuardWeaponBlockSerializer
    required_capability = 'weapons.manage'

    def get_queryset(self):
        if self.request.user.role not in ['ADMIN', 'SUPER_ADMIN']:
            raise PermissionDenied("Only Admin may view guard weapon blocks.")
        return GuardWeaponBlock.objects.filter(company_id=self.request.user.company_id).order_by('-created_at')

    def create(self, request, *args, **kwargs):
        if request.user.role not in ['ADMIN', 'SUPER_ADMIN']:
            raise PermissionDenied("Only Admin may add guard weapon restrictions.")
        company_id = request.user.company_id
        guard_id = request.data.get('guard_id')
        reason = request.data.get('reason')
        if not guard_id or not reason:
            raise ValidationError({"detail": "guard_id and reason are mandatory."})

        block = GuardWeaponBlock.objects.create(
            company_id=company_id,
            guard_id=guard_id,
            reason=reason,
            created_by=request.user.user_id,
            status='ACTIVE'
        )
        return Response(GuardWeaponBlockSerializer(block).data, status=status.HTTP_201_CREATED)


# -----------------------------------------------------------------------------
# 12. RECOVERY REQUIRED (PRD Screen 12, FR-12.187 to FR-12.190)
# -----------------------------------------------------------------------------
class WeaponRecoveryViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = WeaponRecoverySerializer
    required_capability = 'weapons.manage'

    def get_queryset(self):
        user = self.request.user
        if user.role in ['CLIENT', 'GUARD']:
            raise PermissionDenied("Access denied.")
        qs = WeaponRecovery.objects.filter(company_id=user.company_id)
        if user.role == 'SUPERVISOR':
            assigned_sites = get_supervisor_site_ids(user)
            qs = qs.filter(last_known_site_id__in=assigned_sites)
        return qs.order_by('-created_at')


# -----------------------------------------------------------------------------
# 13. DAILY CUSTODY SHEET (PRD Screen 13, FR-12.225, FR-12.226)
# -----------------------------------------------------------------------------
class DailyCustodySheetView(APIView):
    permission_classes = [IsAuthenticated]
    required_capability = 'weapons.issue_return'

    def get(self, request):
        user = request.user
        if user.role == 'CLIENT':
            raise PermissionDenied("Access denied.")

        site_id = request.query_params.get('site_id')
        company_id = user.company_id

        qs = WeaponCustodyRecord.objects.filter(is_current=True)
        if site_id:
            qs = qs.filter(site_id=site_id)
        if user.role == 'SUPERVISOR':
            assigned_sites = get_supervisor_site_ids(user)
            qs = qs.filter(site_id__in=assigned_sites)

        # Build list with weapon details
        results = []
        for c in qs:
            w = Weapon.objects.filter(weapon_id=c.weapon_id, company_id=company_id).first()
            if not w:
                continue

            results.append({
                'custody_id': str(c.custody_id),
                'weapon_id': str(w.weapon_id),
                'asset_id': w.asset_id,
                'weapon_type': w.weapon_type,
                'make_model': f"{w.make} {w.model}",
                'masked_serial': w.masked_serial_number(),
                'custodian_type': c.custodian_type,
                'custodian_id': str(c.custodian_id),
                'ammunition_rounds': c.ammunition_rounds,
                'start_time': c.start_time.isoformat() if c.start_time else None,
                'site_id': str(c.site_id) if c.site_id else None
            })

        return Response(results)


# -----------------------------------------------------------------------------
# 14. MAINTENANCE LOGS (PRD Screen 14, FR-12.215 to FR-12.221)
# -----------------------------------------------------------------------------
class WeaponMaintenanceLogViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = WeaponMaintenanceLogSerializer
    required_capability = 'weapons.manage'

    def get_queryset(self):
        user = self.request.user
        if user.role in ['CLIENT', 'GUARD']:
            raise PermissionDenied("Access denied.")
        return WeaponMaintenanceLog.objects.filter(company_id=user.company_id).order_by('-record_date')

    def create(self, request, *args, **kwargs):
        if request.user.role not in ['ADMIN', 'SUPER_ADMIN']:
            raise PermissionDenied("Only Admin may record maintenance.")
        ser = WeaponMaintenanceLogSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        maint = ser.save(company_id=request.user.company_id, created_by=request.user.user_id)

        # Update weapon status if outcome is UNSERVICEABLE or REPAIRED
        w = Weapon.objects.filter(weapon_id=maint.weapon_id).first()
        if w:
            if maint.outcome == 'PASSED' or maint.outcome == 'REPAIRED':
                w.status = 'IN_STORAGE'
                w.status_reason = f"Maintenance completed ({maint.outcome}) by {maint.done_by}"
                w.save()
            elif maint.outcome == 'FAILED' or maint.outcome == 'PENDING_PARTS':
                w.status = 'IN_MAINTENANCE'
                w.status_reason = f"Maintenance in progress ({maint.outcome})"
                w.save()

        return Response(WeaponMaintenanceLogSerializer(maint).data, status=status.HTTP_201_CREATED)


# -----------------------------------------------------------------------------
# 15. MISSING OR STOLEN WEAPON REPORT (PRD Screen 15, 28, FR-12.206 to FR-12.210)
# -----------------------------------------------------------------------------
class MissingWeaponReportView(APIView):
    permission_classes = [IsAuthenticated]
    required_capability = 'weapons.report'

    def post(self, request):
        user = request.user
        if user.role == 'CLIENT':
            raise PermissionDenied("Access denied.")

        weapon_id = request.data.get('weapon_id')
        description = request.data.get('description')
        is_stolen = request.data.get('is_stolen', False)

        if not weapon_id or not description:
            raise ValidationError({"detail": "weapon_id and description are mandatory."})

        weapon, alert = report_missing_or_stolen_weapon(
            reporting_user=user,
            weapon_id=weapon_id,
            description=description,
            is_stolen=is_stolen
        )

        return Response({
            'asset_id': weapon.asset_id,
            'status': weapon.status,
            'alert_id': str(alert.alert_id),
            'message': 'CRITICAL: Report submitted. Admin has been notified immediately.'
        }, status=status.HTTP_201_CREATED)


# -----------------------------------------------------------------------------
# 16. EXPORT REGISTERS (PRD Screen 16, FR-12.233 to FR-12.238, AC-12.70, AC-12.71)
# -----------------------------------------------------------------------------
class ExportWeaponRegisterView(APIView):
    permission_classes = [IsAuthenticated]
    required_capability = 'weapons.manage'

    def get(self, request):
        user = request.user
        if user.role not in ['ADMIN', 'SUPER_ADMIN']:
            raise PermissionDenied("Only Admin may export weapon registers.")

        export_type = request.query_params.get('type', 'weapons') # 'weapons' | 'ammunition' | 'discrepancies'
        fmt = request.query_params.get('format', 'csv')

        output = io.StringIO()
        writer = csv.writer(output)

        if export_type == 'weapons':
            writer.writerow(['Asset ID', 'Type', 'Make', 'Model', 'Calibre', 'Serial Number', 'Status', 'Acquisition Date', 'Supplier'])
            for w in Weapon.objects.filter(company_id=user.company_id, is_active=True).order_by('asset_id'):
                writer.writerow([w.asset_id, w.weapon_type, w.make, w.model, w.calibre, w.serial_number, w.status, str(w.acquisition_date), w.supplier or ''])
            filename = f"weapons_register_{date.today()}.csv"

        elif export_type == 'ammunition':
            writer.writerow(['Entry ID', 'Type', 'Entry Type', 'Quantity', 'Reason', 'Timestamp'])
            for l in AmmunitionLedger.objects.filter(company_id=user.company_id).order_by('-server_timestamp'):
                writer.writerow([str(l.ledger_entry_id), l.ammunition_type, l.entry_type, l.quantity, l.reason or '', str(l.server_timestamp)])
            filename = f"ammunition_ledger_{date.today()}.csv"

        else:
            writer.writerow(['Discrepancy ID', 'Type', 'Status', 'Explanation', 'Outcome', 'Created At'])
            for d in WeaponDiscrepancy.objects.filter(company_id=user.company_id).order_by('-created_at'):
                writer.writerow([str(d.discrepancy_id), d.discrepancy_type, d.status, d.explanation or '', d.outcome or '', str(d.created_at)])
            filename = f"weapon_discrepancies_{date.today()}.csv"

        try:
            write_audit_event(
                action_code='WEAPON_REGISTER_EXPORTED',
                actor_user=user,
                company_id=user.company_id,
                module='weapons_register',
                entity_name='WeaponRegister',
                entity_id=None,
                payload={'export_type': export_type, 'format': fmt}
            )
        except Exception:
            pass

        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


# -----------------------------------------------------------------------------
# 17. MODULE 13 REPORTING CONTRACT (PRD 13.7, FR-12.241 to FR-12.246)
# -----------------------------------------------------------------------------
class Module13ReportingView(APIView):
    permission_classes = [IsAuthenticated]
    required_capability = 'weapons.manage'

    def get(self, request):
        if request.user.role not in ['ADMIN', 'SUPER_ADMIN']:
            raise PermissionDenied("Access denied.")

        company_id = request.user.company_id

        # Weapon counts by status
        counts_by_status = dict(
            Weapon.objects.filter(company_id=company_id, is_active=True)
            .values('status')
            .annotate(c=Count('status'))
            .values_list('status', 'c')
        )

        # Counts by location
        counts_by_loc = list(
            Weapon.objects.filter(company_id=company_id, is_active=True, current_location_id__isnull=False)
            .values('current_location_id')
            .annotate(count=Count('weapon_id'))
        )

        # Issues & returns counts
        total_issues = WeaponTransfer.objects.filter(company_id=company_id, transfer_type='ISSUE', status='COMPLETED').count()
        total_returns = WeaponTransfer.objects.filter(company_id=company_id, transfer_type='RETURN', status='COMPLETED').count()
        total_handovers = WeaponTransfer.objects.filter(company_id=company_id, transfer_type='HANDOVER', status='COMPLETED').count()

        # Discrepancies
        total_disc = WeaponDiscrepancy.objects.filter(company_id=company_id).count()
        open_disc = WeaponDiscrepancy.objects.filter(company_id=company_id, status__in=['OPEN', 'UNDER_REVIEW']).count()
        resolved_disc = WeaponDiscrepancy.objects.filter(company_id=company_id, status='RESOLVED').count()

        return Response({
            'counts_by_status': counts_by_status,
            'counts_by_location': counts_by_loc,
            'transfers': {
                'issues': total_issues,
                'returns': total_returns,
                'handovers': total_handovers
            },
            'discrepancies': {
                'total': total_disc,
                'open': open_disc,
                'resolved': resolved_disc
            }
        })
