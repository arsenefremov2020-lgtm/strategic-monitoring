-- Adds the closeout-request workflow: an admin requests manual closure of a
-- measure/period, a super-admin approves or rejects it.
-- Apply this migration in Supabase BEFORE deploying app code that reads/writes
-- the closeout_requests table.

CREATE TABLE IF NOT EXISTS closeout_requests (
    id BIGSERIAL PRIMARY KEY,
    strat_code TEXT NOT NULL,
    period_year TEXT NOT NULL,
    period_quarter TEXT NOT NULL,
    admin_id TEXT,
    admin_email TEXT,
    reason TEXT NOT NULL,
    evidence_note TEXT,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    approval_status TEXT NOT NULL DEFAULT 'Очікує підтвердження',
    superadmin_id TEXT,
    decided_at TIMESTAMPTZ,
    decision_comment TEXT
);

CREATE INDEX IF NOT EXISTS idx_closeout_requests_period
    ON closeout_requests (strat_code, period_year, period_quarter);
