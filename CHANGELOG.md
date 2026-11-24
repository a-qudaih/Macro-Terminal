# Macro Terminal: changes in this version

## Bug fixes
- **fetch_data.py: FRED "list index out of range".** FRED returns "." for the newest day when it has not been
  published yet. With `limit=1` the "." was filtered out and the list was empty. Now over-fetches and takes the newest
  *valid* rows. Every FRED series is isolated, so one failure no longer kills the rest, and `status.fred` names the series.
- **index.html: hardcoded actuals.** When FRED failed, `rates/cpi/unemployment/gdp` silently used values typed into the
  HTML. They are now scored 0 and flagged STALE.
- **Neutral band mismatch.** Label used +/-1.0, backtest used +/-0.8. One shared `NO_TRADE_BAND = 1.0`.
- **Pillar attribution.** A pillar scoring exactly 0.0 was counted as a miss. Now excluded from that pillar's denominator.

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
