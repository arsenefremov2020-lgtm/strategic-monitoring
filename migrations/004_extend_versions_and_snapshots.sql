-- 004: Розширення знімків версій заявок + знімки назв у заявках (DEMO 1.7)
-- Виправляє: у версіях губився маршрут погодження і посилання на НПА;
-- додає механізм П7/П8 (назва заходу/показника на момент подання).

-- 1) monitoring_requests: знімки назв (П7/П8)
ALTER TABLE public.monitoring_requests
    ADD COLUMN IF NOT EXISTS object_name    text DEFAULT '',
    ADD COLUMN IF NOT EXISTS indicator_name text DEFAULT '';

-- 2) monitoring_request_versions: повний контекст версії
ALTER TABLE public.monitoring_request_versions
    ADD COLUMN IF NOT EXISTS npa_link       text    DEFAULT '',
    ADD COLUMN IF NOT EXISTS approval_chain text    DEFAULT '',
    ADD COLUMN IF NOT EXISTS chain_stage    integer DEFAULT 0,
    ADD COLUMN IF NOT EXISTS scheme_label   text    DEFAULT '',
    ADD COLUMN IF NOT EXISTS object_kind    text    DEFAULT '',
    ADD COLUMN IF NOT EXISTS object_name    text    DEFAULT '',
    ADD COLUMN IF NOT EXISTS indicator_name text    DEFAULT '',
    ADD COLUMN IF NOT EXISTS as_of_date     text    DEFAULT '';
