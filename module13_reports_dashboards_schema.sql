-- ==============================================================================
-- Module 13: Reports and Dashboards Schema
-- Security Agency Management and Monitoring System (SGIMS)
-- Target Schema: security_erp
-- PostgreSQL 18 Compatible | Tamper-Evident Reporting, Metrics & Audit Integration
-- ==============================================================================

SET search_path TO security_erp, public;

-- Drop existing Module 13 tables if any
DROP TABLE IF EXISTS security_erp.summary_invalidations CASCADE;
DROP TABLE IF EXISTS security_erp.report_reconciliations CASCADE;
DROP TABLE IF EXISTS security_erp.client_monthly_summaries CASCADE;
DROP TABLE IF EXISTS security_erp.report_generation_records CASCADE;
DROP TABLE IF EXISTS security_erp.saved_filter_presets CASCADE;
DROP TABLE IF EXISTS security_erp.summary_snapshots CASCADE;
DROP TABLE IF EXISTS security_erp.metric_definition_versions CASCADE;
DROP TABLE IF EXISTS security_erp.metric_definitions CASCADE;
DROP TABLE IF EXISTS security_erp.report_definitions CASCADE;

-- ------------------------------------------------------------------------------
-- 1. REPORT DEFINITIONS (PRD Section 9, FR-13.21)
-- Fixed catalogue of 20 authoritative reports
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.report_definitions (
    report_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES security_erp.companies(company_id) ON DELETE RESTRICT,
    report_number INT NOT NULL,
    code VARCHAR(50) NOT NULL,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    category VARCHAR(50) NOT NULL CHECK (category IN (
        'MANPOWER', 'ATTENDANCE', 'GUARDS', 'INCIDENTS', 'MONITORING', 
        'PANIC', 'SALES', 'BILLING', 'ARMED', 'AUDIT', 'CLIENT_PORTAL'
    )),
    audience VARCHAR(50) NOT NULL CHECK (audience IN ('ADMIN_ONLY', 'ADMIN_SUPERVISOR', 'CLIENT_SAFE')),
    sensitivity VARCHAR(50) NOT NULL DEFAULT 'INTERNAL' CHECK (sensitivity IN (
        'INTERNAL', 'PERSONAL', 'SENSITIVE', 'HIGHLY_SENSITIVE', 'COMMERCIAL', 'FINANCIAL', 'CLIENT_CONFIDENTIAL'
    )),
    export_formats TEXT[] NOT NULL DEFAULT '{"CSV", "PDF"}',
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_report_def_company_code UNIQUE (company_id, code)
);

CREATE INDEX IF NOT EXISTS idx_report_def_company ON security_erp.report_definitions(company_id);
CREATE INDEX IF NOT EXISTS idx_report_def_code ON security_erp.report_definitions(code);

