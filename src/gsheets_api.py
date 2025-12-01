import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google.oauth2.credentials import Credentials as UserCredentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import os
from src.config import SHEET_KEY, get_google_credentials, APARTMENT_SHEET_MAP
from src.utils import parse_pt_date
from datetime import datetime, time, timedelta




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
        
        # Remove colunas duplicadas (mantendo a primeira ocorrência)
        df = df.loc[:, ~df.columns.duplicated()]
        
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

def baixar_proximos_hospedes_consolidados(tab_name = "Reservas Consolidadas"):
    """
    Baixa os próximos hóspedes (futuros) de cada apartamento da aba 'Reservas Consolidadas'.
    Retorna DataFrame com colunas específicas e dias até o check-in.
    """
    try:
        gc = authenticate_google_sheets()
        if not gc: return pd.DataFrame()
        
        sh = gc.open_by_key(SHEET_KEY)
        try:
            worksheet = sh.worksheet(tab_name)
        except gspread.WorksheetNotFound:
            st.warning(f"Aba '{tab_name}' não encontrada.")
            return pd.DataFrame()

        all_values = worksheet.get_all_values()
        
        if len(all_values) < 1:
            return pd.DataFrame()
            
        # Busca cabeçalho
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
        
        # Colunas essenciais (Atualizado com as novas colunas solicitadas)
        required_cols = ['Apartamento', 'Início', 'Fim', 'Dias', 'Pessoas', 'Quem', 'Origem', 'Total BT', 'Diária BT', 'Data Reserva', 'Status']
        existing_cols = [c for c in required_cols if c in df.columns]
        
        if not existing_cols:
            return pd.DataFrame()
            
        df = df[existing_cols].copy()
        
        # Conversão de datas
        df['Início'] = pd.to_datetime(df['Início'], dayfirst=True, errors='coerce')
        df['Fim'] = pd.to_datetime(df['Fim'], dayfirst=True, errors='coerce')
        
        # Remove datas inválidas
        df = df.dropna(subset=['Início'])
        
        # Filtra apenas reservas ativas (não canceladas) se a coluna Status existir
        if 'Status' in df.columns:
            df = df[~df['Status'].astype(str).str.contains('Cancelad', case=False, na=False)]

        # Define "hoje" (apenas data, sem hora)
        hoje = pd.Timestamp.now().normalize()
        
        # Filtra apenas reservas que começam hoje ou no futuro
        # Se quiser incluir quem já está hospedado (mas ainda não saiu), use: df['Fim'] >= hoje
        # Aqui assumirei "Próximas chegadas" -> Início >= hoje
        df_futuro = df[df['Início'] >= hoje].copy()
        
        if df_futuro.empty:
            return pd.DataFrame()

        # Ordena por data de início (mais próxima primeiro)
        df_futuro = df_futuro.sort_values('Início', ascending=True)
        
        # Pega a primeira ocorrência (mais próxima) para cada apartamento
        df_proximos = df_futuro.groupby('Apartamento').head(1).reset_index(drop=True)
        
        # Calcula dias até o check-in
        df_proximos['Dias até Check-in'] = (df_proximos['Início'] - hoje).dt.days
        
        # Formata a data para visualização
        df_proximos['Início'] = df_proximos['Início'].dt.strftime('%d/%m/%Y')
        df_proximos['Fim'] = df_proximos['Fim'].dt.strftime('%d/%m/%Y')
        
        # Organiza as colunas conforme solicitado
        final_cols_order = ['Apartamento', 'Início', 'Fim', 'Dias', 'Pessoas', 'Quem', 'Origem', 'Total BT', 'Diária BT', 'Data Reserva', 'Dias até Check-in']
        cols_to_return = [c for c in final_cols_order if c in df_proximos.columns]
        
        return df_proximos[cols_to_return]

    except Exception as e:
        st.error(f"Erro ao buscar próximos hóspedes: {e}")
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

  
def salvar_df_no_gsheet(df, tab_name="Reservas Consolidadas"):
    """
    Salva o DataFrame no Google Sheets com lógica robusta:
    1. Limpa a aba antes de escrever (evita problemas com filtros antigos).
    2. Trata NaNs como strings vazias.
    3. Compatível com versões novas e antigas do gspread.
    """
    try:
        gc = authenticate_google_sheets()
        if not gc: return
        
        sh = gc.open_by_key(SHEET_KEY)
        
        # 1. Abre ou cria a aba
        try:
            worksheet = sh.worksheet(tab_name)
            # CRUCIAL: Limpa tudo antes de escrever. 
            # Isso remove filtros antigos e linhas 'fantasmas' que causavam o erro de visualização.
            worksheet.clear() 
        except gspread.WorksheetNotFound:
            worksheet = sh.add_worksheet(title=tab_name, rows=len(df)+20, cols=len(df.columns))
            
        # 2. Tratamento de dados
        # fillna('') deixa a célula vazia no Sheets, em vez de escrever a palavra "nan"
        df_clean = df.fillna('')
        
        # Prepara a lista de listas (Cabeçalho + Dados)
        dados = [df_clean.columns.values.tolist()] + df_clean.values.tolist()
        
        # 3. Escrita Robusta (Bloco do Teste)
        try:
            # Tenta sintaxe nova (gspread >= 6.0)
            worksheet.update(values=dados, range_name='A1')
        except TypeError:
            # Fallback para sintaxe antiga (gspread < 6.0)
            worksheet.update('A1', dados)
        except Exception:
            # Última tentativa genérica
            worksheet.update(dados)
            
        # 4. Ajuste Visual (Opcional, mas bom para manter organizado)
        try:
            # Redimensiona para o tamanho exato dos dados
            worksheet.resize(rows=len(dados), cols=len(df.columns))
            # Ajusta largura das colunas
            # (Se der erro aqui, ignoramos com pass para não travar o processo principal)
            worksheet.columns_auto_resize(0, len(df.columns)-1)
        except Exception:
            pass
        
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


