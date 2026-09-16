# FrontEnd/components.py
# Componentes de UI reutilizáveis para o dashboard Streamlit

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
from typing import Optional

from repository import Machine, Measurement, Client

# Import settings for sidebar caption
from config import settings


def render_machine_card(
    machine: Machine,
    client: Client,
    latest_measurement: Optional[dict],
    latest_traceroute: Optional[dict],
    on_click: callable
) -> None:
    """
    Renderiza um card de máquina com informações resumidas.
    
    Args:
        machine: Objeto Machine
        client: Objeto Client
        latest_measurement: Última medição (dict) ou None
        latest_traceroute: Último traceroute (dict) ou None
        on_click: Callback ao clicar no card
    """
    # Determina cor do status
    if latest_measurement:
        status = latest_measurement.get("status", "")
        latency = latest_measurement.get("latency_ms")
        loss = latest_measurement.get("packet_loss_percent")
        
        if status == "ok":
            status_color = "#28a745"  # verde
            status_icon = "🟢"
            status_text = "OK"
        elif status == "partial":
            status_color = "#ffc107"  # amarelo
            status_icon = "🟡"
            status_text = "PARCIAL"
        elif status == "unreachable":
            status_color = "#dc3545"  # vermelho
            status_icon = "🔴"
            status_text = "INALCANÇÁVEL"
        else:
            status_color = "#6c757d"  # cinza
            status_icon = "⚪"
            status_text = "ERRO"
    else:
        status_color = "#6c757d"
        status_icon = "⚪"
        status_text = "SEM DADOS"
        latency = None
        loss = None
    
    # Traceroute badge
    traceroute_badge = render_traceroute_badge(latest_traceroute)
    
    # Card HTML customizado (sem texto "Clique para ver...")
    card_html = f"""
    <div style="
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 16px;
        margin: 8px 0;
        background: white;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        transition: box-shadow 0.2s, transform 0.2s;
        cursor: pointer;
    " onmouseover="this.style.boxShadow='0 4px 12px rgba(0,0,0,0.1)'; this.style.transform='translateY(-2px)'"
       onmouseout="this.style.boxShadow='0 2px 4px rgba(0,0,0,0.05)'; this.style.transform='translateY(0)'">
        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
            <div>
                <h4 style="margin: 0 0 4px 0; color: #1f77b4; font-size: 1.1rem;">
                    {machine.tag}
                </h4>
                <p style="margin: 0; color: #666; font-size: 0.9rem;">
                    {client.name if client else f"Cliente: {machine.client_id[:8]}..."}
                </p>
                <p style="margin: 4px 0 0 0; color: #888; font-size: 0.8rem; font-family: monospace;">
                    {machine.ip} • {machine.frequency_seconds}s
                </p>
            </div>
            <div style="text-align: right;">
                <span style="
                    background: {status_color};
                    color: white;
                    padding: 4px 10px;
                    border-radius: 12px;
                    font-size: 0.75rem;
                    font-weight: 600;
                    display: inline-block;
                ">
                    {status_icon} {status_text}
                </span>
            </div>
        </div>
        <div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid #f0f0f0; display: flex; gap: 16px;">
            <div style="flex: 1; text-align: center;">
                <div style="font-size: 1.3rem; font-weight: 600; color: {'#28a745' if latency and latency < 50 else '#ffc107' if latency and latency < 150 else '#dc3545' if latency else '#6c757d'};">
                    {f'{latency:.1f} ms' if latency is not None else '—'}
                </div>
                <div style="font-size: 0.7rem; color: #888; text-transform: uppercase;">Latência</div>
            </div>
            <div style="flex: 1; text-align: center;">
                <div style="font-size: 1.3rem; font-weight: 600; color: {'#28a745' if loss is not None and loss == 0 else '#ffc107' if loss is not None and loss < 5 else '#dc3545' if loss is not None else '#6c757d'};">
                    {f'{loss:.1f}%' if loss is not None else '—'}
                </div>
                <div style="font-size: 0.7rem; color: #888; text-transform: uppercase;">Perda</div>
            </div>
            <div style="flex: 1; text-align: center;">
                <div style="font-size: 1.3rem; font-weight: 600; color: #1f77b4;">
                    {latest_measurement.get("measured_at", "")[:16].replace('T', ' ') if latest_measurement else '—'}
                </div>
                <div style="font-size: 0.7rem; color: #888; text-transform: uppercase;">Última</div>
            </div>
        </div>
        <div style="margin-top: 8px; text-align: center;">
            {traceroute_badge}
        </div>
    </div>
    """
    
    # Renderiza card + botão com label da máquina (clicável)
    container = st.container()
    with container:
        st.markdown(card_html, unsafe_allow_html=True)
        # Botão com label da máquina - clica no botão = clica no card
        if st.button(f"▶ Ver detalhes: {machine.tag}", key=f"card_{machine.id}", use_container_width=True):
            on_click(machine.id)


