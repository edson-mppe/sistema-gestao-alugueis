import streamlit as st
import streamlit.components.v1 as components # Importação necessária para o hack do idioma
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

# Importações dos módulos locais
from src.services import sincronizar_dados_completo
from src.gsheets_api import baixar_dados_google_sheet, ler_abas_planilha, baixar_ultimas_reservas_consolidadas, baixar_proximos_hospedes_consolidados
from src.logic import create_gantt_chart, verificar_disponibilidade, consolidar_e_salvar_reservas, tratar_dataframe_consolidado
from src.config import APARTMENT_SHEET_MAP
import src.ui as ui

# --- Configuração da Página ---
st.set_page_config(
    page_title="Gestão de Aluguéis",
    page_icon="🏢",
    layout="wide"
)

# --- HACK: Definir idioma para pt-BR ---
# Isso altera o atributo 'lang' do HTML para evitar que o navegador sugira tradução
components.html("""
    <script>
        window.parent.document.documentElement.lang = 'pt-BR';
    </script>
""", height=0)

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

# A inicialização manual de 'mobile_mode' foi removida para evitar conflito com o valor padrão do widget no ui.py

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
        primeira = df['Última Atualização'].dropna().astype(str).str.strip()
        primeira = primeira[primeira.ne('')]
        if primeira.empty:
            return None
        primeira_texto = primeira.iloc[0]
        
        try:
            return datetime.strptime(primeira_texto, '%d/%m/%Y %H:%M:%S')
        except ValueError:
            return primeira_texto 
            
    except Exception as e:
        print(f"Erro ao extrair última sincronização: {e}")
        return None

@st.cache_data(ttl=300)
def carregar_proximos_hospedes():
    """Wrapper com cache para baixar próximos hóspedes."""
    return baixar_proximos_hospedes_consolidados()

