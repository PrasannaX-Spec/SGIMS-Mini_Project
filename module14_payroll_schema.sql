-- ==============================================================================
-- Module 14: Payroll - Schema Definitions
-- Security Agency Management and Monitoring System (SGIMS)
-- Target Schema: security_erp
-- ==============================================================================

SET search_path TO security_erp, public;

-- Clean up any preliminary baseline stubs if present
DROP TABLE IF EXISTS security_erp.payroll_payments CASCADE;
DROP TABLE IF EXISTS security_erp.payroll_components CASCADE;
DROP TABLE IF EXISTS security_erp.employee_payroll CASCADE;
DROP TABLE IF EXISTS security_erp.employee_advances CASCADE;
DROP TABLE IF EXISTS security_erp.payroll_runs CASCADE;

-- ------------------------------------------------------------------------------
-- 1. Salary Components Catalog
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.payroll_salary_components (
    component_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES security_erp.companies(company_id) ON DELETE RESTRICT,
    component_code VARCHAR(50) NOT NULL,
    component_name VARCHAR(150) NOT NULL,
    component_type VARCHAR(50) NOT NULL CHECK (component_type IN ('EARNING', 'RECURRING_DEDUCTION', 'EMPLOYER_CONTRIBUTION')),
    wage_base_flags JSONB NOT NULL DEFAULT '{"pf": false, "esi": false, "pt": false, "lwf": false}'::jsonb,
    proration_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    classification VARCHAR(100),
    display_order INT NOT NULL DEFAULT 1,
    status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'INACTIVE')),
    created_by UUID REFERENCES security_erp.app_users(user_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_payroll_component UNIQUE (company_id, component_code)
);

CREATE INDEX IF NOT EXISTS idx_payroll_components_co ON security_erp.payroll_salary_components(company_id, status);

