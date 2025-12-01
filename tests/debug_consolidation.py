import pandas as pd
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.gsheets_api import ler_abas_planilha
from src.config import APARTMENT_SHEET_MAP

def debug_consolidation():
    print("--- Debugging Consolidation ---")
    
    # 1. Read Sheets
    print("Reading sheets...")
    dfs_dict = ler_abas_planilha(APARTMENT_SHEET_MAP)
    
    if not dfs_dict:
        print("No data read from sheets.")
        return

    all_reservas = []
    print(f"\nFound {len(dfs_dict)} sheets.")
    
    # 2. Inspect each DataFrame
    for apt, df in dfs_dict.items():
        print(f"\n--- Sheet: {apt} ---")
        if df is not None and not df.empty:
            print(f"Shape: {df.shape}")
            print(f"Columns: {df.columns.tolist()}")
            
            # Simulate the preparation step
            df_copy = df.copy()
            df_copy['Apartamento'] = apt
            all_reservas.append(df_copy)
            print("Added 'Apartamento' column.")
        else:
            print("Empty or None.")

    # 3. Try Concatenation
    print("\n--- Attempting Concatenation ---")
    if all_reservas:
        try:
            df_consolidado = pd.concat(all_reservas, ignore_index=True)
            print("Concatenation SUCCESSFUL.")
            print(f"Consolidated Shape: {df_consolidado.shape}")
            print(f"Consolidated Columns: {df_consolidado.columns.tolist()}")
            print("\nSample Data:")
            print(df_consolidado[['Apartamento', 'Início', 'Fim', 'Summary']].head() if 'Summary' in df_consolidado.columns else df_consolidado.head())
        except Exception as e:
            print(f"Concatenation FAILED: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("No DataFrames to concatenate.")

if __name__ == "__main__":
    debug_consolidation()
