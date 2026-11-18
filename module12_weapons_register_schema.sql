-- ==============================================================================
-- Module 12: Armed Guard and Weapons Register Schema
-- Security Agency Management and Monitoring System (SGIMS)
-- Target Schema: security_erp
-- PostgreSQL 18 Compatible | Tamper-Evident Custody Chain & Immutable Ammunition Ledger
-- ==============================================================================

SET search_path TO security_erp, public;

-- Drop obsolete basic placeholder tables if they exist
DROP TABLE IF EXISTS security_erp.ammunition_transactions CASCADE;
DROP TABLE IF EXISTS security_erp.weapon_assignments CASCADE;
DROP TABLE IF EXISTS security_erp.weapons CASCADE;

-- ------------------------------------------------------------------------------
-- 1. WEAPON LOCATIONS (PRD 12.4, FR-12.42 to FR-12.45)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.weapon_locations (
    location_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES security_erp.companies(company_id) ON DELETE RESTRICT,
    location_type VARCHAR(30) NOT NULL CHECK (location_type IN ('ARMOURY', 'SITE_STORAGE', 'GUARD_CUSTODY', 'MAINTENANCE', 'AUTHORITY', 'UNKNOWN')),
    site_id UUID REFERENCES security_erp.client_sites(site_id) ON DELETE SET NULL,
    name VARCHAR(150) NOT NULL,
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'INACTIVE')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_weapon_loc_company ON security_erp.weapon_locations(company_id);
CREATE INDEX IF NOT EXISTS idx_weapon_loc_site ON security_erp.weapon_locations(site_id);

-- ------------------------------------------------------------------------------
-- 2. WEAPON LICENCES (PRD 12.2, FR-12.20 to FR-12.32)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.weapon_licences (
    licence_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES security_erp.companies(company_id) ON DELETE RESTRICT,
    licence_number VARCHAR(100) NOT NULL,
    licence_type VARCHAR(100) NOT NULL,
    issuing_authority VARCHAR(200) NOT NULL,
    holder_type VARCHAR(30) NOT NULL DEFAULT 'AGENCY' CHECK (holder_type IN ('AGENCY', 'NAMED_PERSON')),
    holder_name VARCHAR(200),
    valid_from DATE NOT NULL,
    valid_until DATE NOT NULL,
    document_reference VARCHAR(500),
    quantity_limit_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    quantity_limit INT,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'EXPIRING_SOON', 'EXPIRED', 'SUSPENDED', 'REVOKED')),
    created_by UUID REFERENCES security_erp.app_users(user_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_licence_dates CHECK (valid_until >= valid_from)
);

CREATE INDEX IF NOT EXISTS idx_weapon_licence_company ON security_erp.weapon_licences(company_id);
CREATE INDEX IF NOT EXISTS idx_weapon_licence_expiry ON security_erp.weapon_licences(valid_until);

