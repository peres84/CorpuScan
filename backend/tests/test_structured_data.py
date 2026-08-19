from __future__ import annotations

import json
import sys
from pathlib import Path

from pytest import MonkeyPatch

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.investigation import structured
from app.investigation.structured import (
    KeyValueEntry,
    StructuredDataStore,
    StructuredFile,
)


class TestStructuredDataStore:
    def test_save_and_load_round_trip_preserves_data(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        monkeypatch.setattr(structured, "STRUCTURED_DATA_ROOT", tmp_path)
        store = StructuredDataStore()
        store.add_file(
            StructuredFile(
                file_id="ledger-1",
                filename="ledger.csv",
                extraction_method="deterministic",
                columns=["vendor_id", "amount"],
                rows=[{"vendor_id": "209101", "amount": "50000.00"}],
                row_count=1,
            )
        )
        store.add_file(
            StructuredFile(
                file_id="report-1",
                filename="report.pdf",
                extraction_method="llm_assisted",
                key_values=[
                    KeyValueEntry(
                        field="payment_threshold",
                        value="€10,000",
                        context="Two-signature rule",
                    )
                ],
            )
        )

        output_path = store.save_to_json("job-123")
        loaded = StructuredDataStore.load_from_json("job-123")

        assert output_path == tmp_path / "job-123" / "structured_data.json"
        assert loaded.list_files() == store.list_files()

    def test_empty_store_produces_valid_json(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        monkeypatch.setattr(structured, "STRUCTURED_DATA_ROOT", tmp_path)

        output_path = StructuredDataStore().save_to_json("empty-job")

        assert json.loads(output_path.read_text(encoding="utf-8")) == {"files": []}
        assert StructuredDataStore.load_from_json("empty-job").file_count == 0
