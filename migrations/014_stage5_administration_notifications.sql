-- 014 (ДЕМО 2.0, Етап 5): ручне закриття з фактичними даними,
-- заборона активних дублікатів і матеріалізація офіційної заявки.
-- Виконати після 013_session_drafts_atomic_submission.sql.

begin;

-- Ж2: фактичні дані, що підтверджуються разом із ручним закриттям.
alter table public.closeout_requests
    add column if not exists fact_status text,
    add column if not exists fact_numeric_value numeric,
    add column if not exists fact_value_text text,
    add column if not exists fact_progress_text text,
    add column if not exists department text,
    add column if not exists object_name text,
    add column if not exists indicator_name text,
    add column if not exists materialized_request_ids jsonb not null default '[]'::jsonb;

alter table public.closeout_requests
    drop constraint if exists chk_closeout_fact_status;

alter table public.closeout_requests
    add constraint chk_closeout_fact_status
    check (
        fact_status is null
        or fact_status in (
            'Виконано',
            'Частково виконано',
            'Не виконано',
            'Не настав час',
            'Втратило актуальність'
        )
    );

-- Наявні тестові дублікати: зберігаємо найперший активний запит у кожній
-- групі, а пізніші позначаємо скасованими. Рядки не видаляються.
-- У поточній базі це означає: лишити №3, скасувати №4 і №5 для
-- заходу 1.1.1., I квартал 2026 року.
do $$
declare
    v_row record;
    v_version integer;
begin
    for v_row in
        with ranked as (
            select
                id,
                first_value(id) over (
                    partition by strat_code, period_year, coalesce(period_quarter, 0)
                    order by requested_at, id
                ) as keep_id,
                row_number() over (
                    partition by strat_code, period_year, coalesce(period_quarter, 0)
                    order by requested_at, id
                ) as rn
            from public.closeout_requests
            where approval_status in ('Очікує підтвердження', 'Підтверджено')
        )
        select r.id, r.keep_id, c.approval_status as old_status
        from ranked r
        join public.closeout_requests c on c.id = r.id
        where rn > 1
        order by id
    loop
        update public.closeout_requests
           set approval_status = 'Скасовано',
               superseded_by_request_id = v_row.keep_id,
               decided_at = coalesce(decided_at, now()),
               decision_comment = concat_ws(
                   ' ',
                   nullif(btrim(coalesce(decision_comment, '')), ''),
                   'Скасовано як дубль під час Етапу 5; чинним лишено перший активний запит №'
                       || v_row.keep_id::text || '.'
               )
         where id = v_row.id;

        v_version := monitoring_internal.snapshot_closeout(
            v_row.id,
            'Етап 5 / скасування дубліката ручного закриття'
        );

        perform monitoring_internal.write_log(
            null,
            'Дублікат запиту на ручне закриття скасовано',
            v_row.old_status,
            'Скасовано',
            'Чинним лишено перший активний запит №' || v_row.keep_id::text || '.',
            jsonb_build_object(
                'email', 'system',
                'name', 'Міграція Етапу 5',
                'role', 'system'
            ),
            null,
            'closeout_requests',
            v_row.id::text,
            jsonb_build_object(
                'kept_closeout_id', v_row.keep_id,
                'version_number', v_version
            )
        );
    end loop;
end;
$$;

-- Ж1: фізичний захист бази від другого активного запиту.
create unique index if not exists uq_closeout_requests_active_period
    on public.closeout_requests (
        strat_code,
        period_year,
        coalesce(period_quarter, 0)
    )
    where approval_status in ('Очікує підтвердження', 'Підтверджено');

-- Формує зрозумілий підпис періоду для повідомлення про дубль.
create or replace function monitoring_internal.closeout_period_label(
    p_year smallint,
    p_quarter smallint
)
returns text
language sql
immutable
security invoker
set search_path = pg_catalog
as $$
    select case
        when p_quarter is null then p_year::text || ' рік'
        else (array['I','II','III','IV'])[p_quarter] || ' квартал ' || p_year::text || ' року'
    end;
$$;

