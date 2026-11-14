-- ==============================================================================
-- MODULE 8: INCIDENT AND REQUEST MANAGEMENT DATABASE SCHEMA (PostgreSQL)
-- Schema: security_erp
-- Scale: 200-500 guards, expandable
-- Context: Karnataka, India Security Agency Operations
-- ==============================================================================

SET search_path TO security_erp, public;

-- Drop existing Module 8 tables / legacy stubs cleanly
DROP TABLE IF EXISTS incident_client_versions CASCADE;
DROP TABLE IF EXISTS incident_follow_up_tasks CASCADE;
DROP TABLE IF EXISTS incident_timelines CASCADE;
DROP TABLE IF EXISTS incident_addendums CASCADE;
DROP TABLE IF EXISTS incident_attachments CASCADE;
DROP TABLE IF EXISTS incident_details CASCADE;
DROP TABLE IF EXISTS incident_contexts CASCADE;
DROP TABLE IF EXISTS incidents CASCADE;
DROP TABLE IF EXISTS client_ticket_messages CASCADE;
DROP TABLE IF EXISTS client_tickets CASCADE;
DROP TABLE IF EXISTS guard_request_replies CASCADE;
DROP TABLE IF EXISTS guard_requests CASCADE;
DROP TABLE IF EXISTS resolution_outcomes CASCADE;
DROP TABLE IF EXISTS guard_request_types CASCADE;
DROP TABLE IF EXISTS incident_categories CASCADE;
DROP TABLE IF EXISTS case_number_sequences CASCADE;

-- ------------------------------------------------------------------------------
-- 1. Configuration & Taxonomy Tables
-- ------------------------------------------------------------------------------