def render_metrics_charts(measurements: list[dict], machine_tag: str) -> None:
    """
    Renderiza gráficos de métricas (latência, jitter, perda) usando Plotly.
    
    Args:
        measurements: Lista de medições (dict) ordenadas cronologicamente
        machine_tag: Tag da máquina para título
    """
    if not measurements:
        st.info("Nenhuma medição disponível para o período selecionado.")
        return
    
    # Prepara dados para DataFrame com conversão para horário de São Paulo
    df = pd.DataFrame([
        {
            "timestamp": pd.to_datetime(m.get("measured_at", "")).tz_convert("America/Sao_Paulo") if pd.to_datetime(m.get("measured_at", "")).tz is not None else pd.to_datetime(m.get("measured_at", "")),
            "latency_ms": m.get("latency_ms"),
            "jitter_ms": m.get("jitter_ms"),
            "packet_loss_percent": m.get("packet_loss_percent", 0),
            "status": m.get("status", ""),
        }
        for m in measurements
    ])
    
    # Cria subplots: latência + jitter (mesmo eixo Y) e perda (eixo separado)
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.1,
        subplot_titles=("Latência e Jitter (ms)", "Perda de Pacotes (%)"),
        row_heights=[0.65, 0.35]
    )
    
    # Latência
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["latency_ms"],
            mode="lines+markers",
            name="Latência (ms)",
            line=dict(color="#1f77b4", width=2),
            marker=dict(size=4),
            connectgaps=False,  # Não conecta pontos com latência None
        ),
        row=1, col=1
    )
    
    # Jitter
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["jitter_ms"],
            mode="lines+markers",
            name="Jitter (ms)",
            line=dict(color="#ff7f0e", width=1.5, dash="dot"),
            marker=dict(size=3),
            connectgaps=False,
        ),
        row=1, col=1
    )
    
    # Perda de pacotes (barras)
    colors = ["#28a745" if v == 0 else "#ffc107" if v < 5 else "#dc3545" for v in df["packet_loss_percent"]]
    fig.add_trace(
        go.Bar(
            x=df["timestamp"],
            y=df["packet_loss_percent"],
            name="Perda (%)",
            marker_color=colors,
            opacity=0.7,
        ),
        row=2, col=1
    )
    
    # Linha de referência para perda
    fig.add_hline(y=1, line_dash="dash", line_color="#ffc107", row=2, col=1, annotation_text="1%")
    fig.add_hline(y=5, line_dash="dash", line_color="#dc3545", row=2, col=1, annotation_text="5%")
    
    # Layout
    fig.update_layout(
        height=500,
        title=f"Métricas de Rede - {machine_tag}",
        title_x=0.5,
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        margin=dict(l=50, r=30, t=60, b=40),
    )
    
    fig.update_xaxes(title_text="Tempo", row=2, col=1)
    fig.update_yaxes(title_text="ms", row=1, col=1)
    fig.update_yaxes(title_text="%", row=2, col=1, range=[0, max(10, df["packet_loss_percent"].max() * 1.2 if not df["packet_loss_percent"].isna().all() else 10)])
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Estatísticas resumidas
    col1, col2, col3, col4 = st.columns(4)
    
    valid_latency = df["latency_ms"].dropna()
    valid_jitter = df["jitter_ms"].dropna()
    
    with col1:
        st.metric(
            "Latência Média",
            f"{valid_latency.mean():.1f} ms" if not valid_latency.empty else "—",
            delta=f"Min: {valid_latency.min():.1f} / Max: {valid_latency.max():.1f}" if not valid_latency.empty else None
        )
    with col2:
        st.metric(
            "Jitter Médio",
            f"{valid_jitter.mean():.1f} ms" if not valid_jitter.empty else "—",
            delta=f"Max: {valid_jitter.max():.1f}" if not valid_jitter.empty else None
        )
    with col3:
        avg_loss = df["packet_loss_percent"].mean()
        st.metric(
            "Perda Média",
            f"{avg_loss:.2f}%",
            delta=f"Total: {df['packet_loss_percent'].sum():.1f}%"
        )
    with col4:
        uptime = (df["status"] == "ok").sum() / len(df) * 100
        st.metric(
            "Disponibilidade",
            f"{uptime:.1f}%",
            delta=f"{(df['status'] == 'ok').sum()}/{len(df)} amostras"
        )


