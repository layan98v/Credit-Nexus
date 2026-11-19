"""
End-to-end test with mocked network: fake Yahoo Finance + fake LLM servers.
Exercises every API route, every provider format, failure paths and the JSON repair.
Run:  python tests/e2e_mock.py      (exit 0 = pass)
"""
import os, sys, json, threading, tempfile, types, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))
os.environ["CN_CONFIG_DIR"] = tempfile.mkdtemp()

import pandas as pd

# ── Fake Yahoo Finance ──
cols = [pd.Timestamp("2026-03-31"), pd.Timestamp("2025-03-31")]
INC = pd.DataFrame({cols[0]: {"Total Revenue": 2.55e12, "Cost Of Revenue": 1.6e12, "Gross Profit": 9.5e11, "EBITDA": 7.0e11,
                              "EBIT": 6.4e11, "Net Income": 4.8e11, "Interest Expense": -1.0e10},
                    cols[1]: {"Total Revenue": 2.4e12, "Cost Of Revenue": 1.5e12, "Gross Profit": 9.0e11, "EBITDA": 6.6e11,
                              "EBIT": 6.0e11, "Net Income": 4.6e11, "Interest Expense": -9e9}})
BS = pd.DataFrame({cols[0]: {"Total Assets": 1.6e12, "Current Assets": 1.0e12, "Current Liabilities": 4.5e11,
                             "Stockholders Equity": 9.5e11, "Total Debt": 9.0e10, "Current Debt": 1e10,
                             "Cash And Cash Equivalents": 1.2e11, "Accounts Receivable": 4.4e11, "Retained Earnings": 8.0e11},
                   cols[1]: {"Total Assets": 1.5e12, "Total Debt": 8.5e10, "Cash And Cash Equivalents": 1.0e11}})
CF = pd.DataFrame({cols[0]: {"Operating Cash Flow": 5.0e11, "Capital Expenditure": -3.5e10, "Free Cash Flow": 4.65e11},
                   cols[1]: {"Operating Cash Flow": 4.6e11, "Capital Expenditure": -3.0e10}})
INFO = {"longName": "Tata Consultancy Services Limited", "sector": "Technology", "industry": "IT Services",
        "country": "India", "financialCurrency": "INR", "currency": "INR", "marketCap": 1.2e13,
        "currentPrice": 3300.5, "heldPercentInsiders": 0.7177, "heldPercentInstitutions": 0.2, "dividendYield": 1.9,
        "targetMeanPrice": 3800, "recommendationKey": "buy", "numberOfAnalystOpinions": 40, "revenueGrowth": 0.06,
        "companyOfficers": [{"name": "Mr. K. Krithivasan", "title": "CEO & MD", "yearBorn": 1965}],
        "longBusinessSummary": "IT services company."}
NEWS = [{"id": "1", "content": {"title": "TCS wins large deal", "pubDate": "2026-11-10T08:00:00Z",
         "provider": {"displayName": "Reuters"}, "canonicalUrl": {"url": "https://example.com/a"}, "summary": "Deal."}}]

# Newer than the annual report: trailing-12-month P&L/cash flow and latest quarterly balance sheet
TQ = pd.Timestamp("2026-09-30")
TTM_INC = pd.DataFrame({TQ: {"Total Revenue": 2.62e12, "EBITDA": 7.2e11, "EBIT": 6.6e11, "Net Income": 4.9e11, "Interest Expense": 1.1e10}})
TTM_CF = pd.DataFrame({TQ: {"Operating Cash Flow": 5.1e11, "Capital Expenditure": -3.6e10}})
Q_BS = pd.DataFrame({TQ: {"Total Assets": 1.7e12, "Current Assets": 1.05e12, "Current Liabilities": 4.6e11,
                          "Stockholders Equity": 1.0e12, "Total Debt": 9.5e10, "Cash And Cash Equivalents": 1.3e11}})
OLD = [pd.Timestamp("2024-03-31")]

INTL = {  # international listings: (longName, quote currency, statement currency, price, shares)
    "2222.SR": ("Saudi Arabian Oil Company", "SAR", "SAR", 25.5, 2.42e11),   # exists on Yahoo, but out of scope
    "HSBA.L": ("HSBC Holdings plc", "GBp", "USD", 900.0, 1.8e10),
    "HSBC": ("HSBC Holdings plc ADR", "USD", "USD", 57.0, 3.6e9),
    "EMAAR.AE": ("Emaar Properties PJSC", "AED", "AED", 14.0, 8.8e9),
    "NOFX.L": ("No FX Rate plc", "GBp", "JPY", 100.0, 1e9),
}
FX = {"GBPUSD=X": 1.27}

