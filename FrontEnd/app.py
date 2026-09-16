# FrontEnd/app.py
# Dashboard Principal - SupaDiag FrontEnd

import streamlit as st
from streamlit_autorefresh import st_autorefresh
from typing import Optional

from config import settings
from repository import FrontendRepository, RepositoryError
from components import (
    render_machine_card,
    render_metrics_charts,
    render_sidebar_filters,
    render_status_badge,
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
        font-size: 2.5rem;
        font-weight: 700;
        color: #1f77b4;
        margin-bottom: 0.5rem;
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


def render_cards_view(repo: FrontendRepository, client_id: Optional[str]) -> None:
    """Renderiza a view de cards (lista de máquinas)."""
    st.markdown('<h1 class="main-header">📊 SupaDiag - Visão Geral</h1>', unsafe_allow_html=True)
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
        
        # Busca traceroute para cada máquina
        for m in machines_data:
            m["latest_traceroute"] = repo.get_latest_traceroute(m["machine"].id)
        
        # Métricas gerais
        total = len(machines_data)
        ok_count = sum(1 for m in machines_data if m["latest_measurement"] and m["latest_measurement"].status == "ok")
        warning_count = sum(1 for m in machines_data if m["latest_measurement"] and m["latest_measurement"].status == "partial")
        critical_count = sum(1 for m in machines_data if m["latest_measurement"] and m["latest_measurement"].status == "unreachable")
        no_data_count = sum(1 for m in machines_data if not m["latest_measurement"])
        
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total", total)
        col2.metric("🟢 OK", ok_count)
        col3.metric("🟡 Parcial", warning_count)
        col4.metric("🔴 Crítico", critical_count)
        col5.metric("⚪ Sem dados", no_data_count)
        
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
                            on_click=on_machine_click
                        )
    
    except RepositoryError as e:
        st.error(f"Erro ao conectar ao Supabase: {e}")
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
                latency_color = "#28a745" if latest.latency_ms and latest.latency_ms < 50 else "#ffc107" if latest.latency_ms and latest.latency_ms < 150 else "#dc3545" if latest.latency_ms else "#6c757d"
                st.markdown(f"""
                <div class="metric-card">
                    <div style="font-size: 0.8rem; color: #666; text-transform: uppercase;">Latência Atual</div>
                    <div style="font-size: 2rem; font-weight: 700; color: {latency_color};">
                        {f'{latest.latency_ms:.1f} ms' if latest.latency_ms else '—'}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            with col2:
                loss_color = "#28a745" if latest.packet_loss_percent == 0 else "#ffc107" if latest.packet_loss_percent < 5 else "#dc3545"
                st.markdown(f"""
                <div class="metric-card">
                    <div style="font-size: 0.8rem; color: #666; text-transform: uppercase;">Perda de Pacotes</div>
                    <div style="font-size: 2rem; font-weight: 700; color: {loss_color};">
                        {latest.packet_loss_percent:.1f}%
                    </div>
                </div>
                """, unsafe_allow_html=True)
            with col3:
                jitter_color = "#28a745" if latest.jitter_ms and latest.jitter_ms < 10 else "#ffc107" if latest.jitter_ms and latest.jitter_ms < 30 else "#dc3545" if latest.jitter_ms else "#6c757d"
                st.markdown(f"""
                <div class="metric-card">
                    <div style="font-size: 0.8rem; color: #666; text-transform: uppercase;">Jitter</div>
                    <div style="font-size: 2rem; font-weight: 700; color: {jitter_color};">
                        {f'{latest.jitter_ms:.1f} ms' if latest.jitter_ms else '—'}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            with col4:
                status_html = render_status_badge(latest.status)
                st.markdown(f"""
                <div class="metric-card">
                    <div style="font-size: 0.8rem; color: #666; text-transform: uppercase;">Status</div>
                    <div style="font-size: 1.5rem;">{status_html}</div>
                </div>
                """, unsafe_allow_html=True)
            
            st.caption(f"Última medição: {latest.measured_at[:19].replace('T', ' ')} UTC")
        else:
            st.warning("Nenhuma medição registrada para esta máquina.")
        
        st.divider()
        
        # Abas: Métricas | Traceroute
        tab_metrics, tab_traceroute = st.tabs(["📊 Métricas", "🔍 Traceroute"])
        
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
                        df_data.append({
                            "Hora": m.measured_at[:19].replace('T', ' '),
                            "Latência (ms)": f"{m.latency_ms:.1f}" if m.latency_ms else "—",
                            "Jitter (ms)": f"{m.jitter_ms:.1f}" if m.jitter_ms else "—",
                            "Perda (%)": f"{m.packet_loss_percent:.1f}",
                            "Status": m.status,
                            "Enviados/Recebidos": f"{m.packets_received}/{m.packets_sent}",
                        })
                    st.dataframe(df_data, width="stretch", hide_index=True)
                else:
                    st.info("Nenhuma medição no período.")
        
        with tab_traceroute:
            render_traceroute_tab(repo, machine_id, machine.tag)
    
    except RepositoryError as e:
        st.error(f"Erro ao conectar ao Supabase: {e}")
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
    
    # Status do Supabase na sidebar
    with st.sidebar:
        if st.session_state.get("health_ok"):
            st.success(f"✅ {st.session_state.health_msg}")
        else:
            st.error(f"❌ {st.session_state.health_msg}")
    
    # Auto-refresh não-bloqueante (a cada 30 segundos)
    if filters["auto_refresh"]:
        st_autorefresh(interval=30_000, key="auto_refresh")
    
    # Roteamento de views
    if st.session_state.view_mode == "detail":
        render_detail_view(repo)
    else:
        render_cards_view(repo, filters["client_id"])


if __name__ == "__main__":
    main()