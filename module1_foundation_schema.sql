-- Migration: Module 1 Foundation Schema Updates
-- Schema: security_erp
SET search_path TO security_erp, public;

-- 1. Alter companies to ensure time_zone exists
ALTER TABLE companies ADD COLUMN IF NOT EXISTS time_zone VARCHAR(50) NOT NULL DEFAULT 'Asia/Kolkata';

-- 2. Alter app_users to add Module 1 Foundation fields
ALTER TABLE app_users ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'GUARD';
ALTER TABLE app_users DROP CONSTRAINT IF EXISTS chk_app_user_role;
ALTER TABLE app_users ADD CONSTRAINT chk_app_user_role CHECK (role IN ('ADMIN', 'SUPERVISOR', 'GUARD', 'CLIENT'));

ALTER TABLE app_users ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE';
ALTER TABLE app_users DROP CONSTRAINT IF EXISTS chk_app_user_status;
ALTER TABLE app_users ADD CONSTRAINT chk_app_user_status CHECK (status IN ('ACTIVE', 'INACTIVE'));

ALTER TABLE app_users ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE app_users ADD COLUMN IF NOT EXISTS failed_attempts INTEGER NOT NULL DEFAULT 0;
ALTER TABLE app_users ADD COLUMN IF NOT EXISTS locked_until TIMESTAMPTZ;
ALTER TABLE app_users ADD COLUMN IF NOT EXISTS guard_profile_id UUID;
ALTER TABLE app_users ADD COLUMN IF NOT EXISTS client_company_id UUID;
ALTER TABLE app_users ADD COLUMN IF NOT EXISTS contact_phone VARCHAR(30);
ALTER TABLE app_users ADD COLUMN IF NOT EXISTS deactivated_at TIMESTAMPTZ;
ALTER TABLE app_users ADD COLUMN IF NOT EXISTS deactivated_by UUID REFERENCES app_users(user_id) ON DELETE SET NULL;
ALTER TABLE app_users ADD COLUMN IF NOT EXISTS deactivation_reason TEXT;
ALTER TABLE app_users ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE app_users ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES app_users(user_id) ON DELETE SET NULL;
ALTER TABLE app_users ADD COLUMN IF NOT EXISTS updated_by UUID REFERENCES app_users(user_id) ON DELETE SET NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_active_guard_profile ON app_users(guard_profile_id) 
WHERE guard_profile_id IS NOT NULL AND status = 'ACTIVE';

CREATE INDEX IF NOT EXISTS idx_users_email_ci ON app_users(lower(email)) WHERE email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_users_phone ON app_users(phone) WHERE phone IS NOT NULL;

-- 3. Scope Grants table
CREATE TABLE IF NOT EXISTS scope_grants (
    grant_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    user_id UUID NOT NULL REFERENCES app_users(user_id) ON DELETE CASCADE,
    scope_type VARCHAR(20) NOT NULL CHECK (scope_type IN ('ALL', 'SITE', 'GUARD', 'COMPANY', 'OWN_PROFILE')),
    target_id UUID,
    effective_from DATE NOT NULL,
    effective_to DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    CHECK (effective_to IS NULL OR effective_to >= effective_from)
);
CREATE INDEX IF NOT EXISTS idx_scope_grants_user_dates ON scope_grants(user_id, effective_from, effective_to);

-- 4. User Sessions
CREATE TABLE IF NOT EXISTS user_sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    user_id UUID NOT NULL REFERENCES app_users(user_id) ON DELETE CASCADE,
    platform VARCHAR(20) NOT NULL CHECK (platform IN ('WEB', 'ANDROID')),
    device_id TEXT,
    ip_address VARCHAR(45) NOT NULL,
    user_agent TEXT,
    session_token_hash TEXT NOT NULL,
    refresh_token_hash TEXT,
    issued_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    revoked_reason VARCHAR(30) CHECK (revoked_reason IN (
        'LOGOUT', 'LOGOUT_ALL', 'PASSWORD_CHANGE', 'DEACTIVATED', 
        'DEVICE_CHANGE', 'ROLE_CHANGE', 'TOKEN_REUSE', 'EXPIRED_BY_ADMIN', 'IDLE_TIMEOUT'
    ))
);
CREATE INDEX IF NOT EXISTS idx_sessions_user_active ON user_sessions(user_id, revoked_at, expires_at);
CREATE INDEX IF NOT EXISTS idx_sessions_refresh_hash ON user_sessions(refresh_token_hash) WHERE refresh_token_hash IS NOT NULL;