-- ------------------------------------------------------------------------------
-- 3. WEAPON MASTER RECORDS (PRD 12.1, FR-12.1 to FR-12.19)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.weapons (
    weapon_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES security_erp.companies(company_id) ON DELETE RESTRICT,
    asset_id VARCHAR(50) NOT NULL UNIQUE,
    weapon_type VARCHAR(100) NOT NULL,
    make VARCHAR(100) NOT NULL,
    model VARCHAR(100) NOT NULL,
    calibre VARCHAR(100) NOT NULL,
    serial_number VARCHAR(100) NOT NULL,
    manufacture_year INT,
    acquisition_date DATE NOT NULL,
    supplier VARCHAR(200),
    status VARCHAR(40) NOT NULL DEFAULT 'IN_STORAGE'
        CHECK (status IN (
            'IN_STORAGE', 'ISSUED', 'IN_MAINTENANCE', 
            'DEPOSITED_WITH_AUTHORITY', 'MISSING', 'LOST_OR_STOLEN', 
            'RETIRED_OR_DISPOSED'
        )),
    current_location_id UUID REFERENCES security_erp.weapon_locations(location_id) ON DELETE SET NULL,
    current_custody_id UUID,
    photo_url VARCHAR(500),
    qr_relabel_count INT NOT NULL DEFAULT 0,
    qr_last_relabeled_at TIMESTAMPTZ,
    status_reason TEXT,
    status_updated_at TIMESTAMPTZ DEFAULT now(),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by UUID REFERENCES security_erp.app_users(user_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_company_serial UNIQUE (company_id, serial_number)
);

CREATE INDEX IF NOT EXISTS idx_weapons_company_status ON security_erp.weapons(company_id, status);
CREATE INDEX IF NOT EXISTS idx_weapons_asset_id ON security_erp.weapons(asset_id);
CREATE INDEX IF NOT EXISTS idx_weapons_serial ON security_erp.weapons(serial_number);

-- ------------------------------------------------------------------------------
-- 4. WEAPON LICENCE ASSOCIATIONS (PRD 12.3, FR-12.26, FR-12.27)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.weapon_licence_associations (
    association_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    weapon_id UUID NOT NULL REFERENCES security_erp.weapons(weapon_id) ON DELETE CASCADE,
    licence_id UUID NOT NULL REFERENCES security_erp.weapon_licences(licence_id) ON DELETE CASCADE,
    effective_from DATE NOT NULL DEFAULT CURRENT_DATE,
    effective_to DATE,
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    created_by UUID REFERENCES security_erp.app_users(user_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_wla_weapon ON security_erp.weapon_licence_associations(weapon_id);
CREATE INDEX IF NOT EXISTS idx_wla_licence ON security_erp.weapon_licence_associations(licence_id);

-- ------------------------------------------------------------------------------
-- 5. SERIAL NUMBER REVEAL AUDIT LOG (PRD 7.4, FR-12.7, AC-12.68)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.weapon_serial_reveal_logs (
    reveal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES security_erp.companies(company_id) ON DELETE CASCADE,
    weapon_id UUID NOT NULL REFERENCES security_erp.weapons(weapon_id) ON DELETE CASCADE,
    revealed_by UUID NOT NULL REFERENCES security_erp.app_users(user_id) ON DELETE CASCADE,
    revealed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    reason TEXT NOT NULL,
    site_id UUID REFERENCES security_erp.client_sites(site_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_serial_reveal_weapon ON security_erp.weapon_serial_reveal_logs(weapon_id);
CREATE INDEX IF NOT EXISTS idx_serial_reveal_user ON security_erp.weapon_serial_reveal_logs(revealed_by);

-- ------------------------------------------------------------------------------
-- 6. WEAPON TRANSFERS (PRD 12.5, FR-12.44 to FR-12.46, FR-12.100 to FR-12.117)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.weapon_transfers (
    transfer_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_generated_id VARCHAR(100) NOT NULL,
    company_id UUID NOT NULL REFERENCES security_erp.companies(company_id) ON DELETE RESTRICT,
    weapon_id UUID NOT NULL REFERENCES security_erp.weapons(weapon_id) ON DELETE RESTRICT,
    transfer_type VARCHAR(40) NOT NULL CHECK (transfer_type IN (
        'ISSUE', 'RETURN', 'HANDOVER', 'LOCATION_TRANSFER', 
        'MAINTENANCE_TRANSFER', 'AUTHORITY_DEPOSIT', 'AUTHORITY_RETURN'
    )),
    from_custodian_type VARCHAR(30) NOT NULL CHECK (from_custodian_type IN ('LOCATION', 'GUARD', 'SUPERVISOR', 'MAINTENANCE', 'AUTHORITY')),
    from_custodian_id UUID NOT NULL,
    to_custodian_type VARCHAR(30) NOT NULL CHECK (to_custodian_type IN ('LOCATION', 'GUARD', 'SUPERVISOR', 'MAINTENANCE', 'AUTHORITY')),
    to_custodian_id UUID NOT NULL,
    site_id UUID REFERENCES security_erp.client_sites(site_id) ON DELETE SET NULL,
    assignment_id UUID,
    attendance_id UUID,
    handover_id UUID,
    status VARCHAR(30) NOT NULL DEFAULT 'PENDING' CHECK (status IN (
        'PENDING', 'ISSUE_PENDING', 'RETURN_PENDING', 'HANDOVER_PENDING', 
        'COMPLETED', 'DISCREPANCY', 'EXPIRED_PENDING', 'RECOVERY_REQUIRED', 'REVERSED'
    )),
    condition_before VARCHAR(100) DEFAULT 'GOOD',
    condition_after VARCHAR(100),
    rounds_issued INT NOT NULL DEFAULT 0,
    rounds_returned INT NOT NULL DEFAULT 0,
    rounds_expended INT NOT NULL DEFAULT 0,
    client_timestamp TIMESTAMPTZ,
    server_timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
    sync_timestamp TIMESTAMPTZ,
    issuer_id UUID REFERENCES security_erp.app_users(user_id) ON DELETE SET NULL,
    guard_confirmation_id UUID REFERENCES security_erp.app_users(user_id) ON DELETE SET NULL,
    guard_confirmed_at TIMESTAMPTZ,
    receiver_confirmation_id UUID REFERENCES security_erp.app_users(user_id) ON DELETE SET NULL,
    receiver_confirmed_at TIMESTAMPTZ,
    is_emergency BOOLEAN NOT NULL DEFAULT FALSE,
    emergency_reason TEXT,
    emergency_ratified_by UUID REFERENCES security_erp.app_users(user_id) ON DELETE SET NULL,
    emergency_ratified_at TIMESTAMPTZ,
    emergency_ratified_status VARCHAR(20) DEFAULT 'NONE' CHECK (emergency_ratified_status IN ('NONE', 'PENDING', 'RATIFIED', 'REJECTED')),
    is_offline BOOLEAN NOT NULL DEFAULT FALSE,
    reason TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_comp_client_gen_id UNIQUE (company_id, client_generated_id)
);

CREATE INDEX IF NOT EXISTS idx_transfers_weapon ON security_erp.weapon_transfers(weapon_id);
CREATE INDEX IF NOT EXISTS idx_transfers_company_status ON security_erp.weapon_transfers(company_id, status);
CREATE INDEX IF NOT EXISTS idx_transfers_site ON security_erp.weapon_transfers(site_id);

-- ------------------------------------------------------------------------------
-- 7. WEAPON CUSTODY RECORDS (PRD 12.6, FR-12.47 to FR-12.49)
-- Exactly one current custody record per weapon enforced via partial unique index
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.weapon_custody_records (
    custody_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    weapon_id UUID NOT NULL REFERENCES security_erp.weapons(weapon_id) ON DELETE RESTRICT,
    custodian_type VARCHAR(30) NOT NULL CHECK (custodian_type IN ('LOCATION', 'GUARD', 'SUPERVISOR', 'MAINTENANCE', 'AUTHORITY')),
    custodian_id UUID NOT NULL,
    start_transfer_id UUID REFERENCES security_erp.weapon_transfers(transfer_id) ON DELETE SET NULL,
    start_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    end_transfer_id UUID REFERENCES security_erp.weapon_transfers(transfer_id) ON DELETE SET NULL,
    end_time TIMESTAMPTZ,
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    ammunition_rounds INT NOT NULL DEFAULT 0,
    site_id UUID REFERENCES security_erp.client_sites(site_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_single_current_custody_per_weapon 
    ON security_erp.weapon_custody_records(weapon_id) 
    WHERE is_current = TRUE;

CREATE INDEX IF NOT EXISTS idx_custody_custodian ON security_erp.weapon_custody_records(custodian_id, is_current);

-- ------------------------------------------------------------------------------
-- 8. AMMUNITION LOTS (PRD 12.7, FR-12.59 to FR-12.61)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.ammunition_lots (
    lot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES security_erp.companies(company_id) ON DELETE RESTRICT,
    ammunition_type VARCHAR(100) NOT NULL,
    lot_number VARCHAR(100) NOT NULL,
    received_date DATE DEFAULT CURRENT_DATE,
    source_reference VARCHAR(200),
    status VARCHAR(30) NOT NULL DEFAULT 'AVAILABLE' CHECK (status IN (
        'AVAILABLE', 'PARTIALLY_ISSUED', 'FULLY_ISSUED', 'IN_CUSTODY', 
        'DISCREPANCY', 'DISPOSED', 'CLOSED'
    )),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_comp_ammo_lot UNIQUE (company_id, ammunition_type, lot_number)
);

CREATE INDEX IF NOT EXISTS idx_ammo_lot_company ON security_erp.ammunition_lots(company_id, ammunition_type);

-- ------------------------------------------------------------------------------
-- 9. IMMUTABLE AMMUNITION LEDGER (PRD 12.8, FR-12.62 to FR-12.75)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.ammunition_ledger (
    ledger_entry_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_generated_id VARCHAR(100),
    company_id UUID NOT NULL REFERENCES security_erp.companies(company_id) ON DELETE RESTRICT,
    lot_id UUID NOT NULL REFERENCES security_erp.ammunition_lots(lot_id) ON DELETE RESTRICT,
    ammunition_type VARCHAR(100) NOT NULL,
    entry_type VARCHAR(30) NOT NULL CHECK (entry_type IN (
        'RECEIVED', 'TRANSFERRED', 'ISSUED', 'RETURNED', 'EXPENDED', 'DISPOSED', 'ADJUSTED', 'REVERSED'
    )),
    source_location_id UUID REFERENCES security_erp.weapon_locations(location_id) ON DELETE SET NULL,
    destination_location_id UUID REFERENCES security_erp.weapon_locations(location_id) ON DELETE SET NULL,
    weapon_id UUID REFERENCES security_erp.weapons(weapon_id) ON DELETE SET NULL,
    guard_id UUID,
    transfer_id UUID REFERENCES security_erp.weapon_transfers(transfer_id) ON DELETE SET NULL,
    incident_id UUID REFERENCES security_erp.incidents(incident_id) ON DELETE SET NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    reversal_reference_id UUID REFERENCES security_erp.ammunition_ledger(ledger_entry_id) ON DELETE SET NULL,
    reason TEXT,
    approved_by UUID REFERENCES security_erp.app_users(user_id) ON DELETE SET NULL,
    actor_id UUID REFERENCES security_erp.app_users(user_id) ON DELETE SET NULL,
    server_timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ammo_ledger_company ON security_erp.ammunition_ledger(company_id, lot_id);
CREATE INDEX IF NOT EXISTS idx_ammo_ledger_weapon ON security_erp.ammunition_ledger(weapon_id);
CREATE INDEX IF NOT EXISTS idx_ammo_ledger_guard ON security_erp.ammunition_ledger(guard_id);

-- ------------------------------------------------------------------------------
-- 10. AMMUNITION PHYSICAL COUNTS & ADJUSTMENTS (PRD 12.9, FR-12.76 to FR-12.84)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.ammunition_stock_counts (
    count_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES security_erp.companies(company_id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES security_erp.weapon_locations(location_id) ON DELETE RESTRICT,
    lot_id UUID NOT NULL REFERENCES security_erp.ammunition_lots(lot_id) ON DELETE RESTRICT,
    ledger_quantity INT NOT NULL,
    physical_quantity INT NOT NULL CHECK (physical_quantity >= 0),
    variance INT NOT NULL,
    reason TEXT,
    counted_by UUID NOT NULL REFERENCES security_erp.app_users(user_id) ON DELETE RESTRICT,
    counted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    adjustment_status VARCHAR(30) NOT NULL DEFAULT 'NOT_REQUIRED' CHECK (adjustment_status IN (
        'NOT_REQUIRED', 'PENDING', 'APPROVED', 'REJECTED'
    )),
    adjustment_approved_by UUID REFERENCES security_erp.app_users(user_id) ON DELETE SET NULL,
    adjustment_approved_at TIMESTAMPTZ,
    adjustment_ledger_entry_id UUID REFERENCES security_erp.ammunition_ledger(ledger_entry_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_ammo_counts_loc ON security_erp.ammunition_stock_counts(location_id, lot_id);

-- ------------------------------------------------------------------------------
-- 11. WEAPON & AMMUNITION DISCREPANCIES (PRD 12.10, FR-12.146 to FR-12.156)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.weapon_discrepancies (
    discrepancy_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES security_erp.companies(company_id) ON DELETE RESTRICT,
    weapon_id UUID REFERENCES security_erp.weapons(weapon_id) ON DELETE SET NULL,
    transfer_id UUID REFERENCES security_erp.weapon_transfers(transfer_id) ON DELETE SET NULL,
    ledger_entry_id UUID REFERENCES security_erp.ammunition_ledger(ledger_entry_id) ON DELETE SET NULL,
    guard_id UUID,
    site_id UUID REFERENCES security_erp.client_sites(site_id) ON DELETE SET NULL,
    discrepancy_type VARCHAR(40) NOT NULL CHECK (discrepancy_type IN (
        'IDENTITY', 'ROUNDS', 'CONDITION', 'LOCATION', 'CUSTODY', 'OFFLINE_CONFLICT', 'OTHER'
    )),
    expected_value JSONB NOT NULL DEFAULT '{}'::jsonb,
    reported_value JSONB NOT NULL DEFAULT '{}'::jsonb,
    recount_value JSONB,
    explanation TEXT,
    outcome TEXT,
    incident_id UUID REFERENCES security_erp.incidents(incident_id) ON DELETE SET NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'UNDER_REVIEW', 'RESOLVED')),
    is_blocking BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ,
    resolved_by UUID REFERENCES security_erp.app_users(user_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_discrepancies_company_status ON security_erp.weapon_discrepancies(company_id, status);
CREATE INDEX IF NOT EXISTS idx_discrepancies_weapon ON security_erp.weapon_discrepancies(weapon_id);

-- ------------------------------------------------------------------------------
-- 12. GUARD WEAPON-SPECIFIC RESTRICTIONS / BLOCK LIST (PRD 12.11, FR-12.180 to FR-12.182)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.guard_weapon_blocks (
    block_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES security_erp.companies(company_id) ON DELETE RESTRICT,
    guard_id UUID NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'REVERSED')),
    reason TEXT NOT NULL,
    created_by UUID NOT NULL REFERENCES security_erp.app_users(user_id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    reversed_by UUID REFERENCES security_erp.app_users(user_id) ON DELETE SET NULL,
    reversal_reason TEXT,
    reversed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_guard_blocks_guard ON security_erp.guard_weapon_blocks(company_id, guard_id, status);

-- ------------------------------------------------------------------------------
-- 13. RECOVERY REQUIRED RECORDS (PRD 12.12, FR-12.187 to FR-12.190)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.weapon_recoveries (
    recovery_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES security_erp.companies(company_id) ON DELETE RESTRICT,
    guard_id UUID NOT NULL,
    weapon_id UUID NOT NULL REFERENCES security_erp.weapons(weapon_id) ON DELETE RESTRICT,
    ammunition_rounds INT NOT NULL DEFAULT 0,
    trigger_reason VARCHAR(50) NOT NULL CHECK (trigger_reason IN (
        'SUSPENSION', 'RESIGNATION', 'TERMINATION', 'NOT_DEPLOYABLE', 'ARMS_DOCUMENT_EXPIRY', 'DISCREPANCY'
    )),
    trigger_timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
    status VARCHAR(30) NOT NULL DEFAULT 'RECOVERY_REQUIRED' CHECK (status IN (
        'RECOVERY_REQUIRED', 'IN_PROGRESS', 'CLOSED'
    )),
    supervisor_id UUID REFERENCES security_erp.app_users(user_id) ON DELETE SET NULL,
    last_known_site_id UUID REFERENCES security_erp.client_sites(site_id) ON DELETE SET NULL,
    notes TEXT,
    return_transfer_id UUID REFERENCES security_erp.weapon_transfers(transfer_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_recoveries_company_status ON security_erp.weapon_recoveries(company_id, status);
CREATE INDEX IF NOT EXISTS idx_recoveries_guard ON security_erp.weapon_recoveries(guard_id);

-- ------------------------------------------------------------------------------
-- 14. WEAPON MAINTENANCE AND INSPECTION LOG (PRD 12.13, FR-12.215 to FR-12.221)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.weapon_maintenance_logs (
    maintenance_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    weapon_id UUID NOT NULL REFERENCES security_erp.weapons(weapon_id) ON DELETE CASCADE,
    company_id UUID NOT NULL REFERENCES security_erp.companies(company_id) ON DELETE RESTRICT,
    record_date DATE NOT NULL DEFAULT CURRENT_DATE,
    maintenance_type VARCHAR(30) NOT NULL CHECK (maintenance_type IN ('INSPECTION', 'REPAIR', 'CLEANING', 'TEST', 'OTHER')),
    done_by VARCHAR(150) NOT NULL,
    outcome VARCHAR(50) NOT NULL CHECK (outcome IN ('PASSED', 'REPAIRED', 'FAILED', 'PENDING_PARTS', 'UNSERVICEABLE')),
    next_due_date DATE,
    notes TEXT,
    created_by UUID REFERENCES security_erp.app_users(user_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_weapon_maint_weapon ON security_erp.weapon_maintenance_logs(weapon_id);

-- ------------------------------------------------------------------------------
-- 15. WEAPON ALERTS (PRD 12.15, AC-12.47, AC-12.48, AC-12.59, AC-12.60)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.weapon_alerts (
    alert_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES security_erp.companies(company_id) ON DELETE RESTRICT,
    alert_type VARCHAR(40) NOT NULL CHECK (alert_type IN (
        'LICENCE_EXPIRY', 'OVERDUE_RETURN', 'RECOVERY_REQUIRED', 'DISCREPANCY', 
        'MISSING_WEAPON', 'LOST_OR_STOLEN', 'EXPENDITURE_DISCHARGE', 'EMERGENCY_RATIFICATION', 'MAINTENANCE_DUE'
    )),
    priority VARCHAR(20) NOT NULL CHECK (priority IN ('NORMAL', 'HIGH', 'CRITICAL')),
    related_entity_type VARCHAR(50) NOT NULL,
    related_entity_id UUID NOT NULL,
    recipient_role VARCHAR(30),
    recipient_id UUID REFERENCES security_erp.app_users(user_id) ON DELETE SET NULL,
    site_id UUID REFERENCES security_erp.client_sites(site_id) ON DELETE SET NULL,
    title VARCHAR(200) NOT NULL,
    message TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'ACKNOWLEDGED', 'RESOLVED')),
    escalation_level INT NOT NULL DEFAULT 0,
    acknowledged_at TIMESTAMPTZ,
    acknowledged_by UUID REFERENCES security_erp.app_users(user_id) ON DELETE SET NULL,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_weapon_alerts_company_status ON security_erp.weapon_alerts(company_id, status);
CREATE INDEX IF NOT EXISTS idx_weapon_alerts_priority ON security_erp.weapon_alerts(priority);

-- ------------------------------------------------------------------------------
-- SEED DEFAULTS FUNCTION FOR MODULE 12
-- ------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION security_erp.seed_module12_company_defaults(comp_id UUID)
RETURNS void AS $$
DECLARE
    armoury_loc_id UUID;
    hq_licence_id UUID;
    wpn1_id UUID;
    wpn2_id UUID;
    ammo_lot1_id UUID;
    ammo_lot2_id UUID;
    ammo_lot3_id UUID;
BEGIN
    -- 1. Create Default Central HQ Armoury location
    INSERT INTO security_erp.weapon_locations (company_id, location_type, name, description, status)
    VALUES (comp_id, 'ARMOURY', 'Main Bangalore HQ Armoury', 'Central secure weapons and ammunition armoury repository', 'ACTIVE')
    ON CONFLICT DO NOTHING
    RETURNING location_id INTO armoury_loc_id;

    IF armoury_loc_id IS NULL THEN
        SELECT location_id INTO armoury_loc_id FROM security_erp.weapon_locations
        WHERE company_id = comp_id AND location_type = 'ARMOURY' LIMIT 1;
    END IF;

    -- 2. Create Default Agency Master Arms Licence
    INSERT INTO security_erp.weapon_licences (
        company_id, licence_number, licence_type, issuing_authority, holder_type, holder_name,
        valid_from, valid_until, quantity_limit_enabled, quantity_limit, status
    )
    VALUES (
        comp_id, 'LIC-KA-BLR-2024-0089', 'Form III Security Guard Arms Agency Licence',
        'Office of Police Commissioner, Bangalore City', 'AGENCY', 'Karnataka Security Services Ltd',
        CURRENT_DATE - INTERVAL '1 year', CURRENT_DATE + INTERVAL '2 years', TRUE, 50, 'ACTIVE'
    )
    ON CONFLICT DO NOTHING
    RETURNING licence_id INTO hq_licence_id;

    IF hq_licence_id IS NULL THEN
        SELECT licence_id INTO hq_licence_id FROM security_erp.weapon_licences
        WHERE company_id = comp_id LIMIT 1;
    END IF;

    -- 3. Register Standard Fictitious Weapons
    INSERT INTO security_erp.weapons (
        company_id, asset_id, weapon_type, make, model, calibre, serial_number,
        manufacture_year, acquisition_date, supplier, status, current_location_id, status_reason
    )
    VALUES 
    (
        comp_id, 'WPN-2024-001', 'Revolver', 'Ordnance Factories Board', 'IOF .32 Mk III', 
        '.32 S&W Long', 'OFB-REV-882910', 2021, CURRENT_DATE - INTERVAL '300 days',
        'Government Ordnance Factory Cossipore', 'IN_STORAGE', armoury_loc_id, 'Initial procurement receipt into storage'
    ),
    (
        comp_id, 'WPN-2024-002', 'Pistol', 'Ashani', 'Ashani .32 Semi-Auto', 
        '.32 ACP', 'ASH-PST-991204', 2022, CURRENT_DATE - INTERVAL '250 days',
        'Ishapore Arms Depot', 'IN_STORAGE', armoury_loc_id, 'Initial procurement receipt into storage'
    )
    ON CONFLICT (company_id, serial_number) DO NOTHING;

    -- Link weapons to licence
    SELECT weapon_id INTO wpn1_id FROM security_erp.weapons WHERE company_id = comp_id AND asset_id = 'WPN-2024-001';
    SELECT weapon_id INTO wpn2_id FROM security_erp.weapons WHERE company_id = comp_id AND asset_id = 'WPN-2024-002';

    IF wpn1_id IS NOT NULL AND hq_licence_id IS NOT NULL THEN
        INSERT INTO security_erp.weapon_licence_associations (weapon_id, licence_id, effective_from, is_current)
        VALUES (wpn1_id, hq_licence_id, CURRENT_DATE - INTERVAL '300 days', TRUE)
        ON CONFLICT DO NOTHING;

        -- Create initial custody record in Armoury
        INSERT INTO security_erp.weapon_custody_records (weapon_id, custodian_type, custodian_id, is_current, ammunition_rounds)
        VALUES (wpn1_id, 'LOCATION', armoury_loc_id, TRUE, 0)
        ON CONFLICT DO NOTHING;
    END IF;

    IF wpn2_id IS NOT NULL AND hq_licence_id IS NOT NULL THEN
        INSERT INTO security_erp.weapon_licence_associations (weapon_id, licence_id, effective_from, is_current)
        VALUES (wpn2_id, hq_licence_id, CURRENT_DATE - INTERVAL '250 days', TRUE)
        ON CONFLICT DO NOTHING;

        -- Create initial custody record in Armoury
        INSERT INTO security_erp.weapon_custody_records (weapon_id, custodian_type, custodian_id, is_current, ammunition_rounds)
        VALUES (wpn2_id, 'LOCATION', armoury_loc_id, TRUE, 0)
        ON CONFLICT DO NOTHING;
    END IF;

    -- 4. Register Ammunition Lots & Seed Ledger
    INSERT INTO security_erp.ammunition_lots (company_id, ammunition_type, lot_number, received_date, source_reference, status)
    VALUES 
    (comp_id, '.32 S&W Long', 'LOT-OFB-2024-B1', CURRENT_DATE - INTERVAL '200 days', 'PO-ARM-9901', 'AVAILABLE'),
    (comp_id, '.32 ACP', 'LOT-KGP-2024-A9', CURRENT_DATE - INTERVAL '180 days', 'PO-ARM-9902', 'AVAILABLE'),
    (comp_id, '12 Gauge 00 Buckshot', 'LOT-SHG-2024-C3', CURRENT_DATE - INTERVAL '150 days', 'PO-ARM-9903', 'AVAILABLE')
    ON CONFLICT (company_id, ammunition_type, lot_number) DO NOTHING;

    SELECT lot_id INTO ammo_lot1_id FROM security_erp.ammunition_lots WHERE company_id = comp_id AND lot_number = 'LOT-OFB-2024-B1';
    SELECT lot_id INTO ammo_lot2_id FROM security_erp.ammunition_lots WHERE company_id = comp_id AND lot_number = 'LOT-KGP-2024-A9';
    SELECT lot_id INTO ammo_lot3_id FROM security_erp.ammunition_lots WHERE company_id = comp_id AND lot_number = 'LOT-SHG-2024-C3';

    IF ammo_lot1_id IS NOT NULL AND armoury_loc_id IS NOT NULL THEN
        INSERT INTO security_erp.ammunition_ledger (
            company_id, lot_id, ammunition_type, entry_type, destination_location_id, quantity, reason
        )
        VALUES (comp_id, ammo_lot1_id, '.32 S&W Long', 'RECEIVED', armoury_loc_id, 200, 'Initial procurement stock receipt')
        ON CONFLICT DO NOTHING;
    END IF;

    IF ammo_lot2_id IS NOT NULL AND armoury_loc_id IS NOT NULL THEN
        INSERT INTO security_erp.ammunition_ledger (
            company_id, lot_id, ammunition_type, entry_type, destination_location_id, quantity, reason
        )
        VALUES (comp_id, ammo_lot2_id, '.32 ACP', 'RECEIVED', armoury_loc_id, 150, 'Initial procurement stock receipt')
        ON CONFLICT DO NOTHING;
    END IF;

    IF ammo_lot3_id IS NOT NULL AND armoury_loc_id IS NOT NULL THEN
        INSERT INTO security_erp.ammunition_ledger (
            company_id, lot_id, ammunition_type, entry_type, destination_location_id, quantity, reason
        )
        VALUES (comp_id, ammo_lot3_id, '12 Gauge 00 Buckshot', 'RECEIVED', armoury_loc_id, 100, 'Initial procurement stock receipt')
        ON CONFLICT DO NOTHING;
    END IF;

END;
$$ LANGUAGE plpgsql;
