# =============================================================================
# sell_signal_scanner.py v8 — daily-timeframe EXIT monitor for held positions
#
# Companion to vcb_screener.py / swing_scanner.py, but runs on a small,
# deliberately different universe: not a watchlist of candidates to BUY, but
# the stocks you already own, read straight from the Trading 212 Public API.
# No point scanning 1,500 watchlist tickers for an exit signal on positions
# you don't hold.
#
# CHANGELOG:
#   v8 (2026-08-09) — Pie tagging: fetch T212 pies, map holdings to pies,
#                      add pie column to holdings_map.csv, display pie badge
#                      on dashboard, add pie filtering. Also: now uses
#                      shared dashboard_shared.py CSS/JS module for
#                      consistent styling across all three scanners (sell/
#                      swing/screener). Font size fix: .ctx and .pill now
#                      0.82em to match table text (was 0.78em).
#   v7 (2026-08-09) — New STEAM tier: an earlier warning stage sitting between
#                      TRIM and HOLD, for "losing steam" positions — momentum
#                      fading before a TRIM-worthy bearish divergence actually
#                      confirms. Fires on either of two independent, additive
#                      conditions (either is enough, doesn't require both):
#                        1. WT2 rollover — WT2 touched SELL_OB_LEVEL within
#                           the last STEAM_ROLLOVER_LOOKBACK_DAYS days and has
#                           now declined for STEAM_ROLLOVER_DECLINE_DAYS
#                           straight days, but hasn't crossed WT1 yet (that's
#                           EXIT) and no confirmed divergence yet (that's
#                           TRIM) — see check_losing_steam().
#                        2. Fib extension — close has pushed beyond the
#                           STEAM_FIB_EXTENSION (1.618) extension of the most
#                           recent swing low -> swing high, i.e. the move is
#                           statistically stretched — see
#                           swing_fib_extension(). Lee's own idea, added
#                           alongside the WT2 rollover rather than replacing
#                           it.
#                      STEAM does NOT override EXIT/STOP/TRIM (checked first,
#                      same elif chain) and, unlike stop_hit, DOES feed back
#                      into trail_stop: a STEAM position's trail_pct is
#                      tightened by STEAM_TRAIL_TIGHTEN_FACTOR (0.5, i.e.
#                      halved) before the trail_stop price is computed in
#                      scan_positions() — the whole point of an early warning
#                      is to actually pull the stop in, not just log a note.
#                      Also: HTML report reworked into an actual dashboard —
#                      sortable/filterable table (click a header to sort,
#                      type in the search box to filter by ticker/name),
#                      last-updated timestamp + next-scheduled-run note, new
#                      STEAM pill styling. Report structure/filename/
#                      GDRIVE_REPORT_DIR logic unchanged, so digest_generator.py
#                      and the existing Drive sync keep working untouched.
#   v6 (2026-08-09) — Platform-aware GDRIVE_REPORT_DIR (uses G:\My Drive\trading
#                      on the PC where it exists, falls back to a local
#                      reports/ folder next to the script otherwise, e.g. the
#                      Pi) — one codebase for both machines instead of
#                      maintaining separate PC/Pi versions. No signal-logic
#                      changes from v5.
#   v5 (2026-08-08) — P&L vs entry, wired in as Lee asked once v4 ran clean
#                      live (81 real positions, correct reconcile, 74
#                      scanned, real signals). Uses averagePrice, already
#                      fetched by fetch_live_positions() since v3 but unused
#                      until now. Added: pnl_pct (close vs average_price,
#                      %) and stop_hit (True when close is STOP_LOSS_PCT=8%
#                      or more below average_price — Lee's own chosen
#                      threshold, asked rather than guessed) on every
#                      result dict, shown as a new P&L column in the
#                      terminal report and HTML report. Purely additive —
#                      does NOT feed into or override tier (EXIT/STOP/TRIM/
#                      HOLD) assignment, which stays exactly the WaveTrend/
#                      structure logic from v2/v3/v4; a HOLD position can
#                      still carry stop_hit=True and vice versa. Also fixed
#                      two bugs found while confirming v4 actually worked
#                      live: main() exited 0 even when it refused to run
#                      (T212Error handler did a bare `return`, not
#                      `sys.exit(1)` — silent false-success for any caller
#                      checking the exit code) and a UnicodeEncodeError
#                      crash printing the tier emoji when stdout isn't
#                      UTF-8-aware (fixed via sys.stdout.reconfigure()).
#   v4 (2026-08-08) — v3's T212 auth was wrong (same mistake as
#                      t212_reconcile_v2.py, see that script's v3 changelog
#                      entry for the full story): claimed T212 uses a single
#                      raw API key, no secret. Confirmed against T212's real
#                      docs (docs.trading212.com/api/section/general-
#                      information/quickstart, fetched 2026-08-08): auth is
#                      Basic base64(API_KEY:API_SECRET). t212_api_key.txt is
#                      now 2 lines (key, secret) instead of 1. NOTE: even
#                      with byte-for-byte correct Basic auth matching T212's
#                      own documented curl example, the live API still
#                      returned 401 as of this writing — a credential/
#                      account-side issue (revoked key, IP restriction, beta
#                      access not fully enabled), not a code bug. Untested
#                      end-to-end until that's resolved.
#   v3 (2026-08-08) — Replaced the PDF-based reconcile (confirmation-of-
#                      holdings-*.pdf) with a direct T212 Public API call.
#                      No more manual PDF export/drop-in-folder step —
#                      holdings, quantity, and current price all come
#                      straight from /equity/portfolio + /equity/metadata/
#                      instruments (joined by ticker, since positions carry
#                      no ISIN/name of their own). Same corrected endpoint/
#                      auth/response-shape fix as t212_reconcile_v2.py (v1
#                      of that script had 3 bugs — wrong endpoint, wrong
#                      auth, wrong response shape — and had never actually
#                      been run against the live API).
#                      reconcile_holdings_api() replaces v2's PDF-based
#                      reconcile_holdings(): same SOLD/NEW/audit-trail
#                      semantics (holdings_map_removed.csv), but sourced
#                      from live positions instead of a PDF snapshot.
#                      New positions now get their ticker filled in
#                      immediately from T212 data (no more blank-ticker
#                      "NEEDS TICKER" gap for anything on a US exchange) —
#                      NEEDS_TICKER_NOTE_PREFIX / needs_ticker handling kept
#                      only for backward compatibility with any legacy rows
#                      left over from the PDF era.
#                      Still a known limitation carried over unchanged:
#                      clean_ticker() strips the T212 exchange/type suffix
#                      but doesn't map it to a yfinance suffix, so new
#                      non-US listings (e.g. LSE "EZJ_l_EQ" -> "EZJ", needs
#                      to be "EZJ.L") still need a manual correction in
#                      holdings_map.csv, exactly as they did before.
#                      No signal logic touched: scan_positions(),
#                      evaluate_position(), the WaveTrend engine, and every
#                      locked constant are unchanged from v2.
#
# WHAT IT DOES EACH RUN:
#   1. Fetches live open positions from T212 (/equity/portfolio) and the
#      tradeable instrument list (/equity/metadata/instruments), joins them
#      by ticker to recover ISIN + name + currency for each position.
#   2. Auto-reconciles holdings_map.csv against that live position set
#      before anything else runs (reconcile_holdings_api()).
#   3. Looks each ISIN up in holdings_map.csv (same folder) to get a
#      yfinance ticker. ISINs not in the map — or in the map with a ticker
#      still pending — are skipped with a loud warning instead of guessed
#      at — add them to holdings_map.csv yourself once and every future run
#      picks them up automatically.
#   4. Batch-downloads daily OHLCV for every mapped ticker and runs the same
#      WaveTrend engine as the rest of the toolkit, but looking for the SELL
#      side: overbought cross-down (red dot), bearish divergence, and a
#      structural stop (fresh multi-week low).
#   5. Prints a tiered terminal report, writes an HTML report next to
#      vcb_report.html / swing_scanner's output, and logs new flags to
#      exit_log.csv for a track record (same pattern as vcb_screener's
#      avoid_log.csv).
#
# WHAT THIS DOES NOT DO (deliberately left out, see notes at the end):
#   - No fundamentals gate. This is a pure trend/momentum exit tool — you
#     already made the fundamentals case when you bought.
#   - initialFillDate (also fetched per position) is still unused — ask for
#     it if a holding-period-based check is ever wanted.
#
# SETUP (one time only):
#   pip install yfinance pandas numpy
#   Generate a T212 API key: account menu -> Settings -> API (Beta) -> Live
#   (not Practice). Grant BOTH the "portfolio" and "metadata" scopes. Copy
#   BOTH the "API Key ID" and "Secret Key" shown at creation time — the
#   secret is never shown again after that screen closes.
#   Put them in t212_api_key.txt in this folder: key on line 1, secret on
#   line 2.
#
# FILES (all in the same folder as this script):
#   t212_api_key.txt                 — 2 lines: your T212 Live API key,
#                                       then your API secret.
#   holdings_map.csv                 — isin,ticker,name,trail_pct,note
#                                       Blank ticker = deliberately excluded
#                                       (ETFs, the worthless warrant, the
#                                       SpaceX line with no public ticker)
#                                       — see the note column. A row MISSING
#                                       entirely can't happen anymore for a
#                                       live position (reconcile adds it
#                                       with ticker filled), but a manually
#                                       added blank-ticker/non-excluded row
#                                       still triggers a loud "needs ticker"
#                                       warning instead of being skipped
#                                       silently.
#   exit_log.csv                     — created/appended automatically.
#
# RUN:
#   python sell_signal_scanner_v7.py
#   python sell_signal_scanner_v7.py --dir "C:\path\to\folder"
#
# SCHEDULING: same pattern as vcb_screener.py / swing_scanner.py — Windows
# Task Scheduler, "Start a program", python, this script's full path as the
# argument.
# =============================================================================

