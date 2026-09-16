# FrontEnd/repository.py
# Camada de acesso a dados do Supabase para o FrontEnd

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from supabase import create_client, Client

from config import settings


@dataclass(frozen=True)
class Client:
    id: str
    name: str
    created_at: str


@dataclass(frozen=True)
class Machine:
    id: str
    client_id: str
    tag: str
    ip: str
    frequency_seconds: int
    active: bool
    created_at: str


@dataclass(frozen=True)
class Measurement:
    id: str
    client_id: str
    machine_id: str
    latency_ms: float | None
    jitter_ms: float | None
    packet_loss_percent: float
    packets_sent: int
    packets_received: int
    status: str
    measured_at: str


@dataclass(frozen=True)
class TracerouteHop:
    hop_number: int
    ip: str | None
    hostname: str | None
    latency_ms: float | None
    packet_loss_percent: float


@dataclass(frozen=True)
class Traceroute:
    id: str
    client_id: str
    machine_id: str
    target_ip: str
    max_hops: int
    total_hops: int
    destination_reached: bool
    measured_at: str
    hops: list[dict]


class RepositoryError(RuntimeError):
    """Erro na comunicação com Supabase."""
    pass


class FrontendRepository:
    """Repositório para leitura de dados do Supabase no FrontEnd."""
    
    def __init__(self) -> None:
        if not settings.validate():
            raise RepositoryError("Configurações do Supabase não encontradas. Verifique .env")
        self.client: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    
    def _execute(self, query) -> list[dict[str, Any]]:
        """Executa query e retorna dados ou levanta exceção."""
        try:
            response = query.execute()
        except Exception as exc:
            raise RepositoryError(f"Erro ao executar consulta: {exc}") from exc
        
        error = getattr(response, "error", None)
        if error:
            raise RepositoryError(str(error))
        
        return response.data or []
    
    def health_check(self) -> tuple[bool, str]:
        """Verifica conectividade com Supabase."""
        try:
            self._execute(self.client.table("clients").select("id").limit(1))
            return True, "Supabase disponível"
        except RepositoryError as exc:
            return False, str(exc)
    
    def list_clients(self) -> list[Client]:
        """Lista todos os clientes ordenados por nome."""
        data = self._execute(
            self.client.table("clients").select("*").order("name")
        )
        return [
            Client(id=row["id"], name=row["name"], created_at=row["created_at"])
            for row in data
        ]
    
    def list_machines(self, client_id: str | None = None, active_only: bool = True) -> list[Machine]:
        """Lista máquinas, opcionalmente filtradas por cliente e status ativo."""
        query = self.client.table("machines").select("*").order("tag")
        
        if client_id:
            query = query.eq("client_id", client_id)
        if active_only:
            query = query.eq("active", True)
        
        data = self._execute(query)
        return [
            Machine(
                id=row["id"],
                client_id=row["client_id"],
                tag=row["tag"],
                ip=row["ip"],
                frequency_seconds=row["frequency_seconds"],
                active=row["active"],
                created_at=row["created_at"],
            )
            for row in data
        ]
    
    def get_machine(self, machine_id: str) -> Machine | None:
        """Obtém uma máquina específica pelo ID."""
        data = self._execute(
            self.client.table("machines").select("*").eq("id", machine_id).limit(1)
        )
        if not data:
            return None
        row = data[0]
        return Machine(
            id=row["id"],
            client_id=row["client_id"],
            tag=row["tag"],
            ip=row["ip"],
            frequency_seconds=row["frequency_seconds"],
            active=row["active"],
            created_at=row["created_at"],
        )
    
    def get_client(self, client_id: str) -> Client | None:
        """Obtém um cliente específico pelo ID."""
        data = self._execute(
            self.client.table("clients").select("*").eq("id", client_id).limit(1)
        )
        if not data:
            return None
        row = data[0]
        return Client(id=row["id"], name=row["name"], created_at=row["created_at"])
    
    def get_measurements(
        self,
        machine_id: str,
        hours: int = 24,
        limit: int = 500
    ) -> list[dict]:
        """Busca medições de uma máquina nas últimas N horas."""
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        
        data = self._execute(
            self.client.table("measurements")
            .select("*")
            .eq("machine_id", machine_id)
            .gte("measured_at", cutoff)
            .order("measured_at", desc=False)  # Ordem cronológica para gráficos
            .limit(limit)
        )
        return data
    
    def get_latest_measurement(self, machine_id: str) -> dict | None:
        """Retorna a medição mais recente de uma máquina."""
        data = self._execute(
            self.client.table("measurements")
            .select("*")
            .eq("machine_id", machine_id)
            .order("measured_at", desc=True)
            .limit(1)
        )
        if not data:
            return None
        return data[0]
    
    def get_latest_traceroute(self, machine_id: str) -> dict | None:
        """Retorna o traceroute mais recente de uma máquina com seus hops."""
        data = self._execute(
            self.client.table("traceroutes")
            .select("*, traceroute_hops(*)")
            .eq("machine_id", machine_id)
            .order("measured_at", desc=True)
            .limit(1)
        )
        if not data:
            return None
        return data[0]
    
    def get_traceroute_history(self, machine_id: str, limit: int = 10) -> list[dict]:
        """Retorna histórico de traceroutes para uma máquina."""
        data = self._execute(
            self.client.table("traceroutes")
            .select("*")
            .eq("machine_id", machine_id)
            .order("measured_at", desc=True)
            .limit(limit)
        )
        return data or []

    def get_sparkline_data(self, machine_id: str, hours: int = 24) -> list[dict]:
        """Retorna dados para sparkline (latência nos últimos N horas)."""
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        data = self._execute(
            self.client.table("measurements")
            .select("latency_ms, measured_at")
            .eq("machine_id", machine_id)
            .gte("measured_at", cutoff)
            .order("measured_at", desc=False)
            .limit(200)  # Suficiente para sparkline
        )
        return data or []
    
    def get_alert_events(self, machine_id: str, status: str | None = None, limit: int = 50) -> list[dict]:
        """Lista eventos de alerta para uma máquina."""
        query = self.client.table("alert_events").select("*").order("started_at", desc=True)
        if machine_id:
            query = query.eq("machine_id", machine_id)
        if status:
            query = query.eq("status", status)
        query = query.limit(limit)
        return self._execute(query) or []
    
    def get_latest_alert_event(self, machine_id: str) -> dict | None:
        """Retorna o evento de alerta mais recente para uma máquina."""
        events = self.get_alert_events(machine_id)
        if not events:
            return None
        return max(events, key=lambda x: x.get("started_at", ""))
    
    def list_alert_rules(self, machine_id: str | None = None) -> list[dict]:
        """Lista regras de alerta para uma máquina."""
        query = self.client.table("alert_rules").select("*").order("created_at", desc=True)
        if machine_id:
            query = query.eq("machine_id", machine_id)
        query = query.eq("enabled", True)
        return self._execute(query) or []
    
    def get_active_alert_event(self, rule_id: str) -> dict | None:
        """Retorna evento ativo para uma regra."""
        data = self._execute(
            self.client.table("alert_events")
            .select("*")
            .eq("rule_id", rule_id)
            .in_("status", ["firing", "acknowledged"])
            .order("started_at", desc=True)
            .limit(1)
        )
        return data[0] if data else None
    
    def update_alert_event(self, event_id: str, updates: dict) -> dict | None:
        data = self._execute(self.client.table("alert_events").update(updates).eq("id", event_id))
        return data[0] if data else None
    
    def get_machines_with_latest_status(self) -> list[dict[str, Any]]:
        """
        Retorna todas as máquinas com sua última medição para exibição em cards.
        Útil para a view principal de cards.
        """
        machines = self.list_machines(active_only=True)
        result = []
        
        for machine in machines:
            latest = self.get_latest_measurement(machine.id)
            client = self.get_client(machine.client_id)
            
            result.append({
                "machine": machine,
                "client": client,
                "latest_measurement": latest,
            })
        
        return result