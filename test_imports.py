import sys
import os

# Adiciona o diretório atual ao path para importar src
sys.path.append(os.getcwd())

try:
    print("Testing imports...")
    import src.config
    print("  src.config: OK")
    import src.utils
    print("  src.utils: OK")
    import src.gsheets_api
    print("  src.gsheets_api: OK")
    import src.data_loader
    print("  src.data_loader: OK")
    import src.logic
    print("  src.logic: OK")
    import src.services
    print("  src.services: OK")
    print("All modules imported successfully!")
except Exception as e:
    print(f"IMPORT ERROR: {e}")
    exit(1)
