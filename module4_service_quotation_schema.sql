-- ==============================================================================
-- Module 4: Service Request and Quotation (Simple) - Schema
-- Security Agency Management and Monitoring System
-- Target Schema: security_erp
-- ==============================================================================

SET search_path TO security_erp, public;

-- ------------------------------------------------------------------------------
-- 1. service_requests
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.service_requests (
    request_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES security_erp.companies(company_id) ON DELETE RESTRICT,
    client_id UUID NOT NULL REFERENCES security_erp.clients(client_id) ON DELETE RESTRICT,
    request_reference VARCHAR(50) NOT NULL UNIQUE,
    submission_reference VARCHAR(100) UNIQUE,
    existing_site_id UUID REFERENCES security_erp.client_sites(site_id) ON DELETE SET NULL,
    new_site_name VARCHAR(180),
    new_site_address TEXT,
    new_site_latitude NUMERIC(10,7),
    new_site_longitude NUMERIC(10,7),
    service_purpose VARCHAR(30) NOT NULL 
        CHECK (service_purpose IN ('office', 'factory', 'residential', 'event', 'other')),
    start_date DATE NOT NULL,
    duration_type VARCHAR(20) NOT NULL 
        CHECK (duration_type IN ('ongoing', 'fixed')),
    end_date DATE,
    site_contact_name VARCHAR(160) NOT NULL,
    site_contact_phone VARCHAR(30) NOT NULL,
    special_requirements TEXT,
    status VARCHAR(30) NOT NULL DEFAULT 'draft' 
        CHECK (status IN (
            'draft', 'submitted', 'under_review', 'awaiting_client', 
            'survey_scheduled', 'quoted', 'countered', 'revised', 
            'accepted', 'rejected_by_client', 'rejected_by_agency', 
            'expired', 'withdrawn', 'converted', 'cancelled'
        )),
    assigned_owner_id UUID REFERENCES security_erp.app_users(user_id) ON DELETE SET NULL,
    created_by_user_id UUID REFERENCES security_erp.app_users(user_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_service_request_dates CHECK (end_date IS NULL OR end_date >= start_date)
);

CREATE INDEX IF NOT EXISTS idx_service_requests_client ON security_erp.service_requests(client_id, status);
CREATE INDEX IF NOT EXISTS idx_service_requests_company ON security_erp.service_requests(company_id, status);

-- ------------------------------------------------------------------------------
-- 2. service_request_lines
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.service_request_lines (
    request_line_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID NOT NULL REFERENCES security_erp.service_requests(request_id) ON DELETE CASCADE,
    post_type_id UUID NOT NULL REFERENCES security_erp.post_types(post_type_id) ON DELETE RESTRICT,
    guard_count INT NOT NULL CHECK (guard_count > 0),
    shift_information VARCHAR(100) NOT NULL,
    hours_per_day NUMERIC(4,1) DEFAULT 8.0,
    working_days TEXT[] NOT NULL,
    armed_required BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_sr_lines_request ON security_erp.service_request_lines(request_id);

-- ------------------------------------------------------------------------------
-- 3. service_request_attachments
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.service_request_attachments (
    attachment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID NOT NULL REFERENCES security_erp.service_requests(request_id) ON DELETE CASCADE,
    file_name VARCHAR(255) NOT NULL,
    file_type VARCHAR(100) NOT NULL,
    storage_key TEXT NOT NULL,
    file_size INT NOT NULL,
    uploaded_by_user_id UUID REFERENCES security_erp.app_users(user_id) ON DELETE SET NULL,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sr_attachments_request ON security_erp.service_request_attachments(request_id);

-- ------------------------------------------------------------------------------
-- 4. service_request_comments
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.service_request_comments (
    comment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID NOT NULL REFERENCES security_erp.service_requests(request_id) ON DELETE CASCADE,
    sender_user_id UUID REFERENCES security_erp.app_users(user_id) ON DELETE SET NULL,
    sender_role VARCHAR(20) NOT NULL,
    message TEXT NOT NULL,
    is_clarification_request BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sr_comments_request ON security_erp.service_request_comments(request_id);

-- ------------------------------------------------------------------------------
-- 5. service_site_surveys
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.service_site_surveys (
    survey_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID NOT NULL REFERENCES security_erp.service_requests(request_id) ON DELETE CASCADE,
    survey_date DATE NOT NULL,
    visited_by VARCHAR(160) NOT NULL,
    assigned_supervisor_id UUID REFERENCES security_erp.app_users(user_id) ON DELETE SET NULL,
    findings TEXT NOT NULL,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sr_surveys_request ON security_erp.service_site_surveys(request_id);

-- ------------------------------------------------------------------------------
-- 6. Extend quotations Table
-- ------------------------------------------------------------------------------
ALTER TABLE security_erp.quotations 
    ADD COLUMN IF NOT EXISTS request_id UUID REFERENCES security_erp.service_requests(request_id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS current_version INT NOT NULL DEFAULT 1;

DO $$
BEGIN
    ALTER TABLE security_erp.quotations DROP CONSTRAINT IF EXISTS quotations_status_check;
    ALTER TABLE security_erp.quotations 
        ADD CONSTRAINT quotations_status_check 
        CHECK (status IN (
            'draft', 'submitted', 'negotiation', 'sent', 'countered', 
            'revised', 'accepted', 'rejected', 'expired', 'converted'
        ));
EXCEPTION
    WHEN OTHERS THEN NULL;
END $$;

-- ------------------------------------------------------------------------------
-- 7. quotation_versions (Immutable sent revisions)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.quotation_versions (
    quotation_version_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quotation_id UUID NOT NULL REFERENCES security_erp.quotations(quotation_id) ON DELETE RESTRICT,
    version_number INT NOT NULL,
    quotation_date DATE NOT NULL DEFAULT CURRENT_DATE,
    validity_date DATE NOT NULL,
    subtotal NUMERIC(14,2) NOT NULL CHECK (subtotal >= 0),
    tax_note VARCHAR(50) NOT NULL DEFAULT 'Applicable taxes extra' 
        CHECK (tax_note IN ('Applicable taxes extra', 'Applicable taxes included')),
    payment_terms TEXT,
    additional_terms TEXT,
    internal_notes TEXT,
    pdf_path TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'draft' 
        CHECK (status IN ('draft', 'sent', 'superseded', 'accepted', 'rejected', 'expired')),
    created_by_user_id UUID REFERENCES security_erp.app_users(user_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sent_at TIMESTAMPTZ,
    CONSTRAINT uq_quote_version UNIQUE (quotation_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_quote_versions_quote ON security_erp.quotation_versions(quotation_id, version_number);

-- ------------------------------------------------------------------------------
-- 8. Extend quotation_lines Table
-- ------------------------------------------------------------------------------
ALTER TABLE security_erp.quotation_lines
    ADD COLUMN IF NOT EXISTS quotation_version_id UUID REFERENCES security_erp.quotation_versions(quotation_version_id) ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS post_type_id UUID REFERENCES security_erp.post_types(post_type_id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS billing_unit VARCHAR(30) NOT NULL DEFAULT 'per_guard_per_month';

ALTER TABLE security_erp.quotation_lines ALTER COLUMN post_type DROP NOT NULL;

DO $$
BEGIN
    ALTER TABLE security_erp.quotation_lines DROP CONSTRAINT IF EXISTS chk_quotation_lines_billing_unit;
    ALTER TABLE security_erp.quotation_lines 
        ADD CONSTRAINT chk_quotation_lines_billing_unit 
        CHECK (billing_unit IN ('per_guard_per_month', 'per_guard_per_day', 'per_guard_per_shift'));
EXCEPTION
    WHEN OTHERS THEN NULL;
END $$;

-- ------------------------------------------------------------------------------
-- 9. quotation_acceptances (Click-to-accept metadata)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.quotation_acceptances (
    acceptance_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quotation_version_id UUID NOT NULL REFERENCES security_erp.quotation_versions(quotation_version_id) ON DELETE RESTRICT,
    client_user_id UUID NOT NULL REFERENCES security_erp.app_users(user_id) ON DELETE RESTRICT,
    accepted_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ip_address VARCHAR(50),
    device_information TEXT,
    agreed_text TEXT NOT NULL,
    confirmation_value BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_quote_acceptances_version ON security_erp.quotation_acceptances(quotation_version_id);

-- ------------------------------------------------------------------------------
-- 10. quotation_counters (Negotiation proposals)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.quotation_counters (
    counter_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quotation_version_id UUID NOT NULL REFERENCES security_erp.quotation_versions(quotation_version_id) ON DELETE RESTRICT,
    client_user_id UUID NOT NULL REFERENCES security_erp.app_users(user_id) ON DELETE RESTRICT,
    comment TEXT NOT NULL,
    proposed_guard_count INT,
    proposed_rate NUMERIC(12,2),
    proposed_start_date DATE,
    negotiation_round INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_quote_counters_version ON security_erp.quotation_counters(quotation_version_id);

-- ------------------------------------------------------------------------------
-- 11. quotation_conversions (Module 2 Setup Generation)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.quotation_conversions (
    conversion_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quotation_version_id UUID NOT NULL REFERENCES security_erp.quotation_versions(quotation_version_id) ON DELETE RESTRICT,
    conversion_reference VARCHAR(60) NOT NULL UNIQUE,
    conversion_status VARCHAR(20) NOT NULL DEFAULT 'pending' 
        CHECK (conversion_status IN ('pending', 'completed', 'failed')),
    module2_site_id UUID REFERENCES security_erp.client_sites(site_id) ON DELETE SET NULL,
    module2_agreement_id UUID REFERENCES security_erp.service_agreements(agreement_id) ON DELETE SET NULL,
    generated_records JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,
    error_details TEXT
);

CREATE INDEX IF NOT EXISTS idx_quote_conversions_version ON security_erp.quotation_conversions(quotation_version_id);

-- ------------------------------------------------------------------------------
-- 12. Seed System Settings for Module 4
-- ------------------------------------------------------------------------------
INSERT INTO security_erp.system_settings (company_id, key, value)
SELECT 
    c.company_id,
    s.key,
    s.value
FROM security_erp.companies c
CROSS JOIN (
    VALUES 
        ('service_request_code_prefix', 'SR'),
        ('quotation_code_prefix', 'QT'),
        ('max_negotiation_rounds', '3'),
        ('quotation_validity_days', '15'),
        ('max_request_attachments', '5'),
        ('max_attachment_size_mb', '10')
) AS s(key, value)
ON CONFLICT (company_id, key) DO NOTHING;

