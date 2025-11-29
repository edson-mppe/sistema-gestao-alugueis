
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

# Importações dos módulos locais
from src.services import sincronizar_dados_completo
from src.gsheets_api import baixar_dados_google_sheet, ler_abas_planilha
from src.logic import tratar_dataframe_consolidado, create_gantt_chart, verificar_disponibilidade
from src.config import APARTMENT_SHEET_MAP
import src.ui as ui

# --- Configuração da Página ---
st.set_page_config(
    page_title="Gestão de Aluguéis",
    page_icon="🏢",
    layout="wide"
)

# --- Inicialização do Session State ---
if 'gantt_fig' not in st.session_state:
    st.session_state.gantt_fig = None
if 'check_result_msg' not in st.session_state:
    st.session_state.check_result_msg = None
if 'check_result_status' not in st.session_state:
    st.session_state.check_result_status = None 

# Inicializa datas se não existirem
if 'checkin_input' not in st.session_state:
    st.session_state.checkin_input = datetime.now().date()
if 'checkout_input' not in st.session_state:
    st.session_state.checkout_input = st.session_state.checkin_input + timedelta(days=1)

# --- CARREGAMENTO DE DADOS ---
@st.cache_data(ttl=300)
def carregar_dados_consolidados():
    try:
        # Tenta baixar da aba consolidada primeiro
        df = baixar_dados_google_sheet("Reservas Consolidadas")
        
        # Se estiver vazia ou mal formatada, tenta reconstruir das abas individuais
        if df.empty or len(df.columns) < 3:
            dfs = ler_abas_planilha(APARTMENT_SHEET_MAP)
            all_reservas = []
            for apt, df_apt in dfs.items():
                if df_apt is not None and not df_apt.empty:
                    df_apt['Apartamento'] = apt
                    all_reservas.append(df_apt)
            if all_reservas:
                df = pd.concat(all_reservas, ignore_index=True)
            else:
                return pd.DataFrame()
        
        return tratar_dataframe_consolidado(df)
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()

def obter_ultima_sincronizacao(df):
    """
    Extrai a data mais recente da coluna 'Última Atualização'
    """
    if df is None or df.empty or 'Última Atualização' not in df.columns:
        return None
    
    try:
        # Pegar a primeira célula não vazia como texto
        primeira = df['Última Atualização'].dropna().astype(str).str.strip()
        primeira = primeira[primeira.ne('')]
        if primeira.empty:
            return None
        primeira_texto = primeira.iloc[0]
        
        # Tenta converter para datetime para garantir que é válido
        try:
            return datetime.strptime(primeira_texto, '%d/%m/%Y %H:%M:%S')
        except ValueError:
            return primeira_texto # Retorna como string se falhar conversão, UI lida com isso
            
    except Exception as e:
        print(f"Erro ao extrair última sincronização: {e}")
        return None

# --- Callbacks ---

def on_sync_click():
    """Callback para o botão de sincronização."""
    with st.spinner("Sincronizando dados..."):
        try:
            logs = sincronizar_dados_completo()
            st.success("Sincronização concluída!")
            st.cache_data.clear() # Limpa o cache para recarregar dados novos
            
            # Força recarga dos dados
            df_novo = carregar_dados_consolidados()
            
            # Atualiza gráfico se houver dados
            if not df_novo.empty:
                apts_sel = st.session_state.get('apts_multiselect', [])
                if not apts_sel:
                    apts_sel = sorted(df_novo['Apartamento'].unique())
                
                df_filtered = df_novo[df_novo['Apartamento'].isin(apts_sel)]
                st.session_state.gantt_fig = create_gantt_chart(df_filtered)
            
            st.session_state.check_result_msg = None
            st.rerun()
        except Exception as e:
            st.error(f"Erro na sincronização: {e}")

def atualizar_grafico_base():
    """Callback: Gera apenas o gráfico base quando o filtro de apartamentos muda."""
    df_completo = carregar_dados_consolidados()
    if df_completo.empty: return

    apts_sel = st.session_state.apts_multiselect
    df_filtered = df_completo[df_completo['Apartamento'].isin(apts_sel)]
    
    st.session_state.gantt_fig = create_gantt_chart(df_filtered)
    st.session_state.check_result_msg = None
    st.session_state.check_result_status = None

