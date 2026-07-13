-- ДЕМО 2.0 — Етап 1, міграція 011.
-- Переводить роки, квартали, дати та фактичні значення на справжні типи.
-- Виконувати лише після інвентаризаційного SELECT із супровідної інструкції.

begin;

create or replace function public.demo2_parse_year(raw_value text)
returns smallint
language plpgsql
immutable
as $$
declare
    matched_year text;
begin
    if raw_value is null or btrim(raw_value) = '' then
        return null;
    end if;

    matched_year := substring(raw_value from '(20[0-9]{2})');
    if matched_year is null then
        raise exception 'Не вдалося перетворити рік: "%"', raw_value;
    end if;

    return matched_year::smallint;
end;
$$;

create or replace function public.demo2_parse_quarter(raw_value text)
returns smallint
language plpgsql
immutable
as $$
declare
    normalised text;
begin
    if raw_value is null or btrim(raw_value) = '' then
        return null;
    end if;

    normalised := upper(btrim(raw_value));
    normalised := replace(normalised, 'КВАРТАЛ', '');
    normalised := replace(normalised, 'КВ.', '');
    normalised := replace(normalised, '.', '');
    normalised := replace(normalised, 'І', 'I');
    normalised := btrim(normalised);

    case normalised
        when '1' then return 1;
        when 'I' then return 1;
        when '2' then return 2;
        when 'II' then return 2;
        when '3' then return 3;
        when 'III' then return 3;
        when '4' then return 4;
        when 'IV' then return 4;
        when 'РІК' then return null;
        when 'ВЕСЬ РІК' then return null;
        else
            raise exception 'Не вдалося перетворити квартал: "%"', raw_value;
    end case;
end;
$$;

create or replace function public.demo2_parse_date(raw_value text, boundary text default 'start')
returns date
language plpgsql
immutable
as $$
declare
    normalised text;
    found text[];
    found_quarter smallint;
    found_year integer;
    candidate date;
    result_date date;
begin
    if raw_value is null or btrim(raw_value) = '' then
        return null;
    end if;

    normalised := replace(replace(raw_value, chr(160), ' '), E'\n', ' ');
    normalised := regexp_replace(normalised, '[[:space:]]+', ' ', 'g');
    normalised := btrim(normalised);

    if normalised ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' then
        return normalised::date;
    end if;

    if normalised ~ '^[0-9]{2}\.[0-9]{2}\.[0-9]{4}$' then
        return make_date(
            substring(normalised from 7 for 4)::integer,
            substring(normalised from 4 for 2)::integer,
            substring(normalised from 1 for 2)::integer
        );
    end if;

    if normalised ~ '^[0-9]{2}/[0-9]{2}/[0-9]{4}$' then
        return make_date(
            substring(normalised from 7 for 4)::integer,
            substring(normalised from 4 for 2)::integer,
            substring(normalised from 1 for 2)::integer
        );
    end if;

    for found in
        select regexp_matches(
            normalised,
            '([1-4]|IV|III|II|I|ІV|ІІІ|ІІ|І)[[:space:]-]*й?[[:space:]]*квартал[^0-9]*(20[0-9]{2})',
            'gi'
        )
    loop
        found_quarter := public.demo2_parse_quarter(found[1]);
        found_year := found[2]::integer;

        if lower(boundary) = 'end' then
            candidate := (
                make_date(found_year, found_quarter * 3, 1)
                + interval '1 month'
                - interval '1 day'
            )::date;
            if result_date is null or candidate > result_date then
                result_date := candidate;
            end if;
        else
            candidate := make_date(found_year, (found_quarter - 1) * 3 + 1, 1);
            if result_date is null or candidate < result_date then
                result_date := candidate;
            end if;
        end if;
    end loop;

    if result_date is null then
        raise exception 'Не вдалося перетворити дату/період: "%"', raw_value;
    end if;

    return result_date;
end;
$$;

-- Перед зміною типів прибираємо індекси, що залежать від текстових полів.
drop index if exists public.idx_monitoring_requests_code_period;
drop index if exists public.uq_measure_request_per_period;
drop index if exists public.idx_closeout_period_code;
drop index if exists public.idx_closeout_requests_period;
drop index if exists public.uq_confirmed_closeout_per_period;
drop index if exists public.idx_archive_snapshots_period;

-- Текстовий порожній default не можна автоматично привести до date.
alter table public.monitoring_request_versions
    alter column as_of_date drop default;

-- Річне ручне закриття зберігається з NULL у полі кварталу.
alter table public.closeout_requests
    alter column period_quarter drop not null;

-- Основна таблиця заявок.
alter table public.monitoring_requests
    alter column year type smallint using public.demo2_parse_year(year),
    alter column quarter type smallint using public.demo2_parse_quarter(quarter),
    alter column start_date type date using public.demo2_parse_date(start_date, 'start'),
    alter column end_date type date using public.demo2_parse_date(end_date, 'end'),
    alter column as_of_date type date using public.demo2_parse_date(as_of_date, 'end');

alter table public.monitoring_requests
    rename column numeric_value to numeric_value_legacy;

