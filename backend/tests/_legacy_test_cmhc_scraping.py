#!/usr/bin/env python3
"""Test CMHC web scraping functionality."""

import sys                                                                                                                                                                                                
from pathlib import Path                                                                                                                                                                                  
sys.path.insert(0, str(Path(__file__).parent.parent)) 

from datetime import datetime
from database import SessionLocal, init_db
from collectors import CMHCCollector

def test_find_excel_urls():
    """Test finding Excel download URLs."""
    print("=" * 60)
    print("TEST 1: Finding Excel Download URLs")
    print("=" * 60)

    collector = CMHCCollector(SessionLocal())

    # Test rental market URL
    print("\n[1.1] Testing rental market Excel URL...")
    rental_url = collector._find_excel_download_url(
        "https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research/housing-data/data-tables/rental-market/rental-market-report-data-tables",
        "rental"
    )
    if rental_url:
        print(f"✓ Found rental URL: {rental_url}")
    else:
        print("✗ Could not find rental URL")

    return rental_url


def test_download_excel(url):
    """Test downloading and parsing Excel file."""
    print("\n" + "=" * 60)
    print("TEST 2: Downloading and Parsing Excel")
    print("=" * 60)

    if not url:
        print("✗ Skipping: no URL provided")
        return None

    print(f"\n[2.1] Downloading Excel from: {url}")
    collector = CMHCCollector(SessionLocal())
    df = collector._download_and_parse_excel(url)

    if df is None:
        print("✗ Failed to download/parse Excel")
        return None

    print(f"✓ Successfully parsed Excel")
    print(f"  Shape: {df.shape} (rows x columns)")
    print(f"  Columns: {list(df.columns[:5])}{'...' if len(df.columns) > 5 else ''}")

    return df


def test_filter_kcw(df):
    """Test KCW filtering."""
    print("\n" + "=" * 60)
    print("TEST 3: KCW Filtering")
    print("=" * 60)

    if df is None:
        print("✗ Skipping: no DataFrame provided")
        return None

    print("\n[3.1] Original DataFrame:")
    print(f"  Rows: {len(df)}")

    collector = CMHCCollector(SessionLocal())
    kcw_df = collector._filter_for_kcw(df)

    print(f"\n[3.2] After KCW filtering:")
    print(f"  Rows: {len(kcw_df)}")

    if kcw_df.empty:
        print("✗ No KCW rows found in data")
        print(f"  KCW patterns: {collector.KCW_PATTERNS}")
        print(f"  Sample row: {df.iloc[0].to_dict() if len(df) > 0 else 'N/A'}")
        return None

    print(f"✓ Found {len(kcw_df)} KCW rows")
    print(f"  Sample: {kcw_df.iloc[0].to_dict()}")

    return kcw_df


def test_full_collection():
    """Test full collection process."""
    print("\n" + "=" * 60)
    print("TEST 4: Full Collection Process")
    print("=" * 60)

    print("\n[4.1] Initializing database...")
    init_db()
    db = SessionLocal()

    print("[4.2] Running full collection...")
    collector = CMHCCollector(db)
    metrics = collector.collect()

    print(f"✓ Collection complete")
    print(f"  Total metrics collected: {len(metrics)}")

    if metrics:
        print(f"\n  Sample metrics:")
        for metric in metrics[:3]:
            print(f"    - {metric.category}: {metric.metric_name} = {metric.value} {metric.unit}")

    db.close()
    return metrics


def main():
    """Run all tests."""
    print("\n🧪 CMHC Web Scraping Tests\n")

    try:
        # Test 1: Find URLs
        rental_url = test_find_excel_urls()

        # Test 2: Download and parse
        df = test_download_excel(rental_url)

        # Test 3: Filter for KCW
        kcw_df = test_filter_kcw(df)

        # Test 4: Full collection
        metrics = test_full_collection()

        # Summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        if metrics:
            print(f"✓ All tests passed! Collected {len(metrics)} metrics.")
        else:
            print("⚠ Tests completed but no metrics were collected.")
            print("  This may indicate issues with URL finding, downloading, or KCW filtering.")

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
