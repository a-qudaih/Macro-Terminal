# Macro Terminal: changes in this version

## Bug fixes
- **fetch_data.py: FRED "list index out of range".** FRED returns "." for the newest day when it has not been
  published yet. With `limit=1` the "." was filtered out and the list was empty. Now over-fetches and takes the newest
  *valid* rows. Every FRED series is isolated, so one failure no longer kills the rest, and `status.fred` names the series.
- **index.html: hardcoded actuals.** When FRED failed, `rates/cpi/unemployment/gdp` silently used values typed into the
  HTML. They are now scored 0 and flagged STALE.
- **Hardcoded daily changes.** 10Y bps / VIX % / DXY % stayed at defaults (+5.0 / +8.4 / +0.35) whenever the browser live feed
  was down, and the +5.0 bps fed the Central Bank Policy score. Now taken from data.json.
- **data.json read once.** The page only read data.json at load; an open tab never saw newer snapshots and the banner age
  kept growing. Now re-read every 5 min and on the Sync button.
- **Neutral band mismatch.** Label used +/-1.0, backtest used +/-0.8. One shared `NO_TRADE_BAND = 1.0`.
- **Pillar attribution.** A pillar scoring exactly 0.0 was counted as a miss. Now excluded from that pillar's denominator.

## Added: Nonfarm Payrolls, Retail Sales, ISM Services PMI
- **NFP** (labor channel, with unemployment) and **Retail Sales MoM** (growth channel): actuals auto-fetched from FRED
  (`PAYEMS` monthly change in thousands, `RSAFS` MoM %). **ISM Services**: actual + expected typed in consensus.json (not on FRED).
  Expected values for all three are yours to supply (consensus.json or the card fields).
- Channels are *averages*, so weights are unchanged: labor = avg(unemployment, NFP); growth = avg(GDP, ISM Mfg, ISM Services, Retail).
  The earnings/cycle modifier uses the same growth channel.
- Typical-surprise scales (starting values): NFP 80k, Retail 0.45 pts, ISM Services 1.8 pts.
- An indicator with no values shows NEEDS INPUT, is excluded (not a hidden 0), and is listed in the banner.
  Stale/missing indicators are now excluded from a channel's average instead of diluting it.
- A value typed by hand with no known release date decays from the day you typed it.
- Fixed while testing: typing a value into a card did not clear the stale flag; strict release-date parsing.

## Consensus can now be entered on the page
- A value typed in an Expected field is saved in the browser and **always wins over consensus.json** (the file is now an optional fallback).
- A typed Actual wins only if it was typed on/after the release data.json knows about; a newer release replaces it.
- If a new release arrives after you entered the consensus, the card shows NEW RELEASE: CHECK CONSENSUS with a one-click "still valid" button,
  and the banner lists it under UPDATE CONSENSUS.
- Typed values live in that browser only (like the history log).

## Banner is schedule-aware
- "SNAPSHOT ... live feed down" was shown permanently because the browser's live prices go through a free public proxy that
  is blocked for you. Running on the daily snapshot is the normal mode, so it now reads "DAILY SNAPSHOT ... (latest scheduled run)" in neutral colour.
- Amber only when a scheduled refresh is overdue; red only when data is stale (>36h and not the latest scheduled run).
- The red "DO NOT TRADE" no longer fires all weekend / Monday morning, when Friday's close is the newest data that exists.
- Constants `SCHEDULE_UTC_HOUR/MIN/GRACE_MIN` in index.html must match the cron in update-data.yml (currently 22:30 UTC Mon-Fri).

## Score History compares score to the market's move; click-for-details on pillars and slots
- **Score History:** new columns Day Δ (the market's move on the snapshot day), Next Δ (move to the next day's snapshot of the same asset,
  automatic, no typing) and Call (✓/✕ if a directional score called it, NT in the no-trade zone, … while pending).
  A summary strip shows hit rate vs the always-long rate, average next move when bullish / bearish / no-trade, and score↔move correlation.
  The newest row stays pending until the following day's snapshot, so a flat provisional price is never scored as a miss.
  New snapshots store the day's move; older rows derive it from the previous snapshot (marked ~).
- **Click a slot name** (any of the 10) for: what it measures, bullish/bearish conditions, the live inputs and maths behind the current number, and the data source.
  **Click a pillar header** for the breakdown: bars per slot, biggest driver, how many slots are static or stale, contribution to the composite.
  Explanations are written by the scoring code itself as it calculates, so they always match the number.
- Disclosed by this view: the Earnings/Structural slot is mostly a fixed number in the code, and Seasonality is a fixed table.

## Economic engine organized into Growth / Inflation / Labor; added PPI, Core PCE, weekly jobless claims
- The engine is now three sections. Each shows its indicators, how many are live, the selected asset's sensitivity, and the **channel Z**
  (the average of the live indicators in that section, which is what feeds the Economic Surprise slot), plus one line on how it is read in the current regime.
  - **Growth:** GDP, ISM Manufacturing, ISM Services, Retail Sales
  - **Inflation:** CPI, **PPI**, **Core PCE** (and the Fed Target Rate card, which feeds the Central Bank slot, not this one)
  - **Labor:** Unemployment, Nonfarm Payrolls, **Initial Jobless Claims**
- Inflation was a single input (CPI); it is now the average of CPI, PPI and core PCE, like the other channels, so weights are unchanged.
- **Claims:** higher than expected = weaker labor (inverted); fades over 7 days instead of 21 (weekly release). If no consensus is entered, the
  **average of the previous 4 weeks** stands in for it (labelled "Expected (4-wk avg)"); type a value to replace it, clear the box to return to it.
- FRED series: `PPIFIS` (PPI final demand YoY), `PCEPILFE` (CORE PCE YoY; use `PCEPI` in fetch_data.py for headline), `ICSA` (claims, in thousands).
- Clearing an Actual/Expected box now removes your typed value so the file / automatic baseline applies again.
- Regression-tested: with no data for the new indicators every score is identical to the previous version.

## Methodology
1. Double counting: VIX *level* removed from `crossAssetVol` (it is already inside CNN Fear & Greed).
   Replaced by VIX/VIX3M term structure + high-yield OAS (FRED BAMLH0A0HYM2).
2. Contrarian F&G at extremes (<=20 / >=80) is halved when price trend disagrees (vs 200d SMA).
3. COT: 3-year COT index (percentile of long %), weekly-shift weight halved.
4. Term structure: see 1.
5. Asset-specific FX: JP225 blends in USDJPY, GER40 blends in EURUSD (50/50 with DXY).
6. Trend filter: COUNTER-TREND tag when a directional call is against the 200d SMA.
7. Stale data: per-input age check. Stale input => slot scored 0 + badge + listed in the banner.
   Proxy F&G is excluded. Manual F&G / actuals entered today now survive a page reload.
8. Backtest: always-long baseline + edge, long vs short hit rate, effective sample size.
9. No-trade zone: unified (see bug fixes).

## Not done / unverified
- Item 6 as a full third pillar (touches history schema, UI, exports): implemented as a trend filter instead.
- Bund yield for GER40 (no free daily source verified).
- Switching COT to the TFF / disaggregated reports (could not test CFTC endpoints from the build environment).
- Network calls (FRED, CFTC, Yahoo `^VIX3M`, `JPY=X`, `EURUSD=X`) were tested against mocks only.
