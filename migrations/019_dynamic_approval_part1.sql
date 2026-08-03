-- 019: динамічна схема погодження, Частина 1.
-- Нижній цикл: подавач ССП -> координатор -> очікування вибору керівника.

begin;

-- 0. Спершу знімаємо старе обмеження, інакше перейменування статусів
--    нижче блокується старим переліком дозволених значень.
alter table public.monitoring_requests
    drop constraint if exists chk_approval_status;

-- 1. Переведення наявних робочих статусів у нову шкалу.
update public.monitoring_requests
   set approval_status = case approval_status
       when 'Очікує погодження' then 'На розгляді координатора'
       when 'Очікує: Керівник ССП' then 'На розгляді керівника'
       when 'Очікує: Керівник управління' then 'На розгляді керівника'
       when 'Очікує: Заступник керівника ССП' then 'На розгляді керівника'
       when 'Очікує: Супер-адмін' then 'На розгляді супер-адміна'
       when 'Повернуто на доопрацювання' then 'Повернуто на доопрацювання координатором'
       when 'Відкликано' then null
       else approval_status
   end
 where approval_status in (
       'Очікує погодження',
       'Очікує: Керівник ССП',
       'Очікує: Керівник управління',
       'Очікує: Заступник керівника ССП',
       'Очікує: Супер-адмін',
       'Повернуто на доопрацювання',
       'Відкликано'
   );

-- Версії не мають CHECK-обмеження, але їхні статуси оновлюються для
-- узгодженого відображення історії.
update public.monitoring_request_versions
   set approval_status = case approval_status
       when 'Очікує погодження' then 'На розгляді координатора'
       when 'Очікує: Керівник ССП' then 'На розгляді керівника'
       when 'Очікує: Керівник управління' then 'На розгляді керівника'
       when 'Очікує: Заступник керівника ССП' then 'На розгляді керівника'
       when 'Очікує: Супер-адмін' then 'На розгляді супер-адміна'
       when 'Повернуто на доопрацювання' then 'Повернуто на доопрацювання координатором'
       when 'Відкликано' then null
       else approval_status
   end
 where approval_status in (
       'Очікує погодження',
       'Очікує: Керівник ССП',
       'Очікує: Керівник управління',
       'Очікує: Заступник керівника ССП',
       'Очікує: Супер-адмін',
       'Повернуто на доопрацювання',
       'Відкликано'
   );

alter table public.monitoring_requests
    alter column approval_status set default 'На розгляді координатора';

alter table public.monitoring_requests
    add constraint chk_approval_status check (
        approval_status in (
            'На розгляді координатора',
            'Повернуто на доопрацювання координатором',
            'Повернуто на доопрацювання керівником',
            'Повернуто на доопрацювання супер-адміном',
            'Очікує вибору керівника',
            'На розгляді супер-адміна',
            'На розгляді керівника',
            'Погоджено'
        )
    );

-- CHECK у PostgreSQL не відхиляє NULL. NULL є технічною ознакою відкликаного рядка, а не статусом погодження.
-- Це зберігає м'яке відкликання й не розширює перелік статусів у CHECK.

-- 2. Єдине зведення ролі поточної ланки до нового статусу.
create or replace function monitoring_internal.waiting_status_for_chain_stage(
    p_approval_chain text,
    p_stage integer
)
returns text
language plpgsql
immutable
security invoker
set search_path = pg_catalog
as $$
declare
    v_chain jsonb;
    v_role text;
    v_previous_role text;
