# Macro & Sentiment Terminal v7

Rebuilt version with the following upgrades over v6:

## Key Improvements

### 1. Scoring Model
- **Driver Attribution**: Every asset card and the inspector show the top positive and negative contributors to the score.
- **Data Quality Multiplier**: Scores built on fresher, more complete data are trusted more. Stale or missing inputs reduce confidence instead of silently diluting.
- **Improved Risk Appetite**: Blends Fear & Greed (CNN or improved VIX-term + HY OAS proxy) with term structure and credit.
- **Cleaner Channel Logic**: Labor = avg(Unemployment, NFP), Growth = avg(GDP, ISM Mfg, ISM Services, Retail) with proper exclusion of missing/stale.

### 2. History & Edge Measurement
- Forward return distributions by score bucket
- Regime-conditioned hit rates
- Simple expectancy calculation
- High-conviction (≥ ±1.5) vs neutral performance
- Pillar attribution (Fundamental vs Sentiment)

### 3. Architecture
- Much cleaner internal structure (scoring, state, rendering separated conceptually)
- Better separation of pure scoring functions vs UI
- Model version tracked on every history snapshot

### 4. UX / Data Quality
- Clearer freshness and quality badges
- Explicit "why is this score what it is" on every asset
- Improved stale / needs-input handling
- Regime note + quantitative regime bias still present

### How to use
1. Run `python fetch_data.py` (requires `FRED_API_KEY` env var) to refresh `data.json` + `data.js`
2. Open `index.html` in a browser (works from disk via data.js, or via any static host)
3. Use **Log Snapshot** to record current scores into the performance history
4. Switch to **Score History & Performance** tab for analytics

### Files
- `index.html` — the terminal
- `fetch_data.py` — daily data fetcher (Yahoo + FRED + CFTC)
- `data.json` / `data.js` — latest snapshot
- `consensus.json` — your expected values + release dates for non-FRED series

---

Built as a focused evolution of the original Macro Terminal.