-- ------------------------------------------------------------------------------
-- 2. Salary Structures
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.payroll_salary_structures (
    structure_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES security_erp.companies(company_id) ON DELETE RESTRICT,
    name VARCHAR(150) NOT NULL,
    version INT NOT NULL DEFAULT 1,
    effective_from DATE NOT NULL,
    effective_to DATE,
    status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('DRAFT', 'ACTIVE', 'SUPERSEDED')),
    change_reason TEXT NOT NULL,
    created_by UUID REFERENCES security_erp.app_users(user_id),
    approved_by UUID REFERENCES security_erp.app_users(user_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_payroll_struct_co ON security_erp.payroll_salary_structures(company_id, status);

-- ------------------------------------------------------------------------------
-- 3. Salary Structure Lines
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.payroll_salary_structure_lines (
    line_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    structure_id UUID NOT NULL REFERENCES security_erp.payroll_salary_structures(structure_id) ON DELETE CASCADE,
    component_id UUID NOT NULL REFERENCES security_erp.payroll_salary_components(component_id) ON DELETE RESTRICT,
    amount NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    calculation_type VARCHAR(50) NOT NULL DEFAULT 'FIXED' CHECK (calculation_type IN ('FIXED', 'PERCENTAGE_OF_BASIC', 'FORMULA')),
    effective_from DATE NOT NULL,
    effective_to DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_payroll_struct_line ON security_erp.payroll_salary_structure_lines(structure_id);

-- ------------------------------------------------------------------------------
-- 4. Guard Salary Assignments (Effective-Dated)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.payroll_guard_salary_assignments (
    assignment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES security_erp.companies(company_id) ON DELETE RESTRICT,
    guard_id UUID NOT NULL REFERENCES security_erp.employees(employee_id) ON DELETE RESTRICT,
    structure_id UUID NOT NULL REFERENCES security_erp.payroll_salary_structures(structure_id) ON DELETE RESTRICT,
    pay_basis VARCHAR(30) NOT NULL DEFAULT 'MONTHLY' CHECK (pay_basis IN ('MONTHLY', 'DAILY', 'HOURLY')),
    effective_from DATE NOT NULL,
    effective_to DATE,
    reason TEXT NOT NULL,
    prepared_by UUID REFERENCES security_erp.app_users(user_id),
    approved_by UUID REFERENCES security_erp.app_users(user_id),
    status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('DRAFT', 'PENDING_APPROVAL', 'ACTIVE', 'SUPERSEDED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_payroll_assign_guard ON security_erp.payroll_guard_salary_assignments(guard_id, status, effective_from);

-- ------------------------------------------------------------------------------
-- 5. Configurable Minimum Wages
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.payroll_minimum_wages (
    record_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES security_erp.companies(company_id) ON DELETE RESTRICT,
    state VARCHAR(100) NOT NULL,
    zone VARCHAR(100),
    skill_category VARCHAR(100) NOT NULL,
    amount NUMERIC(12, 2) NOT NULL,
    pay_basis VARCHAR(30) NOT NULL DEFAULT 'DAILY' CHECK (pay_basis IN ('MONTHLY', 'DAILY', 'HOURLY')),
    effective_from DATE NOT NULL,
    effective_to DATE,
    source_document TEXT,
    approved_by UUID REFERENCES security_erp.app_users(user_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_payroll_min_wage ON security_erp.payroll_minimum_wages(company_id, state, skill_category);

-- ------------------------------------------------------------------------------
-- 6. Paid-Day Rule Sets
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.payroll_paid_day_rules (
    rule_set_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES security_erp.companies(company_id) ON DELETE RESTRICT,
    name VARCHAR(150) NOT NULL,
    month_length_rule VARCHAR(50) NOT NULL DEFAULT 'CALENDAR_DAYS' CHECK (month_length_rule IN ('CALENDAR_DAYS', 'FIXED_26', 'FIXED_30')),
    paid_day_mappings JSONB NOT NULL DEFAULT '{"worked": 1.0, "weekly_off": 1.0, "holiday": 1.0, "paid_leave": 1.0, "unpaid_leave": 0.0, "half_day": 0.5}'::jsonb,
    half_day_treatment VARCHAR(50) NOT NULL DEFAULT 'HALF_RATE',
    manual_treatment VARCHAR(50) NOT NULL DEFAULT 'NORMAL_PAID',
    offline_treatment VARCHAR(50) NOT NULL DEFAULT 'NORMAL_PAID',
    late_early_treatment VARCHAR(50) NOT NULL DEFAULT 'NO_DEDUCTION',
    weekly_off_treatment VARCHAR(50) NOT NULL DEFAULT 'PAID_IF_ELIGIBLE',
    holiday_treatment VARCHAR(50) NOT NULL DEFAULT 'PAID_IF_ELIGIBLE',
    effective_from DATE NOT NULL,
    effective_to DATE,
    version INT NOT NULL DEFAULT 1,
    approved_by UUID REFERENCES security_erp.app_users(user_id),
    status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('DRAFT', 'ACTIVE', 'SUPERSEDED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------------------
-- 7. Weekly Off & Holiday Calendars
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.payroll_weekly_off_calendars (
    calendar_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES security_erp.companies(company_id) ON DELETE RESTRICT,
    site_id UUID REFERENCES security_erp.client_sites(site_id) ON DELETE CASCADE,
    name VARCHAR(150) NOT NULL,
    weekly_off_pattern VARCHAR(50) NOT NULL DEFAULT 'SUNDAY',
    holidays JSONB NOT NULL DEFAULT '[]'::jsonb,
    status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------------------
-- 8. Statutory Rule Sets (Versioned & Dual-Approved)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.payroll_statutory_rule_sets (
    rule_set_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES security_erp.companies(company_id) ON DELETE RESTRICT,
    scheme VARCHAR(50) NOT NULL CHECK (scheme IN ('PF', 'ESI', 'PROFESSIONAL_TAX', 'LABOUR_WELFARE_FUND')),
    version INT NOT NULL DEFAULT 1,
    applicability JSONB NOT NULL DEFAULT '{}'::jsonb,
    eligibility JSONB NOT NULL DEFAULT '{}'::jsonb,
    wage_base_components JSONB NOT NULL DEFAULT '[]'::jsonb,
    employee_rate NUMERIC(6, 4),
    employer_rate NUMERIC(6, 4),
    contribution_splits JSONB NOT NULL DEFAULT '{}'::jsonb,
    wage_floor NUMERIC(12, 2),
    wage_ceiling NUMERIC(12, 2),
    slabs JSONB NOT NULL DEFAULT '[]'::jsonb,
    frequency VARCHAR(30) NOT NULL DEFAULT 'MONTHLY' CHECK (frequency IN ('MONTHLY', 'HALF_YEARLY', 'ANNUAL')),
    rounding_rule VARCHAR(50) NOT NULL DEFAULT 'NEAREST_RUPEE' CHECK (rounding_rule IN ('NEAREST_RUPEE', 'ROUND_UP', 'ROUND_DOWN', 'EXACT_PAISE')),
    rounding_level VARCHAR(50) NOT NULL DEFAULT 'EMPLOYEE_LEVEL',
    due_day INT,
    source_document TEXT,
    effective_from DATE NOT NULL,
    effective_to DATE,
    prepared_by UUID REFERENCES security_erp.app_users(user_id),
    approved_by UUID REFERENCES security_erp.app_users(user_id),
    status VARCHAR(30) NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'UNDER_REVIEW', 'APPROVED', 'ACTIVE', 'SUPERSEDED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_payroll_statutory_rule ON security_erp.payroll_statutory_rule_sets(company_id, scheme, status);

-- ------------------------------------------------------------------------------
-- 9. Guard Advances & Loans
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.payroll_advances (
    advance_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES security_erp.companies(company_id) ON DELETE RESTRICT,
    guard_id UUID NOT NULL REFERENCES security_erp.employees(employee_id) ON DELETE RESTRICT,
    amount NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
    issue_date DATE NOT NULL,
    reason TEXT NOT NULL,
    recovery_type VARCHAR(30) NOT NULL DEFAULT 'FIXED' CHECK (recovery_type IN ('FIXED', 'PERCENTAGE')),
    recovery_value NUMERIC(12, 2) NOT NULL CHECK (recovery_value > 0),
    max_per_instalment NUMERIC(12, 2) NOT NULL CHECK (max_per_instalment > 0),
    interest_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(30) NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'SUBMITTED', 'APPROVED', 'ISSUED', 'RECOVERING', 'RECOVERED', 'WRITTEN_OFF', 'REJECTED', 'CANCELLED')),
    approved_by UUID REFERENCES security_erp.app_users(user_id),
    created_by UUID REFERENCES security_erp.app_users(user_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_payroll_advances_guard ON security_erp.payroll_advances(guard_id, status);

-- ------------------------------------------------------------------------------
-- 10. Advance Append-Only Ledger
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.payroll_advance_ledger (
    entry_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    advance_id UUID NOT NULL REFERENCES security_erp.payroll_advances(advance_id) ON DELETE RESTRICT,
    entry_type VARCHAR(30) NOT NULL CHECK (entry_type IN ('ISSUE', 'RECOVERY', 'ADJUSTMENT', 'WRITE_OFF')),
    amount NUMERIC(12, 2) NOT NULL,
    entry_date DATE NOT NULL,
    payroll_run_id UUID,
    reason TEXT,
    created_by UUID REFERENCES security_erp.app_users(user_id),
    approved_by UUID REFERENCES security_erp.app_users(user_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_payroll_adv_ledger ON security_erp.payroll_advance_ledger(advance_id, entry_date);

-- ------------------------------------------------------------------------------
-- 11. Manual Deductions
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.payroll_manual_deductions (
    deduction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES security_erp.companies(company_id) ON DELETE RESTRICT,
    guard_id UUID NOT NULL REFERENCES security_erp.employees(employee_id) ON DELETE RESTRICT,
    category VARCHAR(100) NOT NULL,
    amount NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
    reason TEXT NOT NULL,
    source_reference VARCHAR(100),
    acknowledgement_required BOOLEAN NOT NULL DEFAULT FALSE,
    acknowledgement_status VARCHAR(30) DEFAULT 'PENDING' CHECK (acknowledgement_status IN ('PENDING', 'ACCEPTED', 'DISPUTED')),
    prepared_by UUID REFERENCES security_erp.app_users(user_id),
    approved_by UUID REFERENCES security_erp.app_users(user_id),
    status VARCHAR(30) NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'PENDING', 'APPROVED', 'REJECTED', 'APPLIED')),
    applied_in_run_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_payroll_manual_ded ON security_erp.payroll_manual_deductions(guard_id, status);

-- ------------------------------------------------------------------------------
-- 12. Payroll Runs
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.payroll_runs (
    run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES security_erp.companies(company_id) ON DELETE RESTRICT,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    period_reference VARCHAR(50) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'CALCULATED', 'UNDER_REVIEW', 'APPROVED', 'RELEASED', 'PAID', 'PARTIALLY_PAID', 'CLOSED', 'CANCELLED')),
    run_type VARCHAR(30) NOT NULL DEFAULT 'FINAL' CHECK (run_type IN ('FINAL', 'PROVISIONAL', 'SUPPLEMENTARY')),
    prepared_by UUID REFERENCES security_erp.app_users(user_id),
    approved_by UUID REFERENCES security_erp.app_users(user_id),
    approved_at TIMESTAMPTZ,
    result_hash VARCHAR(128),
    version INT NOT NULL DEFAULT 1,
    cancellation_reason TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_payroll_run_period UNIQUE (company_id, period_reference, run_type, version)
);

CREATE INDEX IF NOT EXISTS idx_payroll_runs_co ON security_erp.payroll_runs(company_id, period_reference, status);

-- ------------------------------------------------------------------------------
-- 13. Payroll Results (Per Guard)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.payroll_results (
    result_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES security_erp.payroll_runs(run_id) ON DELETE CASCADE,
    guard_id UUID NOT NULL REFERENCES security_erp.employees(employee_id) ON DELETE RESTRICT,
    salary_assignment_id UUID REFERENCES security_erp.payroll_guard_salary_assignments(assignment_id),
    paid_days NUMERIC(5, 2) NOT NULL DEFAULT 0.00,
    regular_minutes INT NOT NULL DEFAULT 0,
    overtime_minutes INT NOT NULL DEFAULT 0,
    gross_earnings NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    employee_deductions NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    employer_contributions NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    net_pay NUMERIC(12, 2) NOT NULL DEFAULT 0.00 CHECK (net_pay >= 0.00),
    is_held BOOLEAN NOT NULL DEFAULT FALSE,
    hold_reason TEXT,
    calculation_details JSONB NOT NULL DEFAULT '{}'::jsonb,
    rule_versions JSONB NOT NULL DEFAULT '{}'::jsonb,
    result_hash VARCHAR(128),
    version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_guard_per_run UNIQUE (run_id, guard_id)
);

CREATE INDEX IF NOT EXISTS idx_payroll_res_run ON security_erp.payroll_results(run_id, guard_id);

-- ------------------------------------------------------------------------------
-- 14. Payroll Result Lines (Itemized components, deductions, OT)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.payroll_result_lines (
    line_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    result_id UUID NOT NULL REFERENCES security_erp.payroll_results(result_id) ON DELETE CASCADE,
    component_id UUID REFERENCES security_erp.payroll_salary_components(component_id),
    line_type VARCHAR(50) NOT NULL CHECK (line_type IN ('EARNING', 'STATUTORY_DEDUCTION', 'RECURRING_DEDUCTION', 'MANUAL_DEDUCTION', 'ADVANCE_RECOVERY', 'EMPLOYER_CONTRIBUTION', 'ADJUSTMENT')),
    code VARCHAR(50) NOT NULL,
    description VARCHAR(150) NOT NULL,
    amount NUMERIC(12, 2) NOT NULL,
    reason TEXT,
    source_reference VARCHAR(100),
    formula_reference TEXT,
    rule_version VARCHAR(50)
);

CREATE INDEX IF NOT EXISTS idx_payroll_lines_res ON security_erp.payroll_result_lines(result_id);

-- ------------------------------------------------------------------------------
-- 15. Payslips (Immutable with Hash)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.payroll_payslips (
    payslip_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payslip_number VARCHAR(100) NOT NULL UNIQUE,
    guard_id UUID NOT NULL REFERENCES security_erp.employees(employee_id) ON DELETE RESTRICT,
    run_id UUID NOT NULL REFERENCES security_erp.payroll_runs(run_id) ON DELETE RESTRICT,
    result_id UUID NOT NULL REFERENCES security_erp.payroll_results(result_id) ON DELETE RESTRICT,
    version INT NOT NULL DEFAULT 1,
    pdf_reference TEXT,
    pdf_hash VARCHAR(128),
    released_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    previous_payslip_id UUID REFERENCES security_erp.payroll_payslips(payslip_id),
    is_latest BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_payroll_payslips_guard ON security_erp.payroll_payslips(guard_id, released_at);

-- ------------------------------------------------------------------------------
-- 16. Payment Records (External Disbursement & Reconciliation)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.payroll_payments (
    payment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES security_erp.payroll_runs(run_id) ON DELETE RESTRICT,
    result_id UUID NOT NULL REFERENCES security_erp.payroll_results(result_id) ON DELETE RESTRICT,
    guard_id UUID NOT NULL REFERENCES security_erp.employees(employee_id) ON DELETE RESTRICT,
    payment_date DATE NOT NULL,
    amount NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
    mode VARCHAR(30) NOT NULL DEFAULT 'BANK_TRANSFER' CHECK (mode IN ('BANK_TRANSFER', 'CASH', 'CHEQUE', 'OTHER')),
    bank_reference VARCHAR(100),
    status VARCHAR(30) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'PAID', 'FAILED', 'HELD', 'REVERSED')),
    failure_reason TEXT,
    reversal_reason TEXT,
    reversal_of_payment_id UUID REFERENCES security_erp.payroll_payments(payment_id),
    witness_or_acknowledgement TEXT,
    recorded_by UUID NOT NULL REFERENCES security_erp.app_users(user_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_payroll_payments_run ON security_erp.payroll_payments(run_id, guard_id, status);

-- ------------------------------------------------------------------------------
-- 17. Full and Final Settlement (Dual-Approval)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.payroll_final_settlements (
    settlement_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES security_erp.companies(company_id) ON DELETE RESTRICT,
    guard_id UUID NOT NULL REFERENCES security_erp.employees(employee_id) ON DELETE RESTRICT,
    exit_date DATE NOT NULL,
    final_payable_days NUMERIC(5, 2) NOT NULL DEFAULT 0.00,
    final_pay NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    advance_balance NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    manual_deductions NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    manual_dues NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    settlement_total NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    status VARCHAR(30) NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'UNDER_REVIEW', 'APPROVED', 'UNCLAIMED', 'PAID')),
    approver_one UUID REFERENCES security_erp.app_users(user_id),
    approver_two UUID REFERENCES security_erp.app_users(user_id),
    unclaimed_reason TEXT,
    contact_attempts JSONB NOT NULL DEFAULT '[]'::jsonb,
    statement_file TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_payroll_fnf_guard ON security_erp.payroll_final_settlements(guard_id, status);

-- ------------------------------------------------------------------------------
-- 18. Statutory Payments Tracker
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.payroll_statutory_payments (
    record_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES security_erp.companies(company_id) ON DELETE RESTRICT,
    scheme VARCHAR(50) NOT NULL CHECK (scheme IN ('PF', 'ESI', 'PROFESSIONAL_TAX', 'LABOUR_WELFARE_FUND')),
    period VARCHAR(50) NOT NULL,
    payment_date DATE,
    amount NUMERIC(12, 2) NOT NULL CHECK (amount >= 0),
    reference_number VARCHAR(100),
    paid_by UUID REFERENCES security_erp.app_users(user_id),
    proof_file TEXT,
    status VARCHAR(30) NOT NULL DEFAULT 'DUE' CHECK (status IN ('DUE', 'PAID', 'OVERDUE')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_payroll_stat_pay ON security_erp.payroll_statutory_payments(company_id, scheme, period);

-- ------------------------------------------------------------------------------
-- 19. Seed Function for Starter Components and Paid-Day Rule Set
-- ------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION security_erp.seed_module14_company_defaults(comp_id UUID)
RETURNS VOID AS $$
BEGIN
    -- Starter Salary Components
    INSERT INTO security_erp.payroll_salary_components (
        company_id, component_code, component_name, component_type, wage_base_flags, proration_enabled, classification, display_order, status
    ) VALUES 
        (comp_id, 'BASIC', 'Basic Salary', 'EARNING', '{"pf": true, "esi": true, "pt": true, "lwf": true}'::jsonb, true, 'Base Pay', 1, 'ACTIVE'),
        (comp_id, 'DA', 'Dearness Allowance', 'EARNING', '{"pf": true, "esi": true, "pt": true, "lwf": true}'::jsonb, true, 'Inflation Allowance', 2, 'ACTIVE'),
        (comp_id, 'HRA', 'House Rent Allowance', 'EARNING', '{"pf": false, "esi": true, "pt": true, "lwf": true}'::jsonb, true, 'Housing', 3, 'ACTIVE'),
        (comp_id, 'CONV', 'Conveyance Allowance', 'EARNING', '{"pf": false, "esi": true, "pt": true, "lwf": true}'::jsonb, true, 'Travel', 4, 'ACTIVE'),
        (comp_id, 'SPL_ALLW', 'Special Allowance', 'EARNING', '{"pf": false, "esi": true, "pt": true, "lwf": true}'::jsonb, true, 'Other Allowances', 5, 'ACTIVE')
    ON CONFLICT (company_id, component_code) DO NOTHING;

    -- Standard Paid-Day Rule Set
    INSERT INTO security_erp.payroll_paid_day_rules (
        company_id, name, month_length_rule, paid_day_mappings, half_day_treatment, manual_treatment, offline_treatment, late_early_treatment, weekly_off_treatment, holiday_treatment, effective_from, version, status
    ) VALUES (
        comp_id, 'Standard Monthly Calendar Rule Set', 'CALENDAR_DAYS',
        '{"worked": 1.0, "weekly_off": 1.0, "holiday": 1.0, "paid_leave": 1.0, "unpaid_leave": 0.0, "half_day": 0.5}'::jsonb,
        'HALF_RATE', 'NORMAL_PAID', 'NORMAL_PAID', 'NO_DEDUCTION', 'PAID_IF_ELIGIBLE', 'PAID_IF_ELIGIBLE',
        '2026-01-01', 1, 'ACTIVE'
    ) ON CONFLICT DO NOTHING;

END;
$$ LANGUAGE plpgsql;