import argparse
import base64
import csv
import json
import logging
import math
import os
import shutil
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import yfinance as yf

try:
    from dashboard_shared import get_dashboard_css, get_dashboard_js
except ImportError:
    get_dashboard_css = lambda: "<style></style>"
    get_dashboard_js = lambda: "<script></script>"

# v4 — force UTF-8 stdout regardless of the console's codepage. Without
# this, printing the tier emoji (🔴/🩹/⚠️/✅ etc. in log()/print_report())
# crashes with UnicodeEncodeError under Windows' legacy cp1252 console
# fallback — happens whenever stdout isn't attached to a real UTF-8-aware
# terminal (piped output, some Task Scheduler contexts, etc.), silently
# invisible from a normal interactive terminal until it isn't.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

logging.getLogger("yfinance").setLevel(logging.CRITICAL)

# -----------------------------------------------------------------------------
# Constants — kept in the same units/spirit as vcb_screener.py / swing_scanner.py
# so results are comparable across the toolkit (same regression-risk rule as
# OS_LEVEL / GDRIVE_REPORT_DIR documented there — don't silently retune here
# without a reason).
# -----------------------------------------------------------------------------
CHANNEL_LEN  = 10
AVG_LEN      = 21
SMOOTH_LEN   = 4
DIV_LOOKBACK = 12

# Overbought / sell-side thresholds — see sell_signal_scanner_v2.py's history
# for why this diverged from the buy-side SWING_OB_LEVEL (2026-08-04, GPN/DPZ
# gap-day false positives). Unchanged in v3.
SELL_OB_LEVEL = 40

GAP_LOOKBACK_DAYS = 5
GAP_THRESHOLD_PCT = 8.0

MA_TREND_LOOKBACK = 20
STRUCTURE_LOW_LOOKBACK = 30

TRAIL_LOOKBACK_DAYS = 90
DEFAULT_TRAIL_PCT   = 12.0

# v5 (2026-08-08) — P&L vs entry, informational only. Lee's own choice
# (asked explicitly rather than guessed): 8% below averagePrice (T212's
# real entry price, now available via fetch_live_positions()) flags
# stop_hit=True on a position's result. Does NOT feed into tier
# (EXIT/STOP/TRIM/HOLD) assignment or override it — that logic is
# unchanged from v2/v3/v4 and stays driven purely by WaveTrend/structure,
# same as STOP already means "fresh N-day low", a different, unrelated
# concept from "below entry price". stop_hit is a separate, additive flag
# a HOLD position can carry too.
STOP_LOSS_PCT = 8.0

# v7 (2026-08-09) — "losing steam" early-warning tier, pre-TRIM. Two
# independent triggers (see check_losing_steam() / swing_fib_extension()):
# WT2 rolling over from overbought without a confirmed cross/divergence yet,
# or price beyond a 1.618 Fibonacci extension of the recent swing low->high.
# Asked-for values, not guessed: 1.618 is the standard fib extension ratio,
# 2 straight down days is enough to call a rollover without waiting for a
# full confirmed cross.
STEAM_ROLLOVER_LOOKBACK_DAYS = 5
STEAM_ROLLOVER_DECLINE_DAYS  = 2
STEAM_FIB_LOOKBACK_DAYS      = STRUCTURE_LOW_LOOKBACK
STEAM_FIB_EXTENSION          = 1.618
STEAM_TRAIL_TIGHTEN_FACTOR   = 0.5

DOWNLOAD_PERIOD = "1y"
BATCH_SIZE      = 100

T212_KEY_FILENAME    = "t212_api_key.txt"
T212_BASE_URL        = "https://live.trading212.com/api/v0"
HOLDINGS_MAP_FILENAME = "holdings_map.csv"
HOLDINGS_MAP_FIELDS  = ["isin", "ticker", "name", "trail_pct", "pie", "entry_date", "note"]
HOLDINGS_MAP_REMOVED_FILENAME = "holdings_map_removed.csv"
NEEDS_TICKER_NOTE_PREFIX = "NEEDS TICKER"   # kept for backward-compat with any
                                              # legacy rows from the PDF era
