import pandas as pd
import os
import time
from datetime import datetime, timedelta
from src.config import OTA_URLS, APARTMENT_SHEET_MAP, SHEET_KEY
from src.data_loader import baixar_calendario_ota, atualizar_summaries_ical, save_dataframe_to_ical
from src.gsheets_api import baixar_dados_google_sheet, inserir_linha_google_sheet
from src.logic import merge_ical_files, ler_calendario_ics
from src.utils import parse_pt_date

# --- Step 1: Baixar Calendários das OTAs ---
def step_1_baixar_otas():
    print("\n--- PASSO 1: Baixando Calendários das OTAs ---")
    
    # Flat list of all calendars to download
    # OTA_URLS structure: {'c108': {'airbnb': 'url', 'booking': 'url'}, ...}
    
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
            df['Início'] = df['Início'].apply(lambda x: x + timedelta(hours=15) if pd.notnull(x) and x.time() == datetime.min.time() else x)
        if 'Fim' in df.columns:
            df['Fim'] = df['Fim'].apply(parse_pt_date)
            df['Fim'] = df['Fim'].apply(lambda x: x + timedelta(hours=11) if pd.notnull(x) and x.time() == datetime.min.time() else x)
        return df

    for apt, tab_name in APARTMENT_SHEET_MAP.items():
        fname_short = f'{apt}_google.ics'
        try:
            df = baixar_dados_google_sheet(tab_name)
            if df is None or df.empty:
                print(f"  [AVISO] Sem dados para {apt} ({tab_name})")
                continue
            df = formatar_dataframe_reservas(df)
            # data_loader.save_dataframe_to_ical prepends CALENDARS_DIR
            save_dataframe_to_ical(df, fname_short)
            print(f"  [OK] calendars/{fname_short} gerado.")
        except Exception as e:
            print(f"  [ERRO] {apt}: {e}")

# --- Step 3: Juntar Calendários ---
def step_3_juntar_calendarios():
    print("\n--- PASSO 3: Juntando Calendários (Merge) ---")
    
    # 1. Merge OTAs (Booking + Airbnb)
    print("  3.1: Mesclando OTAs...")
    apt_configs = {apt: True for apt in OTA_URLS.keys()}
    
    for apt in apt_configs:
        fname_airbnb_short = f'{apt}_airbnb.ics'
        fname_booking_short = f'{apt}_booking.ics'
        fname_merged_short = f'{apt}_merged_booking_airbnb.ics'
        
        path_airbnb = os.path.join('calendars', fname_airbnb_short)
        path_booking = os.path.join('calendars', fname_booking_short)
        
        # Merge simples (Concat)
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
        path_final = os.path.join('calendars', fname_final_short)
        
        if os.path.exists(path_otas) and os.path.exists(path_google):
             # merge_ical_files expects full paths for input, and full path for output?
             # Let's check src.logic.merge_ical_files
             # It calls ler_calendario_ics(file_ota) -> needs full path
             # It calls save_dataframe_to_ical(df, output_filename) -> this IMPORTED function inside logic might be modifying path?
             # logic.py imports save_dataframe_to_ical from data_loader.
             # So logic.merge_ical_files(..., output_filename) calls save_dataframe_to_ical(..., output_filename).
             # save_dataframe_to_ical prepends CALENDARS_DIR.
             # SO output_filename PASSED to merge_ical_files must be SHORT name.
             
             merge_ical_files(path_otas, path_google, fname_final_short)
             print(f"    [OK] {apt} Final Merge Created")
        else:
             print(f"    [SKIP] {apt} missing input files for final merge")

