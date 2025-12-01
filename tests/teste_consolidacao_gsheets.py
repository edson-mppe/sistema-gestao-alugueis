import sys
import os
import pandas as pd
import gspread

# Configuração de PATH para encontrar o módulo 'src'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.config import APARTMENT_SHEET_MAP, SHEET_KEY
from src.gsheets_api import authenticate_google_sheets, ler_abas_planilha
from datetime import datetime

# --- CONFIGURAÇÃO DO TESTE ---
TAB_NAME_TESTE = "Reservas Consolidadas"

def debug_consolidacao_completa():
    print(f"\n{'='*60}")
    print("INICIANDO DEBUG DETALHADO DA CONSOLIDAÇÃO")
    print(f"{'='*60}")

    # 1. Autenticação
    print("\n[1] Autenticando...")
    gc = authenticate_google_sheets()
    if not gc:
        print("❌ Falha na autenticação. Abortando.")
        return
    print("✅ Autenticado com sucesso.")

    # 2. Leitura
    print("\n[2] Lendo abas individuais...")
    dfs_dict = ler_abas_planilha(APARTMENT_SHEET_MAP)
    
    all_reservas = []
    for nome, df in dfs_dict.items():
        if not df.empty:
            df['Apartamento'] = nome
            all_reservas.append(df)
            print(f"   -> Aba '{nome}': {len(df)} linhas lidas.")
    
    if not all_reservas:
        print("❌ Nenhuma reserva encontrada. Abortando.")
        return

    # 3. Concatenação
    print("\n[3] Concatenando DataFrames...")
    df_final = pd.concat(all_reservas, ignore_index=True, sort=False)
    
    # Tratamentos básicos para simular o script real
    df_final['idReserva'] = df_final.index + 1
    df_final['Última Atualização'] = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    
    # Limpeza de NaN (crucial para o gspread)
    df_final = df_final.fillna('')
    
    rows_count, cols_count = df_final.shape
    print(f"✅ DataFrame Final na Memória: {rows_count} linhas e {cols_count} colunas.")
    print("   -> Amostra dos dados (primeira linha):")
    print(df_final.iloc[0].to_dict())

    # 4. Preparação do Payload (A lista de listas que vai pro Google)
    print("\n[4] Convertendo para Lista de Listas (Payload)...")
    dados_cabecalho = df_final.columns.values.tolist()
    dados_corpo = df_final.astype(str).values.tolist()
    payload_completo = [dados_cabecalho] + dados_corpo
    
    qtd_linhas_payload = len(payload_completo)
    print(f"   -> Tamanho da lista preparada para envio: {qtd_linhas_payload} itens (1 cabeçalho + {qtd_linhas_payload-1} dados).")
    
    if qtd_linhas_payload <= 1:
        print("❌ ERRO CRÍTICO: O payload ficou vazio ou só tem cabeçalho antes de enviar!")
        return

    # 5. Tentativa de Escrita Manual (Bypass da função original para debug)
    print(f"\n[5] Escrevendo na aba '{TAB_NAME_TESTE}'...")
    sh = gc.open_by_key(SHEET_KEY)
    
    try:
        ws = sh.worksheet(TAB_NAME_TESTE)
        print(f"   -> Aba '{TAB_NAME_TESTE}' encontrada. Limpando dados antigos...")
        ws.clear() 
    except gspread.WorksheetNotFound:
        print(f"   -> Aba '{TAB_NAME_TESTE}' não existe. Criando nova...")
        ws = sh.add_worksheet(title=TAB_NAME_TESTE, rows=qtd_linhas_payload + 20, cols=cols_count)

    # TESTE A: Update sem resize (Para ver se os dados entram)
    print("   -> Enviando dados via 'update'...")
    try:
        # Tenta método v6
        resp = ws.update(values=payload_completo, range_name='A1')
        print(f"   ✅ Resposta do Update (v6): {resp}")
    except TypeError:
        # Tenta método antigo
        print("   -> Método v6 falhou, tentando v5...")
        resp = ws.update('A1', payload_completo)
        print(f"   ✅ Resposta do Update (v5): {resp}")
    except Exception as e:
        print(f"❌ ERRO FATAL NO UPDATE: {e}")
        return

    # 6. Verificação Pós-Escrita
    print("\n[6] Verificando o que foi salvo no Google Sheets...")
    valores_salvos = ws.get_all_values()
    qtd_salva = len(valores_salvos)
    print(f"   -> O Google Sheets reporta ter agora: {qtd_salva} linhas.")

    if qtd_salva == qtd_linhas_payload:
        print("\n✅ SUCESSO! O número de linhas bate (Memória vs Planilha).")
        
        # Só faz o resize se deu certo, para testar se é o resize que quebra
        print("[7] Testando Resize (Redimensionar planilha)...")
        try:
            ws.resize(rows=qtd_linhas_payload, cols=cols_count)
            print("   ✅ Resize concluído.")
        except Exception as e:
            print(f"   ⚠️ Erro no Resize (mas os dados devem estar lá): {e}")

    else:
        print(f"\n❌ ERRO: Discrepância! Enviamos {qtd_linhas_payload} mas a planilha tem {qtd_salva}.")
        print("   -> Dica: Verifique se existem células mescladas ou filtros na planilha que impedem a escrita.")

if __name__ == "__main__":
    debug_consolidacao_completa()