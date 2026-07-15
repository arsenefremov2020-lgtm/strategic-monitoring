-- Етап 6: тест незмінності та атомарного створення архіву.
-- Завершується ROLLBACK; тестові дані не залишаються.

begin;

create temporary table stage6_test_result (
    check_name text not null,
    passed boolean not null,
    details text not null
) on commit drop;

do $$
declare
    v_result jsonb;
    v_snapshot_id bigint;
    v_update_blocked boolean := false;
    v_delete_blocked boolean := false;
    v_count integer;
begin
    -- Для базової перевірки використовуємо ручний знімок, щоб тест був
    -- незалежним від того, чи вже створено автоматичний знімок сьогодні.
    v_result := public.transition_create_archive_snapshot(
        jsonb_build_object(
            'schema_version', 'TEST',
            'generated_at_utc', now()::text,
            'snapshot_type', 'manual',
            'reason', 'Тест атомарного архівного знімка',
            'payload_size_bytes', 4,
            'coverage_label', 'Тестовий період',
            'request_count', 1,
            'version_count', 1,
            'measure_count', 1,
            'mio_record_count', 1,
            'log_count', 1,
            'closeout_count', 0,
            'anchor_year', 2099,
            'anchor_quarter', 1
        ),
        'H4sI',
        jsonb_build_object(
            'email', 'stage6-test@example.invalid',
            'name', 'Тест Етапу 6',
            'role', 'super_admin'
        )
    );

    v_snapshot_id := nullif(v_result->>'snapshot_id', '')::bigint;

    insert into stage6_test_result values (
        'Знімок створено через атомарну функцію',
        coalesce((v_result->>'success')::boolean, false) and v_snapshot_id is not null,
        'result=' || v_result::text
    );

    select count(*) into v_count
    from public.monitoring_logs
    where related_table = 'archive_snapshots'
      and related_key = v_snapshot_id::text;

    insert into stage6_test_result values (
        'Створення знімка записано в журнал',
        v_count = 1,
        'logs=' || v_count::text
    );

    begin
        update public.archive_snapshots
           set reason = 'Спроба зміни'
         where id = v_snapshot_id;
    exception when sqlstate '55000' then
        v_update_blocked := true;
    end;

    insert into stage6_test_result values (
        'Пряме UPDATE архівного рядка заблоковано',
        v_update_blocked,
        'blocked=' || v_update_blocked::text
    );

    begin
        delete from public.archive_snapshots where id = v_snapshot_id;
    exception when sqlstate '55000' then
        v_delete_blocked := true;
    end;

    insert into stage6_test_result values (
        'Пряме DELETE архівного рядка заблоковано',
        v_delete_blocked,
        'blocked=' || v_delete_blocked::text
    );
end;
$$;

do $$
declare
    v_first jsonb;
    v_duplicate jsonb;
    v_existing_id bigint;
begin
    select id into v_existing_id
    from public.archive_snapshots
    where snapshot_type = 'automatic'
      and snapshot_day_kyiv = (now() at time zone 'Europe/Kyiv')::date
    limit 1;

    if v_existing_id is null then
        v_first := public.transition_create_archive_snapshot(
            jsonb_build_object(
                'snapshot_type', 'automatic',
                'reason', 'Перший автоматичний знімок для тесту дублювання',
                'payload_size_bytes', 4,
                'anchor_year', 2099,
                'anchor_quarter', 1
            ),
            'H4sI',
            jsonb_build_object(
                'email', 'stage6-test@example.invalid',
                'name', 'Тест Етапу 6',
                'role', 'system'
            )
        );

        if not coalesce((v_first->>'success')::boolean, false) then
            raise exception 'Не вдалося підготувати перший автоматичний знімок: %', v_first;
        end if;
    end if;

    v_duplicate := public.transition_create_archive_snapshot(
        jsonb_build_object(
            'snapshot_type', 'automatic',
            'reason', 'Другий автоматичний знімок того самого дня',
            'payload_size_bytes', 4,
            'anchor_year', 2099,
            'anchor_quarter', 1
        ),
        'H4sI',
        jsonb_build_object(
            'email', 'stage6-test@example.invalid',
            'name', 'Тест Етапу 6',
            'role', 'system'
        )
    );

    insert into stage6_test_result values (
        'Другий автоматичний знімок того самого дня відхилено',
        coalesce((v_duplicate->>'success')::boolean, false) = false
            and v_duplicate->>'code' = 'automatic_snapshot_exists',
        'result=' || v_duplicate::text
    );
