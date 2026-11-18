import uuid
from datetime import date, datetime, timedelta
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum, Q

from .models import (
    WeaponLocation, WeaponLicence, Weapon, WeaponLicenceAssociation,
    WeaponSerialRevealLog, WeaponTransfer, WeaponCustodyRecord,
    AmmunitionLot, AmmunitionLedger, AmmunitionStockCount,
    WeaponDiscrepancy, GuardWeaponBlock, WeaponRecovery,
    WeaponMaintenanceLog, WeaponAlert
)
from foundation.models import User, BoundDevice, AuditEvent
from foundation.services.audit_service import write_audit_event


# -----------------------------------------------------------------------------
# ASSET ID GENERATOR (PRD FR-12.2, FR-12.3)
# -----------------------------------------------------------------------------
def generate_weapon_asset_id(company_id):
    """
    Generates a permanent, unique internal asset ID (e.g. WPN-202611-001) that is never reused.
    """
    now = datetime.now()
    prefix = f"WPN-{now.year}{now.month:02d}-"
    # Find max existing sequence for this company and prefix
    existing = Weapon.objects.filter(company_id=company_id, asset_id__startswith=prefix).count()
    seq = existing + 1
    asset_id = f"{prefix}{seq:04d}"
    # Ensure absolute uniqueness
    while Weapon.objects.filter(asset_id=asset_id).exists():
        seq += 1
        asset_id = f"{prefix}{seq:04d}"
    return asset_id


# -----------------------------------------------------------------------------
# AMMUNITION STOCK CALCULATOR (PRD FR-12.68, FR-12.69, NFR-12.7)
# -----------------------------------------------------------------------------
def calculate_ammunition_stock(company_id, lot_id=None, location_id=None):
    """
    Computes stock derived authoritatively from the immutable ledger.
    Stock = Received + Returned + Adjusted - Issued - Expended - Disposed
    """
    qs = AmmunitionLedger.objects.filter(company_id=company_id)
    if lot_id:
        qs = qs.filter(lot_id=lot_id)
    if location_id:
        # Stock at specific location: destination is positive, source is negative
        pos = qs.filter(
            destination_location_id=location_id,
            entry_type__in=['RECEIVED', 'TRANSFERRED', 'RETURNED', 'ADJUSTED']
        ).aggregate(total=Sum('quantity'))['total'] or 0

        neg = qs.filter(
            source_location_id=location_id,
            entry_type__in=['TRANSFERRED', 'ISSUED', 'EXPENDED', 'DISPOSED']
        ).aggregate(total=Sum('quantity'))['total'] or 0

        return max(0, pos - neg)

    pos = qs.filter(entry_type__in=['RECEIVED', 'RETURNED', 'ADJUSTED']).aggregate(total=Sum('quantity'))['total'] or 0
    neg = qs.filter(entry_type__in=['ISSUED', 'EXPENDED', 'DISPOSED']).aggregate(total=Sum('quantity'))['total'] or 0
    return max(0, pos - neg)