begin
    begin
        v_chain := coalesce(nullif(btrim(p_approval_chain), ''), '[]')::jsonb;
    exception
        when others then
            return 'На розгляді координатора';
    end;

    if jsonb_typeof(v_chain) <> 'array' then
        return 'На розгляді координатора';
    end if;

    if coalesce(p_stage, 0) >= 0
       and coalesce(p_stage, 0) < jsonb_array_length(v_chain) then
        v_role := coalesce(v_chain -> coalesce(p_stage, 0) ->> 'role', '');
        return case v_role
            when 'admin' then 'На розгляді координатора'
            when 'super_admin' then 'На розгляді супер-адміна'
            when 'ssp_head' then 'На розгляді керівника'
            when 'ssp_deputy' then 'На розгляді керівника'
            else 'На розгляді керівника'
        end;
    end if;

    if coalesce(p_stage, 0) > 0
       and coalesce(p_stage, 0) - 1 < jsonb_array_length(v_chain) then
        v_previous_role := coalesce(
            v_chain -> (coalesce(p_stage, 0) - 1) ->> 'role',
            ''
        );
        if v_previous_role = 'admin' then
            return 'Очікує вибору керівника';
        end if;
    end if;

    return 'Погоджено';
end;
$$;

-- 3. Первинне подання: чинна RPC з новою шкалою активних статусів.
create or replace function public.transition_submit_request(
    p_payload jsonb,
    p_action text,
    p_actor jsonb,
    p_created_by text,
    p_draft_email text,
    p_draft_key text
)
returns jsonb
language plpgsql
security invoker
set search_path = public, monitoring_internal, pg_catalog
as $$
declare
    v_request public.monitoring_requests%rowtype;
    v_existing_id bigint;
    v_version integer;
    v_kind text := coalesce(nullif(btrim(p_payload->>'object_kind'), ''), 'measure');
    v_code text := btrim(coalesce(p_payload->>'strat_code', ''));
    v_indicator_name text := lower(btrim(coalesce(p_payload->>'indicator_name', '')));
    v_year smallint := nullif(p_payload->>'year', '')::smallint;
    v_quarter smallint := nullif(p_payload->>'quarter', '')::smallint;
    v_chain text := coalesce(p_payload->>'approval_chain', '');
    v_first_status text;
    v_first_label text;
