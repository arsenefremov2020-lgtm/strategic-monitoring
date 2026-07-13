-- ДЕМО 2.0 — Етап 2: перевірка атомарності переходу.
--
-- Виконувати ПІСЛЯ міграції 012 у Supabase SQL Editor.
-- Скрипт створює один тимчасовий запис, штучно перериває операцію на етапі
-- запису журналу, перевіряє повний відкат і наприкінці робить ROLLBACK.
-- Жодних тестових даних після завершення не залишається.

begin;

create temporary table stage2_atomic_test_result (
    check_name text not null,
    passed boolean not null,
    details text not null
) on commit drop;

create or replace function pg_temp.stage2_force_log_failure()
returns trigger
language plpgsql
as $$
begin
    if new.action = 'DEMO2_ATOMIC_TEST_FORCE_FAILURE' then
        raise exception 'DEMO2: штучний обрив перед записом журналу';
    end if;
    return new;
end;
$$;

create trigger trg_stage2_force_log_failure
before insert on public.monitoring_logs
for each row
execute function pg_temp.stage2_force_log_failure();

do $$
declare
    v_request_id bigint;
    v_result jsonb;
    v_interrupted boolean := false;
    v_status text;
    v_stage integer;
    v_versions integer;
    v_logs integer;
begin
    insert into public.monitoring_requests (
        year,
        quarter,
        strat_code,
        status,
        approval_status,
        chain_stage,
        object_kind,
        object_name,
        final_locked
    ) values (
        2099,
        4,
        '__DEMO2_ATOMIC_TEST__' || txid_current()::text,
        'Частково виконано',
        'Очікує погодження',
        0,
        'measure',
        'Тимчасова заявка для перевірки атомарності',
        false
    ) returning id into v_request_id;

    begin
        v_result := public.transition_approve_request_step(
            v_request_id,
            'Очікує погодження',
            0,
            'Очікує: Керівник ССП',
            1,
            '[]',
            'Тест атомарності',
            'DEMO2_ATOMIC_TEST_FORCE_FAILURE',
            jsonb_build_object(
                'email', 'atomic-test@example.invalid',
                'name', 'Тест атомарності',
                'role', 'system'
            ),
            'Тест атомарності'
        );
    exception
        when others then
            v_interrupted := true;
    end;

    select approval_status, chain_stage
      into v_status, v_stage
      from public.monitoring_requests
     where id = v_request_id;

    select count(*) into v_versions
      from public.monitoring_request_versions
     where request_id = v_request_id;

    select count(*) into v_logs
      from public.monitoring_logs
     where request_id = v_request_id
       and action = 'DEMO2_ATOMIC_TEST_FORCE_FAILURE';

    insert into stage2_atomic_test_result(check_name, passed, details)
    values
        (
            'Штучний обрив спрацював',
            v_interrupted,
            'interrupted=' || v_interrupted::text
        ),
        (
            'Статус і ланка не змінилися',
            v_status = 'Очікує погодження' and coalesce(v_stage, 0) = 0,
            'status=' || coalesce(v_status, 'NULL') || '; stage=' || coalesce(v_stage::text, 'NULL')
        ),
        (
            'Часткові версії не залишилися',
            v_versions = 0,
            'versions=' || v_versions::text
        ),
        (
            'Частковий журнал не залишився',
            v_logs = 0,
            'logs=' || v_logs::text
        );

    if not v_interrupted
       or v_status <> 'Очікує погодження'
       or coalesce(v_stage, 0) <> 0
       or v_versions <> 0
       or v_logs <> 0
    then
        raise exception 'Перевірку атомарності не пройдено.';
    end if;
end;
$$;

select check_name, passed, details
from stage2_atomic_test_result
order by check_name;

rollback;
