"""Integration check for the 1000-row Supabase pagination limit.

Before running, create ``public.monitoring_requests_pagination_test`` with the
SQL supplied with DEMO 2.0 Stage 1. The script inserts 1500 rows identified by
a unique marker, reads them through ``core.db.fetch_all`` and always removes
the test rows in ``finally``.

Run from the repository root with a service-role key in the environment:

    SUPABASE_URL=... SUPABASE_KEY=... python scripts/test_pagination.py
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

from supabase import create_client

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.db import fetch_all  # noqa: E402

TABLE_NAME = "monitoring_requests_pagination_test"
ROW_COUNT = 1500
INSERT_BATCH_SIZE = 250


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Не задано обов'язкову змінну середовища {name}.")
    return value


def main() -> None:
    client = create_client(_required_env("SUPABASE_URL"), _required_env("SUPABASE_KEY"))
    marker = f"demo2-pagination-{uuid.uuid4()}"
    rows = [
        {
            "test_marker": marker,
            "sequence_no": sequence_no,
            "payload": f"Тестовий запис {sequence_no}",
        }
        for sequence_no in range(1, ROW_COUNT + 1)
    ]

    try:
        for start in range(0, ROW_COUNT, INSERT_BATCH_SIZE):
            client.table(TABLE_NAME).insert(rows[start:start + INSERT_BATCH_SIZE]).execute()

        loaded = fetch_all(
            TABLE_NAME,
            "id,test_marker,sequence_no,payload",
            filters={"test_marker": marker},
            order=("sequence_no", False),
            client=client,
        )

        if len(loaded) != ROW_COUNT:
            raise AssertionError(
                f"Очікувалося {ROW_COUNT} рядків, але fetch_all повернув {len(loaded)}."
            )

        actual_sequence = [int(row["sequence_no"]) for row in loaded]
        expected_sequence = list(range(1, ROW_COUNT + 1))
        if actual_sequence != expected_sequence:
            raise AssertionError("Порядок або повнота тестових рядків порушені.")

        print(f"OK: fetch_all прочитав усі {len(loaded)} із {ROW_COUNT} тестових рядків.")
    finally:
        client.table(TABLE_NAME).delete().eq("test_marker", marker).execute()
        print("Тестові рядки видалено.")


if __name__ == "__main__":
    main()