# -----------------------------------------------------------------------------
# ISSUE ELIGIBILITY ENGINE (PRD Section 8.1 & 8.2)
# -----------------------------------------------------------------------------
def validate_issue_eligibility(guard_id, weapon_id, site_id, duty_date, company_id, issuer_user, is_emergency=False, is_handover=False):
    """
    Evaluates every mandatory condition in Section 8.1 with exact PRD failure messages.
    Returns (True, None) or (False, "Issue blocked: ...")
    """
    # 1. Weapon checks
    weapon = Weapon.objects.filter(weapon_id=weapon_id, company_id=company_id).first()
    if not weapon:
        return False, "Issue blocked: Weapon record not found."

    if weapon.status == 'IN_MAINTENANCE':
        return False, "Issue blocked: Weapon is currently in maintenance."

    if weapon.status in ['MISSING', 'LOST_OR_STOLEN', 'RETIRED_OR_DISPOSED', 'DEPOSITED_WITH_AUTHORITY']:
        return False, "Issue blocked: Weapon is not available in storage."

    if not is_handover and not is_emergency and weapon.status != 'IN_STORAGE':
        return False, "Issue blocked: Weapon is not available in storage."

    # Weapon location check: if site is specified, weapon must be at issuing location or Armoury
    if weapon.current_location_id:
        loc = WeaponLocation.objects.filter(location_id=weapon.current_location_id).first()
        if loc and loc.site_id and str(loc.site_id) != str(site_id):
            return False, "Issue blocked: Weapon is recorded at a different location."

    # Weapon licence check
    current_assoc = WeaponLicenceAssociation.objects.filter(weapon_id=weapon_id, is_current=True).first()
    if not current_assoc:
        return False, "Issue blocked: Weapon does not have a valid linked licence."

    licence = WeaponLicence.objects.filter(licence_id=current_assoc.licence_id).first()
    if not licence:
        return False, "Issue blocked: Weapon does not have a valid linked licence."

    if licence.valid_until < duty_date:
        return False, "Issue blocked: Weapon licence has expired."

    # Unresolved blocking discrepancy on weapon
    if WeaponDiscrepancy.objects.filter(weapon_id=weapon_id, is_blocking=True, status__in=['OPEN', 'UNDER_REVIEW']).exists():
        return False, "Issue blocked: Weapon has an unresolved discrepancy."

    # Single valid current custodian
    current_custody = WeaponCustodyRecord.objects.filter(weapon_id=weapon_id, is_current=True).all()
    if current_custody.count() != 1:
        return False, "Issue blocked: Current custody is unresolved."

    # 2. Guard checks
    # Check guard weapon block list
    if GuardWeaponBlock.objects.filter(guard_id=guard_id, company_id=company_id, status='ACTIVE').exists():
        return False, "Issue blocked: Guard has an active weapon restriction. Contact Admin."

    # Unresolved blocking guard discrepancy
    if WeaponDiscrepancy.objects.filter(guard_id=guard_id, is_blocking=True, status__in=['OPEN', 'UNDER_REVIEW']).exists():
        return False, "Issue blocked: Guard has an unresolved custody discrepancy."

    # Module 3 Guard verification
    user_guard = User.objects.filter(Q(user_id=guard_id) | Q(guard_profile_id=guard_id)).first()
    if user_guard:
        if user_guard.status != 'ACTIVE':
            return False, "Issue blocked: Guard is not Active in Guard Management."

    # Check Employee record if exists
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT e.lifecycle_status, e.employment_status
            FROM security_erp.employees e
            WHERE e.employee_id = %s
            LIMIT 1
            """,
            [str(guard_id)]
        )
        emp_row = cursor.fetchone()
        if emp_row:
            l_status, emp_status = emp_row
            if l_status in ['suspended', 'resigned', 'terminated'] or emp_status in ['suspended', 'resigned', 'terminated']:
                return False, "Issue blocked: Guard is not Active in Guard Management."

        # Check arms licence document
        cursor.execute(
            """
            SELECT ed.verification_status, ed.expiry_date
            FROM security_erp.employee_documents ed
            WHERE ed.employee_id = %s AND (ed.document_type ILIKE '%%arm%%' OR ed.document_type ILIKE '%%gun%%')
            ORDER BY ed.uploaded_at DESC
            LIMIT 1
            """,
            [str(guard_id)]
        )
        doc_row = cursor.fetchone()
        if doc_row:
            v_status, exp_date = doc_row
            if v_status == 'expired' or (exp_date and exp_date < duty_date):
                return False, "Issue blocked: Guard's arms licence document is expired or unavailable."

    # 3. Module 5 Assignment & Armed post check
    if not is_emergency and site_id:
        with connection.cursor() as cursor:
            # Check assignment
            cursor.execute(
                """
                SELECT ra.assignment_id, ra.site_id, ra.requires_arms
                FROM security_erp.roster_assignments ra
                WHERE (ra.employee_id = %s OR ra.guard_id = %s)
                  AND ra.duty_date = %s
                LIMIT 1
                """,
                [str(guard_id), str(guard_id), duty_date]
            )
            assign_row = cursor.fetchone()
            if not assign_row:
                # Check shift_assignments
                cursor.execute(
                    """
                    SELECT sa.assignment_id, rs.site_id, TRUE
                    FROM security_erp.shift_assignments sa
                    JOIN security_erp.roster_shifts rs ON sa.shift_id = rs.shift_id
                    WHERE sa.employee_id = %s AND rs.shift_date = %s
                    LIMIT 1
                    """,
                    [str(guard_id), duty_date]
                )
                assign_row = cursor.fetchone()

            if assign_row:
                _, assign_site_id, requires_arms = assign_row
                if str(assign_site_id) != str(site_id):
                    return False, "Issue blocked: Guard is not assigned to this site."
                if requires_arms is False:
                    return False, "Issue blocked: Current assignment is not an armed post."
            else:
                return False, "Issue blocked: No current assignment was found for this guard."

            # 4. Module 6 Check-in attendance check
            cursor.execute(
                """
                SELECT ar.attendance_id, ar.status, ar.check_in_time
                FROM security_erp.attendance_records ar
                WHERE (ar.employee_id = %s OR ar.user_id = %s)
                  AND ar.duty_date = %s AND ar.check_in_time IS NOT NULL
                LIMIT 1
                """,
                [str(guard_id), str(guard_id), duty_date]
            )
            att_row = cursor.fetchone()
            if not att_row:
                return False, "Issue blocked: Guard has not checked in for this assignment."

    # 5. Site permissions check for Issuer
    if issuer_user and issuer_user.role == 'SUPERVISOR' and site_id:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT 1 FROM security_erp.site_supervisor_assignments
                WHERE supervisor_user_id = %s AND site_id = %s AND is_active = TRUE
                LIMIT 1
                """,
                [str(issuer_user.user_id), str(site_id)]
            )
            if not cursor.fetchone():
                return False, "Issue blocked: You are not authorised to issue weapons at this site."

    return True, None


