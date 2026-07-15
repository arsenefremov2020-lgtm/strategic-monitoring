-- ДЕМО 2.0, Етап 5: атомарність, дублікати і фактичні дані ручного закриття.
-- Виконувати після міграції 014. У кінці ROLLBACK — тестові дані не залишаються.

begin;

create temporary table stage5_test_result (
    check_name text not null,
    passed boolean not null,
    details text not null
) on commit drop;

-- 1. Успішне пряме закриття супер-адміном створює closeout + офіційну заявку.
do $$
declare
    v_code text := '__DEMO2_STAGE5_SUCCESS__' || txid_current()::text;
    v_result jsonb;
    v_closeout_id bigint;
    v_request_id bigint;
    v_request public.monitoring_requests%rowtype;
    v_versions integer;
    v_logs integer;
begin
    v_result := public.transition_create_closeout(
        jsonb_build_object(
            'strat_code', v_code,
            'period_year', 2099,
            'period_quarter', 4,
            'scope', 'Квартал',
            'admin_id', 'Тестовий супер-адмін',
            'admin_email', 'stage5-super@example.invalid',
            'reason', 'Тестова підстава',
            'evidence_note', 'Ризики відсутні',
            'approval_status', 'Підтверджено',
            'fact_status', 'Частково виконано',
            'fact_numeric_value', 75,
            'fact_progress_text', 'Виконано 75 відсотків тестового заходу',
            'department', 'TEST',
            'object_name', 'Тестовий захід',
            'indicator_name', 'Тестовий індикатор'
        ),
        jsonb_build_object(
            'email', 'stage5-super@example.invalid',
            'name', 'Тестовий супер-адмін',
            'role', 'super_admin'
        )
    );

    v_closeout_id := (v_result->>'closeout_id')::bigint;
    v_request_id := (v_result->'request_ids'->>0)::bigint;

    select * into v_request
      from public.monitoring_requests
     where id = v_request_id;

    select count(*) into v_versions
      from public.monitoring_request_versions
     where request_id = v_request_id;

    select count(*) into v_logs
      from public.monitoring_logs
     where request_id = v_request_id
       and action = 'Ручне закриття: створено офіційні фактичні дані';

    insert into stage5_test_result values
        ('Успішне ручне закриття повернуло success',
         coalesce((v_result->>'success')::boolean, false), v_result::text),
        ('Створено погоджену final_locked заявку з фактичними даними',
         v_request.approval_status = 'Погоджено'
         and v_request.final_locked
         and v_request.status = 'Частково виконано'
         and v_request.numeric_value = 75,
         'request_id=' || coalesce(v_request_id::text, 'NULL')),
        ('Створено версію і журнал офіційної заявки',
         v_versions = 1 and v_logs = 1,
         'versions=' || v_versions || '; logs=' || v_logs),
        ('Closeout зберіг зв’язок з офіційною заявкою',
         exists (
             select 1 from public.closeout_requests
             where id = v_closeout_id
               and materialized_request_ids @> jsonb_build_array(v_request_id)
         ),
         'closeout_id=' || coalesce(v_closeout_id::text, 'NULL'));
end;
$$;

-- 2. Другий активний запит по тому самому періоду відхиляється.
do $$
declare
    v_code text := '__DEMO2_STAGE5_DUP__' || txid_current()::text;
    v_first jsonb;
    v_second jsonb;
    v_count integer;
    v_payload jsonb;
begin
    v_payload := jsonb_build_object(
        'strat_code', v_code,
        'period_year', 2098,
        'period_quarter', 1,
        'scope', 'Квартал',
        'admin_id', 'Тестовий адміністратор',
        'admin_email', 'stage5-admin@example.invalid',
        'reason', 'Тест дубля',
        'approval_status', 'Очікує підтвердження',
        'fact_status', 'Виконано',
        'fact_numeric_value', 1,
        'fact_progress_text', 'Тестові фактичні дані'
    );
    v_first := public.transition_create_closeout(
        v_payload,
        jsonb_build_object('email','stage5-admin@example.invalid','name','Тест','role','admin')
    );
    v_second := public.transition_create_closeout(
        v_payload,
        jsonb_build_object('email','stage5-admin@example.invalid','name','Тест','role','admin')
    );

    select count(*) into v_count
      from public.closeout_requests
     where strat_code = v_code
       and approval_status in ('Очікує підтвердження','Підтверджено');

    insert into stage5_test_result values
        ('Перший активний запит створено',
         coalesce((v_first->>'success')::boolean, false), v_first::text),
        ('Другий активний запит відхилено зрозуміло',
         coalesce((v_second->>'success')::boolean, false) = false
         and v_second->>'code' = 'duplicate_active_closeout'
         and position('вже подано' in lower(v_second->>'message')) > 0,
         v_second::text),
        ('У базі лишився один активний запит',
         v_count = 1, 'active=' || v_count);
end;
$$;

-- 3. Штучна помилка журналу відкочує і closeout, і офіційну заявку.
create or replace function pg_temp.stage5_force_log_failure()
returns trigger
language plpgsql
as $$
begin
    if new.action = 'Ручне закриття: створено офіційні фактичні дані' then
        raise exception 'DEMO2_STAGE5_FORCE_FAILURE';
    end if;
    return new;
end;
$$;

create trigger trg_stage5_force_log_failure
before insert on public.monitoring_logs
for each row execute function pg_temp.stage5_force_log_failure();

do $$
declare
    v_code text := '__DEMO2_STAGE5_ROLLBACK__' || txid_current()::text;
    v_failed boolean := false;
    v_closeouts integer;
    v_requests integer;
begin
    begin
        perform public.transition_create_closeout(
            jsonb_build_object(
                'strat_code', v_code,
                'period_year', 2097,
                'period_quarter', 2,
                'scope', 'Квартал',
                'admin_id', 'Тестовий супер-адмін',
                'admin_email', 'stage5-super@example.invalid',
                'reason', 'Тест відкочування',
                'approval_status', 'Підтверджено',
                'fact_status', 'Виконано',
                'fact_numeric_value', 100,
                'fact_progress_text', 'Має бути відкочено'
            ),
            jsonb_build_object(
                'email','stage5-super@example.invalid',
                'name','Тестовий супер-адмін',
                'role','super_admin'
            )
        );
    exception when others then
        v_failed := true;
    end;

    select count(*) into v_closeouts
      from public.closeout_requests where strat_code = v_code;
    select count(*) into v_requests
      from public.monitoring_requests where strat_code = v_code;

    insert into stage5_test_result values
        ('Штучна помилка журналу спрацювала', v_failed, 'failed=' || v_failed),
        ('Після помилки не залишилось напівзакриття',
         v_closeouts = 0 and v_requests = 0,
         'closeouts=' || v_closeouts || '; requests=' || v_requests);
end;
$$;

select check_name, passed, details
from stage5_test_result
order by check_name;

rollback;
