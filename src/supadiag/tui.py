from __future__ import annotations

import asyncio
import traceback
from datetime import datetime, timezone
from typing import Optional

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    Header,
    Footer,
    Static,
    Button,
    Input,
    DataTable,
    Label,
    Select,
)
from textual.screen import ModalScreen
from textual.message import Message
from textual.reactive import reactive

from .config import Settings
from .diary import Diary
from .monitor import MonitorService, MonitorEvent
from .queue import LocalQueue
from .supabase_repository import SupabaseRepository

# Debug logging
from .debug_log import logger, log_exception


class ConfirmModal(ModalScreen):
    """Modal de confirmação genérico."""

    def __init__(self, message: str, callback) -> None:
        super().__init__()
        self.message = message
        self.callback = callback
        logger.debug("ConfirmModal inicializado")

    def compose(self) -> ComposeResult:
        yield Container(
            Static(self.message, id="confirm-message"),
            Horizontal(
                Button("Confirmar", id="confirm-yes", variant="error"),
                Button("Cancelar", id="confirm-no", variant="primary"),
                id="confirm-buttons"
            ),
            id="confirm-dialog"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        logger.debug(f"ConfirmModal botão pressionado: {event.button.id}")
        if event.button.id == "confirm-yes":
            logger.debug("ConfirmModal: dismiss True")
            self.dismiss(True)
        else:
            logger.debug("ConfirmModal: dismiss False")
            self.dismiss(False)

    def on_mount(self) -> None:
        logger.debug("ConfirmModal montado")
        self.query_one("#confirm-no", Button).focus()


class ClientFormModal(ModalScreen):
    """Modal para adicionar/editar cliente."""

    def __init__(self, repo: SupabaseRepository, diary: Diary, client_id: Optional[str] = None, current_name: str = "") -> None:
        super().__init__()
        self.repo = repo
        self.diary = diary
        self.client_id = client_id
        self.current_name = current_name
        self.is_edit = client_id is not None
        logger.debug(f"ClientFormModal inicializado: is_edit={self.is_edit}")

    def compose(self) -> ComposeResult:
        title = "Editar Cliente" if self.is_edit else "Adicionar Cliente"
        yield Container(
            Static(title, id="form-title"),
            Input(
                placeholder="Nome do cliente",
                value=self.current_name,
                id="client-name-input"
            ),
            Horizontal(
                Button("Salvar", id="save-client", variant="primary"),
                Button("Cancelar", id="cancel-client", variant="default"),
                id="form-buttons"
            ),
            id="client-form-dialog"
        )

    async def on_mount(self) -> None:
        logger.debug("ClientFormModal montado")
        self.query_one("#client-name-input", Input).focus()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        logger.debug(f"ClientFormModal botão pressionado: {event.button.id}")
        if event.button.id == "save-client":
            name = self.query_one("#client-name-input", Input).value.strip()
            logger.debug(f"ClientFormModal: save-client, name='{name}'")
            if not name:
                self.app.notify("Nome do cliente é obrigatório", severity="error")
                return
            logger.debug(f"ClientFormModal: dismiss com name='{name}'")
            self.dismiss(name)
        else:
            logger.debug("ClientFormModal: dismiss None (cancelar)")
            self.dismiss(None)


class MachineFormModal(ModalScreen):
    """Modal para adicionar/editar máquina."""

    def __init__(
        self,
        repo: SupabaseRepository,
        diary: Diary,
        machine_id: Optional[str] = None,
        client_id: str = "",
        tag: str = "",
        ip: str = "",
        frequency: int = 60,
        active: bool = True,
    ) -> None:
        super().__init__()
        self.repo = repo
        self.diary = diary
        self.machine_id = machine_id
        self.client_id = client_id
        self.tag = tag
        self.ip = ip
        self.frequency = frequency
        self.active = active
        self.is_edit = machine_id is not None
        logger.debug(f"MachineFormModal inicializado: is_edit={self.is_edit}")

    def compose(self) -> ComposeResult:
        title = "Editar Máquina" if self.is_edit else "Adicionar Máquina"
        yield Container(
            Static(title, id="form-title"),
            Input(placeholder="ID do Cliente (obrigatório)", value=self.client_id, id="machine-client-id-input"),
            Input(placeholder="Tag (obrigatório)", value=self.tag, id="machine-tag-input"),
            Input(placeholder="IP (obrigatório)", value=self.ip, id="machine-ip-input"),
            Input(placeholder="Frequência em segundos (mín 10)", value=str(self.frequency), id="machine-freq-input"),
            Select([("Ativa", True), ("Inativa", False)], value=self.active, id="machine-active-select", allow_blank=False),
            Horizontal(
                Button("Salvar", id="save-machine", variant="primary"),
                Button("Cancelar", id="cancel-machine", variant="default"),
                id="form-buttons"
            ),
            id="machine-form-dialog"
        )

    async def on_mount(self) -> None:
        logger.debug("MachineFormModal montado")
        self.query_one("#machine-client-id-input", Input).focus()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        logger.debug(f"MachineFormModal botão pressionado: {event.button.id}")
        if event.button.id == "save-machine":
            client_id = self.query_one("#machine-client-id-input", Input).value.strip()
            tag = self.query_one("#machine-tag-input", Input).value.strip()
            ip = self.query_one("#machine-ip-input", Input).value.strip()
            freq_str = self.query_one("#machine-freq-input", Input).value.strip()
            active = self.query_one("#machine-active-select", Select).value

            logger.debug(f"MachineFormModal: save-machine, client_id={client_id}, tag={tag}, ip={ip}, freq={freq_str}, active={active}")

            if not all([client_id, tag, ip, freq_str]):
                self.app.notify("Todos os campos são obrigatórios", severity="error")
                return
            try:
                freq = int(freq_str)
                if freq < 10:
                    self.app.notify("Frequência mínima é 10 segundos", severity="error")
                    return
            except ValueError:
                self.app.notify("Frequência deve ser um número inteiro", severity="error")
                return

            data = {
                "client_id": client_id,
                "tag": tag,
                "ip": ip,
                "frequency": freq,
                "active": active
            }
            logger.debug(f"MachineFormModal: dismiss com data={data}")
            self.dismiss(data)
        else:
            logger.debug("MachineFormModal: dismiss None (cancelar)")
            self.dismiss(None)


class SupaDiagApp(App):
    TITLE = "SupaDiag"
    CSS = """
    .status-ok { color: green; }
    .status-error { color: red; }
    .status-warning { color: yellow; }
    #left-panel { width: 60%; }
    #right-panel { width: 40%; }
    #client-form-dialog, #machine-form-dialog, #confirm-dialog {
        width: 60;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    #form-title { text-align: center; text-style: bold; margin-bottom: 1; }
    #form-buttons { margin-top: 1; }
    #confirm-message { margin-bottom: 1; text-align: center; }
    #confirm-buttons { margin-top: 1; }
    """

    def __init__(
        self,
        settings: Settings,
        diary: Diary,
        repo: SupabaseRepository,
        queue: LocalQueue,
    ) -> None:
        super().__init__()
        self.settings = settings
        self.diary = diary
        self.repo = repo
        self.queue = queue
        self.monitor: Optional[MonitorService] = None
        self.monitor_task: Optional[asyncio.Task] = None
        self.supabase_status = "Desconhecido"
        self.last_events: list[MonitorEvent] = []
        self._selected_client_id: Optional[str] = None
        self._selected_machine_id: Optional[str] = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Container():
            with Horizontal():
                # Painel esquerdo: Clientes e Máquinas
                with Vertical(id="left-panel"):
                    # --- CLIENTES ---
                    yield Static("📋 Clientes", id="clients-title")
                    yield DataTable(id="clients-table")
                    with Horizontal(id="client-actions"):
                        yield Button("➕ Novo Cliente", id="add-client", variant="primary")
                        yield Button("✏️ Editar Selecionado", id="edit-client", variant="primary")
                        yield Button("🗑️ Excluir Selecionado", id="delete-client", variant="error")

                    # --- MÁQUINAS ---
                    yield Static("🖥️ Máquinas", id="machines-title")
                    yield DataTable(id="machines-table")
                    with Horizontal(id="machine-actions"):
                        yield Button("➕ Nova Máquina", id="add-machine", variant="primary")
                        yield Button("✏️ Editar Selecionado", id="edit-machine", variant="primary")
                        yield Button("🗑️ Excluir Selecionado", id="delete-machine", variant="error")

                # Painel direito: Status, Monitor, Medições, Diário
                with Vertical(id="right-panel"):
                    yield Static("☁️ Supabase: ", id="supabase-status")
                    yield Static("📊 Monitor", id="monitor-title")
                    with Horizontal(id="monitor-controls"):
                        yield Button("▶️ Iniciar Monitor", id="start-monitor", variant="success")
                        yield Button("⏹️ Parar Monitor", id="stop-monitor", variant="error")
                    yield Static("📦 Fila local: 0", id="queue-size")
                    yield Static("📈 Últimas medições:", id="measurements-title")
                    yield DataTable(id="measurements-table")
                    with Horizontal(id="service-controls"):
                        yield Button("🔧 Instalar Serviço", id="install-service", variant="primary")
                        yield Button("🗑️ Remover Serviço", id="remove-service", variant="error")
                    yield Static("📝 Diário (últimas 20 linhas):", id="diary-title")
                    yield DataTable(id="diary-table")
        yield Footer()

    async def on_mount(self) -> None:
        self._init_tables()
        await self.refresh_all()
        self.run_worker(self._check_supabase(), exclusive=True, group="startup")

    def _init_tables(self) -> None:
        clients = self.query_one("#clients-table", DataTable)
        clients.add_columns("ID", "Nome", "Criado em")
        clients.cursor_type = "row"
        clients.zebra_stripes = True

        machines = self.query_one("#machines-table", DataTable)
        machines.add_columns("ID", "Cliente", "Tag", "IP", "Freq (s)", "Ativa")
        machines.cursor_type = "row"
        machines.zebra_stripes = True

        measurements = self.query_one("#measurements-table", DataTable)
        measurements.add_columns("ID", "Máquina", "Tag", "IP", "Latência (ms)", "Jitter (ms)", "Perda (%)", "Status", "Hora")
        measurements.cursor_type = "row"
        measurements.zebra_stripes = True

        diary = self.query_one("#diary-table", DataTable)
        diary.add_columns("Hora", "Evento", "Mensagem")
        diary.cursor_type = "row"
        diary.zebra_stripes = True

    async def _check_supabase(self) -> None:
        ok, msg = await asyncio.to_thread(self.repo.health_check)
        self.supabase_status = f"OK - {msg}" if ok else f"FALHA - {msg}"
        self.query_one("#supabase-status", Static).update(f"☁️ Supabase: {self.supabase_status}")
        self.diary.log("CHECK", msg, {"ok": ok})
        await self.refresh_all()

    async def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        table = event.data_table
        if table.id == "clients-table":
            row_data = table.get_row(event.row_key)
            if row_data:
                self._selected_client_id = str(row_data[0])
                self._selected_machine_id = None
                self.notify(f"Cliente selecionado: {self._selected_client_id[:8]}... ({row_data[1]})")
        elif table.id == "machines-table":
            row_data = table.get_row(event.row_key)
            if row_data:
                self._selected_machine_id = str(row_data[0])
                self._selected_client_id = None
                self.notify(f"Máquina selecionada: {self._selected_machine_id[:8]}... ({row_data[2]})")

    async def refresh_all(self) -> None:
        await self.refresh_clients()
        await self.refresh_machines()
        await self.refresh_measurements()
        await self.refresh_diary()
        self._update_queue_size()

    async def refresh_clients(self) -> None:
        try:
            clients = await asyncio.to_thread(self.repo.list_clients)
            table = self.query_one("#clients-table", DataTable)
            table.clear()
            for c in clients:
                table.add_row(c.id, c.name, c.created_at)
        except Exception as exc:
            self.notify(f"Erro ao listar clientes: {exc}", severity="error")

    async def refresh_machines(self) -> None:
        try:
            machines = await asyncio.to_thread(self.repo.list_machines)
            table = self.query_one("#machines-table", DataTable)
            table.clear()
            for m in machines:
                table.add_row(m.id, m.client_id, m.tag, m.ip, str(m.frequency_seconds), "Sim" if m.active else "Não")
        except Exception as exc:
            self.notify(f"Erro ao listar máquinas: {exc}", severity="error")

    async def refresh_measurements(self) -> None:
        try:
            data = await asyncio.to_thread(self.repo.latest_measurements, 50)
            table = self.query_one("#measurements-table", DataTable)
            table.clear()
            for row in data:
                machine_info = row.get("machines", {})
                table.add_row(
                    row.get("id", "")[:8],
                    row.get("machine_id", "")[:8],
                    machine_info.get("tag", ""),
                    machine_info.get("ip", ""),
                    str(row.get("latency_ms", "")),
                    str(row.get("jitter_ms", "")),
                    str(row.get("packet_loss_percent", "")),
                    row.get("status", ""),
                    row.get("measured_at", ""),
                )
        except Exception as exc:
            self.notify(f"Erro ao listar medições: {exc}", severity="error")

    async def refresh_diary(self) -> None:
        try:
            lines = self.settings.memory_file.read_text(encoding="utf-8").strip().splitlines()[-20:]
            table = self.query_one("#diary-table", DataTable)
            table.clear()
            for line in lines:
                parts = line.split(" | ", 2)
                if len(parts) == 3:
                    table.add_row(*parts)
                else:
                    table.add_row("", "", line)
        except Exception:
            pass

    def _update_queue_size(self) -> None:
        size = self.queue.size()
        self.query_one("#queue-size", Static).update(f"📦 Fila local: {size}")

    # --- Eventos de botões ---
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        logger.debug(f"Botão pressionado: {btn_id}")
        if btn_id == "add-client":
            logger.info("Ação: adicionar cliente")
            await self._action_add_client()
        elif btn_id == "edit-client":
            logger.info("Ação: editar cliente")
            await self._action_edit_client()
        elif btn_id == "delete-client":
            logger.info("Ação: excluir cliente")
            await self._action_delete_client()
        elif btn_id == "add-machine":
            logger.info("Ação: adicionar máquina")
            await self._action_add_machine()
        elif btn_id == "edit-machine":
            logger.info("Ação: editar máquina")
            await self._action_edit_machine()
        elif btn_id == "delete-machine":
            logger.info("Ação: excluir máquina")
            await self._action_delete_machine()
        elif btn_id == "start-monitor":
            logger.info("Ação: iniciar monitor")
            await self._start_monitor()
        elif btn_id == "stop-monitor":
            logger.info("Ação: parar monitor")
            await self._stop_monitor()
        elif btn_id == "install-service":
            logger.info("Ação: instalar serviço")
            await self._install_service()
        elif btn_id == "remove-service":
            logger.info("Ação: remover serviço")
            await self._remove_service()
        logger.debug("Atualizando interface após ação")
        await self.refresh_all()

    # --- CLIENTES ---
    async def _action_add_client(self) -> None:
        logger.info("Iniciando _action_add_client")
        def callback(screen, name: Optional[str]) -> None:
            logger.debug(f"Callback add-client recebido: name={name}")
            if name:
                try:
                    logger.debug("Criando task para _save_client")
                    asyncio.create_task(self._save_client(name))
                except Exception as exc:
                    log_exception(logger, "Erro ao criar task _save_client", exc)
                    self.notify(f"❌ Erro ao criar task: {exc}", severity="error")

        try:
            logger.debug("Abrindo modal ClientFormModal (add)")
            self.push_screen(ClientFormModal(self.repo, self.diary), callback)
            logger.debug("Modal ClientFormModal aberto com sucesso")
        except Exception as exc:
            log_exception(logger, "Erro ao abrir modal ClientFormModal", exc)
            self.notify(f"❌ Erro ao abrir modal: {exc}", severity="error")

    async def _save_client(self, name: str) -> None:
        logger.info(f"_save_client chamado com name={name}")
        try:
            client = await asyncio.to_thread(self.repo.create_client, name)
            self.diary.log("CLIENTE_CRIADO", client.name, {"client_id": client.id})
            self.notify(f"✅ Cliente salvo no Supabase: {client.name} (ID: {client.id[:8]}...)", severity="information")
            await self.refresh_clients()
            logger.info(f"Cliente salvo com sucesso: {client.id}")
        except Exception as exc:
            log_exception(logger, "Erro ao salvar cliente no Supabase", exc)
            self.notify(f"❌ Erro ao salvar no Supabase: {exc}", severity="error")

    async def _action_edit_client(self) -> None:
        logger.info("Iniciando _action_edit_client")
        if not self._selected_client_id:
            self.notify("Selecione um cliente na tabela primeiro", severity="warning")
            return
        client = await asyncio.to_thread(self.repo.get_client, self._selected_client_id)
        if not client:
            self.notify("Cliente não encontrado", severity="error")
            return

        def callback(screen, name: Optional[str]) -> None:
            logger.debug(f"Callback edit-client recebido: name={name}")
            if name:
                try:
                    logger.debug("Criando task para _update_client")
                    asyncio.create_task(self._update_client(name))
                except Exception as exc:
                    log_exception(logger, "Erro ao criar task _update_client", exc)
                    self.notify(f"❌ Erro ao criar task: {exc}", severity="error")

        try:
            logger.debug(f"Abrindo modal ClientFormModal (edit) para client_id={self._selected_client_id}")
            self.push_screen(ClientFormModal(self.repo, self.diary, self._selected_client_id, client.name), callback)
            logger.debug("Modal ClientFormModal (edit) aberto com sucesso")
        except Exception as exc:
            log_exception(logger, "Erro ao abrir modal ClientFormModal (edit)", exc)
            self.notify(f"❌ Erro ao abrir modal: {exc}", severity="error")

    async def _update_client(self, name: str) -> None:
        logger.info(f"_update_client chamado com name={name}, client_id={self._selected_client_id}")
        try:
            updated = await asyncio.to_thread(self.repo.update_client, self._selected_client_id, name)
            self.diary.log("CLIENTE_ATUALIZADO", updated.name, {"client_id": updated.id})
            self._selected_client_id = None
            self.notify(f"✅ Cliente atualizado no Supabase: {updated.name} (ID: {updated.id[:8]}...)", severity="information")
            await self.refresh_clients()
            logger.info(f"Cliente atualizado com sucesso: {updated.id}")
        except Exception as exc:
            log_exception(logger, "Erro ao atualizar cliente no Supabase", exc)
            self.notify(f"❌ Erro ao atualizar no Supabase: {exc}", severity="error")

    async def _action_delete_client(self) -> None:
        logger.info("Iniciando _action_delete_client")
        if not self._selected_client_id:
            self.notify("Selecione um cliente na tabela primeiro", severity="warning")
            return

        def callback(screen, confirmed: bool) -> None:
            logger.debug(f"Callback delete-client recebido: confirmed={confirmed}")
            if confirmed:
                try:
                    asyncio.create_task(self._delete_client())
                except Exception as exc:
                    log_exception(logger, "Erro ao criar task _delete_client", exc)
                    self.notify(f"❌ Erro ao criar task: {exc}", severity="error")

        try:
            logger.debug(f"Abrindo ConfirmModal para client_id={self._selected_client_id}")
            self.push_screen(ConfirmModal(
                f"Excluir cliente {self._selected_client_id[:8]}...?\nIsso removerá TODAS as máquinas e medições associadas.",
                lambda x: x
            ), callback)
            logger.debug("ConfirmModal aberto com sucesso")
        except Exception as exc:
            log_exception(logger, "Erro ao abrir ConfirmModal", exc)
            self.notify(f"❌ Erro ao abrir modal: {exc}", severity="error")

    async def _delete_client(self) -> None:
        logger.info(f"_delete_client chamado para client_id={self._selected_client_id}")
        try:
            await asyncio.to_thread(self.repo.delete_client, self._selected_client_id)
            self.diary.log("CLIENTE_REMOVIDO", "Cliente removido", {"client_id": self._selected_client_id})
            self._selected_client_id = None
            self.notify(f"✅ Cliente excluído do Supabase", severity="information")
            await self.refresh_clients()
            await self.refresh_machines()
            logger.info("Cliente excluído com sucesso")
        except Exception as exc:
            log_exception(logger, "Erro ao excluir cliente no Supabase", exc)
            self.notify(f"❌ Erro ao excluir no Supabase: {exc}", severity="error")
        except Exception as exc:
            log_exception(logger, "Erro ao abrir ConfirmModal", exc)
            self.notify(f"❌ Erro ao abrir modal: {exc}", severity="error")

    async def _delete_client(self) -> None:
        logger.info(f"_delete_client chamado para client_id={self._selected_client_id}")
        try:
            await asyncio.to_thread(self.repo.delete_client, self._selected_client_id)
            self.diary.log("CLIENTE_REMOVIDO", "Cliente removido", {"client_id": self._selected_client_id})
            self._selected_client_id = None
            self.notify(f"✅ Cliente excluído do Supabase", severity="information")
            await self.refresh_clients()
            await self.refresh_machines()
            logger.info("Cliente excluído com sucesso")
        except Exception as exc:
            log_exception(logger, "Erro ao excluir cliente no Supabase", exc)
            self.notify(f"❌ Erro ao excluir no Supabase: {exc}", severity="error")

    # --- MÁQUINAS ---
    async def _action_add_machine(self) -> None:
        logger.info("Iniciando _action_add_machine")
        def callback(screen, data: Optional[dict]) -> None:
            logger.debug(f"Callback add-machine recebido: data={data}")
            if data:
                try:
                    logger.debug("Criando task para _save_machine")
                    asyncio.create_task(self._save_machine(data))
                except Exception as exc:
                    log_exception(logger, "Erro ao criar task _save_machine", exc)
                    self.notify(f"❌ Erro ao criar task: {exc}", severity="error")

        try:
            logger.debug("Abrindo modal MachineFormModal (add)")
            self.push_screen(MachineFormModal(self.repo, self.diary), callback)
            logger.debug("Modal MachineFormModal (add) aberto com sucesso")
        except Exception as exc:
            log_exception(logger, "Erro ao abrir modal MachineFormModal (add)", exc)
            self.notify(f"❌ Erro ao abrir modal: {exc}", severity="error")

    async def _save_machine(self, data: dict) -> None:
        logger.info(f"_save_machine chamado com data={data}")
        try:
            machine = await asyncio.to_thread(
                self.repo.create_machine,
                data["client_id"], data["tag"], data["ip"], data["frequency"]
            )
            self.diary.log("MAQUINA_CRIADA", machine.tag, {"machine_id": machine.id, "client_id": machine.client_id})
            self.notify(f"✅ Máquina salva no Supabase: {machine.tag} (ID: {machine.id[:8]}...)", severity="information")
            await self.refresh_machines()
            logger.info(f"Máquina salva com sucesso: {machine.id}")
        except Exception as exc:
            log_exception(logger, "Erro ao salvar máquina no Supabase", exc)
            self.notify(f"❌ Erro ao salvar no Supabase: {exc}", severity="error")

    async def _action_edit_machine(self) -> None:
        logger.info("Iniciando _action_edit_machine")
        if not self._selected_machine_id:
            self.notify("Selecione uma máquina na tabela primeiro", severity="warning")
            return
        machine = await asyncio.to_thread(self.repo.get_machine, self._selected_machine_id)
        if not machine:
            self.notify("Máquina não encontrada", severity="error")
            return

        def callback(screen, data: Optional[dict]) -> None:
            logger.debug(f"Callback edit-machine recebido: data={data}")
            if data:
                try:
                    logger.debug("Criando task para _update_machine")
                    asyncio.create_task(self._update_machine(data))
                except Exception as exc:
                    log_exception(logger, "Erro ao criar task _update_machine", exc)
                    self.notify(f"❌ Erro ao criar task: {exc}", severity="error")

        try:
            logger.debug(f"Abrindo modal MachineFormModal (edit) para machine_id={self._selected_machine_id}")
            self.push_screen(MachineFormModal(
                self.repo, self.diary, machine.id,
                machine.client_id, machine.tag, machine.ip,
                machine.frequency_seconds, machine.active
            ), callback)
            logger.debug("Modal MachineFormModal (edit) aberto com sucesso")
        except Exception as exc:
            log_exception(logger, "Erro ao abrir modal MachineFormModal (edit)", exc)
            self.notify(f"❌ Erro ao abrir modal: {exc}", severity="error")

    async def _update_machine(self, data: dict) -> None:
        logger.info(f"_update_machine chamado com data={data}, machine_id={self._selected_machine_id}")
        try:
            updated = await asyncio.to_thread(
                self.repo.update_machine,
                self._selected_machine_id,
                tag=data["tag"], ip=data["ip"],
                frequency_seconds=data["frequency"],
                active=data["active"]
            )
            self.diary.log("MAQUINA_ATUALIZADA", updated.tag, {"machine_id": updated.id})
            self._selected_machine_id = None
            self.notify(f"✅ Máquina atualizada no Supabase: {updated.tag} (ID: {updated.id[:8]}...)", severity="information")
            await self.refresh_machines()
            logger.info(f"Máquina atualizada com sucesso: {updated.id}")
        except Exception as exc:
            log_exception(logger, "Erro ao atualizar máquina no Supabase", exc)
            self.notify(f"❌ Erro ao atualizar no Supabase: {exc}", severity="error")

    async def _action_delete_machine(self) -> None:
        logger.info("Iniciando _action_delete_machine")
        if not self._selected_machine_id:
            self.notify("Selecione uma máquina na tabela primeiro", severity="warning")
            return

        def callback(screen, confirmed: bool) -> None:
            logger.debug(f"Callback delete-machine recebido: confirmed={confirmed}")
            if confirmed:
                try:
                    asyncio.create_task(self._delete_machine())
                except Exception as exc:
                    log_exception(logger, "Erro ao criar task _delete_machine", exc)
                    self.notify(f"❌ Erro ao criar task: {exc}", severity="error")

        try:
            logger.debug(f"Abrindo ConfirmModal para machine_id={self._selected_machine_id}")
            self.push_screen(ConfirmModal(
                f"Excluir máquina {self._selected_machine_id[:8]}...?",
                lambda x: x
            ), callback)
            logger.debug("ConfirmModal (machine) aberto com sucesso")
        except Exception as exc:
            log_exception(logger, "Erro ao abrir ConfirmModal (machine)", exc)
            self.notify(f"❌ Erro ao abrir modal: {exc}", severity="error")

    async def _delete_machine(self) -> None:
        logger.info(f"_delete_machine chamado para machine_id={self._selected_machine_id}")
        try:
            await asyncio.to_thread(self.repo.delete_machine, self._selected_machine_id)
            self.diary.log("MAQUINA_REMOVIDA", "Máquina removida", {"machine_id": self._selected_machine_id})
            self._selected_machine_id = None
            self.notify(f"✅ Máquina excluída do Supabase", severity="information")
            await self.refresh_machines()
            logger.info("Máquina excluída com sucesso")
        except Exception as exc:
            log_exception(logger, "Erro ao excluir máquina no Supabase", exc)
            self.notify(f"❌ Erro ao excluir no Supabase: {exc}", severity="error")

    # --- MONITOR ---
    async def _start_monitor(self) -> None:
        if self.monitor and not self.monitor._stop.is_set():
            self.notify("Monitor já está rodando", severity="warning")
            return
        self.monitor = MonitorService(self.settings, self.repo, self.queue, self.diary, self._on_monitor_event)
        self.monitor_task = asyncio.create_task(self.monitor.run_forever())
        self.notify("▶️ Monitor iniciado")
        self.diary.log("MONITOR_INICIADO", "Monitor de medições iniciado")

    async def _stop_monitor(self) -> None:
        if self.monitor and not self.monitor._stop.is_set():
            self.monitor.stop()
            if self.monitor_task:
                await self.monitor_task
            self.notify("⏹️ Monitor parado")
            self.diary.log("MONITOR_PARADO", "Monitor de medições parado")
        else:
            self.notify("Monitor não está rodando", severity="warning")

    def _on_monitor_event(self, event: MonitorEvent) -> None:
        self.last_events.append(event)
        if len(self.last_events) > 100:
            self.last_events = self.last_events[-100:]
        self.call_from_thread(self._update_queue_size)

    # --- SERVIÇO ---
    async def _install_service(self) -> None:
        from .scheduler import WindowsScheduler
        scheduler = WindowsScheduler(self.settings)
        try:
            status = await asyncio.to_thread(scheduler.install)
            self.diary.log("SERVICO_INSTALADO", "Tarefa agendada criada")
            self.notify("🔧 Serviço instalado" if status.installed else "❌ Falha ao instalar", severity="information" if status.installed else "error")
        except Exception as exc:
            self.notify(f"❌ Erro: {exc}", severity="error")

    async def _remove_service(self) -> None:
        from .scheduler import WindowsScheduler
        scheduler = WindowsScheduler(self.settings)
        try:
            await asyncio.to_thread(scheduler.remove)
            self.diary.log("SERVICO_REMOVIDO", "Tarefa agendada removida")
            self.notify("🗑️ Serviço removido", severity="information")
        except Exception as exc:
            self.notify(f"❌ Erro: {exc}", severity="error")