-- Ж2: створює одну або чотири офіційні заявки monitoring_requests із
-- фактичними даними підтвердженого ручного закриття.
create or replace function monitoring_internal.materialize_closeout_requests(
    p_closeout_id bigint,
    p_actor jsonb
)
returns jsonb
language plpgsql
security invoker
set search_path = public, monitoring_internal, pg_catalog
as $$
declare
    v_closeout public.closeout_requests%rowtype;
    v_quarter smallint;
    v_existing public.monitoring_requests%rowtype;
    v_request public.monitoring_requests%rowtype;
    v_version integer;
    v_ids jsonb := '[]'::jsonb;
    v_actor_name text := coalesce(
        nullif(btrim(p_actor->>'name'), ''),
        nullif(btrim(p_actor->>'email'), ''),
        'Супер-адміністратор'
    );
begin
    select *
      into v_closeout
      from public.closeout_requests
     where id = p_closeout_id
     for update;

    if not found then
        return jsonb_build_object(
            'success', false,
            'code', 'not_found',
            'message', 'Запит на ручне закриття не знайдено.'
        );
    end if;

    if v_closeout.approval_status <> 'Підтверджено' then
        return jsonb_build_object(
            'success', false,
            'code', 'not_confirmed',
            'message', 'Фактичні дані можна створити лише після підтвердження закриття.'
        );
    end if;

    if nullif(btrim(coalesce(v_closeout.fact_status, '')), '') is null then
        return jsonb_build_object(
            'success', false,
            'code', 'fact_status_required',
            'message', 'Для ручного закриття обов’язково зазначте статус виконання.'
        );
    end if;

    if v_closeout.fact_numeric_value is null
       and nullif(btrim(coalesce(v_closeout.fact_value_text, '')), '') is null then
        return jsonb_build_object(
            'success', false,
            'code', 'fact_value_required',
            'message', 'Для ручного закриття обов’язково зазначте фактичне значення.'
        );
    end if;

    if nullif(btrim(coalesce(v_closeout.fact_progress_text, '')), '') is null then
        return jsonb_build_object(
            'success', false,
            'code', 'fact_progress_required',
            'message', 'Для ручного закриття обов’язково зазначте пояснення фактичних даних.'
        );
    end if;

    -- Ідемпотентність: повторний технічний виклик не створює нові заявки.
    if jsonb_typeof(v_closeout.materialized_request_ids) = 'array'
       and jsonb_array_length(v_closeout.materialized_request_ids) > 0 then
        return jsonb_build_object(
            'success', true,
            'code', 'already_materialized',
            'message', 'Фактичні дані ручного закриття вже записано.',
            'request_ids', v_closeout.materialized_request_ids
        );
    end if;

    for v_quarter in
        select q::smallint
        from generate_series(
            coalesce(v_closeout.period_quarter, 1),
            coalesce(v_closeout.period_quarter, 4)
        ) as q
    loop
        -- Той самий advisory lock, що й у transition_submit_request (Етап 3),
        -- тому звичайне і ручне подання не можуть одночасно створити один період.
        perform pg_advisory_xact_lock(
            hashtextextended(
                concat_ws(
                    '|',
                    'measure',
                    v_closeout.strat_code,
                    v_closeout.period_year::text,
                    v_quarter::text
                ),
                0
            )
        );

        select *
          into v_existing
          from public.monitoring_requests
         where object_kind = 'measure'
           and strat_code = v_closeout.strat_code
           and year = v_closeout.period_year
           and quarter = v_quarter
           and approval_status <> 'Відкликано'
         order by id desc
         limit 1;

        if found then
            return jsonb_build_object(
                'success', false,
                'code', 'monitoring_request_exists',
                'message',
                    'За цим заходом за '
                    || monitoring_internal.closeout_period_label(
                        v_closeout.period_year,
                        v_quarter
                    )
                    || ' вже існує заявка №'
                    || v_existing.id::text
                    || '. Спочатку врегулюйте її, щоб не затерти подані дані.',
                'existing_request_id', v_existing.id,
                'existing_status', v_existing.approval_status
            );
        end if;

        insert into public.monitoring_requests (
            year,
            quarter,
            department,
            responsible_person,
            email,
            strat_code,
            status,
            numeric_value,
            value_text,
            progress_text,
            risks,
            submitted_at,
            approval_status,
            admin_comment,
            npa_link,
            approval_chain,
            chain_stage,
            scheme_label,
            object_kind,
            object_name,
            indicator_name,
            final_locked,
            final_locked_at
        ) values (
            v_closeout.period_year,
            v_quarter,
            nullif(v_closeout.department, ''),
            coalesce(nullif(v_closeout.admin_id, ''), v_actor_name),
            lower(nullif(v_closeout.admin_email, '')),
            v_closeout.strat_code,
            v_closeout.fact_status,
            v_closeout.fact_numeric_value,
            nullif(v_closeout.fact_value_text, ''),
            v_closeout.fact_progress_text,
            coalesce(v_closeout.evidence_note, ''),
            coalesce(v_closeout.decided_at, now()),
            'Погоджено',
            'Закрито вручну. Підстава: ' || v_closeout.reason,
            coalesce(v_closeout.npa_links, ''),
            '[]',
            0,
            'Ручне закриття',
            'measure',
            coalesce(v_closeout.object_name, ''),
            coalesce(v_closeout.indicator_name, ''),
            true,
            coalesce(v_closeout.decided_at, now())
        )
        returning * into v_request;

        v_version := monitoring_internal.snapshot_request(
            v_request.id,
            'Ручне закриття / офіційні фактичні дані'
        );

        perform monitoring_internal.write_log(
            v_request.id,
            'Ручне закриття: створено офіційні фактичні дані',
            '',
            'Погоджено',
            'Статус: ' || v_closeout.fact_status
                || '; фактичне значення: '
                || coalesce(
                    v_closeout.fact_numeric_value::text,
                    v_closeout.fact_value_text,
                    '—'
                )
                || '; пояснення: ' || v_closeout.fact_progress_text,
            p_actor,
            v_closeout.strat_code,
            'monitoring_requests',
            v_request.id::text,
            jsonb_build_object(
                'closeout_id', v_closeout.id,
                'version_number', v_version,
                'fact_status', v_closeout.fact_status,
                'fact_numeric_value', v_closeout.fact_numeric_value,
                'fact_value_text', v_closeout.fact_value_text,
                'fact_progress_text', v_closeout.fact_progress_text,
                'confirmed_by', v_actor_name
            )
        );

        v_ids := v_ids || jsonb_build_array(v_request.id);
    end loop;

    update public.closeout_requests
       set materialized_request_ids = v_ids
     where id = p_closeout_id;

    return jsonb_build_object(
        'success', true,
        'code', 'ok',
        'message', 'Фактичні дані ручного закриття записано.',
        'request_ids', v_ids
    );