begin
    if v_code = '' or v_year is null or v_quarter is null then
        return jsonb_build_object(
            'success', false,
            'code', 'missing_identity',
            'message', 'Не вдалося визначити захід та звітний період.'
        );
    end if;

    if v_kind not in ('measure', 'indicator') then
        return jsonb_build_object(
            'success', false,
            'code', 'invalid_object_kind',
            'message', 'Недопустимий тип об’єкта подання.'
        );
    end if;

    if v_kind = 'indicator' and v_indicator_name = '' then
        return jsonb_build_object(
            'success', false,
            'code', 'missing_indicator_name',
            'message', 'Не вдалося визначити назву індикатора.'
        );
    end if;

    perform pg_advisory_xact_lock(
        hashtextextended(
            concat_ws(
                '|',
                v_kind,
                v_code,
                v_year::text,
                case
                    when v_kind = 'indicator' then v_indicator_name
                    else v_quarter::text
                end
            ),
            0
        )
    );

    if v_kind = 'measure' then
        select id
          into v_existing_id
          from public.monitoring_requests
         where object_kind = 'measure'
           and strat_code = v_code
           and year = v_year
           and quarter = v_quarter
           and approval_status is not null
         order by id desc
         limit 1;
    else
        select id
          into v_existing_id
          from public.monitoring_requests
         where object_kind = 'indicator'
           and strat_code = v_code
           and year = v_year
           and lower(btrim(coalesce(indicator_name, ''))) = v_indicator_name
           and approval_status in (
               'На розгляді координатора',
               'Очікує вибору керівника',
               'На розгляді супер-адміна',
               'На розгляді керівника'
           )
         order by id desc
         limit 1;
    end if;

    if v_existing_id is not null then
        return jsonb_build_object(
            'success', false,
            'code', 'duplicate_request',
            'message',
                case
                    when v_kind = 'indicator' then
                        'За цим індикатором у вибраному році вже існує активна заявка.'
                    else
                        'За цим заходом у вибраному періоді вже існує активна заявка.'
                end,
            'existing_request_id', v_existing_id
        );
    end if;

    v_first_status := monitoring_internal.waiting_status_for_chain_stage(v_chain, 0);
    v_first_label := monitoring_internal.chain_stage_label(v_chain, 0);

    insert into public.monitoring_requests (
        year, quarter, department, responsible_person, phone, email,
        strat_code, status, progress_text, risks, submitted_at,
        approval_status, admin_comment, start_date, end_date,
        file_names, file_urls, npa_link, approval_chain, chain_stage,
        scheme_label, object_kind, as_of_date, object_name, indicator_name,
        final_locked, numeric_value, value_text
    )
    values (
        v_year,
        v_quarter,
        nullif(p_payload->>'department', ''),
        nullif(p_payload->>'responsible_person', ''),
        nullif(p_payload->>'phone', ''),
        lower(nullif(p_payload->>'email', '')),
        v_code,
        nullif(p_payload->>'status', ''),
        coalesce(p_payload->>'progress_text', ''),
        coalesce(p_payload->>'risks', ''),
        coalesce(nullif(p_payload->>'submitted_at', '')::timestamptz, now()),
        v_first_status,
        coalesce(p_payload->>'admin_comment', ''),
        nullif(p_payload->>'start_date', '')::date,
        nullif(p_payload->>'end_date', '')::date,
        coalesce(p_payload->>'file_names', ''),
        coalesce(p_payload->>'file_urls', ''),
        coalesce(p_payload->>'npa_link', ''),
        v_chain,
        0,
        coalesce(p_payload->>'scheme_label', ''),
        v_kind,
        nullif(p_payload->>'as_of_date', '')::date,
        coalesce(p_payload->>'object_name', ''),
        coalesce(p_payload->>'indicator_name', ''),
        false,
        nullif(p_payload->>'numeric_value', '')::numeric,
        nullif(p_payload->>'value_text', '')
    )
    returning * into v_request;

    v_version := monitoring_internal.snapshot_request(
        v_request.id,
        coalesce(nullif(btrim(p_created_by), ''), 'Первинне подання')
    );

    perform monitoring_internal.write_log(
        v_request.id,
        coalesce(nullif(btrim(p_action), ''), 'Подання моніторингових відомостей'),
        '',
        v_first_status,
        'Заявку створено подавачем',
        p_actor,
        v_request.strat_code,
        'monitoring_requests',
        v_request.id::text,
        jsonb_build_object(
            'version_number', v_version,
            'object_kind', v_kind,
            'indicator_name', v_request.indicator_name,
            'scheme_label', v_request.scheme_label
        )
    );

    if nullif(lower(btrim(coalesce(p_draft_email, ''))), '') is not null
       and nullif(btrim(coalesce(p_draft_key, '')), '') is not null then
        delete from public.monitoring_drafts
         where user_email = lower(btrim(p_draft_email))
           and object_key = btrim(p_draft_key);
    end if;

    return jsonb_build_object(
        'success', true,
        'code', 'ok',
        'message', 'Заявку подано.',
        'request_id', v_request.id,
        'new_status', v_first_status,
        'first_stage_label', v_first_label,
        'version_number', v_version,
        'updated_at', v_request.updated_at
    );
end;
$$;

-- 4. Погодження кроку з новими допустимими статусами.
create or replace function public.transition_approve_request_step(
    p_request_id bigint,
    p_expected_status text,
    p_expected_chain_stage integer,
    p_new_status text,
    p_new_chain_stage integer,
    p_approval_chain text,
    p_comment text,
    p_action text,
    p_actor jsonb,
    p_created_by text
)
returns jsonb
language plpgsql
security invoker
set search_path = public, monitoring_internal, pg_catalog
as $$
declare
    v_row public.monitoring_requests%rowtype;
    v_version integer;
    v_allowed text[] := array[
        'На розгляді координатора',
        'Очікує вибору керівника',
        'На розгляді супер-адміна',
        'На розгляді керівника',
        'Погоджено'
    ];
