import pandas as pd
from icalendar import Calendar, Event
from datetime import datetime, timedelta, date
import os
import plotly.express as px
import plotly.graph_objects as go
from src.config import CALENDARS_DIR, COLORS
from src.utils import get_holidays, parse_pt_date

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
        
        # Normaliza datas para datetime (remove timezone se houver, ou converte date para datetime)
        if isinstance(start, date) and not isinstance(start, datetime):
            start = datetime.combine(start, datetime.min.time())
        if isinstance(end, date) and not isinstance(end, datetime):
            end = datetime.combine(end, datetime.min.time())
            
        # Remove timezone info para comparação simples
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
    
    # Adiciona origem para rastreio (opcional, mas útil)
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
    from src.data_loader import save_dataframe_to_ical
    save_dataframe_to_ical(df_merged, output_filename)
    
    return df_merged

def verificar_inconsistencias(df_merged):
    """
    Verifica sobreposições de reservas no DataFrame mesclado.
    Retorna DataFrame com as inconsistências.
    """
    if df_merged.empty:
        return pd.DataFrame()
        
    inconsistencias = []
    
    # Ordena por data
    df = df_merged.sort_values('Início')
    
    for i in range(len(df)):
        for j in range(i + 1, len(df)):
            reserva1 = df.iloc[i]
            reserva2 = df.iloc[j]
            
            # Se a reserva 2 começa depois que a 1 termina, não há mais conflitos possíveis com a 1
            if reserva2['Início'] >= reserva1['Fim']:
                break
                
            # Se há sobreposição (e não são idênticas, pois drop_duplicates já rodou)
            # Sobreposição: Inicio1 < Fim2 AND Inicio2 < Fim1
            if (reserva1['Início'] < reserva2['Fim']) and (reserva2['Início'] < reserva1['Fim']):
                inconsistencias.append({
                    'Reserva 1': f"{reserva1['Summary']} ({reserva1['Início']} - {reserva1['Fim']})",
                    'Reserva 2': f"{reserva2['Summary']} ({reserva2['Início']} - {reserva2['Fim']})",
                    'Conflito': 'Sim',
                    'Data Detecção': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                
    return pd.DataFrame(inconsistencias)

def tratar_dataframe_consolidado(df):
    """
    Limpa e padroniza o DataFrame consolidado de todas as abas.
    """
    if df.empty:
        return df
        
    # Remove linhas vazias essenciais
    df = df.dropna(subset=['Início', 'Fim'])
    
    # Converte datas
    def parse_date_br(date_str):
        if not isinstance(date_str, str): return pd.NaT
        # Tenta formato DD/MM/YYYY HH:MM (vindo da planilha consolidada)
        try:
            return pd.to_datetime(date_str, format='%d/%m/%Y %H:%M')
        except:
            pass
        # Tenta formato português (DD-Mês.YY-Dia)
        dt = parse_pt_date(date_str)
        if pd.notna(dt):
            return dt
        # Tenta parsing genérico
        try:
            return pd.to_datetime(date_str, dayfirst=True)
        except:
            return pd.NaT

    # Se as colunas já não forem datetime (do gsheets vem como string)
    if df['Início'].dtype == object:
        df['Início'] = df['Início'].apply(parse_date_br)
    if df['Fim'].dtype == object:
        df['Fim'] = df['Fim'].apply(parse_date_br)
        
    # Remove linhas onde a data não pôde ser convertida (NaT)
    df = df.dropna(subset=['Início', 'Fim'])
        
    # Adiciona horários padrão se não tiverem (15h para Início, 11h para Fim)
    df['Início'] = df['Início'].apply(lambda x: x + timedelta(hours=15) if pd.notnull(x) and x.hour == 0 else x)
    df['Fim'] = df['Fim'].apply(lambda x: x + timedelta(hours=11) if pd.notnull(x) and x.hour == 0 else x)

    # Marca reservas passadas como 'Concluído'
    agora = datetime.now()
    if 'Status' not in df.columns:
        df['Status'] = ''
    df.loc[df['Fim'] < agora, 'Status'] = 'Concluído'
    
    # Garante que a coluna Origem exista para o gráfico
    if 'Origem' not in df.columns:
        df['Origem'] = 'Desconhecido'

    return df

def create_gantt_chart(df, is_mobile=False):
    """
    Gera o gráfico de Gantt com as reservas (baseado no notebook).
    """
    if df.empty:
        return None
        
    # --- Definições de Data ---
    hoje = pd.to_datetime('today').normalize()
    agora = pd.to_datetime('now')
    
    # Zoom Fixo: 10 dias para mobile, 20 dias para desktop
    days_back = 2
    days_forward = 8 if is_mobile else 18
    
    zoom_inicio = hoje - pd.Timedelta(days=days_back)
    zoom_fim = hoje + pd.Timedelta(days=days_forward)

    # --- Cores ---
    colors = {
        'Booking': 'rgba(46, 137, 205, 0.8)', 
        'Airbnb': 'rgba(255, 90, 95, 0.8)',      
        'Direto': 'rgba(75, 181, 67, 0.8)', 
        'Outro': 'rgba(255, 0, 0, 0.8)'          
    }

    # --- Preparação dos Dados ---
    try:
        df_grafico = df.copy()
        df_grafico['Início'] = pd.to_datetime(df_grafico['Início'], errors='coerce')
        df_grafico['Fim'] = pd.to_datetime(df_grafico['Fim'], errors='coerce')
        df_grafico = df_grafico.dropna(subset=['Início', 'Fim'])
    except Exception as e:
        return None

    # Filtra apenas reservas não concluídas
    if 'Status' in df_grafico.columns:
        df_grafico = df_grafico[df_grafico['Status'] != 'Concluído']
    else:
        # Fallback: se não houver coluna Status, filtra por data
        df_grafico = df_grafico[df_grafico['Fim'] >= hoje]
    
    if df_grafico.empty: 
        return None

    df_grafico['Texto_Barra'] = (
        df_grafico['Início'].dt.day.astype(str) + '-' + df_grafico['Fim'].dt.day.astype(str)
    )
    ultima_data_reserva = df_grafico['Fim'].max()
    num_apartamentos = len(df_grafico['Apartamento'].unique())
    
    # Altura dinâmica ajustada para mobile (barras mais altas)
    base_height = 400 if is_mobile else 300
    per_apt_height = 80 if is_mobile else 50
    altura_dinamica = base_height + (num_apartamentos * per_apt_height)

    # --- CRIAÇÃO DO GRÁFICO ---
    fig = px.timeline(df_grafico, x_start="Início", x_end="Fim", y="Apartamento",
                      color="Origem", title="Mapa de Ocupação", color_discrete_map=colors,
                      text="Texto_Barra")
    
    fig.update_traces(textposition='inside', textfont=dict(color='black', size=11))

    # --- FUNDO ALTERNADO ---
    data_inicio_fundo = zoom_inicio
    data_fim_fundo = max(zoom_fim, ultima_data_reserva) + pd.Timedelta(days=5)
    dias_totais = (data_fim_fundo - data_inicio_fundo).days + 1
    
    COR_FERIADO, COR_DOMINGO, COR_SABADO, COR_DIA_UTIL = "#FFEBEE", "#E0E0E0", "#F5F5F5", "white"
    set_datas_feriados = set()
    anos = []
    df_f = pd.DataFrame()
    try:
        anos = sorted(list(set(df_grafico['Início'].dt.year.tolist() + df_grafico['Fim'].dt.year.tolist())))
        if anos:
            df_f = get_holidays(anos)
            for _, r in df_f.iterrows():
                d = datetime.strptime(r['Data'], '%d/%m/%Y').date() if isinstance(r['Data'], str) else r['Data'].date()
                set_datas_feriados.add(d)
    except: 
        pass

    for i in range(dias_totais):
        dia = data_inicio_fundo + pd.Timedelta(days=i)
        cor = COR_DIA_UTIL
        if dia.date() in set_datas_feriados: 
            cor = COR_FERIADO
        elif dia.weekday() == 6: 
            cor = COR_DOMINGO
        elif dia.weekday() == 5: 
            cor = COR_SABADO
        
        if cor != "white":
            fig.add_shape(type="rect", x0=dia, y0=0, x1=dia + pd.Timedelta(days=1), y1=1,
                          xref="x", yref="paper", fillcolor=cor, layer="below", line_width=0)
        
        if dia.day == 1: # Mês
            nome_mes = dia.strftime('%B').capitalize()
            ano_mes = dia.strftime('%Y')
            fig.add_annotation(x=dia, y=1, yref="paper", text=f"<b>{nome_mes} {ano_mes}</b>",
                               showarrow=False, xanchor="left", yanchor="bottom", yshift=45, font=dict(color="black", size=14))
            fig.add_shape(type="line", x0=dia, y0=0, x1=dia, y1=1, xref="x", yref="paper", line=dict(color="black", width=1.5), opacity=0.3)

    # --- Traço Fantasma ---
    fig.add_trace(go.Scatter(x=[zoom_inicio, zoom_fim], y=[df_grafico['Apartamento'].iloc[0]]*2, 
                   mode='markers', xaxis='x2', opacity=0, showlegend=False, hoverinfo='skip'))

    # --- Linha Agora ---
    x_agora = agora.to_pydatetime()
    fig.add_shape(type="line", x0=x_agora, y0=0, x1=x_agora, y1=1, xref="x", yref="paper", line=dict(color="black", width=1.5, dash="dash"))
    fig.add_annotation(x=x_agora, y=0, yref="paper", text="Agora", showarrow=False, font=dict(color="black", size=10, weight="bold"), xanchor="right", yanchor="bottom")

    # --- Feriados (Texto) ---
    try:
        if anos and not df_f.empty:
            for _, r in df_f.iterrows():
                dt = datetime.strptime(r['Data'], '%d/%m/%Y') if isinstance(r['Data'], str) else r['Data']
                if zoom_inicio <= dt <= ultima_data_reserva:
                    dt12 = dt.replace(hour=12, minute=0, second=0)
                    fig.add_shape(type="line", x0=dt12, y0=0, x1=dt12, y1=1, xref="x", yref="paper", line=dict(color="gray", width=1, dash="dot"), opacity=0.4)
                    fig.add_annotation(x=dt12, y=1, yref="paper", text=r['Feriado'], showarrow=False, xanchor="left", yanchor="top", textangle=-90, font=dict(color="#555555", size=9))
    except: 
        pass

    # --- Layout ---
    ordem_apartamentos = ['AP-101', 'AP-201', 'CBL004', 'SM-C108', 'SM-D014']
    
    # Configurações condicionais para Mobile vs Desktop
    margin_l = 10 if is_mobile else 50
    show_y_labels = not is_mobile
    
    fig.update_layout(
        title_text="Mapa de Reservas", 
        height=altura_dinamica, 
        xaxis_rangeslider_visible=False, 
        yaxis_autorange='reversed', 
        hovermode='x unified', 
        barcornerradius=5, 
        plot_bgcolor='white',
        dragmode='pan', 
        margin=dict(t=100, b=40, l=margin_l, r=20), 
        xaxis=dict(
            title="", 
            side="bottom", 
            showgrid=True, 
            gridcolor="#E5E5E5", 
            showticklabels=False, 
            dtick=86400000, 
            range=[zoom_inicio, zoom_fim],
            fixedrange=False 
        ),
        xaxis2=dict(
            title="", 
            side="top", 
            overlaying="x", 
            showgrid=False, 
            matches="x", 
            tickformat='<b>%d</b><br>%a', 
            tickangle=0, 
            dtick=86400000, 
            ticklabelmode="period",
            fixedrange=False
        ),
        yaxis=dict(
            title="", 
            showgrid=True, 
            gridcolor="#E5E5E5", 
            categoryorder='array', 
            categoryarray=ordem_apartamentos,
            fixedrange=True,
            showticklabels=show_y_labels # Oculta labels no mobile
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.1, xanchor="right", x=1)
    )
    
    # Adiciona nomes dos apartamentos dentro do gráfico no modo mobile
    if is_mobile:
        for apt in ordem_apartamentos:
            fig.add_annotation(
                x=0, # Início do gráfico (esquerda)
                y=apt,
                xref="paper",
                yref="y",
                text=f"<b>{apt}</b>",
                showarrow=False,
                xanchor="left",
                yanchor="bottom", # Fica um pouco acima da linha
                yshift=5, # Leve ajuste para cima
                xshift=5, # Leve ajuste para direita da borda
                font=dict(size=12, color="black"),
                bgcolor="rgba(255, 255, 255, 0.7)", # Fundo semi-transparente para leitura
                bordercolor="rgba(0,0,0,0.1)",
                borderwidth=1,
                borderpad=2
            )
    
    return fig

def verificar_disponibilidade(df, data_inicio, data_fim):
    """
    Verifica quais apartamentos estão livres e ocupados no intervalo.
    """
    if df is None or df.empty: return [], []
    
    dt_inicio = pd.to_datetime(data_inicio)
    dt_fim = pd.to_datetime(data_fim)
    
    df_temp = df.copy()
    df_temp['Início'] = pd.to_datetime(df_temp['Início'], errors='coerce', dayfirst=True)
    df_temp['Fim'] = pd.to_datetime(df_temp['Fim'], errors='coerce', dayfirst=True)
    df_temp = df_temp.dropna(subset=['Início', 'Fim'])
    
    todos_aptos = sorted(df_temp['Apartamento'].unique().tolist())
    
    # Lógica de conflito: (Inicio_Reserva < Fim_Busca) & (Fim_Reserva > Inicio_Busca)
    conflitos = df_temp[(df_temp['Início'] < dt_fim) & (df_temp['Fim'] > dt_inicio)]
    
    aptos_ocupados = sorted(list(set(conflitos['Apartamento'].unique())))
    aptos_livres = [ap for ap in todos_aptos if ap not in aptos_ocupados]
    
    return aptos_livres, aptos_ocupados