ETF_NOTE_MARKER = "excluded"   # rows containing this in note are never
                                 # auto-removed by reconcile_holdings_api()
EXIT_LOG_FILENAME    = "exit_log.csv"
EXIT_LOG_DEDUPE_DAYS = 5

# v5: platform-aware — uses the Google Drive path on the PC where it's
# synced, falls back to a local reports/ folder next to the script anywhere
# else (e.g. the Pi, which has no G: drive). No per-machine editing needed.
SHOW_HTML_REPORT     = True
_HERE                = os.path.dirname(os.path.abspath(__file__))
_GDRIVE_WIN_PATH      = r"G:\My Drive\trading"
GDRIVE_REPORT_DIR    = _GDRIVE_WIN_PATH if os.path.isdir(_GDRIVE_WIN_PATH) else os.path.join(_HERE, "reports")
HTML_REPORT_FILENAME = "sell_report.html"
DASHBOARD_FILENAME   = "dashboard.html"

TIER_ICON  = {"EXIT": "\U0001F534", "STOP": "\U0001FA79", "TRIM": "\u26A0\uFE0F",
              "STEAM": "\U0001F7E0", "HOLD": "\u2705"}
TIER_ORDER = ["EXIT", "STOP", "TRIM", "STEAM", "HOLD"]


def log(msg=""):
    print(msg)


def _ensure_dashboard_copied():
    """Copy dashboard.html from source folder to reports folder for persistence.
    This ensures the dashboard stays synced and lives alongside the reports."""
    try:
        src = os.path.join(_HERE, DASHBOARD_FILENAME)
        if not os.path.exists(src):
            return  # Dashboard not in About Me folder, skip
        dst = os.path.join(GDRIVE_REPORT_DIR, DASHBOARD_FILENAME)
        if not os.path.exists(dst) or os.path.getmtime(src) > os.path.getmtime(dst):
            shutil.copy2(src, dst)
    except Exception:
        pass  # Silent fail \u2014 dashboard update is non-critical


# =============================================================================
# T212 API — live positions + instrument metadata (replaces PDF parsing)
# =============================================================================

class T212Error(Exception):
    """Raised on any T212 API failure — caught at the call site in main() so
    a bad key / network hiccup / rate limit produces a clear terse error and
    aborts before touching holdings_map.csv, same posture as v2's 'no PDF
    found -> refuse to run' behaviour."""


def _load_t212_credentials(directory):
    """Returns (key, secret). v4: T212 issues a key+secret pair (the app's
    API (Beta) screen shows both an "API Key ID" and a "Secret Key",
    visible once at creation) — v3's single-key assumption was wrong."""
    fp = os.path.join(directory, T212_KEY_FILENAME)
    if not os.path.exists(fp):
        raise T212Error(f"Missing {fp} — put your T212 API key on line 1 "
                         f"and secret on line 2.")
    lines = [l.strip() for l in open(fp, encoding="utf-8").read().splitlines() if l.strip()]
    if len(lines) < 2:
        raise T212Error(f"{fp} needs two lines: API key on line 1, secret on line 2 "
                         f"(both shown together only once, at key creation, in the T212 app).")
    return lines[0], lines[1]


