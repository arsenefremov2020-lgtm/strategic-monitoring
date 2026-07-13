"""Supabase connection and paginated reading helpers."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import streamlit as st
from supabase import create_client

LOGGER = logging.getLogger(__name__)
PAGE_SIZE = 1000

FilterTuple = tuple[str, str, Any]
FilterSpec = Mapping[str, Any] | Sequence[FilterTuple] | Callable[[Any], Any] | None
OrderTuple = tuple[str, bool]
OrderSpec = str | OrderTuple | Sequence[str | OrderTuple] | None


@st.cache_resource(show_spinner=False)
def get_supabase_client():
    """Return a cached Supabase client configured from Streamlit secrets."""
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])


def _apply_filters(query: Any, filters: FilterSpec) -> Any:
    """Apply reusable filter specifications to a Supabase query builder."""
    if filters is None:
        return query

    if callable(filters):
        return filters(query)

    if isinstance(filters, Mapping):
        for column, value in filters.items():
            query = query.is_(column, "null") if value is None else query.eq(column, value)
        return query

    for operator, column, value in filters:
        method = getattr(query, operator, None)
        if method is None or not callable(method):
            raise ValueError(f"Непідтримуваний оператор фільтра Supabase: {operator}")
        query = method(column, value)
    return query


def _normalise_orders(order: OrderSpec) -> list[OrderTuple]:
    if order is None:
        return [("id", False)]
    if isinstance(order, str):
        return [(order, False)]
    if (
        isinstance(order, tuple)
        and len(order) == 2
        and isinstance(order[0], str)
        and isinstance(order[1], bool)
    ):
        return [order]

    result: list[OrderTuple] = []
    for item in order:
        if isinstance(item, str):
            result.append((item, False))
        else:
            column, desc = item
            result.append((column, bool(desc)))
    return result


def _build_read_query(client: Any, table: str, select: str, filters: FilterSpec,
                      order: OrderSpec, include_count: bool) -> Any:
    query = client.table(table)
    query = query.select(select, count="exact") if include_count else query.select(select)
    query = _apply_filters(query, filters)
    for column, desc in _normalise_orders(order):
        query = query.order(column, desc=desc)
    return query


def fetch_all(
    table: str,
    select: str = "*",
    filters: FilterSpec = None,
    order: OrderSpec = None,
    *,
    client: Any | None = None,
) -> list[dict[str, Any]]:
    """Read all matching rows from a Supabase table in 1000-row pages.

    Supabase/PostgREST commonly limits one response to 1000 rows. This helper
    repeatedly applies ``range(start, end)`` until all rows are collected. The
    first request asks for an exact total count. If fewer rows are returned than
    that count, a technical warning is written to the application log only.

    ``filters`` accepts either a mapping of equality filters, a sequence of
    ``(operator, column, value)`` tuples (for example ``("gte", "id", 10)``),
    or a callable that receives and returns the query builder. ``order`` accepts
    a column name, ``(column, desc)`` or a sequence of those values.
    """
    db_client = client or get_supabase_client()
    rows: list[dict[str, Any]] = []
    expected_count: int | None = None
    start = 0

    while True:
        include_count = start == 0
        query = _build_read_query(
            db_client,
            table,
            select,
            filters,
            order,
            include_count=include_count,
        )
        response = query.range(start, start + PAGE_SIZE - 1).execute()
        page = list(response.data or [])

        if include_count:
            raw_count = getattr(response, "count", None)
            expected_count = int(raw_count) if raw_count is not None else None

        rows.extend(page)

        if not page:
            break
        if expected_count is not None and len(rows) >= expected_count:
            break
        if len(page) < PAGE_SIZE:
            break

        start += PAGE_SIZE

    if expected_count is not None and len(rows) < expected_count:
        LOGGER.warning(
            "Неповне читання таблиці %s: очікувалося %s рядків, отримано %s.",
            table,
            expected_count,
            len(rows),
        )

    return rows