def ler_abas_planilha(abas_map):
    """
    Lê múltiplas abas buscando dinamicamente a linha de cabeçalho.
    Retorna um dicionário {nome_aba: dataframe}.
    """
    dfs = {}
    gc = authenticate_google_sheets()
    if not gc: return dfs
    
    sh = gc.open_by_key(SHEET_KEY)
    
    for apt_cod, tab_name in abas_map.items():
        try:
            worksheet = sh.worksheet(tab_name)
            all_values = worksheet.get_all_values(value_render_option='FORMATTED_VALUE')
            
            if len(all_values) < 1:
                continue

            # --- CORREÇÃO: Busca dinâmica pelo cabeçalho (igual ao baixar_dados) ---
            header_row_index = -1
            for i, row in enumerate(all_values[:10]): # Procura nas primeiras 10 linhas
                # Procura por colunas chave para identificar a linha correta
                row_str = [str(c).strip() for c in row]
                if "Início" in row_str and "Status" in row_str:
                    header_row_index = i
                    break
            
            if header_row_index != -1:
                headers = all_values[header_row_index]
                # Remove espaços extras dos nomes das colunas para evitar erros no concat
                headers = [h.strip() for h in headers] 
                data = all_values[header_row_index + 1:]
                
                df = pd.DataFrame(data, columns=headers)
                
                # Remove colunas vazias ou duplicadas
                df = df.loc[:, ~df.columns.duplicated()]
                dfs[tab_name] = df
            else:
                st.warning(f"Cabeçalho não encontrado na aba '{tab_name}'. Verifique se existem colunas 'Início' e 'Status'.")

        except Exception as e:
            st.warning(f"Aba '{tab_name}' não encontrada ou erro ao ler: {e}")
            
    return dfs

def tratar_dataframe_consolidado(df):
    """
    Realiza a limpeza, padronização de datas e regras de negócio no DataFrame de reservas.

    Processos realizados:
    1. Higiene de Dados: Remove colunas duplicadas e linhas sem data de início.
    2. Conversão de Datas: Transforma 'Início' e 'Fim' em objetos datetime, lidando com formatos variados e nomes de meses em português (ex: 'out' -> '10').
    3. Padronização de Horários:
       - Se a hora não for informada (00:00), define Check-in às 15:00 e Check-out às 11:00.
    4. Atualização de Status: Marca automaticamente como 'Concluído' as reservas cuja data final é anterior ao momento atual.
    5. Garantia de Colunas: Assegura que colunas essenciais como 'Origem' existam.

    Args:
        df (pd.DataFrame): DataFrame bruto concatenado das abas.

    Returns:
        pd.DataFrame: DataFrame limpo e pronto para análise/salvamento.
    """
    if df is None or df.empty:
        return pd.DataFrame()
    
    df_tratado = df.copy()
    
    # 1. Remove duplicatas de colunas
    df_tratado = df_tratado.loc[:, ~df_tratado.columns.duplicated()]

    # 2. Limpeza prévia de linhas vazias
    if 'Início' in df_tratado.columns:
        df_tratado = df_tratado.dropna(subset=['Início'])
        # Garante que é string antes de usar .str
        df_tratado = df_tratado[df_tratado['Início'].astype(str).str.strip() != '']

    # 3. Aplica conversão de datas
    if 'Início' in df_tratado.columns:
        df_tratado['Início'] = df_tratado['Início'].apply(parse_pt_date)
    if 'Fim' in df_tratado.columns:
        df_tratado['Fim'] = df_tratado['Fim'].apply(parse_pt_date)

    # 4. Remove linhas onde a data não pôde ser entendida (NaT)
    df_tratado = df_tratado.dropna(subset=['Início', 'Fim'])

    def add_default_hours(dt, hour_val):
        # Adiciona hora apenas se for meia-noite exata (data pura)
        if pd.notnull(dt) and dt.time() == time(0, 0):
            return dt + timedelta(hours=hour_val)
        return dt

    # 5. Check-in 15h / Check-out 11h
    df_tratado['Início'] = df_tratado['Início'].apply(lambda x: add_default_hours(x, 15))
    df_tratado['Fim'] = df_tratado['Fim'].apply(lambda x: add_default_hours(x, 11))

    # 6. Atualiza Status
    agora = datetime.now()
    if 'Status' not in df_tratado.columns:
        df_tratado['Status'] = ''
        
    df_tratado.loc[df_tratado['Fim'] < agora, 'Status'] = 'Concluído'
    
    # 7. Garante Origem
    if 'Origem' not in df_tratado.columns:
        df_tratado['Origem'] = 'Desconhecido'

    return df_tratado

