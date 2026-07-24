from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field


STRUCTURED_DATA_ROOT = Path("/tmp")


class KeyValueEntry(BaseModel):
    field: str = Field(min_length=1)
    value: str = Field(min_length=1)
    context: str = Field(min_length=1)


class StructuredFile(BaseModel):
    file_id: str = Field(min_length=1)
    filename: str = Field(min_length=1)
    extraction_method: str = Field(min_length=1)
    columns: list[str] | None = None
    rows: list[dict[str, str]] | None = None
    key_values: list[KeyValueEntry] | None = None
    row_count: int = Field(ge=0, default=0)


class StructuredDataStore:
    """In-memory structured file extractions for a single investigation job."""

    def __init__(self) -> None:
        self._files: dict[str, StructuredFile] = {}

    def add_file(self, structured_file: StructuredFile) -> None:
        self._files[structured_file.file_id] = structured_file

    def get_file(self, file_id: str) -> StructuredFile | None:
        return self._files.get(file_id)

    def list_files(self) -> list[StructuredFile]:
        return list(self._files.values())

    @property
    def file_count(self) -> int:
        return len(self._files)

    def save_to_json(self, job_id: str) -> Path:
        output_path = STRUCTURED_DATA_ROOT / job_id / "structured_data.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"files": [structured_file.model_dump(mode="json") for structured_file in self.list_files()]}
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return output_path

    @classmethod
    def load_from_json(cls, job_id: str) -> StructuredDataStore:
        input_path = STRUCTURED_DATA_ROOT / job_id / "structured_data.json"
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("files"), list):
            raise ValueError("structured_data.json must contain a files list")

        store = cls()
        for raw_file in payload["files"]:
            store.add_file(StructuredFile.model_validate(raw_file))
        return store