# -----------------------------------------------------------------------------
# TWO-PERSON CONFIRMATION WORKFLOWS (PRD FR-12.100 to FR-12.117)
# -----------------------------------------------------------------------------
@transaction.atomic
def initiate_weapon_issue(
    issuer_user, weapon_id, guard_id, site_id,
    condition="GOOD", ammunition_count=0, lot_id=None,
    is_emergency=False, emergency_reason="", client_generated_id=None
):
    """
    Step 1 of Issue: Issuer records transfer -> creates ISSUE_PENDING transfer.
    Weapon remains in current custodian's custody until guard confirms.
    """
    company_id = issuer_user.company_id
    today = date.today()

    # Validate eligibility
    is_valid, err_msg = validate_issue_eligibility(
        guard_id=guard_id,
        weapon_id=weapon_id,
        site_id=site_id,
        duty_date=today,
        company_id=company_id,
        issuer_user=issuer_user,
        is_emergency=is_emergency
    )
    if not is_valid:
        raise ValueError(err_msg)

    # Validate ammunition stock if rounds requested
    if ammunition_count > 0:
        available_stock = calculate_ammunition_stock(company_id=company_id, lot_id=lot_id)
        if available_stock < ammunition_count:
            raise ValueError(f"Issue blocked: Insufficient ammunition stock ({available_stock} rounds available, {ammunition_count} requested).")

    # Get current custodian
    current_custody = WeaponCustodyRecord.objects.filter(weapon_id=weapon_id, is_current=True).first()
    from_custodian_type = current_custody.custodian_type if current_custody else 'LOCATION'
    from_custodian_id = current_custody.custodian_id if current_custody else issuer_user.user_id

    cgen_id = client_generated_id or f"TX-ISSUE-{uuid.uuid4().hex[:12].upper()}"

    # Create transfer in ISSUE_PENDING state
    transfer = WeaponTransfer.objects.create(
        client_generated_id=cgen_id,
        company_id=company_id,
        weapon_id=weapon_id,
        transfer_type='ISSUE',
        from_custodian_type=from_custodian_type,
        from_custodian_id=from_custodian_id,
        to_custodian_type='GUARD',
        to_custodian_id=guard_id,
        site_id=site_id,
        status='ISSUE_PENDING',
        condition_before=condition,
        rounds_issued=ammunition_count,
        issuer_id=issuer_user.user_id,
        is_emergency=is_emergency,
        emergency_reason=emergency_reason if is_emergency else None,
        emergency_ratified_status='PENDING' if is_emergency else 'NONE'
    )

    try:
        write_audit_event(
            action_code='WEAPON_ISSUE_INITIATED',
            actor_user=issuer_user,
            company_id=company_id,
            module='weapons_register',
            record_type='WeaponTransfer',
            record_id=str(transfer.transfer_id)
        )
    except Exception:
        pass

    return transfer