-- 5. Bound Devices (Guards)
CREATE TABLE IF NOT EXISTS bound_devices (
    bound_device_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    user_id UUID NOT NULL REFERENCES app_users(user_id) ON DELETE CASCADE,
    device_id TEXT NOT NULL,
    model TEXT,
    os_version TEXT,
    app_version TEXT,
    bound_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    unbound_at TIMESTAMPTZ,
    unbound_reason VARCHAR(30) CHECK (unbound_reason IN ('CHANGE_APPROVED', 'ADMIN_RESET'))
);
CREATE INDEX IF NOT EXISTS idx_bound_device_user_active ON bound_devices(user_id) WHERE unbound_at IS NULL;

-- 6. Device Change Requests
CREATE TABLE IF NOT EXISTS device_change_requests (
    request_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    user_id UUID NOT NULL REFERENCES app_users(user_id) ON DELETE CASCADE,
    new_device_id TEXT NOT NULL,
    new_model TEXT,
    new_os_version TEXT,
    new_app_version TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED', 'EXPIRED', 'SUPERSEDED')),
    requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    decided_by UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    decided_at TIMESTAMPTZ,
    decision_note TEXT
);
CREATE INDEX IF NOT EXISTS idx_dcr_user_status ON device_change_requests(user_id, status);