def _t212_get(directory, path):
    key, secret = _load_t212_credentials(directory)
    creds = base64.b64encode(f"{key}:{secret}".encode()).decode()
    req = urllib.request.Request(f"{T212_BASE_URL}{path}", headers={"Authorization": f"Basic {creds}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 403:
            raise T212Error(f"T212 API 403 on {path} — API key is missing a "
                             f"required scope (needs both 'portfolio' and "
                             f"'metadata').")
        if e.code == 401:
            raise T212Error(f"T212 API 401 on {path} — auth REJECTED even though "
                             f"the request format matches T212's documented Basic "
                             f"auth exactly. This is a credential/account issue, "
                             f"not a code bug: check the key hasn't been revoked/"
                             f"regenerated, whether it has an IP restriction, and "
                             f"that API (Beta) access is fully enabled on the account.")
        raise T212Error(f"T212 API error {e.code} on {path}: {e.read().decode()[:200]}")
    except urllib.error.URLError as e:
        raise T212Error(f"T212 API unreachable: {e.reason}")


def clean_ticker(t212_ticker):
    # "AAPL_US_EQ" -> "AAPL". Does NOT map non-US exchange suffixes to their
    # yfinance equivalent (e.g. LSE "EZJ_l_EQ" -> "EZJ", not "EZJ.L") — same
    # limitation as the old script, fix by hand in holdings_map.csv.
    parts = t212_ticker.split("_")
    return parts[0] if parts else t212_ticker


def fetch_live_positions(directory):
    """
    Fetches /equity/portfolio (flat Position objects: ticker, quantity,
    averagePrice, currentPrice, ppl, initialFillDate — no isin/name) and
    /equity/metadata/instruments (isin/name/currency per ticker), joins them,
    and returns {isin: {ticker, name, quantity, price, currency,
    average_price, initial_fill_date}}.

    Raises T212Error on any failure — caller decides how to handle it.
    """
    positions = _t212_get(directory, "/equity/portfolio")
    instruments = _t212_get(directory, "/equity/metadata/instruments")
    instrument_map = {
        inst["ticker"]: inst for inst in instruments if inst.get("ticker")
    }

    live_by_isin, unresolved = {}, []
    for pos in positions:
        t212_ticker = pos.get("ticker", "")
        inst = instrument_map.get(t212_ticker)
        if not inst or not inst.get("isin"):
            unresolved.append(t212_ticker)
            continue
        live_by_isin[inst["isin"]] = {
            "ticker": clean_ticker(t212_ticker),
            "name": inst.get("name", ""),
            "quantity": pos.get("quantity"),
            "price": pos.get("currentPrice"),
            "currency": inst.get("currencyCode"),
            "average_price": pos.get("averagePrice"),
            "initial_fill_date": pos.get("initialFillDate"),
        }
    if unresolved:
        log(f"  [WARN] {len(unresolved)} live position(s) had no instrument-metadata "
            f"match, skipped: {', '.join(unresolved)}")
    return live_by_isin


# =============================================================================
# T212 PIES — map holdings to pies (show pie ownership context)
# =============================================================================

def fetch_pies(directory):
    """
    Fetches user's pies from T212 API (/equity/pies list, then detail for each).
    Returns {ticker: pie_name} mapping. Respects rate limits: 1/30s for list,
    1/5s per detail call (as documented in pi_setup_summary.md).
    Returns empty dict on any API failure (non-critical, pies are informational).
    """
    try:
        pies_list = _t212_get(directory, "/equity/pies")
        if not pies_list:
            return {}

        # v8 fix (2026-08-10): a ticker can legitimately sit in more than one
        # pie at once (T212 lets you hold the same instrument split across
        # several pies). The old version kept {ticker: pie_name} and just
        # overwrote on collision, so any ticker in 2+ pies silently showed
        # whichever pie happened to be processed last — not necessarily a
        # real answer. Now collects every pie a ticker appears in and joins
        # them for display.
        result = {}
        for pie_summary in pies_list:
            pie_id = pie_summary.get("id")
            pie_name = pie_summary.get("displayName", "")
            if not pie_id:
                continue

            try:
                time.sleep(5)  # Rate limit: 1 request / 5s per pie
                pie_detail = _t212_get(directory, f"/equity/pies/{pie_id}")
                if pie_detail and pie_detail.get("instruments"):
                    for inst in pie_detail["instruments"]:
                        ticker = inst.get("ticker", "")
                        if ticker:
                            t = clean_ticker(ticker)
                            result.setdefault(t, [])
                            if pie_name not in result[t]:
                                result[t].append(pie_name)
            except Exception as e:
                log(f"  [WARN] Failed to fetch pie {pie_id}: {e}")
                continue

        return {t: ", ".join(names) for t, names in result.items()}
    except Exception as e:
        log(f"  [WARN] Failed to fetch pies: {e} — continuing without pie data")
        return {}


# =============================================================================
# HOLDINGS MAP (isin -> yfinance ticker)
# =============================================================================

def load_holdings_map(directory):
    """
    Returns {isin: {"ticker": str, "name": str, "trail_pct": float|None,
    "note": str}}. A row with an empty ticker is a DELIBERATE exclusion
    (ETF, warrant, no public ticker, etc.) — distinct from an ISIN that isn't
    in the file at all, which is an unmapped/unknown holding that should
    warn loudly rather than be silently skipped.
    """
    fp = os.path.join(directory, HOLDINGS_MAP_FILENAME)
    out = {}
    if not os.path.exists(fp):
        log(f"  [WARN] {HOLDINGS_MAP_FILENAME} not found in {directory} — "
            f"every holding will show as unmapped. Create it with columns "
            f"isin,ticker,name,trail_pct,note")
        return out
    with open(fp, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            isin = (row.get("isin") or "").strip()
            if not isin:
                continue
            trail_pct = row.get("trail_pct", "")
            try:
                trail_pct = float(trail_pct) if trail_pct not in (None, "") else None
            except ValueError:
                trail_pct = None
            out[isin] = {
                "ticker": (row.get("ticker") or "").strip(),
                "name": (row.get("name") or "").strip(),
                "trail_pct": trail_pct,
                "pie": (row.get("pie") or "").strip(),
                "entry_date": (row.get("entry_date") or "").strip(),  # v9: optional stored entry_date
                "note": (row.get("note") or "").strip(),
            }
    return out


def _read_holdings_map_rows(directory):
    fp = os.path.join(directory, HOLDINGS_MAP_FILENAME)
    if not os.path.exists(fp):
        return []
    with open(fp, newline="", encoding="utf-8") as f:
        return [dict(row) for row in csv.DictReader(f)]


def _write_holdings_map_rows(directory, rows):
    fp = os.path.join(directory, HOLDINGS_MAP_FILENAME)
    with open(fp, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HOLDINGS_MAP_FIELDS)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in HOLDINGS_MAP_FIELDS})


def _append_removed_holdings_rows(directory, rows):
    """Audit trail for SOLD rows — created with the same header if it
    doesn't exist yet, always appended to, never overwritten/truncated."""
    if not rows:
        return
    fp = os.path.join(directory, HOLDINGS_MAP_REMOVED_FILENAME)
    write_header = not os.path.exists(fp)
    with open(fp, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HOLDINGS_MAP_FIELDS)
        if write_header:
            writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in HOLDINGS_MAP_FIELDS})


def reconcile_holdings_api(directory, live_by_isin, pies=None):
    """
    v3 — auto-reconciles holdings_map.csv against live T212 positions
    (already fetched by fetch_live_positions()). Runs at the start of every
    main(), before the scan, no CLI flag needed — same "always runs"
    philosophy as v2's PDF-based reconcile.

    SOLD (isin in holdings_map.csv, not in live_by_isin): row removed from
    holdings_map.csv, appended UNCHANGED to holdings_map_removed.csv — an
    audit trail, never a silent deletion. EXCEPTION: rows whose note
    contains "excluded" (ETFs, the worthless warrant, etc.) are never
    auto-removed by this diff, even if their isin doesn't appear in
    live_by_isin this run — deliberately conservative, since an ETF isin
    that fails to resolve through the instrument-metadata join (a real
    holding, just not joined this run) must never silently disappear from
    the documented-exclusions list. Same ETF_NOTE_MARKER guard t212_reconcile
    v1 had; ported over here since the PDF-based v2 reconcile never needed
    it (a genuinely-held ETF always appeared in the PDF export).

    NEW (isin in live_by_isin, not in holdings_map.csv): appended to
    holdings_map.csv WITH its ticker already filled in from T212 data (no
    blank/"NEEDS TICKER" gap for anything the API could resolve). If pies
    mapping provided, pie name is auto-filled for new rows.

    Everything else in holdings_map.csv is left exactly as-is: existing row
    order is preserved, this only appends new rows and removes sold ones.
    """
    if pies is None:
        pies = {}
    csv_rows = _read_holdings_map_rows(directory)
    isin_map = load_holdings_map(directory)

    map_isins = set(isin_map.keys())
    live_isins = set(live_by_isin.keys())

    excluded_isins = {isin for isin, e in isin_map.items()
                       if ETF_NOTE_MARKER in (e.get("note") or "").lower()}

    sold_isins = (map_isins - live_isins) - excluded_isins
    new_isins  = live_isins - map_isins

    removed_rows = [r for r in csv_rows if (r.get("isin") or "").strip() in sold_isins]
    kept_rows    = [r for r in csv_rows if (r.get("isin") or "").strip() not in sold_isins]

    today_str = datetime.now().strftime("%Y-%m-%d")
    new_rows = [{
        "isin": isin, "ticker": live_by_isin[isin]["ticker"],
        "name": live_by_isin[isin]["name"],
        "trail_pct": "", "pie": pies.get(live_by_isin[isin]["ticker"], ""),
        "note": f"added by T212 auto-reconcile {today_str}",
    } for isin in sorted(new_isins)]

    unchanged_count = len(kept_rows)

    if removed_rows or new_rows:
        _write_holdings_map_rows(directory, kept_rows + new_rows)
        _append_removed_holdings_rows(directory, removed_rows)

    log(f"  Reconcile: {len(removed_rows)} removed (sold), {len(new_rows)} new "
        f"(ticker auto-filled), {unchanged_count} unchanged")