@transaction.atomic
def confirm_weapon_issue_by_guard(guard_user, transfer_id, bound_device_id=None, reject_reason=None):
    """
    Step 2 of Issue: Guard confirms on registered device -> transfer COMPLETED.
    Custody moves to Guard, weapon status becomes ISSUED, Ammunition Ledger updated.
    """
    transfer = WeaponTransfer.objects.filter(transfer_id=transfer_id).first()
    if not transfer or transfer.status != 'ISSUE_PENDING':
        raise ValueError("Pending issue transfer not found or already processed.")

    if reject_reason:
        # Guard rejected receipt -> creates discrepancy
        transfer.status = 'DISCREPANCY'
        transfer.reason = reject_reason
        transfer.save()

        # Create discrepancy
        disc = WeaponDiscrepancy.objects.create(
            company_id=transfer.company_id,
            weapon_id=transfer.weapon_id,
            transfer_id=transfer.transfer_id,
            guard_id=guard_user.user_id,
            site_id=transfer.site_id,
            discrepancy_type='IDENTITY',
            expected_value={'status': 'ACCEPTED'},
            reported_value={'status': 'REJECTED', 'reason': reject_reason},
            explanation=reject_reason,
            status='OPEN',
            is_blocking=True
        )

        WeaponAlert.objects.create(
            company_id=transfer.company_id,
            alert_type='DISCREPANCY',
            priority='HIGH',
            related_entity_type='WeaponDiscrepancy',
            related_entity_id=disc.discrepancy_id,
            recipient_role='ADMIN',
            site_id=transfer.site_id,
            title='Guard Rejected Weapon Issue Confirmation',
            message=f"Guard {guard_user.email} rejected weapon receipt: {reject_reason}"
        )
        return transfer

    # Close previous custody
    now = timezone.now()
    WeaponCustodyRecord.objects.filter(weapon_id=transfer.weapon_id, is_current=True).update(
        is_current=False,
        end_transfer_id=transfer.transfer_id,
        end_time=now
    )

    # Create new current custody
    new_custody = WeaponCustodyRecord.objects.create(
        weapon_id=transfer.weapon_id,
        custodian_type='GUARD',
        custodian_id=guard_user.user_id,
        start_transfer_id=transfer.transfer_id,
        start_time=now,
        is_current=True,
        ammunition_rounds=transfer.rounds_issued,
        site_id=transfer.site_id
    )

    # Update weapon status
    weapon = Weapon.objects.filter(weapon_id=transfer.weapon_id).first()
    if weapon:
        weapon.status = 'ISSUED'
        weapon.current_custody_id = new_custody.custody_id
        weapon.status_reason = f"Issued to Guard {guard_user.email}"
        weapon.status_updated_at = now
        weapon.save()

    # If ammunition issued, append to immutable ledger
    if transfer.rounds_issued > 0:
        lot = AmmunitionLot.objects.filter(company_id=transfer.company_id, status='AVAILABLE').first()
        lot_id = lot.lot_id if lot else uuid.uuid4()
        ammo_type = lot.ammunition_type if lot else weapon.calibre

        AmmunitionLedger.objects.create(
            client_generated_id=f"AMMO-ISS-{transfer.transfer_id}",
            company_id=transfer.company_id,
            lot_id=lot_id,
            ammunition_type=ammo_type,
            entry_type='ISSUED',
            weapon_id=transfer.weapon_id,
            guard_id=guard_user.user_id,
            transfer_id=transfer.transfer_id,
            quantity=transfer.rounds_issued,
            reason=f"Issued with weapon {weapon.asset_id if weapon else ''}"
        )

    # Mark transfer COMPLETED
    transfer.status = 'COMPLETED'
    transfer.guard_confirmation_id = guard_user.user_id
    transfer.guard_confirmed_at = now
    transfer.save()

    try:
        write_audit_event(
            action_code='WEAPON_ISSUE_CONFIRMED',
            actor_user=guard_user,
            company_id=transfer.company_id,
            module='weapons_register',
            entity_name='WeaponTransfer',
            entity_id=str(transfer.transfer_id),
            payload={'weapon_id': str(transfer.weapon_id), 'guard_id': str(guard_user.user_id)}
        )
    except Exception:
        pass

    return transfer