alter table public.monitoring_requests
    add column numeric_value numeric,
    add column value_text text;

update public.monitoring_requests
set
    numeric_value = case
        when nullif(btrim(numeric_value_legacy), '') is null then null
        when replace(
            regexp_replace(replace(numeric_value_legacy, chr(160), ''), '[[:space:]]+', '', 'g'),
            ',', '.'
        ) ~ '^[+-]?([0-9]+([.][0-9]+)?|[.][0-9]+)$'
        then replace(
            regexp_replace(replace(numeric_value_legacy, chr(160), ''), '[[:space:]]+', '', 'g'),
            ',', '.'
        )::numeric
        else null
    end,
    value_text = case
        when nullif(btrim(numeric_value_legacy), '') is null then null
        when replace(
            regexp_replace(replace(numeric_value_legacy, chr(160), ''), '[[:space:]]+', '', 'g'),
            ',', '.'
        ) ~ '^[+-]?([0-9]+([.][0-9]+)?|[.][0-9]+)$'
        then null
        else btrim(numeric_value_legacy)
    end;

alter table public.monitoring_requests
    drop column numeric_value_legacy;

-- Історичні версії заявок мають ту саму структуру типів.
alter table public.monitoring_request_versions
    alter column year type smallint using public.demo2_parse_year(year),
    alter column quarter type smallint using public.demo2_parse_quarter(quarter),
    alter column start_date type date using public.demo2_parse_date(start_date, 'start'),
    alter column end_date type date using public.demo2_parse_date(end_date, 'end'),
    alter column as_of_date type date using public.demo2_parse_date(as_of_date, 'end');

alter table public.monitoring_request_versions
    rename column numeric_value to numeric_value_legacy;

alter table public.monitoring_request_versions
    add column numeric_value numeric,
    add column value_text text;

update public.monitoring_request_versions
set
    numeric_value = case
        when nullif(btrim(numeric_value_legacy), '') is null then null
        when replace(
            regexp_replace(replace(numeric_value_legacy, chr(160), ''), '[[:space:]]+', '', 'g'),
            ',', '.'
        ) ~ '^[+-]?([0-9]+([.][0-9]+)?|[.][0-9]+)$'
        then replace(
            regexp_replace(replace(numeric_value_legacy, chr(160), ''), '[[:space:]]+', '', 'g'),
            ',', '.'
        )::numeric
        else null
    end,
    value_text = case
        when nullif(btrim(numeric_value_legacy), '') is null then null
        when replace(
            regexp_replace(replace(numeric_value_legacy, chr(160), ''), '[[:space:]]+', '', 'g'),
            ',', '.'
        ) ~ '^[+-]?([0-9]+([.][0-9]+)?|[.][0-9]+)$'
        then null
        else btrim(numeric_value_legacy)
    end;

alter table public.monitoring_request_versions
    drop column numeric_value_legacy;

-- Періоди ручних закриттів та архівних знімків теж стають типізованими.
alter table public.closeout_requests
    alter column period_year type smallint using public.demo2_parse_year(period_year),
    alter column period_quarter type smallint using public.demo2_parse_quarter(period_quarter);

alter table public.archive_snapshots
    alter column year type smallint using public.demo2_parse_year(year),
    alter column quarter type smallint using public.demo2_parse_quarter(quarter);

-- Обмеження цілісності під нові типи.
alter table public.monitoring_requests
    add constraint chk_monitoring_requests_quarter
        check (quarter is null or quarter between 1 and 4),
    add constraint chk_monitoring_requests_date_range
        check (start_date is null or end_date is null or start_date <= end_date);

alter table public.monitoring_request_versions
    add constraint chk_monitoring_request_versions_quarter
        check (quarter is null or quarter between 1 and 4),
    add constraint chk_monitoring_request_versions_date_range
        check (start_date is null or end_date is null or start_date <= end_date);

alter table public.closeout_requests
    add constraint chk_closeout_requests_period_quarter
        check (period_quarter is null or period_quarter between 1 and 4);

alter table public.archive_snapshots
    add constraint chk_archive_snapshots_quarter
        check (quarter is null or quarter between 1 and 4);

-- Індекси відновлюються вже на smallint-полях.
create index idx_monitoring_requests_code_period
    on public.monitoring_requests (strat_code, year, quarter);

create unique index uq_measure_request_per_period
    on public.monitoring_requests (strat_code, year, quarter)
    where object_kind = 'measure';

create index idx_closeout_period_code
    on public.closeout_requests (strat_code, period_year, period_quarter, approval_status);

create index idx_closeout_requests_period
    on public.closeout_requests (strat_code, period_year, period_quarter);

create unique index uq_confirmed_closeout_per_period
    on public.closeout_requests (strat_code, period_year, period_quarter)
    where approval_status = 'Підтверджено';

create index idx_archive_snapshots_period
    on public.archive_snapshots (year, quarter);

-- Допоміжні функції потрібні лише під час міграції.
drop function public.demo2_parse_date(text, text);
drop function public.demo2_parse_quarter(text);
drop function public.demo2_parse_year(text);

commit;
