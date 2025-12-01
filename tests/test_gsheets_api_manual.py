import sys
import os
import pandas as pd

# Add project root to sys.path to ensure imports work
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.config import APARTMENT_SHEET_MAP

from src.gsheets_api import (
    authenticate_google_sheets,
    baixar_dados_google_sheet,
    baixar_proximos_hospedes_consolidados,
    baixar_ultimas_reservas_consolidadas,
    ler_abas_planilha,
    consolidar_e_salvar_reservas,
    salvar_df_no_gsheet,
)

def test_authenticate():
    print("\n--- Testing Authentication ---")
    try:
        creds = authenticate_google_sheets()
        if creds:
            print("Authentication SUCCESS")
        else:
            print("Authentication FAILED (returned None)")
    except Exception as e:
        print(f"Authentication ERROR: {e}")

def test_baixar_dados():
    print("\n--- Testing baixar_dados_google_sheet ---")
    try:
        df = baixar_dados_google_sheet("Reservas Consolidadas")
        print(f"Result shape: {df.shape}")
        if not df.empty:
            print("Head:")
            print(df.head(2).to_string())
        else:
            print("DataFrame is empty")
    except Exception as e:
        print(f"Error: {e}")

def test_proximos_hospedes():
    print("\n--- Testing baixar_proximos_hospedes_consolidados ---")
    try:
        df = baixar_proximos_hospedes_consolidados()
        print(f"Result shape: {df.shape}")
        if not df.empty:
            print("Columns:", df.columns.tolist())
            print(df.head(2).to_string())
        else:
            print("DataFrame is empty")
    except Exception as e:
        print(f"Error: {e}")

def test_ultimas_reservas():
    print("\n--- Testing baixar_ultimas_reservas_consolidadas ---")
    try:
        df = baixar_ultimas_reservas_consolidadas()
        print(f"Result shape: {df.shape}")
        if not df.empty:
            print("Columns:", df.columns.tolist())
            print(df.head(2).to_string())
        else:
            print("DataFrame is empty")
    except Exception as e:
        print(f"Error: {e}")

def test_ler_abas():
    print("\n--- Testing ler_abas_planilha ---")
    try:
        # Using 'Reservas Consolidadas' as a test case since we know it likely exists
        
        dfs = ler_abas_planilha(APARTMENT_SHEET_MAP)
        for k, v in dfs.items():
            print(f"Tab '{k}' read with shape {v.shape}")
            if not v.empty:
                print(v.head(1).to_string())
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    print("Starting Manual Tests for gsheets_api.py...")
    #test_authenticate()
    #test_baixar_dados()
    #test_proximos_hospedes()
    #test_ultimas_reservas()
    #dfs = ler_abas_planilha(APARTMENT_SHEET_MAP)
    #print(dfs)
    #primeiro_df = list(dfs.values())[0]
    #print('primeiro_df.shape: ', primeiro_df.shape)
    #print(primeiro_df)
    #salvar_df_no_gsheet(primeiro_df, "Reservas Consolidadas")
    consolidar_e_salvar_reservas(lambda x: print(x))
    print("\nTests Completed.")