class FakeTicker:
    def __init__(self, sym):
        self.sym = sym
        empty = pd.DataFrame()
        self.ttm_income_stmt = self.ttm_cashflow = self.quarterly_balance_sheet = empty
        if sym in FX:
            self.info = {"regularMarketPrice": FX[sym]}; self.income_stmt = self.balance_sheet = self.cashflow = empty
            self.news, self.institutional_holders = [], empty; return
        if sym.endswith("=X"):
            self.info = {}; self.income_stmt = self.balance_sheet = self.cashflow = empty
            self.news, self.institutional_holders = [], empty; return
        if sym in INTL:
            n, qc, fc, px, sh = INTL[sym]
            self.info = {**INFO, "longName": n, "currency": qc, "financialCurrency": fc, "currentPrice": px,
                         "sharesOutstanding": sh, "marketCap": px * sh, "companyOfficers": []}
            self.income_stmt, self.balance_sheet, self.cashflow = INC, BS, CF
            self.news, self.institutional_holders = [], empty
            return
        if sym in ("TCS.NS", "AAPL", "INFY.NS", "OLDCO"):
            self.info, self.income_stmt, self.balance_sheet, self.cashflow = dict(INFO), INC, BS, CF
            if sym == "TCS.NS":
                self.ttm_income_stmt, self.ttm_cashflow, self.quarterly_balance_sheet = TTM_INC, TTM_CF, Q_BS
            if sym == "INFY.NS":
                self.info["longName"] = "Infosys Limited"
            if sym == "OLDCO":  # last report long ago -> must be flagged stale
                self.info["longName"] = "Old Reporting Co"
                self.income_stmt = INC.iloc[:, :1].set_axis(OLD, axis=1)
                self.balance_sheet = BS.iloc[:, :1].set_axis(OLD, axis=1)
                self.cashflow = CF.iloc[:, :1].set_axis(OLD, axis=1)
        else:
            self.info = {"trailingPegRatio": None}
            self.income_stmt = self.balance_sheet = self.cashflow = empty
        self.news = NEWS
        self.institutional_holders = pd.DataFrame([{"Holder": "LIC", "pctHeld": 0.05, "Shares": 1}])

class FakeSearch:
    def __init__(self, q, **k):
        ql = q.lower()
        self.quotes = []
        if "tata" in ql:
            self.quotes = [{"symbol": "TCS.NS", "quoteType": "EQUITY"}]
        if "hsbc" in ql:
            self.quotes = [{"symbol": "HSBA.L", "quoteType": "EQUITY", "longname": "HSBC Holdings plc", "exchDisp": "London"},
                           {"symbol": "HSBC", "quoteType": "EQUITY", "longname": "HSBC Holdings plc", "exchDisp": "NYSE"},
                           {"symbol": "0005.HK", "quoteType": "EQUITY", "longname": "HSBC Holdings plc", "exchDisp": "Hong Kong"}]

fake_yf = types.SimpleNamespace(Ticker=FakeTicker, Search=FakeSearch, __version__="1.8.0")

