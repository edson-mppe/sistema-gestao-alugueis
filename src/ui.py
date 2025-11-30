import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

def render_custom_css():
    """Renders custom CSS for the application."""
    st.markdown("""
    <style>
        /* --- CORREÇÃO DE ESPAÇO EM BRANCO (TOPO) --- */
        /* Reduz o padding padrão do Streamlit que empurra o conteúdo para baixo */
        .block-container {
            padding-top: 3rem !important;
            padding-bottom: 1rem !important;
            margin-top: 0rem !important;
        }

        .stButton>button {
            width: 100%;
            background-color: #FF4B4B;
            color: white;
        }
        .stButton>button:hover {
            background-color: #D32F2F;
            color: white;
        }
        .status-box {
            padding: 10px;
            border-radius: 5px;
            background-color: #f0f2f6;
            margin-bottom: 10px;
        }
        /* Mobile Optimizations */
        @media (max-width: 768px) {
            /* Ajuste fino para mobile: ainda menos espaço se necessário */
            .block-container {
                padding-top: 0.5rem !important;
            }
            
            .stButton>button {
                padding: 15px 10px;
                font-size: 16px;
                margin-bottom: 8px;
            }
            .status-box {
                padding: 8px;
                font-size: 14px;
            }
            /* Ajuste para inputs em mobile */
            div[data-baseweb="input"] {
                font-size: 16px; /* Evita zoom automático no iOS */
            }
            /* --- CORREÇÃO: Diminuir fonte do título principal (h1) no mobile --- */
            h1 {
                font-size: 1.5rem !important; /* Reduz para ~24px */
                padding-top: 0rem !important; /* Remove padding extra do próprio H1 */
            }
            /* --- CORREÇÃO: Diminuir fonte do subtítulo "Consultar Disponibilidade" (h3) --- */
            h3 {
                font-size: 1.1rem !important; /* Reduz para ~18px */
                padding-top: 0.5rem !important;
            }
        }
    </style>
    """, unsafe_allow_html=True)

def render_sidebar(last_sync_date, on_sync_click, on_mobile_mode_change=None):
    """
    Renders the sidebar with controls and sync status.
    
    Args:
        last_sync_date (datetime or str): The timestamp of the last synchronization.
        on_sync_click (callable): Function to be called when sync button is clicked.
        on_mobile_mode_change (callable): Function to be called when mobile mode is toggled.
    """
    with st.sidebar:
        st.title("Controles")
        
        # Toggle para Modo Mobile
        st.checkbox("📱 Modo Mobile", value=True, key="mobile_mode", help="Ativa otimizações para telas pequenas (Galaxy S25 Ultra)", on_change=on_mobile_mode_change)
        
        if st.button("🔄 Sincronizar Dados Agora"):
            on_sync_click()
        
        # --- Exibir Última Sincronização ---
        if last_sync_date:
            # Ensure last_sync_date is a datetime object for calculation
            if isinstance(last_sync_date, str):
                try:
                    last_sync_dt = datetime.strptime(last_sync_date, '%d/%m/%Y %H:%M:%S')
                except ValueError:
                    last_sync_dt = datetime.now() # Fallback
            else:
                last_sync_dt = last_sync_date

            tempo_decorrido = datetime.now() - last_sync_dt
            
            # Formatação do tempo decorrido
            total_seconds = tempo_decorrido.total_seconds()
            if total_seconds < 60:
                tempo_texto = "há poucos segundos"
            elif total_seconds < 3600:
                minutos = int(total_seconds // 60)
                tempo_texto = f"há {minutos} minuto(s)"
            elif tempo_decorrido.days == 0:
                horas = int(total_seconds // 3600)
                tempo_texto = f"há {horas} hora(s)"
            else:
                tempo_texto = f"há {tempo_decorrido.days} dia(s)"
            
            st.markdown(f"""
            <div style='background-color: #e8f5e9; padding: 12px; border-radius: 8px; margin-top: 15px; border-left: 4px solid #4caf50;'>
                <strong>✅ Última Sincronização:</strong><br>
                {last_sync_dt.strftime('%d/%m/%Y às %H:%M:%S')}<br>
                <small>({tempo_texto})</small>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style='background-color: #fff3e0; padding: 12px; border-radius: 8px; margin-top: 15px; border-left: 4px solid #ff9800;'>
                <strong>⚠️ Nenhuma sincronização realizada</strong>
            </div>
            """, unsafe_allow_html=True)
        
        st.divider()
        st.info("Painel de controle do sistema.")

def render_main_header():
    """Renders the main page header."""
    st.title("📅 Mapa de Ocupação & Disponibilidade")

def render_filters_and_actions(all_apts, on_filter_change, on_verify_click):
    """
    Renders the filter section and action buttons.
    
    Args:
        all_apts (list): List of all available apartments.
        on_filter_change (callable): Callback when filter changes.
        on_verify_click (callable): Callback when verify button is clicked.
    """
    st.markdown("### 🔍 Consultar Disponibilidade")
    
    # Se mobile mode ativo, usar expander para economizar espaço
    is_mobile = st.session_state.get('mobile_mode', False)
    
    if is_mobile:
        with st.expander("🔧 Filtros e Datas", expanded=True):
            _render_filter_content(all_apts, on_filter_change, on_verify_click)
    else:
        _render_filter_content(all_apts, on_filter_change, on_verify_click)

def _render_filter_content(all_apts, on_filter_change, on_verify_click):
    """Helper function to render filter content (used with or without expander)."""
    col_filtros, col_dates = st.columns([1, 2])
    
    with col_filtros:
        st.multiselect(
            "Filtrar Apartamentos (Visualização)", 
            options=all_apts,
            default=all_apts,
            key="apts_multiselect",
            on_change=on_filter_change 
        )

    with col_dates:
        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            st.date_input("Check-in", key="checkin_input", format="DD/MM/YYYY", on_change=lambda: st.session_state.update(checkout_input=st.session_state.checkin_input + timedelta(days=1)))
        with c2:
            st.date_input("Check-out", key="checkout_input", format="DD/MM/YYYY")
        with c3:
            st.write("") 
            st.write("") 
            st.button("Verificar Disponibilidade", on_click=on_verify_click)

def render_check_results():
    """Renders the results of the availability check."""
    if st.session_state.get('check_result_msg'):
        status = st.session_state.get('check_result_status')
        msg = st.session_state.get('check_result_msg')
        
        if status == 'success': st.success(msg)
        elif status == 'error': st.error(msg)
        elif status == 'warning': st.warning(msg)
        else: st.info(msg)

def render_gantt_chart():
    """Renders the Gantt chart from session state."""
    if st.session_state.get('gantt_fig'):
        # Atualizado para corrigir aviso de depreciação do Streamlit (2025)
        # De use_container_width=True para width="stretch"
        st.plotly_chart(st.session_state.gantt_fig, width="stretch")