# =============================================================================
# INDICATORS — same math as vcb_screener.py / swing_scanner.py (unchanged)
# =============================================================================

def wavetrend(df):
    ap = (df["High"] + df["Low"] + df["Close"]) / 3
    esa = ap.ewm(span=CHANNEL_LEN, adjust=False).mean()
    d = (ap - esa).abs().ewm(span=CHANNEL_LEN, adjust=False).mean()
    ci = (ap - esa) / (0.015 * d.replace(0, np.nan))
    wt1 = ci.ewm(span=AVG_LEN, adjust=False).mean()
    wt2 = wt1.rolling(SMOOTH_LEN).mean()
    return wt1, wt2


def compute_rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def check_losing_steam(wt2, idx):
    """
    v7 — early-warning rollover check, cheaper/earlier than a confirmed
    bearish divergence (check_bearish_divergence): True when WT2 touched
    overbought (>= SELL_OB_LEVEL) within the last
    STEAM_ROLLOVER_LOOKBACK_DAYS days and has now declined for
    STEAM_ROLLOVER_DECLINE_DAYS consecutive days. Deliberately does NOT
    require a WT1/WT2 cross (that's the confirmed EXIT red-dot) — this is
    meant to fire before that, while momentum is only just turning.
    """
    if idx < STEAM_ROLLOVER_DECLINE_DAYS:
        return False
    recent = wt2.iloc[idx - STEAM_ROLLOVER_DECLINE_DAYS: idx + 1]
    if recent.isna().any():
        return False
    declining = all(recent.iloc[i] < recent.iloc[i - 1] for i in range(1, len(recent)))
    if not declining:
        return False
    lookback_start = max(0, idx - STEAM_ROLLOVER_LOOKBACK_DAYS)
    window = wt2.iloc[lookback_start: idx + 1]
    return bool((window >= SELL_OB_LEVEL).any())


def swing_fib_extension(df, idx, lookback=STEAM_FIB_LOOKBACK_DAYS):
    """
    v7 — 1.618 Fibonacci extension of the most recent swing low -> swing
    high within `lookback` days: finds the lowest Low in the window, then
    the highest High from that low forward to idx (the impulse leg), then
    projects 1.618x that leg's range beyond the swing low. Returns
    (swing_low, swing_high, ext_1618) or (None, None, None) if there isn't
    enough of a window to measure.
    """
    lo_start = max(0, idx - lookback)
    window_low = df["Low"].iloc[lo_start: idx + 1]
    if window_low.empty or window_low.isna().all():
        return None, None, None
    swing_low = float(window_low.min())
    low_pos = window_low.idxmin()
    low_iloc = df.index.get_loc(low_pos)
    window_high = df["High"].iloc[low_iloc: idx + 1]
    if window_high.empty or window_high.isna().all():
        return None, None, None
    swing_high = float(window_high.max())
    if swing_high <= swing_low:
        return swing_low, swing_high, None
    ext_1618 = swing_low + (swing_high - swing_low) * STEAM_FIB_EXTENSION
    return swing_low, swing_high, ext_1618


def check_bearish_divergence(wt2, close, offset, ob_level):
    curr_wt2 = wt2.iloc[offset]
    curr_close = close.iloc[offset]
    if pd.isna(curr_wt2) or curr_wt2 < ob_level:
        return False
    for i in range(offset - DIV_LOOKBACK, offset - 1):
        if i < 0:
            continue
        prev_wt2, prev_close = wt2.iloc[i], close.iloc[i]
        if pd.isna(prev_wt2):
            continue
        if prev_wt2 >= ob_level:
            if curr_close > prev_close and curr_wt2 < prev_wt2:
                prev_curr_wt2 = wt2.iloc[offset - 1]
                if pd.isna(prev_curr_wt2) or offset - 2 < 0:
                    return True
                was_firing = (prev_curr_wt2 < wt2.iloc[offset - 2] and
                              close.iloc[offset - 1] > prev_close and
                              prev_curr_wt2 < prev_wt2)
                if not was_firing:
                    return True
    return False


def evaluate_position(df, wt1, wt2, ma50, idx):
    n = len(df)
    idx = n + idx if idx < 0 else idx
    if idx < max(60, DIV_LOOKBACK + 2) or idx >= n:
        return None
    prev = idx - 1

    w1, w2 = wt1.iloc[idx], wt2.iloc[idx]
    w1p, w2p = wt1.iloc[prev], wt2.iloc[prev]
    if any(pd.isna(x) for x in (w1, w2, w1p, w2p)):
        return None

    close = float(df["Close"].iloc[idx])
    rsi = compute_rsi(df["Close"], 14).iloc[idx]

    cross_down = (w1 < w2) and (w1p >= w2p)
    red_dot = cross_down and (w2p >= SELL_OB_LEVEL)

    bearish_div = (not red_dot) and check_bearish_divergence(wt2, df["Close"], idx, SELL_OB_LEVEL)

    gap_pct = None
    gap_start = max(1, idx - GAP_LOOKBACK_DAYS + 1)
    for i in range(gap_start, idx + 1):
        prior_close = float(df["Close"].iloc[i - 1])
        if prior_close == 0 or pd.isna(prior_close):
            continue
        today_open = float(df["Open"].iloc[i])
        g = (today_open - prior_close) / prior_close * 100
        if gap_pct is None or abs(g) > abs(gap_pct):
            gap_pct = g
    gap_flag = gap_pct is not None and abs(gap_pct) >= GAP_THRESHOLD_PCT

    lo_start = max(0, idx - STRUCTURE_LOW_LOOKBACK)
    prior_low = float(df["Close"].iloc[lo_start:idx].min()) if idx > lo_start else float("nan")
    structure_break = (not pd.isna(prior_low)) and (close < prior_low)
    recent_low = float(df["Low"].iloc[lo_start:idx + 1].min())

    m50 = ma50.iloc[idx]
    ago = idx - MA_TREND_LOOKBACK
    ma50_slope = None
    if ago >= 0 and not pd.isna(m50):
        m50_ago = ma50.iloc[ago]
        if not pd.isna(m50_ago) and m50_ago > 0:
            ma50_slope = (m50 / m50_ago - 1) * 100

    hi_start = max(0, idx - TRAIL_LOOKBACK_DAYS + 1)
    recent_high = float(df["High"].iloc[hi_start:idx + 1].max())

    # v7 — STEAM: only evaluated if none of the three confirmed tiers above
    # already fired, so it never overrides EXIT/STOP/TRIM.
    already_flagged = red_dot or structure_break or bearish_div
    wt2_rollover = (not already_flagged) and check_losing_steam(wt2, idx)
    swing_low, swing_high, fib_ext = swing_fib_extension(df, idx)
    fib_extended = (not already_flagged) and fib_ext is not None and close >= fib_ext
    losing_steam = wt2_rollover or fib_extended

    if red_dot:
        tier = "EXIT"
    elif structure_break:
        tier = "STOP"
    elif bearish_div:
        tier = "TRIM"
    elif losing_steam:
        tier = "STEAM"
    else:
        tier = "HOLD"

    notes = []
    if red_dot:
        notes.append("overbought cross-down (red dot)")
    if bearish_div:
        notes.append("bearish divergence")
    if structure_break:
        notes.append(f"fresh {STRUCTURE_LOW_LOOKBACK}d low")
    if wt2_rollover:
        notes.append("WT2 rolling over from overbought — tighten stop before divergence confirms")
    if fib_extended:
        notes.append(f"price beyond {STEAM_FIB_EXTENSION}x fib extension "
                      f"({swing_low:.2f} → {swing_high:.2f}, ext {fib_ext:.2f})")
    if gap_flag and (red_dot or bearish_div):
        notes.append(f"post-gap ({gap_pct:+.1f}% in last {GAP_LOOKBACK_DAYS}d) — "
                      f"cross may be gap mechanics, verify before acting")

    # v9 — WEINSTEIN_STOP: structural backstop independent of WaveTrend tiers
    # Fires when close is below 150-day SMA (30-week proxy), a sign of
    # structural weakness — acts as underlying layer, doesn't override main
    # tiers but complements them as an additional warning flag
    sma_150 = sma(close, 150)
    sma_150_val = float(sma_150.iloc[idx]) if (idx >= 150 and not pd.isna(sma_150.iloc[idx])) else None
    weinstein_stop = False
    if sma_150_val is not None and close_val < sma_150_val:
        weinstein_stop = True

    return {
        "date": df.index[idx].date() if hasattr(df.index[idx], "date") else df.index[idx],
        "tier": tier,
        "notes": notes,
        "close": round(close, 2),
        "wt2": round(float(w2), 2),
        "gap_pct": round(gap_pct, 1) if gap_pct is not None else None,
        "rsi": round(float(rsi), 1) if not pd.isna(rsi) else None,
        "ma50_slope": round(ma50_slope, 1) if ma50_slope is not None else None,
        "recent_high": round(recent_high, 2),
        "recent_low": round(recent_low, 2),
        "fib_ext_1618": round(fib_ext, 2) if fib_ext is not None else None,
        "losing_steam": losing_steam,
        "weinstein_stop": weinstein_stop,
    }


