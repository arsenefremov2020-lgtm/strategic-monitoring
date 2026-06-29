-- Adds an optional field for linking a monitoring submission to a regulatory act (НПА).
-- Apply this migration in Supabase BEFORE deploying app code that reads/writes npa_link.

ALTER TABLE monitoring_requests
ADD COLUMN IF NOT EXISTS npa_link text;
