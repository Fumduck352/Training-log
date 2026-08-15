# VCB•W Trading System — Project State (as of 15 August 2026)

## What this is
A personal trading signal system with two halves:
- **vcb_screener_v18.py** — weekly/monthly value-dip BUY signal scanner (WaveTrend + fundamentals gate + conviction tiers: BUY TRIGGER / CONFIRMED / PRIME / WEAK / AVOID)
- **sell_signal_scanner_v8.py** — daily EXIT monitor for positions already held (T212-linked): EXIT / STOP / TRIM / STEAM / HOLD tiers

Runs on a Raspberry Pi, reports sync to Google Drive as HTML (`vcb_report.html`, `sell_report.html`) for mobile viewing. Full technical reference lives in `VCB_Reference_9.docx` (in the repo, see below).

## Where the code actually lives (IMPORTANT — known discrepancy)
- **Original/intended repo:** `github.com/Fumduck352/Trading` — has a `backup/before-weinstein-integration` tag cut before this session's changes, for rollback.
- **Where this session's commits actually landed:** `github.com/Fumduck352/Training-log`, branch `claude/trading-features-update-81njw5`, inside a `trading/` subfolder. (Training-log is otherwise a family fitness-tracking app — unrelated project sharing the repo.) This happened because the coding environment was scoped to Training-log, not Trading.
- **Not yet reconciled.** These two GitHub locations need merging into one authoritative repo/branch before this is "done." Flag this if picking the work back up.

## What was completed this session (7-item build brief from Lee)
1. ✅ **Stage-check column** — `stage_context` in vcb_screener_v18.py: Weinstein stage read-out per ticker (price vs 150-day SMA as a 30-week-MA proxy, SMA slope over ~26w, % off 52-week high). Context/display only — does not gate any existing tier.
2. ✅ **Stop-loss layer** — `weinstein_stop` in sell_signal_scanner_v8.py: 150-day SMA structural break, computed as an independent boolean sitting *underneath* the existing EXIT/STOP/TRIM/STEAM/HOLD hierarchy, not a new tier that reorders anything.
3. ✅ **Sector gate** — `sector_map.csv` (72 tickers → ~15 sector buckets) + `sector_states.csv` (Leading/Improving/Weakening/Lagging per sector) + a 📈✓ combo flag when a ticker's sector is Leading AND the ticker itself is in early-stage recovery.
4. ✅ **Trailing stop fix** — high-water mark in sell_signal_scanner_v8.py now anchors to the position's actual T212 entry date instead of full price history. Fixed TRMB/BABA, where the old whole-history high sat above every post-entry price, making the stop untriggerable.
5. ✅ **Volume-confirmation check** — current bar's volume vs 20-day/50-day average, classified strong (≥+10% above avg) / normal / weak.
6. ✅ **RS-line-rising check** — ⚠️ shipped as an **interim proxy only**: currently just the ticker's own 4-week price momentum, NOT true SPY-relative strength. The real version should reuse the existing `rs3m`/`_spy_trailing_returns()` logic already in `swing_pullback_shared.py`. Flagged as unfinished, not to be treated as done.
7. ⏸ **Pyramiding logic** (adding to winning positions) — deferred, not started.

**Bonus, not in the original brief:** `update_sector_states.py` — a new standalone script that calculates sector states automatically (ETF-vs-SPY relative strength, 4-week + 13-week, RRG-quadrant classification) instead of requiring manual updates from the RRG website. Run it before the screener, or on its own schedule; it overwrites `sector_states.csv`.

## Locked constants — never change these
`GDRIVE_REPORT_DIR`, `OS_LEVEL`/`OB_LEVEL` (-50/+50), `BUY_TRIGGER_MAX_DOWNSLOPE` (-2.0%), `RS3M_MIN` (10%), `DVOL_MIN_M` ($1M), `DIV_LOOKBACK` (12). All existing tier hierarchies (BUY TRIGGER > CONFIRMED > PRIME etc., and EXIT > STOP > TRIM > STEAM > HOLD) are primary structures — everything new is an additive display/context layer only.

## Documentation
- `trading/VCB_Reference_9.docx` — current reference doc (supersedes v8; v7/v8 kept alongside per the project's own "never edit in place, increment instead" convention). Has a full session-log section on everything above, a Known Issues list, and a Next Steps list.
- `trading/README.md` — practical setup/usage/cron guide for the three scripts.

## Known open issues
- GitHub repo discrepancy (see above) — needs reconciling.
- RS-line-rising is a proxy, not real relative strength — needs the SPY-relative swap.
- Sector ETF proxies are approximate for a few buckets with no clean dedicated ETF (Business Services, Entertainment/Gaming, Automotive/EV use a representative single stock instead).
- `sector_states.csv` can be silently overwritten by either the automated calculator or a manual RRG-based edit — whichever ran most recently wins, no conflict warning yet.
- Pyramiding logic not started.

## Next steps (in rough priority order)
1. Reconcile the two GitHub repos into one.
2. Live-test the new signals (📈✓ combo flag, weinstein_stop, volume-confirmation) against real data before trusting them for decisions.
3. Replace the RS-line-rising proxy with true SPY-relative strength.
4. Decide if `update_sector_states.py` runs on a cron schedule or stays manual.
5. Build pyramiding logic (item 7 of the original brief).