@transaction.atomic
def process_weapon_return(
    actor_user, weapon_id, condition="GOOD",
    rounds_returned=0, rounds_expended=0, incident_id=None,
    destination_location_id=None, reason=""
):
    """
    Processes weapon return with two-person validation.
    Checks Issued - Returned - Expended = 0.
    Mismatch flags Discrepancy (FR-12.74).
    """
    company_id = actor_user.company_id
    now = timezone.now()

    weapon = Weapon.objects.filter(weapon_id=weapon_id, company_id=company_id).first()
    if not weapon:
        raise ValueError("Weapon record not found.")

    custody = WeaponCustodyRecord.objects.filter(weapon_id=weapon_id, is_current=True).first()
    if not custody or custody.custodian_type != 'GUARD':
        raise ValueError("Weapon is not currently recorded in a guard's custody.")

    guard_id = custody.custodian_id
    rounds_held = custody.ammunition_rounds

    # Reconcile ammunition balance: Issued - Returned - Expended = 0
    balance_diff = rounds_held - (rounds_returned + rounds_expended)
    has_discrepancy = balance_diff != 0

    if rounds_expended > 0 and not incident_id:
        raise ValueError("An Expended ammunition entry requires a linked Module 8 incident reference.")

    # Determine destination location
    dest_loc = None
    if destination_location_id:
        dest_loc = WeaponLocation.objects.filter(location_id=destination_location_id).first()
    if not dest_loc:
        dest_loc = WeaponLocation.objects.filter(company_id=company_id, location_type='ARMOURY').first()

    dest_id = dest_loc.location_id if dest_loc else actor_user.user_id

    # Create Return Transfer
    transfer = WeaponTransfer.objects.create(
        client_generated_id=f"TX-RET-{uuid.uuid4().hex[:12].upper()}",
        company_id=company_id,
        weapon_id=weapon_id,
        transfer_type='RETURN',
        from_custodian_type='GUARD',
        from_custodian_id=guard_id,
        to_custodian_type='LOCATION',
        to_custodian_id=dest_id,
        site_id=custody.site_id,
        status='DISCREPANCY' if has_discrepancy else 'COMPLETED',
        condition_before='ISSUED',
        condition_after=condition,
        rounds_returned=rounds_returned,
        rounds_expended=rounds_expended,
        receiver_confirmation_id=actor_user.user_id,
        receiver_confirmed_at=now,
        reason=reason
    )

    if has_discrepancy:
        # Create Discrepancy record (FR-12.74)
        disc = WeaponDiscrepancy.objects.create(
            company_id=company_id,
            weapon_id=weapon_id,
            transfer_id=transfer.transfer_id,
            guard_id=guard_id,
            site_id=custody.site_id,
            discrepancy_type='ROUNDS',
            expected_value={'rounds_held': rounds_held},
            reported_value={'returned': rounds_returned, 'expended': rounds_expended, 'missing': balance_diff},
            explanation=f"Ammunition count mismatch upon return: expected {rounds_held}, returned {rounds_returned}, expended {rounds_expended}.",
            status='OPEN',
            is_blocking=True
        )

        WeaponAlert.objects.create(
            company_id=company_id,
            alert_type='DISCREPANCY',
            priority='HIGH',
            related_entity_type='WeaponDiscrepancy',
            related_entity_id=disc.discrepancy_id,
            recipient_role='ADMIN',
            site_id=custody.site_id,
            title='Ammunition Count Mismatch at Return',
            message=f"Weapon {weapon.asset_id}: Expected {rounds_held} rounds, returned {rounds_returned}, missing {balance_diff}."
        )

    # Complete custody move back to Storage / Location
    custody.is_current = False
    custody.end_transfer_id = transfer.transfer_id
    custody.end_time = now
    custody.save()

    new_custody = WeaponCustodyRecord.objects.create(
        weapon_id=weapon_id,
        custodian_type='LOCATION',
        custodian_id=dest_id,
        start_transfer_id=transfer.transfer_id,
        start_time=now,
        is_current=True,
        ammunition_rounds=0,
        site_id=custody.site_id
    )

    # Update weapon status
    weapon.status = 'IN_STORAGE'
    weapon.current_custody_id = new_custody.custody_id
    weapon.current_location_id = dest_id
    weapon.status_reason = f"Returned from guard custody by {actor_user.email}"
    weapon.status_updated_at = now
    weapon.save()

    # Append Ammunition Ledger entries
    lot = AmmunitionLot.objects.filter(company_id=company_id).first()
    lot_id = lot.lot_id if lot else uuid.uuid4()
    ammo_type = lot.ammunition_type if lot else weapon.calibre

    if rounds_returned > 0:
        AmmunitionLedger.objects.create(
            client_generated_id=f"AMMO-RET-{transfer.transfer_id}",
            company_id=company_id,
            lot_id=lot_id,
            ammunition_type=ammo_type,
            entry_type='RETURNED',
            destination_location_id=dest_id,
            weapon_id=weapon_id,
            guard_id=guard_id,
            transfer_id=transfer.transfer_id,
            quantity=rounds_returned,
            reason=f"Returned with weapon {weapon.asset_id}"
        )

    if rounds_expended > 0:
        AmmunitionLedger.objects.create(
            client_generated_id=f"AMMO-EXP-{transfer.transfer_id}",
            company_id=company_id,
            lot_id=lot_id,
            ammunition_type=ammo_type,
            entry_type='EXPENDED',
            weapon_id=weapon_id,
            guard_id=guard_id,
            transfer_id=transfer.transfer_id,
            incident_id=incident_id,
            quantity=rounds_expended,
            reason=f"Expended during incident {incident_id}"
        )

        WeaponAlert.objects.create(
            company_id=company_id,
            alert_type='EXPENDITURE_DISCHARGE',
            priority='CRITICAL',
            related_entity_type='AmmunitionLedger',
            related_entity_id=transfer.transfer_id,
            recipient_role='ADMIN',
            site_id=custody.site_id,
            title='Critical: Ammunition Expended / Discharge Reported',
            message=f"Weapon {weapon.asset_id}: {rounds_expended} rounds expended in incident {incident_id}."
        )

    # If weapon was damaged upon return, create maintenance log (FR-12.144)
    if condition in ['DAMAGED', 'NEEDS_REPAIR', 'BROKEN']:
        WeaponMaintenanceLog.objects.create(
            weapon_id=weapon_id,
            company_id=company_id,
            maintenance_type='REPAIR',
            done_by='Pending Armourer Inspection',
            outcome='PENDING_PARTS',
            notes=f"Damage reported upon return from guard custody: {condition}. {reason}"
        )
        weapon.status = 'IN_MAINTENANCE'
        weapon.status_reason = f"Sent to maintenance due to return damage: {condition}"
        weapon.save()

    # Close any open recovery records
    WeaponRecovery.objects.filter(weapon_id=weapon_id, status='RECOVERY_REQUIRED').update(
        status='CLOSED',
        return_transfer_id=transfer.transfer_id,
        closed_at=now
    )

    try:
        write_audit_event(
            action_code='WEAPON_RETURNED',
            actor_user=actor_user,
            company_id=company_id,
            module='weapons_register',
            entity_name='WeaponTransfer',
            entity_id=str(transfer.transfer_id),
            payload={'weapon_id': str(weapon_id), 'guard_id': str(guard_id), 'condition': condition}
        )
    except Exception:
        pass

    return transfer


