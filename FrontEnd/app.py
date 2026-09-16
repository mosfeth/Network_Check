# FrontEnd/app.py
# Dashboard Principal - AI Network Analyzer

import streamlit as st
from streamlit_autorefresh import st_autorefresh
from typing import Optional
import pandas as pd
from datetime import datetime
import subprocess
import os

from config import settings
from repository import FrontendRepository, RepositoryError
from components import (
    render_machine_card,
    render_metrics_charts,
    render_sidebar_filters,
    render_status_badge,
    render_traceroute_tab,
    render_alert_tab,
)

# Configuração da página
st.set_page_config(
    page_title=settings.PAGE_TITLE,
    page_icon=settings.PAGE_ICON,
    layout=settings.LAYOUT,
    initial_sidebar_state="expanded",
)

# CSS customizado
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: 800;
        color: #1f77b4;
        margin-bottom: 0.5rem;
        letter-spacing: -0.02em;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        border-radius: 12px;
        padding: 20px;
        margin: 10px 0;
    }
    .stButton > button {
        border-radius: 8px;
        font-weight: 500;
    }
    div[data-testid="stHorizontalBlock"] > div {
        padding: 0 8px;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_repository() -> FrontendRepository:
    """Inicializa repositório (cached)."""
    return FrontendRepository()


def init_session_state() -> None:
    """Inicializa estado da sessão."""
    if "selected_machine_id" not in st.session_state:
        st.session_state.selected_machine_id = None
    if "view_mode" not in st.session_state:
        st.session_state.view_mode = "cards"  # "cards" ou "detail"


def on_machine_click(machine_id: str) -> None:
    """Callback ao clicar em um card de máquina."""
    st.session_state.selected_machine_id = machine_id
    st.session_state.view_mode = "detail"
    st.rerun()


def run_traceroute_cli(machine_id: str) -> bool:
    """Executa traceroute via CLI e retorna True se sucesso."""
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    venv_python = os.path.join(project_dir, "venv", "Scripts", "python.exe")
    if not os.path.exists(venv_python):
        venv_python = "python"
    try:
        with st.spinner(f"🔍 Executando traceroute..."):
            result = subprocess.run(
                [venv_python, "-m", "supadiag", "traceroute", "--machine-id", machine_id],
                capture_output=True,
                text=True,
                timeout=600,
            )
        if result.returncode == 0:
            st.success("Traceroute executado com sucesso!")
            return True
        else:
            st.error(f"Erro: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        st.error("Traceroute demorou muito. Tente novamente.")
        return False
    except FileNotFoundError:
        st.error("Python não encontrado.")
        return False


def format_event_time(timestamp: str) -> str:
    """Converte timestamp UTC para America/Sao_Paulo e formata como DD/MM HH:MM."""
    if not timestamp:
        return ""
    try:
        # Tenta parsear como ISO format
        if "T" in timestamp:
            dt = pd.to_datetime(timestamp)
        else:
            dt = pd.to_datetime(timestamp, errors="coerce")
        if dt is pd.NaT or dt is None:
            return timestamp[:5]  # DD/MM HH:MM fallback
        # Converte para America/Sao_Paulo
        if dt.tz is None:
            dt = dt.tz_localize("UTC")
        dt_sp = dt.tz_convert("America/Sao_Paulo")
        return dt_sp.strftime("%d/%m %H:%M")
    except Exception:
        return timestamp[:5] if len(timestamp) >= 5 else timestamp


def get_sidebar_events(repo: FrontendRepository, limit: int = 30) -> list[dict]:
    """Gera eventos da sidebar a partir de dados reais do Supabase."""
    events = []
    try:
        machines_data = repo.get_machines_with_latest_status()
    except Exception:
        return []
    
    for m in machines_data:
        machine = m["machine"]
        client = m["client"]
        latest = m["latest_measurement"]
        
        client_name = client.name if client else "?"
        machine_tag = machine.tag if machine else machine.id[:8]
        
        # Verifica alertas ativos
        try:
            alert_rules = repo.list_alert_rules(machine.id)
            for rule in alert_rules:
                event = repo.get_active_alert_event(rule.get("id", ""))
                if event:
                    severity = event.get("severity", "warning")
                    metric = event.get("metric", "")
                    value = event.get("metric_value", 0)
                    threshold = event.get("threshold_value", 0)
                    started = event.get("started_at", "")[:19].replace("T", " ")
                    
                    if severity == "critical" or event.get("status") == "firing":
                        icon = "🔴"
                        event_type = "CRITICAL"
                    elif severity == "warning":
                        icon = "🟡"
                        event_type = "WARNING"
                    else:
                        icon = "🟠"
                        event_type = "ACK"
                    
                    events.append({
                        "timestamp": started or "",
                        "event": event_type,
                        "message": f"{icon} {machine_tag}: {metric}={value} (>{threshold})",
                        "severity": severity,
                    })
        except Exception:
            pass
        
        # Status da máquina
        if latest:
            status = latest.get("status", "ok")
            latency = latest.get("latency_ms")
            loss = latest.get("packet_loss_percent")
            measured = latest.get("measured_at", "")[:19].replace("T", " ")
            
            if status == "unreachable":
                events.append({
                    "timestamp": measured,
                    "event": "UNREACHABLE",
                    "message": f"🔴 {machine_tag}: INALCANÇÁVEL (loss: {loss}%)",
                    "severity": "critical",
                })
            elif status == "partial":
                events.append({
                    "timestamp": measured,
                    "event": "PARTIAL",
                    "message": f"🟡 {machine_tag}: PARCIAL (lat: {latency}ms, loss: {loss}%)",
                    "severity": "warning",
                })
            elif status == "error":
                events.append({
                    "timestamp": measured,
                    "event": "ERROR",
                    "message": f"🔴 {machine_tag}: ERRO",
                    "severity": "critical",
                })
            else:
                events.append({
                    "timestamp": measured,
                    "event": "OK",
                    "message": f"🟢 {machine_tag}: OK ({latency}ms)",
                    "severity": "ok",
                })
    
    # Ordena por severidade (critical > warning > ack > ok) e tempo
    severity_order = {"critical": 0, "warning": 1, "ack": 2, "ok": 3}
    events.sort(key=lambda e: (severity_order.get(e.get("severity", "ok"), 3), e.get("timestamp", "")))
    
    return events[-limit:]


def render_cards_view(repo: FrontendRepository, client_id: Optional[str]) -> None:
    """Renderiza a view de cards (lista de máquinas)."""
    st.markdown('<h1 class="main-header">AI Network Analyzer</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Clique em um card para ver métricas detalhadas da máquina</p>', unsafe_allow_html=True)
    
    # Tenta buscar máquinas com status
    try:
        with st.spinner("Carregando máquinas..."):
            machines_data = repo.get_machines_with_latest_status()
        
        if client_id:
            machines_data = [m for m in machines_data if m["machine"].client_id == client_id]
        
        if not machines_data:
            st.info("Nenhuma máquina encontrada com os filtros atuais.")
            return
        
        # Busca traceroute e alertas para cada máquina
        for m in machines_data:
            m["latest_traceroute"] = repo.get_latest_traceroute(m["machine"].id)
            m["latest_alert_event"] = repo.get_latest_alert_event(m["machine"].id)
        
        # Métricas gerais
        total = len(machines_data)
        ok_count = sum(1 for m in machines_data if m["latest_measurement"] and m["latest_measurement"].get("status") == "ok")
        warning_count = sum(1 for m in machines_data if m["latest_measurement"] and m["latest_measurement"].get("status") == "partial")
        critical_count = sum(1 for m in machines_data if m["latest_measurement"] and m["latest_measurement"].get("status") == "unreachable")
        no_data_count = sum(1 for m in machines_data if not m["latest_measurement"])
        
        # Alertas ativos
        alert_active_count = sum(1 for m in machines_data if m["latest_alert_event"] and m["latest_alert_event"].get("status") in ["firing", "acknowledged"])
        
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        col1.metric("Total", total)
        col2.metric("🟢 OK", ok_count)
        col3.metric("🟡 Parcial", warning_count)
        col4.metric("🔴 Crítico", critical_count)
        col5.metric("⚪ Sem dados", no_data_count)
        col6.metric("🔔 Alertas", alert_active_count)
        
        st.divider()
        
        # Grid de cards (3 colunas)
        cols_per_row = 3
        for i in range(0, len(machines_data), cols_per_row):
            cols = st.columns(cols_per_row)
            for j, col in enumerate(cols):
                idx = i + j
                if idx < len(machines_data):
                    m = machines_data[idx]
                    with col:
                        render_machine_card(
                            machine=m["machine"],
                            client=m["client"],
                            latest_measurement=m["latest_measurement"],
                            latest_traceroute=m["latest_traceroute"],
                            latest_alert_event=m["latest_alert_event"],
                            on_click=on_machine_click
                        )
    
    except RepositoryError as e:
        st.error(f"Erro ao conectar ao Cloud: {e}")
    except Exception as e:
        st.error(f"Erro inesperado: {e}")


def render_detail_view(repo: FrontendRepository) -> None:
    """Renderiza a view de detalhes de uma máquina."""
    machine_id = st.session_state.selected_machine_id
    if not machine_id:
        st.session_state.view_mode = "cards"
        st.rerun()
        return
    
    try:
        machine = repo.get_machine(machine_id)
        if not machine:
            st.error("Máquina não encontrada.")
            if st.button("← Voltar"):
                st.session_state.view_mode = "cards"
                st.session_state.selected_machine_id = None
                st.rerun()
            return
        
        client = repo.get_client(machine.client_id)
        
        # Header com botão voltar
        col1, col2 = st.columns([6, 1])
        with col1:
            st.markdown(f'<h1 class="main-header">📈 {machine.tag}</h1>', unsafe_allow_html=True)
            st.markdown(f'<p class="sub-header">Cliente: {client.name if client else "Desconhecido"} • IP: {machine.ip} • Frequência: {machine.frequency_seconds}s</p>', unsafe_allow_html=True)
        with col2:
            if st.button("← Voltar", use_container_width=True):
                st.session_state.view_mode = "cards"
                st.session_state.selected_machine_id = None
                st.rerun()
        
        # Última medição (cards de status)
        latest = repo.get_latest_measurement(machine_id)
        
        if latest:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                latency_ms = latest.get("latency_ms")
                latency_color = "#28a745" if latency_ms and latency_ms < 50 else "#ffc107" if latency_ms and latency_ms < 150 else "#dc3545" if latency_ms else "#6c757d"
                st.markdown(f"""
                <div class="metric-card">
                    <div style="font-size: 0.8rem; color: #666; text-transform: uppercase;">Latência Atual</div>
                    <div style="font-size: 2rem; font-weight: 700; color: {latency_color};">
                        {f'{latency_ms:.1f} ms' if latency_ms else '—'}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            with col2:
                loss_pct = latest.get("packet_loss_percent", 0)
                loss_color = "#28a745" if loss_pct == 0 else "#ffc107" if loss_pct < 5 else "#dc3545"
                st.markdown(f"""
                <div class="metric-card">
                    <div style="font-size: 0.8rem; color: #666; text-transform: uppercase;">Perda de Pacotes</div>
                    <div style="font-size: 2rem; font-weight: 700; color: {loss_color};">
                        {loss_pct:.1f}%
                    </div>
                </div>
                """, unsafe_allow_html=True)
            with col3:
                jitter_ms = latest.get("jitter_ms")
                jitter_color = "#28a745" if jitter_ms and jitter_ms < 10 else "#ffc107" if jitter_ms and jitter_ms < 30 else "#dc3545" if jitter_ms else "#6c757d"
                st.markdown(f"""
                <div class="metric-card">
                    <div style="font-size: 0.8rem; color: #666; text-transform: uppercase;">Jitter</div>
                    <div style="font-size: 2rem; font-weight: 700; color: {jitter_color};">
                        {f'{jitter_ms:.1f} ms' if jitter_ms else '—'}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            with col4:
                status_html = render_status_badge(latest.get("status", ""))
                st.markdown(f"""
                <div class="metric-card">
                    <div style="font-size: 0.8rem; color: #666; text-transform: uppercase;">Status</div>
                    <div style="font-size: 1.5rem;">{status_html}</div>
                </div>
                """, unsafe_allow_html=True)
            
            st.caption(f"Última medição: {pd.to_datetime(latest.get('measured_at', '')).tz_convert('America/Sao_Paulo').strftime('%Y-%m-%d %H:%M:%S') if latest.get('measured_at') else '—'}")
        else:
            st.warning("Nenhuma medição registrada para esta máquina.")
        
        st.divider()
        
        # Abas: Métricas | Traceroute | Alertas
        tab_metrics, tab_traceroute, tab_alerts = st.tabs(["📊 Métricas", "🔍 Traceroute", "🔔 Alertas"])
        
        with tab_metrics:
            # Seletor de período histórico
            st.subheader("📊 Histórico de Métricas")
            
            # Presets de período
            period_presets = {
                "Últimas 24h": 24,
                "Últimos 7 dias": 168,
                "Últimos 30 dias": 720,
                "Últimos 90 dias": 2160,
                "Últimos 6 meses": 4320,
            }
            
            col_preset, col_custom = st.columns([2, 2])
            
            with col_preset:
                preset = st.selectbox(
                    "Período rápido",
                    options=list(period_presets.keys()),
                    index=1,  # 7 dias padrão
                    key=f"preset_{machine_id}"
                )
                hours = period_presets[preset]
            
            with col_custom:
                # Date picker para período customizado
                from datetime import datetime, timedelta
                default_start = datetime.now() - timedelta(hours=hours)
                date_range = st.date_input(
                    "Período personalizado",
                    value=(default_start.date(), datetime.now().date()),
                    max_value=datetime.now().date(),
                    key=f"date_range_{machine_id}"
                )
                
                # Se selecionou data customizada, usa ela
                if isinstance(date_range, tuple) and len(date_range) == 2:
                    start_date, end_date = date_range
                    start_dt = datetime.combine(start_date, datetime.min.time())
                    end_dt = datetime.combine(end_date, datetime.max.time())
                    # Converte para horas
                    delta = end_dt - start_dt
                    hours = max(1, int(delta.total_seconds() / 3600))
            
            # Busca medições
            measurements = repo.get_measurements(machine_id, hours=hours, limit=settings.MAX_MEASUREMENTS)
            render_metrics_charts(measurements, machine.tag)
            
            # Tabela de medições recentes
            with st.expander("📋 Ver medições recentes (tabela)"):
                if measurements:
                    df_data = []
                    for m in reversed(measurements[-50:]):
                        dt = pd.to_datetime(m.get("measured_at", ""))
                        hora_sp = dt.tz_convert("America/Sao_Paulo").strftime("%Y-%m-%d %H:%M:%S") if dt.tz is not None else m.get("measured_at", "")[:19].replace('T', ' ')
                        df_data.append({
                            "Hora (SP)": hora_sp,
                            "Latência (ms)": f"{m.get('latency_ms'):.1f}" if m.get('latency_ms') else "—",
                            "Jitter (ms)": f"{m.get('jitter_ms'):.1f}" if m.get('jitter_ms') else "—",
                            "Perda (%)": f"{m.get('packet_loss_percent', 0):.1f}",
                            "Status": m.get("status", ""),
                            "Enviados/Recebidos": f"{m.get('packets_received', 0)}/{m.get('packets_sent', 0)}",
                        })
                    st.dataframe(df_data, width="stretch", hide_index=True)
                else:
                    st.info("Nenhuma medição no período.")
        
        with tab_traceroute:
            traceroute_exists = repo.get_latest_traceroute(machine_id) is not None
            if not traceroute_exists:
                st.info(f"ℹ️ Traceroute para {machine.tag} ({machine.ip}). Será executado automaticamente quando a qualidade da conexão mudar de OK.")
                if st.button("🔍 Executar Traceroute Agora", use_container_width=True):
                    if run_traceroute_cli(machine_id):
                        st.rerun()
            else:
                render_traceroute_tab(repo, machine_id, machine.tag)
        
        with tab_alerts:
            render_alert_tab(repo, machine_id, machine.tag)
    
    except RepositoryError as e:
        st.error(f"Erro ao conectar ao Cloud: {e}")
    except Exception as e:
        st.error(f"Erro inesperado: {e}")


def main() -> None:
    init_session_state()
    repo = get_repository()
    
    # Health check silencioso na inicialização
    if "health_checked" not in st.session_state:
        ok, msg = repo.health_check()
        st.session_state.health_checked = True
        st.session_state.health_ok = ok
        st.session_state.health_msg = msg
    
    # Sidebar
    filters = render_sidebar_filters(repo)
    
    # Sidebar content
    with st.sidebar:
        # Cloud status
        if st.session_state.get("health_ok"):
            st.success("☁️ Cloud Online")
        else:
            st.error("❌ Cloud Offline")
        
        # Alertas ativos no sidebar
        st.divider()
        st.markdown("### 🔔 Alertas Ativos")
        
        try:
            active_alerts = repo.list_alert_rules()
            if active_alerts:
                for rule in active_alerts[:5]:
                    machine_tag = rule.get("machine_tag", "")
                    machine_id = rule.get("machine_id", "")
                    if machine_id:
                        machine = repo.get_machine(machine_id)
                        machine_tag = machine.tag if machine else machine_id[:8]
                    
                    event = repo.get_active_alert_event(rule.get("id", ""))
                    if event:
                        severity = event.get("severity", "warning")
                        metric = event.get("metric", "")
                        value = event.get("metric_value", 0)
                        
                        if severity == "critical" or event.get("status") == "firing":
                            icon = "🔴"
                        elif severity == "warning":
                            icon = "🟡"
                        else:
                            icon = "🟠"
                        
                        st.markdown(f"{icon} **{machine_tag}** ({metric}: {value})")
            else:
                st.markdown("<span style='color: #28a745; font-size: 0.85rem;'>✓ Nenhum alerta ativo</span>", unsafe_allow_html=True)
        except Exception:
            st.caption("Nenhum dado de alerta disponível")
        
        # Últimos eventos no sidebar
        st.divider()
        st.markdown("### 📋 Últimos Eventos")
        try:
            events = get_sidebar_events(repo, 30)
            for event in reversed(events):
                timestamp = format_event_time(event.get("timestamp", ""))
                message = event.get("message", "")[:80]
                color = "#888"
                severity = event.get("severity", "ok")
                if severity == "critical":
                    color = "#dc3545"
                elif severity == "warning":
                    color = "#ffc107"
                elif severity == "ok":
                    color = "#28a745"
                st.markdown(f'<span style="color:{color};font-size:0.75rem;">{timestamp} | {message}</span>', unsafe_allow_html=True)
        except Exception:
            st.caption("Nenhum evento disponível")
    
    # Auto-refresh (sempre ativo, a cada 30 segundos)
    st_autorefresh(interval=30_000, key="auto_refresh")
    
    # Roteamento de views
    if st.session_state.view_mode == "detail":
        render_detail_view(repo)
    else:
        render_cards_view(repo, filters["client_id"])


if __name__ == "__main__":
    main()
