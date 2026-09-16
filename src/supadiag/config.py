from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    project_root: Path
    supabase_url: str
    supabase_key: str
    data_dir: Path
    memory_file: Path
    queue_file: Path
    task_name: str
    ping_count: int
    ping_timeout_seconds: float
    retention_days: int
    internet_check_enabled: bool
    internet_check_ip: str
    internet_check_frequency_seconds: int
    traceroute_enabled: bool
    traceroute_frequency_seconds: int
    traceroute_max_hops: int
    traceroute_timeout_seconds: float

    @property
    def db_dir(self) -> Path:
        return self.data_dir


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_settings(root: Path | None = None) -> Settings:
    root = (root or project_root()).resolve()
    load_dotenv(root / ".env")

    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not supabase_url:
        raise ConfigError("SUPABASE_URL não está configurada. Copie .env.example para .env e preencha o arquivo.")
    if not supabase_key:
        raise ConfigError("SUPABASE_SERVICE_ROLE_KEY não está configurada. Nunca compartilhe essa chave.")

    data_dir = Path(os.getenv("SUPADIAG_DATA_DIR", "data")).expanduser()
    if not data_dir.is_absolute():
        data_dir = root / data_dir

    return Settings(
        project_root=root,
        supabase_url=supabase_url.rstrip("/"),
        supabase_key=supabase_key,
        data_dir=data_dir,
        memory_file=root / "memory.txt",
        queue_file=data_dir / "pending_measurements.jsonl",
        task_name=os.getenv("SUPADIAG_TASK_NAME", "SupaDiag Monitor"),
        ping_count=int(os.getenv("SUPADIAG_PING_COUNT", "100")),
        ping_timeout_seconds=float(os.getenv("SUPADIAG_PING_TIMEOUT_SECONDS", "2.0")),
        retention_days=int(os.getenv("SUPADIAG_RETENTION_DAYS", "180")),
        internet_check_enabled=os.getenv("SUPADIAG_INTERNET_CHECK_ENABLED", "true").lower() == "true",
        internet_check_ip=os.getenv("SUPADIAG_INTERNET_CHECK_IP", "8.8.8.8").strip(),
        internet_check_frequency_seconds=int(os.getenv("SUPADIAG_INTERNET_CHECK_FREQUENCY", "300")),
        traceroute_enabled=os.getenv("SUPADIAG_TRACEROUTE_ENABLED", "true").lower() == "true",
        traceroute_frequency_seconds=int(os.getenv("SUPADIAG_TRACEROUTE_FREQUENCY", "3600")),
        traceroute_max_hops=int(os.getenv("SUPADIAG_TRACEROUTE_MAX_HOPS", "30")),
        traceroute_timeout_seconds=float(os.getenv("SUPADIAG_TRACEROUTE_TIMEOUT", "5.0")),
    )


def ensure_runtime_files(settings: Settings) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.memory_file.touch(exist_ok=True)
    settings.queue_file.parent.mkdir(parents=True, exist_ok=True)


def public_dict(settings: Settings) -> dict[str, Any]:
    return {
        "project_root": str(settings.project_root),
        "supabase_url": settings.supabase_url,
        "data_dir": str(settings.data_dir),
        "memory_file": str(settings.memory_file),
        "queue_file": str(settings.queue_file),
        "task_name": settings.task_name,
        "ping_count": settings.ping_count,
        "retention_days": settings.retention_days,
        "internet_check_enabled": settings.internet_check_enabled,
        "internet_check_ip": settings.internet_check_ip,
        "internet_check_frequency_seconds": settings.internet_check_frequency_seconds,
        "traceroute_enabled": settings.traceroute_enabled,
        "traceroute_frequency_seconds": settings.traceroute_frequency_seconds,
        "traceroute_max_hops": settings.traceroute_max_hops,
        "traceroute_timeout_seconds": settings.traceroute_timeout_seconds,
    }
