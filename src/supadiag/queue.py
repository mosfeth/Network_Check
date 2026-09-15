from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .models import MeasurementSample


class LocalQueueError(RuntimeError):
    pass


class LocalQueue:
    def __init__(self, path: Path, max_retries: int = 10, base_delay_seconds: int = 30) -> None:
        self.path = path
        self.max_retries = max_retries
        self.base_delay_seconds = base_delay_seconds
        self._lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")

    def enqueue(self, sample: MeasurementSample) -> dict[str, Any]:
        entry = {
            "id": str(uuid.uuid4()),
            "created_at": self._now_iso(),
            "attempts": 0,
            "next_attempt_at": self._now_iso(),
            "last_error": None,
            "sample": sample.as_insert(),
        }
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry

    def due_entries(self, now: datetime | None = None) -> list[dict[str, Any]]:
        now = now or datetime.now(timezone.utc)
        with self._lock:
            entries = self._read()
        return [entry for entry in entries if self._parse_time(entry.get("next_attempt_at")) <= now]

    def acknowledge(self, entry_id: str) -> None:
        with self._lock:
            entries = [entry for entry in self._read() if entry.get("id") != entry_id]
            self._rewrite(entries)

    def fail(self, entry_id: str, error: str) -> dict[str, Any] | None:
        with self._lock:
            entries = self._read()
            for entry in entries:
                if entry.get("id") == entry_id:
                    entry["attempts"] = int(entry.get("attempts", 0)) + 1
                    entry["last_error"] = str(error)[:500]
                    if entry["attempts"] >= self.max_retries:
                        entry["next_attempt_at"] = "dead-letter"
                    else:
                        delay = min(3600, self.base_delay_seconds * (2 ** (entry["attempts"] - 1)))
                        entry["next_attempt_at"] = (datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat()
                    self._rewrite(entries)
                    return entry
        return None

    def size(self) -> int:
        with self._lock:
            return len(self._read())

    def dead_letter_size(self) -> int:
        with self._lock:
            return sum(1 for entry in self._read() if entry.get("next_attempt_at") == "dead-letter")

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        entries: list[dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise LocalQueueError(f"Registro corrompido na linha {line_number} da fila local.") from exc
                if isinstance(value, dict):
                    entries.append(value)
        return entries

    def _rewrite(self, entries: list[dict[str, Any]]) -> None:
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            for entry in entries:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        os.replace(temporary, self.path)

    @staticmethod
    def _parse_time(value: Any) -> datetime:
        if not value or value == "dead-letter":
            return datetime.max.replace(tzinfo=timezone.utc)
        try:
            parsed = datetime.fromisoformat(str(value))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return datetime.max.replace(tzinfo=timezone.utc)

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")