end;
$$;

create or replace function pg_temp.stage6_force_archive_log_failure()
returns trigger
language plpgsql
as $$
begin
    if new.related_table = 'archive_snapshots'
       and new.admin_comment = 'DEMO2_STAGE6_FORCE_FAILURE' then
        raise exception 'DEMO2: штучна помилка журналу архіву';
    end if;
    return new;
end;
$$;

create trigger trg_stage6_force_archive_log_failure
before insert on public.monitoring_logs
for each row
execute function pg_temp.stage6_force_archive_log_failure();

do $$
declare
    v_failed boolean := false;
    v_snapshots integer;
    v_logs integer;
begin
    begin
        perform public.transition_create_archive_snapshot(
            jsonb_build_object(
                'snapshot_type', 'manual',
                'reason', 'DEMO2_STAGE6_FORCE_FAILURE',
                'payload_size_bytes', 4,
                'anchor_year', 2099,
                'anchor_quarter', 1
            ),
            'H4sI',
            jsonb_build_object(
                'email', 'stage6-test@example.invalid',
                'name', 'Тест атомарності',
                'role', 'super_admin'
            )
        );
    exception when others then
        v_failed := true;
    end;

    select count(*) into v_snapshots
    from public.archive_snapshots
    where reason = 'DEMO2_STAGE6_FORCE_FAILURE';

    select count(*) into v_logs
    from public.monitoring_logs
    where related_table = 'archive_snapshots'
      and admin_comment = 'DEMO2_STAGE6_FORCE_FAILURE';

    insert into stage6_test_result values (
        'Помилка журналу не залишає напівстворений знімок',
        v_failed and v_snapshots = 0 and v_logs = 0,
        'failed=' || v_failed::text
            || '; snapshots=' || v_snapshots::text
            || '; logs=' || v_logs::text
    );
end;
$$;

do $$
declare
    v_old jsonb;
    v_new jsonb;
    v_old_id bigint;
    v_new_id bigint;
    v_count integer;
begin
    v_old := public.transition_create_archive_snapshot(
        jsonb_build_object(
            'snapshot_type', 'manual',
            'reason', 'Початковий ручний знімок',
            'payload_size_bytes', 4,
            'anchor_year', 2099,
            'anchor_quarter', 1
        ),
        'H4sI',
        jsonb_build_object('email', 'stage6-test@example.invalid', 'name', 'Тест', 'role', 'super_admin')
    );
    v_old_id := (v_old->>'snapshot_id')::bigint;

    v_new := public.transition_create_archive_snapshot(
        jsonb_build_object(
            'snapshot_type', 'manual',
            'reason', 'Новий знімок після виправлення живих даних',
            'replacement_reason', 'Виправлено тестову помилку',
            'replaces_snapshot_id', v_old_id,
            'payload_size_bytes', 4,
            'anchor_year', 2099,
            'anchor_quarter', 1
        ),
        'H4sI',
        jsonb_build_object('email', 'stage6-test@example.invalid', 'name', 'Тест', 'role', 'super_admin')
    );
    v_new_id := (v_new->>'snapshot_id')::bigint;

    insert into stage6_test_result values (
        'Знімок-заміна містить зв’язок зі старим',
        v_new_id is not null and exists (
            select 1 from public.archive_snapshots
            where id = v_new_id
              and replaces_snapshot_id = v_old_id
              and replacement_reason = 'Виправлено тестову помилку'
        ),
        'old=' || v_old_id::text || '; new=' || coalesce(v_new_id::text, 'NULL')
    );

    select count(*) into v_count
    from public.monitoring_logs
    where related_table = 'archive_snapshots'
      and related_key = v_old_id::text
      and action = 'Архівний знімок має новішу версію';

    insert into stage6_test_result values (
        'Подію заміни записано в журнал старого знімка',
        v_count = 1,
        'logs=' || v_count::text
    );
end;
$$;

select check_name, passed, details
from stage6_test_result
order by check_name;

rollback;
