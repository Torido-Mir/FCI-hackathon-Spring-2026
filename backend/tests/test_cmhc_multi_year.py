#!/usr/bin/env python3
"""Test CMHC web scraping for multiple years (2023, 2024, 2025)."""

import sys                                                                                                                                                                                                
from pathlib import Path                                                                                                                                                                                  
sys.path.insert(0, str(Path(__file__).parent.parent)) 

import io
import pandas as pd
import requests
from collectors import CMHCCollector
from database import SessionLocal


def test_year(year: int) -> dict:
    """Test CMHC rental vacancy data for a specific year."""
    print(f"\n{'=' * 60}")
    print(f"Testing Year {year}")
    print(f"{'=' * 60}")

    result = {
        "year": year,
        "url": None,
        "url_status": None,
        "downloaded": False,
        "sheet_found": False,
        "kcw_row_found": False,
        "metrics_extracted": 0,
        "metrics": [],
        "error": None,
    }

    # Construct URL for the year
    slug = "kitchener-cambridge-waterloo"
    url = (
        f"https://assets.cmhc-schl.gc.ca/sites/cmhc/professional/"
        f"housing-markets-data-and-research/housing-data-tables/rental-market/"
        f"rental-market-report-data-tables/{year}/"
        f"rmr-{slug}-{year}-en.xlsx"
    )

    result["url"] = url

    # Check if URL exists
    print(f"\n[1] Checking URL availability...")
    try:
        resp = requests.head(url, timeout=10)
        result["url_status"] = resp.status_code
        print(f"   Status: {resp.status_code}")

        if resp.status_code != 200:
            result["error"] = f"URL returned status {resp.status_code}"
            return result
    except Exception as e:
        result["error"] = f"URL check failed: {e}"
        print(f"   Error: {e}")
        return result

    # Download and parse
    print(f"\n[2] Downloading and parsing Excel...")
    try:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        result["downloaded"] = True
        print(f"   ✓ Downloaded successfully")
    except Exception as e:
        result["error"] = f"Download failed: {e}"
        print(f"   Error: {e}")
        return result

    # Check sheet names
    print(f"\n[3] Checking sheet names...")
    try:
        xl_file = pd.ExcelFile(io.BytesIO(response.content), engine="openpyxl")
        print(f"   Total sheets: {len(xl_file.sheet_names)}")

        # Look for the correct sheet
        target_sheet = "Table 1.1.1"
        if target_sheet in xl_file.sheet_names:
            result["sheet_found"] = True
            print(f"   ✓ Found sheet: {target_sheet}")
        else:
            print(f"   ✗ Sheet '{target_sheet}' not found")
            print(f"   Available sheets: {xl_file.sheet_names[:10]}")
            result["error"] = f"Sheet '{target_sheet}' not found"
            return result
    except Exception as e:
        result["error"] = f"Sheet check failed: {e}"
        print(f"   Error: {e}")
        return result

    # Load data
    print(f"\n[4] Loading data from sheet...")
    try:
        df = pd.read_excel(
            io.BytesIO(response.content),
            sheet_name=target_sheet,
            engine="openpyxl"
        )
        print(f"   Shape: {df.shape} (rows x columns)")
    except Exception as e:
        result["error"] = f"Failed to load sheet: {e}"
        print(f"   Error: {e}")
        return result

    # Find KCW row
    print(f"\n[5] Finding KCW row...")
    collector = CMHCCollector(SessionLocal())
    kcw_row = collector._find_kcw_row(df)

    if kcw_row is None:
        result["error"] = "KCW row not found"
        print(f"   ✗ KCW row not found")
        return result

    result["kcw_row_found"] = True
    print(f"   ✓ Found KCW row")

    # Extract metrics
    print(f"\n[6] Extracting vacancy rates...")
    try:
        metrics = collector._extract_vacancy_rates_from_row(kcw_row)
        result["metrics_extracted"] = len(metrics)
        result["metrics"] = [
            {
                "name": m.metric_name,
                "value": float(m.value),
                "unit": m.unit,
            }
            for m in metrics
        ]
        print(f"   ✓ Extracted {len(metrics)} metrics")
        for metric in metrics:
            print(f"     - {metric.value}% ({metric.metric_name})")
    except Exception as e:
        result["error"] = f"Failed to extract metrics: {e}"
        print(f"   Error: {e}")
        return result

    return result


def main():
    """Test multiple years."""
    print("\n🧪 CMHC Multi-Year Web Scraping Test\n")

    results = []
    for year in [2025, 2024, 2023]:
        result = test_year(year)
        results.append(result)

    # Summary
    print(f"\n\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}\n")

    for result in results:
        year = result["year"]
        status = "✓" if result["error"] is None else "✗"

        print(f"{status} {year}:")
        print(f"   URL Status: {result['url_status']}")
        print(f"   Downloaded: {result['downloaded']}")
        print(f"   Sheet Found: {result['sheet_found']}")
        print(f"   KCW Row Found: {result['kcw_row_found']}")
        print(f"   Metrics Extracted: {result['metrics_extracted']}")

        if result["error"]:
            print(f"   Error: {result['error']}")
        else:
            print(f"   Values: {[m['value'] for m in result['metrics']]}")
        print()


if __name__ == "__main__":
    main()
