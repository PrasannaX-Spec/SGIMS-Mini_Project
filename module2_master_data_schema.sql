-- ==============================================================================
-- Module 2: Master Data - Schema Extensions & New Tables
-- Security Agency Management and Monitoring System
-- Target Schema: security_erp
-- ==============================================================================

SET search_path TO security_erp, public;

-- ------------------------------------------------------------------------------
-- 1. Extend Existing Tables
-- ------------------------------------------------------------------------------

-- 1.1 Extend companies table with PRD fields (FR-2.1)
ALTER TABLE security_erp.companies 
    ADD COLUMN IF NOT EXISTS district VARCHAR(100),
    ADD COLUMN IF NOT EXISTS psara_number VARCHAR(100),
    ADD COLUMN IF NOT EXISTS psara_validity DATE,
    ADD COLUMN IF NOT EXISTS logo_url TEXT;

-- 1.2 Extend clients table (FR-2.7, FR-2.8)
ALTER TABLE security_erp.clients 
    ADD COLUMN IF NOT EXISTS notes TEXT;

-- Update clients.status constraint to include 'prospect' and 'suspended'
DO $$
BEGIN
    ALTER TABLE security_erp.clients DROP CONSTRAINT IF EXISTS clients_status_check;
    ALTER TABLE security_erp.clients 
        ADD CONSTRAINT clients_status_check 
        CHECK (status IN ('prospect', 'active', 'on_hold', 'suspended', 'inactive', 'closed'));
EXCEPTION
    WHEN OTHERS THEN NULL;
END $$;

-- 1.3 Extend client_contacts table (FR-2.14, FR-2.15, FR-2.16)
ALTER TABLE security_erp.client_contacts 
    ADD COLUMN IF NOT EXISTS contact_role VARCHAR(30) DEFAULT 'general',
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;

DO $$
BEGIN
    ALTER TABLE security_erp.client_contacts DROP CONSTRAINT IF EXISTS client_contacts_role_check;
    ALTER TABLE security_erp.client_contacts 
        ADD CONSTRAINT client_contacts_role_check 
        CHECK (contact_role IN ('primary', 'billing', 'site_contact', 'escalation', 'general'));
EXCEPTION
    WHEN OTHERS THEN NULL;
END $$;

-- 1.4 Extend client_sites table (FR-2.22, FR-2.26, FR-2.27)
ALTER TABLE security_erp.client_sites 
    ADD COLUMN IF NOT EXISTS district VARCHAR(100),
    ADD COLUMN IF NOT EXISTS guard_instructions TEXT;

-- ------------------------------------------------------------------------------
-- 2. New Master Data Tables
-- ------------------------------------------------------------------------------

