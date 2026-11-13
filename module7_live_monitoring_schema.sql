-- ==============================================================================
-- MODULE 7: LIVE MONITORING DATABASE SCHEMA (PostgreSQL)
-- Schema: security_erp
-- ==============================================================================

SET search_path TO security_erp, public;

DROP TABLE IF EXISTS supervisor_pings CASCADE;
DROP TABLE IF EXISTS monitoring_alerts CASCADE;
DROP TABLE IF EXISTS alert_rules CASCADE;
DROP TABLE IF EXISTS monitoring_status_history CASCADE;
DROP TABLE IF EXISTS guard_monitoring_statuses CASCADE;
DROP TABLE IF EXISTS heartbeats CASCADE;
DROP TABLE IF EXISTS location_points CASCADE;
DROP TABLE IF EXISTS monitoring_duties CASCADE;
DROP TABLE IF EXISTS outage_groups CASCADE;
DROP TABLE IF EXISTS tracking_configurations CASCADE;

-- 1. Monitoring Duties (Session per guard assignment duty)
CREATE TABLE IF NOT EXISTS monitoring_duties (
    duty_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    employee_id UUID NOT NULL REFERENCES employees(employee_id) ON DELETE CASCADE,
    assignment_id UUID NOT NULL REFERENCES roster_assignments(assignment_id) ON DELETE CASCADE,
    site_id UUID NOT NULL REFERENCES client_sites(site_id) ON DELETE RESTRICT,
    shift_id UUID NOT NULL REFERENCES site_shifts(shift_id) ON DELETE RESTRICT,
    attendance_record_id UUID REFERENCES attendance_records(attendance_id) ON DELETE SET NULL,
    duty_start_at TIMESTAMPTZ NOT NULL,
    duty_end_at TIMESTAMPTZ,
    tracking_start_at TIMESTAMPTZ,
    tracking_end_at TIMESTAMPTZ,
    consent_record_id UUID REFERENCES consent_records(consent_id) ON DELETE SET NULL,
    consent_policy_version VARCHAR(50),
    tracking_state VARCHAR(20) NOT NULL DEFAULT 'ACTIVE' CHECK (tracking_state IN ('ACTIVE', 'NOT_TRACKED', 'STOPPED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_monitoring_duty_assignment UNIQUE (company_id, assignment_id)
);

CREATE INDEX IF NOT EXISTS idx_monitoring_duties_company_state ON monitoring_duties (company_id, tracking_state);
CREATE INDEX IF NOT EXISTS idx_monitoring_duties_guard_site ON monitoring_duties (employee_id, site_id);

-- 2. Location Points (Append-only GPS telemetry with client idempotency)
CREATE TABLE IF NOT EXISTS location_points (
    point_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    duty_id UUID NOT NULL REFERENCES monitoring_duties(duty_id) ON DELETE CASCADE,
    employee_id UUID NOT NULL REFERENCES employees(employee_id) ON DELETE CASCADE,
    assignment_id UUID NOT NULL REFERENCES roster_assignments(assignment_id) ON DELETE CASCADE,
    client_generated_id UUID NOT NULL,
    latitude NUMERIC(10, 7) NOT NULL,
    longitude NUMERIC(10, 7) NOT NULL,
    accuracy_m NUMERIC(8, 2) NOT NULL,
    device_captured_at TIMESTAMPTZ NOT NULL,
    server_received_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    mock_location BOOLEAN NOT NULL DEFAULT FALSE,
    battery_percent INTEGER CHECK (battery_percent BETWEEN 0 AND 100),
    charging_state VARCHAR(20) CHECK (charging_state IN ('CHARGING', 'NOT_CHARGING', 'UNKNOWN')),
    network_type VARCHAR(20),
    app_version VARCHAR(50),
    location_permission VARCHAR(30),
    battery_optimization_state VARCHAR(30),
    sequence_number INTEGER,
    accepted BOOLEAN NOT NULL DEFAULT TRUE,
    rejection_reason TEXT,
    CONSTRAINT uq_location_points_client_id UNIQUE (company_id, employee_id, client_generated_id)
);

CREATE INDEX IF NOT EXISTS idx_location_points_duty_capture ON location_points (duty_id, device_captured_at);
CREATE INDEX IF NOT EXISTS idx_location_points_employee_time ON location_points (employee_id, device_captured_at);

-- 3. Heartbeats (Periodic status signals even when stationary)
CREATE TABLE IF NOT EXISTS heartbeats (
    heartbeat_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    duty_id UUID NOT NULL REFERENCES monitoring_duties(duty_id) ON DELETE CASCADE,
    employee_id UUID NOT NULL REFERENCES employees(employee_id) ON DELETE CASCADE,
    client_generated_id UUID NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    battery_percent INTEGER CHECK (battery_percent BETWEEN 0 AND 100),
    charging_state VARCHAR(20) CHECK (charging_state IN ('CHARGING', 'NOT_CHARGING', 'UNKNOWN')),
    network_type VARCHAR(20),
    app_version VARCHAR(50),
    permission_state VARCHAR(30),
    sequence_number INTEGER,
    CONSTRAINT uq_heartbeats_client_id UNIQUE (company_id, employee_id, client_generated_id)
);

CREATE INDEX IF NOT EXISTS idx_heartbeats_duty_captured ON heartbeats (duty_id, captured_at);

-- 4. Guard Monitoring Status (Current operational snapshot per duty)
CREATE TABLE IF NOT EXISTS guard_monitoring_statuses (
    status_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    duty_id UUID NOT NULL UNIQUE REFERENCES monitoring_duties(duty_id) ON DELETE CASCADE,
    employee_id UUID NOT NULL REFERENCES employees(employee_id) ON DELETE CASCADE,
    assignment_id UUID NOT NULL REFERENCES roster_assignments(assignment_id) ON DELETE CASCADE,
    site_id UUID NOT NULL REFERENCES client_sites(site_id) ON DELETE RESTRICT,
    primary_status VARCHAR(30) NOT NULL DEFAULT 'on_duty_at_site' CHECK (
        primary_status IN ('not_started', 'on_duty_at_site', 'on_duty_outside_site', 'stale', 'no_contact', 'off_duty', 'not_tracked')
    ),
    has_active_alert BOOLEAN NOT NULL DEFAULT FALSE,
    display_status VARCHAR(50) NOT NULL DEFAULT 'On Duty at Site',
    consecutive_outside_count INTEGER NOT NULL DEFAULT 0,
    last_location_point_id UUID REFERENCES location_points(point_id) ON DELETE SET NULL,
    last_heartbeat_id UUID REFERENCES heartbeats(heartbeat_id) ON DELETE SET NULL,
    last_communication_at TIMESTAMPTZ,
    status_calculated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_monitoring_statuses_site ON guard_monitoring_statuses (site_id, primary_status);
CREATE INDEX IF NOT EXISTS idx_monitoring_statuses_company_calc ON guard_monitoring_statuses (company_id, status_calculated_at);

-- 5. Monitoring Status History (Append-only audit trail of operational transitions)
CREATE TABLE IF NOT EXISTS monitoring_status_history (
    history_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    duty_id UUID NOT NULL REFERENCES monitoring_duties(duty_id) ON DELETE CASCADE,
    employee_id UUID NOT NULL REFERENCES employees(employee_id) ON DELETE CASCADE,
    previous_status VARCHAR(30),
    new_status VARCHAR(30) NOT NULL,
    trigger_type VARCHAR(50) NOT NULL,
    related_location_id UUID REFERENCES location_points(point_id) ON DELETE SET NULL,
    changed_at TIMESTAMPTZ NOT NULL,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_monitoring_status_history_duty ON monitoring_status_history (duty_id, changed_at);

-- 6. Alert Rules (Configurable detection criteria per company)
CREATE TABLE IF NOT EXISTS alert_rules (
    rule_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    rule_name VARCHAR(100) NOT NULL,
    rule_code VARCHAR(50) NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    threshold_value NUMERIC(10, 2),
    threshold_unit VARCHAR(30),
    severity VARCHAR(20) NOT NULL DEFAULT 'NORMAL' CHECK (severity IN ('NORMAL', 'HIGH', 'CRITICAL')),
    recipient_policy VARCHAR(50) NOT NULL DEFAULT 'PRIMARY_SUPERVISOR',
    cooldown_seconds INTEGER NOT NULL DEFAULT 900,
    escalation_policy JSONB,
    updated_by UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_alert_rules_code UNIQUE (company_id, rule_code)
);

-- 7. Monitoring Alerts (Active & historic alerts lifecycle)
CREATE TABLE IF NOT EXISTS monitoring_alerts (
    alert_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    duty_id UUID NOT NULL REFERENCES monitoring_duties(duty_id) ON DELETE CASCADE,
    employee_id UUID NOT NULL REFERENCES employees(employee_id) ON DELETE CASCADE,
    site_id UUID NOT NULL REFERENCES client_sites(site_id) ON DELETE RESTRICT,
    alert_rule_id UUID REFERENCES alert_rules(rule_id) ON DELETE SET NULL,
    alert_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL DEFAULT 'NORMAL' CHECK (severity IN ('NORMAL', 'HIGH', 'CRITICAL')),
    state VARCHAR(30) NOT NULL DEFAULT 'RAISED' CHECK (state IN ('RAISED', 'ACKNOWLEDGED', 'RESOLVED', 'AUTO_RESOLVED', 'DISMISSED')),
    trigger_value TEXT,
    raised_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    acknowledged_at TIMESTAMPTZ,
    acknowledged_by UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    resolved_at TIMESTAMPTZ,
    resolved_by UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    resolution_note TEXT,
    dismissal_reason TEXT,
    escalation_level INTEGER NOT NULL DEFAULT 0,
    last_escalated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_monitoring_alerts_active ON monitoring_alerts (company_id, state) WHERE state IN ('RAISED', 'ACKNOWLEDGED');
CREATE INDEX IF NOT EXISTS idx_monitoring_alerts_site_duty ON monitoring_alerts (site_id, duty_id);

-- 8. Supervisor Pings (Check-on-you prompt tracking)
CREATE TABLE IF NOT EXISTS supervisor_pings (
    ping_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    duty_id UUID NOT NULL REFERENCES monitoring_duties(duty_id) ON DELETE CASCADE,
    employee_id UUID NOT NULL REFERENCES employees(employee_id) ON DELETE CASCADE,
    supervisor_id UUID NOT NULL REFERENCES app_users(user_id) ON DELETE RESTRICT,
    sent_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    delivery_state VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (delivery_state IN ('PENDING', 'DELIVERED', 'FAILED', 'UNKNOWN')),
    response_state VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (response_state IN ('PENDING', 'RESPONDED', 'NO_RESPONSE')),
    responded_at TIMESTAMPTZ,
    response_value VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_supervisor_pings_duty_sent ON supervisor_pings (duty_id, sent_at);

-- 9. Outage Groups (Correlated network or power disruptions)
CREATE TABLE IF NOT EXISTS outage_groups (
    group_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    site_id UUID REFERENCES client_sites(site_id) ON DELETE SET NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMPTZ,
    suspected_cause TEXT,
    affected_guard_count INTEGER NOT NULL DEFAULT 0,
    group_state VARCHAR(20) NOT NULL DEFAULT 'ACTIVE' CHECK (group_state IN ('ACTIVE', 'RESOLVED'))
);

-- 10. Tracking Configurations (Company-level telemetry & threshold policies)
CREATE TABLE IF NOT EXISTS tracking_configurations (
    config_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL UNIQUE REFERENCES companies(company_id) ON DELETE CASCADE,
    normal_interval_mins INTEGER NOT NULL DEFAULT 5,
    moving_interval_mins INTEGER NOT NULL DEFAULT 2,
    low_battery_interval_mins INTEGER NOT NULL DEFAULT 10,
    stale_threshold_mins INTEGER NOT NULL DEFAULT 10,
    no_contact_threshold_mins INTEGER NOT NULL DEFAULT 20,
    geofence_debounce_count INTEGER NOT NULL DEFAULT 3,
    low_accuracy_threshold_meters NUMERIC(8, 2) NOT NULL DEFAULT 50.0,
    post_shift_cutoff_mins INTEGER NOT NULL DEFAULT 30,
    raw_retention_days INTEGER NOT NULL DEFAULT 30,
    max_local_buffer_size INTEGER NOT NULL DEFAULT 1000,
    max_upload_batch_size INTEGER NOT NULL DEFAULT 50,
    updated_by UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Seed Default Alert Rules for initial company
INSERT INTO alert_rules (company_id, rule_name, rule_code, severity, recipient_policy, cooldown_seconds, threshold_value, threshold_unit)
SELECT
    c.company_id,
    r.rule_name,
    r.rule_code,
    r.severity,
    r.recipient_policy,
    r.cooldown_seconds,
    r.threshold_value,
    r.threshold_unit
FROM companies c
CROSS JOIN (
    VALUES
        ('Geofence Exit', 'GEOFENCE_EXIT', 'HIGH', 'PRIMARY_SUPERVISOR', 900, 3.0, 'readings'),
        ('Prolonged Outside Site', 'OUTSIDE_SITE_PROLONGED', 'HIGH', 'PRIMARY_SUPERVISOR', 900, 15.0, 'minutes'),
        ('No Contact', 'NO_CONTACT', 'HIGH', 'PRIMARY_SUPERVISOR', 1200, 20.0, 'minutes'),
        ('Low Battery', 'LOW_BATTERY', 'NORMAL', 'PRIMARY_SUPERVISOR', 1800, 15.0, 'percentage'),
        ('Location Permission Unavailable', 'PERMISSION_UNAVAILABLE', 'HIGH', 'PRIMARY_SUPERVISOR', 3600, 1.0, 'detection'),
        ('Mock Location Detected', 'MOCK_LOCATION_DETECTED', 'HIGH', 'PRIMARY_SUPERVISOR', 3600, 1.0, 'detection'),
        ('Device Time Mismatch', 'TIME_MISMATCH', 'NORMAL', 'PRIMARY_SUPERVISOR', 1800, 5.0, 'minutes')
) AS r(rule_name, rule_code, severity, recipient_policy, cooldown_seconds, threshold_value, threshold_unit)
ON CONFLICT (company_id, rule_code) DO NOTHING;

-- Seed Default Tracking Configuration for initial company
INSERT INTO tracking_configurations (company_id)
SELECT company_id FROM companies
ON CONFLICT (company_id) DO NOTHING;
