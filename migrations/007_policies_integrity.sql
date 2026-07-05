-- 007 (DEMO 1.7.1): Функціональні виправлення БД
--
-- 1) RLS-політики для таблиць, де RLS було ввімкнено БЕЗ жодної політики —
--    через це ручні закриття, архівні знімки та журнал сповіщень НЕ
--    працювали з ключем застосунку (читання = порожньо, запис = помилка).
--    Політики тимчасово дозвільні (як у monitoring_request_versions);
--    вони будуть звужені на етапі безпеки (RLS + розділення ключів).
--
-- 2) Цілісність: зовнішні ключі, захист від дублікатів заявок заходів,
--    словникові CHECK-обмеження статусів.

-- ── 1. Політики (усунення «мертвих» таблиць) ──
DROP POLICY IF EXISTS closeout_all_select ON public.closeout_requests;
DROP POLICY IF EXISTS closeout_all_insert ON public.closeout_requests;
DROP POLICY IF EXISTS closeout_all_update ON public.closeout_requests;
CREATE POLICY closeout_all_select ON public.closeout_requests FOR SELECT USING (true);
CREATE POLICY closeout_all_insert ON public.closeout_requests FOR INSERT WITH CHECK (true);
CREATE POLICY closeout_all_update ON public.closeout_requests FOR UPDATE USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS snapshots_all_select ON public.archive_snapshots;
DROP POLICY IF EXISTS snapshots_all_insert ON public.archive_snapshots;
CREATE POLICY snapshots_all_select ON public.archive_snapshots FOR SELECT USING (true);
CREATE POLICY snapshots_all_insert ON public.archive_snapshots FOR INSERT WITH CHECK (true);

DROP POLICY IF EXISTS notiflog_all_select ON public.notification_log;
DROP POLICY IF EXISTS notiflog_all_insert ON public.notification_log;
CREATE POLICY notiflog_all_select ON public.notification_log FOR SELECT USING (true);
CREATE POLICY notiflog_all_insert ON public.notification_log FOR INSERT WITH CHECK (true);

-- ── 2. Зовнішні ключі (журнал/версії/спори не можуть посилатися в нікуди) ──
ALTER TABLE public.monitoring_logs
    DROP CONSTRAINT IF EXISTS fk_logs_request,
    ADD CONSTRAINT fk_logs_request
        FOREIGN KEY (request_id) REFERENCES public.monitoring_requests(id)
        ON DELETE CASCADE;

ALTER TABLE public.monitoring_request_versions
    DROP CONSTRAINT IF EXISTS fk_versions_request,
    ADD CONSTRAINT fk_versions_request
        FOREIGN KEY (request_id) REFERENCES public.monitoring_requests(id)
        ON DELETE CASCADE;

ALTER TABLE public.closeout_requests
    DROP CONSTRAINT IF EXISTS fk_closeout_dispute_request,
    ADD CONSTRAINT fk_closeout_dispute_request
        FOREIGN KEY (dispute_request_id) REFERENCES public.monitoring_requests(id)
        ON DELETE SET NULL;

-- ── 3. Захист від дублікатів заявок ЗАХОДІВ за період
--     (індикатори можуть подаватися повторно в межах кварталу — їх не чіпаємо) ──
CREATE UNIQUE INDEX IF NOT EXISTS uq_measure_request_per_period
    ON public.monitoring_requests (strat_code, year, quarter)
    WHERE object_kind = 'measure';

-- Захист від двох ПІДТВЕРДЖЕНИХ ручних закриттів одного періоду
CREATE UNIQUE INDEX IF NOT EXISTS uq_confirmed_closeout_per_period
    ON public.closeout_requests (strat_code, period_year, period_quarter)
    WHERE approval_status = 'Підтверджено';

-- ── 4. Словникові обмеження статусів (єдина модель) ──
ALTER TABLE public.monitoring_requests
    DROP CONSTRAINT IF EXISTS chk_approval_status,
    ADD CONSTRAINT chk_approval_status CHECK (approval_status IN (
        'Очікує погодження',
        'Направлено на підпис',
        'Очікує: Керівник управління',
        'Очікує: Заступник керівника ССП',
        'Повернуто на доопрацювання',
        'Погоджено'
    ));

ALTER TABLE public.monitoring_requests
    DROP CONSTRAINT IF EXISTS chk_execution_status,
    ADD CONSTRAINT chk_execution_status CHECK (status IN (
        'Виконано',
        'Частково виконано',
        'Не виконано',
        'Не настав час',
        'Втратило актуальність'
    ));

ALTER TABLE public.monitoring_requests
    DROP CONSTRAINT IF EXISTS chk_object_kind,
    ADD CONSTRAINT chk_object_kind CHECK (object_kind IN ('measure', 'indicator'));
