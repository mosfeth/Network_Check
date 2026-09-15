from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any


class Diary:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")

    def log(self, event: str, message: str, details: dict[str, Any] | None = None) -> None:
        safe_details = self._sanitize(details or {})
        suffix = ""
        if safe_details:
            rendered = ", ".join(f"{key}={value}" for key, value in safe_details.items())
            suffix = f" | {rendered}"
        line = f"{self._timestamp()} | {event.upper()} | {message}{suffix}\n"
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line)

    @staticmethod
    def _timestamp() -> str:
        return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _sanitize(details: dict[str, Any]) -> dict[str, str]:
        blocked = ("key", "token", "secret", "password", "senha", "auth", "authorization")
        sanitized: dict[str, str] = {}
        for key, value in details.items():
            if any(part in key.lower() for part in blocked):
                sanitized[key] = "[redigido]"
                continue
            if isinstance(value, (dict, list)):
                sanitized[key] = str(value)[:240]
            else:
                sanitized[key] = str(value)[:240]
        return sanitized
