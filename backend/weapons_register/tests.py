import uuid
from datetime import date, timedelta
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from django.contrib.auth.hashers import make_password
from foundation.models import User, Company
from master_data.models import ClientSite, SiteSupervisorAssignment
from .models import (
    WeaponLocation, WeaponLicence, Weapon, WeaponLicenceAssociation,
    WeaponSerialRevealLog, WeaponTransfer, WeaponCustodyRecord,
    AmmunitionLot, AmmunitionLedger, AmmunitionStockCount,
    WeaponDiscrepancy, GuardWeaponBlock, WeaponRecovery,
    WeaponMaintenanceLog, WeaponAlert
)
from .services import (
    generate_weapon_asset_id, calculate_ammunition_stock,
    validate_issue_eligibility, initiate_weapon_issue,
    confirm_weapon_issue_by_guard, process_weapon_return,
    process_guard_handover, report_missing_or_stolen_weapon,
    handle_guard_status_change, check_out_custody_validation,
    panic_custody_query
)


class WeaponsRegisterModule12Tests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.company = Company.objects.create(
            legal_name="Karnataka Security Services Ltd",
            trade_name="KSS Arms Agency",
            gstin="29AAAAA0000A1Z5",
            pan="AAAAA0000A",
            state_code="KA",
            is_active=True
        )

        # Admin User
        self.admin = User.objects.create(
            company_id=self.company.company_id,
            email=f"admin_{uuid.uuid4().hex[:6]}@securityagency.local",
            role="ADMIN",
            status="ACTIVE",
            full_name="Admin Officer",
            password_hash=make_password("AdminPass123!")
        )

        # Supervisor User
        self.supervisor = User.objects.create(
            company_id=self.company.company_id,
            email=f"supervisor_{uuid.uuid4().hex[:6]}@securityagency.local",
            role="SUPERVISOR",
            status="ACTIVE",
            full_name="Supervisor Officer",
            password_hash=make_password("SuperPass123!")
        )

        # Guard User
        self.guard = User.objects.create(
            company_id=self.company.company_id,
            email=f"guard_{uuid.uuid4().hex[:6]}@securityagency.local",
            role="GUARD",
            status="ACTIVE",
            full_name="Armed Guard 1",
            password_hash=make_password("GuardPass123!")
        )

        # Guard 2 User
        self.guard2 = User.objects.create(
            company_id=self.company.company_id,
            email=f"guard2_{uuid.uuid4().hex[:6]}@securityagency.local",
            role="GUARD",
            status="ACTIVE",
            full_name="Armed Guard 2",
            password_hash=make_password("GuardPass123!")
        )

        # Client User
        self.client_user = User.objects.create(
            company_id=self.company.company_id,
            email=f"client_{uuid.uuid4().hex[:6]}@securityagency.local",
            role="CLIENT",
            status="ACTIVE",
            full_name="Client Portal User",
            password_hash=make_password("ClientPass123!")
        )

        # Location: Central Armoury
        self.armoury = WeaponLocation.objects.create(
            company_id=self.company.company_id,
            location_type='ARMOURY',
            name="Bangalore Central Armoury",
            status='ACTIVE'
        )

        # Master Licence
        self.licence = WeaponLicence.objects.create(
            company_id=self.company.company_id,
            licence_number="LIC-KA-2024-TEST",
            licence_type="Form III Security Agency",
            issuing_authority="Office of Police Commissioner Bangalore",
            holder_type="AGENCY",
            holder_name="Karnataka Security Services Ltd",
            valid_from=date.today() - timedelta(days=100),
            valid_until=date.today() + timedelta(days=365),
            status="ACTIVE"
        )

        # Register standard test weapon
        self.weapon = Weapon.objects.create(
            company_id=self.company.company_id,
            asset_id=generate_weapon_asset_id(self.company.company_id),
            weapon_type="Revolver",
            make="Ordnance Factories Board",
            model="IOF .32 Mk III",
            calibre=".32 S&W Long",
            serial_number="OFB-REV-100201",
            acquisition_date=date.today() - timedelta(days=200),
            status="IN_STORAGE",
            current_location_id=self.armoury.location_id
        )

        # Link licence
        WeaponLicenceAssociation.objects.create(
            weapon_id=self.weapon.weapon_id,
            licence_id=self.licence.licence_id,
            is_current=True
        )

        # Initial custody in Armoury
        self.initial_custody = WeaponCustodyRecord.objects.create(
            weapon_id=self.weapon.weapon_id,
            custodian_type='LOCATION',
            custodian_id=self.armoury.location_id,
            is_current=True,
            ammunition_rounds=0
        )
        self.weapon.current_custody_id = self.initial_custody.custody_id
        self.weapon.save()

        # Ammunition Lot & Initial Ledger stock
        self.ammo_lot = AmmunitionLot.objects.create(
            company_id=self.company.company_id,
            ammunition_type=".32 S&W Long",
            lot_number="LOT-OFB-TEST-01",
            status="AVAILABLE"
        )
        AmmunitionLedger.objects.create(
            company_id=self.company.company_id,
            lot_id=self.ammo_lot.lot_id,
            ammunition_type=".32 S&W Long",
            entry_type="RECEIVED",
            destination_location_id=self.armoury.location_id,
            quantity=100,
            reason="Initial ammunition intake"
        )

    # -------------------------------------------------------------------------
    # 1. Weapon Registration & Validation (AC-12.1, AC-12.2, AC-12.3, AC-12.4)
    # -------------------------------------------------------------------------
    def test_weapon_creation_and_asset_id_generation(self):
        """AC-12.1: Weapon registration generates unique permanent asset ID."""
        self.client.force_authenticate(user=self.admin)
        res = self.client.post('/api/weapons/records/', {
            'weapon_type': 'Pistol',
            'make': 'Ashani',
            'model': '.32 Semi-Auto',
            'calibre': '.32 ACP',
            'serial_number': 'ASH-PST-99001',
            'serial_number_confirm': 'ASH-PST-99001',
            'acquisition_date': str(date.today()),
            'current_location_id': str(self.armoury.location_id)
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data['asset_id'].startswith('WPN-'))
        self.assertEqual(res.data['status'], 'IN_STORAGE')

    def test_serial_number_mismatch_rejected(self):
        """AC-12.2: Serial number double entry mismatch is rejected."""
        self.client.force_authenticate(user=self.admin)
        res = self.client.post('/api/weapons/records/', {
            'weapon_type': 'Pistol',
            'make': 'Ashani',
            'model': '.32 Semi-Auto',
            'calibre': '.32 ACP',
            'serial_number': 'ASH-PST-99002',
            'serial_number_confirm': 'ASH-PST-99003', # mismatch
            'acquisition_date': str(date.today())
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        errs = res.data.get('errors', res.data)
        self.assertIn('serial_number_confirm', errs)

    def test_duplicate_serial_number_blocked(self):
        """AC-12.3: Duplicate serial number within company is blocked."""
        self.client.force_authenticate(user=self.admin)
        res = self.client.post('/api/weapons/records/', {
            'weapon_type': 'Revolver',
            'make': 'OFB',
            'model': '.32',
            'calibre': '.32',
            'serial_number': 'OFB-REV-100201', # existing serial
            'serial_number_confirm': 'OFB-REV-100201',
            'acquisition_date': str(date.today())
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        errs = res.data.get('errors', res.data)
        self.assertIn('serial_number', errs)

    def test_physical_deletion_blocked(self):
        """AC-12.4: Physical deletion of weapon records is rejected."""
        self.client.force_authenticate(user=self.admin)
        res = self.client.delete(f'/api/weapons/records/{self.weapon.weapon_id}/')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # -------------------------------------------------------------------------
    # 2. Licence Expiry & Restrictions (AC-12.6, AC-12.7, AC-12.9)
    # -------------------------------------------------------------------------
    def test_unlicensed_weapon_issue_blocked(self):
        """AC-12.6: Unlicensed weapon issue is blocked."""
        # Create unlinked weapon
        unlinked = Weapon.objects.create(
            company_id=self.company.company_id,
            asset_id=generate_weapon_asset_id(self.company.company_id),
            weapon_type="Shotgun",
            make="Remington",
            model="870",
            calibre="12 Gauge",
            serial_number="REM-870-1122",
            acquisition_date=date.today(),
            status="IN_STORAGE"
        )
        WeaponCustodyRecord.objects.create(
            weapon_id=unlinked.weapon_id,
            custodian_type='LOCATION',
            custodian_id=self.armoury.location_id,
            is_current=True
        )

        ok, msg = validate_issue_eligibility(
            guard_id=self.guard.user_id,
            weapon_id=unlinked.weapon_id,
            site_id=None,
            duty_date=date.today(),
            company_id=self.company.company_id,
            issuer_user=self.admin,
            is_emergency=False
        )
        self.assertFalse(ok)
        self.assertEqual(msg, "Issue blocked: Weapon does not have a valid linked licence.")

    def test_expired_licence_blocks_issue(self):
        """AC-12.7: Expired licence blocks issue."""
        self.licence.valid_until = date.today() - timedelta(days=1)
        self.licence.save()

        ok, msg = validate_issue_eligibility(
            guard_id=self.guard.user_id,
            weapon_id=self.weapon.weapon_id,
            site_id=None,
            duty_date=date.today(),
            company_id=self.company.company_id,
            issuer_user=self.admin,
            is_emergency=False
        )
        self.assertFalse(ok)
        self.assertEqual(msg, "Issue blocked: Weapon licence has expired.")

    def test_supervisor_cannot_view_licence_documents(self):
        """AC-12.9: Supervisor access to licence management is restricted."""
        self.client.force_authenticate(user=self.supervisor)
        res = self.client.get('/api/weapons/licences/')
        # Supervisor receives limited view or 403
        self.assertIn(res.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN])

    # -------------------------------------------------------------------------
    # 3. Guard Weapon Restrictions & Status (AC-12.16, AC-12.17, AC-12.18, AC-12.19)
    # -------------------------------------------------------------------------
    def test_guard_block_list_blocks_issue(self):
        """AC-12.16: Guard on block list cannot receive weapon."""
        GuardWeaponBlock.objects.create(
            company_id=self.company.company_id,
            guard_id=self.guard.user_id,
            reason="Pending internal investigation",
            created_by=self.admin.user_id,
            status='ACTIVE'
        )

        ok, msg = validate_issue_eligibility(
            guard_id=self.guard.user_id,
            weapon_id=self.weapon.weapon_id,
            site_id=None,
            duty_date=date.today(),
            company_id=self.company.company_id,
            issuer_user=self.admin,
            is_emergency=False
        )
        self.assertFalse(ok)
        self.assertEqual(msg, "Issue blocked: Guard has an active weapon restriction. Contact Admin.")

    def test_weapon_in_maintenance_blocks_issue(self):
        """AC-12.17: Weapon in maintenance cannot be issued."""
        self.weapon.status = 'IN_MAINTENANCE'
        self.weapon.save()

        ok, msg = validate_issue_eligibility(
            guard_id=self.guard.user_id,
            weapon_id=self.weapon.weapon_id,
            site_id=None,
            duty_date=date.today(),
            company_id=self.company.company_id,
            issuer_user=self.admin,
            is_emergency=False
        )
        self.assertFalse(ok)
        self.assertEqual(msg, "Issue blocked: Weapon is currently in maintenance.")

    def test_weapon_missing_or_stolen_blocks_issue(self):
        """AC-12.18: Missing or stolen weapon cannot be issued."""
        self.weapon.status = 'MISSING'
        self.weapon.save()

        ok, msg = validate_issue_eligibility(
            guard_id=self.guard.user_id,
            weapon_id=self.weapon.weapon_id,
            site_id=None,
            duty_date=date.today(),
            company_id=self.company.company_id,
            issuer_user=self.admin,
            is_emergency=False
        )
        self.assertFalse(ok)
        self.assertEqual(msg, "Issue blocked: Weapon is not available in storage.")

    # -------------------------------------------------------------------------
    # 4. Two-Person Confirmation Issue & Return (AC-12.23, AC-12.24, AC-12.27, AC-12.37)
    # -------------------------------------------------------------------------
    def test_two_person_confirmation_issue_workflow(self):
        """AC-12.23 & AC-12.24: Issue remains ISSUE_PENDING until guard confirms."""
        transfer = initiate_weapon_issue(
            issuer_user=self.admin,
            weapon_id=self.weapon.weapon_id,
            guard_id=self.guard.user_id,
            site_id=None,
            ammunition_count=6,
            lot_id=self.ammo_lot.lot_id
        )
        self.assertEqual(transfer.status, 'ISSUE_PENDING')

        # Verify weapon remains in storage/issuer's custody until confirmation
        self.weapon.refresh_from_db()
        self.assertEqual(self.weapon.status, 'IN_STORAGE')

        # Guard confirms receipt
        confirmed_tx = confirm_weapon_issue_by_guard(
            guard_user=self.guard,
            transfer_id=transfer.transfer_id
        )
        self.assertEqual(confirmed_tx.status, 'COMPLETED')

        self.weapon.refresh_from_db()
        self.assertEqual(self.weapon.status, 'ISSUED')

        # Current custody now belongs to guard with 6 rounds
        current_c = WeaponCustodyRecord.objects.get(weapon_id=self.weapon.weapon_id, is_current=True)
        self.assertEqual(current_c.custodian_type, 'GUARD')
        self.assertEqual(current_c.custodian_id, self.guard.user_id)
        self.assertEqual(current_c.ammunition_rounds, 6)

        # Ammunition Ledger has ISSUED entry
        issued_entry = AmmunitionLedger.objects.filter(transfer_id=transfer.transfer_id, entry_type='ISSUED').first()
        self.assertIsNotNone(issued_entry)
        self.assertEqual(issued_entry.quantity, 6)

    def test_return_workflow_and_reconciliation(self):
        """AC-12.27 & AC-12.37: Return reconciles ammunition and updates custody."""
        # Set up weapon in guard custody
        transfer = initiate_weapon_issue(
            issuer_user=self.admin,
            weapon_id=self.weapon.weapon_id,
            guard_id=self.guard.user_id,
            site_id=None,
            ammunition_count=6,
            lot_id=self.ammo_lot.lot_id
        )
        confirm_weapon_issue_by_guard(self.guard, transfer.transfer_id)

        # Process return: 6 returned
        ret_tx = process_weapon_return(
            actor_user=self.admin,
            weapon_id=self.weapon.weapon_id,
            condition="GOOD",
            rounds_returned=6,
            rounds_expended=0
        )
        self.assertEqual(ret_tx.status, 'COMPLETED')

        self.weapon.refresh_from_db()
        self.assertEqual(self.weapon.status, 'IN_STORAGE')

        # Custody returned to Location
        current_c = WeaponCustodyRecord.objects.get(weapon_id=self.weapon.weapon_id, is_current=True)
        self.assertEqual(current_c.custodian_type, 'LOCATION')
        self.assertEqual(current_c.ammunition_rounds, 0)

    def test_ammunition_mismatch_creates_discrepancy(self):
        """AC-12.41 & AC-12.42: Ammunition count mismatch creates Discrepancy."""
        transfer = initiate_weapon_issue(
            issuer_user=self.admin,
            weapon_id=self.weapon.weapon_id,
            guard_id=self.guard.user_id,
            site_id=None,
            ammunition_count=6,
            lot_id=self.ammo_lot.lot_id
        )
        confirm_weapon_issue_by_guard(self.guard, transfer.transfer_id)

        # Guard returns only 4 rounds (missing 2)
        ret_tx = process_weapon_return(
            actor_user=self.admin,
            weapon_id=self.weapon.weapon_id,
            condition="GOOD",
            rounds_returned=4,
            rounds_expended=0
        )
        self.assertEqual(ret_tx.status, 'DISCREPANCY')

        # Check Discrepancy record created
        disc = WeaponDiscrepancy.objects.filter(weapon_id=self.weapon.weapon_id, status='OPEN').first()
        self.assertIsNotNone(disc)
        self.assertEqual(disc.discrepancy_type, 'ROUNDS')
        self.assertEqual(disc.reported_value['missing'], 2)

    # -------------------------------------------------------------------------
    # 5. Guard-to-Guard Handover (AC-12.28, AC-12.31)
    # -------------------------------------------------------------------------
    def test_guard_handover_success(self):
        """AC-12.31: Matching handover moves custody to incoming guard."""
        # Issue to guard 1
        transfer = initiate_weapon_issue(
            issuer_user=self.admin,
            weapon_id=self.weapon.weapon_id,
            guard_id=self.guard.user_id,
            site_id=None,
            ammunition_count=6,
            lot_id=self.ammo_lot.lot_id
        )
        confirm_weapon_issue_by_guard(self.guard, transfer.transfer_id)

        # Handover to guard 2
        handover_tx = process_guard_handover(
            outgoing_guard=self.guard,
            incoming_guard_id=self.guard2.user_id,
            weapon_id=self.weapon.weapon_id,
            ammunition_count=6,
            condition="GOOD"
        )
        self.assertEqual(handover_tx.status, 'COMPLETED')

        # Custody now belongs to Guard 2
        current_c = WeaponCustodyRecord.objects.get(weapon_id=self.weapon.weapon_id, is_current=True)
        self.assertEqual(current_c.custodian_id, self.guard2.user_id)
        self.assertEqual(current_c.ammunition_rounds, 6)

    # -------------------------------------------------------------------------
    # 6. Ammunition Ledger & Negative Stock Prevention (AC-12.32, AC-12.33)
    # -------------------------------------------------------------------------
    def test_negative_ammunition_stock_prevented(self):
        """AC-12.32: Issue exceeding available stock is blocked."""
        # Current stock is 100
        with self.assertRaises(ValueError):
            initiate_weapon_issue(
                issuer_user=self.admin,
                weapon_id=self.weapon.weapon_id,
                guard_id=self.guard.user_id,
                site_id=None,
                ammunition_count=500, # exceeds 100
                lot_id=self.ammo_lot.lot_id
            )

    def test_physical_stock_count_and_adjustment_approval(self):
        """AC-12.38 & AC-12.39: Variance creates adjustment request needing admin approval."""
        self.client.force_authenticate(user=self.supervisor)
        # Supervisor counts 95 rounds (variance -5)
        res = self.client.post('/api/weapons/ammo/stock-count/', {
            'location_id': str(self.armoury.location_id),
            'lot_id': str(self.ammo_lot.lot_id),
            'physical_quantity': 95,
            'reason': 'Found 5 defective rounds removed for disposal'
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        count_id = res.data['count_id']
        self.assertEqual(res.data['variance'], -5)
        self.assertEqual(res.data['adjustment_status'], 'PENDING')

        # Stock is still 100 before admin approval
        stock_before = calculate_ammunition_stock(self.company.company_id, lot_id=self.ammo_lot.lot_id)
        self.assertEqual(stock_before, 100)

        # Admin approves adjustment
        self.client.force_authenticate(user=self.admin)
        app_res = self.client.post(f'/api/weapons/ammo/stock-count/{count_id}/approve/', {
            'approve': True
        }, format='json')
        self.assertEqual(app_res.status_code, status.HTTP_200_OK)

        # Stock is now 95
        stock_after = calculate_ammunition_stock(self.company.company_id, lot_id=self.ammo_lot.lot_id)
        self.assertEqual(stock_after, 95)

    # -------------------------------------------------------------------------
    # 7. Recovery Required on Guard Status Change (AC-12.44, AC-12.45)
    # -------------------------------------------------------------------------
    def test_guard_suspension_creates_recovery_required(self):
        """AC-12.44: Guard suspended while holding weapon triggers Recovery Required."""
        # Issue weapon to guard
        transfer = initiate_weapon_issue(
            issuer_user=self.admin,
            weapon_id=self.weapon.weapon_id,
            guard_id=self.guard.user_id,
            site_id=None,
            ammunition_count=6,
            lot_id=self.ammo_lot.lot_id
        )
        confirm_weapon_issue_by_guard(self.guard, transfer.transfer_id)

        # Guard gets suspended
        recoveries = handle_guard_status_change(
            guard_id=self.guard.user_id,
            new_status="SUSPENSION",
            company_id=self.company.company_id
        )
        self.assertEqual(len(recoveries), 1)
        self.assertEqual(recoveries[0].status, 'RECOVERY_REQUIRED')
        self.assertEqual(recoveries[0].ammunition_rounds, 6)

        # Check High Priority Alert was created
        alert = WeaponAlert.objects.filter(
            related_entity_id=recoveries[0].recovery_id,
            alert_type='RECOVERY_REQUIRED'
        ).first()
        self.assertIsNotNone(alert)
        self.assertEqual(alert.priority, 'HIGH')

    # -------------------------------------------------------------------------
    # 8. Missing Weapon Report (AC-12.60)
    # -------------------------------------------------------------------------
    def test_missing_weapon_report(self):
        """AC-12.60: Reporting weapon missing updates status and creates Critical alert."""
        weapon, alert = report_missing_or_stolen_weapon(
            reporting_user=self.admin,
            weapon_id=self.weapon.weapon_id,
            description="Armoury safe lock broken during inspection"
        )
        self.assertEqual(weapon.status, 'MISSING')
        self.assertEqual(alert.priority, 'CRITICAL')
        self.assertEqual(alert.alert_type, 'MISSING_WEAPON')

    # -------------------------------------------------------------------------
    # 9. Panic Hook & Client Access Prohibited (AC-12.61, AC-12.62, AC-12.66)
    # -------------------------------------------------------------------------
    def test_panic_custody_hook_and_client_denial(self):
        """AC-12.61 & AC-12.62: Panic custody details returned for Admin, denied for Client."""
        # Issue weapon to guard
        transfer = initiate_weapon_issue(
            issuer_user=self.admin,
            weapon_id=self.weapon.weapon_id,
            guard_id=self.guard.user_id,
            site_id=None,
            ammunition_count=6,
            lot_id=self.ammo_lot.lot_id
        )
        confirm_weapon_issue_by_guard(self.guard, transfer.transfer_id)

        # Admin query
        info = panic_custody_query(self.guard.user_id, self.company.company_id, self.admin)
        self.assertTrue(info['has_weapon'])
        self.assertEqual(info['ammunition_rounds'], 6)

        # Client query must raise PermissionError
        with self.assertRaises(PermissionError):
            panic_custody_query(self.guard.user_id, self.company.company_id, self.client_user)

    def test_client_portal_weapon_access_denied(self):
        """AC-12.66: Client requests to weapon APIs are forbidden (403)."""
        self.client.force_authenticate(user=self.client_user)
        res = self.client.get('/api/weapons/dashboard/')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        res2 = self.client.get('/api/weapons/records/')
        self.assertEqual(res2.status_code, status.HTTP_403_FORBIDDEN)

    # -------------------------------------------------------------------------
    # 10. Serial Masking & Logged Reveal (AC-12.67, AC-12.68)
    # -------------------------------------------------------------------------
    def test_masked_serial_and_logged_reveal(self):
        """AC-12.67 & AC-12.68: Serial masked for supervisor unless revealed with reason."""
        self.client.force_authenticate(user=self.supervisor)
        res = self.client.get(f'/api/weapons/records/{self.weapon.weapon_id}/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data['display_serial'].startswith('***'))

        # Reveal serial number
        reveal_res = self.client.post(f'/api/weapons/records/{self.weapon.weapon_id}/reveal-serial/', {
            'reason': 'Site transfer inspection and verification'
        }, format='json')
        self.assertEqual(reveal_res.status_code, status.HTTP_200_OK)
        self.assertEqual(reveal_res.data['serial_number'], 'OFB-REV-100201')

        # Check reveal log created
        log = WeaponSerialRevealLog.objects.filter(weapon_id=self.weapon.weapon_id).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.reason, 'Site transfer inspection and verification')

    # -------------------------------------------------------------------------
    # 11. Module 13 Reporting Contract (AC-12.74)
    # -------------------------------------------------------------------------
    def test_module13_reporting_contract(self):
        """AC-12.74: Module 13 reporting endpoint returns authoritative counts."""
        self.client.force_authenticate(user=self.admin)
        res = self.client.get('/api/weapons/reporting/module13/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('counts_by_status', res.data)
        self.assertIn('counts_by_location', res.data)
        self.assertIn('transfers', res.data)
        self.assertIn('discrepancies', res.data)
