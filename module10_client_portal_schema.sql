-- ==============================================================================
-- Module 10: Client Portal Schema
-- Security Agency Management and Monitoring System (SGIMS)
-- Target Schema: security_erp
-- ==============================================================================

SET search_path TO security_erp, public;

-- 1. Client User Site Access Restrictions
CREATE TABLE IF NOT EXISTS client_user_site_access (
    access_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    client_user_id UUID NOT NULL REFERENCES app_users(user_id) ON DELETE CASCADE,
    access_mode VARCHAR(30) NOT NULL DEFAULT 'ALL_SITES' 
        CHECK (access_mode IN ('ALL_SITES', 'SELECTED_SITES')),
    site_id UUID REFERENCES client_sites(site_id) ON DELETE CASCADE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_client_user_site UNIQUE (client_user_id, site_id)
);

CREATE INDEX IF NOT EXISTS idx_cusa_user_active ON client_user_site_access(client_user_id, is_active);
CREATE INDEX IF NOT EXISTS idx_cusa_company ON client_user_site_access(company_id);

-- 2. Client Portal Configuration per Client Organization
CREATE TABLE IF NOT EXISTS client_portal_configurations (
    configuration_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    client_id UUID NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
    future_roster_visibility BOOLEAN NOT NULL DEFAULT FALSE,
    incident_sharing_default VARCHAR(50) NOT NULL DEFAULT 'EXPLICIT_APPROVAL'
        CHECK (incident_sharing_default IN ('EXPLICIT_APPROVAL', 'ALL_RESOLVED', 'CUSTOM')),
    retention_window_days INTEGER NOT NULL DEFAULT 365,
    checkin_photo_visibility BOOLEAN NOT NULL DEFAULT FALSE,
    invoices_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    requests_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    documents_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    announcements_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    enabled_sections JSONB NOT NULL DEFAULT '["dashboard", "deployment", "attendance", "incidents", "panic", "tickets", "documents", "contacts"]'::jsonb,
    updated_by UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_portal_config_client UNIQUE (client_id)
);

CREATE INDEX IF NOT EXISTS idx_cpc_company ON client_portal_configurations(company_id);

-- 3. Client User Notification Preferences
CREATE TABLE IF NOT EXISTS client_notification_preferences (
    preference_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    client_user_id UUID NOT NULL REFERENCES app_users(user_id) ON DELETE CASCADE,
    notification_category VARCHAR(50) NOT NULL 
        CHECK (notification_category IN ('DEPLOYMENT', 'ATTENDANCE', 'INCIDENT', 'BILLING', 'TICKET', 'GENERAL', 'ANNOUNCEMENT', 'PANIC')),
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    quiet_hours_start TIME,
    quiet_hours_end TIME,
    frequency_limit INTEGER,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_cnp_user_cat UNIQUE (client_user_id, notification_category)
);

CREATE INDEX IF NOT EXISTS idx_cnp_user ON client_notification_preferences(client_user_id);

-- 4. Client Document Access / Download Logs
CREATE TABLE IF NOT EXISTS client_document_access_logs (
    download_log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    client_user_id UUID NOT NULL REFERENCES app_users(user_id) ON DELETE CASCADE,
    document_id UUID NOT NULL,
    source_module VARCHAR(30) NOT NULL DEFAULT 'MODULE_2'
        CHECK (source_module IN ('MODULE_1', 'MODULE_2', 'MODULE_6', 'MODULE_11')),
    site_id UUID REFERENCES client_sites(site_id) ON DELETE SET NULL,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    result VARCHAR(20) NOT NULL DEFAULT 'SUCCESS'
        CHECK (result IN ('SUCCESS', 'FAILED')),
    file_type VARCHAR(20) NOT NULL DEFAULT 'PDF'
        CHECK (file_type IN ('PDF', 'CSV', 'DOCX', 'XLSX', 'OTHER')),
    access_reference VARCHAR(255)
);

CREATE INDEX IF NOT EXISTS idx_cdal_client_user ON client_document_access_logs(client_user_id);
CREATE INDEX IF NOT EXISTS idx_cdal_company ON client_document_access_logs(company_id);
CREATE INDEX IF NOT EXISTS idx_cdal_requested ON client_document_access_logs(requested_at);

-- 5. Client Portal Usage Events (Auditing & Real Metric Logging)
CREATE TABLE IF NOT EXISTS client_portal_usage_events (
    usage_event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    client_user_id UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    event_type VARCHAR(50) NOT NULL 
        CHECK (event_type IN ('FIRST_LOGIN', 'LOGIN', 'TICKET_RAISED', 'DOCUMENT_DOWNLOAD', 'PREVIEW', 'ATTENDANCE_QUERY', 'POST_ISSUE')),
    related_record_id UUID,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    source VARCHAR(30) NOT NULL DEFAULT 'MOBILE_APP'
        CHECK (source IN ('MOBILE_APP', 'WEB_PORTAL', 'ADMIN_PREVIEW'))
);

CREATE INDEX IF NOT EXISTS idx_cpue_company ON client_portal_usage_events(company_id);
CREATE INDEX IF NOT EXISTS idx_cpue_user ON client_portal_usage_events(client_user_id);
CREATE INDEX IF NOT EXISTS idx_cpue_event_time ON client_portal_usage_events(event_type, occurred_at);

-- 6. Client Announcements (Admin to Client Notices)
CREATE TABLE IF NOT EXISTS client_announcements (
    announcement_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(company_id) ON DELETE RESTRICT,
    target_client_id UUID REFERENCES clients(client_id) ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL,
    message TEXT NOT NULL,
    starts_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ends_at TIMESTAMPTZ NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE'
        CHECK (status IN ('DRAFT', 'SCHEDULED', 'ACTIVE', 'EXPIRED', 'CANCELLED')),
    created_by UUID REFERENCES app_users(user_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ca_target_status ON client_announcements(company_id, target_client_id, status);

-- 7. Helper Function to Seed Default Configuration for Company Clients
CREATE OR REPLACE FUNCTION seed_module10_company_defaults(p_company_id UUID)
RETURNS void AS $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN SELECT client_id FROM clients WHERE company_id = p_company_id LOOP
        INSERT INTO client_portal_configurations (
            company_id,
            client_id,
            future_roster_visibility,
            incident_sharing_default,
            retention_window_days,
            checkin_photo_visibility,
            invoices_enabled,
            requests_enabled,
            documents_enabled,
            announcements_enabled
        ) VALUES (
            p_company_id,
            r.client_id,
            FALSE,
            'EXPLICIT_APPROVAL',
            365,
            FALSE,
            FALSE,
            TRUE,
            TRUE,
            TRUE
        ) ON CONFLICT (client_id) DO NOTHING;
    END LOOP;
END;
$$ LANGUAGE plpgsql;
