import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, time, date, timedelta
import os
from icalendar import Calendar
from zoneinfo import ZoneInfo
from src.gsheets_api import salvar_df_no_gsheet, ler_abas_planilha
from src.config import OTA_URLS, APARTMENT_SHEET_MAP, CALENDARS_DIR

# Tenta importar utilitários, com fallback se não existirem
try:
    from src.utils import get_holidays, parse_pt_date
except ImportError:
    def get_holidays(years): return pd.DataFrame(columns=['Data', 'Feriado'])
    def parse_pt_date(d): return pd.NaT

'''# Mapa de meses para parse de datas em português
MESES_MAP_REPLACE = {
    'jan': '01', 'fev': '02', 'mar': '03', 'abr': '04', 
    'mai': '05', 'jun': '06', 'jul': '07', 'ago': '08', 
    'set': '09', 'out': '10', 'nov': '11', 'dez': '12'
}'''

# --- 1. Funções de Backend (ETL e Arquivos) ---

def ler_calendario_ics(filepath):
    """
    Lê um arquivo .ics e retorna um DataFrame.
    """
    if not os.path.exists(filepath):
        return pd.DataFrame()

    with open(filepath, 'rb') as f:
        try:
            cal = Calendar.from_ical(f.read())
        except Exception:
            return pd.DataFrame()

    events = []
    for component in cal.walk('VEVENT'):
        start = component.get('dtstart').dt
        end = component.get('dtend').dt
        summary = str(component.get('summary'))
        
        # Normaliza datas para datetime
        if isinstance(start, date) and not isinstance(start, datetime):
            start = datetime.combine(start, datetime.min.time())
        if isinstance(end, date) and not isinstance(end, datetime):
            end = datetime.combine(end, datetime.min.time())
            
        # Remove timezone info
        start = start.replace(tzinfo=None)
        end = end.replace(tzinfo=None)

        events.append({
            'Início': start,
            'Fim': end,
            'Summary': summary
        })

    return pd.DataFrame(events)

def merge_ical_files(file_ota, file_google, output_filename):
    """
    Mescla calendário OTA e Google, removendo duplicatas e filtrando datas passadas.
    Salva o resultado em output_filename.
    """
    df_ota = ler_calendario_ics(file_ota)
    df_google = ler_calendario_ics(file_google)
    
    # Adiciona origem para rastreio
    if not df_ota.empty:
        df_ota['Origem'] = 'OTA'
    if not df_google.empty:
        df_google['Origem'] = 'Google'
        
    df_merged = pd.concat([df_ota, df_google], ignore_index=True)
    
    if df_merged.empty:
        return pd.DataFrame()
        
    # Filtra passadas e muito futuras (> 1 ano)
    agora = datetime.now().replace(tzinfo=None)
    um_ano_depois = agora + timedelta(days=365)
    
    df_merged = df_merged[
        (df_merged['Fim'] >= agora) & 
        (df_merged['Início'] <= um_ano_depois)
    ]
    
    # Remove duplicatas exatas de horário
    df_merged = df_merged.drop_duplicates(subset=['Início', 'Fim'], keep='first')
    
    # Salva o merged
    try:
        from src.data_loader import save_dataframe_to_ical
        save_dataframe_to_ical(df_merged, output_filename)
    except ImportError:
        pass
    
    return df_merged

