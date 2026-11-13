-- ==============================================================================
-- MODULE 6: ATTENDANCE SCHEMA
-- Security Agency Management and Monitoring System (Karnataka, India)
-- Schema: security_erp
-- ==============================================================================

SET search_path TO security_erp, public;

-- Drop obsolete or empty legacy table
DROP TABLE IF EXISTS attendance_records CASCADE;
DROP TABLE IF EXISTS attendance_periods CASCADE;
DROP TABLE IF EXISTS attendance_captures CASCADE;
DROP TABLE IF EXISTS attendance_evidence CASCADE;
DROP TABLE IF EXISTS attendance_flags CASCADE;
DROP TABLE IF EXISTS attendance_revisions CASCADE;
DROP TABLE IF EXISTS attendance_regularisations CASCADE;
DROP TABLE IF EXISTS attendance_approvals CASCADE;
DROP TABLE IF EXISTS attendance_period_exceptions CASCADE;
DROP TABLE IF EXISTS attendance_handovers CASCADE;
DROP TABLE IF EXISTS manual_attendance_counters CASCADE;

-- 1. ATTENDANCE PERIODS (Monthly Period Lock & Reopen)
CREATE TABLE attendance_periods (
    period_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    site_id UUID NULL REFERENCES client_sites(site_id) ON DELETE CASCADE,
    period_name VARCHAR(50) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    cut_off_day INTEGER NOT NULL DEFAULT 25,
    status VARCHAR(20) NOT NULL DEFAULT 'open', -- 'open', 'locked', 'reopened'
    closed_by UUID NULL REFERENCES app_users(user_id) ON DELETE SET NULL,
    closed_at TIMESTAMPTZ NULL,
    reopened_by UUID NULL REFERENCES app_users(user_id) ON DELETE SET NULL,
    reopened_at TIMESTAMPTZ NULL,
    reopen_reason TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_attendance_periods_company_dates ON attendance_periods(company_id, start_date, end_date);

-- 2. ATTENDANCE RECORDS (One per assignment per duty date)
CREATE TABLE attendance_records (
    attendance_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    assignment_id UUID NULL REFERENCES roster_assignments(assignment_id) ON DELETE SET NULL,
    employee_id UUID NOT NULL REFERENCES employees(employee_id) ON DELETE CASCADE,
    site_id UUID NOT NULL REFERENCES client_sites(site_id) ON DELETE CASCADE,
    shift_id UUID NOT NULL REFERENCES site_shifts(shift_id) ON DELETE CASCADE,
    duty_date DATE NOT NULL,
    scheduled_start TIMESTAMPTZ NOT NULL,
    scheduled_end TIMESTAMPTZ NOT NULL,
    actual_check_in TIMESTAMPTZ NULL,
    actual_check_out TIMESTAMPTZ NULL,
    late_minutes INTEGER NOT NULL DEFAULT 0,
    early_exit_minutes INTEGER NOT NULL DEFAULT 0,
    worked_minutes INTEGER NOT NULL DEFAULT 0,
    regular_minutes INTEGER NOT NULL DEFAULT 0,
    overtime_minutes INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(30) NOT NULL DEFAULT 'scheduled',
    -- 'scheduled', 'in_progress', 'completed', 'late', 'absent', 'no_checkout', 'pending_approval', 'approved', 'rejected', 'corrected'
    is_manual BOOLEAN NOT NULL DEFAULT FALSE,
    is_offline BOOLEAN NOT NULL DEFAULT FALSE,
    is_unscheduled BOOLEAN NOT NULL DEFAULT FALSE,
    period_id UUID NULL REFERENCES attendance_periods(period_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX uq_attendance_assignment_duty_date
    ON attendance_records(assignment_id, duty_date)
    WHERE assignment_id IS NOT NULL;

CREATE INDEX idx_attendance_records_site_date ON attendance_records(site_id, duty_date);
CREATE INDEX idx_attendance_records_employee_date ON attendance_records(employee_id, duty_date);
CREATE INDEX idx_attendance_records_status ON attendance_records(status);

-- 3. ATTENDANCE CAPTURES (Raw physical mobile captures - Check In / Check Out)
CREATE TABLE attendance_captures (
    capture_id UUID PRIMARY KEY, -- Client-generated UUID for idempotency
    attendance_id UUID NULL REFERENCES attendance_records(attendance_id) ON DELETE CASCADE,
    assignment_id UUID NULL REFERENCES roster_assignments(assignment_id) ON DELETE SET NULL,
    employee_id UUID NOT NULL REFERENCES employees(employee_id) ON DELETE CASCADE,
    capture_type VARCHAR(20) NOT NULL, -- 'CHECK_IN', 'CHECK_OUT'
    device_time TIMESTAMPTZ NOT NULL,
    server_received_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    latitude NUMERIC(9,6) NOT NULL,
    longitude NUMERIC(9,6) NOT NULL,
    gps_accuracy NUMERIC(6,2) NOT NULL,
    distance_meters NUMERIC(8,2) NOT NULL DEFAULT 0,
    geofence_outcome VARCHAR(30) NOT NULL DEFAULT 'valid', -- 'valid', 'outside_with_reason', 'blocked'
    outside_reason TEXT NULL,
    device_id VARCHAR(100) NOT NULL,
    app_version VARCHAR(50) NOT NULL,
    battery_level INTEGER NULL,
    network_type VARCHAR(30) NULL,
    mock_location_detected BOOLEAN NOT NULL DEFAULT FALSE,
    photo_storage_key TEXT NOT NULL,
    photo_hash VARCHAR(64) NOT NULL,
    sync_state VARCHAR(20) NOT NULL DEFAULT 'synced', -- 'pending', 'uploading', 'synced', 'failed'
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_attendance_captures_employee ON attendance_captures(employee_id);
CREATE INDEX idx_attendance_captures_attendance ON attendance_captures(attendance_id);
CREATE INDEX idx_attendance_captures_photo_hash ON attendance_captures(photo_hash);

-- 4. ATTENDANCE EVIDENCE (Forensic references)
CREATE TABLE attendance_evidence (
    evidence_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    attendance_id UUID NOT NULL REFERENCES attendance_records(attendance_id) ON DELETE CASCADE,
    capture_id UUID NOT NULL REFERENCES attendance_captures(capture_id) ON DELETE CASCADE,
    evidence_type VARCHAR(30) NOT NULL, -- 'photo', 'gps', 'device_metadata'
    storage_reference TEXT NOT NULL,
    hash VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_attendance_evidence_attendance ON attendance_evidence(attendance_id);

-- 5. ATTENDANCE FLAGS (Fraud / Anomaly Detection)
CREATE TABLE attendance_flags (
    flag_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    attendance_id UUID NOT NULL REFERENCES attendance_records(attendance_id) ON DELETE CASCADE,
    flag_type VARCHAR(50) NOT NULL,
    -- 'outside_geofence', 'mock_location', 'device_time_mismatch', 'low_gps_accuracy',
    -- 'offline_capture', 'unscheduled', 'unregistered_device', 'repeated_location',
    -- 'reused_photo_hash', 'no_checkout', 'late_offline_sync', 'early_checkout', 'manual_attendance'
    severity VARCHAR(20) NOT NULL DEFAULT 'MEDIUM', -- 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    description TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMPTZ NULL,
    resolution TEXT NULL
);

CREATE INDEX idx_attendance_flags_attendance ON attendance_flags(attendance_id);
CREATE INDEX idx_attendance_flags_type ON attendance_flags(flag_type);

-- 6. ATTENDANCE REVISIONS (Immutable Correction Audit Trail)
CREATE TABLE attendance_revisions (
    revision_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    attendance_id UUID NOT NULL REFERENCES attendance_records(attendance_id) ON DELETE CASCADE,
    revision_number INTEGER NOT NULL DEFAULT 1,
    previous_values JSONB NOT NULL,
    new_values JSONB NOT NULL,
    reason TEXT NOT NULL,
    actor_id UUID NOT NULL REFERENCES app_users(user_id) ON DELETE CASCADE,
    correction_size_minutes INTEGER NOT NULL DEFAULT 0,
    requires_admin_approval BOOLEAN NOT NULL DEFAULT FALSE,
    approval_status VARCHAR(20) NOT NULL DEFAULT 'approved', -- 'pending', 'approved', 'rejected'
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_attendance_revisions_attendance ON attendance_revisions(attendance_id);

-- 7. REGULARISATION REQUESTS (Missed capture guard submissions)
CREATE TABLE attendance_regularisations (
    request_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID NOT NULL REFERENCES employees(employee_id) ON DELETE CASCADE,
    attendance_id UUID NULL REFERENCES attendance_records(attendance_id) ON DELETE SET NULL,
    assignment_id UUID NULL REFERENCES roster_assignments(assignment_id) ON DELETE SET NULL,
    site_id UUID NOT NULL REFERENCES client_sites(site_id) ON DELETE CASCADE,
    shift_id UUID NOT NULL REFERENCES site_shifts(shift_id) ON DELETE CASCADE,
    duty_date DATE NOT NULL,
    claimed_check_in TIMESTAMPTZ NOT NULL,
    claimed_check_out TIMESTAMPTZ NOT NULL,
    reason TEXT NOT NULL,
    photo_storage_key TEXT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending', -- 'pending', 'approved', 'rejected'
    reviewed_by UUID NULL REFERENCES app_users(user_id) ON DELETE SET NULL,
    reviewed_at TIMESTAMPTZ NULL,
    rejection_reason TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_attendance_regularisations_guard ON attendance_regularisations(employee_id);
CREATE INDEX idx_attendance_regularisations_status ON attendance_regularisations(status);

-- 8. ATTENDANCE APPROVALS (Supervisor / Admin Decisions)
CREATE TABLE attendance_approvals (
    approval_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    attendance_id UUID NOT NULL REFERENCES attendance_records(attendance_id) ON DELETE CASCADE,
    actor_id UUID NOT NULL REFERENCES app_users(user_id) ON DELETE CASCADE,
    action VARCHAR(30) NOT NULL, -- 'approve', 'reject', 'correct', 'mark_absent', 'request_explanation'
    reason TEXT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_attendance_approvals_attendance ON attendance_approvals(attendance_id);

-- 9. PERIOD EXCEPTIONS (Allowed pending records when closing period)
CREATE TABLE attendance_period_exceptions (
    exception_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    period_id UUID NOT NULL REFERENCES attendance_periods(period_id) ON DELETE CASCADE,
    attendance_id UUID NOT NULL REFERENCES attendance_records(attendance_id) ON DELETE CASCADE,
    exception_type VARCHAR(50) NOT NULL DEFAULT 'PENDING_APPROVAL',
    reason TEXT NOT NULL,
    created_by UUID NOT NULL REFERENCES app_users(user_id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 10. ATTENDANCE HANDOVERS (Reliever Transition Link)
CREATE TABLE attendance_handovers (
    handover_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    outgoing_attendance_id UUID NOT NULL REFERENCES attendance_records(attendance_id) ON DELETE CASCADE,
    incoming_attendance_id UUID NULL REFERENCES attendance_records(attendance_id) ON DELETE SET NULL,
    incoming_employee_code VARCHAR(50) NOT NULL,
    site_id UUID NOT NULL REFERENCES client_sites(site_id) ON DELETE CASCADE,
    handover_time TIMESTAMPTZ NOT NULL,
    notes TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 11. MANUAL ATTENDANCE COUNTERS (Monthly Guard Limit Tracking)
CREATE TABLE manual_attendance_counters (
    counter_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID NOT NULL REFERENCES employees(employee_id) ON DELETE CASCADE,
    period_month VARCHAR(7) NOT NULL, -- 'YYYY-MM'
    count INTEGER NOT NULL DEFAULT 0,
    configured_limit INTEGER NOT NULL DEFAULT 3,
    alert_status VARCHAR(20) NOT NULL DEFAULT 'normal', -- 'normal', 'exceeded'
    UNIQUE(employee_id, period_month)
);

-- Seed Module 6 operational settings into system_settings
INSERT INTO system_settings (setting_id, company_id, key, value, updated_at)
SELECT
    gen_random_uuid(),
    c.company_id,
    s.key,
    s.value,
    CURRENT_TIMESTAMP
FROM companies c
CROSS JOIN (
    VALUES
        ('check_in_window_before_mins', '30'),
        ('check_in_window_after_mins', '60'),
        ('late_grace_period_mins', '15'),
        ('max_gps_accuracy_meters', '100.0'),
        ('device_time_mismatch_max_seconds', '300'),
        ('offline_sync_acceptance_hours', '24'),
        ('auto_close_delay_hours', '4'),
        ('no_show_delay_minutes', '60'),
        ('regularisation_window_days', '3'),
        ('manual_attendance_monthly_limit', '3'),
        ('large_correction_threshold_mins', '120'),
        ('attendance_cutoff_day', '25')
) AS s(key, value)
ON CONFLICT (company_id, key) DO UPDATE SET value = EXCLUDED.value;
