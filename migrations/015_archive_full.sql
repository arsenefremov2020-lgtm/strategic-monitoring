-- 015 (ДЕМО 2.0, Етап 6): повний незмінний архів, знімки-заміни та атомарне створення.
-- Виконати після 014_stage5_administration_notifications.sql.

begin;

alter table public.archive_snapshots
    add column if not exists snapshot_type text not null default 'manual',
    add column if not exists reason text,
    add column if not exists replacement_reason text,
    add column if not exists replaces_snapshot_id bigint,
    add column if not exists snapshot_gzip_b64 text,
    add column if not exists payload_size_bytes bigint not null default 0,
    add column if not exists coverage_label text not null default '',
    add column if not exists coverage_year_from smallint,
    add column if not exists coverage_year_to smallint,
    add column if not exists structure_row_count integer not null default 0,
    add column if not exists request_count integer not null default 0,
    add column if not exists version_count integer not null default 0,
    add column if not exists measure_count integer not null default 0,
    add column if not exists mio_record_count integer not null default 0,
    add column if not exists log_count integer not null default 0,
    add column if not exists closeout_count integer not null default 0,
    add column if not exists closeout_version_count integer not null default 0,
    add column if not exists snapshot_day_kyiv date,
    add column if not exists created_by_email text,
    add column if not exists created_by_name text,
    add column if not exists created_by_role text;

alter table public.archive_snapshots
    drop constraint if exists chk_archive_snapshot_type;

alter table public.archive_snapshots
    add constraint chk_archive_snapshot_type
    check (snapshot_type in ('manual', 'automatic'));

do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conname = 'fk_archive_snapshot_replaces'
          and conrelid = 'public.archive_snapshots'::regclass
    ) then
        alter table public.archive_snapshots
            add constraint fk_archive_snapshot_replaces
            foreign key (replaces_snapshot_id)
            references public.archive_snapshots(id);
    end if;
end;
$$;

create index if not exists idx_archive_snapshots_archived_at
    on public.archive_snapshots (archived_at desc);

create index if not exists idx_archive_snapshots_replaces
    on public.archive_snapshots (replaces_snapshot_id)
    where replaces_snapshot_id is not null;

-- Один автоматичний знімок на один київський календарний день.
create unique index if not exists uq_archive_automatic_day
    on public.archive_snapshots (snapshot_day_kyiv)
    where snapshot_type = 'automatic';

-- З3: рядок знімка після вставки незмінний навіть для service_role.
create or replace function public.prevent_archive_snapshot_mutation()
returns trigger
language plpgsql
security invoker
set search_path = pg_catalog
as $$
begin
    raise exception using
        errcode = '55000',
        message = 'Архівний знімок є незмінним. Створіть новий знімок або знімок-заміна.';
end;
$$;

drop trigger if exists trg_archive_snapshots_immutable
    on public.archive_snapshots;

create trigger trg_archive_snapshots_immutable
before update or delete on public.archive_snapshots
for each row
execute function public.prevent_archive_snapshot_mutation();

-- З1–З5: вставка знімка та журнал — одна транзакція.
create or replace function public.transition_create_archive_snapshot(
    p_snapshot_meta jsonb,
    p_snapshot_gzip_b64 text,
    p_actor jsonb
)
returns jsonb
language plpgsql
security invoker
set search_path = public, monitoring_internal, pg_catalog
as $$
declare
    v_type text := lower(btrim(coalesce(p_snapshot_meta->>'snapshot_type', 'manual')));
    v_reason text := btrim(coalesce(p_snapshot_meta->>'reason', ''));
    v_replacement_reason text := btrim(coalesce(p_snapshot_meta->>'replacement_reason', ''));
    v_replaces bigint := nullif(p_snapshot_meta->>'replaces_snapshot_id', '')::bigint;
    v_target public.archive_snapshots%rowtype;
    v_row public.archive_snapshots%rowtype;
    v_day date := (now() at time zone 'Europe/Kyiv')::date;
    v_actor_email text := lower(btrim(coalesce(p_actor->>'email', '')));
    v_actor_name text := btrim(coalesce(p_actor->>'name', ''));
    v_actor_role text := btrim(coalesce(p_actor->>'role', ''));
    v_anchor_year smallint := coalesce(
        nullif(p_snapshot_meta->>'anchor_year', '')::smallint,
        extract(year from (now() at time zone 'Europe/Kyiv'))::smallint
    );
    v_anchor_quarter smallint := coalesce(
        nullif(p_snapshot_meta->>'anchor_quarter', '')::smallint,
        extract(quarter from (now() at time zone 'Europe/Kyiv'))::smallint
    );
