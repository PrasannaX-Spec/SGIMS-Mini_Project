-- Security Agency ERP Database Schema
-- Target DB: PostgreSQL 15+
-- Source: Uploaded "ERP Modules for a Security Agency Business Management System"
-- Design status: Baseline schema. Review assumptions and legal/statutory rules before production.
-- IMPORTANT: Run in a new database/schema. This script does not configure Supabase Auth or RLS policies.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS security_erp;
SET search_path TO security_erp, public;

-- 1. Organization, branches, access control
CREATE TABLE companies (
    company_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    legal_name VARCHAR(200) NOT NULL,
    trade_name VARCHAR(200),
    registration_no VARCHAR(100),
    gstin VARCHAR(15),
    pan VARCHAR(10),
    email VARCHAR(254),
    phone VARCHAR(30),
    address_line1 VARCHAR(200),
    address_line2 VARCHAR(200),
    city VARCHAR(100),
    state_code VARCHAR(10),
    postal_code VARCHAR(20),
    country_code CHAR(2) NOT NULL DEFAULT 'IN',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (registration_no),
    UNIQUE (gstin)
);

CREATE TABLE branches (
    branch_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    branch_code VARCHAR(30) NOT NULL,
    branch_name VARCHAR(150) NOT NULL,
    phone VARCHAR(30),
    email VARCHAR(254),
    address_line1 VARCHAR(200),
    address_line2 VARCHAR(200),
    city VARCHAR(100),
    state_code VARCHAR(10),
    postal_code VARCHAR(20),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (company_id, branch_code)
);

CREATE TABLE app_users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    branch_id UUID REFERENCES branches(branch_id) ON DELETE SET NULL,
    auth_provider VARCHAR(40) NOT NULL DEFAULT 'local',
    auth_subject VARCHAR(200),
    full_name VARCHAR(160) NOT NULL,
    email VARCHAR(254),
    phone VARCHAR(30),
    password_hash TEXT, -- nullable when an external identity provider is used
    account_status VARCHAR(20) NOT NULL DEFAULT 'invited'
        CHECK (account_status IN ('invited','active','locked','disabled')),
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (auth_provider, auth_subject),
    UNIQUE (company_id, email)
);

CREATE TABLE roles (
    role_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(company_id) ON DELETE CASCADE,
    role_code VARCHAR(50) NOT NULL,
    role_name VARCHAR(100) NOT NULL,
    description TEXT,
    UNIQUE (company_id, role_code)
);

CREATE TABLE permissions (
    permission_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    permission_code VARCHAR(100) NOT NULL UNIQUE,
    description TEXT NOT NULL
);

