-- ==============================================================================
-- Module 5: Deployment and Roster Schema Extension
-- Target DB: PostgreSQL 15+
-- Schema: security_erp
-- ==============================================================================

SET search_path TO security_erp, public;

-- ------------------------------------------------------------------------------
-- 1. post_slots (Translates active manpower requirements into discrete daily slots)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.post_slots (
    slot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES security_erp.companies(company_id) ON DELETE RESTRICT,
    site_id UUID NOT NULL REFERENCES security_erp.client_sites(site_id) ON DELETE RESTRICT,
    requirement_id UUID REFERENCES security_erp.site_manpower_requirements(requirement_id) ON DELETE SET NULL,
    post_type_id UUID NOT NULL REFERENCES security_erp.post_types(post_type_id) ON DELETE RESTRICT,
    shift_id UUID NOT NULL REFERENCES security_erp.site_shifts(shift_id) ON DELETE RESTRICT,
    deployment_date DATE NOT NULL,
    slot_sequence INT NOT NULL,
    slot_status VARCHAR(20) NOT NULL DEFAULT 'open'
        CHECK (slot_status IN ('open', 'filled', 'at_risk', 'cancelled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_site_shift_post_date_seq UNIQUE (site_id, shift_id, post_type_id, deployment_date, slot_sequence)
);

CREATE INDEX IF NOT EXISTS idx_post_slots_date_status ON security_erp.post_slots(deployment_date, slot_status);
CREATE INDEX IF NOT EXISTS idx_post_slots_site ON security_erp.post_slots(site_id, deployment_date);

-- ------------------------------------------------------------------------------
-- 2. rosters (Site-level calendar grouping: Draft, Published, Locked)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.rosters (
    roster_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES security_erp.companies(company_id) ON DELETE RESTRICT,
    site_id UUID NOT NULL REFERENCES security_erp.client_sites(site_id) ON DELETE RESTRICT,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'published', 'locked')),
    published_by UUID REFERENCES security_erp.app_users(user_id) ON DELETE SET NULL,
    published_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_roster_date_order CHECK (end_date >= start_date)
);

CREATE INDEX IF NOT EXISTS idx_rosters_site_dates ON security_erp.rosters(site_id, start_date, end_date);