begin
    if v_type not in ('manual', 'automatic') then
        return jsonb_build_object(
            'success', false,
            'code', 'invalid_snapshot_type',
            'message', 'Недопустимий тип архівного знімка.'
        );
    end if;

    if v_reason = '' then
        return jsonb_build_object(
            'success', false,
            'code', 'reason_required',
            'message', 'Причина створення архівного знімка є обов’язковою.'
        );
    end if;

    if nullif(btrim(coalesce(p_snapshot_gzip_b64, '')), '') is null then
        return jsonb_build_object(
            'success', false,
            'code', 'payload_required',
            'message', 'Дані архівного знімка не сформовано.'
        );
    end if;

    if v_replaces is not null then
        if v_replacement_reason = '' then
            return jsonb_build_object(
                'success', false,
                'code', 'replacement_reason_required',
                'message', 'Для знімка-заміни обов’язково зазначте причину заміни.'
            );
        end if;

        select * into v_target
          from public.archive_snapshots
         where id = v_replaces;

        if not found then
            return jsonb_build_object(
                'success', false,
                'code', 'replacement_target_not_found',
                'message', 'Знімок, який потрібно замінити, не знайдено.'
            );
        end if;
    end if;

    begin
        insert into public.archive_snapshots (
            year,
            quarter,
            snapshot_data,
            archived_by,
            archived_at,
            snapshot_type,
            reason,
            replacement_reason,
            replaces_snapshot_id,
            snapshot_gzip_b64,
            payload_size_bytes,
            coverage_label,
            coverage_year_from,
            coverage_year_to,
            structure_row_count,
            request_count,
            version_count,
            measure_count,
            mio_record_count,
            log_count,
            closeout_count,
            closeout_version_count,
            snapshot_day_kyiv,
            created_by_email,
            created_by_name,
            created_by_role
        ) values (
            v_anchor_year,
            v_anchor_quarter,
            jsonb_build_object(
                'schema_version', coalesce(p_snapshot_meta->>'schema_version', 'DEMO2-ARCHIVE-1'),
                'generated_at_utc', p_snapshot_meta->>'generated_at_utc',
                'coverage_label', coalesce(p_snapshot_meta->>'coverage_label', ''),
                'compressed', true,
                'compression', 'gzip+base64'
            ),
            coalesce(nullif(v_actor_name, ''), nullif(v_actor_email, ''), 'Система'),
            now(),
            v_type,
            v_reason,
            nullif(v_replacement_reason, ''),
            v_replaces,
            p_snapshot_gzip_b64,
            coalesce(nullif(p_snapshot_meta->>'payload_size_bytes', '')::bigint, 0),
            coalesce(p_snapshot_meta->>'coverage_label', ''),
            nullif(p_snapshot_meta->>'coverage_year_from', '')::smallint,
            nullif(p_snapshot_meta->>'coverage_year_to', '')::smallint,
            coalesce(nullif(p_snapshot_meta->>'structure_row_count', '')::integer, 0),
            coalesce(nullif(p_snapshot_meta->>'request_count', '')::integer, 0),
            coalesce(nullif(p_snapshot_meta->>'version_count', '')::integer, 0),
            coalesce(nullif(p_snapshot_meta->>'measure_count', '')::integer, 0),
            coalesce(nullif(p_snapshot_meta->>'mio_record_count', '')::integer, 0),
            coalesce(nullif(p_snapshot_meta->>'log_count', '')::integer, 0),
            coalesce(nullif(p_snapshot_meta->>'closeout_count', '')::integer, 0),
            coalesce(nullif(p_snapshot_meta->>'closeout_version_count', '')::integer, 0),
            v_day,
            nullif(v_actor_email, ''),
            nullif(v_actor_name, ''),
            nullif(v_actor_role, '')
        )
        returning * into v_row;
    exception
        when unique_violation then
            if v_type = 'automatic' then
                return jsonb_build_object(
                    'success', false,
                    'code', 'automatic_snapshot_exists',
                    'message', 'Автоматичний архівний знімок за сьогодні вже створено.'
                );
            end if;
            raise;
    end;

    perform monitoring_internal.write_log(
        null,
        case
            when v_replaces is not null then 'Створено архівний знімок-заміна'
            when v_type = 'automatic' then 'Створено автоматичний архівний знімок'
            else 'Створено архівний знімок вручну'
        end,
        '',
        'Створено',
        v_reason,
        p_actor,
        '',
        'archive_snapshots',
        v_row.id::text,
        jsonb_build_object(
            'snapshot_id', v_row.id,
            'snapshot_type', v_type,
            'replaces_snapshot_id', v_replaces,
            'replacement_reason', v_replacement_reason,
            'payload_size_bytes', v_row.payload_size_bytes,
            'structure_row_count', v_row.structure_row_count,
            'request_count', v_row.request_count,
            'version_count', v_row.version_count,
            'measure_count', v_row.measure_count,
            'mio_record_count', v_row.mio_record_count,
            'log_count', v_row.log_count,
            'closeout_count', v_row.closeout_count,
            'closeout_version_count', v_row.closeout_version_count
        )
    );

    if v_replaces is not null then
        perform monitoring_internal.write_log(
            null,
            'Архівний знімок має новішу версію',
            'Чинний архівний знімок',
            'Є новіша версія',
            v_replacement_reason,
            p_actor,
            '',
            'archive_snapshots',
            v_replaces::text,
            jsonb_build_object(
                'old_snapshot_id', v_replaces,
                'new_snapshot_id', v_row.id,
                'replacement_reason', v_replacement_reason
            )
        );
    end if;

    return jsonb_build_object(
        'success', true,
        'code', 'ok',
        'message', 'Архівний знімок створено.',
        'snapshot_id', v_row.id,
        'archived_at', v_row.archived_at,
        'snapshot_type', v_row.snapshot_type,
        'replaces_snapshot_id', v_row.replaces_snapshot_id
    );
end;
$$;

revoke all
    on function public.prevent_archive_snapshot_mutation()
    from public;

revoke all
    on function public.transition_create_archive_snapshot(jsonb, text, jsonb)
    from public;

grant execute
    on function public.transition_create_archive_snapshot(jsonb, text, jsonb)
    to anon, authenticated, service_role;

commit;