CREATE TABLE user_roles (
    user_id UUID NOT NULL REFERENCES app_users(user_id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES roles(role_id) ON DELETE CASCADE,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    assigned_by UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    PRIMARY KEY (user_id, role_id)
);

CREATE TABLE role_permissions (
    role_id UUID NOT NULL REFERENCES roles(role_id) ON DELETE CASCADE,
    permission_id UUID NOT NULL REFERENCES permissions(permission_id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

-- 2. CRM, client master, contacts, sites and surveys
CREATE TABLE leads (
    lead_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    branch_id UUID REFERENCES branches(branch_id) ON DELETE SET NULL,
    lead_name VARCHAR(180) NOT NULL,
    organization_name VARCHAR(200),
    lead_type VARCHAR(30) NOT NULL DEFAULT 'corporate'
        CHECK (lead_type IN ('corporate','residential','industrial','event','other')),
    source VARCHAR(80),
    email VARCHAR(254),
    phone VARCHAR(30),
    status VARCHAR(30) NOT NULL DEFAULT 'new'
        CHECK (status IN ('new','contacted','qualified','survey_scheduled','quoted','negotiation','won','lost','closed')),
    estimated_value NUMERIC(14,2) CHECK (estimated_value IS NULL OR estimated_value >= 0),
    owner_user_id UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE clients (
    client_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    client_code VARCHAR(40) NOT NULL,
    legal_name VARCHAR(200) NOT NULL,
    display_name VARCHAR(200),
    client_type VARCHAR(30) NOT NULL DEFAULT 'corporate',
    gstin VARCHAR(15),
    pan VARCHAR(10),
    billing_email VARCHAR(254),
    billing_phone VARCHAR(30),
    billing_address JSONB,
    payment_terms_days INTEGER NOT NULL DEFAULT 30 CHECK (payment_terms_days >= 0),
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active','on_hold','inactive')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (company_id, client_code)
);

CREATE TABLE client_contacts (
    contact_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
    full_name VARCHAR(160) NOT NULL,
    designation VARCHAR(100),
    email VARCHAR(254),
    phone VARCHAR(30),
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    contact_type VARCHAR(30) DEFAULT 'general',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE client_sites (
    site_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(client_id) ON DELETE RESTRICT,
    branch_id UUID REFERENCES branches(branch_id) ON DELETE SET NULL,
    site_code VARCHAR(40) NOT NULL,
    site_name VARCHAR(180) NOT NULL,
    site_type VARCHAR(40),
    address_line1 VARCHAR(200) NOT NULL,
    address_line2 VARCHAR(200),
    city VARCHAR(100),
    state_code VARCHAR(10) NOT NULL,
    postal_code VARCHAR(20),
    latitude NUMERIC(10,7),
    longitude NUMERIC(10,7),
    geofence_radius_m INTEGER CHECK (geofence_radius_m IS NULL OR geofence_radius_m > 0),
    site_contact_name VARCHAR(160),
    site_contact_phone VARCHAR(30),
    operational_status VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (operational_status IN ('planned','active','suspended','closed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (client_id, site_code)
);

CREATE TABLE site_surveys (
    survey_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID REFERENCES leads(lead_id) ON DELETE SET NULL,
    client_id UUID REFERENCES clients(client_id) ON DELETE SET NULL,
    site_id UUID REFERENCES client_sites(site_id) ON DELETE SET NULL,
    surveyed_by UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    survey_date DATE NOT NULL,
    risk_level VARCHAR(20) CHECK (risk_level IN ('low','medium','high','critical')),
    findings TEXT,
    recommended_posts JSONB,
    status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','submitted','approved','rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (lead_id IS NOT NULL OR client_id IS NOT NULL OR site_id IS NOT NULL)
);

-- 3. Quotations, contracts, rate cards, SLAs
CREATE TABLE quotations (
    quotation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    lead_id UUID REFERENCES leads(lead_id) ON DELETE SET NULL,
    client_id UUID REFERENCES clients(client_id) ON DELETE RESTRICT,
    quotation_no VARCHAR(50) NOT NULL,
    version_no INTEGER NOT NULL DEFAULT 1 CHECK (version_no > 0),
    issue_date DATE NOT NULL DEFAULT CURRENT_DATE,
    valid_until DATE,
    currency CHAR(3) NOT NULL DEFAULT 'INR',
    subtotal NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (subtotal >= 0),
    tax_amount NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (tax_amount >= 0),
    total_amount NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (total_amount >= 0),
    cost_breakdown JSONB NOT NULL DEFAULT '{}'::jsonb,
    margin_percent NUMERIC(6,3) CHECK (margin_percent IS NULL OR margin_percent >= 0),
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft','submitted','negotiation','accepted','rejected','expired','converted')),
    created_by UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (company_id, quotation_no, version_no),
    CHECK (valid_until IS NULL OR valid_until >= issue_date)
);

CREATE TABLE quotation_lines (
    quotation_line_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quotation_id UUID NOT NULL REFERENCES quotations(quotation_id) ON DELETE CASCADE,
    post_type VARCHAR(40) NOT NULL,
    shift_hours NUMERIC(4,1) NOT NULL DEFAULT 8 CHECK (shift_hours > 0),
    headcount INTEGER NOT NULL CHECK (headcount > 0),
    wage_cost NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (wage_cost >= 0),
    statutory_cost NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (statutory_cost >= 0),
    uniform_cost NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (uniform_cost >= 0),
    overhead_cost NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (overhead_cost >= 0),
    margin_amount NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (margin_amount >= 0),
    unit_rate NUMERIC(12,2) NOT NULL CHECK (unit_rate >= 0),
    line_total NUMERIC(14,2) NOT NULL CHECK (line_total >= 0)
);

CREATE TABLE contracts (
    contract_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    client_id UUID NOT NULL REFERENCES clients(client_id) ON DELETE RESTRICT,
    quotation_id UUID REFERENCES quotations(quotation_id) ON DELETE SET NULL,
    contract_no VARCHAR(60) NOT NULL,
    title VARCHAR(200) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE,
    renewal_notice_days INTEGER NOT NULL DEFAULT 30 CHECK (renewal_notice_days >= 0),
    billing_frequency VARCHAR(20) NOT NULL DEFAULT 'monthly'
        CHECK (billing_frequency IN ('weekly','fortnightly','monthly','quarterly','custom')),
    billing_method VARCHAR(20) NOT NULL DEFAULT 'fixed_monthly'
        CHECK (billing_method IN ('attendance_based','fixed_monthly')),
    escalation_terms JSONB NOT NULL DEFAULT '[]'::jsonb,
    sla_terms JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft','under_review','active','expired','terminated','renewed')),
    signed_at DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (company_id, contract_no),
    CHECK (end_date IS NULL OR end_date >= start_date)
);

CREATE TABLE post_types (
    post_type_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    code VARCHAR(40) NOT NULL,
    name VARCHAR(100) NOT NULL,
    requires_armed_authorization BOOLEAN NOT NULL DEFAULT FALSE,
    description TEXT,
    UNIQUE (company_id, code)
);

CREATE TABLE contract_site_requirements (
    requirement_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id UUID NOT NULL REFERENCES contracts(contract_id) ON DELETE RESTRICT,
    site_id UUID NOT NULL REFERENCES client_sites(site_id) ON DELETE RESTRICT,
    post_type_id UUID NOT NULL REFERENCES post_types(post_type_id) ON DELETE RESTRICT,
    shift_name VARCHAR(60) NOT NULL,
    shift_start TIME NOT NULL,
    shift_end TIME NOT NULL,
    shift_hours NUMERIC(4,1) NOT NULL CHECK (shift_hours > 0),
    required_headcount INTEGER NOT NULL CHECK (required_headcount >= 0),
    effective_from DATE NOT NULL,
    effective_to DATE,
    client_bill_rate NUMERIC(12,2) NOT NULL CHECK (client_bill_rate >= 0),
    UNIQUE (contract_id, site_id, post_type_id, shift_name, effective_from),
    CHECK (effective_to IS NULL OR effective_to >= effective_from)
);

CREATE TABLE contract_rate_revisions (
    revision_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id UUID NOT NULL REFERENCES contracts(contract_id) ON DELETE RESTRICT,
    effective_date DATE NOT NULL,
    reason VARCHAR(200) NOT NULL,
    old_rate_snapshot JSONB,
    new_rate_snapshot JSONB NOT NULL,
    approved_by UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 4. Recruitment, employee records, documents, checks, skills and training
CREATE TABLE applicants (
    applicant_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    branch_id UUID REFERENCES branches(branch_id) ON DELETE SET NULL,
    full_name VARCHAR(160) NOT NULL,
    date_of_birth DATE,
    phone VARCHAR(30),
    email VARCHAR(254),
    address JSONB,
    source VARCHAR(50),
    applied_role VARCHAR(100),
    application_status VARCHAR(30) NOT NULL DEFAULT 'received'
        CHECK (application_status IN ('received','screening','interview','selected','rejected','hired','withdrawn')),
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    notes TEXT
);

CREATE TABLE employees (
    employee_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    branch_id UUID REFERENCES branches(branch_id) ON DELETE SET NULL,
    applicant_id UUID UNIQUE REFERENCES applicants(applicant_id) ON DELETE SET NULL,
    employee_code VARCHAR(50) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    middle_name VARCHAR(100),
    last_name VARCHAR(100),
    date_of_birth DATE,
    gender VARCHAR(30),
    phone VARCHAR(30),
    email VARCHAR(254),
    address JSONB,
    emergency_contact JSONB,
    date_joined DATE NOT NULL,
    employment_type VARCHAR(30) NOT NULL DEFAULT 'full_time',
    employment_status VARCHAR(30) NOT NULL DEFAULT 'active'
        CHECK (employment_status IN ('active','on_leave','suspended','resigned','terminated','retired')),
    designation VARCHAR(100),
    grade VARCHAR(50),
    bank_details JSONB, -- restrict access; consider encrypting sensitive values outside this baseline
    id_card_no VARCHAR(60),
    exit_date DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (company_id, employee_code),
    CHECK (exit_date IS NULL OR exit_date >= date_joined)
);

CREATE TABLE employee_documents (
    document_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID NOT NULL REFERENCES employees(employee_id) ON DELETE RESTRICT,
    document_type VARCHAR(60) NOT NULL,
    storage_key TEXT NOT NULL,
    original_filename VARCHAR(255),
    issue_date DATE,
    expiry_date DATE,
    verification_status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (verification_status IN ('pending','verified','rejected','expired')),
    verified_by UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    verified_at TIMESTAMPTZ,
    notes TEXT,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE employee_checks (
    check_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID NOT NULL REFERENCES employees(employee_id) ON DELETE RESTRICT,
    check_type VARCHAR(40) NOT NULL CHECK (check_type IN ('police','background','medical','other')),
    provider VARCHAR(160),
    requested_at DATE,
    completed_at DATE,
    valid_until DATE,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','in_progress','cleared','failed','expired')),
    result_reference TEXT,
    notes TEXT
);

CREATE TABLE skills (
    skill_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    skill_code VARCHAR(50) NOT NULL,
    skill_name VARCHAR(100) NOT NULL,
    UNIQUE (company_id, skill_code)
);

CREATE TABLE employee_skills (
    employee_id UUID NOT NULL REFERENCES employees(employee_id) ON DELETE CASCADE,
    skill_id UUID NOT NULL REFERENCES skills(skill_id) ON DELETE RESTRICT,
    proficiency VARCHAR(30),
    verified BOOLEAN NOT NULL DEFAULT FALSE,
    valid_until DATE,
    PRIMARY KEY (employee_id, skill_id)
);

CREATE TABLE training_courses (
    course_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    course_code VARCHAR(50) NOT NULL,
    course_name VARCHAR(160) NOT NULL,
    course_type VARCHAR(50) NOT NULL,
    mandatory BOOLEAN NOT NULL DEFAULT FALSE,
    validity_months INTEGER CHECK (validity_months IS NULL OR validity_months > 0),
    description TEXT,
    UNIQUE (company_id, course_code)
);

CREATE TABLE training_sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id UUID NOT NULL REFERENCES training_courses(course_id) ON DELETE RESTRICT,
    session_name VARCHAR(160),
    trainer_name VARCHAR(160),
    location VARCHAR(200),
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ NOT NULL,
    capacity INTEGER CHECK (capacity IS NULL OR capacity > 0),
    status VARCHAR(20) NOT NULL DEFAULT 'scheduled'
        CHECK (status IN ('scheduled','completed','cancelled')),
    CHECK (ends_at > starts_at)
);

CREATE TABLE employee_training (
    employee_training_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID NOT NULL REFERENCES employees(employee_id) ON DELETE RESTRICT,
    session_id UUID NOT NULL REFERENCES training_sessions(session_id) ON DELETE RESTRICT,
    attendance_status VARCHAR(20) NOT NULL DEFAULT 'registered'
        CHECK (attendance_status IN ('registered','present','absent','excused')),
    result VARCHAR(20) CHECK (result IN ('passed','failed','not_assessed')),
    certificate_storage_key TEXT,
    certificate_no VARCHAR(100),
    completed_at DATE,
    valid_until DATE,
    UNIQUE (employee_id, session_id)
);

CREATE TABLE employee_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID NOT NULL REFERENCES employees(employee_id) ON DELETE RESTRICT,
    event_type VARCHAR(30) NOT NULL
        CHECK (event_type IN ('transfer','promotion','disciplinary_action','resignation','termination','f_and_f')),
    effective_date DATE NOT NULL,
    from_site_id UUID REFERENCES client_sites(site_id) ON DELETE SET NULL,
    to_site_id UUID REFERENCES client_sites(site_id) ON DELETE SET NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    approved_by UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE leave_requests (
    leave_request_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID NOT NULL REFERENCES employees(employee_id) ON DELETE RESTRICT,
    leave_type VARCHAR(50) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    reason TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','approved','rejected','cancelled')),
    requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_by UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    reviewed_at TIMESTAMPTZ,
    CHECK (end_date >= start_date)
);

-- 5. Deployment, posts, rosters and shift assignments
CREATE TABLE site_posts (
    site_post_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    requirement_id UUID REFERENCES contract_site_requirements(requirement_id) ON DELETE RESTRICT,
    site_id UUID NOT NULL REFERENCES client_sites(site_id) ON DELETE RESTRICT,
    post_type_id UUID NOT NULL REFERENCES post_types(post_type_id) ON DELETE RESTRICT,
    post_code VARCHAR(50) NOT NULL,
    post_name VARCHAR(120) NOT NULL,
    is_armed BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active','inactive')),
    UNIQUE (site_id, post_code)
);

CREATE TABLE roster_shifts (
    shift_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id UUID NOT NULL REFERENCES client_sites(site_id) ON DELETE RESTRICT,
    shift_name VARCHAR(60) NOT NULL,
    starts_at TIME NOT NULL,
    ends_at TIME NOT NULL,
    duration_hours NUMERIC(4,1) NOT NULL CHECK (duration_hours > 0),
    crosses_midnight BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (site_id, shift_name)
);

CREATE TABLE shift_assignments (
    assignment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_post_id UUID NOT NULL REFERENCES site_posts(site_post_id) ON DELETE RESTRICT,
    shift_id UUID NOT NULL REFERENCES roster_shifts(shift_id) ON DELETE RESTRICT,
    employee_id UUID NOT NULL REFERENCES employees(employee_id) ON DELETE RESTRICT,
    duty_date DATE NOT NULL,
    assignment_type VARCHAR(20) NOT NULL DEFAULT 'regular'
        CHECK (assignment_type IN ('regular','reliever','replacement','overtime')),
    status VARCHAR(20) NOT NULL DEFAULT 'planned'
        CHECK (status IN ('planned','confirmed','completed','cancelled','no_show')),
    assigned_by UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (site_post_id, shift_id, duty_date, employee_id)
);

-- 6. Attendance, patrol checkpoints, supervisor visits
CREATE TABLE attendance_records (
    attendance_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assignment_id UUID REFERENCES shift_assignments(assignment_id) ON DELETE RESTRICT,
    employee_id UUID NOT NULL REFERENCES employees(employee_id) ON DELETE RESTRICT,
    site_id UUID NOT NULL REFERENCES client_sites(site_id) ON DELETE RESTRICT,
    duty_date DATE NOT NULL,
    check_in_at TIMESTAMPTZ,
    check_out_at TIMESTAMPTZ,
    check_in_lat NUMERIC(10,7),
    check_in_lon NUMERIC(10,7),
    check_out_lat NUMERIC(10,7),
    check_out_lon NUMERIC(10,7),
    check_in_evidence_key TEXT,
    check_out_evidence_key TEXT,
    source VARCHAR(20) NOT NULL DEFAULT 'mobile'
        CHECK (source IN ('mobile','biometric','manual','device','client_portal')),
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','present','late','absent','half_day','rejected')),
    regular_hours NUMERIC(6,2) NOT NULL DEFAULT 0 CHECK (regular_hours >= 0),
    overtime_hours NUMERIC(6,2) NOT NULL DEFAULT 0 CHECK (overtime_hours >= 0),
    approval_status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (approval_status IN ('pending','approved','rejected')),
    approved_by UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    approved_at TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (check_out_at IS NULL OR check_in_at IS NULL OR check_out_at > check_in_at)
);

CREATE TABLE patrol_checkpoints (
    checkpoint_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id UUID NOT NULL REFERENCES client_sites(site_id) ON DELETE RESTRICT,
    checkpoint_code VARCHAR(60) NOT NULL,
    checkpoint_name VARCHAR(120) NOT NULL,
    checkpoint_type VARCHAR(10) NOT NULL CHECK (checkpoint_type IN ('QR','NFC','RFID','GPS')),
    device_reference VARCHAR(160),
    latitude NUMERIC(10,7),
    longitude NUMERIC(10,7),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (site_id, checkpoint_code)
);

CREATE TABLE patrol_rounds (
    patrol_round_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id UUID NOT NULL REFERENCES client_sites(site_id) ON DELETE RESTRICT,
    employee_id UUID NOT NULL REFERENCES employees(employee_id) ON DELETE RESTRICT,
    assignment_id UUID REFERENCES shift_assignments(assignment_id) ON DELETE SET NULL,
    planned_start TIMESTAMPTZ,
    planned_end TIMESTAMPTZ,
    actual_start TIMESTAMPTZ,
    actual_end TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL DEFAULT 'planned'
        CHECK (status IN ('planned','in_progress','completed','missed','cancelled')),
    notes TEXT,
    CHECK (planned_end IS NULL OR planned_start IS NULL OR planned_end > planned_start)
);

CREATE TABLE patrol_scans (
    scan_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patrol_round_id UUID NOT NULL REFERENCES patrol_rounds(patrol_round_id) ON DELETE CASCADE,
    checkpoint_id UUID NOT NULL REFERENCES patrol_checkpoints(checkpoint_id) ON DELETE RESTRICT,
    scanned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    latitude NUMERIC(10,7),
    longitude NUMERIC(10,7),
    evidence_key TEXT,
    scan_status VARCHAR(20) NOT NULL DEFAULT 'valid'
        CHECK (scan_status IN ('valid','late','out_of_geofence','invalid')),
    UNIQUE (patrol_round_id, checkpoint_id, scanned_at)
);

CREATE TABLE supervisor_visits (
    visit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id UUID NOT NULL REFERENCES client_sites(site_id) ON DELETE RESTRICT,
    supervisor_employee_id UUID NOT NULL REFERENCES employees(employee_id) ON DELETE RESTRICT,
    visited_at TIMESTAMPTZ NOT NULL,
    latitude NUMERIC(10,7),
    longitude NUMERIC(10,7),
    photo_storage_key TEXT,
    notes TEXT,
    outcome VARCHAR(30) DEFAULT 'completed'
);

-- 7. Incidents, daily logs, gate passes, SOS and complaints
CREATE TABLE incidents (
    incident_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    site_id UUID NOT NULL REFERENCES client_sites(site_id) ON DELETE RESTRICT,
    reported_by_employee_id UUID REFERENCES employees(employee_id) ON DELETE SET NULL,
    incident_no VARCHAR(60) NOT NULL,
    incident_type VARCHAR(80) NOT NULL,
    severity VARCHAR(20) NOT NULL DEFAULT 'medium'
        CHECK (severity IN ('low','medium','high','critical')),
    occurred_at TIMESTAMPTZ NOT NULL,
    reported_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    description TEXT NOT NULL,
    action_taken TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'open'
        CHECK (status IN ('open','investigating','escalated','resolved','closed')),
    assigned_to UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (company_id, incident_no)
);

CREATE TABLE incident_attachments (
    attachment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID NOT NULL REFERENCES incidents(incident_id) ON DELETE CASCADE,
    storage_key TEXT NOT NULL,
    media_type VARCHAR(30) NOT NULL CHECK (media_type IN ('photo','video','document','other')),
    original_filename VARCHAR(255),
    uploaded_by UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE daily_site_logs (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id UUID NOT NULL REFERENCES client_sites(site_id) ON DELETE RESTRICT,
    employee_id UUID NOT NULL REFERENCES employees(employee_id) ON DELETE RESTRICT,
    log_date DATE NOT NULL,
    log_type VARCHAR(50) NOT NULL DEFAULT 'daily_activity',
    entry_text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE gate_passes (
    gate_pass_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id UUID NOT NULL REFERENCES client_sites(site_id) ON DELETE RESTRICT,
    pass_type VARCHAR(20) NOT NULL CHECK (pass_type IN ('visitor','vehicle','material')),
    pass_no VARCHAR(60) NOT NULL,
    person_name VARCHAR(160),
    organization_name VARCHAR(160),
    phone VARCHAR(30),
    vehicle_no VARCHAR(40),
    material_description TEXT,
    direction VARCHAR(10) CHECK (direction IN ('in','out')),
    entry_at TIMESTAMPTZ,
    exit_at TIMESTAMPTZ,
    authorized_by_employee_id UUID REFERENCES employees(employee_id) ON DELETE SET NULL,
    recorded_by_employee_id UUID REFERENCES employees(employee_id) ON DELETE SET NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'open' CHECK (status IN ('open','closed','cancelled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (site_id, pass_no),
    CHECK (exit_at IS NULL OR entry_at IS NULL OR exit_at >= entry_at)
);

CREATE TABLE escalation_rules (
    escalation_rule_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    site_id UUID REFERENCES client_sites(site_id) ON DELETE CASCADE,
    event_type VARCHAR(60) NOT NULL,
    severity VARCHAR(20),
    step_no INTEGER NOT NULL CHECK (step_no > 0),
    target_role VARCHAR(80),
    target_user_id UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    delay_minutes INTEGER NOT NULL DEFAULT 0 CHECK (delay_minutes >= 0),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (company_id, site_id, event_type, severity, step_no)
);

CREATE TABLE sos_events (
    sos_event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    site_id UUID REFERENCES client_sites(site_id) ON DELETE SET NULL,
    employee_id UUID REFERENCES employees(employee_id) ON DELETE SET NULL,
    triggered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    latitude NUMERIC(10,7),
    longitude NUMERIC(10,7),
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'triggered'
        CHECK (status IN ('triggered','acknowledged','responding','resolved','false_alarm')),
    acknowledged_by UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    resolved_at TIMESTAMPTZ
);

CREATE TABLE client_tickets (
    ticket_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(client_id) ON DELETE RESTRICT,
    site_id UUID REFERENCES client_sites(site_id) ON DELETE SET NULL,
    ticket_no VARCHAR(60) NOT NULL,
    ticket_type VARCHAR(30) NOT NULL CHECK (ticket_type IN ('complaint','feedback','extra_manpower','service_request','other')),
    subject VARCHAR(200) NOT NULL,
    description TEXT,
    priority VARCHAR(20) NOT NULL DEFAULT 'normal' CHECK (priority IN ('low','normal','high','urgent')),
    status VARCHAR(20) NOT NULL DEFAULT 'open'
        CHECK (status IN ('open','assigned','in_progress','resolved','closed','rejected')),
    assigned_to UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ,
    UNIQUE (client_id, ticket_no)
);

-- 8. Payroll, wage structures, pay runs, deductions, advances and payslips
CREATE TABLE wage_rates (
    wage_rate_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    state_code VARCHAR(10) NOT NULL,
    site_id UUID REFERENCES client_sites(site_id) ON DELETE SET NULL,
    client_id UUID REFERENCES clients(client_id) ON DELETE SET NULL,
    post_type_id UUID NOT NULL REFERENCES post_types(post_type_id) ON DELETE RESTRICT,
    effective_from DATE NOT NULL,
    effective_to DATE,
    pay_basis VARCHAR(20) NOT NULL DEFAULT 'monthly'
        CHECK (pay_basis IN ('hourly','daily','monthly')),
    base_rate NUMERIC(12,2) NOT NULL CHECK (base_rate >= 0),
    overtime_multiplier NUMERIC(5,2) NOT NULL DEFAULT 1.5 CHECK (overtime_multiplier >= 0),
    statutory_config JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (effective_to IS NULL OR effective_to >= effective_from)
);

CREATE TABLE payroll_runs (
    payroll_run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    branch_id UUID REFERENCES branches(branch_id) ON DELETE SET NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft','calculated','approved','paid','cancelled')),
    created_by UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    approved_by UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (company_id, branch_id, period_start, period_end),
    CHECK (period_end >= period_start)
);

CREATE TABLE employee_payroll (
    employee_payroll_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payroll_run_id UUID NOT NULL REFERENCES payroll_runs(payroll_run_id) ON DELETE RESTRICT,
    employee_id UUID NOT NULL REFERENCES employees(employee_id) ON DELETE RESTRICT,
    paid_days NUMERIC(6,2) NOT NULL DEFAULT 0 CHECK (paid_days >= 0),
    regular_hours NUMERIC(7,2) NOT NULL DEFAULT 0 CHECK (regular_hours >= 0),
    overtime_hours NUMERIC(7,2) NOT NULL DEFAULT 0 CHECK (overtime_hours >= 0),
    gross_pay NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (gross_pay >= 0),
    total_allowances NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (total_allowances >= 0),
    total_deductions NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (total_deductions >= 0),
    employer_contributions NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (employer_contributions >= 0),
    net_pay NUMERIC(14,2) NOT NULL DEFAULT 0,
    payment_status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (payment_status IN ('pending','approved','paid','failed','held')),
    payslip_storage_key TEXT,
    UNIQUE (payroll_run_id, employee_id)
);

CREATE TABLE payroll_components (
    payroll_component_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_payroll_id UUID NOT NULL REFERENCES employee_payroll(employee_payroll_id) ON DELETE CASCADE,
    component_type VARCHAR(20) NOT NULL CHECK (component_type IN ('earning','allowance','deduction','employer_contribution')),
    component_code VARCHAR(50) NOT NULL,
    description VARCHAR(200),
    amount NUMERIC(14,2) NOT NULL CHECK (amount >= 0)
);

CREATE TABLE employee_advances (
    advance_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID NOT NULL REFERENCES employees(employee_id) ON DELETE RESTRICT,
    advance_type VARCHAR(20) NOT NULL CHECK (advance_type IN ('advance','loan','uniform','penalty','other')),
    amount NUMERIC(14,2) NOT NULL CHECK (amount > 0),
    issued_on DATE NOT NULL,
    outstanding_amount NUMERIC(14,2) NOT NULL CHECK (outstanding_amount >= 0),
    status VARCHAR(20) NOT NULL DEFAULT 'open' CHECK (status IN ('open','settled','cancelled')),
    approved_by UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    notes TEXT,
    CHECK (outstanding_amount <= amount)
);

CREATE TABLE payroll_payments (
    payroll_payment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_payroll_id UUID NOT NULL REFERENCES employee_payroll(employee_payroll_id) ON DELETE RESTRICT,
    payment_date DATE,
    amount NUMERIC(14,2) NOT NULL CHECK (amount > 0),
    payment_method VARCHAR(20) NOT NULL CHECK (payment_method IN ('bank_transfer','cash','cheque','other')),
    bank_reference VARCHAR(120),
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','successful','failed','reversed')),
    notes TEXT
);

-- 9. Statutory compliance and licences
CREATE TABLE compliance_obligations (
    obligation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    state_code VARCHAR(10),
    obligation_type VARCHAR(40) NOT NULL
        CHECK (obligation_type IN ('PF','ESI','PT','LWF','BONUS','GRATUITY','PSARA','ARMS','OTHER')),
    reference_no VARCHAR(100),
    period_start DATE,
    period_end DATE,
    due_date DATE,
    filed_date DATE,
    amount_due NUMERIC(14,2) CHECK (amount_due IS NULL OR amount_due >= 0),
    amount_paid NUMERIC(14,2) CHECK (amount_paid IS NULL OR amount_paid >= 0),
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','in_progress','filed','paid','overdue','not_applicable')),
    evidence_storage_key TEXT,
    notes TEXT,
    CHECK (period_end IS NULL OR period_start IS NULL OR period_end >= period_start)
);

CREATE TABLE agency_licences (
    licence_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    branch_id UUID REFERENCES branches(branch_id) ON DELETE SET NULL,
    licence_type VARCHAR(50) NOT NULL,
    licence_number VARCHAR(100) NOT NULL,
    issuing_authority VARCHAR(160),
    state_code VARCHAR(10),
    valid_from DATE,
    valid_until DATE,
    status VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active','expiring','expired','suspended','cancelled')),
    document_storage_key TEXT,
    UNIQUE (company_id, licence_type, licence_number),
    CHECK (valid_until IS NULL OR valid_from IS NULL OR valid_until >= valid_from)
);

CREATE TABLE weapons (
    weapon_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    weapon_type VARCHAR(80) NOT NULL,
    serial_number VARCHAR(100) NOT NULL,
    arms_licence_id UUID REFERENCES agency_licences(licence_id) ON DELETE RESTRICT,
    status VARCHAR(20) NOT NULL DEFAULT 'available'
        CHECK (status IN ('available','issued','maintenance','retired','confiscated')),
    storage_location VARCHAR(160),
    UNIQUE (company_id, serial_number)
);

CREATE TABLE weapon_assignments (
    weapon_assignment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    weapon_id UUID NOT NULL REFERENCES weapons(weapon_id) ON DELETE RESTRICT,
    employee_id UUID NOT NULL REFERENCES employees(employee_id) ON DELETE RESTRICT,
    issued_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    returned_at TIMESTAMPTZ,
    issued_by UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    returned_to UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    issue_condition TEXT,
    return_condition TEXT,
    CHECK (returned_at IS NULL OR returned_at >= issued_at)
);

CREATE TABLE ammunition_transactions (
    ammunition_transaction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    weapon_id UUID REFERENCES weapons(weapon_id) ON DELETE RESTRICT,
    employee_id UUID REFERENCES employees(employee_id) ON DELETE SET NULL,
    transaction_type VARCHAR(20) NOT NULL CHECK (transaction_type IN ('received','issued','used','returned','disposed','adjustment')),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    transaction_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    reference_no VARCHAR(100),
    authorized_by UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    notes TEXT
);

-- 10. Billing, invoices, credit notes, annexures and collections
CREATE TABLE client_invoices (
    invoice_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    client_id UUID NOT NULL REFERENCES clients(client_id) ON DELETE RESTRICT,
    contract_id UUID REFERENCES contracts(contract_id) ON DELETE RESTRICT,
    site_id UUID REFERENCES client_sites(site_id) ON DELETE SET NULL,
    invoice_no VARCHAR(60) NOT NULL,
    invoice_date DATE NOT NULL DEFAULT CURRENT_DATE,
    due_date DATE,
    period_start DATE,
    period_end DATE,
    invoice_type VARCHAR(30) NOT NULL DEFAULT 'service'
        CHECK (invoice_type IN ('service','supplementary','arrears','credit_adjustment')),
    subtotal NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (subtotal >= 0),
    discount_amount NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
    tax_amount NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (tax_amount >= 0),
    total_amount NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (total_amount >= 0),
    outstanding_amount NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (outstanding_amount >= 0),
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft','issued','part_paid','paid','overdue','cancelled')),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (company_id, invoice_no),
    CHECK (due_date IS NULL OR due_date >= invoice_date),
    CHECK (period_end IS NULL OR period_start IS NULL OR period_end >= period_start)
);

CREATE TABLE invoice_lines (
    invoice_line_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id UUID NOT NULL REFERENCES client_invoices(invoice_id) ON DELETE RESTRICT,
    description VARCHAR(250) NOT NULL,
    site_id UUID REFERENCES client_sites(site_id) ON DELETE SET NULL,
    quantity NUMERIC(12,3) NOT NULL DEFAULT 1 CHECK (quantity > 0),
    unit_rate NUMERIC(14,2) NOT NULL CHECK (unit_rate >= 0),
    tax_rate NUMERIC(6,3) NOT NULL DEFAULT 0 CHECK (tax_rate >= 0),
    line_amount NUMERIC(14,2) NOT NULL CHECK (line_amount >= 0)
);

CREATE TABLE invoice_attachments (
    invoice_attachment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id UUID NOT NULL REFERENCES client_invoices(invoice_id) ON DELETE RESTRICT,
    attachment_type VARCHAR(50) NOT NULL,
    storage_key TEXT NOT NULL,
    original_filename VARCHAR(255),
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE credit_notes (
    credit_note_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    invoice_id UUID NOT NULL REFERENCES client_invoices(invoice_id) ON DELETE RESTRICT,
    credit_note_no VARCHAR(60) NOT NULL,
    issue_date DATE NOT NULL DEFAULT CURRENT_DATE,
    reason TEXT NOT NULL,
    amount NUMERIC(14,2) NOT NULL CHECK (amount > 0),
    tax_amount NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (tax_amount >= 0),
    status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','issued','cancelled')),
    UNIQUE (company_id, credit_note_no)
);

CREATE TABLE client_payments (
    client_payment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(client_id) ON DELETE RESTRICT,
    payment_date DATE NOT NULL,
    amount NUMERIC(14,2) NOT NULL CHECK (amount > 0),
    payment_method VARCHAR(20) NOT NULL CHECK (payment_method IN ('bank_transfer','cash','cheque','upi','other')),
    reference_no VARCHAR(120),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE invoice_payment_allocations (
    invoice_id UUID NOT NULL REFERENCES client_invoices(invoice_id) ON DELETE RESTRICT,
    client_payment_id UUID NOT NULL REFERENCES client_payments(client_payment_id) ON DELETE RESTRICT,
    allocated_amount NUMERIC(14,2) NOT NULL CHECK (allocated_amount > 0),
    PRIMARY KEY (invoice_id, client_payment_id)
);

-- 11. Accounting, expenses, vendors, purchases and inventory
CREATE TABLE vendors (
    vendor_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    vendor_code VARCHAR(50) NOT NULL,
    legal_name VARCHAR(200) NOT NULL,
    gstin VARCHAR(15),
    pan VARCHAR(10),
    email VARCHAR(254),
    phone VARCHAR(30),
    address JSONB,
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active','inactive','blocked')),
    UNIQUE (company_id, vendor_code)
);

CREATE TABLE purchase_orders (
    purchase_order_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    vendor_id UUID NOT NULL REFERENCES vendors(vendor_id) ON DELETE RESTRICT,
    po_no VARCHAR(60) NOT NULL,
    order_date DATE NOT NULL DEFAULT CURRENT_DATE,
    expected_date DATE,
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft','submitted','approved','part_received','received','cancelled')),
    subtotal NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (subtotal >= 0),
    tax_amount NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (tax_amount >= 0),
    total_amount NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (total_amount >= 0),
    created_by UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    UNIQUE (company_id, po_no),
    CHECK (expected_date IS NULL OR expected_date >= order_date)
);

CREATE TABLE inventory_items (
    item_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    item_code VARCHAR(60) NOT NULL,
    item_name VARCHAR(160) NOT NULL,
    category VARCHAR(80) NOT NULL,
    unit_of_measure VARCHAR(30) NOT NULL DEFAULT 'each',
    is_serialized BOOLEAN NOT NULL DEFAULT FALSE,
    reorder_level NUMERIC(12,3) NOT NULL DEFAULT 0 CHECK (reorder_level >= 0),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (company_id, item_code)
);

CREATE TABLE purchase_order_lines (
    purchase_order_line_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    purchase_order_id UUID NOT NULL REFERENCES purchase_orders(purchase_order_id) ON DELETE RESTRICT,
    item_id UUID NOT NULL REFERENCES inventory_items(item_id) ON DELETE RESTRICT,
    quantity NUMERIC(12,3) NOT NULL CHECK (quantity > 0),
    unit_cost NUMERIC(14,2) NOT NULL CHECK (unit_cost >= 0),
    tax_rate NUMERIC(6,3) NOT NULL DEFAULT 0 CHECK (tax_rate >= 0),
    line_total NUMERIC(14,2) NOT NULL CHECK (line_total >= 0)
);

CREATE TABLE inventory_locations (
    location_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    branch_id UUID REFERENCES branches(branch_id) ON DELETE SET NULL,
    location_code VARCHAR(50) NOT NULL,
    location_name VARCHAR(120) NOT NULL,
    location_type VARCHAR(30) NOT NULL DEFAULT 'warehouse',
    UNIQUE (company_id, location_code)
);

CREATE TABLE goods_receipts (
    goods_receipt_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    purchase_order_id UUID REFERENCES purchase_orders(purchase_order_id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES inventory_locations(location_id) ON DELETE RESTRICT,
    receipt_no VARCHAR(60) NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    received_by UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'received' CHECK (status IN ('received','rejected','reversed')),
    UNIQUE (location_id, receipt_no)
);

CREATE TABLE inventory_transactions (
    inventory_transaction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    item_id UUID NOT NULL REFERENCES inventory_items(item_id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES inventory_locations(location_id) ON DELETE RESTRICT,
    transaction_type VARCHAR(20) NOT NULL
        CHECK (transaction_type IN ('receipt','issue','return','transfer_in','transfer_out','adjustment','write_off')),
    quantity NUMERIC(12,3) NOT NULL CHECK (quantity > 0),
    unit_cost NUMERIC(14,2) CHECK (unit_cost IS NULL OR unit_cost >= 0),
    transaction_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    reference_type VARCHAR(50),
    reference_id UUID,
    employee_id UUID REFERENCES employees(employee_id) ON DELETE SET NULL,
    performed_by UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    notes TEXT
);

CREATE TABLE asset_assignments (
    asset_assignment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    item_id UUID NOT NULL REFERENCES inventory_items(item_id) ON DELETE RESTRICT,
    employee_id UUID NOT NULL REFERENCES employees(employee_id) ON DELETE RESTRICT,
    issued_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    returned_at TIMESTAMPTZ,
    issued_quantity NUMERIC(12,3) NOT NULL DEFAULT 1 CHECK (issued_quantity > 0),
    returned_quantity NUMERIC(12,3) NOT NULL DEFAULT 0 CHECK (returned_quantity >= 0),
    condition_on_issue TEXT,
    condition_on_return TEXT,
    deduction_amount NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (deduction_amount >= 0),
    issued_by UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    CHECK (returned_quantity <= issued_quantity),
    CHECK (returned_at IS NULL OR returned_at >= issued_at)
);

CREATE TABLE expenses (
    expense_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    branch_id UUID REFERENCES branches(branch_id) ON DELETE SET NULL,
    site_id UUID REFERENCES client_sites(site_id) ON DELETE SET NULL,
    expense_date DATE NOT NULL,
    category VARCHAR(80) NOT NULL,
    description TEXT NOT NULL,
    amount NUMERIC(14,2) NOT NULL CHECK (amount >= 0),
    tax_amount NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (tax_amount >= 0),
    payment_method VARCHAR(20),
    vendor_id UUID REFERENCES vendors(vendor_id) ON DELETE SET NULL,
    receipt_storage_key TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'submitted' CHECK (status IN ('submitted','approved','rejected','paid')),
    submitted_by UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    approved_by UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE chart_of_accounts (
    account_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    account_code VARCHAR(40) NOT NULL,
    account_name VARCHAR(160) NOT NULL,
    account_type VARCHAR(20) NOT NULL CHECK (account_type IN ('asset','liability','equity','income','expense')),
    parent_account_id UUID REFERENCES chart_of_accounts(account_id) ON DELETE RESTRICT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (company_id, account_code)
);

CREATE TABLE journal_entries (
    journal_entry_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    entry_no VARCHAR(60) NOT NULL,
    entry_date DATE NOT NULL,
    description TEXT,
    source_type VARCHAR(50),
    source_id UUID,
    status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','posted','reversed')),
    created_by UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    posted_by UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    posted_at TIMESTAMPTZ,
    UNIQUE (company_id, entry_no)
);

CREATE TABLE journal_lines (
    journal_line_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    journal_entry_id UUID NOT NULL REFERENCES journal_entries(journal_entry_id) ON DELETE RESTRICT,
    account_id UUID NOT NULL REFERENCES chart_of_accounts(account_id) ON DELETE RESTRICT,
    site_id UUID REFERENCES client_sites(site_id) ON DELETE SET NULL,
    client_id UUID REFERENCES clients(client_id) ON DELETE SET NULL,
    debit NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (debit >= 0),
    credit NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (credit >= 0),
    description TEXT,
    CHECK ((debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0))
);

CREATE TABLE bank_transactions (
    bank_transaction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    bank_account_label VARCHAR(120) NOT NULL,
    transaction_date DATE NOT NULL,
    reference_no VARCHAR(120),
    description TEXT,
    amount NUMERIC(14,2) NOT NULL,
    reconciled BOOLEAN NOT NULL DEFAULT FALSE,
    reconciled_at TIMESTAMPTZ,
    matched_journal_entry_id UUID REFERENCES journal_entries(journal_entry_id) ON DELETE SET NULL
);

CREATE TABLE tds_records (
    tds_record_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    party_type VARCHAR(20) NOT NULL CHECK (party_type IN ('client','vendor','employee','other')),
    party_reference UUID,
    financial_year VARCHAR(9) NOT NULL,
    section_code VARCHAR(20),
    taxable_amount NUMERIC(14,2) NOT NULL CHECK (taxable_amount >= 0),
    tds_amount NUMERIC(14,2) NOT NULL CHECK (tds_amount >= 0),
    deducted_on DATE,
    deposited_on DATE,
    challan_reference VARCHAR(100),
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','deducted','deposited','filed'))
);

-- 12. Optional fleet management
CREATE TABLE fleet_vehicles (
    vehicle_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    branch_id UUID REFERENCES branches(branch_id) ON DELETE SET NULL,
    registration_no VARCHAR(30) NOT NULL,
    vehicle_type VARCHAR(60) NOT NULL,
    make_model VARCHAR(120),
    assigned_driver_employee_id UUID REFERENCES employees(employee_id) ON DELETE SET NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active','maintenance','retired')),
    UNIQUE (company_id, registration_no)
);

CREATE TABLE vehicle_logs (
    vehicle_log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vehicle_id UUID NOT NULL REFERENCES fleet_vehicles(vehicle_id) ON DELETE RESTRICT,
    employee_id UUID REFERENCES employees(employee_id) ON DELETE SET NULL,
    log_type VARCHAR(30) NOT NULL CHECK (log_type IN ('trip','fuel','maintenance','gps')),
    logged_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    odometer_km NUMERIC(12,2) CHECK (odometer_km IS NULL OR odometer_km >= 0),
    quantity NUMERIC(12,3) CHECK (quantity IS NULL OR quantity >= 0),
    amount NUMERIC(14,2) CHECK (amount IS NULL OR amount >= 0),
    latitude NUMERIC(10,7),
    longitude NUMERIC(10,7),
    details JSONB NOT NULL DEFAULT '{}'::jsonb
);

-- 13. Notifications, approvals, audit and integrations
CREATE TABLE notifications (
    notification_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    user_id UUID REFERENCES app_users(user_id) ON DELETE CASCADE,
    channel VARCHAR(20) NOT NULL CHECK (channel IN ('in_app','sms','whatsapp','email')),
    event_type VARCHAR(80) NOT NULL,
    subject VARCHAR(200),
    message TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(20) NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued','sent','delivered','failed','read')),
    scheduled_at TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE approval_requests (
    approval_request_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    workflow_type VARCHAR(80) NOT NULL,
    entity_type VARCHAR(80) NOT NULL,
    entity_id UUID NOT NULL,
    requested_by UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    assigned_to UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','approved','rejected','cancelled')),
    requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    decided_at TIMESTAMPTZ,
    decision_note TEXT
);

CREATE TABLE audit_logs (
    audit_log_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id UUID REFERENCES companies(company_id) ON DELETE SET NULL,
    actor_user_id UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    action VARCHAR(40) NOT NULL,
    entity_type VARCHAR(100) NOT NULL,
    entity_id TEXT,
    old_values JSONB,
    new_values JSONB,
    ip_address INET,
    user_agent TEXT,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE integration_events (
    integration_event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    integration_name VARCHAR(100) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    external_reference VARCHAR(200),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','processing','succeeded','failed','retry')),
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at TIMESTAMPTZ
);

-- Useful indexes
CREATE INDEX idx_leads_company_status ON leads(company_id, status);
CREATE INDEX idx_clients_company_status ON clients(company_id, status);
CREATE INDEX idx_sites_client_status ON client_sites(client_id, operational_status);
CREATE INDEX idx_contracts_client_status ON contracts(client_id, status);
CREATE INDEX idx_contracts_end_date ON contracts(end_date) WHERE end_date IS NOT NULL;
CREATE INDEX idx_employee_status_branch ON employees(company_id, branch_id, employment_status);
CREATE INDEX idx_employee_docs_expiry ON employee_documents(expiry_date) WHERE expiry_date IS NOT NULL;
CREATE INDEX idx_checks_employee_status ON employee_checks(employee_id, status);
CREATE INDEX idx_assignments_date_site ON shift_assignments(duty_date, site_post_id, status);
CREATE INDEX idx_attendance_employee_date ON attendance_records(employee_id, duty_date);
CREATE INDEX idx_attendance_site_date ON attendance_records(site_id, duty_date);
CREATE INDEX idx_attendance_approval ON attendance_records(approval_status, duty_date);
CREATE INDEX idx_patrol_rounds_site_status ON patrol_rounds(site_id, status, planned_start);
CREATE INDEX idx_incidents_site_occurred ON incidents(site_id, occurred_at DESC);
CREATE INDEX idx_tickets_client_status ON client_tickets(client_id, status);
CREATE INDEX idx_payroll_run_period ON payroll_runs(company_id, period_start, period_end);
CREATE INDEX idx_compliance_due_date ON compliance_obligations(due_date, status);
CREATE INDEX idx_licences_expiry ON agency_licences(valid_until) WHERE valid_until IS NOT NULL;
CREATE INDEX idx_invoices_client_due ON client_invoices(client_id, due_date, status);
CREATE INDEX idx_invoices_company_date ON client_invoices(company_id, invoice_date);
CREATE INDEX idx_client_payments_date ON client_payments(client_id, payment_date);
CREATE INDEX idx_inventory_tx_item_location_date ON inventory_transactions(item_id, location_id, transaction_at);
CREATE INDEX idx_expenses_company_date ON expenses(company_id, expense_date);
CREATE INDEX idx_journal_entries_company_date ON journal_entries(company_id, entry_date);
CREATE INDEX idx_audit_entity ON audit_logs(entity_type, entity_id, occurred_at DESC);
CREATE INDEX idx_notifications_user_status ON notifications(user_id, status, created_at DESC);

-- Starter roles are data, not schema. Seed permissions and roles in a separate controlled migration.
-- Application must validate company/branch consistency across related records.
-- Additional production work: RLS policies (if using Supabase), immutable posted accounting entries,
-- payroll/statutory calculation rules, invoice totals, journal balancing, stock balance derivation,
-- retention policies, encrypted PII handling, and integration retry/idempotency.

COMMIT;