begin
    select * into v_row
      from public.monitoring_requests
     where id = p_request_id
     for update;

    if not found then
        return jsonb_build_object('success', false, 'code', 'not_found',
                                  'message', 'Заявку не знайдено.');
    end if;
    if v_row.final_locked then
        return jsonb_build_object('success', false, 'code', 'already_final_locked',
                                  'message', 'Заявку вже остаточно погоджено.');
    end if;
    if v_row.approval_status is distinct from p_expected_status
       or coalesce(v_row.chain_stage, 0) is distinct from coalesce(p_expected_chain_stage, 0)
    then
        return jsonb_build_object(
            'success', false,
            'code', 'state_changed',
            'message', 'Перехід недопустимий: заявку вже опрацювала інша ланка.',
            'current_status', v_row.approval_status,
            'current_chain_stage', coalesce(v_row.chain_stage, 0)
        );
    end if;
    if not (p_new_status = any(v_allowed)) then
        return jsonb_build_object('success', false, 'code', 'invalid_target_status',
                                  'message', 'Задано недопустимий новий статус.');
    end if;
    if coalesce(p_new_chain_stage, 0) < coalesce(v_row.chain_stage, 0) then
        return jsonb_build_object('success', false, 'code', 'invalid_stage_direction',
                                  'message', 'Погодження не може повернути заявку на попередню ланку.');
    end if;

    update public.monitoring_requests
       set approval_status = p_new_status,
           chain_stage = coalesce(p_new_chain_stage, chain_stage),
           approval_chain = coalesce(p_approval_chain, approval_chain),
           admin_comment = coalesce(p_comment, ''),
           final_locked = case when p_new_status = 'Погоджено' then true else final_locked end,
           final_locked_at = case
               when p_new_status = 'Погоджено' then coalesce(final_locked_at, now())
               else final_locked_at
           end
     where id = p_request_id;

    v_version := monitoring_internal.snapshot_request(
        p_request_id,
        coalesce(p_created_by, 'Погодження')
    );

    perform monitoring_internal.write_log(
        p_request_id, p_action, v_row.approval_status, p_new_status,
        p_comment, p_actor, v_row.strat_code, 'monitoring_requests',
        p_request_id::text,
        jsonb_build_object('version_number', v_version)
    );

    return jsonb_build_object(
        'success', true, 'code', 'ok', 'message', 'Перехід виконано.',
        'request_id', p_request_id, 'new_status', p_new_status,
        'new_chain_stage', p_new_chain_stage,
        'final_locked', p_new_status = 'Погоджено',
        'version_number', v_version
    );
end;
$$;

-- 5. Повернення з трьома окремими статусами джерела повернення.
create or replace function public.transition_return_request(
    p_request_id bigint,
    p_expected_status text,
    p_expected_chain_stage integer,
    p_new_status text,
    p_new_chain_stage integer,
    p_comment text,
    p_action text,
    p_actor jsonb,
    p_created_by text
)
returns jsonb
language plpgsql
security invoker
set search_path = public, monitoring_internal, pg_catalog
as $$
declare
    v_row public.monitoring_requests%rowtype;
    v_version integer;
    v_allowed text[] := array[
        'Повернуто на доопрацювання координатором',
        'Повернуто на доопрацювання керівником',
        'Повернуто на доопрацювання супер-адміном',
        'На розгляді координатора',
        'Очікує вибору керівника',
        'На розгляді супер-адміна',
        'На розгляді керівника'
    ];