# =============================================================================
# DATA DOWNLOAD — batched + threaded, same pattern as the rest of the toolkit
# =============================================================================

REQUIRED_COLS = {"Open", "High", "Low", "Close"}


def download_batch(tickers):
    out = {}
    total_batches = math.ceil(len(tickers) / BATCH_SIZE)
    for b in range(total_batches):
        chunk = tickers[b * BATCH_SIZE:(b + 1) * BATCH_SIZE]
        sys.stdout.write(f"  downloading batch {b + 1}/{total_batches} "
                          f"({len(chunk)} tickers)...        \r")
        sys.stdout.flush()
        try:
            data = yf.download(chunk, period=DOWNLOAD_PERIOD, interval="1d",
                                group_by="ticker", threads=True,
                                progress=False, auto_adjust=True)
        except Exception as e:
            print(f"\n  [WARN] batch {b + 1} download failed: {e}")
            continue
        if data is None or data.empty:
            continue
        if len(chunk) == 1:
            df = data
            if isinstance(df.columns, pd.MultiIndex):
                if chunk[0] in df.columns.get_level_values(0):
                    df = df[chunk[0]]
                elif chunk[0] in df.columns.get_level_values(-1):
                    df.columns = df.columns.droplevel(-1)
                else:
                    df.columns = df.columns.droplevel(0)
            df = df.dropna(how="all")
            if not df.empty:
                out[chunk[0]] = df
            continue
        for t in chunk:
            try:
                df = data[t].dropna(how="all")
                if not df.empty and REQUIRED_COLS.issubset(df.columns):
                    out[t] = df
            except (KeyError, TypeError):
                continue
    sys.stdout.write(" " * 70 + "\r")
    return out


# =============================================================================
# SCAN — unchanged from v2
# =============================================================================

def scan_positions(mapped):
    tickers = sorted({m["ticker"] for m in mapped})
    data = download_batch(tickers)
    log(f"  data retrieved for {len(data)}/{len(tickers)} tickers\n")

    results = []
    for m in mapped:
        t = m["ticker"]
        df = data.get(t)
        if df is None or len(df) < 80:
            log(f"  [WARN] {t} ({m['name']}): insufficient data, skipped")
            continue
        try:
            wt1, wt2 = wavetrend(df)
            ma50 = df["Close"].rolling(50).mean()
            r = evaluate_position(df, wt1, wt2, ma50, -2)
        except Exception as e:
            log(f"  [WARN] {t}: {e}")
            continue
        if r is None:
            continue
        
        # v9 fix: anchor high-water-mark to entry date, not full price history
        # Fixes TRMB (entry during recovery) and BABA (pie-blended entries)
        recent_high = r.get("recent_high")
        entry_date = m.get("entry_date")
        if recent_high is not None and entry_date is not None:
            # Parse entry_date (ISO string or datetime object) and filter df
            try:
                if isinstance(entry_date, str):
                    from datetime import datetime as dt
                    entry_dt = dt.fromisoformat(entry_date.split("T")[0]) if "T" in entry_date else dt.strptime(entry_date[:10], "%Y-%m-%d")
                else:
                    entry_dt = entry_date
                # Filter price data to start from entry date forward
                df_from_entry = df[df.index.date >= entry_dt.date()]
                if len(df_from_entry) > 0:
                    recent_high = float(df_from_entry["High"].max())
            except Exception as e:
                # Silently fall back to original calculation on parse error
                pass
        
        trail_pct = m["trail_pct"] if m["trail_pct"] is not None else DEFAULT_TRAIL_PCT
        # v7 — STEAM tier tightens the trail stop rather than just noting a
        # warning: the point of an early "losing steam" flag is to actually
        # pull the stop in before a confirmed TRIM/EXIT, not just log it.
        if r["tier"] == "STEAM":
            trail_pct = round(trail_pct * STEAM_TRAIL_TIGHTEN_FACTOR, 1)
        avg_price = m.get("average_price")
        pnl_pct = (round((r["close"] - avg_price) / avg_price * 100, 1)
                   if avg_price else None)
        stop_hit = (avg_price is not None
                    and r["close"] <= avg_price * (1 - STOP_LOSS_PCT / 100))
        r.update({
            "ticker": t, "name": m["name"], "quantity": m["quantity"],
            "held_price": m["held_price"], "held_currency": m["held_currency"],
            "trail_pct": trail_pct,
            "trail_stop": round(recent_high * (1 - trail_pct / 100), 2) if recent_high else None,
            "average_price": avg_price,
            "pnl_pct": pnl_pct,
            "stop_hit": stop_hit,
        })
        results.append(r)

    tier_rank = {t: i for i, t in enumerate(TIER_ORDER)}
    results.sort(key=lambda r: (tier_rank.get(r["tier"], 99), r["wt2"]))
    return results