-- ------------------------------------------------------------------------------
-- 2. METRIC DEFINITIONS (PRD Section 7, FR-13.14 to FR-13.20)
-- Central metric dictionary (M01 to M81)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.metric_definitions (
    metric_id VARCHAR(10) PRIMARY KEY, -- 'M01' through 'M81'
    company_id UUID REFERENCES security_erp.companies(company_id) ON DELETE RESTRICT,
    name VARCHAR(150) NOT NULL,
    definition TEXT NOT NULL,
    formula TEXT NOT NULL,
    numerator_desc TEXT,
    denominator_desc TEXT,
    source_module VARCHAR(10) NOT NULL,
    source_fields TEXT NOT NULL,
    period_basis VARCHAR(50) NOT NULL,
    inclusion_rules TEXT,
    exclusion_rules TEXT,
    manual_offline_handling TEXT,
    unit VARCHAR(50) NOT NULL,
    rounding_rule VARCHAR(50) NOT NULL DEFAULT '2_DECIMALS',
    visibility VARCHAR(50) NOT NULL DEFAULT 'ADMIN_SUPERVISOR' CHECK (visibility IN ('ADMIN_ONLY', 'ADMIN_SUPERVISOR', 'CLIENT_SAFE')),
    current_version INT NOT NULL DEFAULT 1,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_metric_def_company ON security_erp.metric_definitions(company_id);
CREATE INDEX IF NOT EXISTS idx_metric_def_visibility ON security_erp.metric_definitions(visibility);

-- ------------------------------------------------------------------------------
-- 3. METRIC DEFINITION VERSIONS (PRD 7.12, FR-13.17 to FR-13.19)
-- Preserves version history so past reports remain auditable
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.metric_definition_versions (
    version_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_id VARCHAR(10) NOT NULL REFERENCES security_erp.metric_definitions(metric_id) ON DELETE CASCADE,
    version_number INT NOT NULL,
    effective_date DATE NOT NULL DEFAULT CURRENT_DATE,
    changed_by_user_id UUID REFERENCES security_erp.app_users(user_id) ON DELETE SET NULL,
    definition_snapshot JSONB NOT NULL,
    change_reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_metric_version UNIQUE (metric_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_metric_ver_metric ON security_erp.metric_definition_versions(metric_id);

-- ------------------------------------------------------------------------------
-- 4. SUMMARY SNAPSHOTS (PRD 13.2, FR-13.37, FR-13.39)
-- Cached summary calculations with data quality notes
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.summary_snapshots (
    summary_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES security_erp.companies(company_id) ON DELETE RESTRICT,
    metric_id VARCHAR(10) NOT NULL REFERENCES security_erp.metric_definitions(metric_id) ON DELETE CASCADE,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    site_id UUID REFERENCES security_erp.client_sites(site_id) ON DELETE CASCADE,
    client_id UUID REFERENCES security_erp.clients(client_id) ON DELETE CASCADE,
    filters JSONB NOT NULL DEFAULT '{}'::jsonb,
    calculated_value NUMERIC(15, 2),
    data_quality_notes JSONB NOT NULL DEFAULT '{}'::jsonb,
    as_of_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_valid BOOLEAN NOT NULL DEFAULT TRUE,
    definition_version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_summary_snap_company ON security_erp.summary_snapshots(company_id);
CREATE INDEX IF NOT EXISTS idx_summary_snap_metric ON security_erp.summary_snapshots(metric_id);
CREATE INDEX IF NOT EXISTS idx_summary_snap_period ON security_erp.summary_snapshots(period_start, period_end);
CREATE INDEX IF NOT EXISTS idx_summary_snap_site ON security_erp.summary_snapshots(site_id);

-- ------------------------------------------------------------------------------
-- 5. SAVED FILTER PRESETS (PRD 11.1 Screen 3, FR-13.28)
-- Reusable filter configurations per user
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.saved_filter_presets (
    preset_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES security_erp.companies(company_id) ON DELETE RESTRICT,
    user_id UUID NOT NULL REFERENCES security_erp.app_users(user_id) ON DELETE CASCADE,
    report_code VARCHAR(50) NOT NULL,
    name VARCHAR(100) NOT NULL,
    filter_params JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_filter_presets_user ON security_erp.saved_filter_presets(user_id);
CREATE INDEX IF NOT EXISTS idx_filter_presets_report ON security_erp.saved_filter_presets(report_code);

-- ------------------------------------------------------------------------------
-- 6. REPORT GENERATION RECORDS (PRD 6.6, 6.7, FR-13.49 to FR-13.62)
-- Tracks async jobs, completed exports, audit references, and content hashes
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.report_generation_records (
    job_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES security_erp.companies(company_id) ON DELETE RESTRICT,
    user_id UUID NOT NULL REFERENCES security_erp.app_users(user_id) ON DELETE CASCADE,
    report_code VARCHAR(50) NOT NULL,
    filters JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(30) NOT NULL DEFAULT 'COMPLETED' CHECK (status IN ('PENDING', 'GENERATING', 'COMPLETED', 'FAILED')),
    as_of_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    definition_versions JSONB NOT NULL DEFAULT '{}'::jsonb,
    content_hash VARCHAR(64),
    row_count INT NOT NULL DEFAULT 0,
    file_format VARCHAR(10) NOT NULL CHECK (file_format IN ('CSV', 'PDF')),
    file_path TEXT,
    file_size_bytes BIGINT DEFAULT 0,
    error_message TEXT,
    bulk_reason TEXT,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_rep_gen_company ON security_erp.report_generation_records(company_id);
CREATE INDEX IF NOT EXISTS idx_rep_gen_user ON security_erp.report_generation_records(user_id);
CREATE INDEX IF NOT EXISTS idx_rep_gen_status ON security_erp.report_generation_records(status);

-- ------------------------------------------------------------------------------
-- 7. CLIENT MONTHLY SUMMARIES (PRD 6.5, 12.7, FR-13.40 to FR-13.48)
-- Multi-version, immutable released summaries for Client Portal (Module 10)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.client_monthly_summaries (
    summary_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES security_erp.companies(company_id) ON DELETE RESTRICT,
    client_id UUID NOT NULL REFERENCES security_erp.clients(client_id) ON DELETE RESTRICT,
    period_month INT NOT NULL CHECK (period_month BETWEEN 1 AND 12),
    period_year INT NOT NULL CHECK (period_year >= 2020),
    version_number INT NOT NULL DEFAULT 1,
    status VARCHAR(20) NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'RELEASED')),
    previous_version_id UUID REFERENCES security_erp.client_monthly_summaries(summary_id) ON DELETE SET NULL,
    summary_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    content_hash VARCHAR(64),
    generated_by_user_id UUID REFERENCES security_erp.app_users(user_id) ON DELETE SET NULL,
    released_by_user_id UUID REFERENCES security_erp.app_users(user_id) ON DELETE SET NULL,
    released_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_client_summary_version UNIQUE (client_id, period_month, period_year, version_number)
);

CREATE INDEX IF NOT EXISTS idx_client_sum_client ON security_erp.client_monthly_summaries(client_id);
CREATE INDEX IF NOT EXISTS idx_client_sum_status ON security_erp.client_monthly_summaries(status);

-- ------------------------------------------------------------------------------
-- 8. REPORT RECONCILIATIONS (PRD 6.4, 12.8, FR-13.37 to FR-13.39)
-- Detects discrepancies between summary snapshots and raw operational tables
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.report_reconciliations (
    reconciliation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES security_erp.companies(company_id) ON DELETE RESTRICT,
    metric_id VARCHAR(10) NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    expected_value NUMERIC(15, 2) NOT NULL,
    calculated_value NUMERIC(15, 2) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'MATCH' CHECK (status IN ('MATCH', 'MISMATCH', 'REPAIRED')),
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_reconciliation_company ON security_erp.report_reconciliations(company_id);
CREATE INDEX IF NOT EXISTS idx_reconciliation_status ON security_erp.report_reconciliations(status);

-- ------------------------------------------------------------------------------
-- 9. SUMMARY INVALIDATIONS (PRD 12.4, 14.4)
-- Records source-module changes that trigger report recalculation
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.summary_invalidations (
    invalidation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES security_erp.companies(company_id) ON DELETE RESTRICT,
    source_module VARCHAR(50) NOT NULL,
    source_record_id VARCHAR(100),
    affected_periods JSONB NOT NULL DEFAULT '[]'::jsonb,
    invalidation_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_processed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_invalidation_processed ON security_erp.summary_invalidations(is_processed);

-- ------------------------------------------------------------------------------
-- 10. SEED FUNCTION FOR MODULE 13 DEFAULTS
-- Populates 20 fixed reports, 81 metric definitions, and initial version snapshots
-- ------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION security_erp.seed_module13_company_defaults(comp_id UUID)
RETURNS VOID AS $$
DECLARE
    m_rec RECORD;
BEGIN
    -- 1. Seed Fixed Report Definitions (20 Reports from Section 9)
    INSERT INTO security_erp.report_definitions (
        company_id, report_number, code, name, description, category, audience, sensitivity, export_formats
    ) VALUES
    (comp_id, 1, 'MANPOWER_REQ', 'Manpower Strength vs Requirement', 'Compares authorized manpower requirements with filled posts, vacancies, and fill rate by site and shift.', 'MANPOWER', 'ADMIN_SUPERVISOR', 'INTERNAL', '{"CSV", "PDF"}'),
    (comp_id, 2, 'VACANCY_SHORTFALL', 'Vacancy and Shortfall Report', 'Tracks open vacancies, vacancy durations in days, and calculated site shortfalls.', 'MANPOWER', 'ADMIN_SUPERVISOR', 'INTERNAL', '{"CSV", "PDF"}'),
    (comp_id, 3, 'DAILY_DEPLOYMENT', 'Daily Deployment Sheet', 'Detailed daily post-by-post roster showing assigned guards, replacements, and deployment status.', 'MANPOWER', 'ADMIN_SUPERVISOR', 'INTERNAL', '{"CSV", "PDF"}'),
    (comp_id, 4, 'ATTENDANCE_SUMMARY', 'Attendance Summary', 'Comprehensive attendance totals, regular hours, manual entries, offline captures, and approval status.', 'ATTENDANCE', 'ADMIN_SUPERVISOR', 'PERSONAL', '{"CSV", "PDF"}'),
    (comp_id, 5, 'LATE_NOSHOW_EARLY', 'Late, No Show and Early Exit', 'Monitors punctual attendance metrics, tardiness minutes, early exits, and unexcused absences.', 'ATTENDANCE', 'ADMIN_SUPERVISOR', 'PERSONAL', '{"CSV", "PDF"}'),
    (comp_id, 6, 'OVERTIME_REPORT', 'Overtime Report', 'Approved overtime minutes and hours accrued per guard, site, and period.', 'ATTENDANCE', 'ADMIN_SUPERVISOR', 'PERSONAL', '{"CSV", "PDF"}'),
    (comp_id, 7, 'ATTENDANCE_FLAGS', 'Attendance Exceptions and Flags', 'Exception logs for geofence breaches, biometric mismatches, device discrepancies, and manual overrides.', 'ATTENDANCE', 'ADMIN_SUPERVISOR', 'PERSONAL', '{"CSV", "PDF"}'),
    (comp_id, 8, 'APPROVAL_TURNAROUND', 'Approval Turnaround and Pending Approvals', 'Measures supervisor attendance review efficiency, pending approval queues, and average decision latency.', 'ATTENDANCE', 'ADMIN_SUPERVISOR', 'INTERNAL', '{"CSV", "PDF"}'),
    (comp_id, 9, 'GUARD_ATTRITION', 'Guard Roster and Attrition', 'Agency-wide guard lifecycle tracking: active headcount, joiners, leavers, and turnover rate.', 'GUARDS', 'ADMIN_ONLY', 'PERSONAL', '{"CSV", "PDF"}'),
    (comp_id, 10, 'DOC_EXPIRY', 'Document, Training and Licence Expiry', 'Proactive compliance tracking for expiring PSARA badges, police verifications, medicals, and training gaps.', 'GUARDS', 'ADMIN_SUPERVISOR', 'PERSONAL', '{"CSV", "PDF"}'),
    (comp_id, 11, 'INCIDENT_SUMMARY', 'Incident Summary and Detail', 'Chronological and categorical incident logs, severity breakdowns, and authorized operational details.', 'INCIDENTS', 'ADMIN_SUPERVISOR', 'SENSITIVE', '{"CSV", "PDF"}'),
    (comp_id, 12, 'INCIDENT_TIMELINESS', 'Response and Resolution Time', 'SLA metrics for incident acknowledgement, resolution turnaround, overdue counts, and reopenings.', 'INCIDENTS', 'ADMIN_SUPERVISOR', 'INTERNAL', '{"CSV", "PDF"}'),
    (comp_id, 13, 'MONITORING_ALERTS', 'Alert and Monitoring Report', 'Live monitoring radar statistics, rule-based alerts, false alarm ratios, and patrol scan coverage.', 'MONITORING', 'ADMIN_SUPERVISOR', 'SENSITIVE', '{"CSV", "PDF"}'),
    (comp_id, 14, 'PANIC_RESPONSE', 'Panic Response Report', 'Emergency SOS response metrics, responder action timelines, delivery failures, and false alarms (excluding tests).', 'PANIC', 'ADMIN_SUPERVISOR', 'HIGHLY_SENSITIVE', '{"CSV", "PDF"}'),
    (comp_id, 15, 'QUOTATION_FUNNEL', 'Quotation Funnel', 'Commercial pipeline tracking: service requests received, quotes submitted, accepted, rejected, and conversion rate.', 'SALES', 'ADMIN_ONLY', 'COMMERCIAL', '{"CSV", "PDF"}'),
    (comp_id, 16, 'BILLING_SUMMARY', 'Billing Summary, Ageing and Collections', 'Accounts receivable register: billed totals, collected amounts, outstanding balances, and ageing buckets.', 'BILLING', 'ADMIN_ONLY', 'FINANCIAL', '{"CSV", "PDF"}'),
    (comp_id, 17, 'WEAPONS_AMMUNITION', 'Weapons and Ammunition Summary', 'Strictly confidential armoury audit: firearm custody, active issues, overdue returns, and ammunition balances.', 'ARMED', 'ADMIN_ONLY', 'HIGHLY_SENSITIVE', '{"CSV", "PDF"}'),
    (comp_id, 18, 'CLIENT_MONTHLY', 'Client Monthly Service Summary', 'Client-safe service delivery dossier: covered posts, coverage percentage, shared incidents, and resolved tickets.', 'CLIENT_PORTAL', 'CLIENT_SAFE', 'CLIENT_CONFIDENTIAL', '{"PDF"}'),
    (comp_id, 19, 'AUDIT_ACTIVITY', 'Audit Activity Report', 'Compliance trail from Module 1: administrative actions, role modifications, export requests, and system events.', 'AUDIT', 'ADMIN_ONLY', 'HIGHLY_SENSITIVE', '{"CSV", "PDF"}'),
    (comp_id, 20, 'CLIENT_PORTAL_USAGE', 'Client Portal Usage', 'Client engagement metrics: active client users, last login timestamps, and portal-originated tickets.', 'CLIENT_PORTAL', 'ADMIN_ONLY', 'PERSONAL', '{"CSV", "PDF"}')
    ON CONFLICT (company_id, code) DO NOTHING;

    -- 2. Seed Central Metric Dictionary (M01 to M81)
    INSERT INTO security_erp.metric_definitions (
        metric_id, company_id, name, definition, formula, numerator_desc, denominator_desc,
        source_module, source_fields, period_basis, inclusion_rules, exclusion_rules, manual_offline_handling, unit, rounding_rule, visibility
    ) VALUES
    -- Manpower Metrics (M01 - M11)
    ('M01', comp_id, 'Required Posts', 'Count of post slots required for the selected period.', 'COUNT(post_slots)', 'Active required post slots', NULL, 'M2/M5', 'site_manpower_requirements, post_slots', 'Duty Date', 'Include effective requirements', 'Exclude inactive requirements', 'N/A', 'Posts', 'INTEGER', 'ADMIN_SUPERVISOR'),
    ('M02', comp_id, 'Filled Posts', 'Count of required post slots with a valid active assignment.', 'COUNT(assignments WHERE status IN (CONFIRMED, COMPLETED))', 'Valid assignments', NULL, 'M5', 'roster_assignments.status', 'Duty Date', 'Active confirmed assignments', 'Exclude cancelled assignments', 'N/A', 'Posts', 'INTEGER', 'ADMIN_SUPERVISOR'),
    ('M03', comp_id, 'Fill Rate', 'Percentage of required post slots successfully filled.', '(Filled Posts / Required Posts) * 100', 'Filled Posts (M02)', 'Required Posts (M01)', 'M2/M5', 'Derived M01 & M02', 'Duty Date', 'Matching M01 & M02 filters', 'Exclude cancelled slots', 'N/A', 'Percentage', '2_DECIMALS', 'ADMIN_SUPERVISOR'),
    ('M04', comp_id, 'Vacancy Count', 'Count of required slots without a valid active assignment.', 'COUNT(unassigned post_slots)', 'Unfilled required slots', NULL, 'M5', 'post_slots.is_filled', 'Duty Date', 'Open slots within period', 'Exclude cancelled slots', 'N/A', 'Posts', 'INTEGER', 'ADMIN_SUPERVISOR'),
    ('M05', comp_id, 'Vacancy Days', 'Sum of calendar days each vacancy remains open within selected period.', 'SUM(open_days)', 'Total unfilled slot days', NULL, 'M5', 'post_slots.duty_date', 'Duty Date', 'Open vacancy dates', 'Exclude filled dates', 'N/A', 'Days', 'INTEGER', 'ADMIN_SUPERVISOR'),
    ('M06', comp_id, 'Shortfall', 'Required Posts minus Filled Posts (clamped to zero minimum).', 'GREATEST(0, Required Posts - Filled Posts)', 'Shortfall slots', NULL, 'M2/M5', 'Derived M01 & M02', 'Duty Date', 'Same as M03', 'Clamped at 0', 'N/A', 'Posts', 'INTEGER', 'ADMIN_SUPERVISOR'),
    ('M07', comp_id, 'Shortfall by Site', 'Sum of shortfall grouped by client site.', 'SUM(Shortfall) GROUP BY site_id', 'Site shortfall slots', NULL, 'M2/M5', 'site_id, post_slots', 'Duty Date', 'Active sites', 'Clamped at 0', 'N/A', 'Posts', 'INTEGER', 'ADMIN_SUPERVISOR'),
    ('M08', comp_id, 'Shortfall by Shift', 'Sum of shortfall grouped by shift template.', 'SUM(Shortfall) GROUP BY shift_id', 'Shift shortfall slots', NULL, 'M2/M5', 'shift_id, post_slots', 'Duty Date', 'Active shifts', 'Clamped at 0', 'N/A', 'Posts', 'INTEGER', 'ADMIN_SUPERVISOR'),
    ('M09', comp_id, 'Replacement Deployments', 'Count of replacement deployment records.', 'COUNT(replacement_deployments)', 'Replacement events', NULL, 'M5', 'roster_assignments.is_replacement', 'Deployment Date', 'Replacement flagged records', 'Exclude regular deployments', 'Preserved as replacement', 'Deployments', 'INTEGER', 'ADMIN_SUPERVISOR'),
    ('M10', comp_id, 'Emergency Deployments', 'Count of emergency deployment records.', 'COUNT(emergency_deployments)', 'Emergency deployments', NULL, 'M5', 'roster_assignments.is_emergency', 'Deployment Date', 'Emergency marked assignments', 'Exclude regular assignments', 'N/A', 'Deployments', 'INTEGER', 'ADMIN_SUPERVISOR'),
    ('M11', comp_id, 'Unfilled Slot Events', 'Count of unfilled slot exception events.', 'COUNT(unfilled_slot_events)', 'Unfilled events', NULL, 'M5', 'unfilled_slot_events', 'Event Date', 'Recorded shortfall events', 'N/A', 'N/A', 'Events', 'INTEGER', 'ADMIN_SUPERVISOR'),

    -- Attendance Metrics (M12 - M25)
    ('M12', comp_id, 'Attendance Rate', 'Percentage of scheduled assignments with confirmed attendance.', '(Attended Assignments / Eligible Assignments) * 100', 'Attended count', 'Eligible assignments', 'M5/M6', 'attendance_records.status', 'Duty Date', 'Approved and present records', 'Exclude excused leaves', 'Manual and Offline included', 'Percentage', '2_DECIMALS', 'ADMIN_SUPERVISOR'),
    ('M13', comp_id, 'Late Rate', 'Percentage of attendance records marked late.', '(Late Records / Total Attendance) * 100', 'Late records', 'Total attendance records', 'M6', 'attendance_records.is_late', 'Duty Date', 'Late flagged check-ins', 'Exclude on-time records', 'Labelled in breakdown', 'Percentage', '2_DECIMALS', 'ADMIN_SUPERVISOR'),
    ('M14', comp_id, 'No Show Rate', 'Percentage of scheduled assignments where guard did not report.', '(No Show Assignments / Eligible Assignments) * 100', 'No-show count', 'Total scheduled assignments', 'M5/M6', 'attendance_records.status = NO_SHOW', 'Duty Date', 'Explicit NO_SHOW records', 'Exclude approved leaves', 'N/A', 'Percentage', '2_DECIMALS', 'ADMIN_SUPERVISOR'),
    ('M15', comp_id, 'Early Exit Rate', 'Percentage of check-outs recorded before shift conclusion.', '(Early Exits / Total Check-outs) * 100', 'Early exit count', 'Total check-outs', 'M6', 'attendance_records.is_early_exit', 'Duty Date', 'Early departure records', 'Exclude on-time departures', 'N/A', 'Percentage', '2_DECIMALS', 'ADMIN_SUPERVISOR'),
    ('M16', comp_id, 'Manual Entry Share', 'Proportion of attendance entered manually by supervisor.', '(Manual Entries / Total Attendance) * 100', 'Manual attendance records', 'Total attendance records', 'M6', 'attendance_records.is_manual', 'Duty Date', 'Supervisor manual records', 'Exclude automated app punches', 'Explicitly tracked', 'Percentage', '2_DECIMALS', 'ADMIN_SUPERVISOR'),
    ('M17', comp_id, 'Offline Capture Share', 'Proportion of attendance captured while offline and synced later.', '(Offline Captures / Total Attendance) * 100', 'Offline captured records', 'Total attendance records', 'M6', 'attendance_records.is_offline', 'Duty Date', 'Offline sync records', 'Exclude real-time punches', 'Explicitly tracked', 'Percentage', '2_DECIMALS', 'ADMIN_SUPERVISOR'),
    ('M18', comp_id, 'Flagged Record Share', 'Proportion of attendance records triggering audit or compliance flags.', '(Flagged Records / Total Attendance) * 100', 'Flagged records', 'Total attendance records', 'M6', 'attendance_flags', 'Duty Date', 'Geofence/biometric/device flags', 'Exclude clean records', 'Flag details available', 'Percentage', '2_DECIMALS', 'ADMIN_SUPERVISOR'),
    ('M19', comp_id, 'Overtime Minutes', 'Sum of approved overtime minutes across all guards.', 'SUM(overtime_minutes)', 'Approved overtime minutes', NULL, 'M6', 'attendance_records.overtime_minutes', 'Duty Date', 'Approved overtime only', 'Exclude rejected/pending overtime', 'N/A', 'Minutes', 'INTEGER', 'ADMIN_SUPERVISOR'),
    ('M20', comp_id, 'Approval Turnaround', 'Average duration in minutes from attendance submission to approval.', 'AVG(EXTRACT(EPOCH FROM (approved_at - submitted_at))/60)', 'Approval latency sum', 'Approved record count', 'M6', 'attendance_records.approved_at', 'Approval Date', 'Approved records with timestamps', 'Exclude unapproved records', 'N/A', 'Minutes', '2_DECIMALS', 'ADMIN_SUPERVISOR'),
    ('M21', comp_id, 'Pending Approval Count', 'Count of attendance records currently awaiting review.', 'COUNT(attendance_records WHERE status = PENDING_APPROVAL)', 'Pending attendance rows', NULL, 'M6', 'attendance_records.status', 'Current', 'Unreviewed attendance records', 'Exclude approved/rejected records', 'N/A', 'Records', 'INTEGER', 'ADMIN_SUPERVISOR'),
    ('M22', comp_id, 'Periods Closed on Time', 'Percentage of payroll periods locked prior to statutory cut-off.', '(On-Time Closures / Total Periods) * 100', 'On-time period closures', 'Due periods', 'M6', 'attendance_periods.closed_at', 'Cut-off Date', 'Closed within cut-off', 'Exclude late closures', 'N/A', 'Percentage', '2_DECIMALS', 'ADMIN_ONLY'),
    ('M23', comp_id, 'Attendance Correction Count', 'Total number of post-hoc attendance regularisations and corrections.', 'COUNT(attendance_corrections)', 'Correction records', NULL, 'M6', 'attendance_regularisations', 'Correction Date', 'Approved corrections', 'Exclude unapproved regularisations', 'N/A', 'Corrections', 'INTEGER', 'ADMIN_SUPERVISOR'),
    ('M24', comp_id, 'Unlocked Period Count', 'Count of past attendance periods remaining in open or unlocked status.', 'COUNT(attendance_periods WHERE status != LOCKED AND end_date < CURRENT_DATE)', 'Overdue open periods', NULL, 'M6', 'attendance_periods.status', 'Current', 'Past due open periods', 'Exclude current active period', 'N/A', 'Periods', 'INTEGER', 'ADMIN_ONLY'),
    ('M25', comp_id, 'Late-Synced Attendance Count', 'Number of records synchronized more than 15 minutes post capture.', 'COUNT(attendance_records WHERE sync_delay > 15 mins)', 'Delayed sync records', NULL, 'M6', 'attendance_records.synced_at', 'Capture Date', 'Delay > 15 minutes', 'Exclude immediate syncs', 'N/A', 'Records', 'INTEGER', 'ADMIN_SUPERVISOR'),

    -- Guard Lifecycle & Compliance Metrics (M26 - M35)
    ('M26', comp_id, 'Total Guard Headcount', 'Total number of guards currently in the personnel registry.', 'COUNT(guards)', 'All guards in registry', NULL, 'M3', 'guards.status', 'As-of Date', 'All records regardless of status', 'N/A', 'N/A', 'Guards', 'INTEGER', 'ADMIN_SUPERVISOR'),
    ('M27', comp_id, 'Active Guards', 'Number of guards in ACTIVE lifecycle status.', 'COUNT(guards WHERE status = ACTIVE)', 'Active guards', NULL, 'M3', 'guards.status', 'As-of Date', 'Status ACTIVE', 'Exclude inactive/terminated', 'N/A', 'Guards', 'INTEGER', 'ADMIN_SUPERVISOR'),
    ('M28', comp_id, 'Joiners', 'Count of new guards enrolled during the selected period.', 'COUNT(guards WHERE date_of_joining IN PERIOD)', 'New joiner guards', NULL, 'M3', 'guards.date_of_joining', 'Selected Period', 'Joining date matches period', 'N/A', 'N/A', 'Guards', 'INTEGER', 'ADMIN_ONLY'),
    ('M29', comp_id, 'Leavers', 'Count of guards exited or terminated during the selected period.', 'COUNT(guards WHERE date_of_leaving IN PERIOD)', 'Exited guards', NULL, 'M3', 'guards.date_of_leaving', 'Selected Period', 'Leaving date matches period', 'N/A', 'N/A', 'Guards', 'INTEGER', 'ADMIN_ONLY'),
    ('M30', comp_id, 'Attrition Rate', 'Proportion of departures relative to active headcount.', '(Leavers / Average Headcount) * 100', 'Leavers (M29)', 'Active Headcount', 'M3', 'Derived M27 & M29', 'Selected Period', 'Standard turnover formula', 'Needs confirmation if avg', 'N/A', 'Percentage', '2_DECIMALS', 'ADMIN_ONLY'),
    ('M31', comp_id, 'Deployable Share', 'Percentage of active guards who are verified and eligible for shift duty.', '(Deployable Guards / Active Guards) * 100', 'Deployable guards', 'Active guards (M27)', 'M3', 'guards.is_deployable', 'As-of Date', 'Fully verified and compliant', 'Exclude blocked/unverified', 'N/A', 'Percentage', '2_DECIMALS', 'ADMIN_SUPERVISOR'),
    ('M32', comp_id, 'Documents Expiring in N Days', 'Count of guard credentials expiring within the alert window (default 30d).', 'COUNT(documents WHERE expiry BETWEEN NOW() AND NOW() + 30d)', 'Expiring credentials', NULL, 'M3', 'guard_documents.expiry_date', 'As-of Date', 'Active documents in window', 'Exclude already expired', 'N/A', 'Documents', 'INTEGER', 'ADMIN_SUPERVISOR'),
    ('M33', comp_id, 'Expired Guard Documents', 'Total count of guard documents past expiration that lack a verified renewal.', 'COUNT(documents WHERE expiry_date < NOW())', 'Expired credentials', NULL, 'M3', 'guard_documents.expiry_date', 'As-of Date', 'Overdue expired documents', 'Exclude renewed documents', 'N/A', 'Documents', 'INTEGER', 'ADMIN_SUPERVISOR'),
    ('M34', comp_id, 'Training Gaps', 'Guards missing mandatory fire-safety, unarmed combat, or site induction training.', 'COUNT(guards missing required training certifications)', 'Guards with training deficits', NULL, 'M3', 'guard_trainings', 'As-of Date', 'Mandatory missing modules', 'N/A', 'N/A', 'Guards', 'INTEGER', 'ADMIN_SUPERVISOR'),
    ('M35', comp_id, 'Guards with Unavailability', 'Number of guards with an approved leave or unavailability record.', 'COUNT(unavailability_records overlapping date)', 'Unavailable guards', NULL, 'M3', 'guard_unavailability', 'Selected Date', 'Approved leave / sickness', 'Exclude rejected requests', 'N/A', 'Guards', 'INTEGER', 'ADMIN_SUPERVISOR'),

    -- Incident & Request Metrics (M36 - M44)
    ('M36', comp_id, 'Incident Count', 'Total number of recorded operational incidents.', 'COUNT(incidents)', 'All incident events', NULL, 'M8', 'incidents.id', 'Reported Date', 'Valid incident records', 'Exclude deleted records', 'N/A', 'Incidents', 'INTEGER', 'ADMIN_SUPERVISOR'),
    ('M37', comp_id, 'Incident Acknowledgement Time', 'Average minutes from incident reporting to supervisor triage.', 'AVG(EXTRACT(EPOCH FROM (acknowledged_at - reported_at))/60)', 'Triage delay sum', 'Acknowledged incidents', 'M8', 'incidents.acknowledged_at', 'Reported Date', 'Incidents with triage timestamp', 'Exclude unacknowledged', 'N/A', 'Minutes', '2_DECIMALS', 'ADMIN_SUPERVISOR'),
    ('M38', comp_id, 'Incident Resolution Time', 'Average hours required to bring an incident to final closure.', 'AVG(EXTRACT(EPOCH FROM (resolved_at - reported_at))/3600)', 'Resolution hours sum', 'Resolved incidents', 'M8', 'incidents.resolved_at', 'Reported Date', 'Closed and resolved cases', 'Exclude open cases', 'N/A', 'Hours', '2_DECIMALS', 'ADMIN_SUPERVISOR'),
    ('M39', comp_id, 'Overdue Incident Share', 'Percentage of open incidents exceeding SLA resolution deadlines.', '(Overdue Incidents / Open Incidents) * 100', 'Overdue open incidents', 'Total open incidents', 'M8', 'incidents.sla_deadline', 'As-of Date', 'Past SLA deadline', 'Exclude resolved incidents', 'N/A', 'Percentage', '2_DECIMALS', 'ADMIN_SUPERVISOR'),
    ('M40', comp_id, 'Reopened Incident Share', 'Percentage of closed incidents subsequently reopened due to recurring issues.', '(Reopened Incidents / Resolved Incidents) * 100', 'Reopened incidents', 'Total resolved incidents', 'M8', 'incidents.is_reopened', 'Selected Period', 'Reopen flag TRUE', 'Exclude clean closures', 'N/A', 'Percentage', '2_DECIMALS', 'ADMIN_SUPERVISOR'),
    ('M41', comp_id, 'Guard Request Count', 'Number of formal requests lodged by guards (uniform, shift swap, equipment).', 'COUNT(guard_requests)', 'Total guard requests', NULL, 'M8', 'guard_requests.id', 'Created Date', 'All registered requests', 'N/A', 'N/A', 'Requests', 'INTEGER', 'ADMIN_SUPERVISOR'),
    ('M42', comp_id, 'Guard Request Fulfilment Time', 'Average hours to fulfill and close an internal guard request.', 'AVG(EXTRACT(EPOCH FROM (fulfilled_at - created_at))/3600)', 'Fulfilment hours sum', 'Fulfilled requests', 'M8', 'guard_requests.fulfilled_at', 'Created Date', 'Fulfilled requests only', 'Exclude pending requests', 'N/A', 'Hours', '2_DECIMALS', 'ADMIN_SUPERVISOR'),
    ('M43', comp_id, 'Client Ticket Count', 'Count of concerns or queries submitted by client representatives.', 'COUNT(client_tickets)', 'Total client tickets', NULL, 'M8', 'client_tickets.id', 'Created Date', 'Portal-originated tickets', 'N/A', 'N/A', 'Tickets', 'INTEGER', 'ADMIN_SUPERVISOR'),
    ('M44', comp_id, 'Client Ticket Resolution Time', 'Average hours to address and resolve client tickets.', 'AVG(EXTRACT(EPOCH FROM (resolved_at - created_at))/3600)', 'Resolution hours sum', 'Resolved tickets', 'M8', 'client_tickets.resolved_at', 'Created Date', 'Resolved tickets only', 'Exclude pending tickets', 'N/A', 'Hours', '2_DECIMALS', 'ADMIN_SUPERVISOR'),

    -- Monitoring & Panic Metrics (M45 - M54)
    ('M45', comp_id, 'Monitoring Alert Count', 'Total automated sensor or geofence alerts generated.', 'COUNT(monitoring_alerts)', 'Total alert events', NULL, 'M7', 'alerts.id', 'Alert Date', 'System generated alerts', 'N/A', 'N/A', 'Alerts', 'INTEGER', 'ADMIN_SUPERVISOR'),
    ('M46', comp_id, 'Monitoring Acknowledgement Time', 'Average minutes for command centre operators to respond to an alert.', 'AVG(EXTRACT(EPOCH FROM (acknowledged_at - created_at))/60)', 'Operator response sum', 'Acknowledged alerts', 'M7', 'alerts.acknowledged_at', 'Alert Date', 'Acknowledged events', 'Exclude ignored alerts', 'N/A', 'Minutes', '2_DECIMALS', 'ADMIN_SUPERVISOR'),
    ('M47', comp_id, 'False Alarm Share', 'Proportion of alerts confirmed as false triggers upon investigation.', '(False Alarms / Resolved Alerts) * 100', 'False alarm alerts', 'Total resolved alerts', 'M7', 'alerts.is_false_alarm', 'Alert Date', 'Classified FALSE_ALARM', 'Exclude true emergencies', 'N/A', 'Percentage', '2_DECIMALS', 'ADMIN_SUPERVISOR'),
    ('M48', comp_id, 'Tracking Coverage', 'Proportion of active duty minutes with healthy telemetry pings.', '(Tracked Duty Minutes / Scheduled Duty Minutes) * 100', 'Live GPS active minutes', 'Scheduled duty minutes', 'M7', 'telemetry_pings', 'Duty Date', 'Ping within freshness threshold', 'Coordinates withheld', 'Preserves privacy', 'Percentage', '2_DECIMALS', 'ADMIN_SUPERVISOR'),
    ('M49', comp_id, 'Consent Not Given Count', 'Count of deployed guards missing active telemetry/tracking consent.', 'COUNT(guards lacking active consent_records)', 'Guards lacking consent', NULL, 'M1', 'consent_records', 'As-of Date', 'Deployed without valid consent', 'Exclude signed consents', 'N/A', 'Guards', 'INTEGER', 'ADMIN_ONLY'),
    ('M50', comp_id, 'Real Panic Count', 'Count of authentic SOS distress alerts (strictly excluding test drills).', 'COUNT(panic_alerts WHERE is_test = FALSE)', 'Real panic emergencies', NULL, 'M9', 'panic_alerts.is_test', 'Alert Date', 'Real emergency panics only', 'Strictly exclude test drills', 'N/A', 'Alerts', 'INTEGER', 'ADMIN_SUPERVISOR'),
    ('M51', comp_id, 'Panic First Acknowledgement Time', 'Average minutes to first human or operator acknowledgement of an SOS.', 'AVG(EXTRACT(EPOCH FROM (acknowledged_at - created_at))/60)', 'Distress latency sum', 'Acknowledged real alerts', 'M9', 'panic_alerts.acknowledged_at', 'Alert Date', 'Real alerts with timestamp', 'Exclude test records', 'N/A', 'Minutes', '2_DECIMALS', 'ADMIN_SUPERVISOR'),
    ('M52', comp_id, 'Panic Resolution Time', 'Average minutes to disarm, escalate, and resolve an active SOS situation.', 'AVG(EXTRACT(EPOCH FROM (resolved_at - created_at))/60)', 'Resolution duration sum', 'Resolved real alerts', 'M9', 'panic_alerts.resolved_at', 'Alert Date', 'Resolved real alerts', 'Exclude test records', 'N/A', 'Minutes', '2_DECIMALS', 'ADMIN_SUPERVISOR'),
    ('M53', comp_id, 'Panic False Alarm Share', 'Percentage of genuine SOS alerts verified as accidental or false alarms.', '(False Panic Alarms / Resolved Real Panics) * 100', 'Accidental SOS triggers', 'Total real panic alerts', 'M9', 'panic_alerts.outcome', 'Alert Date', 'Classified ACCIDENTAL/FALSE', 'Exclude test records', 'N/A', 'Percentage', '2_DECIMALS', 'ADMIN_SUPERVISOR'),
    ('M54', comp_id, 'Delivery Failure Rate by Route', 'Percentage of automated SMS/Push dispatch attempts that timed out or failed.', '(Failed Dispatches / Total Dispatch Attempts) * 100', 'Failed notification dispatches', 'Total dispatch attempts', 'M9', 'panic_deliveries.status', 'Alert Date', 'Status FAILED/TIMEOUT', 'Exclude successful deliveries', 'N/A', 'Percentage', '2_DECIMALS', 'ADMIN_ONLY'),

    -- Commercial & Sales Metrics (M55 - M62)
    ('M55', comp_id, 'Service Requests Received', 'Total commercial RFPs and inbound security service inquiries.', 'COUNT(service_requests)', 'Inbound service requests', NULL, 'M4', 'service_requests.id', 'Received Date', 'All unique requests', 'N/A', 'N/A', 'Requests', 'INTEGER', 'ADMIN_ONLY'),
    ('M56', comp_id, 'Quotes Sent', 'Formal cost sheets and quotation proposals dispatched to clients.', 'COUNT(quotation_versions WHERE status = SENT)', 'Dispatched quotes', NULL, 'M4', 'quotation_versions.status', 'Sent Date', 'Sent quotation versions', 'Exclude internal drafts', 'N/A', 'Quotes', 'INTEGER', 'ADMIN_ONLY'),
    ('M57', comp_id, 'Accepted Quotes', 'Proposals formally accepted and converted into client contracts.', 'COUNT(quotations WHERE status = ACCEPTED)', 'Accepted proposals', NULL, 'M4', 'quotations.status', 'Acceptance Date', 'Status ACCEPTED', 'Exclude rejected/pending', 'N/A', 'Quotes', 'INTEGER', 'ADMIN_ONLY'),
    ('M58', comp_id, 'Rejected Quotes', 'Proposals declined by prospective or existing clients.', 'COUNT(quotations WHERE status = REJECTED)', 'Declined proposals', NULL, 'M4', 'quotations.status', 'Rejection Date', 'Status REJECTED', 'Exclude active quotes', 'N/A', 'Quotes', 'INTEGER', 'ADMIN_ONLY'),
    ('M59', comp_id, 'Countered Quotes', 'Quotations returned by clients requesting commercial revisions or rate negotiations.', 'COUNT(quotations WHERE status = COUNTERED)', 'Negotiated quotes', NULL, 'M4', 'quotations.status', 'Event Date', 'Status COUNTERED', 'N/A', 'N/A', 'Quotes', 'INTEGER', 'ADMIN_ONLY'),
    ('M60', comp_id, 'Expired Quotes', 'Proposals that exceeded their 30-day validity window without acceptance.', 'COUNT(quotations WHERE status = EXPIRED)', 'Lapsed quotes', NULL, 'M4', 'quotations.status', 'Expiry Date', 'Status EXPIRED', 'N/A', 'N/A', 'Quotes', 'INTEGER', 'ADMIN_ONLY'),
    ('M61', comp_id, 'Quote Conversion Rate', 'Percentage of submitted quotations that successfully converted to contracts.', '(Accepted Quotes / (Accepted + Rejected Quotes)) * 100', 'Accepted quotes (M57)', 'Final outcome quotes', 'M4', 'Derived M57 & M58', 'Outcome Date', 'Final decision proposals', 'Exclude pending quotes', 'N/A', 'Percentage', '2_DECIMALS', 'ADMIN_ONLY'),
    ('M62', comp_id, 'Time to First Response', 'Average turnaround in hours from service inquiry receipt to initial quotation.', 'AVG(EXTRACT(EPOCH FROM (first_response_at - received_at))/3600)', 'Response hours sum', 'Responded requests', 'M4', 'service_requests.first_response_at', 'Received Date', 'Requests with quote logged', 'Exclude pending requests', 'N/A', 'Hours', '2_DECIMALS', 'ADMIN_ONLY'),

    -- Billing & Invoicing Metrics (M63 - M69)
    ('M63', comp_id, 'Billed Amount', 'Total INR value of officially issued client tax invoices (excluding drafts).', 'SUM(total_amount WHERE status != DRAFT)', 'Issued invoice sums', NULL, 'M11', 'client_invoices.total_amount', 'Invoice Date', 'Officially issued invoices', 'Strictly exclude drafts', 'N/A', 'INR', '2_DECIMALS', 'ADMIN_ONLY'),
    ('M64', comp_id, 'Collected Amount', 'Total payments received and reconciled against issued invoices.', 'SUM(payment_amount)', 'Reconciled collections', NULL, 'M11', 'client_payments.amount', 'Payment Date', 'Cleared payments', 'Exclude bounced/reversed', 'N/A', 'INR', '2_DECIMALS', 'ADMIN_ONLY'),
    ('M65', comp_id, 'Outstanding Amount', 'Total unpaid balance on currently active issued invoices.', 'SUM(balance_due WHERE status IN (ISSUED, PARTIALLY_PAID, OVERDUE))', 'Unpaid balances', NULL, 'M11', 'client_invoices.balance_due', 'As-of Date', 'Open balances', 'Exclude cancelled/drafts', 'N/A', 'INR', '2_DECIMALS', 'ADMIN_ONLY'),
    ('M66', comp_id, 'Overdue Amount', 'Outstanding invoice balance that has exceeded credit period due dates.', 'SUM(balance_due WHERE due_date < CURRENT_DATE AND status != PAID)', 'Overdue balances', NULL, 'M11', 'client_invoices.balance_due', 'As-of Date', 'Past due date', 'Exclude on-time invoices', 'N/A', 'INR', '2_DECIMALS', 'ADMIN_ONLY'),
    ('M67', comp_id, 'Invoice Count by Status', 'Distribution of invoices across DRAFT, ISSUED, PAID, OVERDUE, CANCELLED.', 'COUNT(invoices) GROUP BY status', 'Count by status', NULL, 'M11', 'client_invoices.status', 'Invoice Date', 'All records', 'N/A', 'N/A', 'Invoices', 'INTEGER', 'ADMIN_ONLY'),
    ('M68', comp_id, 'Ageing Bucket Amount', 'Accounts receivable categorized into 0-30, 31-60, 61-90, and 90+ day overdue brackets.', 'SUM(balance_due) GROUP BY ageing_bucket', 'Bucket balances', NULL, 'M11', 'client_invoices.due_date', 'As-of Date', 'Open invoices with due dates', 'Exclude drafts', 'N/A', 'INR', '2_DECIMALS', 'ADMIN_ONLY'),
    ('M69', comp_id, 'Invoices Under Query', 'Count of issued invoices disputed or questioned by client billing teams.', 'COUNT(invoices WHERE has_active_query = TRUE)', 'Invoices under query', NULL, 'M11', 'client_invoices.has_query', 'As-of Date', 'Disputed invoices', 'Exclude clean invoices', 'N/A', 'Invoices', 'INTEGER', 'ADMIN_ONLY'),

    -- Armed Guard & Armoury Metrics (M70 - M78)
    ('M70', comp_id, 'Weapons by Status', 'Armoury inventory count grouped by ACTIVE, IN_MAINTENANCE, DECOMMISSIONED.', 'COUNT(weapons) GROUP BY status', 'Count by status', NULL, 'M12', 'weapons.status', 'As-of Date', 'All registered firearms', 'Serials masked', 'Masked output', 'Weapons', 'INTEGER', 'ADMIN_ONLY'),
    ('M71', comp_id, 'Current Weapon Issues', 'Count of firearms currently checked out into active guard custody.', 'COUNT(weapon_transfers WHERE status = ACTIVE)', 'Active custody assignments', NULL, 'M12', 'weapon_transfers.status', 'As-of Date', 'Active checked-out weapons', 'Exclude vault inventory', 'N/A', 'Issues', 'INTEGER', 'ADMIN_ONLY'),
    ('M72', comp_id, 'Overdue Weapon Returns', 'Checked-out weapons that have exceeded shift conclusion without vault check-in.', 'COUNT(active transfers WHERE expected_return < NOW())', 'Overdue returns', NULL, 'M12', 'weapon_transfers.expected_return_at', 'As-of Date', 'Past return deadline', 'Exclude returned weapons', 'N/A', 'Issues', 'INTEGER', 'ADMIN_ONLY'),
    ('M73', comp_id, 'Open Weapon Discrepancies', 'Unresolved serial, quantity, or damage discrepancies noted in armoury logs.', 'COUNT(weapon_discrepancies WHERE status = OPEN)', 'Unresolved discrepancies', NULL, 'M12', 'weapon_discrepancies.status', 'As-of Date', 'Status OPEN', 'Exclude resolved issues', 'N/A', 'Discrepancies', 'INTEGER', 'ADMIN_ONLY'),
    ('M74', comp_id, 'Weapon Variances', 'Discrepancies identified during monthly physical stock count verifications.', 'COUNT(stock_variances WHERE variance != 0)', 'Discrepant stock counts', NULL, 'M12', 'ammunition_stock_counts.variance', 'Audit Date', 'Non-zero variances', 'Exclude reconciled counts', 'N/A', 'Variances', 'INTEGER', 'ADMIN_ONLY'),
    ('M75', comp_id, 'Licences Due', 'Agency or guard firearm licences expiring within the 60-day renewal threshold.', 'COUNT(licences WHERE valid_until BETWEEN NOW() AND NOW() + 60d)', 'Expiring licences', NULL, 'M12', 'weapon_licences.valid_until', 'As-of Date', 'Expiring within 60 days', 'Exclude expired/suspended', 'N/A', 'Licences', 'INTEGER', 'ADMIN_ONLY'),
    ('M76', comp_id, 'Inspections Due', 'Weapons due for statutory armourer cleaning and safety inspections.', 'COUNT(weapons WHERE next_inspection_due <= NOW())', 'Weapons requiring inspection', NULL, 'M12', 'weapon_maintenance_logs.next_due', 'As-of Date', 'Inspection past due date', 'Exclude freshly certified', 'N/A', 'Inspections', 'INTEGER', 'ADMIN_ONLY'),
    ('M77', comp_id, 'Ammunition Balance', 'Current verified round count per caliber (.32, 12 Bore, .315) across all armouries.', 'SUM(current_stock) GROUP BY caliber', 'Caliber round balance', NULL, 'M12', 'ammunition_lots.quantity_available', 'As-of Date', 'Verified ammunition lots', 'Exclude expended rounds', 'No tactical details', 'Quantity', 'INTEGER', 'ADMIN_ONLY'),
    ('M78', comp_id, 'Armed Posts Without a Weapon', 'Deployment slots designated armed where no linked weapon asset is logged.', 'COUNT(armed_assignments lacking linked weapon)', 'Unarmed armed posts', NULL, 'M2/M5/M12', 'roster_assignments.weapon_id', 'Duty Date', 'Armed posts with null weapon', 'Exclude unarmed posts', 'N/A', 'Posts', 'INTEGER', 'ADMIN_ONLY'),

    -- Client Portal Metrics (M79 - M81)
    ('M79', comp_id, 'Active Client Users', 'Client stakeholder accounts that have signed in within the past 30 days.', 'COUNT(client_users WHERE last_login > NOW() - 30d)', 'Active client stakeholders', NULL, 'M1/M10', 'app_users.last_login', 'As-of Date', 'Client users logged in <=30d', 'Exclude inactive accounts', 'N/A', 'Users', 'INTEGER', 'ADMIN_ONLY'),
    ('M80', comp_id, 'Last Client Login', 'Timestamp of the most recent portal session for each client organization.', 'MAX(last_login) GROUP BY client_id', 'Latest login timestamp', NULL, 'M1/M10', 'app_users.last_login', 'As-of Date', 'Client accounts', 'Privacy preserved', 'N/A', 'Timestamp', 'DATETIME', 'ADMIN_ONLY'),
    ('M81', comp_id, 'Portal Tickets Raised', 'Service queries or incident reports submitted digitally through Module 10.', 'COUNT(client_tickets WHERE channel = PORTAL)', 'Digital client tickets', NULL, 'M8/M10', 'client_tickets.channel', 'Created Date', 'Channel = PORTAL', 'Exclude phone/email tickets', 'N/A', 'Tickets', 'INTEGER', 'ADMIN_ONLY')
    ON CONFLICT (metric_id) DO NOTHING;

    -- 3. Seed Initial Metric Definition Versions (Version 1 snapshots)
    FOR m_rec IN SELECT metric_id, name, definition, formula, source_module, unit, visibility FROM security_erp.metric_definitions LOOP
        INSERT INTO security_erp.metric_definition_versions (
            metric_id, version_number, effective_date, definition_snapshot, change_reason
        ) VALUES (
            m_rec.metric_id, 1, CURRENT_DATE, 
            json_build_object(
                'metric_id', m_rec.metric_id,
                'name', m_rec.name,
                'definition', m_rec.definition,
                'formula', m_rec.formula,
                'source_module', m_rec.source_module,
                'unit', m_rec.unit,
                'visibility', m_rec.visibility
            ),
            'Initial baseline metric definition (Module 13 v1.0 release)'
        )
        ON CONFLICT (metric_id, version_number) DO NOTHING;
    END LOOP;

END;
$$ LANGUAGE plpgsql;
