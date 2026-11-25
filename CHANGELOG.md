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
