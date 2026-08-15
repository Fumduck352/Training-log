#!/usr/bin/env python3
"""
Dynamic Sector State Calculator
Calculates sector rotation states (Leading/Improving/Weakening/Lagging)
by comparing sector ETF performance vs SPY over 4-week and 13-week timeframes.
Replicates RRG (Relative Rotation Graph) logic automatically.

Usage:
    python update_sector_states.py

Output:
    Updates sector_states.csv with current sector states and timestamp.
"""

import yfinance as yf
import pandas as pd
import os
from datetime import datetime, timedelta
import sys

# Sector mapping: sector_name -> (sector_etf, description)
SECTOR_ETF_MAP = {
    "Aerospace/Defense": ("LMT", "Lockheed Martin proxy"),
    "Airlines/Transport": ("IYT", "Transportation ETF"),
    "Automotive": ("F", "Ford proxy"),
    "Automotive/EV": ("XPEV", "EV proxy"),
    "Business Services": ("G", "Genpact proxy"),
    "Clean Energy": ("ICLN", "Clean Energy ETF"),
    "Communication Services": ("XLC", "Communication Services ETF"),
    "Consumer Discretionary": ("XLY", "Consumer Discretionary ETF"),
    "Consumer Staples": ("XLP", "Consumer Staples ETF"),
    "E-Commerce/Cloud": ("QQQ", "Nasdaq-100 proxy"),
    "Emerging Markets": ("EEM", "Emerging Markets ETF"),
    "Entertainment/Gaming": ("NTDOY", "Nintendo proxy"),
    "Financial Services": ("XLF", "Financial Services ETF"),
    "Gold Miners": ("GDX", "Gold Miners ETF"),
    "Health Care": ("XLV", "Health Care ETF"),
    "Industrials": ("XLI", "Industrials ETF"),
    "Industrials/Defense": ("XLI", "Industrials ETF"),
    "Industrial Software": ("PSP", "Software ETF proxy"),
    "Semiconductors": ("SMH", "Semiconductor ETF"),
    "Software/SaaS": ("PSP", "Software ETF"),
    "Technology Hardware": ("XLK", "Technology ETF"),
}

BENCHMARK = "SPY"
LOOKBACK_4W = 20  # ~4 trading weeks
LOOKBACK_13W = 65  # ~13 trading weeks


def fetch_data(ticker, days_back=100):
    """Fetch OHLCV data for a ticker."""
    try:
        df = yf.download(ticker, period=f"{days_back}d", progress=False)
        return df["Close"] if not df.empty else None
    except Exception as e:
        print(f"  [WARN] Could not fetch {ticker}: {e}")
        return None


def calculate_returns(prices, lookback):
    """Calculate return over lookback period."""
    if prices is None or len(prices) <= lookback:
        return None
    current = float(prices.iloc[-1])
    past = float(prices.iloc[-lookback-1])
    if past <= 0:
        return None
    return ((current / past) - 1) * 100


def calculate_relative_strength(sector_prices, spy_prices, lookback):
    """Calculate relative strength: sector return - SPY return."""
    sector_ret = calculate_returns(sector_prices, lookback)
    spy_ret = calculate_returns(spy_prices, lookback)
    if sector_ret is None or spy_ret is None:
        return None
    return sector_ret - spy_ret