# =============================================================================
# TERMINAL REPORT — unchanged from v2
# =============================================================================

def print_report(results, unmapped, run_time, needs_ticker=None):
    log(f"\n{'=' * 78}")
    log(f"  SELL SIGNAL SCANNER — {run_time}")
    log(f"{'=' * 78}")

    if unmapped:
        log(f"\n  \u26A0  {len(unmapped)} holding(s) not in {HOLDINGS_MAP_FILENAME} — "
            f"add a ticker column for these to include them:")
        for u in unmapped:
            log(f"      {u['isin']}  {u['name']}")

    if needs_ticker:
        log(f"\n  ⚠  {len(needs_ticker)} holding(s) in {HOLDINGS_MAP_FILENAME} still need "
            f"a ticker — fill in the ticker column to include them:")
        for u in needs_ticker:
            log(f"      {u['isin']}  {u['name']}")

    if not results:
        log("\n  No mapped positions with usable data this run.")
        return

    counts = {t: sum(1 for r in results if r["tier"] == t) for t in TIER_ORDER}
    log(f"\n  {counts['EXIT']} EXIT   {counts['STOP']} STOP   "
        f"{counts['TRIM']} TRIM   {counts['STEAM']} STEAM   {counts['HOLD']} HOLD")

    for tier in TIER_ORDER:
        rows = [r for r in results if r["tier"] == tier]
        if not rows:
            continue
        log(f"\n  {TIER_ICON[tier]}  {tier}  ({len(rows)})")
        log("  " + "-" * 92)
        for r in rows:
            rsi = f"{r['rsi']:.1f}" if r["rsi"] is not None else "n/a"
            slope = f"{r['ma50_slope']:+.1f}%" if r["ma50_slope"] is not None else "n/a"
            pnl = f"{r['pnl_pct']:+.1f}%" if r.get("pnl_pct") is not None else "n/a"
            log(f"    {r['ticker']:<8} {r['name'][:24]:<24} close {r['close']:>9.2f}  "
                f"WT2 {r['wt2']:>7.2f}  RSI {rsi:>5}  50MAslp {slope:>7}  "
                f"trail-stop {r['trail_stop']:>9.2f} ({r['trail_pct']:.0f}%)  "
                f"P&L {pnl:>7}")
            if r.get("stop_hit"):
                log(f"      ⛔ STOP-HIT: {STOP_LOSS_PCT:.0f}%+ below entry "
                    f"(avg {r['average_price']:.2f})")
            if r["notes"]:
                log(f"      {'  |  '.join(r['notes'])}")
    log(f"\n{'=' * 78}\n")


# =============================================================================
# HTML REPORT — v7: sortable/filterable dashboard (structure/filename/
# GDRIVE_REPORT_DIR logic unchanged, so digest_generator.py's read-by-exact-
# name still works)
# =============================================================================

