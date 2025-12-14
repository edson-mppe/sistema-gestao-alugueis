import os
import streamlit as st
from pathlib import Path

# --- Caminhos ---
BASE_DIR = Path(__file__).parent.parent
CALENDARS_DIR = BASE_DIR / "calendars"
CREDENTIALS_FILE = BASE_DIR / "credentials.json" # Fallback para desenvolvimento local
CREDENTIALS_FILE_2 = BASE_DIR / "credentials2.json" # Outro arquivo de credenciais visto nos notebooks

# Garante que a pasta calendars existe
CALENDARS_DIR.mkdir(exist_ok=True)

# --- Google Sheets ---
# ID da planilha principal
SHEET_KEY = '1FqgTQAGebxvHUdVXI471HpAaXeXyCFdFWur7Pck0hLY'

# Mapeamento de Apartamentos para Abas do Google Sheets
APARTMENT_SHEET_MAP = {
    'c108': 'SM-C108',
    'd014': 'SM-D014',
    'cbl004': 'CBL004',
    'ap101': 'AP-101',
    'ap201': 'AP-201',
    'f216': 'SM-F216'
}

# --- URLs dos Calendários (OTAs) ---
# Extraído de 1_Baixar_calendarios_OTAs.ipynb
OTA_URLS = {
    'ap101': {
        'airbnb': "https://www.airbnb.com.br/calendar/ical/2710524.ics?s=bc7ceeb248c20334bd52ccf30acabc07",
        'booking': None # Não tem booking
    },
    'ap201': {
        'airbnb': "https://www.airbnb.com.br/calendar/ical/17246144.ics?s=466804a1ee4a8d8dbf117f6fc6bd1420",
        'booking': None # Não tem booking
    },
    'c108': {
        'airbnb': "https://www.airbnb.com.br/calendar/ical/1428938746995365808.ics?s=a66ee2191a8f4d5486cb078f9de34f88",
        'booking': "https://ical.booking.com/v1/export?t=359f0248-5265-4cde-82a8-c353156ad9be"
    },
    'cbl004': {
        'airbnb': "https://www.airbnb.com.br/calendar/ical/35679659.ics?s=bc17a6ccf8f6e21d4da62b155265b96c",
        'booking': "https://admin.booking.com/hotel/hoteladmin/ical.html?t=2e033af1-32e7-4f9c-aabe-afbfd5ece986"
    },
    'd014': {
        'airbnb': "https://www.airbnb.com.br/calendar/ical/1447417239837262921.ics?s=d025b75182c4a9391da767c47ee15692",
        'booking': "https://ical.booking.com/v1/export?t=d980d943-1019-4765-b8b9-670a2439cf46"
    },
    'f216': {
        'airbnb': "https://www.airbnb.com/calendar/ical/1470964694636236725.ics?s=95cf86fef315ea900c0ed146f223abf7",
        'booking': None # Não tem booking
    }
}

# --- Configurações de Cores para o Gráfico ---
COLORS = {
    'Booking': 'rgb(46, 137, 205)', 
    'Airbnb': 'rgb(255, 90, 95)',      
    'Direto': 'rgb(75, 181, 67)', 
    'Outro': 'rgb(255, 0, 0)'          
}

def get_google_credentials():
    """
    Tenta carregar credenciais do st.secrets, ou falha para arquivo local.
    Retorna um dicionário de credenciais ou None.
    """
    # 1. Tenta pegar do st.secrets (Produção/Streamlit Cloud)
    if "gcp_service_account" in st.secrets:
        return dict(st.secrets["gcp_service_account"])
    
    # 2. Tenta pegar de arquivo local (Desenvolvimento)
    # Tenta primeiro credentials2.json (que parecia ser o usado para escrita em alguns scripts)
    if CREDENTIALS_FILE_2.exists():
        return str(CREDENTIALS_FILE_2)
    
    if CREDENTIALS_FILE.exists():
        return str(CREDENTIALS_FILE)
        
    return None