def render_status_badge(status: str) -> str:
    """Retorna HTML para badge de status."""
    badges = {
        "ok": ("🟢 OK", "#28a745"),
        "partial": ("🟡 PARCIAL", "#ffc107"),
        "unreachable": ("🔴 INALCANÇÁVEL", "#dc3545"),
        "error": ("⚪ ERRO", "#6c757d"),
    }
    text, color = badges.get(status, ("❓ DESCONHECIDO", "#6c757d"))
    return f'<span style="background:{color};color:white;padding:2px 8px;border-radius:10px;font-size:0.75rem;font-weight:600;">{text}</span>'


def render_sidebar_filters(repo) -> dict:
    """
    Renderiza filtros na sidebar e retorna parâmetros selecionados.
    
    Returns:
        Dict com: client_id, auto_refresh
    """
    with st.sidebar:
        st.markdown("## ⚙️ Filtros")
        
        # Filtro por cliente
        clients = repo.list_clients()
        client_options = {"Todos": None}
        client_options.update({c.name: c.id for c in clients})
        
        selected_client_name = st.selectbox(
            "Filtrar por cliente",
            options=list(client_options.keys()),
            index=0
        )
        selected_client_id = client_options[selected_client_name]
        
        st.divider()
        
        # Auto-refresh
        auto_refresh = st.checkbox("🔄 Auto-atualizar (30s)", value=False)
        
        if st.button("🔄 Atualizar Agora", use_container_width=True):
            st.rerun()
        
        st.divider()
        st.caption(f"SupaDiag FrontEnd v1.0")
        st.caption(f"Fonte: Supabase ({settings.SUPABASE_URL[:30]}...)")
    
    return {
        "client_id": selected_client_id,
        "auto_refresh": auto_refresh,
    }