def _html_escape(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


TIER_PILL_CLASS = {"EXIT": "pill-exit", "STOP": "pill-stop",
                    "TRIM": "pill-trim", "STEAM": "pill-steam", "HOLD": "pill-hold"}



def write_html_report(results, unmapped, run_time, needs_ticker=None):
    if not SHOW_HTML_REPORT:
        return

    generated_iso = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    parts = [f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sell Signal Scanner — {_html_escape(run_time)}</title>
{get_dashboard_css()}
</head><body>
<h1>\U0001F4C9 Sell Signal Scanner</h1>
<div class="subtitle">Run: {_html_escape(run_time)} &middot; refreshes with each scheduled scan (07:00 / 19:00)</div>
<div class="filter-bar"><input id="filterBox" type="text" placeholder="Filter by ticker or name..."></div>"""]

    if unmapped:
        parts.append(f"<div class='warn-card'>\u26A0 {len(unmapped)} holding(s) not in "
                      f"{HOLDINGS_MAP_FILENAME}: " +
                      ", ".join(f"{_html_escape(u['name'])} ({_html_escape(u['isin'])})" for u in unmapped) +
                      "</div>")

    if needs_ticker:
        parts.append(f"<div class='warn-card'>\u26A0 {len(needs_ticker)} holding(s) in "
                      f"{HOLDINGS_MAP_FILENAME} still need a ticker: " +
                      ", ".join(f"{_html_escape(u['name'])} ({_html_escape(u['isin'])})" for u in needs_ticker) +
                      "</div>")

    if not results:
        parts.append("<p>No mapped positions with usable data this run.</p>")
    else:
        for tier in TIER_ORDER:
            rows = [r for r in results if r["tier"] == tier]
            if not rows:
                continue
            parts.append(f"<div class='tier-section'><h2>{TIER_ICON[tier]} {tier} ({len(rows)})</h2>")
            parts.append("<div class='tbl-wrap'><table class='dash'><thead><tr>"
                          "<th data-numeric='0'>Ticker</th><th data-numeric='0'>Name</th>"
                          "<th data-numeric='1'>Close</th><th data-numeric='1'>WT2</th>"
                          "<th data-numeric='1'>RSI</th><th data-numeric='1'>50MA slope</th>"
                          "<th data-numeric='1'>Trail stop</th><th data-numeric='1'>P&amp;L</th>"
                          "<th data-numeric='0'>Pie</th>"
                          "<th data-numeric='0'>Notes</th></tr></thead><tbody>")
            for r in rows:
                rsi = f"{r['rsi']:.1f}" if r["rsi"] is not None else "n/a"
                slope = f"{r['ma50_slope']:+.1f}%" if r["ma50_slope"] is not None else "n/a"
                notes = "; ".join(r["notes"]) if r["notes"] else "—"
                pcls = TIER_PILL_CLASS[tier]
                pnl = f"{r['pnl_pct']:+.1f}%" if r.get("pnl_pct") is not None else "n/a"
                pnl_sort = r.get("pnl_pct") if r.get("pnl_pct") is not None else -9999
                pnl_html = f"<span class='pill pill-stop'>⛔ {pnl}</span>" if r.get("stop_hit") else pnl
                ticker_esc = _html_escape(r['ticker'])
                name_esc = _html_escape(r['name'])
                # v8 fix (2026-08-10): was defaulting to the literal string
                # "my picks" whenever pie data was missing, which rendered
                # identically to a real pie tag — misleading, since it wasn't
                # verified against T212 at all, just a guess for "unknown".
                pie_str = r.get('pie', '') or "—"
                parts.append(f"<tr data-ticker='{ticker_esc}' data-name='{name_esc}'>"
                              f"<td><b>{ticker_esc}</b></td>"
                              f"<td>{name_esc}</td><td data-sort='{r['close']}'>{r['close']:.2f}</td>"
                              f"<td data-sort='{r['wt2']}'>{r['wt2']:.2f}</td><td>{rsi}</td><td>{slope}</td>"
                              f"<td data-sort='{r['trail_stop']}'>{r['trail_stop']:.2f} ({r['trail_pct']:.0f}%)</td>"
                              f"<td data-sort='{pnl_sort}'>{pnl_html}</td>"
                              f"<td class='ctx'><span class='pill pill-hold'>{_html_escape(pie_str)}</span></td>"
                              f"<td class='ctx'><span class='pill {pcls}'>{notes}</span></td></tr>")
            parts.append("</tbody></table></div></div>")

    parts.append(get_dashboard_js())
    parts.append(f"<div class='ctx' style='margin-top:20px'>Generated {generated_iso}</div>")
    parts.append("</body></html>")

    try:
        os.makedirs(GDRIVE_REPORT_DIR, exist_ok=True)
    except Exception as e:
        log(f"  [WARN] Could not create {GDRIVE_REPORT_DIR} — HTML report not written: {e}")
        return
    out_path = os.path.join(GDRIVE_REPORT_DIR, HTML_REPORT_FILENAME)
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(parts))
        log(f"  HTML report written: {out_path}")
        # Dated archive copy — out_path above stays a fixed filename since
        # digest_generator.py reads it by that exact name every run. This is
        # just a same-content snapshot alongside it so history isn't lost
        # each time the next run overwrites sell_report.html.
        stem, ext = os.path.splitext(HTML_REPORT_FILENAME)
        dated_path = os.path.join(GDRIVE_REPORT_DIR, f"{stem}_{datetime.now().strftime('%Y-%m-%d_%H%M')}{ext}")
        shutil.copy2(out_path, dated_path)
    except Exception as e:
        log(f"  [WARN] could not write HTML report: {e}")


# =============================================================================
# EXIT LOG — unchanged from v2
# =============================================================================

EXIT_LOG_FIELDS = ["date", "ticker", "tier", "close", "wt2", "notes"]


def _migrate_exit_log(fp):
    if not os.path.exists(fp):
        return
    with open(fp, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        rows = list(reader)
    if "wt2" in header:
        return
    for row in rows:
        row.setdefault("wt2", "")
    with open(fp, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=EXIT_LOG_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in EXIT_LOG_FIELDS})
    log(f"  migrated {os.path.basename(fp)} to include wt2 column ({len(rows)} existing row(s), left blank)")


def log_exit_events(results, directory, now):
    flagged = [r for r in results if r["tier"] != "HOLD"]
    if not flagged:
        return

    fp = os.path.join(directory, EXIT_LOG_FILENAME)
    _migrate_exit_log(fp)

    existing = []
    if os.path.exists(fp):
        with open(fp, newline="", encoding="utf-8") as f:
            existing = list(csv.DictReader(f))

    cutoff = now - timedelta(days=EXIT_LOG_DEDUPE_DAYS)
    recent_keys = set()
    for row in existing:
        try:
            d = datetime.fromisoformat(row["date"])
        except (KeyError, ValueError):
            continue
        if d >= cutoff:
            recent_keys.add((row.get("ticker"), row.get("tier")))

    new_rows = []
    for r in flagged:
        key = (r["ticker"], r["tier"])
        if key in recent_keys:
            continue
        new_rows.append({
            "date": now.strftime("%Y-%m-%dT%H:%M:%S"),
            "ticker": r["ticker"], "tier": r["tier"],
            "close": r["close"], "wt2": r["wt2"], "notes": "; ".join(r["notes"]),
        })

    if not new_rows:
        return

    write_header = not os.path.exists(fp)
    with open(fp, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=EXIT_LOG_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerows(new_rows)
    log(f"  {len(new_rows)} new flag(s) logged to {EXIT_LOG_FILENAME}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Daily-timeframe exit monitor for held positions.")
    parser.add_argument("--dir", default=os.path.dirname(os.path.abspath(__file__)),
                         help="Folder containing t212_api_key.txt and holdings_map.csv")
    args = parser.parse_args()

    run_time = datetime.now().strftime("%A %d %b %Y  %H:%M")
    log("\nSell Signal Scanner v8")
    log(f"Run: {run_time}")
    _ensure_dashboard_copied()

    try:
        live_by_isin = fetch_live_positions(args.dir)
    except T212Error as e:
        log(f"  [ERROR] {e}")
        log(f"  Refusing to run a scan on nothing — fix the T212 API access "
            f"and re-run. holdings_map.csv left untouched.")
        sys.exit(1)
    log(f"  {len(live_by_isin)} live position(s) from T212")

    pies = fetch_pies(args.dir)
    if pies:
        log(f"  {len(pies)} ticker(s) found in pies")

    reconcile_holdings_api(args.dir, live_by_isin, pies=pies)

    isin_map = load_holdings_map(args.dir)

    mapped, unmapped, needs_ticker, excluded = [], [], [], 0
    for isin, pos in live_by_isin.items():
        entry = isin_map.get(isin)
        if entry is None:
            unmapped.append({"isin": isin, "name": pos["name"]})
            continue
        if not entry["ticker"]:
            if entry["note"].startswith(NEEDS_TICKER_NOTE_PREFIX):
                needs_ticker.append({"isin": isin, "name": entry["name"] or pos["name"]})
            else:
                excluded += 1
            continue
        # v8 fix (2026-08-10): reconcile_holdings_api() only ever backfills
        # "pie" for brand-new rows, so every pre-existing row's pie tag was
        # frozen at whatever it was (usually blank) the day it was added and
        # never updated again. Prefer this run's live pies fetch; only fall
        # back to the stored CSV value if the API had nothing for this ticker
        # (e.g. a failed pies fetch this run).
        pie = pies.get(entry["ticker"], "") or entry.get("pie", "")
        mapped.append({
            "isin": isin, "ticker": entry["ticker"],
            "name": entry["name"] or pos["name"],
            "quantity": pos["quantity"], "held_price": pos["price"],
            "held_currency": pos["currency"], "trail_pct": entry["trail_pct"],
            "average_price": pos.get("average_price"), "pie": pie,
            "entry_date": pos.get("initial_fill_date"),  # v9 fix: anchor trailing stop to entry date
        })

    log(f"  {len(mapped)} scannable position(s), {excluded} deliberately excluded, "
        f"{len(unmapped)} unmapped, {len(needs_ticker)} needing a ticker")

    if not mapped:
        log("  [ERROR] No scannable positions — check holdings_map.csv.")
        print_report([], unmapped, run_time, needs_ticker=needs_ticker)
        return

    results = scan_positions(mapped)
    print_report(results, unmapped, run_time, needs_ticker=needs_ticker)
    write_html_report(results, unmapped, run_time, needs_ticker=needs_ticker)
    log_exit_events(results, args.dir, datetime.now())

    log(f"Done — {datetime.now().strftime('%H:%M')}")


if __name__ == "__main__":
    main()
