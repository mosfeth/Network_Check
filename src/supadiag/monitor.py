from __future__ import annotations

import asyncio
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from .config import Settings
from .diary import Diary
from .icmp import measure_host
from .models import Machine, MeasurementSample
from .queue import LocalQueue
from .supabase_repository import SupabaseRepository


INTERNET_CHECK_MACHINE_TAG = "INTERNET-CHECK"
INTERNET_CHECK_MACHINE_IP = "8.8.8.8"


@dataclass
class MonitorEvent:
    machine_id: str
    tag: str
    ip: str
    status: str
    latency_ms: float | None
    jitter_ms: float | None
    packet_loss: float
    timestamp: str


class MonitorService:
    def __init__(
        self,
        settings: Settings,
        repository: SupabaseRepository,
        queue: LocalQueue,
        diary: Diary,
        event_callback: Optional[Callable[[MonitorEvent], None]] = None,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.queue = queue
        self.diary = diary
        self.event_callback = event_callback
        self._executor = ThreadPoolExecutor(max_workers=16)
        self._stop = asyncio.Event()
        self._last_cleanup = time.monotonic()
        self._last_run: dict[str, float] = {}
        self._last_internet_check: dict[str, float] = {}

    def stop(self) -> None:
        self._stop.set()

    async def run_forever(self) -> None:
        while not self._stop.is_set():
            await self.run_cycle()
            await asyncio.sleep(1)

    async def run_cycle(self) -> None:
        now = time.monotonic()
        
        # 1. Verifica máquinas regulares
        machines = await asyncio.to_thread(self.repository.list_machines, active_only=True)
        due_machines = [
            m for m in machines
            if self._is_due(m, now)
        ]
        if due_machines:
            await self._measure_batch(due_machines, now)
        
        # 2. Verifica internet check (se habilitado)
        if self.settings.internet_check_enabled:
            await self._run_internet_checks(now)
        
        # 3. Processa fila de retry e limpeza
        await self._retry_queue(now)
        await self._maybe_cleanup(now)

    def _is_due(self, machine: Machine, now: float) -> bool:
        last = self._last_run.get(machine.id, 0)
        interval = max(1, machine.frequency_seconds)
        if now - last >= interval:
            self._last_run[machine.id] = now
            return True
        return False

    def _is_internet_check_due(self, client_id: str, now: float) -> bool:
        last = self._last_internet_check.get(client_id, 0)
        interval = max(1, self.settings.internet_check_frequency_seconds)
        if now - last >= interval:
            self._last_internet_check[client_id] = now
            return True
        return False

    async def _run_internet_checks(self, now: float) -> None:
        """Executa verificação de conectividade com internet (8.8.8.8) para cada cliente."""
        try:
            clients = await asyncio.to_thread(self.repository.list_clients)
            for client in clients:
                if not self._is_internet_check_due(client.id, now):
                    continue
                
                # Busca ou cria máquina de internet check para este cliente
                internet_machine = await self._get_or_create_internet_machine(client.id)
                if not internet_machine:
                    continue
                
                # Executa medição com 100 pings
                sample = await asyncio.to_thread(
                    self._measure_machine,
                    internet_machine,
                    count=self.settings.ping_count,
                    timeout_seconds=self.settings.ping_timeout_seconds,
                )
                
                # Salva medição
                try:
                    await asyncio.to_thread(self.repository.save_measurement, sample)
                    self.diary.log(
                        "INTERNET_CHECK_OK",
                        f"Verificação internet {client.name}",
                        {"client_id": client.id, "latency": sample.latency_ms, "loss": sample.packet_loss_percent},
                    )
                except Exception as exc:
                    self.diary.log(
                        "INTERNET_CHECK_ERRO_ENVIO",
                        f"Falha ao enviar internet check para {client.name}",
                        {"client_id": client.id, "error": str(exc)},
                    )
                    self.queue.enqueue(sample)
                    
        except Exception as exc:
            self.diary.log(
                "INTERNET_CHECK_ERRO",
                "Falha ao executar verificações de internet",
                {"error": str(exc)},
            )

    async def _get_or_create_internet_machine(self, client_id: str) -> Machine | None:
        """Busca ou cria máquina de internet check para o cliente."""
        try:
            # Busca máquina existente com tag INTERNET-CHECK
            machines = await asyncio.to_thread(
                self.repository.list_machines, client_id=client_id, active_only=False
            )
            for m in machines:
                if m.tag == INTERNET_CHECK_MACHINE_TAG:
                    # Garante que está ativa e com IP correto
                    if not m.active or m.ip != self.settings.internet_check_ip:
                        await asyncio.to_thread(
                            self.repository.update_machine,
                            m.id,
                            active=True,
                            ip=self.settings.internet_check_ip,
                            frequency_seconds=self.settings.internet_check_frequency_seconds,
                        )
                    return m
            
            # Cria nova máquina de internet check
            machine = await asyncio.to_thread(
                self.repository.create_machine,
                client_id=client_id,
                tag=INTERNET_CHECK_MACHINE_TAG,
                ip=self.settings.internet_check_ip,
                frequency_seconds=self.settings.internet_check_frequency_seconds,
            )
            self.diary.log(
                "INTERNET_CHECK_MACHINE_CRIADA",
                f"Máquina de internet check criada para cliente",
                {"client_id": client_id, "machine_id": machine.id},
            )
            return machine
        except Exception as exc:
            self.diary.log(
                "INTERNET_CHECK_MACHINE_ERRO",
                f"Falha ao obter/criar máquina internet check",
                {"client_id": client_id, "error": str(exc)},
            )
            return None

    async def _measure_batch(self, machines: list[Machine], now: float) -> None:
        loop = asyncio.get_running_loop()
        tasks = [
            loop.run_in_executor(
                self._executor,
                self._measure_machine,
                machine,
            )
            for machine in machines
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for machine, result in zip(machines, results):
            if isinstance(result, Exception):
                self.diary.log(
                    "ERRO_MEDICAO",
                    f"Falha ao medir {machine.tag} ({machine.ip})",
                    {"machine_id": machine.id, "error": str(result)},
                )
                self.queue.enqueue(
                    MeasurementSample(
                        client_id=machine.client_id,
                        machine_id=machine.id,
                        latency_ms=None,
                        jitter_ms=None,
                        packet_loss_percent=100.0,
                        packets_sent=0,
                        packets_received=0,
                        status="error",
                        measured_at=datetime.now(timezone.utc).isoformat(),
                    )
                )
                continue
            sample = result
            try:
                await asyncio.to_thread(self.repository.save_measurement, sample)
                self.diary.log(
                    "MEDICAO_OK",
                    f"Medição enviada para {sample.machine_id}",
                    {"machine_id": sample.machine_id, "latency": sample.latency_ms},
                )
            except Exception as exc:
                self.diary.log(
                    "ERRO_ENVIO",
                    f"Falha ao enviar medição para Supabase",
                    {"machine_id": sample.machine_id, "error": str(exc)},
                )
                self.queue.enqueue(sample)

    def _measure_machine(self, machine: Machine, count: int | None = None, timeout_seconds: float | None = None) -> MeasurementSample:
        return measure_host(
            ip=machine.ip,
            client_id=machine.client_id,
            machine_id=machine.id,
            count=count or self.settings.ping_count,
            timeout_seconds=timeout_seconds or self.settings.ping_timeout_seconds,
        )

    async def _retry_queue(self, now: float) -> None:
        due = await asyncio.to_thread(self.queue.due_entries)
        for entry in due:
            sample_data = entry.get("sample", {})
            sample = MeasurementSample(**sample_data)
            try:
                await asyncio.to_thread(self.repository.save_measurement, sample)
                await asyncio.to_thread(self.queue.acknowledge, entry["id"])
                self.diary.log(
                    "RETRY_OK",
                    "Medição reenviada com sucesso",
                    {"entry_id": entry["id"]},
                )
            except Exception as exc:
                await asyncio.to_thread(self.queue.fail, entry["id"], str(exc))
                self.diary.log(
                    "RETRY_FALHA",
                    "Falha ao reenviar medição",
                    {"entry_id": entry["id"], "error": str(exc)},
                )

    async def _maybe_cleanup(self, now: float) -> None:
        if now - self._last_cleanup > 86400:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=self.settings.retention_days)).isoformat()
            try:
                await asyncio.to_thread(self.repository.cleanup_old_measurements, cutoff)
                self.diary.log("LIMPEZA", f"Medições antigas removidas (>{self.settings.retention_days} dias)")
            except Exception as exc:
                self.diary.log("ERRO_LIMPEZA", "Falha ao limpar medições antigas", {"error": str(exc)})
            self._last_cleanup = now