#!/usr/bin/env python3
"""Автоматичне створення незмінного архівного знімка ДЕМО 2.0."""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

from supabase import create_client

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.archive import build_archive_payload, create_archive_snapshot  # noqa: E402
from core.timeutils import now_kyiv  # noqa: E402

DRY_RUN = os.environ.get("ARCHIVE_DRY_RUN", "0") == "1"
FORCE_RUN = os.environ.get("ARCHIVE_FORCE_RUN", "0") == "1"
SCHEDULE_MONTHS = {1: (4, -1), 4: (1, 0), 7: (2, 0), 10: (3, 0)}
ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV"}


def reporting_period(now: datetime) -> tuple[int, int]:
    """Повертає квартал, вікно подання якого щойно завершилося."""
    if now.month in SCHEDULE_MONTHS and now.day == 15:
        quarter, year_shift = SCHEDULE_MONTHS[now.month]
        return now.year + year_shift, quarter

    current_quarter = ((now.month - 1) // 3) + 1
    previous_quarter = current_quarter - 1
    year = now.year
    if previous_quarter == 0:
        previous_quarter = 4
        year -= 1
    return year, previous_quarter


def should_run(now: datetime) -> bool:
    return (
        now.day == 15
        and now.month in SCHEDULE_MONTHS
        and now.hour == 18
    )


def main() -> int:
    now = now_kyiv()
    print(
        f"== Архівний знімок, Київ: {now:%d.%m.%Y %H:%M %Z}, "
        f"DRY_RUN={DRY_RUN}, FORCE_RUN={FORCE_RUN} =="
    )

    if not FORCE_RUN and not should_run(now):
        print("-- Зараз не контрольний час 18:00 за Києвом; створення знімка пропущено.")
        return 0

    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_KEY", "").strip()
    if not url or not key:
        print("!! Не задано SUPABASE_URL або SUPABASE_KEY.", file=sys.stderr)
        return 2

    year, quarter = reporting_period(now)
    reason = (
        "Автоматичний знімок за підсумками вікна подання "
        f"{ROMAN[quarter]} квартал {year}"
    )
    actor = {
        "email": "archive-workflow@system.local",
        "name": "Автоматичний архів GitHub Actions",
        "role": "system",
    }
    client = create_client(url, key)

    if DRY_RUN:
        metadata, encoded = build_archive_payload(client, actor, reason)
        print("-- Тестовий прогін: запис у базу НЕ виконується.")
        print(f"-- Причина: {reason}")
        print(
            "-- Вміст: "
            f"заявок={metadata.get('request_count')}, "
            f"версій={metadata.get('version_count')}, "
            f"заходів={metadata.get('measure_count')}, "
            f"МіО={metadata.get('mio_record_count')}, "
            f"журнал={metadata.get('log_count')}, "
            f"стиснений payload={metadata.get('payload_size_bytes')} байт, "
            f"base64={len(encoded)} символів"
        )
        return 0

    try:
        result = create_archive_snapshot(
            client,
            actor=actor,
            reason=reason,
            snapshot_type="automatic",
        )
    except Exception as exc:
        print(f"!! Не вдалося створити автоматичний знімок: {exc}", file=sys.stderr)
        return 1

    if result.get("success"):
        print(
            f"OK: створено архівний знімок №{result.get('snapshot_id')} · {reason}"
        )
        return 0

    if result.get("code") == "automatic_snapshot_exists":
        print(f"-- Автоматичний знімок за сьогодні вже існує: {result.get('message')}")
        return 0

    print(
        f"!! Архівний знімок не створено: {result.get('message') or result}",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
