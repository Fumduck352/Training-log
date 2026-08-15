# VCB•W Trading System Scripts

Automated buy/sell signal generation and sector rotation analysis for the VCB•W (VuManChu Cipher B + Weinstein) trading system.

## Scripts

### 1. `vcb_screener_v18.py` - Main Buy Signal Scanner

**Purpose:** Weekly/monthly value-dip screener with multi-layered signal confidence.

**Signals Generated:**
- 🎯 BUY TRIGGER - High conviction buy signals (strong fundamentals + technicals)
- 🟢 CONFIRMED - Good setup, passes fundamentals gate
- 🟠 CONFIRMED (DOWNTREND) - Good setup but in a downtrend
- 🟠 WEAK - Technical signal but weak fundamentals
- 🚫 AVOID - Death cross, bearish divergence, or value trap

**Features Added (Aug 2026):**
1. **Stage-check** - Weinstein stage context (price vs 150-day SMA, MA slope, distance from 52w high)
2. **Sector gate** - Top-down sector rotation filter with "Leading sector + early recovery" combo flag (📈✓)
3. **Volume confirmation** - Current volume vs 20/50-day average (strong/normal/weak)
4. **RS-line rising** - 4-week price momentum filter showing if stock maintaining uptrend

**Dependencies:**
```bash
pip install yfinance pandas
```

**Usage:**
```bash
python vcb_screener_v18.py
```

**Output:**
- Terminal: detailed report with all signal tiers and context
- HTML: `vcb_report.html` - synced to Google Drive for mobile viewing
- CSV: `full_rankings.csv` (all tickers with scores)

**Timeframes:** Weekly and Monthly (configurable)

---

### 2. `sell_signal_scanner_v8.py` - Exit Monitor for Held Positions

**Purpose:** Daily monitor for existing T212 positions, flags when to trim/exit.

**Signals Generated:**
- 🔴 EXIT (red dot cross) - WT crosses below overbought, exit immediately
- ⛔ STOP (structural low breach) - 150-day SMA break, activate stop-loss
- ✂️ TRIM (bearish divergence) - Take profits on overbought exhaustion
- 💨 STEAM (losing steam) - Momentum weakening, prepare to exit
- 🟢 HOLD (default) - Position healthy, hold

**Key Features:**
- Entry-date anchored trailing stop (high-water mark from actual entry)
- Weinstein stage analysis (150-day SMA structural support)
- Real-time T212 API integration for live position tracking
- ISIN-to-ticker mapping for position reconciliation

**Dependencies:**
```bash
pip install yfinance pandas
```

**Usage:**
```bash
python sell_signal_scanner_v8.py
```

**Output:**
- Terminal: position-by-position exit signals
- `exit_log.csv` - historical track record

---

### 3. `update_sector_states.py` - Automatic Sector Rotation Calculator

**Purpose:** Replaces manual RRG updates with programmatic calculation.

**Calculates:**
- 4-week relative strength (sector vs SPY)
- 13-week relative strength (sector vs SPY)
- Classifies sectors using RRG quadrant logic:
  - **Leading** - Strong on both 4w & 13w momentum (top-right)
  - **Improving** - Weak recent but strong longer-term (bottom-right)
  - **Holding** - Mixed momentum (middle)
  - **Weakening** - Strong longer-term but weak recent (top-left)
  - **Lagging** - Weak on both (bottom-left)

**Sectors Tracked:** 19 sectors including Software/SaaS, Semiconductors, Health Care, Industrials, etc.

**Dependencies:**
```bash
pip install yfinance pandas
```

**Usage:**
```bash
python update_sector_states.py
```

**Output:**
- Terminal: sector rankings by phase
- `sector_states.csv` - updated with current states and date

**Typical Runtime:** ~2-3 seconds (no API limits)

---

## Workflow

### Weekly Trading System Run

```bash
cd /home/user/Training-log/trading

# 1. Update sector rotation states (optional but recommended)
python update_sector_states.py

# 2. Run main buy signal scanner
python vcb_screener_v18.py

# 3. Check daily exit signals on held positions (daily)
python sell_signal_scanner_v8.py
```

### Recommended Automation (Cron on Pi)

**Weekly buy signal scan (Friday 22:00 UTC):**
```bash
0 22 * * 5 cd /home/user/Training-log/trading && python vcb_screener_v18.py >> vcb_screener.log 2>&1
```

**Daily exit signal scan (08:30 UTC weekdays):**
```bash
30 8 * * 1-5 cd /home/user/Training-log/trading && python sell_signal_scanner_v8.py >> exit_scanner.log 2>&1
```

