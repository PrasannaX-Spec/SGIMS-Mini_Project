-- ============================================================================
-- Module 11: Billing and Invoices (Simple) Relational Schema
-- PostgreSQL 18 Compatible | Exact Decimal Handling | Immutability & Audit Traceability
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS security_erp;

-- ----------------------------------------------------------------------------
-- 1. Company Invoice Settings (PRD 12.1, FR-11.1 to FR-11.14)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.invoice_settings (
    settings_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES security_erp.companies(company_id) ON DELETE CASCADE,
    invoice_prefix VARCHAR(30) NOT NULL DEFAULT 'INV',
    number_format VARCHAR(100) NOT NULL DEFAULT '{PREFIX}/{FY}/{SEQ:04d}',
    financial_year_start_month INT NOT NULL DEFAULT 4,
    financial_year_start_day INT NOT NULL DEFAULT 1,
    next_sequence INT NOT NULL DEFAULT 1,
    default_tax_label VARCHAR(50) DEFAULT 'GST',
    default_tax_percentage NUMERIC(5,2) DEFAULT 18.00,
    rounding_method VARCHAR(30) DEFAULT 'ROUND_HALF_UP', -- ROUND_HALF_UP, ROUND_HALF_EVEN, CEILING, FLOOR
    rounding_level VARCHAR(20) DEFAULT 'TOTAL', -- TOTAL, LINE
    default_payment_terms_days INT NOT NULL DEFAULT 30,
    bank_name VARCHAR(150),
    account_number VARCHAR(50),
    ifsc_code VARCHAR(20),
    branch_name VARCHAR(150),
    default_notes TEXT DEFAULT 'Payment is due within payment terms. Please cite the invoice number upon bank transfer.',
    second_admin_approval_required BOOLEAN DEFAULT FALSE,
    second_admin_approval_threshold NUMERIC(12,2) DEFAULT 50000.00,
    negative_line_approval_threshold NUMERIC(12,2) DEFAULT 5000.00,
    effective_from DATE NOT NULL DEFAULT CURRENT_DATE,
    effective_to DATE,
    created_by UUID,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_tax_percentage CHECK (default_tax_percentage >= 0.00 AND default_tax_percentage <= 100.00),
    CONSTRAINT chk_fy_month CHECK (financial_year_start_month >= 1 AND financial_year_start_month <= 12),
    CONSTRAINT chk_fy_day CHECK (financial_year_start_day >= 1 AND financial_year_start_day <= 31),
    CONSTRAINT chk_rounding_method CHECK (rounding_method IN ('ROUND_HALF_UP', 'ROUND_HALF_EVEN', 'CEILING', 'FLOOR')),
    CONSTRAINT chk_rounding_level CHECK (rounding_level IN ('TOTAL', 'LINE'))
);

CREATE INDEX IF NOT EXISTS idx_inv_settings_company ON security_erp.invoice_settings(company_id);

