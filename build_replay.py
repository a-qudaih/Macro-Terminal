#!/usr/bin/env python3
\"\"\"Builds a point-in-time historical replay dataset (replay_data.json & replay_data.js)
from Yahoo Finance, FRED, and CFTC so index.html can jump to any past date and
compare its bias score against actual subsequent price moves.\"\"\"

import argparse
import datetime as dt
import json
import math
import os
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
KEY = os.environ.get("FRED_API_KEY", "")
UA = {"User-Agent": "Mozilla/5.0 (compatible; macro-terminal-replay/1.0)"}

YAHOO_ASSETS = {
    "US500": "^GSPC",
    "US100": "^NDX",
    "US30": "^DJI",
    "US2000": "^RUT",
    "GER40": "^GDAXI",
    "JP225": "^N225",
    "XAUUSD": "GC=F",
}

YAHOO_MACRO = {
    "us10y": "^TNX",
    "vix": "^VIX",
    "dxy": "DX-Y.NYB",
    "vix3m": "^VIX3M",
    "usdjpy": "JPY=X",
    "eurusd": "EURUSD=X",
}

COT_PATTERNS = {
    "US500": "E-MINI S&P 500%",
    "US100": "NASDAQ%MINI%",
    "US30": "DJIA%",
    "US2000": "RUSSELL%E-MINI%",
    "JP225": "NIKKEI%",
    "XAUUSD": "GOLD - COMMODITY EXCHANGE%",
}


def get_json(url, headers=None, timeout=30):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def stats(xs):
    clean = [float(x) for x in xs if isinstance(x, (int, float)) and not math.isnan(x)]
    if len(clean) < 6:
        return None, None
    mu = sum(clean) / len(clean)
    sd = math.sqrt(sum((x - mu) ** 2 for x in clean) / len(clean))
    return mu, sd


def fetch_yahoo_series(symbol, range_str="3y"):
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{urllib.parse.quote(symbol)}?interval=1d&range={range_str}"
    )
    data = get_json(url)
    res = data["chart"]["result"][0]
    timestamps = res.get("timestamp") or []
    closes = res["indicators"]["quote"][0].get("close") or []
    rows = []
    for ts, c in zip(timestamps, closes):
        if isinstance(c, (int, float)) and not math.isnan(c):
            d_str = dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc).date().isoformat()
            rows.append((d_str, float(c)))
    by_date = {}
    for d_str, c in rows:
        by_date[d_str] = c
    return sorted(by_date.items())


def fetch_fred_series(series_id, start_date="2021-01-01"):
    if not KEY:
        return []
    params = urllib.parse.urlencode({
        "series_id": series_id,
        "api_key": KEY,
        "file_type": "json",
        "sort_order": "asc",
        "observation_start": start_date,
    })
    obs = get_json("https://api.stlouisfed.org/fred/series/observations?" + params)["observations"]
    out = []
    for o in obs:
        if o["value"] not in (".", "", None):
            try:
                out.append((o["date"], float(o["value"])))
            except ValueError:
                pass
    return out


def fetch_cot_history(pattern):
    q = urllib.parse.urlencode({
        "$select": (
            "market_and_exchange_names,report_date_as_yyyy_mm_dd,"
            "open_interest_all,noncomm_positions_long_all,noncomm_positions_short_all"
        ),
        "$where": f"upper(market_and_exchange_names) like '{pattern.upper()}'",
        "$order": "report_date_as_yyyy_mm_dd ASC",
        "$limit": "5000",
    })
    rows = get_json("https://publicreporting.cftc.gov/resource/6dca-aqww.json?" + q)
    if not rows:
        return []
    by_date = {}
    for r in rows:
        d = r["report_date_as_yyyy_mm_dd"][:10]
        oi = float(r.get("open_interest_all") or 0)
        if d not in by_date or oi > by_date[d]["oi"]:
            lng = float(r.get("noncomm_positions_long_all") or 0)
            sht = float(r.get("noncomm_positions_short_all") or 0)
            tot = lng + sht
            long_pct = (lng / tot * 100.0) if tot > 0 else 50.0
            by_date[d] = {
                "date": d,
                "oi": oi,
                "longPct": round(long_pct, 2),
                "market": r.get("market_and_exchange_names", ""),
            }
    return [by_date[k] for k in sorted(by_date.keys())]


def latest_on_or_before(series, target_date):
    return [(d, v) for (d, v) in series if d <= target_date]