-- 2.1 site_geofences: Versioned circular geofence history (FR-2.34 to FR-2.42)
CREATE TABLE IF NOT EXISTS security_erp.site_geofences (
    geofence_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id UUID NOT NULL REFERENCES security_erp.client_sites(site_id) ON DELETE RESTRICT,
    version INT NOT NULL DEFAULT 1,
    latitude NUMERIC(10, 7) NOT NULL,
    longitude NUMERIC(10, 7) NOT NULL,
    radius_meters NUMERIC(8, 2) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    effective_from TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    effective_to TIMESTAMPTZ,
    reason_for_change TEXT,
    created_by_user_id UUID REFERENCES security_erp.app_users(user_id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_site_geofence_version UNIQUE (site_id, version)
);

CREATE INDEX IF NOT EXISTS idx_site_geofences_site_active 
    ON security_erp.site_geofences(site_id, is_active);

-- 2.2 site_supervisor_assignments: Supervisor assignments (FR-2.43 to FR-2.52)
CREATE TABLE IF NOT EXISTS security_erp.site_supervisor_assignments (
    assignment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id UUID NOT NULL REFERENCES security_erp.client_sites(site_id) ON DELETE RESTRICT,
    supervisor_user_id UUID NOT NULL REFERENCES security_erp.app_users(user_id) ON DELETE RESTRICT,
    role_type VARCHAR(20) NOT NULL DEFAULT 'primary' 
        CHECK (role_type IN ('primary', 'backup')),
    effective_from TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    effective_to TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    assignment_reason TEXT,
    assigned_by_user_id UUID REFERENCES security_erp.app_users(user_id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_site_sup_site_active 
    ON security_erp.site_supervisor_assignments(site_id, is_active);
CREATE INDEX IF NOT EXISTS idx_site_sup_user_active 
    ON security_erp.site_supervisor_assignments(supervisor_user_id, is_active);

-- 2.3 shift_templates: Company-level reusable shift templates (FR-2.58 to FR-2.61)
CREATE TABLE IF NOT EXISTS security_erp.shift_templates (
    template_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES security_erp.companies(company_id) ON DELETE RESTRICT,
    template_code VARCHAR(30) NOT NULL,
    template_name VARCHAR(100) NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    duration_minutes INT NOT NULL,
    is_cross_midnight BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_company_shift_template_code UNIQUE (company_id, template_code)
);

-- 2.4 site_shifts: Site-specific shifts (FR-2.62 to FR-2.67)
CREATE TABLE IF NOT EXISTS security_erp.site_shifts (
    shift_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id UUID NOT NULL REFERENCES security_erp.client_sites(site_id) ON DELETE RESTRICT,
    shift_code VARCHAR(30) NOT NULL,
    shift_name VARCHAR(100) NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    duration_minutes INT NOT NULL,
    is_cross_midnight BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_site_shift_code UNIQUE (site_id, shift_code)
);

CREATE INDEX IF NOT EXISTS idx_site_shifts_site_active 
    ON security_erp.site_shifts(site_id, is_active);

-- 2.5 site_manpower_requirements: Effective-dated guard requirements (FR-2.68 to FR-2.77)
CREATE TABLE IF NOT EXISTS security_erp.site_manpower_requirements (
    requirement_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id UUID NOT NULL REFERENCES security_erp.client_sites(site_id) ON DELETE RESTRICT,
    shift_id UUID NOT NULL REFERENCES security_erp.site_shifts(shift_id) ON DELETE RESTRICT,
    post_type_id UUID NOT NULL REFERENCES security_erp.post_types(post_type_id) ON DELETE RESTRICT,
    required_count INT NOT NULL CHECK (required_count > 0),
    effective_from DATE NOT NULL,
    effective_to DATE,
    version INT NOT NULL DEFAULT 1,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by_user_id UUID REFERENCES security_erp.app_users(user_id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_mpr_dates CHECK (effective_to IS NULL OR effective_to >= effective_from)
);

CREATE INDEX IF NOT EXISTS idx_site_mpr_site_dates 
    ON security_erp.site_manpower_requirements(site_id, effective_from, effective_to);

-- 2.6 service_agreements: Agreements with document upload (FR-2.78 to FR-2.85)
CREATE TABLE IF NOT EXISTS security_erp.service_agreements (
    agreement_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES security_erp.clients(client_id) ON DELETE RESTRICT,
    site_id UUID REFERENCES security_erp.client_sites(site_id) ON DELETE RESTRICT,
    agreement_reference VARCHAR(100) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    document_path TEXT,
    document_filename VARCHAR(255),
    document_mime_type VARCHAR(100),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    notes TEXT,
    created_by_user_id UUID REFERENCES security_erp.app_users(user_id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_agreement_dates CHECK (end_date >= start_date)
);

CREATE INDEX IF NOT EXISTS idx_service_agreements_client 
    ON security_erp.service_agreements(client_id, is_active);
CREATE INDEX IF NOT EXISTS idx_service_agreements_dates 
    ON security_erp.service_agreements(end_date, is_active);

-- 2.7 client_billing_rates: Effective-dated rates with precedence (FR-2.86 to FR-2.95)
CREATE TABLE IF NOT EXISTS security_erp.client_billing_rates (
    rate_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES security_erp.clients(client_id) ON DELETE RESTRICT,
    site_id UUID REFERENCES security_erp.client_sites(site_id) ON DELETE RESTRICT,
    post_type_id UUID NOT NULL REFERENCES security_erp.post_types(post_type_id) ON DELETE RESTRICT,
    rate_type VARCHAR(20) NOT NULL DEFAULT 'hourly' 
        CHECK (rate_type IN ('hourly', 'daily', 'monthly')),
    rate_amount NUMERIC(12, 2) NOT NULL CHECK (rate_amount >= 0),
    effective_from DATE NOT NULL,
    effective_to DATE,
    version INT NOT NULL DEFAULT 1,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by_user_id UUID REFERENCES security_erp.app_users(user_id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_billing_dates CHECK (effective_to IS NULL OR effective_to >= effective_from)
);

CREATE INDEX IF NOT EXISTS idx_billing_rates_client_site 
    ON security_erp.client_billing_rates(client_id, site_id, post_type_id, effective_from, effective_to);

-- ------------------------------------------------------------------------------
-- 3. System Settings Seed for Module 2
-- ------------------------------------------------------------------------------
INSERT INTO security_erp.system_settings (company_id, key, value)
SELECT 
    c.company_id,
    s.key,
    s.value
FROM security_erp.companies c
CROSS JOIN (
    VALUES 
        ('geofence_min_radius_m', '20'),
        ('geofence_max_radius_m', '2000'),
        ('max_shift_duration_minutes', '960'),
        ('agreement_expiry_notification_days', '30')
) AS s(key, value)
ON CONFLICT (company_id, key) DO NOTHING;