begin
    if nullif(btrim(coalesce(p_comment, '')), '') is null then
        return jsonb_build_object('success', false, 'code', 'comment_required',
                                  'message', 'Для повернення обов’язковий коментар.');
    end if;

    select * into v_row
      from public.monitoring_requests
     where id = p_request_id
     for update;

    if not found then
        return jsonb_build_object('success', false, 'code', 'not_found',
                                  'message', 'Заявку не знайдено.');
    end if;
    if v_row.final_locked then
        return jsonb_build_object('success', false, 'code', 'already_final_locked',
                                  'message', 'Остаточно погоджену заявку повернути неможливо.');
    end if;
    if v_row.approval_status is distinct from p_expected_status
       or coalesce(v_row.chain_stage, 0) is distinct from coalesce(p_expected_chain_stage, 0)
    then
        return jsonb_build_object(
            'success', false, 'code', 'state_changed',
            'message', 'Перехід недопустимий: заявку вже опрацювала інша ланка.',
            'current_status', v_row.approval_status,
            'current_chain_stage', coalesce(v_row.chain_stage, 0)
        );
    end if;
    if not (p_new_status = any(v_allowed)) then
        return jsonb_build_object('success', false, 'code', 'invalid_target_status',
                                  'message', 'Задано недопустимий статус повернення.');
    end if;
    if coalesce(p_new_chain_stage, 0) > coalesce(v_row.chain_stage, 0) then
        return jsonb_build_object('success', false, 'code', 'invalid_stage_direction',
                                  'message', 'Повернення не може передати заявку на наступну ланку.');
    end if;

    update public.monitoring_requests
       set approval_status = p_new_status,
           chain_stage = coalesce(p_new_chain_stage, chain_stage),
           admin_comment = p_comment
     where id = p_request_id;

    v_version := monitoring_internal.snapshot_request(
        p_request_id,
        coalesce(p_created_by, 'Повернення')
    );

    perform monitoring_internal.write_log(
        p_request_id, p_action, v_row.approval_status, p_new_status,
        p_comment, p_actor, v_row.strat_code, 'monitoring_requests',
        p_request_id::text,
        jsonb_build_object('version_number', v_version)
    );

    return jsonb_build_object(
        'success', true, 'code', 'ok', 'message', 'Заявку повернуто.',
        'request_id', p_request_id, 'new_status', p_new_status,
        'new_chain_stage', p_new_chain_stage,
        'version_number', v_version
    );
end;
$$;

-- 6. Повторне подання/редагування з динамічним визначенням нового статусу.
-- Збережено наявну семантику optimistic locking, версій і журналу.
create or replace function public.transition_resubmit_request(
    p_request_id bigint,
    p_expected_updated_at timestamptz,
    p_expected_status text,
    p_expected_chain_stage integer,
    p_target_chain_stage integer,
    p_payload jsonb,
    p_mode text,
    p_action text,
    p_actor jsonb,
    p_created_by_before text,
    p_created_by_after text,
    p_draft_email text,
    p_draft_key text
)
returns jsonb
language plpgsql
security invoker
set search_path = public, monitoring_internal, pg_catalog
as $$
declare
    v_row public.monitoring_requests%rowtype;
    v_new_row public.monitoring_requests%rowtype;
    v_before integer;
    v_after integer;
    v_new_stage integer;
    v_new_status text;
    v_chain jsonb;
    v_current_role text;
    v_last_actor text;
    v_last_changed_at timestamptz;
    v_conflict_time text;