-- 7. Login Attempts (Login History)
CREATE TABLE IF NOT EXISTS login_attempts (
    attempt_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(company_id) ON DELETE SET NULL,
    user_id UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    identifier_entered TEXT,
    result VARCHAR(30) NOT NULL CHECK (result IN (
        'SUCCESS', 'WRONG_PASSWORD', 'LOCKED', 'INACTIVE', 
        'NOT_LINKED', 'WRONG_PLATFORM', 'DEVICE_PENDING', 'FORMAT_ERROR', 'RATE_LIMITED'
    )),
    platform VARCHAR(20),
    ip_address VARCHAR(45),
    device_id TEXT,
    device_model TEXT,
    app_version TEXT,
    attempted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_login_attempts_user_time ON login_attempts(user_id, attempted_at DESC);
CREATE INDEX IF NOT EXISTS idx_login_attempts_ip_time ON login_attempts(ip_address, attempted_at DESC);

-- 8. One-Time Tokens (Password Reset & Invites)
CREATE TABLE IF NOT EXISTS one_time_tokens (
    token_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    user_id UUID NOT NULL REFERENCES app_users(user_id) ON DELETE CASCADE,
    purpose VARCHAR(20) NOT NULL CHECK (purpose IN ('RESET', 'INVITE')),
    token_hash TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_tokens_hash ON one_time_tokens(token_hash) WHERE used_at IS NULL;

-- 9. Notification Types Registry
CREATE TABLE IF NOT EXISTS notification_types (
    type_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(80) NOT NULL UNIQUE,
    title_key VARCHAR(120) NOT NULL,
    body_key VARCHAR(120) NOT NULL,
    recipient_rule VARCHAR(80) NOT NULL,
    channels JSONB NOT NULL DEFAULT '["IN"]'::jsonb,
    priority VARCHAR(20) NOT NULL DEFAULT 'NORMAL' CHECK (priority IN ('NORMAL', 'HIGH', 'CRITICAL')),
    related_record_type VARCHAR(80)
);

-- 10. Notification Deliveries & Enhancements to Notifications
ALTER TABLE notifications ADD COLUMN IF NOT EXISTS type_code VARCHAR(80);
ALTER TABLE notifications ADD COLUMN IF NOT EXISTS params JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE notifications ADD COLUMN IF NOT EXISTS related_record_type VARCHAR(80);
ALTER TABLE notifications ADD COLUMN IF NOT EXISTS related_record_id UUID;
ALTER TABLE notifications ADD COLUMN IF NOT EXISTS dedupe_key VARCHAR(120);
ALTER TABLE notifications ADD COLUMN IF NOT EXISTS read_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS notification_deliveries (
    delivery_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notification_id UUID NOT NULL REFERENCES notifications(notification_id) ON DELETE CASCADE,
    channel VARCHAR(20) NOT NULL CHECK (channel IN ('IN', 'PUSH', 'WEB', 'SMS')),
    status VARCHAR(20) NOT NULL DEFAULT 'QUEUED' CHECK (status IN ('QUEUED', 'SENT', 'FAILED', 'SKIPPED', 'NOT_CONFIGURED')),
    attempts INTEGER NOT NULL DEFAULT 0,
    last_attempt_at TIMESTAMPTZ,
    failure_reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_notif_deliveries_status ON notification_deliveries(status);
CREATE INDEX IF NOT EXISTS idx_notifs_recipient_read ON notifications(user_id, read_at, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notifs_dedupe ON notifications(type_code, user_id, dedupe_key, created_at DESC) WHERE dedupe_key IS NOT NULL;

-- 11. Push Tokens
CREATE TABLE IF NOT EXISTS push_tokens (
    token_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    user_id UUID NOT NULL REFERENCES app_users(user_id) ON DELETE CASCADE,
    session_id UUID REFERENCES user_sessions(session_id) ON DELETE CASCADE,
    token TEXT NOT NULL,
    registered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    removed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_push_tokens_user ON push_tokens(user_id) WHERE removed_at IS NULL;

-- 12. Notification Preferences
CREATE TABLE IF NOT EXISTS notification_preferences (
    preference_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE REFERENCES app_users(user_id) ON DELETE CASCADE,
    push_normal BOOLEAN NOT NULL DEFAULT TRUE,
    browser_notifications BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 13. Audit Events (Append-only)
CREATE TABLE IF NOT EXISTS audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    actor_user_id UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    actor_role VARCHAR(20) NOT NULL,
    actor_name VARCHAR(160) NOT NULL,
    action_code VARCHAR(80) NOT NULL,
    module VARCHAR(50) NOT NULL DEFAULT 'foundation',
    record_type VARCHAR(80),
    record_id TEXT,
    result VARCHAR(20) NOT NULL CHECK (result IN ('SUCCESS', 'FAILURE')),
    old_values JSONB,
    new_values JSONB,
    reason TEXT,
    ip_address VARCHAR(45),
    device_id TEXT,
    user_agent TEXT,
    request_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_occurred_at ON audit_events(occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_actor_time ON audit_events(actor_user_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_action_time ON audit_events(action_code, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_record ON audit_events(record_type, record_id, occurred_at DESC);

-- Prevent UPDATE or DELETE on audit_events via Trigger
CREATE OR REPLACE FUNCTION prevent_audit_tampering() 
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Audit records are append-only and cannot be updated or deleted.';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_audit_events_immutable ON audit_events;
CREATE TRIGGER trg_audit_events_immutable
BEFORE UPDATE OR DELETE ON audit_events
FOR EACH ROW EXECUTE FUNCTION prevent_audit_tampering();

-- 14. Consent Records (Append-only)
CREATE TABLE IF NOT EXISTS consent_records (
    consent_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    user_id UUID NOT NULL REFERENCES app_users(user_id) ON DELETE CASCADE,
    item VARCHAR(30) NOT NULL CHECK (item IN ('TERMS_PRIVACY', 'LOCATION', 'CAMERA', 'NOTIFICATIONS')),
    decision VARCHAR(20) NOT NULL CHECK (decision IN ('GRANTED', 'DENIED', 'WITHDRAWN')),
    policy_version VARCHAR(50) NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    device_id TEXT,
    app_version TEXT,
    ip_address VARCHAR(45)
);
CREATE INDEX IF NOT EXISTS idx_consent_user_item ON consent_records(user_id, item, recorded_at DESC);

DROP TRIGGER IF EXISTS trg_consent_records_immutable ON consent_records;
CREATE TRIGGER trg_consent_records_immutable
BEFORE UPDATE OR DELETE ON consent_records
FOR EACH ROW EXECUTE FUNCTION prevent_audit_tampering();

-- 15. System Settings
CREATE TABLE IF NOT EXISTS system_settings (
    setting_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    key VARCHAR(100) NOT NULL,
    value TEXT NOT NULL,
    updated_by UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (company_id, key)
);

