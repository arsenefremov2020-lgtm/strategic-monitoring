-- 008 (DEMO 1.7.1): Дозапис колонок closeout_requests, які були додані
-- вручну в Supabase і не були зафіксовані в міграціях (відтворюваність).
-- Безпечний до повторного запуску; на живій БД нічого не змінює.

ALTER TABLE public.closeout_requests
    ADD COLUMN IF NOT EXISTS npa_links          text,
    ADD COLUMN IF NOT EXISTS scope              text DEFAULT 'Квартал',
    ADD COLUMN IF NOT EXISTS head_status        text,
    ADD COLUMN IF NOT EXISTS head_comment       text,
    ADD COLUMN IF NOT EXISTS head_email         text,
    ADD COLUMN IF NOT EXISTS dispute_request_id bigint,
    ADD COLUMN IF NOT EXISTS dispute_note       text,
    ADD COLUMN IF NOT EXISTS dispute_status     text;
