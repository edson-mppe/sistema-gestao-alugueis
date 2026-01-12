import streamlit as st
import pandas as pd
import os
import time
from datetime import datetime, timedelta
from src.config import OTA_URLS, APARTMENT_SHEET_MAP, CALENDARS_DIR
from src.data_loader import baixar_calendario_ota, atualizar_summaries_ical, save_dataframe_to_ical
from src.gsheets_api import baixar_dados_google_sheet, inserir_linha_google_sheet
from src.logic import merge_ical_files, verificar_inconsistencias, consolidar_e_salvar_reservas, ler_calendario_ics
from src.utils import get_holidays, parse_pt_date

# --- Step 1: Baixar Calendários das OTAs ---
def step_1_baixar_otas():
    print("\n--- PASSO 1: Baixando Calendários das OTAs ---")
    
    tasks = []
    
    for apt, sources in OTA_URLS.items():
        for source, url in sources.items():
            filename = f"{apt}_{source}.ics"
            tasks.append((url, filename))

    count = 0
    for url, filename in tasks:
        if baixar_calendario_ota(url, filename):
            atualizar_summaries_ical(filename)
            print(f"  [OK] {filename}")
            count += 1
        else:
            print(f"  [ERRO] Falha ao baixar {filename}")
            
    print(f"Passo 1 concluído: {count}/{len(tasks)} calendários baixados.")

# --- Step 2: Baixar Calendários do Google Sheets ---
def step_2_baixar_google_sheets():
    print("\n--- PASSO 2: Baixando Dados do Google Sheets ---")
    
    def formatar_dataframe_reservas(df):
        if df.empty: return df
        if 'Início' in df.columns:
            df['Início'] = df['Início'].apply(parse_pt_date)
        if 'Fim' in df.columns:
            df['Fim'] = df['Fim'].apply(parse_pt_date)
        return df

    for apt, tab_name in APARTMENT_SHEET_MAP.items():
        fname_short = f'{apt}_google.ics'
        try:
            df = baixar_dados_google_sheet(tab_name)
            if df is None or df.empty:
                print(f"  [AVISO] Sem dados para {apt} ({tab_name})")
                continue
            df = formatar_dataframe_reservas(df)
            save_dataframe_to_ical(df, fname_short)
            print(f"  [OK] calendars/{fname_short} gerado.")
        except Exception as e:
            print(f"  [ERRO] {apt}: {e}")

# --- Step 3: Juntar Calendários OTAs ---
def step_3_juntar_calendarios():
    print("\n--- PASSO 3: Juntando Calendários OTAs (Merge) ---")
    
    # 1. Merge OTAs (Booking + Airbnb)
    print("  3.1: Mesclando OTAs...")
    apt_configs = {apt: True for apt in OTA_URLS.keys()}
    
    for apt in apt_configs:
        fname_airbnb_short = f'{apt}_airbnb.ics'
        fname_booking_short = f'{apt}_booking.ics'
        fname_merged_short = f'{apt}_merged_booking_airbnb.ics'
        
        path_airbnb = os.path.join('calendars', fname_airbnb_short)
        path_booking = os.path.join('calendars', fname_booking_short)
        
        df_ab = pd.DataFrame()
        if os.path.exists(path_airbnb):
            df_ab = ler_calendario_ics(path_airbnb)
            if not df_ab.empty: df_ab['Origem'] = 'Airbnb'
        
        df_bk = pd.DataFrame()
        if os.path.exists(path_booking):
            df_bk = ler_calendario_ics(path_booking)
            if not df_bk.empty: df_bk['Origem'] = 'Booking'
            
        df_otas = pd.concat([df_ab, df_bk], ignore_index=True)
        if not df_otas.empty:
             save_dataframe_to_ical(df_otas, fname_merged_short)
             print(f"    [OK] {apt} merged OTA ({len(df_otas)} events)")
        else:
             print(f"    [AVISO] {apt} merged OTA empty")

    # 2. Merge OTA + Google
    print("  3.2: Mesclando OTA + Google...")
    for apt in apt_configs:
        fname_otas_short = f'{apt}_merged_booking_airbnb.ics'
        fname_google_short = f'{apt}_google.ics'
        fname_final_short = f'{apt}_merged_booking_airbnb_google.ics'
        
        path_otas = os.path.join('calendars', fname_otas_short)
        path_google = os.path.join('calendars', fname_google_short)
        
        if os.path.exists(path_otas) and os.path.exists(path_google):
             merge_ical_files(path_otas, path_google, fname_final_short)
             print(f"    [OK] {apt} Final Merge Created")
        else:
             print(f"    [SKIP] {apt} missing input files for final merge")

