-- 010 (DEMO 1.8): Остаточне закриття заявки після проходження
-- останньої ланки схеми погодження.
--
-- Причина: під час стрес-тестування адміністратор змінив схему
-- погодження вже ПОГОДЖЕНІЙ заявці (pages/3_Адміністрування.py,
-- блок "Підтвердити або змінити схему погодження"), і заявка знову
-- відкрилася для проходження циклу погодження — хоча вона вже мала
-- статус "Погоджено". final_locked прибирає саму можливість цього:
-- прапорець виставляється ОДИН РАЗ (коли останню ланку погоджено)
-- і фізично не може бути знятий жодним подальшим UPDATE.
--
-- Право редагувати ДАНІ (не маршрут погодження) закритої заявки
-- лишається лише за супер-адміном — окремим шляхом, який ЦЮ колонку
-- не займає (final_locked лишається true).

-- 1) Нові колонки
ALTER TABLE public.monitoring_requests
    ADD COLUMN IF NOT EXISTS final_locked    boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS final_locked_at timestamptz;

-- 2) Дозаповнення для вже погоджених заявок (щоб старі записи теж
--    потрапили під захист одразу після накатки міграції)
UPDATE public.monitoring_requests
SET final_locked = true,
    final_locked_at = COALESCE(final_locked_at, submitted_at, now())
WHERE approval_status = 'Погоджено'
  AND final_locked = false;

-- 3) Тригер-функція: якщо рядок УЖЕ final_locked = true, забороняємо
--    змінювати approval_status, chain_stage або approval_chain —
--    незалежно від того, звідки прийшов запит (Streamlit-код,
--    ручний запит у Supabase Studio, майбутній баг тощо).
--
--    Дозволено: змінювати final_locked/final_locked_at (щоб можна було
--    один раз ВСТАНОВИТИ прапорець при закритті), а також будь-які
--    інші поля (numeric_value, status, progress_text, risks, npa_link,
--    admin_comment...) — саме ці поля потрібні супер-адміну для
--    коригування даних уже закритого заходу.
CREATE OR REPLACE FUNCTION public.prevent_reopen_final_locked()
RETURNS trigger AS $$
BEGIN
    IF OLD.final_locked = true THEN
        IF NEW.approval_status IS DISTINCT FROM OLD.approval_status
           OR NEW.chain_stage    IS DISTINCT FROM OLD.chain_stage
           OR NEW.approval_chain IS DISTINCT FROM OLD.approval_chain
        THEN
            RAISE EXCEPTION
                'monitoring_requests.id=%: заявку остаточно закрито (final_locked = true) — '
                'approval_status/chain_stage/approval_chain більше не можна змінювати.',
                OLD.id
                USING ERRCODE = 'P0001';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_prevent_reopen_final_locked ON public.monitoring_requests;
CREATE TRIGGER trg_prevent_reopen_final_locked
    BEFORE UPDATE ON public.monitoring_requests
    FOR EACH ROW
    EXECUTE FUNCTION public.prevent_reopen_final_locked();

-- 4) Індекс — швидкий фільтр "закриті/відкриті" для Архіву/Дашборду
CREATE INDEX IF NOT EXISTS idx_monitoring_requests_final_locked
    ON public.monitoring_requests (final_locked);
