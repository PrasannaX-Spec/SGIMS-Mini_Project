-- ==============================================================================
-- Module 9: Panic and Escalation Schema
-- Security Agency Management and Monitoring System (SGIMS)
-- Target Schema: security_erp
-- ==============================================================================

SET search_path TO security_erp, public;

-- Allow PANIC record_type in case_number_sequences
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_schema = 'security_erp' AND table_name = 'case_number_sequences'
    ) THEN
        ALTER TABLE case_number_sequences DROP CONSTRAINT IF EXISTS case_number_sequences_record_type_check;
        ALTER TABLE case_number_sequences ADD CONSTRAINT case_number_sequences_record_type_check 
            CHECK (record_type IN ('INCIDENT', 'REQUEST', 'TICKET', 'PANIC'));
    END IF;
END $$;

-- 1. Panic Alerts Central Table
CREATE TABLE IF NOT EXISTS panic_alerts (
    panic_alert_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    alert_number VARCHAR(50) NOT NULL UNIQUE,
    client_generated_id VARCHAR(100) NOT NULL,
    guard_id UUID NOT NULL REFERENCES employees(employee_id) ON DELETE RESTRICT,
    registered_device_id UUID REFERENCES bound_devices(bound_device_id) ON DELETE SET NULL,
    assignment_id UUID REFERENCES roster_assignments(assignment_id) ON DELETE SET NULL,
    site_id UUID REFERENCES client_sites(site_id) ON DELETE SET NULL,
    trigger_server_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    trigger_device_time TIMESTAMPTZ,
    alert_status VARCHAR(30) NOT NULL DEFAULT 'TRIGGERED'
        CHECK (alert_status IN (
            'TRIGGERED', 'DELIVERING', 'ACKNOWLEDGED', 'RESPONDING', 
            'GUARD_CONFIRMED_SAFE', 'ESCALATED', 'RESOLVED', 'FALSE_ALARM', 
            'TEST', 'FAILED_TO_DELIVER', 'CLOSED'
        )),
    duty_status VARCHAR(20) NOT NULL DEFAULT 'ON_DUTY'
        CHECK (duty_status IN ('ON_DUTY', 'OUTSIDE_DUTY')),
    test_flag BOOLEAN NOT NULL DEFAULT FALSE,
    current_escalation_stage INTEGER NOT NULL DEFAULT 0,
    last_escalated_at TIMESTAMPTZ,
    first_acknowledged_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_panic_alerts_company_status ON panic_alerts(company_id, alert_status);
CREATE INDEX IF NOT EXISTS idx_panic_alerts_guard ON panic_alerts(guard_id);
CREATE INDEX IF NOT EXISTS idx_panic_alerts_site ON panic_alerts(site_id);
CREATE INDEX IF NOT EXISTS idx_panic_alerts_client_gen_id ON panic_alerts(client_generated_id);
CREATE INDEX IF NOT EXISTS idx_panic_alerts_test_flag ON panic_alerts(test_flag);

-- 2. Panic Trigger Context Table
CREATE TABLE IF NOT EXISTS panic_trigger_contexts (
    context_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    panic_alert_id UUID NOT NULL UNIQUE REFERENCES panic_alerts(panic_alert_id) ON DELETE CASCADE,
    battery_level NUMERIC(5, 2),
    network_type VARCHAR(40),
    device_time TIMESTAMPTZ,
    server_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    app_version VARCHAR(50),
    device_status VARCHAR(50),
    raw_metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_panic_context_alert ON panic_trigger_contexts(panic_alert_id);

-- 3. Panic Position Records Table (Fresh & Historical breadcrumbs)
CREATE TABLE IF NOT EXISTS panic_position_records (
    position_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    panic_alert_id UUID NOT NULL REFERENCES panic_alerts(panic_alert_id) ON DELETE CASCADE,
    latitude NUMERIC(10, 7),
    longitude NUMERIC(10, 7),
    accuracy NUMERIC(8, 2),
    captured_at TIMESTAMPTZ,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    source VARCHAR(30) NOT NULL DEFAULT 'FRESH_DEVICE'
        CHECK (source IN ('FRESH_DEVICE', 'MODULE_7_LAST_KNOWN', 'UNAVAILABLE', 'MANUAL')),
    position_age_seconds INTEGER,
    validity_status VARCHAR(20) NOT NULL DEFAULT 'AVAILABLE'
        CHECK (validity_status IN ('AVAILABLE', 'STALE', 'UNAVAILABLE', 'INVALID')),
    is_latest BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_panic_pos_alert ON panic_position_records(panic_alert_id, is_latest);

-- 4. Panic Escalation Settings Table
CREATE TABLE IF NOT EXISTS panic_escalation_configs (
    config_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    site_id UUID REFERENCES client_sites(site_id) ON DELETE CASCADE,
    stage0_timer_seconds INTEGER NOT NULL DEFAULT 0,
    stage1_timer_seconds INTEGER NOT NULL DEFAULT 30,
    stage2_timer_seconds INTEGER NOT NULL DEFAULT 60,
    stage3_timer_seconds INTEGER NOT NULL DEFAULT 120,
    stage4_timer_seconds INTEGER NOT NULL DEFAULT 300,
    notify_client_immediately BOOLEAN NOT NULL DEFAULT FALSE,
    enabled_routes JSONB NOT NULL DEFAULT '["PUSH", "WEB_CONSOLE", "SMS"]'::jsonb,
    on_call_contact_name VARCHAR(150),
    on_call_contact_phone VARCHAR(30),
    emergency_number_to_display VARCHAR(20) NOT NULL DEFAULT '112',
    panic_tracking_interval_seconds INTEGER NOT NULL DEFAULT 15,
    max_panic_tracking_duration_minutes INTEGER NOT NULL DEFAULT 60,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (company_id, site_id)
);

-- 5. Panic Recipients Table
CREATE TABLE IF NOT EXISTS panic_recipients (
    recipient_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    panic_alert_id UUID NOT NULL REFERENCES panic_alerts(panic_alert_id) ON DELETE CASCADE,
    user_id UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    contact_id UUID REFERENCES client_contacts(contact_id) ON DELETE SET NULL,
    recipient_role VARCHAR(30) NOT NULL
        CHECK (recipient_role IN ('ADMIN', 'SUPERVISOR', 'CLIENT', 'ADDITIONAL_CONTACT')),
    recipient_type VARCHAR(30) NOT NULL
        CHECK (recipient_type IN ('PRIMARY_SUPERVISOR', 'BACKUP_SUPERVISOR', 'ADMIN', 'CLIENT_ESCALATION', 'ADDITIONAL_CONTACT', 'ON_CALL')),
    notification_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    acknowledged_at TIMESTAMPTZ,
    acknowledgement_channel VARCHAR(30)
        CHECK (acknowledgement_channel IN ('APP', 'WEB', 'SMS_LINK'))
);

CREATE INDEX IF NOT EXISTS idx_panic_recipients_alert ON panic_recipients(panic_alert_id);

-- 6. Panic Delivery Attempts Table (Per-recipient, per-route)
CREATE TABLE IF NOT EXISTS panic_delivery_attempts (
    delivery_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    panic_alert_id UUID NOT NULL REFERENCES panic_alerts(panic_alert_id) ON DELETE CASCADE,
    recipient_id UUID NOT NULL REFERENCES panic_recipients(recipient_id) ON DELETE CASCADE,
    route VARCHAR(30) NOT NULL
        CHECK (route IN ('PUSH', 'WEB_CONSOLE', 'SMS', 'VOICE', 'DEVICE_SMS_FALLBACK')),
    attempt_number INTEGER NOT NULL DEFAULT 1,
    attempted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    provider_reference VARCHAR(150),
    provider_status VARCHAR(100),
    delivered_at TIMESTAMPTZ,
    failure_reason TEXT,
    delivery_status VARCHAR(30) NOT NULL DEFAULT 'PENDING'
        CHECK (delivery_status IN ('PENDING', 'ATTEMPTED', 'DELIVERED', 'FAILED', 'UNKNOWN'))
);

CREATE INDEX IF NOT EXISTS idx_panic_deliv_alert ON panic_delivery_attempts(panic_alert_id);
CREATE INDEX IF NOT EXISTS idx_panic_deliv_recipient ON panic_delivery_attempts(recipient_id);

-- 7. Panic Acknowledgements Table
CREATE TABLE IF NOT EXISTS panic_acknowledgements (
    acknowledgement_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    panic_alert_id UUID NOT NULL REFERENCES panic_alerts(panic_alert_id) ON DELETE CASCADE,
    recipient_id UUID NOT NULL REFERENCES panic_recipients(recipient_id) ON DELETE CASCADE,
    user_id UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    acknowledged_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    channel VARCHAR(30) NOT NULL CHECK (channel IN ('APP', 'WEB', 'SMS_LINK')),
    acknowledgement_type VARCHAR(30) NOT NULL DEFAULT 'RECEIPT'
        CHECK (acknowledgement_type IN ('RECEIPT', 'RESPONSE')),
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_panic_ack_alert ON panic_acknowledgements(panic_alert_id);

-- 8. Panic Responder Actions Table
CREATE TABLE IF NOT EXISTS panic_responder_actions (
    responder_action_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    panic_alert_id UUID NOT NULL REFERENCES panic_alerts(panic_alert_id) ON DELETE CASCADE,
    responder_user_id UUID NOT NULL REFERENCES app_users(user_id) ON DELETE RESTRICT,
    action_type VARCHAR(40) NOT NULL CHECK (action_type IN (
        'CALL_GUARD', 'RESPONSE_STARTED', 'HELP_REQUESTED',
        'EMERGENCY_SERVICE_INFORMED', 'DEPLOYMENT_REQUESTED',
        'ARE_YOU_SAFE_SENT', 'GUARD_SAFETY_RESPONSE', 'NOTE_ADDED', 'OTHER'
    )),
    action_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    description TEXT,
    reference VARCHAR(150)
);

CREATE INDEX IF NOT EXISTS idx_panic_action_alert ON panic_responder_actions(panic_alert_id);

-- 9. False Alarm Reports Table
CREATE TABLE IF NOT EXISTS panic_false_alarm_reports (
    false_alarm_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    panic_alert_id UUID NOT NULL REFERENCES panic_alerts(panic_alert_id) ON DELETE CASCADE,
    guard_id UUID NOT NULL REFERENCES employees(employee_id) ON DELETE RESTRICT,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    guard_explanation TEXT,
    are_you_safe_answer VARCHAR(10) DEFAULT 'YES',
    supervisor_id UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    supervisor_decision VARCHAR(30) NOT NULL DEFAULT 'PENDING'
        CHECK (supervisor_decision IN ('CONFIRMED', 'REJECTED', 'PENDING')),
    supervisor_notes TEXT,
    decision_time TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_panic_false_alarm_alert ON panic_false_alarm_reports(panic_alert_id);

-- 10. Panic Resolutions and Admin Review Table
CREATE TABLE IF NOT EXISTS panic_resolutions (
    resolution_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    panic_alert_id UUID NOT NULL UNIQUE REFERENCES panic_alerts(panic_alert_id) ON DELETE CASCADE,
    outcome VARCHAR(50) NOT NULL CHECK (outcome IN (
        'SITUATION_RESOLVED_ON_SITE', 'POLICE_INTERVENED', 'MEDICAL_ATTENTION_GIVEN',
        'INTRUDER_APPREHENDED', 'FALSE_ALARM_VERIFIED', 'GUARD_RELIEVED_SAFELY', 'OTHER'
    )),
    description TEXT NOT NULL,
    injury_status TEXT,
    emergency_services_informed BOOLEAN NOT NULL DEFAULT FALSE,
    emergency_service_ref VARCHAR(150),
    follow_up_required BOOLEAN NOT NULL DEFAULT FALSE,
    submitted_by UUID NOT NULL REFERENCES app_users(user_id) ON DELETE RESTRICT,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    admin_review_status VARCHAR(30) NOT NULL DEFAULT 'PENDING'
        CHECK (admin_review_status IN ('PENDING', 'APPROVED', 'RETURNED')),
    reviewed_by UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    reviewed_at TIMESTAMPTZ,
    review_notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_panic_res_alert ON panic_resolutions(panic_alert_id);

-- 11. Immutable Panic Event Timeline Table
CREATE TABLE IF NOT EXISTS panic_event_timelines (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    panic_alert_id UUID NOT NULL REFERENCES panic_alerts(panic_alert_id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL CHECK (event_type IN (
        'TRIGGER', 'DELIVERY_ATTEMPT', 'DELIVERY_SUCCESS', 'DELIVERY_FAILURE',
        'ACKNOWLEDGEMENT', 'ESCALATION_STAGE', 'NO_ACKNOWLEDGEMENT_WARNING',
        'RESPONSE_STARTED', 'CALL_INITIATED', 'EMERGENCY_SERVICE_NOTIFIED',
        'DEPLOYMENT_REQUESTED', 'ARE_YOU_SAFE_SENT', 'GUARD_SAFETY_REPLY',
        'FALSE_ALARM_REPORTED', 'FALSE_ALARM_CONFIRMED', 'FALSE_ALARM_REJECTED',
        'STATUS_CHANGE', 'INTERNAL_NOTE', 'RESOLUTION_SUBMITTED', 'ADMIN_REVIEWED',
        'ADMIN_CLOSED', 'ADMIN_RETURNED', 'CORRECTION_ENTRY', 'INCIDENT_LINKED'
    )),
    actor_id UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    event_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    event_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_reference VARCHAR(150),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_panic_timeline_alert ON panic_event_timelines(panic_alert_id, event_time ASC);

-- Immutability enforcement trigger on panic_event_timelines
CREATE OR REPLACE FUNCTION trg_panic_timeline_immutable()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION 'Updates to panic_event_timelines are strictly prohibited (FR-9.111, AC-9.54).';
    ELSIF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Deletions from panic_event_timelines are strictly prohibited (FR-9.111, AC-9.54).';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_protect_panic_timeline ON panic_event_timelines;
CREATE TRIGGER trg_protect_panic_timeline
BEFORE UPDATE OR DELETE ON panic_event_timelines
FOR EACH ROW EXECUTE FUNCTION trg_panic_timeline_immutable();

-- 12. Test Drills Table
CREATE TABLE IF NOT EXISTS panic_test_drills (
    drill_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    drill_name VARCHAR(150) NOT NULL,
    scheduled_at TIMESTAMPTZ,
    executed_at TIMESTAMPTZ,
    status VARCHAR(30) NOT NULL DEFAULT 'SCHEDULED'
        CHECK (status IN ('SCHEDULED', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED')),
    selected_recipient_roles JSONB NOT NULL DEFAULT '["SUPERVISOR", "ADMIN"]'::jsonb,
    selected_routes JSONB NOT NULL DEFAULT '["PUSH", "WEB_CONSOLE"]'::jsonb,
    include_clients BOOLEAN NOT NULL DEFAULT FALSE,
    notes TEXT,
    created_by UUID NOT NULL REFERENCES app_users(user_id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_panic_drills_company ON panic_test_drills(company_id, status);

-- 13. Device Readiness Table
CREATE TABLE IF NOT EXISTS panic_device_readiness (
    readiness_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    guard_id UUID NOT NULL REFERENCES employees(employee_id) ON DELETE CASCADE,
    device_id UUID REFERENCES bound_devices(bound_device_id) ON DELETE SET NULL,
    app_version VARCHAR(50),
    notification_permission VARCHAR(20) NOT NULL DEFAULT 'UNKNOWN'
        CHECK (notification_permission IN ('GRANTED', 'DENIED', 'UNKNOWN')),
    battery_optimization VARCHAR(20) NOT NULL DEFAULT 'UNKNOWN'
        CHECK (battery_optimization IN ('OPTIMIZED', 'RESTRICTED', 'UNRESTRICTED', 'UNKNOWN')),
    location_permission VARCHAR(20) NOT NULL DEFAULT 'UNKNOWN'
        CHECK (location_permission IN ('GRANTED', 'DENIED', 'UNKNOWN')),
    last_seen_at TIMESTAMPTZ,
    overall_readiness VARCHAR(20) NOT NULL DEFAULT 'UNKNOWN'
        CHECK (overall_readiness IN ('READY', 'NOT_READY', 'UNKNOWN')),
    corrective_instructions TEXT,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (company_id, guard_id)
);

CREATE INDEX IF NOT EXISTS idx_panic_readiness ON panic_device_readiness(company_id, overall_readiness);

-- 14. Welfare Follow-up Table
CREATE TABLE IF NOT EXISTS panic_welfare_followups (
    followup_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    panic_alert_id UUID NOT NULL REFERENCES panic_alerts(panic_alert_id) ON DELETE CASCADE,
    recorded_by UUID NOT NULL REFERENCES app_users(user_id) ON DELETE RESTRICT,
    followup_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    note TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_panic_welfare_alert ON panic_welfare_followups(panic_alert_id);

-- 15. Module 9 Seeding Procedure
CREATE OR REPLACE FUNCTION seed_module9_company_defaults(p_company_id UUID)
RETURNS VOID AS $$
BEGIN
    -- 1. Default Escalation Config
    INSERT INTO panic_escalation_configs (
        company_id, site_id, stage0_timer_seconds, stage1_timer_seconds,
        stage2_timer_seconds, stage3_timer_seconds, stage4_timer_seconds,
        notify_client_immediately, enabled_routes, emergency_number_to_display,
        panic_tracking_interval_seconds, max_panic_tracking_duration_minutes
    )
    VALUES (
        p_company_id, NULL, 0, 30, 60, 120, 300, FALSE,
        '["PUSH", "WEB_CONSOLE", "SMS"]'::jsonb, '112', 15, 60
    )
    ON CONFLICT (company_id, site_id) DO NOTHING;
END;
$$ LANGUAGE plpgsql;