# --- Step 4: Verificar Inconsistências ---
def step_4_verificar_inconsistencias():
    print("\n--- PASSO 4: Verificando Inconsistências ---")
    inconsistencias_por_apt = {}
    
    for apt in APARTMENT_SHEET_MAP.keys():
        path_ota_merged = os.path.join('calendars', f'{apt}_merged_booking_airbnb.ics')
        path_google = os.path.join('calendars', f'{apt}_google.ics')
        
        if not (os.path.exists(path_ota_merged) and os.path.exists(path_google)):
            continue
            
        df_ota = ler_calendario_ics(path_ota_merged)
        df_google = ler_calendario_ics(path_google)
        
        if df_ota.empty: continue
        
        hoje = datetime.now()
        df_ota = df_ota[df_ota['Fim'] >= hoje]
        
        lista_apt = []
        for idx, row_ota in df_ota.iterrows():
            start_o = row_ota['Início']
            end_o = row_ota['Fim']
            
            has_overlap = False
            if not df_google.empty:
                overlaps = df_google[
                    (df_google['Início'] < end_o) & 
                    (df_google['Fim'] > start_o)
                ]
                if not overlaps.empty:
                    has_overlap = True
            
            if not has_overlap:
                rec = row_ota.to_dict()
                rec['Apartamento'] = apt
                lista_apt.append(rec)
                print(f"Inconsistência em {apt}: {rec}.")
        
        if lista_apt:
            inconsistencias_por_apt[apt] = lista_apt
    
    total_inc = sum(len(l) for l in inconsistencias_por_apt.values())
    print(f"  Encontradas {total_inc} inconsistências no total across {len(inconsistencias_por_apt)} apts.")
    
    return inconsistencias_por_apt

# --- Step 5: Atualizar Planilha Google ---
def step_5_atualizar_google_sheets(inconsistencias_dict):
    """
    Recebe um DICIONÁRIO { 'apt': [ {item_dict}, ... ] }
    Converte cada item_dict em uma lista de valores (linha) e insere.
    """
    print("\n--- PASSO 5: Atualizando Google Sheets ---")
    
    if not inconsistencias_dict:
        print("  Nada a atualizar (dicionário vazio).")
        return

    for apt, items in inconsistencias_dict.items():
        tab_name = APARTMENT_SHEET_MAP.get(apt)
        if not tab_name: 
            print(f"  [AVISO] {apt} não mapeado para uma aba do Google Sheets.")
            continue
        
        print(f"  Processando {apt} ({len(items)} itens)...")
        
        rows_to_insert = []
        for item in items:
            dt_inicio = item['Início'].strftime('%d/%m/%Y')
            dt_fim = item['Fim'].strftime('%d/%m/%Y')
            summary = item.get('Summary', 'Importado Auto')
            origem = item.get('Origem', 'OTA')
            
            row_data = [
                 dt_inicio, 
                 dt_fim, 
                 "", # Dias
                 "", # Pessoas
                 f"** IMPORTADO AUTOMATICO ** ({summary})", # Quem
                 summary, #origem, 
                 "", "", "", "", "", "", "", "", "", "", "", 
                 datetime.now().strftime('%d/%m/%Y %H:%M:%S') # Log
            ]
            
            rows_to_insert.append(row_data)
            
        if rows_to_insert:
            if inserir_linha_google_sheet(rows_to_insert, tab_name=tab_name):
                print(f"    [OK] Inserido lote de {len(rows_to_insert)} linhas.")
            else:
                print(f"    [ERRO] Falha ao inserir lote.")


def sincronizar_dados_completo():
    print("=== INICIANDO SINCRONIZAÇÃO COMPLETA ===")
    step_1_baixar_otas()
    step_2_baixar_google_sheets()
    step_3_juntar_calendarios()
    inconsistencias = step_4_verificar_inconsistencias()
    step_5_atualizar_google_sheets(inconsistencias)
    
    print("\n--- PASSO 6: Consolidando Reservas ---")
    def safe_log(msg):
        try:
            print(f"  {msg}")
        except UnicodeEncodeError:
            print(f"  {msg.encode('utf-8').decode('utf-8')}") # Attempt to print utf-8 if terminal supports, else it typically fails on cp1252. 
            # Better: ignore errors for console
            # print(f"  {msg.encode('ascii', 'ignore').decode()}")
    
    # Simple lambda approach that replaces unprintable chars
    consolidar_e_salvar_reservas(lambda x: print(f"  {str(x).encode('ascii', 'replace').decode()}"))
    
    print("\n=== SINCRONIZAÇÃO CONCLUÍDA ===")