def gerar_grafico_e_verificar():
    """
    Callback do Botão Verificar.
    Executa a verificação e regenera o gráfico COM os highlights.
    """
    dt_in = st.session_state.checkin_input
    dt_out = st.session_state.checkout_input
    apts_sel = st.session_state.get('apts_multiselect', [])
    
    # 1. Validações
    if not dt_in or not dt_out:
        st.session_state.check_result_status = 'warning'
        st.session_state.check_result_msg = "⚠️ Por favor, selecione ambas as datas."
        return

    dt_ini_reserva = pd.to_datetime(dt_in) + pd.Timedelta(hours=15)
    dt_fim_reserva = pd.to_datetime(dt_out) + pd.Timedelta(hours=11)

    if dt_ini_reserva >= dt_fim_reserva:
        st.session_state.check_result_status = 'error'
        st.session_state.check_result_msg = "⚠️ ERRO: A data de Check-out deve ser posterior à de Check-in."
        return

    # 2. Dados
    df_completo = carregar_dados_consolidados()
    if df_completo.empty:
        st.session_state.check_result_status = 'error'
        st.session_state.check_result_msg = "Erro: Dados não carregados."
        return

    if not apts_sel:
        apts_sel = sorted(df_completo['Apartamento'].unique())

    df_filtered = df_completo[df_completo['Apartamento'].isin(apts_sel)]

    # 3. Lógica de Verificação
    livres, ocupados = verificar_disponibilidade(df_filtered, dt_ini_reserva, dt_fim_reserva)
    
    # 4. Gerar Gráfico
    fig = create_gantt_chart(df_filtered)
    
    if fig:
        # 5. Adicionar Highlight (Sua Seleção)
        if livres:
            duracao_ms = (dt_fim_reserva - dt_ini_reserva).total_seconds() * 1000
            
            fig.add_trace(go.Bar(
                name="Sua Seleção",
                x=[duracao_ms] * len(livres),
                y=livres,
                base=[dt_ini_reserva] * len(livres),
                orientation='h',
                marker=dict(color='rgba(255, 215, 0, 0.5)', line=dict(width=1, color='gold')), 
                text=["SUA SELEÇÃO"] * len(livres),
                textposition='inside',
                insidetextanchor='middle',
                textfont=dict(color='black', size=12, weight='bold'),
                hoverinfo="text",
                hovertext=[
                    f"<b>DISPONÍVEL: {ap}</b><br>Início: {dt_ini_reserva.strftime('%d/%m %H:%M')}<br>Fim: {dt_fim_reserva.strftime('%d/%m %H:%M')}" 
                    for ap in livres
                ]
            ))

            fig.update_layout(
                barmode='overlay',
                xaxis=dict(range=[dt_ini_reserva - pd.Timedelta(days=3), dt_fim_reserva + pd.Timedelta(days=10)]),
                xaxis2=dict(range=[dt_ini_reserva - pd.Timedelta(days=3), dt_fim_reserva + pd.Timedelta(days=10)])
            )
        
        st.session_state.gantt_fig = fig
    
    # 6. Definir Mensagem de Resultado
    msg_html = f"**📅 Período:** {dt_ini_reserva.strftime('%d/%m/%Y')} até {dt_fim_reserva.strftime('%d/%m/%Y')}\n\n"
    if livres:
        st.session_state.check_result_status = 'success'
        msg_html += f"✅ **DISPONÍVEIS ({len(livres)}):** {', '.join(livres)}"
    else:
        st.session_state.check_result_status = 'error'
        msg_html += "❌ **NENHUM APARTAMENTO DISPONÍVEL.**"
    
    if ocupados:
        msg_html += f"\n\n⛔ **Ocupados ({len(ocupados)}):** {', '.join(ocupados)}"
        
    st.session_state.check_result_msg = msg_html

# --- Main Execution ---

ui.render_custom_css()

# Carrega dados iniciais
df_reservas = carregar_dados_consolidados()
ultima_sync = obter_ultima_sincronizacao(df_reservas)

# Renderiza Sidebar
ui.render_sidebar(ultima_sync, on_sync_click)

# Renderiza Header
ui.render_main_header()

if not df_reservas.empty:
    all_apts = sorted(df_reservas['Apartamento'].unique())
    
    # Renderiza Filtros e Ações
    ui.render_filters_and_actions(all_apts, atualizar_grafico_base, gerar_grafico_e_verificar)
    
    st.divider()
    
    # Renderiza Resultados da Verificação
    ui.render_check_results()

    # Inicializa gráfico se necessário
    if st.session_state.gantt_fig is None:
        atualizar_grafico_base()

    # Renderiza Gráfico
    ui.render_gantt_chart()

else:
    st.info("Nenhuma reserva encontrada. Clique em 'Sincronizar Dados Agora' na barra lateral.")