# -----------------------------------------------------------------------------
# GUARD-TO-GUARD HANDOVER (PRD FR-12.118 to FR-12.126)
# -----------------------------------------------------------------------------
@transaction.atomic
def process_guard_handover(
    outgoing_guard, incoming_guard_id, weapon_id,
    ammunition_count, condition="GOOD", handover_ref=None, site_id=None
):
    """
    Direct handover between outgoing guard and incoming guard.
    Validates incoming guard's eligibility and assignment.
    """
    company_id = outgoing_guard.company_id
    today = date.today()
    now = timezone.now()

    weapon = Weapon.objects.filter(weapon_id=weapon_id, company_id=company_id).first()
    if not weapon:
        raise ValueError("Weapon not found.")

    custody = WeaponCustodyRecord.objects.filter(weapon_id=weapon_id, is_current=True).first()
    if not custody or str(custody.custodian_id) != str(outgoing_guard.user_id):
        raise ValueError("Weapon is not in your current custody.")

    # Validate incoming guard's eligibility
    is_valid, err_msg = validate_issue_eligibility(
        guard_id=incoming_guard_id,
        weapon_id=weapon_id,
        site_id=site_id or custody.site_id,
        duty_date=today,
        company_id=company_id,
        issuer_user=outgoing_guard,
        is_handover=True
    )
    if not is_valid:
        raise ValueError(f"Handover blocked: {err_msg}")

    # Close outgoing custody
    custody.is_current = False
    custody.end_time = now
    custody.save()

    # Create transfer record
    transfer = WeaponTransfer.objects.create(
        client_generated_id=f"TX-HND-{uuid.uuid4().hex[:12].upper()}",
        company_id=company_id,
        weapon_id=weapon_id,
        transfer_type='HANDOVER',
        from_custodian_type='GUARD',
        from_custodian_id=outgoing_guard.user_id,
        to_custodian_type='GUARD',
        to_custodian_id=incoming_guard_id,
        site_id=site_id or custody.site_id,
        status='COMPLETED',
        condition_before=condition,
        condition_after=condition,
        rounds_issued=ammunition_count,
        handover_id=handover_ref if isinstance(handover_ref, uuid.UUID) else None,
        guard_confirmation_id=outgoing_guard.user_id,
        guard_confirmed_at=now,
        receiver_confirmation_id=incoming_guard_id,
        receiver_confirmed_at=now
    )

    custody.end_transfer_id = transfer.transfer_id
    custody.save()

    # Create new current custody for incoming guard
    new_custody = WeaponCustodyRecord.objects.create(
        weapon_id=weapon_id,
        custodian_type='GUARD',
        custodian_id=incoming_guard_id,
        start_transfer_id=transfer.transfer_id,
        start_time=now,
        is_current=True,
        ammunition_rounds=ammunition_count,
        site_id=site_id or custody.site_id
    )

    weapon.current_custody_id = new_custody.custody_id
    weapon.status_updated_at = now
    weapon.save()

    # Notify Site Supervisor
    WeaponAlert.objects.create(
        company_id=company_id,
        alert_type='DISCREPANCY',
        priority='NORMAL',
        related_entity_type='WeaponTransfer',
        related_entity_id=transfer.transfer_id,
        recipient_role='SUPERVISOR',
        site_id=site_id or custody.site_id,
        title='Guard Handover Completed',
        message=f"Weapon {weapon.asset_id} handed over from {outgoing_guard.email} to incoming guard."
    )

    try:
        write_audit_event(
            action_code='GUARD_HANDOVER_COMPLETED',
            actor_user=outgoing_guard,
            company_id=company_id,
            module='weapons_register',
            entity_name='WeaponTransfer',
            entity_id=str(transfer.transfer_id),
            payload={'weapon_id': str(weapon_id), 'from_guard': str(outgoing_guard.user_id), 'to_guard': str(incoming_guard_id)}
        )
    except Exception:
        pass

    return transfer