def consolidar_e_salvar_reservas(add_log_func):
    """
    Função isolada para consolidar reservas de todos os apartamentos.
    """
    add_log_func("--- Iniciando Consolidação de Reservas ---")
    
    # 1. Ler as abas individuais
    dfs_dict = ler_abas_planilha(APARTMENT_SHEET_MAP)
    
    all_reservas = []
    total_linhas_lidas = 0
    
    if dfs_dict:
        for tab_name, df in dfs_dict.items():
            if df is not None and not df.empty:
                df = df.copy()
                
                # Preenche coluna de origem (Apartamento)
                # Nota: tab_name é o nome da aba (ex: SM-C108)
                df['Apartamento'] = tab_name 
                
                all_reservas.append(df)
                total_linhas_lidas += len(df)
                # Log detalhado para debug (opcional)
                # print(f"Aba {tab_name}: {len(df)} reservas encontradas.")
    else:
        add_log_func("Nenhuma aba foi lida corretamente. Verifique os nomes das abas e cabeçalhos.")
        return
    
    if all_reservas:
        # 2. Concatenação (União)
        # sort=False evita reordenar colunas alfabeticamente
        df_consolidado = pd.concat(all_reservas, ignore_index=True, sort=False)
        
        qtd_final = len(df_consolidado)
        add_log_func(f"União realizada: {len(all_reservas)} abas resultando em {qtd_final} linhas totais.")
        
        # 3. Tratamento inicial (limpeza e padronização externa)
        # Certifique-se que esta função trata erros caso colunas essenciais faltem
        if 'tratar_dataframe_consolidado' in globals():
            df_consolidado = tratar_dataframe_consolidado(df_consolidado)
        
        # 4. Adicionar/Regerar idReserva sequencial
        df_consolidado.reset_index(drop=True, inplace=True)
        df_consolidado['idReserva'] = df_consolidado.index + 1
        
        # 5. Formatar Datas
        for col in ['Início', 'Fim']:
            if col in df_consolidado.columns:
                # Converte para datetime forçando erros a virarem NaT
                df_consolidado[col] = pd.to_datetime(df_consolidado[col], dayfirst=True, errors='coerce')
                # Formata apenas o que for data válida
                df_consolidado[col] = df_consolidado[col].dt.strftime('%d/%m/%Y %H:%M')
                # Preenche vazios
                df_consolidado[col] = df_consolidado[col].fillna('')

        # 6. Reordenar colunas (idReserva primeiro, Apartamento em segundo)
        cols = list(df_consolidado.columns)
        if 'Apartamento' in cols:
            cols.insert(0, cols.pop(cols.index('Apartamento')))
            df_consolidado = df_consolidado[cols]

        cols = list(df_consolidado.columns)
        if 'idReserva' in cols:
            cols.insert(0, cols.pop(cols.index('idReserva')))
            df_consolidado = df_consolidado[cols]

        # 7. Timestamp
        # Define o fuso horário diretamente
        timestamp_agora = datetime.now(ZoneInfo('America/Recife'))
        df_consolidado['Última Atualização'] = timestamp_agora.strftime('%d/%m/%Y %H:%M:%S')

        # 8. Salvar
        salvar_df_no_gsheet(df_consolidado, "Reservas Consolidadas")
        add_log_func("✅ Sucesso: Reservas consolidadas salvas no Google Sheets.")
    else:
        add_log_func("Nenhuma reserva encontrada para consolidar (Listas vazias).")