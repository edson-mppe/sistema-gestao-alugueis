import pandas as pd
from datetime import datetime

# Create a DataFrame with duplicate 'Fim' columns
df = pd.DataFrame(
    [[datetime.now(), datetime.now(), 'Pending']], 
    columns=['Fim', 'Fim', 'Status']
)

print("Columns before selection:", df.columns)

# Mimic gsheets_api.py selection
cols_to_keep = ['Fim', 'Status']
existing_cols = [col for col in cols_to_keep if col in df.columns]
print("Existing cols:", existing_cols)

df_selected = df[existing_cols].copy()
print("Columns after selection:", df_selected.columns)

try:
    agora = datetime.now()
    # This mimics src/logic.py line 178
    print("Attempting boolean indexing with duplicate 'Fim'...")
    mask = df_selected['Fim'] < agora
    print("Mask type:", type(mask))
    
    print("Attempting loc assignment...")
    df_selected.loc[mask, 'Status'] = 'Concluído'
    print("Success!")
except Exception as e:
    print(f"Caught expected error: {e}")
