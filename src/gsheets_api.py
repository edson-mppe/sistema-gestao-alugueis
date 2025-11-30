import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google.oauth2.credentials import Credentials as UserCredentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import os
from src.config import SHEET_KEY, get_google_credentials

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

def authenticate_google_sheets():
    """
    Autentica no Google Sheets.
    Suporta Service Account (via st.secrets ou arquivo) e OAuth User (via credentials.json local).
    """
    creds_data = get_google_credentials()
    
    creds = None
    
    # 1. Service Account (Dicionário do st.secrets ou Caminho do Arquivo)
    if isinstance(creds_data, dict):
        creds = ServiceAccountCredentials.from_service_account_info(creds_data, scopes=SCOPES)
    elif isinstance(creds_data, str) and "service" in creds_data.lower(): # Heurística simples
        creds = ServiceAccountCredentials.from_service_account_file(creds_data, scopes=SCOPES)
        
    # 2. Fallback para OAuth User (Fluxo original dos notebooks)
    # Se creds_data for string e não parecer service account, ou se falhar acima
    if not creds and isinstance(creds_data, str):
        token_file = 'token.json'
        if os.path.exists(token_file):
            creds = UserCredentials.from_authorized_user_file(token_file, SCOPES)
            
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception:
                    creds = None # Força re-login se refresh falhar
            
            if not creds:
                # Tenta o fluxo interativo apenas se estiver rodando localmente (não no Streamlit Cloud)
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(creds_data, SCOPES)
                    creds = flow.run_local_server(port=0)
                    # Salva o token para próximas execuções
                    with open(token_file, 'w') as token:
                        token.write(creds.to_json())
                except Exception as e:
                    st.error(f"Falha na autenticação OAuth local: {e}")
                    return None

    if not creds:
        st.error("Não foi possível encontrar credenciais válidas. Verifique o .streamlit/secrets.toml ou credentials.json.")
        return None

    return gspread.authorize(creds)

def baixar_dados_google_sheet(tab_name):
    """
    Baixa dados de uma aba específica.
    Procura dinamicamente pela linha de cabeçalho.
    """
    try:
        gc = authenticate_google_sheets()
        if not gc: return pd.DataFrame()
        
        sh = gc.open_by_key(SHEET_KEY)
        worksheet = sh.worksheet(tab_name)
        all_values = worksheet.get_all_values()
        
        if len(all_values) < 1:
            return pd.DataFrame()
            
        # Procura pela linha de cabeçalho
        header_row_index = -1
        for i, row in enumerate(all_values[:10]): # Procura nas primeiras 10 linhas
            if "Início" in row and "Fim" in row:
                header_row_index = i
                break
        
        if header_row_index != -1:
            headers = all_values[header_row_index]
            data = all_values[header_row_index + 1:]
        else:
            # Se não achar, assume que não tem cabeçalho ou está em formato inesperado
            # Tenta usar a primeira linha se parecer cabeçalho, senão retorna vazio
            # Mas como falhou antes, melhor retornar vazio para forçar o fallback
            st.warning(f"Cabeçalhos 'Início' e 'Fim' não encontrados na aba '{tab_name}'.")
            return pd.DataFrame()
        
        df = pd.DataFrame(data, columns=headers)
        
        # Validação de colunas essenciais
        if 'Início' not in df.columns or 'Fim' not in df.columns:
            st.warning(f"Colunas 'Início' e 'Fim' não encontradas na aba '{tab_name}'. Retornando vazio para forçar fallback.")
            return pd.DataFrame()
            
        # Seleção de colunas por nome para maior robustez
        cols_to_keep = ['Início', 'Fim', 'Apartamento', 'Status', 'Quem', 'Origem', 'Última Atualização']
        existing_cols = [col for col in cols_to_keep if col in df.columns]
        
        if existing_cols:
            df = df[existing_cols].copy()
            
        return df
    except Exception as e:
        st.error(f"Erro ao baixar dados da aba '{tab_name}': {e}")
        return pd.DataFrame()