begin
    select *
      into v_row
      from public.monitoring_requests
     where id = p_request_id
     for update;

    if not found then
        return jsonb_build_object(
            'success', false,
            'code', 'not_found',
            'message', 'Заявку не знайдено.'
        );
    end if;

    if v_row.final_locked then
        return jsonb_build_object(
            'success', false,
            'code', 'already_final_locked',
            'message', 'Остаточно погоджену заявку редагувати неможливо.'
        );
    end if;

    if v_row.updated_at is distinct from p_expected_updated_at then
        select
            coalesce(
                nullif(btrim(actor_name), ''),
                nullif(btrim(changed_by), ''),
                'інший користувач'
            ),
            changed_at
          into v_last_actor, v_last_changed_at
          from public.monitoring_logs
         where request_id = p_request_id
         order by changed_at desc nulls last, id desc
         limit 1;

        v_conflict_time := case
            when v_last_changed_at is null then 'щойно'
            else to_char(
                timezone('Europe/Kyiv', v_last_changed_at),
                'DD.MM.YYYY HH24:MI'
            )
        end;

        return jsonb_build_object(
            'success', false,
            'code', 'concurrent_change',
            'message',
                'Цей запис щойно змінив інший користувач ('
                || coalesce(v_last_actor, 'інший користувач')
                || ', '
                || v_conflict_time
                || '). Ваші зміни не збережено, щоб не затерти чужі. '
                || 'Оновіть сторінку, перегляньте актуальні дані '
                || 'та внесіть зміни повторно.',
            'current_updated_at', v_row.updated_at,
            'changed_by', coalesce(v_last_actor, 'інший користувач'),
            'changed_at', v_last_changed_at
        );
    end if;

    if v_row.approval_status is distinct from p_expected_status
       or coalesce(v_row.chain_stage, 0)
          is distinct from coalesce(p_expected_chain_stage, 0)
    then
        return jsonb_build_object(
            'success', false,
            'code', 'state_changed',
            'message',
                'Заявку вже змінила інша ланка. '
                || 'Оновіть сторінку та перегляньте її актуальний стан.',
            'current_status', v_row.approval_status,
            'current_chain_stage', coalesce(v_row.chain_stage, 0)
        );
    end if;

    if p_mode = 'returned' then
        if v_row.approval_status not in (
            'Повернуто на доопрацювання координатором',
            'Повернуто на доопрацювання керівником',
            'Повернуто на доопрацювання супер-адміном'
        ) then
            return jsonb_build_object(
                'success', false,
                'code', 'not_returned',
                'message',
                    'Повторне подання доступне лише для заявки, '
                    || 'повернутої на доопрацювання.'
            );
        end if;
        v_new_stage := 0;
    elsif p_mode = 'stage_edit' then
        v_new_stage := greatest(coalesce(p_target_chain_stage, 0), 0);
    else
        return jsonb_build_object(
            'success', false,
            'code', 'invalid_mode',
            'message', 'Недопустимий режим повторного подання.'
        );
    end if;

    if nullif(btrim(coalesce(v_row.approval_chain, '')), '') is not null then
        begin
            v_chain := v_row.approval_chain::jsonb;
            if jsonb_typeof(v_chain) = 'array' then
                v_current_role := coalesce(
                    v_chain -> coalesce(v_row.chain_stage, 0) ->> 'role',
                    ''
                );
                if v_new_stage >= jsonb_array_length(v_chain)
                   and not (
                       p_mode = 'stage_edit'
                       and v_row.approval_status = 'На розгляді координатора'
                       and v_current_role = 'admin'
                       and v_new_stage = jsonb_array_length(v_chain)
                   )
                then
                    return jsonb_build_object(
                        'success', false,
                        'code', 'invalid_target_stage',
                        'message', 'У маршруті погодження немає обраної ланки.'
                    );
                end if;
            end if;
        exception
            when others then
                v_chain := '[]'::jsonb;
        end;
    end if;

    v_new_status := monitoring_internal.waiting_status_for_chain_stage(
        v_row.approval_chain,
        v_new_stage
    );

    v_before := monitoring_internal.snapshot_request(
        p_request_id,
        coalesce(
            nullif(btrim(p_created_by_before), ''),
            'До повторного подання'
        )
    );

    update public.monitoring_requests
       set status = case
               when p_payload ? 'status'
               then nullif(p_payload->>'status', '')
               else status
           end,
           numeric_value = case
               when p_payload ? 'numeric_value'
               then nullif(p_payload->>'numeric_value', '')::numeric
               else numeric_value
           end,
           value_text = case
               when p_payload ? 'value_text'
               then nullif(p_payload->>'value_text', '')
               else value_text
           end,
           progress_text = case
               when p_payload ? 'progress_text'
               then coalesce(p_payload->>'progress_text', '')
               else progress_text
           end,
           risks = case
               when p_payload ? 'risks'
               then coalesce(p_payload->>'risks', '')
               else risks
           end,
           npa_link = case
               when p_payload ? 'npa_link'
               then coalesce(p_payload->>'npa_link', '')
               else npa_link
           end,
           responsible_person = case
               when p_payload ? 'responsible_person'
               then nullif(p_payload->>'responsible_person', '')
               else responsible_person
           end,
           phone = case
               when p_payload ? 'phone'
               then nullif(p_payload->>'phone', '')
               else phone
           end,
           email = case
               when p_payload ? 'email'
               then lower(nullif(p_payload->>'email', ''))
               else email
           end,
           approval_status = v_new_status,
           chain_stage = v_new_stage,
           submitted_at = coalesce(
               nullif(p_payload->>'submitted_at', '')::timestamptz,
               now()
           ),
           admin_comment = coalesce(p_payload->>'admin_comment', '')
     where id = p_request_id
     returning * into v_new_row;

    v_after := monitoring_internal.snapshot_request(
        p_request_id,
        coalesce(
            nullif(btrim(p_created_by_after), ''),
            'Повторне подання'
        )
    );

    perform monitoring_internal.write_log(
        p_request_id,
        coalesce(nullif(btrim(p_action), ''), 'Повторне подання')
        || ': версія '
        || v_before
        || ' → '
        || v_after,
        v_row.approval_status,
        v_new_status,
        coalesce(p_payload->>'log_comment', 'Заявку повторно подано.'),
        p_actor,
        v_row.strat_code,
        'monitoring_requests',
        p_request_id::text,
        jsonb_build_object(
            'version_before', v_before,
            'version_after', v_after,
            'mode', p_mode,
            'expected_updated_at', p_expected_updated_at,
            'new_updated_at', v_new_row.updated_at
        )
    );

    if nullif(lower(btrim(coalesce(p_draft_email, ''))), '') is not null
       and nullif(btrim(coalesce(p_draft_key, '')), '') is not null
    then
        delete from public.monitoring_drafts
         where user_email = lower(btrim(p_draft_email))
           and object_key = btrim(p_draft_key);
    end if;

    return jsonb_build_object(
        'success', true,
        'code', 'ok',
        'message', 'Заявку повторно подано.',
        'request_id', p_request_id,
        'new_status', v_new_status,
        'new_chain_stage', v_new_stage,
        'first_stage_label', monitoring_internal.chain_stage_label(
            v_row.approval_chain,
            v_new_stage
        ),
        'version_before', v_before,
        'version_after', v_after,
        'updated_at', v_new_row.updated_at
    );
