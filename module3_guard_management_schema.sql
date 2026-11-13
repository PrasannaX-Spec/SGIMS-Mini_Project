-- ==============================================================================
-- Module 3: Guard Management - Schema Extensions & New Tables
-- Security Agency Management and Monitoring System
-- Target Schema: security_erp
-- ==============================================================================

SET search_path TO security_erp, public;

-- ------------------------------------------------------------------------------
-- 1. Extend Existing employees Table
-- ------------------------------------------------------------------------------
ALTER TABLE security_erp.employees 
    ADD COLUMN IF NOT EXISTS father_guardian_name VARCHAR(160),
    ADD COLUMN IF NOT EXISTS blood_group VARCHAR(10),
    ADD COLUMN IF NOT EXISTS marital_status VARCHAR(20),
    ADD COLUMN IF NOT EXISTS height_cm NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS weight_kg NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS languages_known TEXT[],
    ADD COLUMN IF NOT EXISTS qualification VARCHAR(100),
    ADD COLUMN IF NOT EXISTS experience_summary TEXT,
    ADD COLUMN IF NOT EXISTS is_ex_serviceman BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS reference_photo_url TEXT,
    ADD COLUMN IF NOT EXISTS lifecycle_status VARCHAR(30) NOT NULL DEFAULT 'applicant',
    ADD COLUMN IF NOT EXISTS pan_number VARCHAR(10),
    ADD COLUMN IF NOT EXISTS uan_number VARCHAR(20),
    ADD COLUMN IF NOT EXISTS esi_number VARCHAR(20),
    ADD COLUMN IF NOT EXISTS aadhaar_masked VARCHAR(20),
    ADD COLUMN IF NOT EXISTS aadhaar_hash VARCHAR(64),
    ADD COLUMN IF NOT EXISTS home_district VARCHAR(100),
    ADD COLUMN IF NOT EXISTS preferred_work_area VARCHAR(100),
    ADD COLUMN IF NOT EXISTS post_type_id UUID REFERENCES security_erp.post_types(post_type_id),
    ADD COLUMN IF NOT EXISTS reporting_supervisor_id UUID REFERENCES security_erp.app_users(user_id);

DO $$
BEGIN
    ALTER TABLE security_erp.employees DROP CONSTRAINT IF EXISTS chk_employees_lifecycle_status;
    ALTER TABLE security_erp.employees 
        ADD CONSTRAINT chk_employees_lifecycle_status 
        CHECK (lifecycle_status IN (
            'applicant', 'under_verification', 'approved', 'active', 
            'on_leave', 'suspended', 'resigned', 'terminated'
        ));
EXCEPTION
    WHEN OTHERS THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_employees_phone ON security_erp.employees(phone);
CREATE INDEX IF NOT EXISTS idx_employees_lifecycle ON security_erp.employees(company_id, lifecycle_status);
CREATE INDEX IF NOT EXISTS idx_employees_aadhaar_hash ON security_erp.employees(aadhaar_hash) WHERE aadhaar_hash IS NOT NULL;

-- ------------------------------------------------------------------------------
-- 2. Extend Existing employee_documents Table
-- ------------------------------------------------------------------------------
ALTER TABLE security_erp.employee_documents
    ADD COLUMN IF NOT EXISTS document_number VARCHAR(100),
    ADD COLUMN IF NOT EXISTS masked_number VARCHAR(30),
    ADD COLUMN IF NOT EXISTS number_hash VARCHAR(64),
    ADD COLUMN IF NOT EXISTS version INT NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS rejection_reason TEXT,
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;

CREATE INDEX IF NOT EXISTS idx_emp_docs_active ON security_erp.employee_documents(employee_id, is_active);

-- Allow standalone employee training without pre-existing training session
ALTER TABLE security_erp.employee_training 
    ALTER COLUMN session_id DROP NOT NULL;

-- ------------------------------------------------------------------------------
-- 3. New Table: guard_status_history
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.guard_status_history (
    history_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID NOT NULL REFERENCES security_erp.employees(employee_id) ON DELETE RESTRICT,
    previous_status VARCHAR(30),
    new_status VARCHAR(30) NOT NULL,
    reason TEXT NOT NULL,
    changed_by_user_id UUID REFERENCES security_erp.app_users(user_id) ON DELETE SET NULL,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_guard_status_history_emp 
    ON security_erp.guard_status_history(employee_id, changed_at);

-- ------------------------------------------------------------------------------
-- 4. New Table: guard_disciplinary_records
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.guard_disciplinary_records (
    record_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID NOT NULL REFERENCES security_erp.employees(employee_id) ON DELETE RESTRICT,
    category VARCHAR(60) NOT NULL,
    incident_date DATE NOT NULL,
    remarks TEXT NOT NULL,
    is_visible_to_guard BOOLEAN NOT NULL DEFAULT FALSE,
    created_by_user_id UUID REFERENCES security_erp.app_users(user_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_guard_disciplinary_emp 
    ON security_erp.guard_disciplinary_records(employee_id, incident_date);

-- ------------------------------------------------------------------------------
-- 5. New Table: guard_id_cards
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.guard_id_cards (
    card_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID NOT NULL REFERENCES security_erp.employees(employee_id) ON DELETE RESTRICT,
    employee_code VARCHAR(50) NOT NULL,
    issued_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    valid_until DATE,
    reissue_count INT NOT NULL DEFAULT 0,
    qr_payload TEXT NOT NULL,
    pdf_path TEXT
);

CREATE INDEX IF NOT EXISTS idx_guard_id_cards_emp 
    ON security_erp.guard_id_cards(employee_id);

-- ------------------------------------------------------------------------------
-- 6. New Table: profile_change_requests
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.profile_change_requests (
    request_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID NOT NULL REFERENCES security_erp.employees(employee_id) ON DELETE RESTRICT,
    field_name VARCHAR(50) NOT NULL,
    current_value TEXT,
    proposed_value TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' 
        CHECK (status IN ('pending', 'approved', 'rejected')),
    reviewed_by_user_id UUID REFERENCES security_erp.app_users(user_id) ON DELETE SET NULL,
    review_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_profile_change_requests_status 
    ON security_erp.profile_change_requests(status);

-- ------------------------------------------------------------------------------
-- 7. System Settings Seed for Module 3
-- ------------------------------------------------------------------------------
INSERT INTO security_erp.system_settings (company_id, key, value)
SELECT 
    c.company_id,
    s.key,
    s.value
FROM security_erp.companies c
CROSS JOIN (
    VALUES 
        ('guard_min_age_years', '18'),
        ('employee_code_prefix', 'SEC-GRD'),
        ('doc_expiry_alert_days', '30'),
        ('mandatory_doc_types', 'identity_proof,address_proof,police_verification,medical_fitness'),
        ('mandatory_training_types', 'induction,fire_safety')
) AS s(key, value)
ON CONFLICT (company_id, key) DO NOTHING;
