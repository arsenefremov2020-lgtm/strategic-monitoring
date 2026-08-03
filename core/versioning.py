# core/versioning.py

"""
Спільна логіка версіювання заявок моніторингу (monitoring_request_versions).

Раніше ця логіка існувала тільки всередині pages/3_Мої_заявки.py
(повторне подання після доопрацювання). Винесено сюди, щоб її могли
використовувати й інші місця, де тепер теж можливе редагування вже
поданої інформації:

- pages/3_Мої_заявки.py    — подавач редагує свою заявку (пункт 3 ТЗ);
- pages/1_Мій_кабінет.py   — керівник ССП або заступник редагує дані
                              перед остаточним погодженням;
- pages/3_Адміністрування.py — координатор або супер-адмін редагує дані
                              на своїй поточній ланці маршруту.

Принцип той самий у всіх трьох місцях: перед тим, як перезаписати
monitoring_requests, стара версія рядка зберігається в
monitoring_request_versions, а після запису — зберігається й нова.
Так вся історія значень лишається доступною (пор. pages/6_Журнал_дій.py).
"""

from __future__ import annotations

from core import approval_schemes as schemes
from core.data_types import normalise_monitoring_frame, prepare_monitoring_payload
from core.db import fetch_all, get_supabase_client


def get_next_version_number(request_id) -> int:
    supabase = get_supabase_client()
    response = (
        supabase
        .table("monitoring_request_versions")
        .select("version_number")
        .eq("request_id", int(request_id))
        .order("version_number", desc=True)
        .limit(1)
        .execute()
    )

    if not response.data:
        return 1

    return int(response.data[0].get("version_number", 0)) + 1


def _clean(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in ("nan", "none", "null"):
        return ""
    return text


def save_request_version(request_id, row_data: dict, created_by: str = "система") -> int:
    """
    Зберігає знімок рядка ПЕРЕД зміною у monitoring_request_versions.

    row_data — словник чи Series із повним поточним станом рядка
    monitoring_requests (напр. selected_row.to_dict()).
    created_by — короткий підпис джерела версії, напр.:
        "ССП / до редагування", "ССП / повторне подання",
        "Керівник ССП / редагування", "Супер-адмін / коригування після закриття".
    """
    version_number = get_next_version_number(request_id)

    payload = {
        "request_id": int(request_id),
        "version_number": version_number,
        "year": _clean(row_data.get("year", "")),
        "quarter": _clean(row_data.get("quarter", "")),
        "department": _clean(row_data.get("department", "")),
        "responsible_person": _clean(row_data.get("responsible_person", "")),
        "phone": _clean(row_data.get("phone", "")),
        "email": _clean(row_data.get("email", "")),
        "strat_code": _clean(row_data.get("strat_code", "")),
        "status": _clean(row_data.get("status", "")),
        "progress_text": _clean(row_data.get("progress_text", "")),
        "numeric_value": _clean(row_data.get("numeric_value", "")),
        "risks": _clean(row_data.get("risks", "")),
        "file_names": _clean(row_data.get("file_names", "")),
        "file_urls": _clean(row_data.get("file_urls", "")),
        "approval_status": _clean(row_data.get("approval_status", "")),
        "admin_comment": _clean(row_data.get("admin_comment", "")),
        "start_date": _clean(row_data.get("start_date", "")),
        "end_date": _clean(row_data.get("end_date", "")),
        "npa_link": _clean(row_data.get("npa_link", "")),
        "approval_chain": schemes.chain_to_json(
            schemes.parse_chain(row_data.get("approval_chain", ""))
        ),
        "chain_stage": schemes.parse_stage(row_data.get("chain_stage")),
        "scheme_label": _clean(row_data.get("scheme_label", "")),
        "object_kind": _clean(row_data.get("object_kind", "")),
        "object_name": _clean(row_data.get("object_name", "")),
        "indicator_name": _clean(row_data.get("indicator_name", "")),
        "as_of_date": _clean(row_data.get("as_of_date", "")),
        "created_by": created_by,
    }

    payload = prepare_monitoring_payload(payload)
    supabase = get_supabase_client()
    supabase.table("monitoring_request_versions").insert(payload).execute()
    return version_number


def load_versions(request_id):
    import pandas as pd

    rows = fetch_all(
        "monitoring_request_versions",
        "*",
        filters=[("eq", "request_id", int(request_id))],
        order=("version_number", False),
    )
    return normalise_monitoring_frame(pd.DataFrame(rows))


def coordinator_stage_index(chain: list[dict]) -> int:
    """Сумісна обгортка над єдиним визначенням координаторської ланки."""
    return schemes.coordinator_stage_index(chain)