end;
$$;

-- 7. Чинний перехід відкликання зберігається, але технічна ознака
-- відкликання записується як NULL, щоб не розширювати перелік статусів.
create or replace function public.transition_withdraw_request(
    p_request_id bigint,
    p_expected_status text,
    p_expected_chain_stage integer,
    p_comment text,
    p_actor jsonb
)
returns jsonb
language plpgsql
security invoker
set search_path = public, monitoring_internal, pg_catalog
as $$
declare
    v_row public.monitoring_requests%rowtype;
    v_version integer;
begin
    select * into v_row
      from public.monitoring_requests
     where id = p_request_id
     for update;

    if not found then
        return jsonb_build_object('success', false, 'code', 'not_found',
                                  'message', 'Заявку не знайдено.');
    end if;
    if v_row.final_locked then
        return jsonb_build_object('success', false, 'code', 'already_final_locked',
                                  'message', 'Остаточно погоджену заявку відкликати неможливо.');
    end if;
    if v_row.approval_status is distinct from p_expected_status
       or coalesce(v_row.chain_stage, 0) is distinct from coalesce(p_expected_chain_stage, 0)
    then
        return jsonb_build_object(
            'success', false, 'code', 'state_changed',
            'message', 'Відкликання недопустиме: заявку вже опрацювала інша ланка.',
            'current_status', v_row.approval_status,
            'current_chain_stage', coalesce(v_row.chain_stage, 0)
        );
    end if;

    update public.monitoring_requests
       set approval_status = null,
           admin_comment = coalesce(p_comment, 'Відкликано подавачем'),
           updated_at = now()
     where id = p_request_id;

    v_version := monitoring_internal.snapshot_request(
        p_request_id, 'ССП / відкликано'
    );

    perform monitoring_internal.write_log(
        p_request_id, 'Відкликання заявки подавачем',
        v_row.approval_status, 'Відкликано', p_comment, p_actor,
        v_row.strat_code, 'monitoring_requests', p_request_id::text,
        jsonb_build_object('version_number', v_version)
    );

    return jsonb_build_object(
        'success', true, 'code', 'ok', 'message', 'Заявку відкликано.',
        'request_id', p_request_id,
        'version_number', v_version
    );
end;
$$;

commit;
