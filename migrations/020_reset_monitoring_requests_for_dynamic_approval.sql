-- 020_reset_monitoring_requests_for_dynamic_approval.sql
-- Чистий старт тестування динамічного маршруту погодження (Частина 2).
-- Застосовувати вручну під час деплою, коли роботу із заявками тимчасово зупинено.

begin;

-- 1. Видаляємо журнал дій старих моніторингових заявок.
-- Саме monitoring_logs містить також історію їхніх переходів погодження.
delete from public.monitoring_logs
where request_id in (
    select id from public.monitoring_requests
);

-- 2. Видаляємо всі збережені версії старих моніторингових заявок.
delete from public.monitoring_request_versions
where request_id in (
    select id from public.monitoring_requests
);

-- 3. Після очищення залежних записів видаляємо самі старі заявки.
-- Таблиця блокувань періодів, чернетки, довідники та налаштування не змінюються.
-- Записи ручних закриттів не видаляються і не оновлюються цією міграцією явно;
-- наявний зовнішній ключ сам обнулить лише dispute_request_id, якщо він посилався
-- на видалену моніторингову заявку.
delete from public.monitoring_requests;

commit;