end;
$$;

-- Ж1 + Ж2: створення запиту з перевіркою дубля та з фактичними даними.
create or replace function public.transition_create_closeout(
    p_payload jsonb,
    p_actor jsonb
)
returns jsonb
language plpgsql
security invoker
set search_path = public, monitoring_internal, pg_catalog
as $$
declare
    v_row public.closeout_requests%rowtype;
    v_existing public.closeout_requests%rowtype;
    v_version integer;
    v_materialized jsonb;
    v_status text := coalesce(
        nullif(btrim(p_payload->>'approval_status'), ''),
        'Очікує підтвердження'
    );
    v_year smallint := nullif(p_payload->>'period_year', '')::smallint;
    v_quarter smallint := nullif(p_payload->>'period_quarter', '')::smallint;
begin
    if nullif(btrim(coalesce(p_payload->>'strat_code', '')), '') is null then
        return jsonb_build_object(
            'success', false,
            'code', 'strat_code_required',
            'message', 'Не зазначено код заходу.'
        );
    end if;
    if v_year is null then
        return jsonb_build_object(
            'success', false,
            'code', 'period_required',
            'message', 'Не зазначено рік ручного закриття.'
        );
    end if;
    if nullif(btrim(coalesce(p_payload->>'reason', '')), '') is null then
        return jsonb_build_object(
            'success', false,
            'code', 'reason_required',
            'message', 'Підстава ручного закриття обов’язкова.'
        );
    end if;
    if nullif(btrim(coalesce(p_payload->>'fact_status', '')), '') is null then
        return jsonb_build_object(
            'success', false,
            'code', 'fact_status_required',
            'message', 'Статус виконання при ручному закритті обов’язковий.'
        );
    end if;
    if nullif(p_payload->>'fact_numeric_value', '') is null
       and nullif(btrim(coalesce(p_payload->>'fact_value_text', '')), '') is null then
        return jsonb_build_object(
            'success', false,
            'code', 'fact_value_required',
            'message', 'Фактичне значення при ручному закритті обов’язкове.'
        );
    end if;
    if nullif(btrim(coalesce(p_payload->>'fact_progress_text', '')), '') is null then
        return jsonb_build_object(
            'success', false,
            'code', 'fact_progress_required',
            'message', 'Пояснення фактичних даних при ручному закритті обов’язкове.'
        );
    end if;
    if v_status not in ('Очікує підтвердження', 'Підтверджено') then
        return jsonb_build_object(
            'success', false,
            'code', 'invalid_initial_status',
            'message', 'Недопустимий початковий статус ручного закриття.'
        );
    end if;

    -- Один захід/рік блокується спільно: річне закриття не може
    -- одночасно пройти поруч із квартальним закриттям того самого року.
    perform pg_advisory_xact_lock(
        hashtextextended(
            concat_ws(
                '|',
                btrim(p_payload->>'strat_code'),
                v_year::text
            ),
            0
        )
    );

    select *
      into v_existing
      from public.closeout_requests
     where strat_code = btrim(p_payload->>'strat_code')
       and period_year = v_year
       and (
           v_quarter is null
           or period_quarter is null
           or period_quarter = v_quarter
       )
       and approval_status in ('Очікує підтвердження', 'Підтверджено')
     order by requested_at, id
     limit 1;

    if found then
        return jsonb_build_object(
            'success', false,
            'code', 'duplicate_active_closeout',
            'message',
                'Запит на закриття цього заходу за '
                || monitoring_internal.closeout_period_label(v_year, v_quarter)
                || ' вже подано '
                || to_char(
                    timezone('Europe/Kyiv', v_existing.requested_at),
                    'DD.MM.YYYY HH24:MI'
                )
                || ' і він '
                || case
                    when v_existing.approval_status = 'Підтверджено'
                    then 'вже підтверджений.'
                    else 'перебуває на розгляді.'
                   end,
            'existing_closeout_id', v_existing.id,
            'existing_status', v_existing.approval_status,
            'requested_at', v_existing.requested_at
        );
    end if;

    insert into public.closeout_requests (
        strat_code,
        period_year,
        period_quarter,
        admin_id,
        admin_email,
        reason,
        evidence_note,
        approval_status,
        superadmin_id,
        decided_at,
        npa_links,
        scope,
        head_status,
        head_email,
        assigned_superadmin_email,
        assigned_superadmin_name,
        senior_superadmin_email,
        senior_superadmin_name,
        routing_note,
        fact_status,
        fact_numeric_value,
        fact_value_text,
        fact_progress_text,
        department,
        object_name,
        indicator_name
    ) values (
        btrim(p_payload->>'strat_code'),
        v_year,
        v_quarter,
        coalesce(p_payload->>'admin_id', ''),
        lower(btrim(coalesce(p_payload->>'admin_email', ''))),
        btrim(p_payload->>'reason'),
        coalesce(p_payload->>'evidence_note', ''),
        v_status,
        case
            when v_status = 'Підтверджено'
            then coalesce(
                nullif(p_payload->>'superadmin_id', ''),
                p_actor->>'email',
                p_actor->>'name',
                ''
            )
            else nullif(p_payload->>'superadmin_id', '')
        end,
        case when v_status = 'Підтверджено' then now() else null end,
        coalesce(p_payload->>'npa_links', ''),
        coalesce(nullif(p_payload->>'scope', ''), 'Квартал'),
        case
            when v_status = 'Підтверджено'
            then coalesce(nullif(p_payload->>'head_status', ''), 'Очікує реакції')
            else nullif(p_payload->>'head_status', '')
        end,
        nullif(p_payload->>'head_email', ''),
        nullif(p_payload->>'assigned_superadmin_email', ''),
        nullif(p_payload->>'assigned_superadmin_name', ''),
        nullif(p_payload->>'senior_superadmin_email', ''),
        nullif(p_payload->>'senior_superadmin_name', ''),
        nullif(p_payload->>'routing_note', ''),
        p_payload->>'fact_status',
        nullif(p_payload->>'fact_numeric_value', '')::numeric,
        nullif(p_payload->>'fact_value_text', ''),
        p_payload->>'fact_progress_text',
        nullif(p_payload->>'department', ''),
        coalesce(p_payload->>'object_name', ''),
        coalesce(p_payload->>'indicator_name', '')
    )
    returning * into v_row;

    v_version := monitoring_internal.snapshot_closeout(
        v_row.id,
        'Ручне закриття / створення з фактичними даними'
    );

    perform monitoring_internal.write_log(
        null,
        'Ручне закриття заходу',
        '',
        v_status,
        'Підстава: ' || v_row.reason
            || '; статус: ' || v_row.fact_status
            || '; фактичне значення: '
            || coalesce(v_row.fact_numeric_value::text, v_row.fact_value_text, '—')
            || '; пояснення: ' || v_row.fact_progress_text,
        p_actor,
        v_row.strat_code,
        'closeout_requests',
        v_row.id::text,
        jsonb_build_object(
            'version_number', v_version,
            'scope', v_row.scope,
            'year', v_row.period_year,
            'quarter', v_row.period_quarter,
            'fact_status', v_row.fact_status,
            'fact_numeric_value', v_row.fact_numeric_value,
            'fact_value_text', v_row.fact_value_text,
            'fact_progress_text', v_row.fact_progress_text
        )
    );

    if v_status = 'Підтверджено' then
        v_materialized := monitoring_internal.materialize_closeout_requests(
            v_row.id,
            p_actor
        );
        if coalesce((v_materialized->>'success')::boolean, false) = false then
            raise exception using message = 'STAGE5_BUSINESS:' || coalesce(
                v_materialized->>'message',
                'Не вдалося записати фактичні дані ручного закриття.'
            );
        end if;
    end if;

    return jsonb_build_object(
        'success', true,
        'code', 'ok',
        'message',
            case
                when v_status = 'Підтверджено' then 'Захід закрито вручну.'
                else 'Запит на ручне закриття створено.'
            end,
        'closeout_id', v_row.id,
        'new_status', v_status,
        'version_number', v_version,
        'request_ids', coalesce(v_materialized->'request_ids', '[]'::jsonb)
    );