# ── Fake Pollinations (OpenAI-compatible, keyless) ──
MODE = {"v": "good"}
HITS = {"n": 0, "times": []}
INSIGHTS = {
    "credit": {"rationale": "Net cash balance sheet and strong cash generation.", "strengths": ["Net cash", "High margins", "Scale"],
               "risks": ["US demand", "Pricing pressure", "Attrition"], "score": 84, "grade": "AA", "rec": "APPROVE"},
    "outlook": {"outlook": "Steady demand with stable margins.", "guidance": "", "revision": ""},
    "debt": {"capStructure": "Minimal debt; leases dominate.", "liquiditySummary": "Strong", "covenants": "Few restrictive covenants expected."},
    "risk": {"overall": "low", "risks": [{"cat": "market", "factor": "US slowdown", "sev": "med",
             "desc": "EBITDA of ₹72,000 Cr cushions a hit, but a ₹50,000 Cr acquisition was rumoured", "mitigant": "Diversified"}]},
    "industry": {"industry": "IT Services", "moat": "scale", "position": "leader", "kpis": [{"name": "Attrition", "why": "Talent cost driver"}]},
    "governance": {"quality": "strong", "governance": "Experienced board."},
    "peers": [{"name": "Infosys", "symbol": "INFY.NS"}, {"name": "Made Up Corp", "symbol": "MADEUP9.NS"}],
    "news": [{"t": "TCS wins large deal", "sent": "positive", "imp": "high", "why": "Revenue visibility"}],
    "newsSentiment": "positive",
}

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        HITS["n"] += 1; HITS["times"].append(time.time())
        m = MODE["v"]
        def send(code, obj, hdr=None):
            raw = (obj if isinstance(obj, bytes) else json.dumps(obj).encode()); self.send_response(code)
            for k, v in (hdr or {}).items(): self.send_header(k, v)
            self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(raw)))
            self.end_headers(); self.wfile.write(raw)
        if self.headers.get("Authorization"):
            return send(400, {"error": "test expects keyless calls"})
        if m == "rate_once":
            MODE["v"] = "good"
            return send(402, {"error": "Payment Required — rate limit"}, {"Retry-After": "1"})
        if m == "garbage":
            return send(200, b'["not", "an", "object"]')
        if m == "slow":
            time.sleep(5)
        prompt = body["messages"][-1]["content"]
        payload = {"ok": True} if '"ok": true' in prompt else INSIGHTS
        text = json.dumps(payload, ensure_ascii=False)
        if m == "fenced":
            text = "Sure:\n```json\n" + text + "\n```"
        send(200, {"choices": [{"message": {"content": text}}]})

srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()

import data_sources, ai_analyst
data_sources.yf, data_sources.HAS_YF = fake_yf, True
ai_analyst.URL = f"http://127.0.0.1:{srv.server_port}/openai"
ai_analyst.MIN_GAP = 0

async def no_nse(self, s): raise RuntimeError("NSE HTTP 403")
data_sources.NSEDirectFetcher.get_quote = no_nse

from fastapi.testclient import TestClient
import main

