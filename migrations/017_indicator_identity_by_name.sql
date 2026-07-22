-- 017: індикатори цілей/завдань ідентифікуються парою (strat_code, indicator_name).
--
-- Один код цілі/завдання може мати кілька різних індикаторів. Попередня версія
-- transition_submit_request блокувала другу активну заявку лише за strat_code+year,
-- тому різні індикатори одного коду конфліктували між собою. Тепер advisory lock
-- і перевірка дубля для object_kind='indicator' включають нормалізовану назву.

begin;

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

    -- Серіалізуємо перевірку саме одного логічного об'єкта.
    -- Для індикатора ключ включає назву, а для заходу — квартал, як і раніше.
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
           and approval_status <> 'Відкликано'
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
               'Очікує погодження',
               'Очікує: Керівник ССП',
               'Очікує: Керівник управління',
               'Очікує: Заступник керівника ССП',
               'Очікує: Супер-адмін'
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

commit;
