#!/usr/bin/env python3
\"\"\"Daily data fetcher for the Macro Terminal. Python stdlib only.
Env: FRED_API_KEY (free, fred.stlouisfed.org). Optional file: consensus.json (your expected values; actuals FRED does not carry: ISM PMIs).
Writes data.json (for GitHub Pages / http) and data.js (for opening the HTML straight from disk).\"\"\"
import json, os, math, urllib.request, urllib.parse, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
KEY = os.environ.get("FRED_API_KEY", "")
UA = {"User-Agent": "Mozilla/5.0 (compatible; macro-terminal/1.0)"}
NOW = dt.datetime.now(dt.timezone.utc)
TODAY = NOW.date().isoformat()

YAHOO = {"US500": "^GSPC", "US100": "^NDX", "US30": "^DJI", "US2000": "^RUT",
         "GER40": "^GDAXI", "JP225": "^N225", "XAUUSD": "GC=F"}
MACRO_Y = {"us10y": "^TNX", "vix": "^VIX", "dxy": "DX-Y.NYB",
           "vix3m": "^VIX3M", "usdjpy": "JPY=X", "eurusd": "EURUSD=X"}
# CFTC legacy futures-only (non-commercial). GER40 has no CFTC contract: keep manual.
COT = {"US500": "E-MINI S&P 500%", "US100": "NASDAQ%MINI%", "US30": "DJIA%", "US2000": "RUSSELL%E-MINI%",
       "JP225": "NIKKEI%", "XAUUSD": "GOLD - COMMODITY EXCHANGE%"}

def get(url, headers=None, timeout=25):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)

def stats(xs):
    xs = [x for x in xs if isinstance(x, (int, float))]
    if len(xs) < 6: return None, None
    mu = sum(xs) / len(xs)
    return mu, math.sqrt(sum((x - mu) ** 2 for x in xs) / len(xs))

def yahoo(sym):
    d = get(f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}?interval=1d&range=1y")["chart"]["result"][0]
    c = [x for x in d["indicators"]["quote"][0]["close"] if isinstance(x, (int, float))]
    price = d["meta"].get("regularMarketPrice") or c[-1]
    prev = c[-2]  # NOT meta.chartPreviousClose (that is the close before the 1y window)
    mu, sd = stats(c[-60:])
    return dict(price=price, prevClose=prev, changePct=(price - prev) / prev * 100,
                sma50=sum(c[-50:]) / len(c[-50:]), sma200=sum(c[-200:]) / len(c[-200:]), mu=mu, sd=sd)

def fred(series, n=1):
    \"\"\"Latest n valid observations, newest first. Over-fetches because FRED returns '.' placeholders
    for days not yet published; with limit=n those placeholders were filtered out and left an empty list.\"\"\"
    q = urllib.parse.urlencode(dict(series_id=series, api_key=KEY, file_type="json", sort_order="desc", limit=n + 15))
    obs = get("https://api.stlouisfed.org/fred/series/observations?" + q)["observations"]
    vals = [(o["date"], float(o["value"])) for o in obs if o["value"] not in (".", "", None)]
    if len(vals) < n:
        raise RuntimeError(f"{series}: only {len(vals)} valid obs, need {n}")
    return vals[:n]

def cot(pattern):
    q = urllib.parse.urlencode({
        "$select": "market_and_exchange_names,report_date_as_yyyy_mm_dd,open_interest_all,noncomm_positions_long_all,noncomm_positions_short_all",
        "$where": f"upper(market_and_exchange_names) like '{pattern.upper()}'",
        "$order": "report_date_as_yyyy_mm_dd DESC", "$limit": "2500"})
    rows = get("https://publicreporting.cftc.gov/resource/6dca-aqww.json?" + q)
    latest = max(r["report_date_as_yyyy_mm_dd"] for r in rows)
    top = max((r for r in rows if r["report_date_as_yyyy_mm_dd"] == latest), key=lambda r: float(r.get("open_interest_all", 0)))
    mine = sorted((r for r in rows if r["market_and_exchange_names"] == top["market_and_exchange_names"]),
                  key=lambda r: r["report_date_as_yyyy_mm_dd"], reverse=True)
    pct = lambda r: float(r["noncomm_positions_long_all"]) / (float(r["noncomm_positions_long_all"]) + float(r["noncomm_positions_short_all"])) * 100
    hist = [pct(r) for r in mine[:156]]          # up to 3 years of weekly reports
    lo, hi = min(hist), max(hist)
    cot_index = round((hist[0] - lo) / (hi - lo) * 100, 1) if hi > lo else 50.0
    return dict(longPct=round(hist[0], 2), weeklyChangePct=round(hist[0] - pct(mine[1]), 2),
                cotIndex=cot_index, cotWeeks=len(hist),
                reportDate=latest[:10], market=top["market_and_exchange_names"])

def fear_greed(vix):
    try:
        d = get("https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
                {"Referer": "https://edition.cnn.com/", "Origin": "https://edition.cnn.com"})
        return dict(value=round(d["fear_and_greed"]["score"]), source="cnn", asOf=TODAY)
    except Exception:
        return dict(value=round(max(0, min(100, 100 - (vix - 12) / 23 * 100))), source="vix-proxy (CNN unavailable)", asOf=TODAY)

