# Macro Terminal v7 — Changes from v6

## Architecture
- Cleaner, more maintainable single-file structure (~920 lines vs ~2800)
- Scoring logic separated into pure-ish functions (easier to test and evolve)
- Model version (`7.0`) stamped on every history snapshot

## Scoring Model
- **Driver Attribution**: Every asset shows top drivers; full breakdown in Inspector
- **Data Quality Multiplier**: Scores are pulled toward neutral when data is stale or incomplete
- **Improved Risk Appetite proxy**: When CNN is down, blends VIX level + term structure (VIX/VIX3M) + HY OAS instead of a pure VIX linear map
- Regime still controls the sign of growth/labor surprises (hawkish = good data is bad for multiples)

## History & Edge
- Directional hit rate
- High-conviction (≥ ±1.5) hit rate
- Simple expectancy (direction-adjusted average return)
- Regime-conditioned split (Inflation vs Growth hit rates)
- Follow-up price entry still supported for measuring real forward performance

## Data Pipeline (fetch_data.py)
- Fear & Greed fallback now uses VIX + term structure + credit
- `modelVersion` field written into data.json
- Same robust FRED over-fetch + isolation behavior as v6

## Intentionally simplified vs v6
- Removed the full Beta Matrix modal UI (betas are still used, defaults are institutional; can be re-exposed later)
- Removed some of the more elaborate manual override sliders (can be added back on top of the cleaner core)
- Focused on signal quality and attribution rather than every possible control surface

## Not yet done (future)
- Automated consensus scraping
- Full modular ES modules / build step
- Market-structure / volume-profile context layer
- More rigorous walk-forward validation