exception
    when unique_violation then
        return jsonb_build_object(
            'success', false,
            'code', 'duplicate_active_closeout',
            'message',
                'Активний запит на закриття цього заходу за вибраний період уже існує.'
        );
    when others then
        if sqlerrm like 'STAGE5_BUSINESS:%' then
            return jsonb_build_object(
                'success', false,
                'code', 'closeout_materialization_rejected',
                'message', substr(sqlerrm, length('STAGE5_BUSINESS:') + 1)
            );
        end if;
        raise;
end;
$$;

-- Ж2: рішення супер-адміна і створення офіційної заявки — одна транзакція.
create or replace function public.transition_decide_closeout(
    p_closeout_id bigint,
    p_expected_status text,
    p_new_status text,
    p_decision_comment text,
    p_head_email text,
    p_actor jsonb
)
returns jsonb
language plpgsql
security invoker
set search_path = public, monitoring_internal, pg_catalog
as $$
declare
    v_row public.closeout_requests%rowtype;
    v_version integer;
    v_materialized jsonb;
    v_actor_id text := coalesce(p_actor->>'email', p_actor->>'name', '');
begin
    if p_new_status not in ('Підтверджено', 'Відхилено') then
        return jsonb_build_object(
            'success', false,
            'code', 'invalid_target_status',
            'message', 'Недопустиме рішення щодо ручного закриття.'
        );
    end if;

    select *
      into v_row
      from public.closeout_requests
     where id = p_closeout_id
     for update;

    if not found then
        return jsonb_build_object(
            'success', false,
            'code', 'not_found',
            'message', 'Запит на ручне закриття не знайдено.'
        );
    end if;
    if v_row.approval_status is distinct from p_expected_status then
        return jsonb_build_object(
            'success', false,
            'code', 'state_changed',
            'message', 'Перехід недопустимий: цей запит уже розглянуто.',
            'current_status', v_row.approval_status
        );
    end if;

    update public.closeout_requests
       set approval_status = p_new_status,
           superadmin_id = v_actor_id,
           decided_at = now(),
           decision_comment = coalesce(p_decision_comment, ''),
           head_status = case
               when p_new_status = 'Підтверджено' then 'Очікує реакції'
               else head_status
           end,
           head_email = case
               when p_new_status = 'Підтверджено'
               then coalesce(nullif(btrim(p_head_email), ''), head_email)
               else head_email
           end
     where id = p_closeout_id;

    if p_new_status = 'Підтверджено' then
        v_materialized := monitoring_internal.materialize_closeout_requests(
            p_closeout_id,
            p_actor
        );
        if coalesce((v_materialized->>'success')::boolean, false) = false then
            raise exception using message = 'STAGE5_BUSINESS:' || coalesce(
                v_materialized->>'message',
                'Не вдалося записати фактичні дані ручного закриття.'
            );
        end if;
    end if;

    v_version := monitoring_internal.snapshot_closeout(
        p_closeout_id,
        'Ручне закриття / після рішення з фактичними даними'
    );

    perform monitoring_internal.write_log(
        null,
        'Закриття заходу: ' || p_new_status,
        v_row.approval_status,
        p_new_status,
        coalesce(p_decision_comment, '')
            || case
                when p_new_status = 'Підтверджено'
                then '; статус: ' || v_row.fact_status
                    || '; фактичне значення: '
                    || coalesce(v_row.fact_numeric_value::text, v_row.fact_value_text, '—')
                    || '; пояснення: ' || v_row.fact_progress_text
                else ''
               end,
        p_actor,
        v_row.strat_code,
        'closeout_requests',
        p_closeout_id::text,
        jsonb_build_object(
            'version_number', v_version,
            'request_ids', coalesce(v_materialized->'request_ids', '[]'::jsonb),
            'fact_status', v_row.fact_status,
            'fact_numeric_value', v_row.fact_numeric_value,
            'fact_value_text', v_row.fact_value_text,
            'fact_progress_text', v_row.fact_progress_text
        )
    );

    return jsonb_build_object(
        'success', true,
        'code', 'ok',
        'message', 'Рішення зафіксовано.',
        'closeout_id', p_closeout_id,
        'new_status', p_new_status,
        'version_number', v_version,
        'request_ids', coalesce(v_materialized->'request_ids', '[]'::jsonb)
    );
exception
    when others then
        if sqlerrm like 'STAGE5_BUSINESS:%' then
            return jsonb_build_object(
                'success', false,
                'code', 'closeout_materialization_rejected',
                'message', substr(sqlerrm, length('STAGE5_BUSINESS:') + 1)
            );
        end if;
        raise;
end;
$$;

revoke all on function monitoring_internal.closeout_period_label(smallint, smallint) from public;
revoke all on function monitoring_internal.materialize_closeout_requests(bigint, jsonb) from public;
revoke all on function public.transition_create_closeout(jsonb, jsonb) from public;
revoke all on function public.transition_decide_closeout(bigint, text, text, text, text, jsonb) from public;

grant execute on function monitoring_internal.closeout_period_label(smallint, smallint)
    to anon, authenticated, service_role;
grant execute on function monitoring_internal.materialize_closeout_requests(bigint, jsonb)
    to anon, authenticated, service_role;
grant execute on function public.transition_create_closeout(jsonb, jsonb)
    to anon, authenticated, service_role;
grant execute on function public.transition_decide_closeout(bigint, text, text, text, text, jsonb)
    to anon, authenticated, service_role;

commit;
