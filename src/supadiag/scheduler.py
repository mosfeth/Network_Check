from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass

from .config import Settings


class SchedulerError(RuntimeError):
    pass


@dataclass(frozen=True)
class SchedulerStatus:
    installed: bool
    output: str


class WindowsScheduler:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def install(self) -> SchedulerStatus:
        executable = shutil.which("schtasks.exe")
        if not executable:
            raise SchedulerError("schtasks.exe não foi encontrado.")
        action = subprocess.list2cmdline([sys.executable, "-m", "supadiag", "monitor"])
        command = [
            executable,
            "/Create",
            "/F",
            "/TN",
            self.settings.task_name,
            "/TR",
            action,
            "/SC",
            "ONLOGON",
            "/RL",
            "LIMITED",
        ]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=30)
        if completed.returncode != 0:
            raise SchedulerError(completed.stderr.strip() or completed.stdout.strip() or "Falha ao criar tarefa.")
        return self.status()

    def status(self) -> SchedulerStatus:
        executable = shutil.which("schtasks.exe")
        if not executable:
            return SchedulerStatus(False, "schtasks.exe não foi encontrado.")
        completed = subprocess.run(
            [executable, "/Query", "/TN", self.settings.task_name, "/V", "/FO", "LIST"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return SchedulerStatus(completed.returncode == 0, (completed.stdout + completed.stderr).strip())

    def remove(self) -> None:
        executable = shutil.which("schtasks.exe")
        if not executable:
            raise SchedulerError("schtasks.exe não foi encontrado.")
        completed = subprocess.run(
            [executable, "/Delete", "/TN", self.settings.task_name, "/F"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if completed.returncode != 0:
            raise SchedulerError(completed.stderr.strip() or completed.stdout.strip() or "Falha ao remover tarefa.")
