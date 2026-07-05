-- 005: Узгодження типів, час у UTC, прибирання зайвого (DEMO 1.7)

-- 1) year: text (весь код і суміжні таблиці працюють із текстом)
ALTER TABLE public.monitoring_requests
    ALTER COLUMN year TYPE text USING COALESCE(year::text, '');

-- 2) Час — з часовою зоною (існуючі значення трактуються як UTC)
ALTER TABLE public.monitoring_requests
    ALTER COLUMN submitted_at TYPE timestamptz USING submitted_at AT TIME ZONE 'UTC',
    ALTER COLUMN created_at   TYPE timestamptz USING created_at   AT TIME ZONE 'UTC';
ALTER TABLE public.monitoring_logs
    ALTER COLUMN changed_at   TYPE timestamptz USING changed_at   AT TIME ZONE 'UTC';

-- 3) Зайве: колонка, яку код ніколи не використовував
ALTER TABLE public.monitoring_requests
    DROP COLUMN IF EXISTS evidence_links;

-- 4) Зайве: таблиця-залишок тестів (кодом не використовується)
DROP TABLE IF EXISTS public.chat_messages;