**Weekly sector updates (Friday 21:00 UTC):**
```bash
0 21 * * 5 cd /home/user/Training-log/trading && python update_sector_states.py >> sector_calc.log 2>&1
```

---

## Configuration Files

### `sector_map.csv`
Static mapping of 72 watchlist tickers to ~15 sectors.
- Edit manually if adding/removing tickers
- Auto-generated on first run if missing

### `sector_states.csv`
Current sector rotation states (auto-updated by `update_sector_states.py`).
- Can also edit manually if updating from RRG visually
- Format: `sector,state,updated`

### `holdings_map.csv`
Maps T212 ISINs to tickers (used by sell_signal_scanner_v8.py).
- Auto-reconciled from T212 API

### `fundamentals_cache.csv`
Cache of fundamental checks (P/E, debt ratios, insider buying).
- Auto-maintained, 7-day freshness window
- Avoids Yahoo Finance rate-limiting

---

## Key Metrics Explained

### Stage Context (Weinstein Analysis)
Example: "above 30W MA (proxy @ 182.34), MA rising +2.3% (26w), -5.2% off 52wk high"

- **30W MA proxy** - 150-day SMA on daily data
- **MA slope** - Percentage change of SMA over 26 weeks
- **52w high** - Distance from year high (recovery opportunity)

### Combo Flag (📈✓)
Appears when:
1. Sector is **Leading** (top momentum phase), AND
2. Stock is in **early recovery** (price > 150-day SMA with rising MA slope)

This is your top-priority signal: top-down sector strength + early technical recovery.

### Volume Confirmation
Example: "Volume: strong (+45% vs 20d avg)"

- **Strong** - Current volume ≥ +10% above 20-day average (high conviction)
- **Normal** - 0-10% above average (normal participation)
- **Weak** - Below average (insufficient confirmation)

### RS-Line Rising
Example: "RS vs SPY: rising (+5.2% over 4w)"

- Tracks 4-week price momentum as proxy for relative strength
- Positive = stock outperforming (maintaining uptrend)
- Negative = stock lagging (losing momentum)

---

## Output Files

### HTML Report
**Location:** `vcb_report.html` (synced to Google Drive)

- Dark theme, mobile-responsive
- Updated each run, same bookmark works
- Shows: BUY TRIGGER tier, CONFIRMED tier, Full rankings, AVOID track record
- All context fields: stage, sector, volume, RS, earnings warning, entry/stop levels

### Terminal Output
**Console:** Detailed text table with all tickers and context

### CSV Exports
- `full_rankings.csv` - All tickers ranked by quality
- `exit_log.csv` - Exit signal history
- `sector_states.csv` - Current sector rotation phases

---

## Troubleshooting

**"Could not fetch SPY data"** in sector calculator
- Network issue or yfinance rate limit
- Retry in 60 seconds

**"Fundamentals data unavailable"** in buy signals
- Yahoo Finance rate-limited the session
- Signals still show but ungated (no tier assigned)
- Cache will restore on next run

**Missing company names in output**
- First run builds company_name_cache.json
- Subsequent runs use cache (instant lookup)

**CSV not updating**
- Check file permissions in trading directory
- Ensure path is correct: `sector_states.csv` should be in same directory

---

## Development Notes

**Locked Constants:** These values are calibrated and should NOT change:
- `OS_LEVEL = -50` (WaveTrend oversold threshold)
- `OB_LEVEL = 50` (WaveTrend overbought threshold)
- `BUY_TRIGGER_MAX_DOWNSLOPE = -2.0` (MA slope gate)
- `GDRIVE_REPORT_DIR` (report sync location)

**Tier Hierarchy:** Preserved as primary structure; new features (sector, volume, RS) are additive layers:
1. BUY TRIGGER (highest conviction)
2. CONFIRMED
3. CONFIRMED (DOWNTREND)
4. WEAK
5. (not shown) = still scanning

**Data Sources:**
- **Price/Volume:** yfinance (Yahoo Finance)
- **Fundamentals:** yfinance .info dict (earnings, debt, P/E)
- **Sector ETFs:** yfinance (PSP, SMH, XLK, XLV, etc.)
- **Positions:** T212 API (if configured)

---

## Links & Resources

- **VCB•W Theory:** Combines VuManChu Cipher B signals with Weinstein stage analysis
- **WaveTrend:** WT1 (fast), WT2 (slow) momentum divergences + crosses
- **Sector Rotation:** RRG-style phase classification (Leading → Improving → Lagging → Weakening)
- **Google Drive:** G:\My Drive\trading (report sync folder)

---

**Last Updated:** 2026-08-15
**Version:** v18 + dynamic sector updates