-- ----------------------------------------------------------------------------
-- 2. Client Billing Settings (PRD 12.2, FR-11.15 to FR-11.30)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.client_billing_settings (
    settings_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES security_erp.companies(company_id) ON DELETE CASCADE,
    client_id UUID NOT NULL REFERENCES security_erp.clients(client_id) ON DELETE CASCADE,
    site_id UUID REFERENCES security_erp.client_sites(site_id) ON DELETE CASCADE,
    billing_basis VARCHAR(40) NOT NULL DEFAULT 'ATTENDANCE_BASED', -- FIXED_MONTHLY, FIXED_MINUS_DEDUCTIONS, ATTENDANCE_BASED
    billing_unit VARCHAR(30) NOT NULL DEFAULT 'PER_DAY', -- PER_MONTH, PER_DAY, PER_SHIFT
    proration_method VARCHAR(30) NOT NULL DEFAULT 'CALENDAR_DAY', -- CALENDAR_DAY, DUTY_DAY, FULL_MONTH
    invoice_grouping VARCHAR(30) NOT NULL DEFAULT 'ONE_PER_CLIENT', -- ONE_PER_CLIENT, ONE_PER_SITE
    payment_terms_days INT NOT NULL DEFAULT 30,
    po_wo_number VARCHAR(100),
    po_wo_validity_start DATE,
    po_wo_validity_end DATE,
    billing_contact_id UUID REFERENCES security_erp.client_contacts(contact_id) ON DELETE SET NULL,
    tax_override_enabled BOOLEAN DEFAULT FALSE,
    tax_label VARCHAR(50),
    tax_percentage NUMERIC(5,2),
    tax_inclusive BOOLEAN DEFAULT FALSE,
    overtime_billable BOOLEAN DEFAULT FALSE,
    extra_duty_billable BOOLEAN DEFAULT FALSE,
    manual_attendance_confirmation BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    effective_from DATE NOT NULL DEFAULT CURRENT_DATE,
    effective_to DATE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_billing_basis CHECK (billing_basis IN ('FIXED_MONTHLY', 'FIXED_MINUS_DEDUCTIONS', 'ATTENDANCE_BASED')),
    CONSTRAINT chk_billing_unit CHECK (billing_unit IN ('PER_MONTH', 'PER_DAY', 'PER_SHIFT')),
    CONSTRAINT chk_proration_method CHECK (proration_method IN ('CALENDAR_DAY', 'DUTY_DAY', 'FULL_MONTH')),
    CONSTRAINT chk_invoice_grouping CHECK (invoice_grouping IN ('ONE_PER_CLIENT', 'ONE_PER_SITE'))
);

CREATE INDEX IF NOT EXISTS idx_client_billing_settings_client ON security_erp.client_billing_settings(client_id);
CREATE INDEX IF NOT EXISTS idx_client_billing_settings_site ON security_erp.client_billing_settings(site_id);

-- ----------------------------------------------------------------------------
-- 3. Invoice Number Sequences (PRD 12.9, FR-11.3, AC-11.34)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.invoice_number_sequences (
    sequence_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES security_erp.companies(company_id) ON DELETE CASCADE,
    series_code VARCHAR(50) NOT NULL DEFAULT 'DEFAULT',
    financial_year VARCHAR(20) NOT NULL, -- e.g. '2026-27'
    last_number INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_inv_num_seq UNIQUE (company_id, series_code, financial_year)
);