@st.cache_data(ttl=300)
def carregar_ultimas_reservas():
    """Wrapper com cache para baixar últimas reservas."""
    return baixar_ultimas_reservas_consolidadas()

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
                # CORREÇÃO: Default True para garantir visualização mobile no carregamento pós-sync
                is_mobile = st.session_state.get('mobile_mode', True)
                st.session_state.gantt_fig = create_gantt_chart(df_filtered, is_mobile=is_mobile)
            
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
    
    # CORREÇÃO: Default True aqui também
    is_mobile = st.session_state.get('mobile_mode', True)
    st.session_state.gantt_fig = create_gantt_chart(df_filtered, is_mobile=is_mobile)
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
    # CORREÇÃO: Default True para mobile
    is_mobile = st.session_state.get('mobile_mode', True)
    fig = create_gantt_chart(df_filtered, is_mobile=is_mobile)
    
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

            # --- AJUSTE DE ZOOM CONSISTENTE ---
            # Se for mobile, usa um range menor (8 dias à frente) para manter as barras largas (zoom in)
            # Se for desktop, usa um range maior (20 dias à frente)
            days_fwd = 8 if is_mobile else 20
            days_back = 2 if is_mobile else 3

            fig.update_layout(
                barmode='overlay',
                xaxis=dict(range=[dt_ini_reserva - pd.Timedelta(days=days_back), dt_fim_reserva + pd.Timedelta(days=days_fwd)]),
                xaxis2=dict(range=[dt_ini_reserva - pd.Timedelta(days=days_back), dt_fim_reserva + pd.Timedelta(days=days_fwd)])
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
ui.render_sidebar(ultima_sync, on_sync_click, on_mobile_mode_change=atualizar_grafico_base)

# Renderiza Header
ui.render_main_header()

if not df_reservas.empty:
    all_apts = sorted(df_reservas['Apartamento'].unique())
    
    # Renderiza Filtros e Ações
    ui.render_filters_and_actions(all_apts, atualizar_grafico_base, gerar_grafico_e_verificar)
    
    st.divider()
    
    # Renderiza Resultados da Verificação
    ui.render_check_results()

    # Inicializa gráfico se necessário (Primeira carga)
    if st.session_state.gantt_fig is None:
        atualizar_grafico_base()

    # Renderiza Gráfico
    ui.render_gantt_chart()

    st.divider()

    # --- EXIBIR TABELA DE PRÓXIMOS HÓSPEDES ---
    st.markdown("### 📋 Próximos Hóspedes")
    
    with st.spinner("Buscando próximas chegadas..."):
        df_proximos_hospedes = carregar_proximos_hospedes()
    
    if not df_proximos_hospedes.empty:
        # Conversão e limpeza de dados
        for col in ['Início', 'Fim', 'Data Reserva']:
            if col in df_proximos_hospedes.columns:
                df_proximos_hospedes[col] = pd.to_datetime(df_proximos_hospedes[col], dayfirst=True, errors='coerce')
        
        # Tenta garantir que colunas numéricas sejam números
        for col in ['Dias', 'Pessoas']:
            if col in df_proximos_hospedes.columns:
                 df_proximos_hospedes[col] = pd.to_numeric(df_proximos_hospedes[col], errors='coerce')

        # Definição das colunas para exibição (Ordem e existência)
        #desired_order = [
        #    "Apartamento", "Quem", "Início", "Fim", "Dias até Check-in", 
        #    "Dias", "Pessoas", "Total BT", "Diária BT", "Origem"
        
        desired_order = [
            "Apartamento", "Quem", "Início", "Fim", "Dias até Check-in", 
            "Dias", "Pessoas", "Origem"
        ]
        
        # Filtra apenas as colunas que realmente existem no DataFrame
        cols_to_show = [c for c in desired_order if c in df_proximos_hospedes.columns]
        
        # Configuração visual das colunas
        col_config = {
            "Apartamento": st.column_config.TextColumn("Apto"),
            "Início": st.column_config.DateColumn("Check-in", format="DD/MM/YYYY"),
            "Fim": st.column_config.DateColumn("Check-out", format="DD/MM/YYYY"),
            #"Data Reserva": st.column_config.DateColumn("Reserva", format="DD/MM/YYYY"),
            "Dias até Check-in": st.column_config.NumberColumn("Dias p/ Chegar", format="%d dias", help="Dias restantes até o check-in"),
            "Quem": st.column_config.TextColumn("Hóspede"),
            "Origem": st.column_config.TextColumn("Canal"),
            "Dias": st.column_config.NumberColumn("Noites"),
            "Pessoas": st.column_config.NumberColumn("Pax"),
            "Total BT": st.column_config.TextColumn("Total"),   # Mantém como texto para não quebrar formatação "R$" se vier string
            "Diária BT": st.column_config.TextColumn("Diária"), # Mantém como texto
        }

        event = st.dataframe(
            df_proximos_hospedes[cols_to_show], 
            hide_index=True, 
            width="stretch", # Atualizado: width="stretch" em vez de use_container_width=True
            column_config=col_config,
            selection_mode="single-row",
            on_select="rerun"
        )

        # --- BOTÕES AUTOMÁTICOS PARA CHECK-IN HOJE ---
        hoje = datetime.now().date()
        
        # Filtra check-ins de hoje
        if 'Início' in df_proximos_hospedes.columns:
             checkins_hoje = df_proximos_hospedes[
                df_proximos_hospedes['Início'].dt.date == hoje
             ]
             
             if not checkins_hoje.empty:
                 st.markdown("#### 🔔 Check-ins de Hoje")
                 cols = st.columns(len(checkins_hoje))
                 for idx, (_, row) in enumerate(checkins_hoje.iterrows()):
                     apto = row['Apartamento']
                     msg = f"Bom dia!. Hoje teremos chech-in no Apto {apto}"
                     import urllib.parse
                     msg_encoded = urllib.parse.quote(msg)
                     phone = "558193275644"
                     whatsapp_url = f"https://wa.me/{phone}?text={msg_encoded}"
                     
                     with cols[idx]:
                        st.link_button(f"📲 Enviar WhatsApp (Apto {apto})", whatsapp_url, type="primary")

        # --- SELEÇÃO MANUAL ---
        if len(event.selection.rows) > 0:
            selected_row_index = event.selection.rows[0]
            selected_row = df_proximos_hospedes[cols_to_show].iloc[selected_row_index]
            
            apto = selected_row["Apartamento"]
            
            # Formata a mensagem
            msg = f"Bom dia!. Hoje teremos chech-in no Apto {apto}"
            
            # Codifica a mensagem para URL
            import urllib.parse
            msg_encoded = urllib.parse.quote(msg)
            
            # Número fixo conforme solicitado
            phone = "558193275644"
            
            whatsapp_url = f"https://wa.me/{phone}?text={msg_encoded}"
            
            st.link_button(f"📱 Enviar WhatsApp (Apto {apto})", whatsapp_url)
    else:
        st.info("Não foi possível carregar os próximos hóspedes (ou não há reservas futuras).")  
    
    st.divider()

    # --- EXIBIR TABELA DE ÚLTIMAS RESERVAS ---
    st.markdown("### 📋 Últimas Reservas (Top 3 por Apto)")
    
    with st.spinner("Buscando reservas recentes..."):
        # Chama a função cached wrapper
        df_recents = carregar_ultimas_reservas()
        
    if not df_recents.empty:
        # Garante que as colunas de data sejam datetime para ordenação correta
        for col in ['Início', 'Fim', 'Data Reserva']:
            if col in df_recents.columns:
                # ADICIONADO: dayfirst=True para evitar aviso de parser warning com datas DD/MM/YYYY
                df_recents[col] = pd.to_datetime(df_recents[col], dayfirst=True, errors='coerce')

        # Exibe a tabela utilizando st.dataframe com column_config para formatação
        st.dataframe(
            df_recents, 
            hide_index=True,
            width="stretch", # Atualizado: width="stretch" em vez de use_container_width=True
            column_config={
                "Início": st.column_config.DateColumn("Início", format="DD/MM/YYYY"),
                "Fim": st.column_config.DateColumn("Fim", format="DD/MM/YYYY"),
                "Data Reserva": st.column_config.DateColumn("Data Reserva", format="DD/MM/YYYY"),
                "Dias Decorridos": st.column_config.NumberColumn("Dias Decorridos", format="%d dias")
            }
        )
    else:
        st.info("Não foi possível carregar as reservas recentes.")

else:
    st.info("Nenhuma reserva encontrada. Clique em 'Sincronizar Dados Agora' na barra lateral.")