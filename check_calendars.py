import sys
import os
from pathlib import Path

# Add the project root to sys.path to allow importing src
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from src import calendar_utils

def main():
    print("Fetching and processing calendars...")
    data = calendar_utils.get_calendar_data()
    
    apt_code = 'c108'
    if apt_code in data:
        df = data[apt_code]
        print(f"\n--- DataFrame for Apartment {apt_code} ---")
        display(df)
        print(df.head(20))
        print(f"\nTotal records: {len(df)}")
        print("\nValue Counts for 'summary':")
        print(df['summary'].value_counts())
    else:
        print(f"Apartment {apt_code} not found in data.")
        print("Available apartments:", list(data.keys()))

if __name__ == "__main__":
    main()
