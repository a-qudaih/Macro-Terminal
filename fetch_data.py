#!/usr/bin/env python3
"""Daily data fetcher for the Macro Terminal. Python stdlib only.
Env: FRED_API_KEY (free, fred.stlouisfed.org). Optional file: consensus.json (your expected values / PMI actual).
Writes data.json (for GitHub Pages / http) and data.js (for opening the HTML straight from disk)."""
import json, os, math, urllib.request, urllib.parse, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
KEY = os.environ.get("FRED_API_KEY", "")
UA = {"User-Agent": "Mozilla/5.0 (compatible; macro-terminal/1.0)"}
NOW = dt.datetime.now(dt.timezone.utc)
TODAY = NOW.date().isoformat()

YAHOO = {"US500": "^GSPC", "US100": "^NDX", "US30": "^DJI", "US2000": "^RUT",
         "GER40": "^GDAXI", "JP225": "^N225", "XAUUSD": "GC=F"}
MACRO_Y = {"us10y": "^TNX", "vix": "^VIX", "dxy": "DX-Y.NYB"}
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
    q = urllib.parse.urlencode(dict(series_id=series, api_key=KEY, file_type="json", sort_order="desc", limit=n))
    obs = get("https://api.stlouisfed.org/fred/series/observations?" + q)["observations"]
    return [(o["date"], float(o["value"])) for o in obs if o["value"] != "."]

def cot(pattern):
    q = urllib.parse.urlencode({"$where": f"upper(market_and_exchange_names) like '{pattern.upper()}'",
                                "$order": "report_date_as_yyyy_mm_dd DESC", "$limit": "60"})
    rows = get("https://publicreporting.cftc.gov/resource/6dca-aqww.json?" + q)
    latest = max(r["report_date_as_yyyy_mm_dd"] for r in rows)
    top = max((r for r in rows if r["report_date_as_yyyy_mm_dd"] == latest), key=lambda r: float(r.get("open_interest_all", 0)))
    mine = sorted((r for r in rows if r["market_and_exchange_names"] == top["market_and_exchange_names"]),
                  key=lambda r: r["report_date_as_yyyy_mm_dd"], reverse=True)
    pct = lambda r: float(r["noncomm_positions_long_all"]) / (float(r["noncomm_positions_long_all"]) + float(r["noncomm_positions_short_all"])) * 100
    return dict(longPct=round(pct(mine[0]), 2), weeklyChangePct=round(pct(mine[0]) - pct(mine[1]), 2),
                reportDate=latest[:10], market=top["market_and_exchange_names"])

def fear_greed(vix):
    try:
        d = get("https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
                {"Referer": "https://edition.cnn.com/", "Origin": "https://edition.cnn.com"})
        return dict(value=round(d["fear_and_greed"]["score"]), source="cnn")
    except Exception:
        return dict(value=round(max(0, min(100, 100 - (vix - 12) / 23 * 100))), source="vix-proxy (CNN unavailable)")

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
        for k, s in MACRO_Y.items(): out["macro"][k] = yahoo(s) | {"val": None}
        for k in MACRO_Y: out["macro"][k]["val"] = out["macro"][k].pop("price")
    run("yahoo", prices)

    def fred_block():
        if not KEY: raise RuntimeError("FRED_API_KEY not set")
        m = out["macro"]
        m["us2y"] = {"val": fred("DGS2")[0][1]}
        ry = fred("DFII10", 60); mu, sd = stats([v for _, v in ry])
        m["real10y"] = {"val": ry[0][1], "mu": mu, "sd": sd}
        m["be10"] = {"val": fred("T10YIE")[0][1]}
        cpi = fred("CPIAUCSL", 13)
        vals = {"rates": fred("DFEDTARU")[0][1], "cpi": round((cpi[0][1] / cpi[12][1] - 1) * 100, 2),
                "unemployment": fred("UNRATE")[0][1], "gdp": fred("A191RL1Q225SBEA")[0][1]}
        for k, v in vals.items(): out["indicators"].setdefault(k, {})["actual"] = round(v, 2)
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
        v["releaseDate"] = dt.date.fromisoformat(v["releaseISO"]).strftime("%b %d")
        v["needsConsensus"] = v["releaseISO"] > as_of

    json.dump(out, open(path, "w"), indent=1)
    open(os.path.join(HERE, "data.js"), "w").write("window.AUTO_DATA = " + json.dumps(out) + ";\n")
    print(json.dumps(st, indent=1))

if __name__ == "__main__":
    main()
