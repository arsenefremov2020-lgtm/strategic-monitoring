-- 006: Індекси під зростання даних (DEMO 1.7)
CREATE INDEX IF NOT EXISTS idx_monitoring_requests_code_period
    ON public.monitoring_requests (strat_code, year, quarter);
CREATE INDEX IF NOT EXISTS idx_monitoring_requests_approval_status
    ON public.monitoring_requests (approval_status);