# -----------------------------------------------------------------------------
# MISSING OR STOLEN WEAPON REPORTING (PRD FR-12.206 to FR-12.210, AC-12.60)
# -----------------------------------------------------------------------------
@transaction.atomic
def report_missing_or_stolen_weapon(reporting_user, weapon_id, description, is_stolen=False):
    """
    Submits urgent missing/stolen weapon report.
    Updates weapon status to MISSING or LOST_OR_STOLEN.
    Raises CRITICAL alert to Admin.
    """
    company_id = reporting_user.company_id
    now = timezone.now()

    weapon = Weapon.objects.filter(weapon_id=weapon_id, company_id=company_id).first()
    if not weapon:
        raise ValueError("Weapon record not found.")

    new_status = 'LOST_OR_STOLEN' if is_stolen else 'MISSING'
    weapon.status = new_status
    weapon.status_reason = description
    weapon.status_updated_at = now
    weapon.save()

    # Create Critical Alert
    alert = WeaponAlert.objects.create(
        company_id=company_id,
        alert_type='LOST_OR_STOLEN' if is_stolen else 'MISSING_WEAPON',
        priority='CRITICAL',
        related_entity_type='Weapon',
        related_entity_id=weapon_id,
        recipient_role='ADMIN',
        title=f"CRITICAL: Weapon {weapon.asset_id} Reported {new_status}",
        message=f"Reported by {reporting_user.email}. Details: {description}"
    )

    try:
        write_audit_event(
            action_code=f'WEAPON_REPORTED_{new_status}',
            actor_user=reporting_user,
            company_id=company_id,
            module='weapons_register',
            entity_name='Weapon',
            entity_id=str(weapon.weapon_id),
            payload={'asset_id': weapon.asset_id, 'description': description}
        )
    except Exception:
        pass

    return weapon, alert