def main():
    path = os.path.join(HERE, "data.json")
    prev = json.load(open(path)) if os.path.exists(path) else {}
    out = {**prev, "updated": NOW.isoformat(), "status": {}, "macro": dict(prev.get("macro", {})),
           "prices": dict(prev.get("prices", {})), "cot": dict(prev.get("cot", {})),
           "indicators": dict(prev.get("indicators", {}))}
    st = out["status"]

    def run(name, fn):
        try: fn(); st[name] = "ok"
        except Exception as e: st[name] = f"FAILED (kept previous): {e}"

    def prices():
        for k, s in YAHOO.items(): out["prices"][k] = yahoo(s)
        for k, s in MACRO_Y.items():
            try: out["macro"][k] = yahoo(s) | {"val": None, "asOf": TODAY}
            except Exception as e: st[f"yahoo_{k}"] = f"FAILED (kept previous): {e}"
        for k in MACRO_Y:
            if "price" in out["macro"].get(k, {}): out["macro"][k]["val"] = out["macro"][k].pop("price")
    run("yahoo", prices)

    def fred_block():
        if not KEY: raise RuntimeError("FRED_API_KEY not set")
        m, failed = out["macro"], []

        def part(name, fn):
            try: fn()
            except Exception as e: failed.append(f"{name}: {e}")

        def level(key, series):
            d, v = fred(series)[0]; m[key] = {"val": v, "asOf": d}
        def level_z(key, series, n):
            obs = fred(series, n); mu, sd = stats([v for _, v in obs]); m[key] = {"val": obs[0][1], "mu": mu, "sd": sd, "asOf": obs[0][0]}
        def ind(key, fn):
            v = fn(); out["indicators"].setdefault(key, {})["actual"] = round(v, 2)

        part("us2y", lambda: level("us2y", "DGS2"))
        part("be10", lambda: level("be10", "T10YIE"))
        part("real10y", lambda: level_z("real10y", "DFII10", 60))
        part("hyOAS", lambda: level_z("hyOAS", "BAMLH0A0HYM2", 250))      # high-yield credit spread (%)
        part("rates", lambda: ind("rates", lambda: fred("DFEDTARU")[0][1]))
        part("unemployment", lambda: ind("unemployment", lambda: fred("UNRATE")[0][1]))
        part("gdp", lambda: ind("gdp", lambda: fred("A191RL1Q225SBEA")[0][1]))
        part("nfp", lambda: ind("nfp", lambda: (lambda o: o[0][1] - o[1][1])(fred("PAYEMS", 2))))              # monthly change, thousands
        part("retail", lambda: ind("retail", lambda: (lambda o: (o[0][1] / o[1][1] - 1) * 100)(fred("RSAFS", 2))))  # headline retail sales, MoM %
        part("ppi", lambda: ind("ppi", lambda: (lambda c: (c[0][1] / c[12][1] - 1) * 100)(fred("PPIFIS", 13))))      # PPI final demand, YoY %
        part("pce", lambda: ind("pce", lambda: (lambda c: (c[0][1] / c[12][1] - 1) * 100)(fred("PCEPILFE", 13))))   # CORE PCE price index, YoY %

        def claims():
            o = fred("ICSA", 5)                                              # weekly initial claims (persons) -> thousands
            c = out["indicators"].setdefault("claims", {})
            c["actual"] = round(o[0][1] / 1000, 1)
            c["expectedProxy"] = round(sum(v for _, v in o[1:5]) / 4 / 1000, 1)   # prior 4-week average: stand-in when no consensus is given
        part("claims", claims)
        part("cpi", lambda: ind("cpi", lambda: (lambda c: (c[0][1] / c[12][1] - 1) * 100)(fred("CPIAUCSL", 13))))
        if failed: raise RuntimeError(" | ".join(failed))
    run("fred", fred_block)

    def cot_block():
        for k, p in COT.items():
            try: out["cot"][k] = cot(p)
            except Exception as e: st[f"cot_{k}"] = f"FAILED (kept previous): {e}"
    run("cftc", cot_block)

    vix = out["macro"].get("vix", {}).get("val") or 20
    out["fearGreed"] = fear_greed(vix)

    # Consensus / PMI overrides you (or a Claude scheduled task) maintain
    cons = {}
    cp = os.path.join(HERE, "consensus.json")
    if os.path.exists(cp): cons = json.load(open(cp))
    for k, v in cons.get("actual", {}).items(): out["indicators"].setdefault(k, {})["actual"] = v
    for k, v in cons.get("expected", {}).items(): out["indicators"].setdefault(k, {})["expected"] = v
    as_of = cons.get("asOf", "1970-01-01")
    for k, v in out["indicators"].items():
        old = prev.get("indicators", {}).get(k, {})
        if v.get("actual") != old.get("actual") or "releaseISO" not in v:
            v["releaseISO"] = TODAY
        else:
            v["releaseISO"] = old.get("releaseISO", TODAY)
        v["releaseISO"] = cons.get("releaseISO", {}).get(k, v["releaseISO"])  # your real release dates win
        v["releaseDate"] = dt.date.fromisoformat(v["releaseISO"]).strftime("%b %d")
        v["needsConsensus"] = v["releaseISO"] > as_of
        if k == "claims" and v.get("expected") is None: v["needsConsensus"] = False   # weekly: the 4-week-average proxy applies, so no weekly nag

    json.dump(out, open(path, "w"), indent=1)
    open(os.path.join(HERE, "data.js"), "w").write("window.AUTO_DATA = " + json.dumps(out) + ";\n")
    print(json.dumps(st, indent=1))

if __name__ == "__main__":
    main()