def yoy_on_or_before(series, target_date):
    sub = latest_on_or_before(series, target_date)
    if len(sub) < 13:
        return None
    cur_d, cur_v = sub[-1]
    _, prev_v = sub[-13]
    if prev_v == 0:
        return None
    return cur_d, round((cur_v / prev_v - 1.0) * 100.0, 2)


def mom_on_or_before(series, target_date):
    sub = latest_on_or_before(series, target_date)
    if len(sub) < 2:
        return None
    cur_d, cur_v = sub[-1]
    _, prev_v = sub[-2]
    if prev_v == 0:
        return None
    return cur_d, round((cur_v / prev_v - 1.0) * 100.0, 2)


def build_snapshot_for_date(target_date, raw):
    prices_out = {}
    for aid, series in raw["asset_prices"].items():
        sub = latest_on_or_before(series, target_date)
        if len(sub) < 2:
            continue
        closes = [v for _, v in sub]
        price = closes[-1]
        prev = closes[-2]
        mu, sd = stats(closes[-60:])
        sma50 = sum(closes[-50:]) / len(closes[-50:])
        sma200 = sum(closes[-200:]) / len(closes[-200:])
        prices_out[aid] = {
            "asOf": sub[-1][0],
            "price": round(price, 4),
            "prevClose": round(prev, 4),
            "changePct": round((price - prev) / prev * 100.0, 4) if prev else 0.0,
            "sma50": round(sma50, 4),
            "sma200": round(sma200, 4),
            "mu": round(mu, 4) if mu is not None else None,
            "sd": round(sd, 4) if sd is not None else None,
        }

    macro_out = {}
    for mk, series in raw["macro_prices"].items():
        sub = latest_on_or_before(series, target_date)
        if not sub:
            continue
        closes = [v for _, v in sub]
        val = closes[-1]
        prev = closes[-2] if len(closes) >= 2 else val
        mu, sd = stats(closes[-60:])
        macro_out[mk] = {
            "val": round(val, 4),
            "prevClose": round(prev, 4),
            "changePct": round((val - prev) / prev * 100.0, 4) if prev else 0.0,
            "mu": round(mu, 4) if mu is not None else None,
            "sd": round(sd, 4) if sd is not None else None,
            "asOf": sub[-1][0],
        }

    fred = raw["fred"]
    for key, sid in [("us2y", "DGS2"), ("be10", "T10YIE")]:
        sub = latest_on_or_before(fred.get(sid, []), target_date)
        if sub:
            macro_out[key] = {"val": sub[-1][1], "asOf": sub[-1][0]}

    for key, sid, win in [("real10y", "DFII10", 60), ("hyOAS", "BAMLH0A0HYM2", 250)]:
        sub = latest_on_or_before(fred.get(sid, []), target_date)
        if sub:
            mu, sd = stats([v for _, v in sub[-win:]])
            macro_out[key] = {
                "val": sub[-1][1],
                "mu": round(mu, 4) if mu is not None else None,
                "sd": round(sd, 4) if sd is not None else None,
                "asOf": sub[-1][0],
            }

    cot_out = {}
    for aid, rows in raw["cot"].items():
        sub = [r for r in rows if r["date"] <= target_date]
        if not sub:
            continue
        cur = sub[-1]
        prev = sub[-2] if len(sub) >= 2 else cur
        win156 = [r["longPct"] for r in sub[-156:]]
        lo, hi = min(win156), max(win156)
        cot_idx = round((cur["longPct"] - lo) / (hi - lo) * 100.0, 1) if hi > lo else 50.0
        cot_out[aid] = {
            "longPct": cur["longPct"],
            "weeklyChangePct": round(cur["longPct"] - prev["longPct"], 2),
            "cotIndex": cot_idx,
            "cotWeeks": len(win156),
            "reportDate": cur["date"],
            "market": cur["market"],
        }

    indicators_out = {}
    rates_sub = latest_on_or_before(fred.get("DFEDTARU", []), target_date)
    if rates_sub:
        indicators_out["rates"] = {"actual": rates_sub[-1][1], "releaseISO": rates_sub[-1][0]}

    unemp_sub = latest_on_or_before(fred.get("UNRATE", []), target_date)
    if unemp_sub:
        indicators_out["unemployment"] = {"actual": unemp_sub[-1][1], "releaseISO": unemp_sub[-1][0]}

    gdp_sub = latest_on_or_before(fred.get("A191RL1Q225SBEA", []), target_date)
    if gdp_sub:
        indicators_out["gdp"] = {"actual": gdp_sub[-1][1], "releaseISO": gdp_sub[-1][0]}

    nfp_sub = latest_on_or_before(fred.get("PAYEMS", []), target_date)
    if len(nfp_sub) >= 2:
        indicators_out["nfp"] = {
            "actual": round(nfp_sub[-1][1] - nfp_sub[-2][1], 1),
            "releaseISO": nfp_sub[-1][0],
        }

    retail_mom = mom_on_or_before(fred.get("RSAFS", []), target_date)
    if retail_mom:
        indicators_out["retail"] = {"actual": retail_mom[1], "releaseISO": retail_mom[0]}

    for key, sid in [("cpi", "CPIAUCSL"), ("ppi", "PPIFIS"), ("pce", "PCEPILFE")]:
        yoy = yoy_on_or_before(fred.get(sid, []), target_date)
        if yoy:
            indicators_out[key] = {"actual": yoy[1], "releaseISO": yoy[0]}

    claims_sub = latest_on_or_before(fred.get("ICSA", []), target_date)
    if len(claims_sub) >= 5:
        prior4 = sum(v for _, v in claims_sub[-5:-1]) / 4.0 / 1000.0
        indicators_out["claims"] = {
            "actual": round(claims_sub[-1][1] / 1000.0, 1),
            "expectedProxy": round(prior4, 1),
            "releaseISO": claims_sub[-1][0],
        }

    for k, v in indicators_out.items():
        d_iso = v["releaseISO"]
        v["releaseDate"] = dt.date.fromisoformat(d_iso).strftime("%b %d")
        v["needsConsensus"] = v.get("expected") is None and v.get("expectedProxy") is None

    vix_val = macro_out.get("vix", {}).get("val") or 20.0
    fg_proxy = round(max(0.0, min(100.0, 100.0 - (vix_val - 12.0) / 23.0 * 100.0)))

    return {
        "date": target_date,
        "macro": macro_out,
        "prices": prices_out,
        "cot": cot_out,
        "indicators": indicators_out,
        "fearGreed": {"value": fg_proxy, "source": "vix-proxy (historical replay)", "asOf": target_date},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2024-01-01", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", default=dt.date.today().isoformat(), help="End date YYYY-MM-DD")
    parser.add_argument("--range", dest="yahoo_range", default="3y", help="Yahoo chart range (e.g. 2y, 3y, 5y)")
    args = parser.parse_args()

    raw = {
        "asset_prices": {k: fetch_yahoo_series(s, args.yahoo_range) for k, s in YAHOO_ASSETS.items()},
        "macro_prices": {k: fetch_yahoo_series(s, args.yahoo_range) for k, s in YAHOO_MACRO.items()},
        "fred": {},
        "cot": {k: fetch_cot_history(p) for k, p in COT_PATTERNS.items()},
    }

    if KEY:
        fred_ids = [
            "DGS2", "T10YIE", "DFII10", "BAMLH0A0HYM2",
            "DFEDTARU", "UNRATE", "A191RL1Q225SBEA", "PAYEMS",
            "RSAFS", "CPIAUCSL", "PPIFIS", "PCEPILFE", "ICSA",
        ]
        for sid in fred_ids:
            try:
                raw["fred"][sid] = fetch_fred_series(sid, start_date="2021-01-01")
            except Exception as e:
                print(f"FRED warning ({sid}): {e}")
                raw["fred"][sid] = []

    bench = raw["asset_prices"].get("US500") or next(iter(raw["asset_prices"].values()))
    trading_dates = [d for d, _ in bench if args.start <= d <= args.end]

    snapshots = {d: build_snapshot_for_date(d, raw) for d in trading_dates}
    payload = {
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(),
        "start": args.start,
        "end": args.end,
        "dates": trading_dates,
        "snapshots": snapshots,
    }

    json_path = os.path.join(HERE, "replay_data.json")
    js_path = os.path.join(HERE, "replay_data.js")
    with open(json_path, "w") as f:
        json.dump(payload, f)
    with open(js_path, "w") as f:
        f.write("window.REPLAY_DATA = " + json.dumps(payload) + ";\n")

    print(f"Wrote {len(trading_dates)} dates ({args.start} to {args.end}) to replay_data.json & replay_data.js")


if __name__ == "__main__":
    main()