FAILS = []
def check(name, cond, info=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{'' if cond else '  -> ' + str(info)[:300]}")
    if not cond: FAILS.append(name)

def reset_ai():
    ai_analyst._CACHE.clear(); HITS["n"] = 0; HITS["times"].clear(); MODE["v"] = "good"

Q = {"company": "Tata Consultancy"}
with TestClient(main.app) as c:
    r = c.get("/", follow_redirects=False)
    check("dashboard opens directly (no setup, no key)", r.status_code == 200 and '<div id="root">' in r.text, r.status_code)
    st = c.get("/api/status").json()
    check("status: AI = Pollinations keyless", st["ai_enabled"] and "Pollinations" in st["ai"], st)
    check("health page served", c.get("/health").status_code == 200)

    a = c.get("/api/analyze", params=Q).json()
    check("search resolves name -> TCS.NS", a["profile"].get("ticker") == "TCS.NS", a["profile"])
    check("latest data: TTM P&L preferred over annual", a["financials"].get("rev") == 2.62e12 and a["financials"].get("intExp") == 1.1e10, a["financials"])
    check("latest quarterly balance sheet used", a["financials"].get("assets") == 1.7e12 and a["freshness"].get("balance_sheet_date") == "2026-09-30", a["freshness"])
    check("freshness metadata", a["freshness"].get("statements", "").startswith("Trailing 12 months to 2026-09-30") and a["freshness"].get("fetched_at"))
    check("net debt from latest balance sheet", a["financials"].get("netDebt") == -3.5e10, a["financials"].get("netDebt"))
    check("prior period = last full year", a["prev_financials"].get("rev") == 2.55e12)
    check("credit engine ran", a["credit_report"]["summary"]["score"] >= 70, a["credit_report"].get("summary"))
    check("analyze makes no AI call (fast path)", HITS["n"] == 0, HITS)
    check("NSE failure reported, not fatal", "nse" in a["source_errors"] and "yahoo" in a["sources"], a["source_errors"])
    check("no company branding in payload", ("ela"+"ra") not in json.dumps(a).lower())

    # ── international listings ──
    for q in ("2222.SR", "EMAAR.AE"):
        a = c.get("/api/analyze", params={"company": q}).json()
        check(f"out-of-scope listing {q} not offered, message names supported markets", not a["financials"].get("rev")
              and any("US, UK and Indian" in w or "US, UK or Indian" in w for w in a["warnings"]), a["warnings"])
    a = c.get("/api/analyze", params={"company": "2222.SR", "exact": "true"}).json()
    check("out-of-scope listing refused even as an exact click", not a["financials"].get("rev"), a["match"])
    h = c.get("/api/analyze", params={"company": "hsbc"}).json()
    check("'hsbc' -> London listing; NYSE offered; Hong Kong excluded", h["match"]["symbol"] == "HSBA.L" and {o["symbol"] for o in h["match"]["others"]} == {"HSBC"}, h["match"])
    check("London price converted from pence to pounds", h["holders"]["price"] == 9.0 and h["holders"]["currency"] == "GBP", h["holders"])
    check("market cap converted GBP->USD to match USD statements", abs(h["financials"]["mktCap"] - 1.8e10 * 9.0 * 1.27) < 1e3 and "GBP→USD" in h["freshness"].get("fx_note", ""), (h["financials"].get("mktCap"), h["freshness"]))
    hx = c.get("/api/analyze", params={"company": "HSBC", "exact": "true"}).json()
    check("clicking a specific listing opens exactly that ticker (not the alias)", hx["match"]["symbol"] == "HSBC", hx["match"])
    tx = c.get("/api/analyze", params={"company": "TCS"}).json()
    check("typed 'TCS' still means Tata (alias), not the US ticker", tx["match"]["symbol"] == "TCS.NS", tx["match"])
    hu = c.get("/api/analyze", params={"company": "hsbc", "market": "us"}).json()
    check("market filter US -> NYSE listing", hu["match"]["symbol"] == "HSBC" and hu["match"]["market"] == "United States", hu["match"])
    e = c.get("/api/analyze", params={"company": "hsbc", "market": "uk"}).json()
    check("market filter UK -> London listing", e["match"]["symbol"] == "HSBA.L", e["match"])
    e = c.get("/api/analyze", params={"company": "Tata Consultancy", "market": "in"}).json()
    check("market filter India -> NSE listing", e["match"]["symbol"] == "TCS.NS", e["match"])
    nf = c.get("/api/analyze", params={"company": "NOFX.L"}).json()
    check("no FX rate -> market cap left out, not mixed", nf["financials"].get("mktCap") is None and "FX rate unavailable" in nf["freshness"].get("fx_note", ""), (nf["financials"].get("mktCap"), nf["freshness"]))
    ni = c.get("/api/analyze", params={"company": "Nonexistent Widgets Pvt", "market": "in"}).json()
    check("not found in chosen market -> clear message naming the market", any("India" in w for w in ni["warnings"]), ni["warnings"])
    check("markets = US, UK, India only", [m["id"] for m in c.get("/api/markets").json()] == ["", "us", "uk", "in"])

    reset_ai()
    j = c.get("/api/insights", params=Q).json(); x = j["data"]
    check("insights: all sections in ONE request", x and all(k in x for k in ("credit", "outlook", "debt", "risk", "industry", "governance", "peers", "news")) and HITS["n"] == 1, (HITS, j))
    desc = x["risk"]["risks"][0]["desc"]
    check("grounding keeps real figure (₹72,000 Cr)", "₹72,000 Cr" in desc, desc)
    check("grounding removes invented figure (₹50,000 Cr)", "50,000" not in desc and any("50,000" in u["value"] for u in x["_unverified"]), x["_unverified"])
    check("peers: real figures fetched for AI-named ticker", any(r["symbol"] == "INFY.NS" and r["name"] == "Infosys Limited" and r.get("ebitdaM") for r in x["peers"]["rows"]), x["peers"])
    check("peers: invented ticker dropped", any("MADEUP9.NS" in d for d in x["peers"]["dropped"]), x["peers"])
    check("news = real headline + AI sentiment", x["news"][0]["t"] == "TCS wins large deal" and x["news"][0].get("sent") == "positive" and x["news"][0].get("src") == "Reuters", x["news"])
    check("officers + consensus come from real data", x["officers"][0]["name"] == "Mr. K. Krithivasan" and x["consensus"].get("recommendation") == "buy")

    c.get("/api/insights", params=Q)
    check("cached: repeat costs no request", HITS["n"] == 1, HITS)

    reset_ai()
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(3) as ex:
        res = list(ex.map(lambda _: c.get("/api/insights", params=Q).json(), range(3)))
    check("3 simultaneous requests share ONE call", HITS["n"] == 1 and all(r["data"] for r in res), HITS)

    reset_ai(); ai_analyst.MIN_GAP = 2; ai_analyst.STATE["last_call"] = 0
    c.get("/api/analyze", params={"company": "AAPL"})
    c.get("/api/insights", params=Q); c.get("/api/insights", params={"company": "AAPL"})
    gap = HITS["times"][1] - HITS["times"][0] if len(HITS["times"]) == 2 else -1
    check("free-tier spacing enforced between calls", gap >= 1.9, (gap, HITS))
    ai_analyst.MIN_GAP = 0

    reset_ai(); MODE["v"] = "rate_once"
    t = time.time(); j = c.get("/api/insights", params=Q).json()
    check("402 rate limit -> waits Retry-After and succeeds", j["data"] is not None and HITS["n"] == 2, (HITS, j.get("error")))

    reset_ai(); MODE["v"] = "fenced"
    check("reply wrapped in ```json fences parsed", c.get("/api/insights", params=Q).json()["data"] is not None)

    reset_ai(); MODE["v"] = "garbage"
    r = c.get("/api/insights", params=Q)
    check("garbage reply -> HTTP 200 + clear error", r.status_code == 200 and r.json()["data"] is None and "json" in r.json()["error"].lower(), r.text[:200])

    reset_ai(); MODE["v"] = "slow"; old = ai_analyst.CALL_TIMEOUT; ai_analyst.CALL_TIMEOUT = 2
    t = time.time(); r = c.get("/api/insights", params=Q); el = time.time() - t
    ai_analyst.CALL_TIMEOUT = old
    check("slow AI -> clear timeout message, no hang", r.status_code == 200 and "in time" in (r.json()["error"] or "") and el < 15, (el, r.text[:200]))

    reset_ai(); ai_analyst.AI_ENABLED = False
    j = c.get("/api/insights", params=Q).json(); ai_analyst.AI_ENABLED = True
    check("AI switched off -> clean message", j["data"] is None and "switched off" in j["error"], j)

    reset_ai()
    j = c.get("/api/insights", params={"company": "Nonexistent Widgets Pvt"}).json()
    check("no real data -> no AI call, explains why", j["data"] is None and HITS["n"] == 0 and "real financial data" in j["error"], (HITS, j))
    a3 = c.get("/api/analyze", params={"company": "Nonexistent Widgets Pvt"}).json()
    check("unknown company -> no invented numbers, clear warning", not a3["financials"].get("rev") and a3["warnings"] and a3["credit_report"] == {}, a3["warnings"])

    o2 = c.get("/api/analyze", params={"company": "OLDCO"}).json()
    check("stale statements flagged", o2["freshness"].get("statements_stale") and any("days old" in w for w in o2["warnings"]), o2["freshness"])
    r2 = c.get("/api/analyze", params={"company": "Tata Consultancy", "fresh": "true"}).json()
    check("forced refresh works", r2["freshness"].get("fetched_at"))
    st = c.get("/api/stress-test", params=Q).json()
    check("stress test 3 scenarios", all(k in st for k in ("base", "adverse", "severe")), st)

    INFO["companyOfficers"] = [{"name": None, "title": None}, {"name": "Real Person", "title": None}]
    main.orch.yf._cache.clear(); main.ANALYSES.clear()
    r = c.get("/api/analyze", params=Q)
    check("officer with missing name/title: no crash", r.status_code == 200 and r.json()["officers"][0]["name"] == "Real Person", r.text[:200])

    reset_ai()
    d = c.get("/api/diagnose").json()
    names = {x["component"]: x["status"] for x in d["results"]}
    check("diagnose (default) does not spend an AI call", HITS["n"] == 0 and names.get("AI (Pollinations)") == "skip", names)
    check("diagnose: credit engine + Yahoo ok", names.get("Credit engine") == "ok" and names.get("Yahoo Finance") == "ok", names)
    d = c.get("/api/diagnose", params={"ai": "true"}).json()
    names = {x["component"]: x["status"] for x in d["results"]}
    check("diagnose ?ai=true live-tests Pollinations", names.get("AI (Pollinations)") == "ok" and HITS["n"] == 1, (names, HITS))
    check("repair runs", c.post("/api/repair").json()["actions"])
    check("unknown api path -> 404 JSON", c.get("/api/nope").status_code == 404)

print(f"\n  {'ALL PASS' if not FAILS else str(len(FAILS)) + ' FAILED: ' + ', '.join(FAILS)}")
sys.exit(1 if FAILS else 0)
