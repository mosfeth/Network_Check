# SupaDiag - Dashboard Streamlit

import streamlit as st
import asyncio
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

# Adiciona o src ao path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from supadiag.config import load_settings, ensure_runtime_files
from supadiag.diary import Diary
from supadiag.supabase_repository import SupabaseRepository
from supadiag.queue import LocalQueue
from supadiag.models import Client, Machine, validate_ip, validate_tag, validate_client_name, validate_frequency
from supadiag.monitor import MonitorService, MonitorEvent


# Configuração da página
st.set_page_config(
    page_title="SupaDiag - Monitoramento de Rede",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS customizado
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 1rem;
    }
    .status-ok { color: green; font-weight: bold; }
    .status-error { color: red; font-weight: bold; }
    .status-warning { color: orange; font-weight: bold; }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .stButton > button {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def init_app():
    """Inicializa configurações e repositórios (cached)."""
    settings = load_settings()
    ensure_runtime_files(settings)
    diary = Diary(settings.memory_file)
    repo = SupabaseRepository(settings)
    queue = LocalQueue(settings.queue_file)
    return settings, diary, repo, queue


def render_sidebar():
    """Renderiza a sidebar com navegação e status."""
    settings, diary, repo, queue = init_app()
    
    with st.sidebar:
        st.markdown("## 📊 SupaDiag")
        
        # Status do Supabase
        with st.spinner("Verificando Supabase..."):
            ok, msg = repo.health_check()
        
        if ok:
            st.success(f"✅ Supabase: {msg}")
        else:
            st.error(f"❌ Supabase: {msg}")
        
        st.divider()
        
        # Menu de navegação
        page = st.radio(
            "Navegação",
            ["📋 Clientes", "🖥️ Máquinas", "📈 Monitoramento", "📝 Diário", "⚙️ Serviço"],
            key="nav_page"
        )
        
        st.divider()
        
        # Info do sistema
        st.caption(f"Fila local: {queue.size()} itens")
        st.caption(f"Pasta de dados: {settings.data_dir}")
        
        if st.button("🔄 Atualizar Dados", width="stretch"):
            st.rerun()
        
        return page, settings, diary, repo, queue


def render_clientes_page(repo, diary):
    """Página de gerenciamento de clientes."""
    st.markdown('<h1 class="main-header">📋 Gerenciamento de Clientes</h1>', unsafe_allow_html=True)
    
    tab_list, tab_add = st.tabs(["📋 Lista", "➕ Novo"])
    
    with tab_list:
        try:
            clients = repo.list_clients()
            if clients:
                # Prepara dados para DataFrame
                df_data = [{
                    "ID": c.id,
                    "Nome": c.name,
                    "Criado em": c.created_at
                } for c in clients]
                
                st.dataframe(df_data, width="stretch", hide_index=True)
                
                # Seleção para editar/excluir
                selected = st.selectbox(
                    "Selecionar cliente para ações:",
                    options=[f"{c.name} ({c.id[:8]}...)" for c in clients],
                    index=None,
                    placeholder="Escolha um cliente..."
                )
                
                if selected:
                    client_id = clients[[f"{c.name} ({c.id[:8]}...)" for c in clients].index(selected)].id
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if st.button("✏️ Editar", type="primary", width="stretch"):
                            st.session_state.edit_client_id = client_id
                            st.session_state.edit_client_name = next(c.name for c in clients if c.id == client_id)
                            st.rerun()
                    
                    with col2:
                        if st.button("🗑️ Excluir", type="secondary", width="stretch"):
                            if st.session_state.get("confirm_delete") == client_id:
                                repo.delete_client(client_id)
                                diary.log("CLIENTE_REMOVIDO", "Cliente removido", {"client_id": client_id})
                                st.success("✅ Cliente excluído!")
                                st.session_state.confirm_delete = None
                                st.rerun()
                            else:
                                st.session_state.confirm_delete = client_id
                                st.warning("⚠️ Clique novamente para confirmar exclusão")
            else:
                st.info("Nenhum cliente cadastrado.")
        except Exception as e:
            st.error(f"Erro ao carregar clientes: {e}")
    
    with tab_add:
        st.subheader("➕ Adicionar Novo Cliente")
        with st.form("add_client_form"):
            name = st.text_input("Nome do Cliente *", placeholder="Ex: Empresa ABC Ltda")
            submitted = st.form_submit_button("💾 Salvar", type="primary", width="stretch")
            
            if submitted:
                if not name.strip():
                    st.error("Nome é obrigatório")
                else:
                    try:
                        client = repo.create_client(name.strip())
                        diary.log("CLIENTE_CRIADO", client.name, {"client_id": client.id})
                        st.success(f"✅ Cliente '{client.name}' salvo! (ID: {client.id[:8]}...)")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Erro ao salvar: {e}")
    
    # Form de edição (aparece quando selecionado)
    if "edit_client_id" in st.session_state:
        st.divider()
        st.subheader("✏️ Editando Cliente")
        with st.form("edit_client_form"):
            new_name = st.text_input("Novo Nome", value=st.session_state.edit_client_name)
            col1, col2 = st.columns(2)
            with col1:
                if st.form_submit_button("💾 Salvar Alterações", type="primary", width="stretch"):
                    try:
                        updated = repo.update_client(st.session_state.edit_client_id, new_name.strip())
                        diary.log("CLIENTE_ATUALIZADO", updated.name, {"client_id": updated.id})
                        st.success(f"✅ Cliente atualizado!")
                        del st.session_state.edit_client_id
                        del st.session_state.edit_client_name
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Erro: {e}")
            with col2:
                if st.form_submit_button("❌ Cancelar", width="stretch"):
                    del st.session_state.edit_client_id
                    del st.session_state.edit_client_name
                    st.rerun()


def render_maquinas_page(repo, diary):
    """Página de gerenciamento de máquinas."""
    st.markdown('<h1 class="main-header">🖥️ Gerenciamento de Máquinas</h1>', unsafe_allow_html=True)
    
    # Carrega clientes para dropdown
    try:
        clients = repo.list_clients()
        client_options = {f"{c.name} ({c.id[:8]}...)": c.id for c in clients}
    except:
        client_options = {}
    
    tab_list, tab_add = st.tabs(["📋 Lista", "➕ Nova"])
    
    with tab_list:
        try:
            machines = repo.list_machines()
            if machines:
                # Filtros
                col1, col2 = st.columns(2)
                with col1:
                    filter_client = st.selectbox(
                        "Filtrar por cliente:",
                        ["Todos"] + list(client_options.keys()),
                        index=0
                    )
                with col2:
                    filter_active = st.selectbox("Status:", ["Todos", "Ativas", "Inativas"], index=0)
                
                # Aplica filtros
                filtered = machines
                if filter_client != "Todos":
                    filtered = [m for m in filtered if m.client_id == client_options[filter_client]]
                if filter_active == "Ativas":
                    filtered = [m for m in filtered if m.active]
                elif filter_active == "Inativas":
                    filtered = [m for m in filtered if not m.active]
                
                if filtered:
                    df_data = [{
                        "ID": m.id,
                        "Cliente": next((c for c, id_ in client_options.items() if id_ == m.client_id), m.client_id[:8]),
                        "Tag": m.tag,
                        "IP": m.ip,
                        "Freq (s)": m.frequency_seconds,
                        "Status": "🟢 Ativa" if m.active else "🔴 Inativa"
                    } for m in filtered]
                    
                    st.dataframe(df_data, width="stretch", hide_index=True)
                    
                    # Seleção para editar/excluir
                    selected = st.selectbox(
                        "Selecionar máquina:",
                        options=[f"{m.tag} ({m.id[:8]}...)" for m in filtered],
                        index=None,
                        placeholder="Escolha uma máquina..."
                    )
                    
                    if selected:
                        machine_id = filtered[[f"{m.tag} ({m.id[:8]}...)" for m in filtered].index(selected)].id
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("✏️ Editar", type="primary", width="stretch", key="edit_mach"):
                                m = next(m for m in filtered if m.id == machine_id)
                                st.session_state.edit_mach_id = machine_id
                                st.session_state.edit_mach_client = m.client_id
                                st.session_state.edit_mach_tag = m.tag
                                st.session_state.edit_mach_ip = m.ip
                                st.session_state.edit_mach_freq = m.frequency_seconds
                                st.session_state.edit_mach_active = m.active
                                st.rerun()
                        with col2:
                            if st.button("🗑️ Excluir", type="secondary", width="stretch", key="del_mach"):
                                if st.session_state.get("confirm_del_mach") == machine_id:
                                    repo.delete_machine(machine_id)
                                    diary.log("MAQUINA_REMOVIDA", "Máquina removida", {"machine_id": machine_id})
                                    st.success("✅ Máquina excluída!")
                                    st.session_state.confirm_del_mach = None
                                    st.rerun()
                                else:
                                    st.session_state.confirm_del_mach = machine_id
                                    st.warning("⚠️ Clique novamente para confirmar")
                else:
                    st.info("Nenhuma máquina encontrada com os filtros atuais.")
            else:
                st.info("Nenhuma máquina cadastrada.")
        except Exception as e:
            st.error(f"Erro ao carregar máquinas: {e}")
    
    with tab_add:
        st.subheader("➕ Adicionar Nova Máquina")
        if not client_options:
            st.warning("⚠️ Cadastre um cliente primeiro na aba Clientes.")
        else:
            with st.form("add_machine_form"):
                client_sel = st.selectbox("Cliente *", options=list(client_options.keys()))
                tag = st.text_input("Tag *", placeholder="Ex: servidor-web-01")
                ip = st.text_input("IP *", placeholder="Ex: 10.0.1.50")
                freq = st.number_input("Frequência (segundos) *", min_value=10, value=60, step=10)
                active = st.checkbox("Ativa", value=True)
                
                submitted = st.form_submit_button("💾 Salvar", type="primary", width="stretch")
                
                if submitted:
                    if not all([client_sel, tag.strip(), ip.strip()]):
                        st.error("Todos os campos marcados com * são obrigatórios")
                    else:
                        try:
                            client_id = client_options[client_sel]
                            machine = repo.create_machine(client_id, tag.strip(), ip.strip(), int(freq))
                            diary.log("MAQUINA_CRIADA", machine.tag, {"machine_id": machine.id})
                            st.success(f"✅ Máquina '{machine.tag}' salva! (ID: {machine.id[:8]}...)")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Erro: {e}")
    
    # Form de edição de máquina
    if "edit_mach_id" in st.session_state:
        st.divider()
        st.subheader("✏️ Editando Máquina")
        m = repo.get_machine(st.session_state.edit_mach_id)
        if m:
            with st.form("edit_machine_form"):
                client_sel = st.selectbox("Cliente", options=list(client_options.keys()), 
                                        index=list(client_options.values()).index(m.client_id) if m.client_id in client_options.values() else 0)
                tag = st.text_input("Tag", value=st.session_state.edit_mach_tag)
                ip = st.text_input("IP", value=st.session_state.edit_mach_ip)
                freq = st.number_input("Frequência (s)", min_value=10, value=st.session_state.edit_mach_freq, step=10)
                active = st.checkbox("Ativa", value=st.session_state.edit_mach_active)
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button("💾 Salvar", type="primary", width="stretch"):
                        try:
                            client_id = client_options[client_sel]
                            updated = repo.update_machine(
                                st.session_state.edit_mach_id,
                                tag=tag.strip(),
                                ip=ip.strip(),
                                frequency_seconds=int(freq),
                                active=active
                            )
                            diary.log("MAQUINA_ATUALIZADA", updated.tag, {"machine_id": updated.id})
                            st.success("✅ Máquina atualizada!")
                            for k in ["edit_mach_id", "edit_mach_client", "edit_mach_tag", "edit_mach_ip", "edit_mach_freq", "edit_mach_active"]:
                                del st.session_state[k]
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Erro: {e}")
                with col2:
                    if st.form_submit_button("❌ Cancelar", width="stretch"):
                        for k in ["edit_mach_id", "edit_mach_client", "edit_mach_tag", "edit_mach_ip", "edit_mach_freq", "edit_mach_active"]:
                            if k in st.session_state:
                                del st.session_state[k]
                        st.rerun()


def render_monitoramento_page(repo, diary, queue, settings):
    """Página de monitoramento em tempo real."""
    st.markdown('<h1 class="main-header">📈 Monitoramento em Tempo Real</h1>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Fila Local", queue.size())
    with col2:
        st.metric("Itens Dead Letter", queue.dead_letter_size())
    with col3:
        st.metric("Retenção", f"{settings.retention_days} dias")
    
    st.divider()
    
    # Últimas medições
    st.subheader("📊 Últimas Medições")
    try:
        data = repo.latest_measurements(100)
        if data:
            df_data = []
            for row in data:
                machine_info = row.get("machines", {})
                # Handle both object and array from Supabase join
                if isinstance(machine_info, list):
                    machine_info = machine_info[0] if machine_info else {}
                df_data.append({
                    "Hora": row.get("measured_at", "")[:19],
                    "Máquina": machine_info.get("tag", row.get("machine_id", "")[:8]),
                    "IP": machine_info.get("ip", ""),
                    "Latência (ms)": row.get("latency_ms"),
                    "Jitter (ms)": row.get("jitter_ms"),
                    "Perda (%)": row.get("packet_loss_percent"),
                    "Status": row.get("status", "")
                })
            if df_data:
                st.dataframe(df_data, width="stretch", hide_index=True)
            else:
                st.info("Nenhuma medição encontrada.")
        else:
            st.info("Nenhuma medição encontrada.")
    except Exception as e:
        st.error(f"Erro ao carregar medições: {e}")
    
    st.divider()
    
    # Controles do monitor
    st.subheader("🎮 Controles do Monitor")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("▶️ Iniciar Monitor", type="primary", width="stretch"):
            st.info("Use `supadiag monitor` no terminal para iniciar o monitor em background")
    with col2:
        if st.button("🔄 Limpeza Manual (6 meses)", width="stretch"):
            try:
                cutoff = (datetime.now().astimezone() - timedelta(days=settings.retention_days)).isoformat()
                deleted = repo.cleanup_old_measurements(cutoff)
                st.success(f"✅ Limpeza realizada: {deleted} registros removidos")
            except Exception as e:
                st.error(f"Erro: {e}")
    with col3:
        if st.button("🧹 Limpar Fila Local", width="stretch"):
            # Não implementado - apenas demonstração
            st.info("Funcionalidade de limpar fila local não implementada na UI")
    
    # Auto-refresh
    if st.checkbox("🔄 Auto-atualizar (10s)", value=False):
        time.sleep(10)
        st.rerun()


def render_diario_page(diary, settings):
    """Página do diário (memory.txt)."""
    st.markdown('<h1 class="main-header">📝 Diário do Projeto</h1>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([3, 1])
    with col1:
        lines = st.slider("Linhas a exibir:", 10, 200, 50)
    with col2:
        if st.button("🔄 Atualizar", type="primary"):
            st.rerun()
    
    try:
        content = settings.memory_file.read_text(encoding="utf-8").strip().splitlines()
        if content:
            # Mostra últimas N linhas
            recent = content[-lines:] if lines < len(content) else content
            for line in reversed(recent):  # Mais recentes primeiro
                parts = line.split(" | ", 2)
                if len(parts) == 3:
                    timestamp, event, msg = parts
                    # Colorir por tipo de evento
                    if "ERRO" in event or "FALHA" in event:
                        st.error(f"`{timestamp}` **{event}**: {msg}")
                    elif "RESOLUCAO" in event or "OK" in event:
                        st.success(f"`{timestamp}` **{event}**: {msg}")
                    elif "AVISO" in event:
                        st.warning(f"`{timestamp}` **{event}**: {msg}")
                    else:
                        st.info(f"`{timestamp}` **{event}**: {msg}")
                else:
                    st.text(line)
        else:
            st.info("Diário vazio.")
    except Exception as e:
        st.error(f"Erro ao ler diário: {e}")


def render_servico_page(settings):
    """Página de gerenciamento do serviço."""
    st.markdown('<h1 class="main-header">⚙️ Gerenciamento do Serviço</h1>', unsafe_allow_html=True)
    
    st.info("O serviço roda via **Agendador de Tarefas do Windows** (executa no logon do usuário).")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🔧 Instalar Serviço", type="primary", width="stretch"):
            st.code("supadiag service install")
            st.info("Execute no terminal: `supadiag service install`")
    with col2:
        if st.button("📋 Status", width="stretch"):
            st.code("supadiag service status")
            st.info("Execute no terminal: `supadiag service status`")
    with col3:
        if st.button("🗑️ Remover", type="secondary", width="stretch"):
            st.code("supadiag service remove")
            st.info("Execute no terminal: `supadiag service remove`")
    
    st.divider()
    st.subheader("Como funciona")
    st.markdown("""
    - O serviço é instalado no **Agendador de Tarefas do Windows**
    - Executa automaticamente no **logon do usuário**
    - Roda `supadiag monitor` em background
    - Coleta métricas a cada frequência configurada por máquina
    - Envia para Supabase; falhas vão para fila local com retry
    """)


def main():
    # Título principal
    st.markdown('<h1 class="main-header">📊 SupaDiag - Monitoramento de Rede</h1>', unsafe_allow_html=True)
    
    # Inicializa
    page, settings, diary, repo, queue = render_sidebar()
    
    # Roteamento de páginas
    if page == "📋 Clientes":
        render_clientes_page(repo, diary)
    elif page == "🖥️ Máquinas":
        render_maquinas_page(repo, diary)
    elif page == "📈 Monitoramento":
        render_monitoramento_page(repo, diary, queue, settings)
    elif page == "📝 Diário":
        render_diario_page(diary, settings)
    elif page == "⚙️ Serviço":
        render_servico_page(settings)


if __name__ == "__main__":
    main()