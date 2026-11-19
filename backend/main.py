"""
Credit Nexus — credit research dashboard API.
Real data (Yahoo Finance / NSE) -> deterministic credit engine -> one grounded AI pass (Pollinations, keyless).
Run: python run.py   (or: uvicorn main:app --port 8000)
"""

import sys
import asyncio
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from autofix import auto_fix_all
startup_actions = auto_fix_all()  # must run before third-party imports below

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from data_sources import DataOrchestrator, MARKETS
import ai_analyst
from config import PUBLIC
from credit_engine import generate_credit_report, run_stress_test

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("credit-nexus")

VERSION = "4.0.0"
BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))  # _MEIPASS = unpacked one-file app
PAGES = BASE / "pages"
DIST = next((d for d in (BASE / "frontend_dist", BASE.parent / "frontend" / "dist") if (d / "index.html").exists()),
            BASE.parent / "frontend" / "dist")

orch = DataOrchestrator()
ANALYSES: dict = {}  # company(lower) -> last analysis (context for the AI pass)


@asynccontextmanager
async def lifespan(app: FastAPI):
    for a in startup_actions:
        log.info(f"autofix: {a}")
    yield


app = FastAPI(title="Credit Nexus", version=VERSION, lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(Exception)
async def any_error(request, exc):
    """Unexpected bugs become a readable JSON message instead of a bare 500 page."""
    log.exception(f"Unhandled error on {request.url.path}")
    return JSONResponse(status_code=500, content={"error": f"Server error ({exc.__class__.__name__}: {str(exc)[:200]}). Press Retry, or open Health."})


# ── Health ──

@app.get("/health")
async def health_page():
    return HTMLResponse((PAGES / "health.html").read_text(encoding="utf-8"))


@app.get("/api/markets")
async def markets():
    return [{"id": "", "label": "Any market"}] + [{"id": k, "label": v["label"]} for k, v in MARKETS.items()]


@app.get("/api/status")
async def status():
    return {"version": VERSION, "public": PUBLIC, "ai_enabled": ai_analyst.AI_ENABLED, "ai": "Pollinations (free, no key)",
            "ai_queue": ai_analyst.STATE["queue"], "strict": ai_analyst.STRICT,
            "startup_fixes": startup_actions}


@app.get("/api/diagnose")
async def diagnose(ai: bool = False):
    from diagnose import run_full_diagnosis
    return await run_full_diagnosis(orch, test_ai=ai)


@app.post("/api/repair")
async def repair():
    actions = [] if PUBLIC else await asyncio.to_thread(auto_fix_all)
    orch.yf._cache.clear()
    actions.append("Cleared data cache")
    return {"actions": actions}


# ── Analysis (real data + maths only; fast) ──

@app.get("/api/analyze")
async def analyze(company: str = Query(..., min_length=1, max_length=80), fresh: bool = False, market: str = "", exact: bool = False):
    company = company.strip()
    market = market if market in MARKETS else ""
    log.info(f"Analyze: {company}{f' [{market}]' if market else ''}{' (forced refresh)' if fresh else ''}")
    data = await orch.get_all(company, fresh=fresh, market=market, exact=exact)
    fin, warnings = data["financials"], []

    if not (fin.get("rev") or fin.get("assets")):
        yerr = data["errors"].get("yahoo", "")
        if "LookupError" in yerr:
            warnings.append(f"'{company}' was not found on Yahoo Finance{' in ' + MARKETS[market]['label'] if market else ''}. "
                            "This prototype covers US, UK and Indian listings. Try the exact ticker: US AAPL · UK HSBA.L · India TCS.NS.")
        elif yerr:
            warnings.append("Yahoo Finance could not be reached (network, firewall or rate limit). Open Health for the exact cause.")
        warnings.append("No financial data found for this company from any source.")
        report = {}
    else:
        report = generate_credit_report(fin, data["prev_financials"] or None)

    fr = data.get("freshness") or {}
    if (data.get("match") or {}).get("fx_note"):
        fr = {**fr, "fx_note": data["match"]["fx_note"]}
    if fr.get("statements_stale"):
        warnings.append(f"Latest financial statements on Yahoo Finance are {fr['statements_age_days']} days old "
                        f"({fr['statements']}). The company may have reported since — check its filings.")

    payload = {
        "company": company, "match": data.get("match", {}), "sources": data["sources"], "source_errors": data["errors"],
        "profile": data["profile"], "financials": fin, "prev_financials": data["prev_financials"],
        "holders": data["holders"], "credit_report": report,
        "officers": data["officers"], "news": data["news"], "consensus": data["consensus"],
        "warnings": warnings, "ai_enabled": ai_analyst.AI_ENABLED, "strict": ai_analyst.STRICT,
        "freshness": fr,
    }
    ANALYSES[company.lower()] = payload
    if payload["match"].get("symbol"):
        ANALYSES[payload["match"]["symbol"].lower()] = payload
    return payload


@app.get("/api/stress-test")
async def stress_test(company: str = Query(...)):
    a = ANALYSES.get(company.strip().lower()) or await analyze(company)
    if not (a["financials"].get("rev") and a["financials"].get("ebitda")):
        return {"error": "Insufficient financial data for a stress test"}
    return run_stress_test(a["financials"])


# ── AI insights: one grounded call per company ──

def _context(a: dict) -> dict:
    f, p = a.get("financials", {}), a.get("profile", {})
    keys = ("currency", "period", "rev", "ebitda", "ebit", "ni", "debt", "cash", "netDebt", "equity", "assets",
            "intExp", "ocf", "capex", "fcf", "mktCap", "revGr", "ebitdaM", "gpM", "roe", "pe", "evEbitda")
    ctx = {"company": {k: p.get(k) for k in ("name", "ticker", "sector", "industry", "country") if p.get(k)},
           "financials": {k: f[k] for k in keys if f.get(k) not in (None, "")}}
    s = (a.get("credit_report") or {}).get("summary")
    if s:
        dp = a["credit_report"].get("default_probability", {})
        ctx["model"] = {"score": s.get("score"), "grade": s.get("grade"), "verdict": s.get("verdict"),
                        "stress": s.get("stress_resilience"), "pd": dp.get("blended_pd"),
                        "warnings": [w["flag"] for w in a["credit_report"].get("early_warnings", [])][:6]}
    if a.get("consensus"):
        ctx["consensus"] = a["consensus"]
    if a.get("officers"):
        ctx["officers"] = [f"{o.get('name') or '?'} — {o.get('title') or '?'}" for o in a["officers"]][:6]
    if a.get("news"):
        ctx["headlines"] = [n["t"] for n in a["news"]][:8]
    return ctx


def _metrics(f: dict) -> dict:
    def div(a, b, k=1):
        try:
            return round(f[a] / f[b] * k, 2) if f.get(a) is not None and f.get(b) else None
        except (TypeError, ZeroDivisionError):
            return None
    nd = (f.get("debt") or 0) - (f.get("cash") or 0) if f.get("debt") is not None else None
    return {"mktCap": f.get("mktCap"), "rev": f.get("rev"), "currency": f.get("currency", ""),
            "ebitdaM": div("ebitda", "rev", 100), "de": div("debt", "equity"), "roe": div("ni", "equity", 100),
            "ndEbitda": round(nd / f["ebitda"], 2) if nd is not None and f.get("ebitda") else None,
            "intCover": div("ebit", "intExp"), "period": f.get("period", "")}


async def _live_peers(a: dict, named: list) -> dict:
    """AI only NAMES peers; every figure is fetched live. Tickers that don't exist are dropped."""
    own = (a.get("profile") or {}).get("ticker", "").upper()
    named = [p for p in named if isinstance(p, dict) and p.get("symbol") and str(p["symbol"]).upper() != own][:6]

    async def one(p):
        try:
            b = await orch.yf.bundle(str(p["symbol"]), timeout=45)
            return {"name": b["profile"].get("name"), "symbol": b["symbol"], **_metrics(b["financials"]), "live": True}
        except Exception:
            return {"name": p.get("name", ""), "symbol": p["symbol"], "live": False}

    rows = await asyncio.gather(*(one(p) for p in named))
    live = [x for x in rows if x["live"]]
    me = {"name": (a.get("profile") or {}).get("name", a.get("company")), "symbol": own,
          **_metrics(a.get("financials", {})), "live": True, "self": True}

    def med(k):
        v = sorted(x[k] for x in live if isinstance(x.get(k), (int, float)))
        return v[len(v) // 2] if v else None
    return {"rows": [me] + live, "dropped": [f"{x['name']} ({x['symbol']})" for x in rows if not x["live"]],
            "medians": {k: med(k) for k in ("ebitdaM", "de", "roe", "ndEbitda", "intCover")}}


INSIGHTS_DEADLINE = 280  # seconds: may include waiting in the free-tier queue


@app.get("/api/insights")
async def insights(company: str = Query(...)):
    a = ANALYSES.get(company.strip().lower()) or await analyze(company)
    if not ai_analyst.AI_ENABLED:
        return {"data": None, "error": "AI commentary is switched off on this server."}
    if not (a["financials"].get("rev") or a["financials"].get("assets")):
        return {"data": None, "error": "No real financial data for this company, so no AI commentary (it would have nothing to stand on)."}
    try:
        ins, err = await asyncio.wait_for(ai_analyst.get_insights(company.strip(), _context(a)), INSIGHTS_DEADLINE)
    except asyncio.TimeoutError:
        return {"data": None, "error": "The free AI took too long. Press Retry."}
    if not ins:
        return {"data": None, "error": err}
    out = dict(ins)
    # Merge with real data: headlines, officers, consensus and peer figures are never AI-generated.
    tags = {x.get("t"): x for x in (ins.get("news") or []) if isinstance(x, dict)}
    out["news"] = [{**n, **{k: tags.get(n["t"], {}).get(k) for k in ("sent", "imp", "why") if tags.get(n["t"], {}).get(k)}}
                   for n in a.get("news", [])]
    out["officers"] = a.get("officers", [])
    out["consensus"] = a.get("consensus", {})
    try:
        out["peers"] = await asyncio.wait_for(_live_peers(a, ins.get("peers") or []), 60)
    except Exception:
        out["peers"] = {"rows": [], "dropped": [], "medians": {}, "error": "Peer data could not be fetched in time."}
    return {"data": out, "error": None}


# ── Frontend ──

if (DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")


@app.get("/{path:path}")
async def frontend(path: str):
    if path.startswith("api/"):
        return JSONResponse({"error": "Not found"}, status_code=404)
    f = DIST / path
    if path and f.is_file():
        return FileResponse(f)
    if (DIST / "index.html").exists():
        return FileResponse(DIST / "index.html")
    return HTMLResponse("<h3>Frontend build missing: run <code>npm run build</code> in frontend/</h3>", status_code=500)