def render_traceroute_chart(traceroute: dict, machine_tag: str) -> None:
    """
    Renderiza gráfico estilo PingPlotter: hop-a-hop latency/loss.
    
    Args:
        traceroute: Dicionário com traceroute e hops do Supabase
        machine_tag: Tag da máquina para título
    """
    hops = traceroute.get("traceroute_hops", [])
    if not hops:
        st.info("Nenhum hop de traceroute disponível.")
        return
    
    # Ordena hops por número
    hops = sorted(hops, key=lambda h: h["hop_number"])
    
    # Prepara dados
    hop_nums = [h["hop_number"] for h in hops]
    ips = [h.get("ip") or "*" for h in hops]
    hostnames = [h.get("hostname") or "" for h in hops]
    latencies = [h.get("latency_ms") for h in hops]
    losses = [h.get("packet_loss_percent", 0) for h in hops]
    
    # Labels para eixo X
    labels = []
    for i, (ip, host) in enumerate(zip(ips, hostnames)):
        label = f"Hop {hop_nums[i]}\n{ip}"
        if host:
            label += f"\n({host})"
        labels.append(label)
    
    # Cria figura com dois eixos Y
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.1,
        subplot_titles=("Latência por Hop (ms)", "Perda por Hop (%)"),
        row_heights=[0.7, 0.3]
    )
    
    # Latência - barras
    lat_colors = []
    for lat in latencies:
        if lat is None:
            lat_colors.append("#6c757d")  # cinza para timeout
        elif lat < 20:
            lat_colors.append("#28a745")  # verde
        elif lat < 50:
            lat_colors.append("#ffc107")  # amarelo
        elif lat < 100:
            lat_colors.append("#fd7e14")  # laranja
        else:
            lat_colors.append("#dc3545")  # vermelho
    
    fig.add_trace(
        go.Bar(
            x=list(range(len(hop_nums))),
            y=[lat if lat is not None else 0 for lat in latencies],
            name="Latência (ms)",
            marker_color=lat_colors,
            text=[f"{lat:.1f}ms" if lat is not None else "timeout" for lat in latencies],
            textposition="outside",
            hovertemplate="Hop %{x}<br>Latência: %{y:.1f}ms<extra></extra>",
        ),
        row=1, col=1
    )
    
    # Perda - barras
    loss_colors = ["#28a745" if l == 0 else "#ffc107" if l < 10 else "#dc3545" for l in losses]
    
    fig.add_trace(
        go.Bar(
            x=list(range(len(hop_nums))),
            y=losses,
            name="Perda (%)",
            marker_color=loss_colors,
            text=[f"{l:.0f}%" for l in losses],
            textposition="outside",
            hovertemplate="Hop %{x}<br>Perda: %{y:.1f}%<extra></extra>",
        ),
        row=2, col=1
    )
    
    # Linhas de referência
    fig.add_hline(y=1, line_dash="dash", line_color="#ffc107", row=2, col=1, annotation_text="1%")
    fig.add_hline(y=5, line_dash="dash", line_color="#dc3545", row=2, col=1, annotation_text="5%")
    
    # Configura eixo X com labels dos hops
    fig.update_xaxes(
        tickmode="array",
        tickvals=list(range(len(hop_nums))),
        ticktext=labels,
        tickangle=-45,
        row=2, col=1
    )
    fig.update_xaxes(showticklabels=False, row=1, col=1)
    
    fig.update_yaxes(title_text="ms", row=1, col=1)
    fig.update_yaxes(title_text="%", row=2, col=1, range=[0, 100])
    
    # Layout
    dest_reached = "✅" if traceroute.get("destination_reached") else "❌"
    fig.update_layout(
        height=550,
        title=f"🔍 Traceroute - {machine_tag} {dest_reached}",
        title_x=0.5,
        hovermode="x unified",
        showlegend=False,
        margin=dict(l=50, r=30, t=60, b=100),
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Tabela de hops
    with st.expander("📋 Detalhes dos Hops"):
        df_hops = pd.DataFrame([
            {
                "Hop": h["hop_number"],
                "IP": h.get("ip") or "*",
                "Hostname": h.get("hostname") or "—",
                "Latência (ms)": f"{h.get('latency_ms'):.1f}" if h.get("latency_ms") else "timeout",
                "Perda (%)": f"{h.get('packet_loss_percent', 0):.1f}",
            }
            for h in sorted(traceroute.get("traceroute_hops", []), key=lambda x: x["hop_number"])
        ])
        st.dataframe(df_hops, width="stretch", hide_index=True)


def render_traceroute_badge(traceroute: dict | None) -> str:
    """Retorna HTML para badge de traceroute no card."""
    if not traceroute:
        return '<span style="background:#6c757d;color:white;padding:2px 8px;border-radius:10px;font-size:0.7rem;font-weight:600;">🔍 Sem traceroute</span>'
    
    total_hops = traceroute.get("total_hops", 0)
    reached = traceroute.get("destination_reached", False)
    
    if reached:
        color = "#28a745"
        text = f"🔍 Traceroute: {total_hops} hops ✅"
    else:
        color = "#ffc107"
        text = f"🔍 Traceroute: {total_hops} hops ⚠️"
    
    return f'<span style="background:{color};color:white;padding:2px 8px;border-radius:10px;font-size:0.7rem;font-weight:600;">{text}</span>'


def render_traceroute_tab(repo, machine_id: str, machine_tag: str) -> None:
    """Renderiza aba de traceroute no detail view."""
    traceroute = repo.get_latest_traceroute(machine_id)
    
    if not traceroute:
        st.warning("Nenhum traceroute disponível para esta máquina.")
        if st.button("🔄 Verificar agora"):
            st.rerun()
        return
    
    # Info do traceroute
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Hops", traceroute.get("total_hops", 0))
    with col2:
        reached = "✅ Sim" if traceroute.get("destination_reached") else "❌ Não"
        st.metric("Destino Alcançado", reached)
    with col3:
        st.metric("Max Hops Config", traceroute.get("max_hops", 30))
    with col4:
        measured = traceroute.get("measured_at", "")[:16].replace("T", " ")
        st.metric("Última Execução", measured)
    
    st.divider()
    
    # Gráfico principal
    render_traceroute_chart(traceroute, traceroute.get("target_ip", "IP"))
    
    # Histórico
    with st.expander("📜 Histórico de Traceroutes"):
        history = repo.get_traceroute_history(machine_id, limit=20)
        if history:
            df_hist = pd.DataFrame([
                {
                    "Data": h["measured_at"][:16].replace("T", " "),
                    "Hops": h.get("total_hops", 0),
                    "Alcançado": "✅" if h.get("destination_reached") else "❌",
                }
                for h in history
            ])
            st.dataframe(df_hist, width="stretch", hide_index=True)
        else:
            st.info("Sem histórico de traceroutes.")