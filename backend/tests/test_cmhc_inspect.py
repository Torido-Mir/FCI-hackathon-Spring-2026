#!/usr/bin/env python3
"""Inspect actual CMHC Excel file structure."""

import sys                                                                                                                                                                                                
from pathlib import Path                                                                                                                                                                                  
sys.path.insert(0, str(Path(__file__).parent.parent)) 

import io
import pandas as pd
import requests

# Download the Excel file
url = "https://assets.cmhc-schl.gc.ca/sites/cmhc/professional/housing-markets-data-and-research/housing-data-tables/rental-market/rental-market-report-data-tables/2025/rmr-kitchener-cambridge-waterloo-2025-en.xlsx"

print("Downloading Excel file...")
response = requests.get(url, timeout=60)
response.raise_for_status()

print("\n" + "=" * 60)
print("EXCEL FILE INSPECTION")
print("=" * 60)

# Check sheet names
xl_file = pd.ExcelFile(io.BytesIO(response.content), engine="openpyxl")
print(f"\nSheet names: {xl_file.sheet_names}")

# Load each sheet
for sheet_name in xl_file.sheet_names:
    print(f"\n{'=' * 60}")
    print(f"Sheet: {sheet_name}")
    print("=" * 60)

    df = pd.read_excel(io.BytesIO(response.content), sheet_name=sheet_name, engine="openpyxl")

    print(f"Shape: {df.shape} (rows x columns)")
    print(f"Columns: {list(df.columns)}")
    print(f"\nFirst 10 rows:")
    print(df.head(10).to_string())

    print(f"\nData types:")
    print(df.dtypes)
