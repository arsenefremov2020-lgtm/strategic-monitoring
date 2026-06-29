-- Adds the manual archiving workflow: an admin/super-admin freezes a snapshot
-- of monitoring data for a year (optionally a specific quarter within it),
-- viewable later in a read-only "Архів" page without being affected by future
-- changes to calculation logic or live data.
-- Apply this migration in Supabase BEFORE deploying app code that reads/writes
-- the archive_snapshots table.

CREATE TABLE IF NOT EXISTS archive_snapshots (
    id BIGSERIAL PRIMARY KEY,
    year TEXT NOT NULL,
    quarter TEXT,
    snapshot_data JSONB NOT NULL,
    archived_by TEXT,
    archived_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_archive_snapshots_period
    ON archive_snapshots (year, quarter);
