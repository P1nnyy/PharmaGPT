import pandas as pd
import os
import sys

# --- Configuration ---
INPUT_FILE = "HSN_SAC.xlsx"  # Place file in project root
OUTPUT_FILE = os.path.join("config", "hsn_master.csv")

# Map your Excel headers to the required format: 'My Header': 'Target Header'
COLUMN_MAPPING = {
    "HSN_Description": "Description",
    "HSN_CD": "HSN_Code"
}

# Prefixes to keep (Pharma/Retail chapters)
ALLOWED_PREFIXES = ("30", "33", "34", "96")

def convert_hsn_data():
    print(f"Reading input file: {INPUT_FILE}...")
    
    if not os.path.exists(INPUT_FILE):
        print(f"Error: Input file '{INPUT_FILE}' not found.")
        sys.exit(1)

    try:
        # Load Excel file
        df = pd.read_excel(INPUT_FILE)
        
        # Check if required columns exist before renaming
        missing_cols = [col for col in COLUMN_MAPPING.keys() if col not in df.columns]
        if missing_cols:
            print(f"Error: Missing columns in Excel file: {missing_cols}")
            print(f"Available columns: {list(df.columns)}")
            sys.exit(1)

        # Rename columns
        df.rename(columns=COLUMN_MAPPING, inplace=True)
        
        # Ensure HSN_Code is string for filtering
        df['HSN_Code'] = df['HSN_Code'].astype(str)

        # Filter rows
        print(f"Filtering for HSN codes starting with {ALLOWED_PREFIXES}...")
        initial_count = len(df)
        df = df[df['HSN_Code'].str.startswith(ALLOWED_PREFIXES)]
        filtered_count = len(df)
        
        print(f"Rows retained: {filtered_count} / {initial_count}")

        # specific columns only
        df = df[["Description", "HSN_Code"]]

        # Clean Description (optional whitespace stripping)
        df['Description'] = df['Description'].str.strip()

        # Create output directory if it doesn't exist
        os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

        # Save to CSV
        print(f"Saving to {OUTPUT_FILE}...")
        df.to_csv(OUTPUT_FILE, index=False)
        print("Conversion complete successfully.")

    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    convert_hsn_data()