# --- Step 4: Verificar Inconsistências ---
def step_4_verificar_inconsistencias():
    print("\n--- PASSO 4: Verificando Inconsistências ---")
    inconsistencias_total = []
    
    for apt in APARTMENT_SHEET_MAP.keys():
        path_ota_merged = os.path.join('calendars', f'{apt}_merged_booking_airbnb_top.ics') 
        # Wait, step 3.1 creates {apt}_merged_booking_airbnb.ics.
        path_ota_merged = os.path.join('calendars', f'{apt}_merged_booking_airbnb.ics')
        path_google = os.path.join('calendars', f'{apt}_google.ics')
        
        if not (os.path.exists(path_ota_merged) and os.path.exists(path_google)):
            continue
            
        df_ota = ler_calendario_ics(path_ota_merged)
        df_google = ler_calendario_ics(path_google)
        
        if df_ota.empty: continue
        
        hoje = datetime.now()
        df_ota = df_ota[df_ota['Fim'] >= hoje]
        
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
                inconsistencias_total.append(rec)
    
    print(f"  Encontradas {len(inconsistencias_total)} inconsistências.")
    return inconsistencias_total

# --- Step 5: Atualizar Planilha Google ---
def step_5_atualizar_google_sheets(inconsistencias):
    print("\n--- PASSO 5: Atualizando Google Sheets ---")
    
    if not inconsistencias:
        print("  Nada a atualizar.")
        return

    # Group by apartment
    from collections import defaultdict
    grouped = defaultdict(list)
    for item in inconsistencias:
        grouped[item['Apartamento']].append(item)
        
    for apt, items in grouped.items():
        tab_name = APARTMENT_SHEET_MAP.get(apt)
        if not tab_name: continue
        
        print(f"  Processando {apt} ({len(items)} itens)...")
        
        for item in items:
            # Prepare row for Google Sheet
            # Format must match the columns in the sheet. 
            # Based on Notebook 5: [['14/12/2025', '15/12/2025', '', '', '**SINCRONIZAÇÃO...', 'Airbnb', ...]]
            # We need to be careful with column order.
            # Assuming standard columns: Início, Fim, Status, Quem, Origem...
            # We will use a safe generic append or try to match the Notebook 5 structure precisely if possible.
            # Notebook 5 used `inserir_linha_google_sheet`.
            
            dt_inicio = item['Início'].strftime('%d/%m/%Y')
            dt_fim = item['Fim'].strftime('%d/%m/%Y')
            summary = item.get('Summary', 'Importado Auto')
            origem = item.get('Origem', 'OTA')
            
            # Construct row data matching the spreadsheet columns roughly
            # [Início, Fim, Status, Quem, Origem, ...]
            # Using placeholders for unknown cols
            
            # NOTE: Spreadsheet structure is specific.
            # col 0: Início
            # col 1: Fim
            # col 2: Dias (Formula)
            # col 3: Pessoas
            # col 4: Quem -> "** NOTIFICACAO **"
            # col 5: Origem -> summary
            # ...
            
            row_data = [
                 dt_inicio, 
                 dt_fim, 
                 "", # Dias
                 "", # Pessoas
                 f"** IMPORTADO AUTOMATICO ** ({summary})", # Quem
                 origem, 
                 "", "", "", "", "", "", "", "", "", "", "", 
                 datetime.now().strftime('%d/%m/%Y %H:%M:%S') # Log
            ]
            
            # The function expects a list of lists if we modify it or just a list?
            # src.gsheets_api.inserir_linha_google_sheet takes `dados_linha` (list of values).
            # And it wraps it in a list inside: `for l in linha_dados: worksheet.insert_row(l...)` if passed a list of lists?
            # Reading source: `if not isinstance(linha_dados, list): ... for l in linha_dados: ...`
            # Wait, the source says: `for l in linha_dados: worksheet.insert_row(l...)`. 
            # This implies `linha_dados` should be a LIST OF LISTS (rows).
            
            try:
                inserir_linha_google_sheet([row_data], tab_name=tab_name)
                print(f"    Inserido: {dt_inicio} - {dt_fim}")
                # Rate limit safety
                time.sleep(1.5)
            except Exception as e:
                print(f"    Erro ao inserir: {e}")

def main():
    print("=== INICIANDO SINCRONIZAÇÃO COMPLETA ===")
    step_1_baixar_otas()
    step_2_baixar_google_sheets()
    step_3_juntar_calendarios()
    inconsistencias = step_4_verificar_inconsistencias()
    step_5_atualizar_google_sheets(inconsistencias)
    print("\n=== SINCRONIZAÇÃO CONCLUÍDA ===")

if __name__ == "__main__":
    main()
