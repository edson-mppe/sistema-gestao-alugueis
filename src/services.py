import streamlit as st
import pandas as pd
from src.config import OTA_URLS, APARTMENT_SHEET_MAP, CALENDARS_DIR
from src.data_loader import baixar_calendario_ota, atualizar_summaries_ical, save_dataframe_to_ical
from src.gsheets_api import baixar_dados_google_sheet, inserir_linha_google_sheet, consolidar_e_salvar_reservas
from src.logic import merge_ical_files, verificar_inconsistencias
from src.utils import get_holidays
import os




def sincronizar_dados_completo():
    """
    Executa todo o pipeline de sincronização:
    1. Baixa calendários OTAs.
    2. Baixa dados do Google Sheets e converte para ICS.
    3. Mescla calendários.
    4. Verifica inconsistências e reporta.
    5. Consolida todas as reservas em uma aba mestre.
    """
    log = []
    
    def add_log(msg):
        log.append(msg)
        print(msg) # Para debug no terminal

    add_log("Iniciando sincronização...")
    
    # Garante diretório
    if not os.path.exists(CALENDARS_DIR):
        os.makedirs(CALENDARS_DIR)

    # 1. Processar cada apartamento
    for apt, urls in OTA_URLS.items():
        add_log(f"--- Processando {apt} ---")
        
        # A. Baixar OTAs
        for ota, url in urls.items():
            if url:
                filename = f"{apt}_{ota}.ics"
                if baixar_calendario_ota(url, filename):
                    atualizar_summaries_ical(filename)
                    add_log(f"  {ota} baixado.")
                else:
                    add_log(f"  Erro ao baixar {ota}.")
        
        # B. Baixar Google Sheet do Apartamento
        tab_name = APARTMENT_SHEET_MAP.get(apt)
        if tab_name:
            df_gs = baixar_dados_google_sheet(tab_name)
            if not df_gs.empty:
                filename_gs = f"{apt}_google.ics"
                save_dataframe_to_ical(df_gs, filename_gs)
                add_log(f"  Google Sheet ({tab_name}) baixado e convertido.")
            else:
                add_log(f"  Google Sheet ({tab_name}) vazio ou erro.")
        
        # C. Mesclar
        # Ajuste de caminhos para usar os.path.join para compatibilidade
        file_airbnb = os.path.join(CALENDARS_DIR, f"{apt}_airbnb.ics")
        file_booking = os.path.join(CALENDARS_DIR, f"{apt}_booking.ics")
        file_google = os.path.join(CALENDARS_DIR, f"{apt}_google.ics")
        file_merged = os.path.join(CALENDARS_DIR, f"{apt}_merged.ics")
        
        # Merge Final (OTA + Google)
        # Verifica se pelo menos os arquivos básicos existem
        if os.path.exists(file_airbnb) and os.path.exists(file_google):
            # Nota: merge_ical_files deve ser capaz de lidar com a lógica de merge
            df_final = merge_ical_files(file_airbnb, file_google, file_merged)
            add_log(f"  Calendários mesclados em {file_merged}.")
            
            # D. Verificar Inconsistências
            df_incons = verificar_inconsistencias(df_final)
            if not df_incons.empty:
                add_log(f"  {len(df_incons)} inconsistências encontradas!")
                # Salvar na planilha de inconsistências
                for _, row in df_incons.iterrows():
                    inserir_linha_google_sheet(row.tolist(), "Inconsistências")
            else:
                add_log("  Nenhuma inconsistência encontrada.")
                
    # 2. Consolidar Tudo (Chamada da Nova Função)
    consolidar_e_salvar_reservas(add_log)
        
    return log