-- ------------------------------------------------------------------------------
-- 3. roster_assignments (Permanent Assignment ID used by Module 6 Attendance)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.roster_assignments (
    assignment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES security_erp.companies(company_id) ON DELETE RESTRICT,
    slot_id UUID NOT NULL REFERENCES security_erp.post_slots(slot_id) ON DELETE RESTRICT,
    roster_id UUID REFERENCES security_erp.rosters(roster_id) ON DELETE SET NULL,
    employee_id UUID NOT NULL REFERENCES security_erp.employees(employee_id) ON DELETE RESTRICT,
    site_id UUID NOT NULL REFERENCES security_erp.client_sites(site_id) ON DELETE RESTRICT,
    shift_id UUID NOT NULL REFERENCES security_erp.site_shifts(shift_id) ON DELETE RESTRICT,
    post_type_id UUID NOT NULL REFERENCES security_erp.post_types(post_type_id) ON DELETE RESTRICT,
    deployment_date DATE NOT NULL,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    assignment_type VARCHAR(20) NOT NULL DEFAULT 'regular'
        CHECK (assignment_type IN ('regular', 'reliever', 'replacement', 'overtime', 'standby')),
    status VARCHAR(20) NOT NULL DEFAULT 'scheduled'
        CHECK (status IN ('scheduled', 'acknowledged', 'completed', 'no_show', 'cancelled')),
    is_emergency BOOLEAN NOT NULL DEFAULT FALSE,
    original_assignment_id UUID REFERENCES security_erp.roster_assignments(assignment_id) ON DELETE SET NULL,
    created_by_user_id UUID REFERENCES security_erp.app_users(user_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_assignment_time_order CHECK (end_time > start_time)
);

CREATE INDEX IF NOT EXISTS idx_assignments_guard_date ON security_erp.roster_assignments(employee_id, deployment_date);
CREATE INDEX IF NOT EXISTS idx_assignments_slot ON security_erp.roster_assignments(slot_id);
CREATE INDEX IF NOT EXISTS idx_assignments_interval ON security_erp.roster_assignments(start_time, end_time);

-- ------------------------------------------------------------------------------
-- 4. assignment_history (Append-only audit trail of roster changes)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.assignment_history (
    history_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assignment_id UUID NOT NULL REFERENCES security_erp.roster_assignments(assignment_id) ON DELETE CASCADE,
    action VARCHAR(30) NOT NULL
        CHECK (action IN ('created', 'updated', 'cancelled', 'locked', 'swapped', 'replaced', 'no_show')),
    previous_values JSONB,
    new_values JSONB,
    actor_user_id UUID REFERENCES security_erp.app_users(user_id) ON DELETE SET NULL,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_assignment_history_assign ON security_erp.assignment_history(assignment_id, created_at);

-- ------------------------------------------------------------------------------
-- 5. shift_swap_requests (Atomic shift exchange between guards on the same site)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.shift_swap_requests (
    swap_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES security_erp.companies(company_id) ON DELETE RESTRICT,
    site_id UUID NOT NULL REFERENCES security_erp.client_sites(site_id) ON DELETE RESTRICT,
    requesting_employee_id UUID NOT NULL REFERENCES security_erp.employees(employee_id) ON DELETE RESTRICT,
    target_employee_id UUID NOT NULL REFERENCES security_erp.employees(employee_id) ON DELETE RESTRICT,
    assignment_a_id UUID NOT NULL REFERENCES security_erp.roster_assignments(assignment_id) ON DELETE RESTRICT,
    assignment_b_id UUID NOT NULL REFERENCES security_erp.roster_assignments(assignment_id) ON DELETE RESTRICT,
    reason TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected', 'cancelled')),
    reviewed_by_user_id UUID REFERENCES security_erp.app_users(user_id) ON DELETE SET NULL,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------------------
-- 6. emergency_ratifications (Supervisors urgent deployment requiring Admin ratification)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.emergency_ratifications (
    ratification_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assignment_id UUID NOT NULL REFERENCES security_erp.roster_assignments(assignment_id) ON DELETE CASCADE,
    supervisor_user_id UUID NOT NULL REFERENCES security_erp.app_users(user_id) ON DELETE RESTRICT,
    admin_user_id UUID REFERENCES security_erp.app_users(user_id) ON DELETE SET NULL,
    reason TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'ratified', 'rejected', 'overdue')),
    deadline TIMESTAMPTZ NOT NULL,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------------------
-- 7. duty_acknowledgements (Guard digital duty receipt tracking)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.duty_acknowledgements (
    acknowledgement_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assignment_id UUID NOT NULL REFERENCES security_erp.roster_assignments(assignment_id) ON DELETE CASCADE,
    employee_id UUID NOT NULL REFERENCES security_erp.employees(employee_id) ON DELETE RESTRICT,
    acknowledged_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    device_id VARCHAR(100),
    ip_address VARCHAR(50),
    CONSTRAINT uq_assignment_acknowledgement UNIQUE (assignment_id)
);

-- ------------------------------------------------------------------------------
-- 8. overtime_records (Operational tracking for future Module 14 payroll)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.overtime_records (
    overtime_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assignment_id UUID NOT NULL REFERENCES security_erp.roster_assignments(assignment_id) ON DELETE CASCADE,
    threshold_type VARCHAR(20) NOT NULL CHECK (threshold_type IN ('daily', 'weekly')),
    flagged_hours NUMERIC(4,2) NOT NULL,
    approval_status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (approval_status IN ('pending', 'approved', 'rejected')),
    approved_by_user_id UUID REFERENCES security_erp.app_users(user_id) ON DELETE SET NULL,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------------------
-- 9. reliever_pool_memberships (Designated standby and reliever guards)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_erp.reliever_pool_memberships (
    membership_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES security_erp.companies(company_id) ON DELETE RESTRICT,
    employee_id UUID NOT NULL REFERENCES security_erp.employees(employee_id) ON DELETE RESTRICT,
    pool_type VARCHAR(20) NOT NULL DEFAULT 'reliever' CHECK (pool_type IN ('reliever', 'standby')),
    effective_start DATE NOT NULL,
    effective_end DATE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------------------
-- 10. Seed Configuration Settings for Module 5
-- ------------------------------------------------------------------------------
INSERT INTO security_erp.system_settings (company_id, key, value)
SELECT 
    c.company_id,
    s.key,
    s.value
FROM security_erp.companies c
CROSS JOIN (
    VALUES 
        ('rolling_slot_window_days', '14'),
        ('min_rest_gap_hours', '8'),
        ('max_consecutive_days', '6'),
        ('weekly_hours_warning_limit', '48'),
        ('daily_overtime_threshold_hours', '8.0'),
        ('supervisor_future_edit_days', '7'),
        ('emergency_ratification_hours', '24')
) AS s(key, value)
ON CONFLICT (company_id, key) DO NOTHING;