# -----------------------------------------------------------------------------
# GUARD STATUS CHANGE EVENT HANDLER (PRD FR-12.183 to FR-12.190, AC-12.44)
# -----------------------------------------------------------------------------
@transaction.atomic
def handle_guard_status_change(guard_id, new_status, company_id):
    """
    Called when guard becomes SUSPENDED, RESIGNED, TERMINATED, or document expired.
    If guard holds weapon, flags Recovery Required with High priority alert.
    """
    active_custody = WeaponCustodyRecord.objects.filter(
        custodian_type='GUARD',
        custodian_id=guard_id,
        is_current=True
    ).all()

    recoveries = []
    for custody in active_custody:
        recovery = WeaponRecovery.objects.create(
            company_id=company_id,
            guard_id=guard_id,
            weapon_id=custody.weapon_id,
            ammunition_rounds=custody.ammunition_rounds,
            trigger_reason=new_status if new_status in ['SUSPENSION', 'RESIGNATION', 'TERMINATION'] else 'NOT_DEPLOYABLE',
            status='RECOVERY_REQUIRED',
            last_known_site_id=custody.site_id,
            notes=f"Guard status changed to {new_status} while holding weapon."
        )
        recoveries.append(recovery)

        WeaponAlert.objects.create(
            company_id=company_id,
            alert_type='RECOVERY_REQUIRED',
            priority='HIGH',
            related_entity_type='WeaponRecovery',
            related_entity_id=recovery.recovery_id,
            recipient_role='ADMIN',
            site_id=custody.site_id,
            title='High Priority: Armed Weapon Recovery Required',
            message=f"Guard {guard_id} changed to {new_status}. Immediate weapon and ammunition recovery required."
        )

    return recoveries


# -----------------------------------------------------------------------------
# CHECK-OUT CUSTODY VALIDATION (PRD FR-12.136, AC-12.37)
# -----------------------------------------------------------------------------
def check_out_custody_validation(guard_id, company_id):
    """
    Exposed to Module 6 during shift check-out.
    Returns whether the guard currently holds a weapon.
    """
    custodies = WeaponCustodyRecord.objects.filter(
        custodian_type='GUARD',
        custodian_id=guard_id,
        is_current=True
    ).all()

    if not custodies.exists():
        return {'has_weapon': False, 'weapons': [], 'recommended_action': 'ALLOW'}

    weapons_info = []
    for c in custodies:
        w = Weapon.objects.filter(weapon_id=c.weapon_id).first()
        weapons_info.append({
            'asset_id': w.asset_id if w else None,
            'rounds': c.ammunition_rounds
        })

    return {
        'has_weapon': True,
        'weapons': weapons_info,
        'recommended_action': 'BLOCK',
        'message': 'Check-out blocked: You still have an assigned weapon in your custody. Please return the weapon or complete a handover first.'
    }


# -----------------------------------------------------------------------------
# PANIC CUSTODY HOOK (PRD FR-12.211 to FR-12.214, AC-12.61, AC-12.62)
# -----------------------------------------------------------------------------
def panic_custody_query(guard_id, company_id, requesting_user):
    """
    Exposed to Module 9 panic responders.
    Returns whether guard is armed, which weapon, and ammunition count.
    CLIENT role is strictly denied.
    """
    if requesting_user.role == 'CLIENT':
        raise PermissionError("Clients are prohibited from viewing weapon custody information.")

    custody = WeaponCustodyRecord.objects.filter(
        custodian_type='GUARD',
        custodian_id=guard_id,
        is_current=True
    ).first()

    if not custody:
        return {'has_weapon': False}

    weapon = Weapon.objects.filter(weapon_id=custody.weapon_id).first()
    return {
        'has_weapon': True,
        'weapon_id': str(weapon.weapon_id) if weapon else None,
        'asset_id': weapon.asset_id if weapon else None,
        'weapon_type': weapon.weapon_type if weapon else None,
        'ammunition_rounds': custody.ammunition_rounds,
        'custody_start_time': custody.start_time.isoformat() if custody.start_time else None,
        'status': weapon.status if weapon else 'ISSUED'
    }