-- ----------------------------------------------------------------------------
-- 4. Enhance / Create Client Invoices Table (PRD 12.3, 10.1, 10.2)
-- ----------------------------------------------------------------------------
-- Ensure client_invoices table exists or alter columns
CREATE TABLE IF NOT EXISTS security_erp.client_invoices (
    invoice_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES security_erp.companies(company_id) ON DELETE CASCADE,
    client_id UUID NOT NULL REFERENCES security_erp.clients(client_id) ON DELETE CASCADE,
    contract_id UUID,
    site_id UUID REFERENCES security_erp.client_sites(site_id) ON DELETE SET NULL,
    invoice_no VARCHAR(100),
    invoice_date DATE,
    due_date DATE,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    invoice_type VARCHAR(50) NOT NULL DEFAULT 'REGULAR',
    subtotal NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    discount_amount NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    tax_amount NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    total_amount NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    outstanding_amount NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    status VARCHAR(50) NOT NULL DEFAULT 'DRAFT',
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Add Module 11 specific columns safely
DO $$
BEGIN
    ALTER TABLE security_erp.client_invoices ALTER COLUMN invoice_no DROP NOT NULL;
EXCEPTION
    WHEN OTHERS THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE security_erp.client_invoices ALTER COLUMN invoice_date DROP NOT NULL;
EXCEPTION
    WHEN OTHERS THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE security_erp.client_invoices DROP CONSTRAINT IF EXISTS client_invoices_status_check;
    ALTER TABLE security_erp.client_invoices ADD CONSTRAINT client_invoices_status_check
        CHECK (status IN ('draft','issued','part_paid','paid','overdue','cancelled',
                          'DRAFT','PENDING_APPROVAL','SENT','PARTIALLY_PAID','PAID','CANCELLED'));
EXCEPTION
    WHEN OTHERS THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE security_erp.client_invoices ADD COLUMN IF NOT EXISTS draft_reference VARCHAR(100) UNIQUE;
    ALTER TABLE security_erp.client_invoices ADD COLUMN IF NOT EXISTS taxable_amount NUMERIC(12,2) DEFAULT 0.00;
    ALTER TABLE security_erp.client_invoices ADD COLUMN IF NOT EXISTS paid_amount NUMERIC(12,2) DEFAULT 0.00;
    ALTER TABLE security_erp.client_invoices ADD COLUMN IF NOT EXISTS deduction_amount NUMERIC(12,2) DEFAULT 0.00;
    ALTER TABLE security_erp.client_invoices ADD COLUMN IF NOT EXISTS pdf_file_reference TEXT;
    ALTER TABLE security_erp.client_invoices ADD COLUMN IF NOT EXISTS pdf_hash VARCHAR(128);
    ALTER TABLE security_erp.client_invoices ADD COLUMN IF NOT EXISTS source_snapshot JSONB DEFAULT '{}'::jsonb;
    ALTER TABLE security_erp.client_invoices ADD COLUMN IF NOT EXISTS source_changed BOOLEAN DEFAULT FALSE;
    ALTER TABLE security_erp.client_invoices ADD COLUMN IF NOT EXISTS source_change_details JSONB DEFAULT '{}'::jsonb;
    ALTER TABLE security_erp.client_invoices ADD COLUMN IF NOT EXISTS cancelled_reason TEXT;
    ALTER TABLE security_erp.client_invoices ADD COLUMN IF NOT EXISTS client_visible_cancellation_reason TEXT;
    ALTER TABLE security_erp.client_invoices ADD COLUMN IF NOT EXISTS replacement_invoice_id UUID REFERENCES security_erp.client_invoices(invoice_id);
    ALTER TABLE security_erp.client_invoices ADD COLUMN IF NOT EXISTS original_invoice_id UUID REFERENCES security_erp.client_invoices(invoice_id);
    ALTER TABLE security_erp.client_invoices ADD COLUMN IF NOT EXISTS is_unlocked_period_override BOOLEAN DEFAULT FALSE;
    ALTER TABLE security_erp.client_invoices ADD COLUMN IF NOT EXISTS unlocked_period_reason TEXT;
    ALTER TABLE security_erp.client_invoices ADD COLUMN IF NOT EXISTS pending_attendance_count INT DEFAULT 0;
    ALTER TABLE security_erp.client_invoices ADD COLUMN IF NOT EXISTS created_by UUID;
    ALTER TABLE security_erp.client_invoices ADD COLUMN IF NOT EXISTS approved_by UUID;
    ALTER TABLE security_erp.client_invoices ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ;
    ALTER TABLE security_erp.client_invoices ADD COLUMN IF NOT EXISTS issued_by UUID;
    ALTER TABLE security_erp.client_invoices ADD COLUMN IF NOT EXISTS issued_at TIMESTAMPTZ;
    ALTER TABLE security_erp.client_invoices ADD COLUMN IF NOT EXISTS cancelled_by UUID;
    ALTER TABLE security_erp.client_invoices ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMPTZ;
    ALTER TABLE security_erp.client_invoices ADD COLUMN IF NOT EXISTS overdue_flag BOOLEAN DEFAULT FALSE;
    ALTER TABLE security_erp.client_invoices ADD COLUMN IF NOT EXISTS under_query_flag BOOLEAN DEFAULT FALSE;
    ALTER TABLE security_erp.client_invoices ADD COLUMN IF NOT EXISTS internal_notes TEXT;
    ALTER TABLE security_erp.client_invoices ADD COLUMN IF NOT EXISTS annexure_file_reference TEXT;
    ALTER TABLE security_erp.client_invoices ADD COLUMN IF NOT EXISTS annexure_hash VARCHAR(128);
END $$;

CREATE INDEX IF NOT EXISTS idx_client_invoices_client ON security_erp.client_invoices(client_id);
CREATE INDEX IF NOT EXISTS idx_client_invoices_status ON security_erp.client_invoices(status);
CREATE INDEX IF NOT EXISTS idx_client_invoices_period ON security_erp.client_invoices(period_start, period_end);
CREATE INDEX IF NOT EXISTS idx_client_invoices_no ON security_erp.client_invoices(invoice_no);

-- ----------------------------------------------------------------------------
-- 5. Enhance / Create Invoice Lines Table (PRD 12.4)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.invoice_lines (
    invoice_line_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id UUID NOT NULL REFERENCES security_erp.client_invoices(invoice_id) ON DELETE CASCADE,
    description VARCHAR(255) NOT NULL,
    site_id UUID REFERENCES security_erp.client_sites(site_id) ON DELETE SET NULL,
    quantity NUMERIC(12,2) NOT NULL DEFAULT 1.00,
    unit_rate NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    tax_rate NUMERIC(5,2) NOT NULL DEFAULT 0.00,
    line_amount NUMERIC(12,2) NOT NULL DEFAULT 0.00
);

DO $$
BEGIN
    ALTER TABLE security_erp.invoice_lines ADD COLUMN IF NOT EXISTS post_type_id UUID REFERENCES security_erp.post_types(post_type_id) ON DELETE SET NULL;
    ALTER TABLE security_erp.invoice_lines ADD COLUMN IF NOT EXISTS shift_id UUID REFERENCES security_erp.site_shifts(shift_id) ON DELETE SET NULL;
    ALTER TABLE security_erp.invoice_lines ADD COLUMN IF NOT EXISTS source_type VARCHAR(30) DEFAULT 'ATTENDANCE';
    ALTER TABLE security_erp.invoice_lines ADD COLUMN IF NOT EXISTS source_reference TEXT;
    ALTER TABLE security_erp.invoice_lines ADD COLUMN IF NOT EXISTS unit VARCHAR(30) DEFAULT 'PER_DAY';
    ALTER TABLE security_erp.invoice_lines ADD COLUMN IF NOT EXISTS effective_rate_start DATE;
    ALTER TABLE security_erp.invoice_lines ADD COLUMN IF NOT EXISTS effective_rate_end DATE;
    ALTER TABLE security_erp.invoice_lines ADD COLUMN IF NOT EXISTS requirement_version INT;
    ALTER TABLE security_erp.invoice_lines ADD COLUMN IF NOT EXISTS manual_reason TEXT;
    ALTER TABLE security_erp.invoice_lines ADD COLUMN IF NOT EXISTS client_visible_description TEXT;
    ALTER TABLE security_erp.invoice_lines ADD COLUMN IF NOT EXISTS is_negative BOOLEAN DEFAULT FALSE;
    ALTER TABLE security_erp.invoice_lines ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP;
    ALTER TABLE security_erp.invoice_lines DROP CONSTRAINT IF EXISTS invoice_lines_line_amount_check;
END $$;

CREATE INDEX IF NOT EXISTS idx_invoice_lines_invoice ON security_erp.invoice_lines(invoice_id);

-- ----------------------------------------------------------------------------
-- 6. Enhance / Create Client Payments Table (PRD 12.5)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.client_payments (
    client_payment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES security_erp.clients(client_id) ON DELETE CASCADE,
    payment_date DATE NOT NULL,
    amount NUMERIC(12,2) NOT NULL,
    payment_method VARCHAR(50) NOT NULL,
    reference_no VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

DO $$
BEGIN
    ALTER TABLE security_erp.client_payments ADD COLUMN IF NOT EXISTS company_id UUID REFERENCES security_erp.companies(company_id) ON DELETE CASCADE;
    ALTER TABLE security_erp.client_payments ADD COLUMN IF NOT EXISTS invoice_id UUID REFERENCES security_erp.client_invoices(invoice_id) ON DELETE CASCADE;
    ALTER TABLE security_erp.client_payments ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'ACTIVE';
    ALTER TABLE security_erp.client_payments ADD COLUMN IF NOT EXISTS reversal_reason TEXT;
    ALTER TABLE security_erp.client_payments ADD COLUMN IF NOT EXISTS reversed_at TIMESTAMPTZ;
    ALTER TABLE security_erp.client_payments ADD COLUMN IF NOT EXISTS reversed_by UUID;
    ALTER TABLE security_erp.client_payments ADD COLUMN IF NOT EXISTS unallocated_amount NUMERIC(12,2) DEFAULT 0.00;
    ALTER TABLE security_erp.client_payments ADD COLUMN IF NOT EXISTS created_by UUID;
    ALTER TABLE security_erp.client_payments DROP CONSTRAINT IF EXISTS client_payments_payment_method_check;
    ALTER TABLE security_erp.client_payments ADD CONSTRAINT client_payments_payment_method_check
        CHECK (payment_method IN ('bank_transfer','cash','cheque','upi','other',
                                  'NEFT','RTGS','IMPS','CHEQUE','CASH','UPI','OTHER','BANK_TRANSFER'));
END $$;

CREATE INDEX IF NOT EXISTS idx_client_payments_invoice ON security_erp.client_payments(invoice_id);
CREATE INDEX IF NOT EXISTS idx_client_payments_client ON security_erp.client_payments(client_id);

-- ----------------------------------------------------------------------------
-- 7. Payment Deductions Table (PRD 12.6, FR-11.133, FR-11.134)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.client_payment_deductions (
    deduction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payment_id UUID NOT NULL REFERENCES security_erp.client_payments(client_payment_id) ON DELETE CASCADE,
    invoice_id UUID NOT NULL REFERENCES security_erp.client_invoices(invoice_id) ON DELETE CASCADE,
    deduction_type VARCHAR(20) NOT NULL, -- TDS, OTHER
    amount NUMERIC(12,2) NOT NULL,
    reason TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_deduction_type CHECK (deduction_type IN ('TDS', 'OTHER'))
);

CREATE INDEX IF NOT EXISTS idx_payment_deductions_payment ON security_erp.client_payment_deductions(payment_id);
CREATE INDEX IF NOT EXISTS idx_payment_deductions_invoice ON security_erp.client_payment_deductions(invoice_id);

-- ----------------------------------------------------------------------------
-- 8. Invoice Attendance Annexures (PRD 12.8, 6.13)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.invoice_attendance_annexures (
    annexure_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id UUID NOT NULL REFERENCES security_erp.client_invoices(invoice_id) ON DELETE CASCADE,
    site_id UUID NOT NULL REFERENCES security_erp.client_sites(site_id) ON DELETE CASCADE,
    duty_date DATE NOT NULL,
    shift_id UUID REFERENCES security_erp.site_shifts(shift_id) ON DELETE SET NULL,
    shift_name VARCHAR(100),
    post_slot_id UUID,
    post_type_id UUID,
    post_type_name VARCHAR(100),
    guard_id UUID,
    guard_name VARCHAR(150),
    coverage_status VARCHAR(30) NOT NULL, -- COVERED, UNCOVERED, EXTRA_DUTY, REPLACEMENT
    is_manual BOOLEAN DEFAULT FALSE,
    regular_minutes INT DEFAULT 0,
    overtime_minutes INT DEFAULT 0,
    is_billed BOOLEAN DEFAULT TRUE,
    deduction_applied BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_inv_annexures_invoice ON security_erp.invoice_attendance_annexures(invoice_id);
CREATE INDEX IF NOT EXISTS idx_inv_annexures_site_date ON security_erp.invoice_attendance_annexures(site_id, duty_date);

-- ----------------------------------------------------------------------------
-- 9. Invoice Query Links (PRD 12.8, 6.14, Module 8 ticket linking)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.invoice_query_links (
    query_link_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id UUID NOT NULL REFERENCES security_erp.client_invoices(invoice_id) ON DELETE CASCADE,
    ticket_id UUID NOT NULL,
    client_id UUID NOT NULL REFERENCES security_erp.clients(client_id) ON DELETE CASCADE,
    query_category VARCHAR(50),
    status VARCHAR(30) DEFAULT 'OPEN', -- OPEN, IN_PROGRESS, RESOLVED, CLOSED
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_inv_query_links_invoice ON security_erp.invoice_query_links(invoice_id);
CREATE INDEX IF NOT EXISTS idx_inv_query_links_ticket ON security_erp.invoice_query_links(ticket_id);

-- ----------------------------------------------------------------------------
-- 10. Invoice Reminders (PRD 6.12, 11.10)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.invoice_reminders (
    reminder_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id UUID NOT NULL REFERENCES security_erp.client_invoices(invoice_id) ON DELETE CASCADE,
    client_id UUID NOT NULL REFERENCES security_erp.clients(client_id) ON DELETE CASCADE,
    reminder_type VARCHAR(30) NOT NULL, -- BEFORE_DUE, DUE_DATE, OVERDUE
    sent_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    sent_to_contact_id UUID,
    status VARCHAR(30) DEFAULT 'SENT', -- SENT, PAUSED_UNDER_QUERY, CANCELLED_PAID
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_inv_reminders_invoice ON security_erp.invoice_reminders(invoice_id);

-- ----------------------------------------------------------------------------
-- 11. Seed Defaults Helper Function
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION security_erp.seed_module11_company_defaults(p_company_id UUID)
RETURNS VOID AS $$
BEGIN
    -- Seed default company invoice settings if not existing
    IF NOT EXISTS (SELECT 1 FROM security_erp.invoice_settings WHERE company_id = p_company_id) THEN
        INSERT INTO security_erp.invoice_settings (
            company_id,
            invoice_prefix,
            number_format,
            financial_year_start_month,
            financial_year_start_day,
            next_sequence,
            default_tax_label,
            default_tax_percentage,
            rounding_method,
            rounding_level,
            default_payment_terms_days,
            bank_name,
            account_number,
            ifsc_code,
            branch_name,
            default_notes
        ) VALUES (
            p_company_id,
            'INV',
            '{PREFIX}/{FY}/{SEQ:04d}',
            4,
            1,
            1,
            'GST',
            18.00,
            'ROUND_HALF_UP',
            'TOTAL',
            30,
            'State Bank of India',
            '987654321012',
            'SBIN0001234',
            'Bangalore Main Branch',
            'Thank you for your business. Please quote the invoice number when making RTGS/NEFT payment.'
        );
    END IF;

    -- Seed current financial year sequence (e.g. 2026-27)
    IF NOT EXISTS (
        SELECT 1 FROM security_erp.invoice_number_sequences 
        WHERE company_id = p_company_id AND series_code = 'DEFAULT' AND financial_year = '2026-27'
    ) THEN
        INSERT INTO security_erp.invoice_number_sequences (
            company_id,
            series_code,
            financial_year,
            last_number
        ) VALUES (
            p_company_id,
            'DEFAULT',
            '2026-27',
            0
        );
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Seed for existing companies in DB
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN SELECT company_id FROM security_erp.companies LOOP
        PERFORM security_erp.seed_module11_company_defaults(r.company_id);
    END LOOP;
END $$;