def verificar_inconsistencias(df_merged):
    """
    Verifica sobreposições de reservas no DataFrame mesclado.
    """
    if df_merged.empty:
        return pd.DataFrame()
        
    inconsistencias = []
    df = df_merged.sort_values('Início')
    
    for i in range(len(df)):
        for j in range(i + 1, len(df)):
            reserva1 = df.iloc[i]
            reserva2 = df.iloc[j]
            
            if reserva2['Início'] >= reserva1['Fim']:
                break
                
            if (reserva1['Início'] < reserva2['Fim']) and (reserva2['Início'] < reserva1['Fim']):
                inconsistencias.append({
                    'Reserva 1': f"{reserva1['Summary']} ({reserva1['Início']} - {reserva1['Fim']})",
                    'Reserva 2': f"{reserva2['Summary']} ({reserva2['Início']} - {reserva2['Fim']})",
                    'Conflito': 'Sim',
                    'Data Detecção': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                
    return pd.DataFrame(inconsistencias)


def verificar_disponibilidade(df, data_inicio, data_fim):
    """
    Verifica quais apartamentos estão livres e ocupados no intervalo.
    """
    if df is None or df.empty: return [], []
    
    dt_inicio = pd.to_datetime(data_inicio)
    dt_fim = pd.to_datetime(data_fim)
    
    df_temp = df.copy()
    if df_temp['Início'].dtype == object:
        df_temp['Início'] = pd.to_datetime(df_temp['Início'], errors='coerce')
    if df_temp['Fim'].dtype == object:
        df_temp['Fim'] = pd.to_datetime(df_temp['Fim'], errors='coerce')
        
    df_temp = df_temp.dropna(subset=['Início', 'Fim'])
    todos_aptos = sorted(df_temp['Apartamento'].unique().tolist())
    
    conflitos = df_temp[(df_temp['Início'] < dt_fim) & (df_temp['Fim'] > dt_inicio)]
    aptos_ocupados = sorted(list(set(conflitos['Apartamento'].unique())))
    aptos_livres = [ap for ap in todos_aptos if ap not in aptos_ocupados]
    
    return aptos_livres, aptos_ocupados


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

# --- 2. Função de Gráfico (Frontend Logic) ---

def create_gantt_chart(df_grafico, is_mobile=False):
    """
    Gera o gráfico de Gantt (Timeline) com otimizações visuais para Mobile.
    Agora destaca feriados (com nome na vertical), sábados e domingos.
    """
    if df_grafico is None or df_grafico.empty:
        return None

    df = df_grafico.copy()
    
    for col in ['Início', 'Fim']:
        if df[col].dtype == object:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    df = df.dropna(subset=['Início', 'Fim'])

    hoje = pd.to_datetime('today').normalize()
    agora = pd.to_datetime('now')
    
    df = df[df['Fim'] >= hoje]
    if df.empty: return None

    # --- CONFIGURAÇÕES VISUAIS ---
    if is_mobile:
        # --- Configurações Mobile ---
        row_height = 30       # Altura compacta
        bar_gap = 0.6         # Barras finas
        font_size = 10
        margin_l = 0          
        margin_r = 0          
        margin_t = 130        # Espaço extra no topo para legendas e datas
        base_height = 200     
        tick_angle = 0        
        days_forward = 10     
        show_y_labels = False 
        legend_y = 1.25       # Legenda bem acima
    else:
        # --- Configurações Desktop ---
        row_height = 50
        bar_gap = 0.15        
        font_size = 12
        margin_l = 10
        margin_r = 10
        margin_t = 140        
        base_height = 300
        tick_angle = 0
        days_forward = 20
        show_y_labels = True
        legend_y = 1.15       

    df['Texto_Barra'] = df['Início'].dt.day.astype(str) + '-' + df['Fim'].dt.day.astype(str)
    num_apartamentos = len(df['Apartamento'].unique())
    altura_dinamica = base_height + (num_apartamentos * row_height)
    
    colors = {
        'Booking': 'rgba(46, 137, 205, 0.8)', 
        'Airbnb': 'rgba(255, 90, 95, 0.8)',      
        'Direto': 'rgba(75, 181, 67, 0.8)', 
        'Outro': 'rgba(255, 0, 0, 0.8)'          
    }

    # Range inicial do eixo X (apenas para visualização inicial)
    zoom_inicio = hoje - pd.Timedelta(days=2)
    zoom_fim = hoje + pd.Timedelta(days=days_forward)
    ordem_apartamentos = sorted(df['Apartamento'].unique())

    # --- CRIAÇÃO DO GRÁFICO ---
    fig = px.timeline(
        df, 
        x_start="Início", 
        x_end="Fim", 
        y="Apartamento",
        color="Origem", 
        title="Mapa de Reservas" if not is_mobile else "",
        color_discrete_map=colors,
        text="Texto_Barra"
    )
    
    fig.update_traces(
        textposition='inside', 
        textfont=dict(color='black', size=font_size)
    )

    # --- Fundo e Elementos Visuais ---
    x_agora = agora.to_pydatetime()
    fig.add_shape(
        type="line", x0=x_agora, y0=0, x1=x_agora, y1=1, 
        xref="x", yref="paper", 
        line=dict(color="red", width=2, dash="dot")
    )
    
    # --- PREPARAÇÃO DOS FERIADOS E FUNDO ---
    
    # 1. Definir até onde vamos pintar o fundo (180 dias ou +30 dias após última reserva)
    data_inicio_fundo = zoom_inicio
    data_fim_fundo = max(hoje + pd.Timedelta(days=180), df['Fim'].max() + pd.Timedelta(days=30))
    dias_totais = (data_fim_fundo - data_inicio_fundo).days + 1
    
    # 2. Buscar feriados e mapear nomes
    anos_feriados = list(range(data_inicio_fundo.year, data_fim_fundo.year + 2))
    df_feriados = get_holidays(years=anos_feriados)
    
    # Cria um dicionário (data -> nome) para busca e exibição
    dict_feriados = {}
    if not df_feriados.empty and 'Data' in df_feriados.columns:
        # A Data vem como string 'dd/mm/yyyy' do utils.py, precisamos converter para date object
        for idx, row in df_feriados.iterrows():
            try:
                d_obj = datetime.strptime(row['Data'], '%d/%m/%Y').date()
                dict_feriados[d_obj] = row['Feriado']
            except (ValueError, TypeError):
                pass

    # 3. Cores
    COR_DOMINGO = "#E0E0E0"
    COR_SABADO = "#F5F5F5"
    COR_FERIADO = "#FFCDD2" # Vermelho claro/pastel
    
    # 4. Loop de renderização (Percorre o período estendido)
    for i in range(dias_totais): 
        dia = data_inicio_fundo + pd.Timedelta(days=i)
        dia_date = dia.date()
        
        cor = None
        holiday_name = None
        
        # Lógica de prioridade: Feriado > Domingo > Sábado
        if dia_date in dict_feriados:
            cor = COR_FERIADO
            holiday_name = dict_feriados[dia_date]
        elif dia.weekday() == 6: 
            cor = COR_DOMINGO
        elif dia.weekday() == 5: 
            cor = COR_SABADO
        
        if cor:
            # Desenha o fundo
            fig.add_shape(type="rect", x0=dia, y0=0, x1=dia + pd.Timedelta(days=1), y1=1,
                          xref="x", yref="paper", fillcolor=cor, layer="below", line_width=0)
            
            # Se for feriado, escreve o nome na vertical
            if holiday_name:
                fig.add_annotation(
                    x=dia + pd.Timedelta(hours=12), # Centro do dia
                    y=0.5, # Centro da altura
                    xref="x",
                    yref="paper",
                    text=holiday_name.upper(), # Uppercase para ficar mais legível
                    showarrow=False,
                    textangle=-90, # Texto na vertical (lendo de cima para baixo)
                    xanchor="center",
                    yanchor="middle",
                    font=dict(size=10, color="rgba(0, 0, 0, 0.4)") # Cinza translúcido discreto
                )
        
        # Linha vertical separadora de meses e Nome do Mês
        if dia.day == 1:
            nome_mes = dia.strftime('%b').capitalize()
            fig.add_annotation(
                x=dia, y=1, yref="paper", text=f"<b>{nome_mes}</b>",
                showarrow=False, xanchor="left", yanchor="bottom", 
                yshift=40,
                font=dict(color="black", size=10)
            )
            fig.add_shape(type="line", x0=dia, y0=0, x1=dia, y1=1, xref="x", yref="paper", line=dict(color="black", width=1), opacity=0.3)

    # --- Layout ---
    fig.update_layout(
        title_text="Mapa de Reservas" if not is_mobile else "", 
        height=altura_dinamica, 
        bargap=bar_gap, 
        xaxis_rangeslider_visible=False, 
        yaxis_autorange='reversed', 
        hovermode='x unified', 
        barcornerradius=5, 
        plot_bgcolor='white',
        dragmode='pan', 
        margin=dict(t=margin_t, b=20, l=margin_l, r=margin_r), 
        
        # --- Configuração do Eixo X (No Topo) ---
        xaxis=dict(
            title="", 
            side="top", 
            showgrid=True, 
            gridcolor="#E5E5E5", 
            tickformat='<b>%d</b><br>%a', 
            showticklabels=True, 
            tickangle=tick_angle,
            dtick=86400000, 
            ticklabelmode="period", # <--- ADICIONADO: Centraliza o label no período do dia
            range=[zoom_inicio, zoom_fim],
            fixedrange=False 
        ),
        
        # Configuração do Eixo Y
        yaxis=dict(
            title="", 
            showgrid=True, 
            gridcolor="#E5E5E5", 
            categoryorder='array', 
            categoryarray=ordem_apartamentos,
            fixedrange=True,
            showticklabels=show_y_labels
        ),
        legend=dict(orientation="h", yanchor="bottom", y=legend_y, xanchor="right", x=1)
    )
    
    # Adiciona nomes dos apartamentos dentro do gráfico no modo mobile
    if is_mobile:
        for apt in ordem_apartamentos:
            fig.add_annotation(
                x=0,
                y=apt,
                xref="paper",
                yref="y",
                text=f"<b>{apt}</b>",
                showarrow=False,
                xanchor="left",
                yanchor="bottom", 
                yshift=5, 
                xshift=5, 
                font=dict(size=12, color="black"),
                bgcolor="rgba(255, 255, 255, 0.8)",
                bordercolor="rgba(0,0,0,0.1)",
                borderwidth=1,
                borderpad=2
            )
    
    return fig