-- 1.1 Incident Categories (Configurable by Admin, supports sensitive flagging)
CREATE TABLE IF NOT EXISTS incident_categories (
    category_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    code VARCHAR(50) NOT NULL,
    description TEXT,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    sensitive BOOLEAN NOT NULL DEFAULT FALSE,
    sharing_policy VARCHAR(30) NOT NULL DEFAULT 'EXPLICIT_ONLY' 
        CHECK (sharing_policy IN ('AUTOMATIC_AFTER_REVIEW', 'EXPLICIT_ONLY', 'NEVER')),
    default_severity VARCHAR(20) NOT NULL DEFAULT 'MEDIUM' 
        CHECK (default_severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_incident_categories_code UNIQUE (company_id, code)
);

CREATE INDEX IF NOT EXISTS idx_incident_categories_active ON incident_categories (company_id, active);
CREATE INDEX IF NOT EXISTS idx_incident_categories_sensitive ON incident_categories (company_id, sensitive);

-- 1.2 Guard Request Types (Configurable operational request types)
CREATE TABLE IF NOT EXISTS guard_request_types (
    request_type_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    code VARCHAR(50) NOT NULL,
    description TEXT,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    cost_related BOOLEAN NOT NULL DEFAULT FALSE,
    admin_approval_required BOOLEAN NOT NULL DEFAULT FALSE,
    default_response_hours INTEGER NOT NULL DEFAULT 4,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_guard_request_types_code UNIQUE (company_id, code)
);

CREATE INDEX IF NOT EXISTS idx_guard_request_types_active ON guard_request_types (company_id, active);

-- 1.3 Resolution Outcomes (Documented outcomes for closure)
CREATE TABLE IF NOT EXISTS resolution_outcomes (
    outcome_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    code VARCHAR(50) NOT NULL,
    description TEXT,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_resolution_outcomes_code UNIQUE (company_id, code)
);

-- 1.4 Case Number Sequences (Atomic human-readable case numbering)
CREATE TABLE IF NOT EXISTS case_number_sequences (
    sequence_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    record_type VARCHAR(30) NOT NULL CHECK (record_type IN ('INCIDENT', 'REQUEST', 'TICKET', 'PANIC')),
    prefix VARCHAR(10) NOT NULL,
    current_year INTEGER NOT NULL,
    last_number INTEGER NOT NULL DEFAULT 0,
    last_generated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_case_number_sequences UNIQUE (company_id, record_type, current_year)
);

-- ------------------------------------------------------------------------------
-- 2. Incidents & Associated Entities
-- ------------------------------------------------------------------------------

-- 2.1 Core Incidents Table
CREATE TABLE IF NOT EXISTS incidents (
    incident_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    case_number VARCHAR(60) NOT NULL,
    client_generated_id UUID NOT NULL,
    guard_id UUID NOT NULL REFERENCES employees(employee_id) ON DELETE RESTRICT,
    assignment_id UUID REFERENCES roster_assignments(assignment_id) ON DELETE SET NULL,
    site_id UUID NOT NULL REFERENCES client_sites(site_id) ON DELETE RESTRICT,
    supervisor_id UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    category_id UUID NOT NULL REFERENCES incident_categories(category_id) ON DELETE RESTRICT,
    original_category_id UUID NOT NULL REFERENCES incident_categories(category_id) ON DELETE RESTRICT,
    current_category_id UUID NOT NULL REFERENCES incident_categories(category_id) ON DELETE RESTRICT,
    original_severity VARCHAR(20) NOT NULL CHECK (original_severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    current_severity VARCHAR(20) NOT NULL CHECK (current_severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    description TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    device_time TIMESTAMPTZ NOT NULL,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    server_received_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reported_outside_duty BOOLEAN NOT NULL DEFAULT FALSE,
    verification_state VARCHAR(40) NOT NULL DEFAULT 'REPORTED_NOT_VERIFIED'
        CHECK (verification_state IN ('REPORTED_NOT_VERIFIED', 'SUPERVISOR_REVIEWED', 'REJECTED_AS_INVALID')),
    status VARCHAR(30) NOT NULL DEFAULT 'REPORTED'
        CHECK (status IN ('REPORTED', 'ACKNOWLEDGED', 'IN_PROGRESS', 'ESCALATED', 'RESOLVED', 'CLOSED', 'REOPENED', 'REJECTED_AS_INVALID')),
    is_sensitive BOOLEAN NOT NULL DEFAULT FALSE,
    linked_case_id UUID REFERENCES incidents(incident_id) ON DELETE SET NULL,
    resolution_outcome_id UUID REFERENCES resolution_outcomes(outcome_id) ON DELETE SET NULL,
    resolution_note TEXT,
    resolution_action_taken TEXT,
    follow_up_required BOOLEAN NOT NULL DEFAULT FALSE,
    follow_up_due_at TIMESTAMPTZ,
    admin_reviewed BOOLEAN NOT NULL DEFAULT FALSE,
    admin_reviewed_by UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    admin_reviewed_at TIMESTAMPTZ,
    reopen_reason TEXT,
    rejection_reason TEXT,
    escalation_reason TEXT,
    escalated_at TIMESTAMPTZ,
    acknowledged_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    panic_event_reference UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_incidents_company_case UNIQUE (company_id, case_number),
    CONSTRAINT uq_incidents_client_id UNIQUE (company_id, guard_id, client_generated_id)
);

CREATE INDEX IF NOT EXISTS idx_incidents_company_status ON incidents (company_id, status);
CREATE INDEX IF NOT EXISTS idx_incidents_site_occurred ON incidents (site_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_incidents_guard_created ON incidents (guard_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_incidents_supervisor ON incidents (supervisor_id, status);
CREATE INDEX IF NOT EXISTS idx_incidents_severity ON incidents (current_severity);
CREATE INDEX IF NOT EXISTS idx_incidents_case_number ON incidents (case_number);

-- 2.2 Incident Context (Captured telemetry context - not a precise fix)
CREATE TABLE IF NOT EXISTS incident_contexts (
    context_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID NOT NULL UNIQUE REFERENCES incidents(incident_id) ON DELETE CASCADE,
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    site_id UUID NOT NULL REFERENCES client_sites(site_id) ON DELETE RESTRICT,
    assignment_id UUID REFERENCES roster_assignments(assignment_id) ON DELETE SET NULL,
    guard_id UUID NOT NULL REFERENCES employees(employee_id) ON DELETE RESTRICT,
    supervisor_id UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    server_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    device_time TIMESTAMPTZ,
    latitude NUMERIC(10, 7),
    longitude NUMERIC(10, 7),
    accuracy_m NUMERIC(8, 2),
    position_captured_at TIMESTAMPTZ,
    position_age_seconds INTEGER,
    position_source VARCHAR(50),
    location_label VARCHAR(100) NOT NULL DEFAULT 'Evidence context, not a precise fix',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 2.3 Incident Details (Optional structured particulars)
CREATE TABLE IF NOT EXISTS incident_details (
    detail_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID NOT NULL UNIQUE REFERENCES incidents(incident_id) ON DELETE CASCADE,
    people_involved TEXT,
    vehicle_numbers TEXT,
    witnesses TEXT,
    injuries TEXT,
    police_informed BOOLEAN NOT NULL DEFAULT FALSE,
    police_reference VARCHAR(100),
    property_damage TEXT,
    action_taken TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 2.4 Incident Attachments (In-app captured media with SHA-256 integrity verification)
CREATE TABLE IF NOT EXISTS incident_attachments (
    attachment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID NOT NULL REFERENCES incidents(incident_id) ON DELETE CASCADE,
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    uploaded_by UUID NOT NULL REFERENCES app_users(user_id) ON DELETE RESTRICT,
    source_type VARCHAR(30) NOT NULL CHECK (source_type IN ('GUARD_CAPTURED', 'SUPERVISOR_ADDED', 'CLIENT_SUPPLIED')),
    media_type VARCHAR(20) NOT NULL CHECK (media_type IN ('PHOTO', 'VIDEO')),
    file_reference TEXT NOT NULL,
    thumbnail_reference TEXT,
    original_file_name VARCHAR(255),
    file_size_bytes BIGINT NOT NULL,
    duration_seconds INTEGER,
    original_hash VARCHAR(64) NOT NULL,
    uploaded_hash VARCHAR(64),
    verification_state VARCHAR(30) NOT NULL DEFAULT 'PENDING'
        CHECK (verification_state IN ('PENDING', 'VERIFIED', 'FAILED_VERIFICATION')),
    upload_state VARCHAR(30) NOT NULL DEFAULT 'PENDING'
        CHECK (upload_state IN ('PENDING', 'UPLOADING', 'SYNCED', 'FAILED')),
    captured_at TIMESTAMPTZ,
    uploaded_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_incident_attachments_incident ON incident_attachments (incident_id);

-- 2.5 Incident Addendums (Append-only post-submission clarifications)
CREATE TABLE IF NOT EXISTS incident_addendums (
    addendum_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID NOT NULL REFERENCES incidents(incident_id) ON DELETE CASCADE,
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    author_id UUID NOT NULL REFERENCES app_users(user_id) ON DELETE RESTRICT,
    content TEXT NOT NULL,
    client_generated_id UUID NOT NULL,
    device_time TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sync_state VARCHAR(20) NOT NULL DEFAULT 'SYNCED' CHECK (sync_state IN ('PENDING', 'SYNCED', 'FAILED')),
    CONSTRAINT uq_incident_addendums_client UNIQUE (incident_id, client_generated_id)
);

CREATE INDEX IF NOT EXISTS idx_incident_addendums_incident ON incident_addendums (incident_id, created_at ASC);

-- 2.6 Incident Timelines (Immutable, append-only audit trail)
CREATE TABLE IF NOT EXISTS incident_timelines (
    timeline_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID NOT NULL REFERENCES incidents(incident_id) ON DELETE CASCADE,
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    actor_id UUID NOT NULL REFERENCES app_users(user_id) ON DELETE RESTRICT,
    action_type VARCHAR(50) NOT NULL,
    previous_value TEXT,
    new_value TEXT,
    description TEXT,
    audit_reference VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_incident_timelines_incident ON incident_timelines (incident_id, created_at ASC);

-- 2.7 Incident Follow-Up Tasks
CREATE TABLE IF NOT EXISTS incident_follow_up_tasks (
    task_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID NOT NULL REFERENCES incidents(incident_id) ON DELETE CASCADE,
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    assigned_to UUID NOT NULL REFERENCES app_users(user_id) ON DELETE RESTRICT,
    created_by UUID NOT NULL REFERENCES app_users(user_id) ON DELETE RESTRICT,
    description TEXT NOT NULL,
    due_at TIMESTAMPTZ NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED')),
    completed_at TIMESTAMPTZ,
    completion_note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_incident_tasks_assigned_due ON incident_follow_up_tasks (assigned_to, due_at);

-- 2.8 Client Shared Incident Versions (Redacted, approved summary for Client Portal)
CREATE TABLE IF NOT EXISTS incident_client_versions (
    version_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID NOT NULL REFERENCES incidents(incident_id) ON DELETE CASCADE,
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    client_id UUID NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
    site_id UUID NOT NULL REFERENCES client_sites(site_id) ON DELETE RESTRICT,
    title VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    summary TEXT NOT NULL,
    actions_taken TEXT NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'UNDER_REVIEW'
        CHECK (status IN ('UNDER_REVIEW', 'INVESTIGATING', 'RESOLVED', 'CLOSED')),
    approved_by UUID NOT NULL REFERENCES app_users(user_id) ON DELETE RESTRICT,
    approved_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sharing_state VARCHAR(20) NOT NULL DEFAULT 'SHARED'
        CHECK (sharing_state IN ('NOT_SHARED', 'SHARED', 'WITHDRAWN')),
    selected_attachment_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    version_number INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_client_versions_client_site ON incident_client_versions (client_id, site_id, occurred_at DESC);

-- ------------------------------------------------------------------------------
-- 3. Guard Requests & Replies
-- ------------------------------------------------------------------------------

-- 3.1 Guard Requests
CREATE TABLE IF NOT EXISTS guard_requests (
    request_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    request_number VARCHAR(60) NOT NULL,
    client_generated_id UUID NOT NULL,
    guard_id UUID NOT NULL REFERENCES employees(employee_id) ON DELETE RESTRICT,
    site_id UUID NOT NULL REFERENCES client_sites(site_id) ON DELETE RESTRICT,
    assignment_id UUID REFERENCES roster_assignments(assignment_id) ON DELETE SET NULL,
    request_type_id UUID NOT NULL REFERENCES guard_request_types(request_type_id) ON DELETE RESTRICT,
    description TEXT NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'SUBMITTED'
        CHECK (status IN ('SUBMITTED', 'ACKNOWLEDGED', 'APPROVED', 'REJECTED', 'IN_PROGRESS', 'FULFILLED', 'CANCELLED_BY_GUARD')),
    assigned_to UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    cost_related BOOLEAN NOT NULL DEFAULT FALSE,
    admin_approval_required BOOLEAN NOT NULL DEFAULT FALSE,
    admin_approved_by UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    admin_approved_at TIMESTAMPTZ,
    rejection_reason TEXT,
    fulfillment_note TEXT,
    response_due_at TIMESTAMPTZ,
    module5_reference UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_guard_requests_company_number UNIQUE (company_id, request_number),
    CONSTRAINT uq_guard_requests_client_id UNIQUE (company_id, guard_id, client_generated_id)
);

CREATE INDEX IF NOT EXISTS idx_guard_requests_company_status ON guard_requests (company_id, status);
CREATE INDEX IF NOT EXISTS idx_guard_requests_guard ON guard_requests (guard_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_guard_requests_site ON guard_requests (site_id);

-- 3.2 Guard Request Replies (All replies visible to guard)
CREATE TABLE IF NOT EXISTS guard_request_replies (
    reply_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID NOT NULL REFERENCES guard_requests(request_id) ON DELETE CASCADE,
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    actor_id UUID NOT NULL REFERENCES app_users(user_id) ON DELETE RESTRICT,
    message TEXT NOT NULL,
    visibility VARCHAR(20) NOT NULL DEFAULT 'GUARD_VISIBLE' CHECK (visibility IN ('GUARD_VISIBLE', 'INTERNAL')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_guard_replies_request ON guard_request_replies (request_id, created_at ASC);

-- ------------------------------------------------------------------------------
-- 4. Client Tickets & Messages
-- ------------------------------------------------------------------------------

-- 4.1 Client Tickets
CREATE TABLE IF NOT EXISTS client_tickets (
    ticket_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    ticket_number VARCHAR(60) NOT NULL,
    client_generated_id UUID NOT NULL,
    client_id UUID NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
    site_id UUID NOT NULL REFERENCES client_sites(site_id) ON DELETE RESTRICT,
    ticket_type VARCHAR(30) NOT NULL
        CHECK (ticket_type IN ('COMPLAINT', 'FEEDBACK', 'QUERY', 'OBSERVED_ISSUE', 'EXTRA_GUARDS')),
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    named_guard_id UUID REFERENCES employees(employee_id) ON DELETE SET NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'OPEN'
        CHECK (status IN ('OPEN', 'ACKNOWLEDGED', 'IN_PROGRESS', 'WAITING_FOR_CLIENT', 'RESOLVED', 'CLOSED', 'REOPENED')),
    assigned_to UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    is_admin_only BOOLEAN NOT NULL DEFAULT FALSE,
    response_due_at TIMESTAMPTZ,
    resolution_due_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    resolution_note TEXT,
    reopened_count INTEGER NOT NULL DEFAULT 0,
    reopened_at TIMESTAMPTZ,
    reopen_reason TEXT,
    module4_reference UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_client_tickets_company_number UNIQUE (company_id, ticket_number),
    CONSTRAINT uq_client_tickets_client_id UNIQUE (company_id, client_id, client_generated_id)
);

CREATE INDEX IF NOT EXISTS idx_client_tickets_client ON client_tickets (client_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_client_tickets_site ON client_tickets (site_id);
CREATE INDEX IF NOT EXISTS idx_client_tickets_status ON client_tickets (status);
CREATE INDEX IF NOT EXISTS idx_client_tickets_admin_only ON client_tickets (company_id, is_admin_only);

-- 4.2 Client Ticket Messages (Strict separation between client-visible & internal notes)
CREATE TABLE IF NOT EXISTS client_ticket_messages (
    message_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id UUID NOT NULL REFERENCES client_tickets(ticket_id) ON DELETE CASCADE,
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    actor_id UUID NOT NULL REFERENCES app_users(user_id) ON DELETE RESTRICT,
    message TEXT NOT NULL,
    visibility VARCHAR(20) NOT NULL DEFAULT 'CLIENT_VISIBLE'
        CHECK (visibility IN ('CLIENT_VISIBLE', 'INTERNAL')),
    attachment_reference TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ticket_messages_ticket ON client_ticket_messages (ticket_id, created_at ASC);

-- ------------------------------------------------------------------------------
-- 5. Atomic Case Number Generator Function
-- ------------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION generate_case_number(
    p_company_id UUID,
    p_record_type VARCHAR,
    p_prefix VARCHAR
) RETURNS VARCHAR AS $$
DECLARE
    v_year INTEGER := EXTRACT(YEAR FROM CURRENT_DATE)::INTEGER;
    v_next_val INTEGER;
    v_formatted VARCHAR(60);
BEGIN
    INSERT INTO case_number_sequences (company_id, record_type, prefix, current_year, last_number, last_generated_at)
    VALUES (p_company_id, p_record_type, p_prefix, v_year, 1, CURRENT_TIMESTAMP)
    ON CONFLICT (company_id, record_type, current_year)
    DO UPDATE SET 
        last_number = case_number_sequences.last_number + 1,
        last_generated_at = CURRENT_TIMESTAMP
    RETURNING last_number INTO v_next_val;

    v_formatted := p_prefix || '-' || v_year::VARCHAR || '-' || LPAD(v_next_val::VARCHAR, 5, '0');
    RETURN v_formatted;
END;
$$ LANGUAGE plpgsql;

-- ------------------------------------------------------------------------------
-- 6. Default Starter Seed Data for Module 8 (Per Company Triggered)
-- ------------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION seed_module8_company_defaults(p_company_id UUID) RETURNS VOID AS $$
BEGIN
    -- Seed Starter Categories (PRD Section 11.13)
    INSERT INTO incident_categories (company_id, name, code, description, sensitive, sharing_policy, default_severity)
    VALUES
        (p_company_id, 'Theft & Pilferage', 'THEFT', 'Attempted or confirmed theft on site', FALSE, 'EXPLICIT_ONLY', 'HIGH'),
        (p_company_id, 'Trespassing & Unauthorized Access', 'TRESPASS', 'Intrusion or perimeter breach', FALSE, 'AUTOMATIC_AFTER_REVIEW', 'MEDIUM'),
        (p_company_id, 'Fire & Smoke Hazard', 'FIRE', 'Fire incident or smoke alarm trigger', FALSE, 'AUTOMATIC_AFTER_REVIEW', 'CRITICAL'),
        (p_company_id, 'Medical Emergency', 'MEDICAL', 'Injury, fainting, or acute medical incident', FALSE, 'EXPLICIT_ONLY', 'HIGH'),
        (p_company_id, 'Physical Altercation', 'ALTERCATION', 'Physical fight or verbal dispute with threat', FALSE, 'EXPLICIT_ONLY', 'HIGH'),
        (p_company_id, 'Suspicious Activity', 'SUSPICIOUS_ACTIVITY', 'Loitering, surveillance by strangers', FALSE, 'AUTOMATIC_AFTER_REVIEW', 'LOW'),
        (p_company_id, 'Vandalism & Property Damage', 'VANDALISM', 'Damage to gates, cameras, or facilities', FALSE, 'AUTOMATIC_AFTER_REVIEW', 'MEDIUM'),
        (p_company_id, 'Equipment Failure', 'EQUIPMENT_FAILURE', 'Boom barrier, scanner, CCTV, or torch failure', FALSE, 'AUTOMATIC_AFTER_REVIEW', 'LOW'),
        (p_company_id, 'Safety Hazard', 'SAFETY_HAZARD', 'Water leak, exposed wiring, slippery floor', FALSE, 'AUTOMATIC_AFTER_REVIEW', 'LOW'),
        (p_company_id, 'Client Staff Complaint', 'CLIENT_STAFF_CONCERN', 'Dispute or concern involving client personnel', TRUE, 'NEVER', 'HIGH'),
        (p_company_id, 'Weapon Related Incident', 'WEAPON_RELATED', 'Presence or unholstering of arms or sharp weapon', TRUE, 'NEVER', 'CRITICAL'),
        (p_company_id, 'Supervisor Conduct Issue', 'SUPERVISOR_CONDUCT', 'Concern or grievance regarding supervisor actions', TRUE, 'NEVER', 'HIGH'),
        (p_company_id, 'Other Occurrence', 'OTHER', 'Uncategorized operational occurrence', FALSE, 'EXPLICIT_ONLY', 'MEDIUM')
    ON CONFLICT (company_id, code) DO NOTHING;

    -- Seed Guard Request Types (PRD Section 6.7 & 11.14)
    INSERT INTO guard_request_types (company_id, name, code, description, cost_related, admin_approval_required, default_response_hours)
    VALUES
        (p_company_id, 'Relief / Cover Replacement', 'RELIEF_COVER', 'Urgent relief needed during active duty shift', FALSE, FALSE, 1),
        (p_company_id, 'Equipment / Battery / Torch', 'EQUIPMENT_SUPPLIES', 'Duty equipment replenishment or replacement', FALSE, FALSE, 4),
        (p_company_id, 'Uniform Replacement', 'UNIFORM_ISSUE', 'Damaged or missing uniform components', TRUE, TRUE, 24),
        (p_company_id, 'Site Maintenance Hazard', 'SITE_MAINTENANCE', 'Facility or booth repair needed', FALSE, FALSE, 8),
        (p_company_id, 'Safety Concern', 'SAFETY_CONCERN', 'Personal safety hazard at duty post', FALSE, FALSE, 2),
        (p_company_id, 'Welfare & Drinking Water', 'WELFARE_PERSONAL', 'Drinking water, shelter, sanitation needs', FALSE, FALSE, 2),
        (p_company_id, 'General Request', 'OTHER', 'Other operational request', FALSE, FALSE, 12)
    ON CONFLICT (company_id, code) DO NOTHING;

    -- Seed Resolution Outcomes (PRD Section 11.15)
    INSERT INTO resolution_outcomes (company_id, name, code, description)
    VALUES
        (p_company_id, 'Resolved - Action Completed', 'ACTION_COMPLETED', 'All corrective and immediate actions were taken successfully'),
        (p_company_id, 'Resolved - False Alarm / No Breach', 'FALSE_ALARM', 'Investigated and confirmed as false alarm or benign trigger'),
        (p_company_id, 'Resolved - Escalated to Client Security', 'ESCALATED_CLIENT', 'Handed over to client facility security team'),
        (p_company_id, 'Resolved - Police FIR / Complaint Filed', 'POLICE_COMPLAINT', 'Formal police report / Station Diary entry recorded'),
        (p_company_id, 'Resolved - Equipment Repaired / Replaced', 'EQUIPMENT_RESOLVED', 'Faulty equipment replaced or serviced'),
        (p_company_id, 'Closed - Administrative Closure', 'ADMIN_CLOSED', 'Closed after executive review')
    ON CONFLICT (company_id, code) DO NOTHING;
END;
$$ LANGUAGE plpgsql;
