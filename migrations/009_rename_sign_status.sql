-- 009 (DEMO 1.7.3): Відмова від слова «підпис» у статусах.
-- Система не накладає КЕП, тому «Направлено на підпис» → «Очікує: Керівник ССП»
-- (єдиний стиль із рештою ланок «Очікує: …»).

-- 1) Тимчасово зняти CHECK, щоб оновити наявні записи
ALTER TABLE public.monitoring_requests
    DROP CONSTRAINT IF EXISTS chk_approval_status;

-- 2) Мігрувати наявні заявки
UPDATE public.monitoring_requests
    SET approval_status = 'Очікує: Керівник ССП'
    WHERE approval_status = 'Направлено на підпис';

-- 3) Оновити журнал дій (щоб історія читалася коректно)
UPDATE public.monitoring_logs
    SET old_status = 'Очікує: Керівник ССП'
    WHERE old_status = 'Направлено на підпис';
UPDATE public.monitoring_logs
    SET new_status = 'Очікує: Керівник ССП'
    WHERE new_status = 'Направлено на підпис';

-- 4) Повернути CHECK з оновленим словником
ALTER TABLE public.monitoring_requests
    ADD CONSTRAINT chk_approval_status CHECK (approval_status IN (
        'Очікує погодження',
        'Очікує: Керівник ССП',
        'Очікує: Керівник управління',
        'Очікує: Заступник керівника ССП',
        'Повернуто на доопрацювання',
        'Погоджено'
    ));
