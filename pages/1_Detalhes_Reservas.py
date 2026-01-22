import streamlit as st
import pandas as pd
from datetime import datetime
import streamlit.components.v1 as components
import src.ui as ui
from src.gsheets_api import baixar_proximos_hospedes_consolidados, baixar_ultimas_reservas_consolidadas

# --- Configuração da Página ---
# --- Configuração da Página ---
# Config removida (movida para app.py)

# --- HACK: Definir idioma para pt-BR ---
components.html("""
    <script>
        window.parent.document.documentElement.lang = 'pt-BR';
    </script>
""", height=0)

# --- CARREGAMENTO DE DADOS ---
@st.cache_data(ttl=300)
def carregar_proximos_hospedes():
    """Wrapper com cache para baixar próximos hóspedes."""
    return baixar_proximos_hospedes_consolidados()

@st.cache_data(ttl=300)
def carregar_ultimas_reservas():
    """Wrapper com cache para baixar últimas reservas."""
    return baixar_ultimas_reservas_consolidadas()

# --- Main Execution ---

# Inicializa estado de autenticação para esta página
if 'authenticated_details' not in st.session_state:
    st.session_state.authenticated_details = False

def check_password():
    """Verifica a senha inserida."""
    password = st.session_state.password_input_details
    if password == "0512":
        st.session_state.authenticated_details = True
        del st.session_state.password_input_details  # Remove a senha do estado por segurança
    else:
        st.error("Senha incorreta")

if not st.session_state.authenticated_details:
    st.title("🔒 Acesso Restrito")
    st.text_input("Digite a senha de acesso:", type="password", key="password_input_details", on_change=check_password)
    st.stop()

ui.render_custom_css()

st.title("📋 Detalhes das Reservas")

# --- EXIBIR TABELA DE PRÓXIMOS HÓSPEDES ---
st.markdown("### 🏃‍♂️ Próximos Hóspedes")

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
        "Dias até Check-in": st.column_config.NumberColumn("Dias p/ Chegar", format="%d dias", help="Dias restantes até o check-in"),
        "Quem": st.column_config.TextColumn("Hóspede"),
        "Origem": st.column_config.TextColumn("Canal"),
        "Dias": st.column_config.NumberColumn("Noites"),
        "Pessoas": st.column_config.NumberColumn("Pax"),
        "Total BT": st.column_config.TextColumn("Total"),
        "Diária BT": st.column_config.TextColumn("Diária"),
    }

    event = st.dataframe(
        df_proximos_hospedes[cols_to_show], 
        hide_index=True, 
        width="stretch",
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
st.markdown("### 🕒 Últimas Reservas (Top 3 por Apto)")

with st.spinner("Buscando reservas recentes..."):
    # Chama a função cached wrapper
    df_recents = carregar_ultimas_reservas()
    
if not df_recents.empty:
    # Garante que as colunas de data sejam datetime para ordenação correta
    for col in ['Início', 'Fim', 'Data Reserva']:
        if col in df_recents.columns:
            df_recents[col] = pd.to_datetime(df_recents[col], dayfirst=True, errors='coerce')

    # Exibe a tabela utilizando st.dataframe com column_config para formatação
    st.dataframe(
        df_recents, 
        hide_index=True,
        width="stretch",
        column_config={
            "Início": st.column_config.DateColumn("Início", format="DD/MM/YYYY"),
            "Fim": st.column_config.DateColumn("Fim", format="DD/MM/YYYY"),
            "Data Reserva": st.column_config.DateColumn("Data Reserva", format="DD/MM/YYYY"),
            "Dias Decorridos": st.column_config.NumberColumn("Dias Decorridos", format="%d dias")
        }
    )
else:
    st.info("Não foi possível carregar as reservas recentes.")
