import requests
import os
from icalendar import Calendar, Event
import pandas as pd
from datetime import datetime
from src.config import CALENDARS_DIR
from src.utils import parse_pt_date

def baixar_calendario_ota(url, filename):
    """
    Baixa o arquivo .ics da URL fornecida e salva em CALENDARS_DIR.
    """
    if not url:
        return False
        
    filepath = CALENDARS_DIR / filename
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        with open(filepath, 'wb') as f:
            f.write(response.content)
        return True
    except Exception as e:
        print(f"Erro ao baixar {filename}: {e}")
        return False

def atualizar_summaries_ical(filename):
    """
    Padroniza os campos SUMMARY do arquivo .ics.
    """
    filepath = CALENDARS_DIR / filename
    regras_summary = {
        'CLOSED - Not available': 'Booking',
        'Airbnb (Not available)': 'Direto',
        'Reserved': 'Airbnb'
    }
    
    try:
        with open(filepath, 'rb') as f:
            cal = Calendar.from_ical(f.read())
            
        modificado = False
        for component in cal.walk('VEVENT'):
            summary_original = str(component.get('summary'))
            if summary_original in regras_summary:
                component['summary'] = regras_summary[summary_original]
                modificado = True
                
        if modificado:
            with open(filepath, 'wb') as f:
                f.write(cal.to_ical())
                
    except FileNotFoundError:
        print(f"Arquivo {filename} não encontrado para atualização de summary.")
    except Exception as e:
        print(f"Erro ao processar summary de {filename}: {e}")

def save_dataframe_to_ical(df, filename):
    """
    Converte um DataFrame de reservas em um arquivo .ics.
    Espera colunas: 'Início', 'Fim', 'Summary' (ou 'Origem').
    """
    filepath = CALENDARS_DIR / filename
    cal = Calendar()
    
    # Mapeamento de colunas se necessário
    col_inicio = 'Início' if 'Início' in df.columns else 'Start'
    col_fim = 'Fim' if 'Fim' in df.columns else 'End'
    col_summary = 'Summary' if 'Summary' in df.columns else 'Origem'
    
    for _, row in df.iterrows():
        event = Event()
        
        start_dt = row[col_inicio]
        end_dt = row[col_fim]
        summary = row.get(col_summary, 'Reserva')
        
        # Garante que são objetos datetime ou date
        if isinstance(start_dt, str):
            # Tenta parser customizado primeiro
            dt = parse_pt_date(start_dt)
            if pd.isna(dt):
                start_dt = pd.to_datetime(start_dt)
            else:
                start_dt = dt
                
        if isinstance(end_dt, str):
            dt = parse_pt_date(end_dt)
            if pd.isna(dt):
                end_dt = pd.to_datetime(end_dt)
            else:
                end_dt = dt
        
        # Pula se for NaT
        if pd.isna(start_dt) or pd.isna(end_dt):
            continue
            
        event.add('summary', summary)
        event.add('dtstart', start_dt)
        event.add('dtend', end_dt)
        event.add('dtstamp', datetime.now())
        
        cal.add_component(event)
        
    with open(filepath, 'wb') as f:
        f.write(cal.to_ical())