def baixar_ultimas_reservas_consolidadas(tab_name = "Reservas Consolidadas"):
    """
    Baixa as 3 reservas mais recentes de cada apartamento da aba 'Reservas Consolidadas'.
    Retorna DataFrame com colunas específicas e dias desde a reserva.
    """
    try:
        gc = authenticate_google_sheets()
        if not gc: return pd.DataFrame()
        
        sh = gc.open_by_key(SHEET_KEY)
        tab_name = "Reservas Consolidadas"
        try:
            worksheet = sh.worksheet(tab_name)
        except gspread.WorksheetNotFound:
            st.warning(f"Aba '{tab_name}' não encontrada.")
            return pd.DataFrame()

        all_values = worksheet.get_all_values()
        
        if len(all_values) < 1:
            return pd.DataFrame()
            
        # Busca cabeçalho (reutilizando lógica para robustez)
        header_row_index = -1
        for i, row in enumerate(all_values[:10]):
            if "Início" in row and "Fim" in row:
                header_row_index = i
                break
        
        if header_row_index != -1:
            headers = all_values[header_row_index]
            data = all_values[header_row_index + 1:]
        else:
            return pd.DataFrame()
            
        df = pd.DataFrame(data, columns=headers)
        
        # Colunas desejadas
        target_cols = ['Apartamento', 'Início', 'Fim', 'Dias', 'Pessoas', 'Quem', 'Origem', 'Data Reserva']
        # Filtra colunas existentes
        existing_cols = [c for c in target_cols if c in df.columns]
        
        if not existing_cols:
            return pd.DataFrame()
            
        df = df[existing_cols].copy()
        
        if 'Data Reserva' in df.columns and 'Apartamento' in df.columns:
            # Converte para datetime para ordenação e cálculo
            df['Data Reserva'] = pd.to_datetime(df['Data Reserva'], dayfirst=True, errors='coerce')
            
            # Remove linhas sem data de reserva válida para o cálculo
            df = df.dropna(subset=['Data Reserva'])
            
            # Ordena por Data Reserva (mais recente primeiro) e pega top 3 por Apartamento
            df = df.sort_values('Data Reserva', ascending=False)
            df = df.groupby('Apartamento').head(3).reset_index(drop=True)
            
            # Cálculo de dias passados ('Dias Decorridos')
            now = pd.Timestamp.now()
            df['Dias Decorridos'] = (now - df['Data Reserva']).dt.days
            
            return df
        else:
            # Se não tiver as colunas essenciais, retorna vazio ou o que tiver
            if 'Data Reserva' not in df.columns:
                st.warning("Coluna 'Data Reserva' não encontrada para cálculo de recência.")
            return df

    except Exception as e:
        st.error(f"Erro ao buscar últimas reservas: {e}")
        return pd.DataFrame()

def ler_abas_planilha(abas_map):
    """
    Lê múltiplas abas e retorna um dicionário {nome_aba: dataframe}.
    """
    dfs = {}
    gc = authenticate_google_sheets()
    if not gc: return dfs
    
    sh = gc.open_by_key(SHEET_KEY)
    
    for apt_cod, tab_name in abas_map.items():
        try:
            worksheet = sh.worksheet(tab_name)
            all_values = worksheet.get_all_values()
            if len(all_values) >= 4:
                headers = all_values[2]
                data = all_values[3:]
                dfs[tab_name] = pd.DataFrame(data, columns=headers)
        except Exception as e:
            st.warning(f"Aba '{tab_name}' não encontrada ou erro ao ler: {e}")
            
    return dfs


def salvar_df_no_gsheet(df, tab_name="Reservas Consolidadas"):
    try:
        gc = authenticate_google_sheets()
        if not gc: return
        
        sh = gc.open_by_key(SHEET_KEY)
        try:
            worksheet = sh.worksheet(tab_name)
        except gspread.WorksheetNotFound:
            worksheet = sh.add_worksheet(title=tab_name, rows=len(df), cols=len(df.columns))
            
        # 1. Prepara os dados
        df_str = df.astype(str)
        dados = [df_str.columns.values.tolist()] + df_str.values.tolist()
        
        # 2. Sobrescreve os dados (mantendo formatação das células escritas)
        worksheet.update(range_name='A1', values=dados)
        
        # 3. TRUQUE: Redimensiona a planilha para cortar sobras antigas
        # Número de linhas = dados + cabeçalho.
        # Isso deleta as linhas antigas que ficariam sobrando lá embaixo.
        worksheet.resize(rows=len(df_str) + 1, cols=len(df_str.columns))
        
        worksheet.columns_auto_resize(0, len(df.columns)-1)
        
    except Exception as e:
        import streamlit as st
        st.error(f"Erro ao salvar dados na aba '{tab_name}': {e}")

def inserir_linha_google_sheet(dados_linha, tab_name="Inconsistências"):
    """
    Insere uma linha no final da aba especificada.
    """
    try:
        gc = authenticate_google_sheets()
        if not gc: return
        
        sh = gc.open_by_key(SHEET_KEY)
        worksheet = sh.worksheet(tab_name)
        worksheet.append_row(dados_linha)
        
    except Exception as e:
        st.error(f"Erro ao inserir linha em '{tab_name}': {e}")