def classify_sectors(sector_data):
    """
    Classify sectors based on 4-week and 13-week relative strength.

    Leading:    Top quartile on both 4w and 13w RS
    Improving:  Top 13w but weak 4w (momentum building)
    Weakening:  Strong 13w but weak 4w (momentum fading)
    Lagging:    Bottom quartile on both
    Holding:    Middle ground / no clear trend
    """
    sectors_list = []

    # Collect data for ranking
    for sector, data in sector_data.items():
        if data["rs_4w"] is not None and data["rs_13w"] is not None:
            sectors_list.append({
                "sector": sector,
                "rs_4w": data["rs_4w"],
                "rs_13w": data["rs_13w"]
            })

    if not sectors_list:
        return {}

    # Sort by RS for percentile calculation
    rs_4w_sorted = sorted([s["rs_4w"] for s in sectors_list])
    rs_13w_sorted = sorted([s["rs_13w"] for s in sectors_list])

    p25_4w = rs_4w_sorted[len(rs_4w_sorted) // 4] if len(rs_4w_sorted) > 0 else 0
    p75_4w = rs_4w_sorted[3 * len(rs_4w_sorted) // 4] if len(rs_4w_sorted) > 0 else 0
    p25_13w = rs_13w_sorted[len(rs_13w_sorted) // 4] if len(rs_13w_sorted) > 0 else 0
    p75_13w = rs_13w_sorted[3 * len(rs_13w_sorted) // 4] if len(rs_13w_sorted) > 0 else 0

    result = {}
    for s in sectors_list:
        sector = s["sector"]
        rs_4w_strong = s["rs_4w"] >= p75_4w
        rs_4w_weak = s["rs_4w"] <= p25_4w
        rs_13w_strong = s["rs_13w"] >= p75_13w
        rs_13w_weak = s["rs_13w"] <= p25_13w

        # Classify based on RRG quadrants
        if rs_4w_strong and rs_13w_strong:
            state = "Leading"
        elif rs_4w_weak and rs_13w_weak:
            state = "Lagging"
        elif rs_13w_strong and rs_4w_weak:
            state = "Improving"
        elif rs_13w_weak and rs_4w_strong:
            state = "Weakening"
        else:
            state = "Holding"

        result[sector] = state

    return result


def update_sector_states_csv(classifications, output_file):
    """Write classifications to sector_states.csv."""
    rows = []
    today = datetime.now().strftime("%Y-%m-%d")

    for sector, state in sorted(classifications.items()):
        rows.append({"sector": sector, "state": state, "updated": today})

    if not rows:
        print("  [ERROR] No sector classifications to write")
        return False

    df = pd.DataFrame(rows)
    try:
        df.to_csv(output_file, index=False)
        print(f"  [OK] Updated {output_file} with {len(rows)} sectors")
        return True
    except Exception as e:
        print(f"  [ERROR] Could not write {output_file}: {e}")
        return False


def main():
    print(f"\n{'='*70}")
    print("Sector State Calculator")
    print(f"{'='*70}")

    # Determine output file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_file = os.path.join(script_dir, "sector_states.csv")

    print(f"\n[*] Fetching data for {len(SECTOR_ETF_MAP)} sectors...")

    # Fetch SPY data once (benchmark)
    spy_prices = fetch_data(BENCHMARK, days_back=100)
    if spy_prices is None or len(spy_prices) < LOOKBACK_13W + 1:
        print(f"  [ERROR] Could not fetch sufficient SPY data")
        return False

    print(f"  [OK] SPY: {len(spy_prices)} bars")

    # Fetch sector data and calculate RS
    sector_data = {}
    for sector, (etf, desc) in SECTOR_ETF_MAP.items():
        prices = fetch_data(etf, days_back=100)

        if prices is None or len(prices) < LOOKBACK_13W + 1:
            print(f"  [SKIP] {sector:<30} ({etf}) - insufficient data")
            continue

        rs_4w = calculate_relative_strength(prices, spy_prices, LOOKBACK_4W)
        rs_13w = calculate_relative_strength(prices, spy_prices, LOOKBACK_13W)

        state_str = f"RS: 4w={rs_4w:+.1f}% | 13w={rs_13w:+.1f}%" if rs_4w and rs_13w else "RS: n/a"
        print(f"  [OK] {sector:<30} ({etf:<5}) {state_str}")

        sector_data[sector] = {
            "rs_4w": rs_4w,
            "rs_13w": rs_13w,
            "etf": etf
        }

    if not sector_data:
        print("\n  [ERROR] No sector data available")
        return False

    # Classify sectors
    print(f"\n[*] Classifying sectors by RRG quadrants...")
    classifications = classify_sectors(sector_data)

    # Show results
    print(f"\nSector States (updated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}):")
    print("-" * 50)
    for state in ["Leading", "Improving", "Holding", "Weakening", "Lagging"]:
        sectors_in_state = [s for s, st in classifications.items() if st == state]
        if sectors_in_state:
            print(f"\n{state}:")
            for sector in sorted(sectors_in_state):
                rs_4w = sector_data[sector]["rs_4w"]
                rs_13w = sector_data[sector]["rs_13w"]
                print(f"  • {sector:<30} (4w: {rs_4w:+6.1f}% | 13w: {rs_13w:+6.1f}%)")

    # Write to CSV
    print(f"\n[*] Writing results to {os.path.basename(output_file)}...")
    success = update_sector_states_csv(classifications, output_file)

    if success:
        print(f"\n{'='*70}")
        print("✓ Sector states updated successfully")
        print(f"{'='*70}\n")
        return True
    else:
        print(f"\n{'='*70}")
        print("✗ Failed to update sector states")
        print(f"{'='*70}\n")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
