-- Редагування керівником ССП: координатор стає новою фінальною ланкою.
-- Функція обгортає чинний transition_resubmit_request в одну транзакцію,
-- а потім атомарно фіксує розширений маршрут і фінальний індекс координатора.

begin;

create or replace function public.transition_resubmit_head_edit_final_coordinator(
    p_request_id bigint,
    p_expected_updated_at timestamptz,
    p_expected_status text,
    p_expected_chain_stage integer,
    p_existing_coordinator_stage integer,
    p_final_coordinator_stage integer,
    p_approval_chain text,
    p_scheme_label text,
    p_payload jsonb,
    p_action text,
    p_actor jsonb,
    p_created_by_before text,
    p_created_by_after text
)
returns jsonb
language plpgsql
security invoker
set search_path = public, monitoring_internal, pg_catalog
as $$
declare
    v_chain jsonb;
    v_result jsonb;
    v_row public.monitoring_requests%rowtype;
    v_updated public.monitoring_requests%rowtype;
    v_new_status text;
    v_after_version integer;
begin
    begin
        v_chain := p_approval_chain::jsonb;
    exception
        when others then
            return jsonb_build_object(
                'success', false,
                'code', 'invalid_approval_chain',
                'message', 'Не вдалося прочитати оновлену схему погодження.'
            );
    end;

    if jsonb_typeof(v_chain) <> 'array'
       or jsonb_array_length(v_chain) = 0 then
        return jsonb_build_object(
            'success', false,
            'code', 'invalid_approval_chain',
            'message', 'Оновлена схема погодження має бути непорожнім ланцюжком.'
        );
    end if;

    if p_final_coordinator_stage < 0
       or p_final_coordinator_stage >= jsonb_array_length(v_chain)
       or coalesce(v_chain -> p_final_coordinator_stage ->> 'role', '') <> 'admin' then
        return jsonb_build_object(
            'success', false,
            'code', 'invalid_final_coordinator',
            'message', 'Фінальна ланка оновленої схеми має бути координатором.'
        );
    end if;

    -- Чинна функція виконує optimistic locking, оновлює дані,
    -- створює версії та журнал. Вона тимчасово повертає заявку на вже
    -- наявну координаторську ланку старого маршруту.
    v_result := public.transition_resubmit_request(
        p_request_id,
        p_expected_updated_at,
        p_expected_status,
        p_expected_chain_stage,
        p_existing_coordinator_stage,
        p_payload,
        'stage_edit',
        p_action,
        p_actor,
        p_created_by_before,
        p_created_by_after,
        '',
        ''
    );

    if not coalesce((v_result ->> 'success')::boolean, false) then
        return v_result;
    end if;

    select *
      into v_row
      from public.monitoring_requests
     where id = p_request_id
     for update;

    if not found then
        return jsonb_build_object(
            'success', false,
            'code', 'not_found_after_resubmit',
            'message', 'Заявку не знайдено після збереження редагування.'
        );
    end if;

    v_new_status := monitoring_internal.waiting_status_for_chain_stage(
        p_approval_chain,
        p_final_coordinator_stage
    );

    update public.monitoring_requests
       set approval_chain = p_approval_chain,
           scheme_label = coalesce(nullif(btrim(p_scheme_label), ''), scheme_label),
           chain_stage = p_final_coordinator_stage,
           approval_status = v_new_status,
           admin_comment = '',
           updated_at = now()
     where id = p_request_id
     returning * into v_updated;

    v_after_version := nullif(v_result ->> 'version_after', '')::integer;

    -- Чинна RPC уже створила «після»-версію редагування. Оновлюємо саме її
    -- маршрутом, який є частиною цієї ж атомарної дії, замість створення
    -- зайвої третьої версії лише через технічну зміну схеми.
    if v_after_version is not null then
        update public.monitoring_request_versions
           set approval_chain = p_approval_chain,
               scheme_label = coalesce(nullif(btrim(p_scheme_label), ''), scheme_label),
               chain_stage = p_final_coordinator_stage,
               approval_status = v_new_status
         where request_id = p_request_id
           and version_number = v_after_version;
    end if;

    perform monitoring_internal.write_log(
        p_request_id,
        'Редагування керівником ССП: координатора додано фінальною ланкою',
        v_row.approval_status,
        v_new_status,
        'Після редагування керівником ССП пройдену схему збережено, '
            || 'а координатора додано в кінець маршруту для остаточного контролю.',
        p_actor,
        v_row.strat_code,
        'monitoring_requests',
        p_request_id::text,
        jsonb_build_object(
            'previous_chain_stage', v_row.chain_stage,
            'final_coordinator_stage', p_final_coordinator_stage,
            'version_after', v_after_version,
            'approval_chain', v_chain
        )
    );

    return v_result || jsonb_build_object(
        'success', true,
        'code', 'ok',
        'message', 'Дані змінено; координатора додано фінальною ланкою.',
        'new_status', v_new_status,
        'new_chain_stage', p_final_coordinator_stage,
        'first_stage_label', monitoring_internal.chain_stage_label(
            p_approval_chain,
            p_final_coordinator_stage
        ),
        'version_after', v_after_version,
        'updated_at', v_updated.updated_at
    );
end;
$$;

revoke all on function public.transition_resubmit_head_edit_final_coordinator(
    bigint, timestamptz, text, integer, integer, integer, text, text,
    jsonb, text, jsonb, text, text
) from public;

grant execute on function public.transition_resubmit_head_edit_final_coordinator(
    bigint, timestamptz, text, integer, integer, integer, text, text,
    jsonb, text, jsonb, text, text
) to anon, authenticated, service_role;

commit;
