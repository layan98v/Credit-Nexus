"""
Self-diagnosis — live checks of every component, each with a plain-English fix.
Used by /api/diagnose (health page) and `python diagnose.py`.
"""

import sys
import asyncio
import importlib


def _r(component, status, detail, fix=None):
    return {"component": component, "status": status, "detail": str(detail)[:220], "fix": fix}


async def run_full_diagnosis(orch=None, test_ai: bool = False) -> dict:
    res = []

    v = sys.version_info
    res.append(_r("Python", "ok" if v >= (3, 10) else "error", f"{v.major}.{v.minor}.{v.micro}",
                  None if v >= (3, 10) else "Install Python 3.10+ from python.org"))

    for mod in ("fastapi", "uvicorn", "httpx", "yfinance", "certifi"):
        try:
            m = importlib.import_module(mod)
            res.append(_r(f"Package {mod}", "ok", getattr(m, "__version__", "installed")))
        except ImportError:
            res.append(_r(f"Package {mod}", "error", "missing", "Click Auto-repair"))

    # Yahoo Finance — real fetch through the same code path the dashboard uses
    try:
        from data_sources import YFinanceFetcher
        b = await YFinanceFetcher().bundle("AAPL", timeout=45)
        f = b["financials"]
        res.append(_r("Yahoo Finance", "ok" if f.get("rev") else "warn",
                      f"{b['profile'].get('name')}: revenue {f.get('rev'):,.0f} {f.get('currency', '')}" if f.get("rev")
                      else "Profile OK but statements empty",
                      None if f.get("rev") else "Click Auto-repair (upgrades yfinance)"))
    except Exception as e:
        msg = f"{e.__class__.__name__}: {e}"
        fix = "Click Auto-repair to upgrade yfinance; if it persists your network may block *.finance.yahoo.com — ask IT to allow it."
        if "SSL" in msg or "certificate" in msg.lower():
            fix = "SSL interception by a corporate proxy. Click Auto-repair; if it persists ask IT to allow *.finance.yahoo.com."
        if "Too Many Requests" in msg or "429" in msg:
            fix = "Yahoo is rate-limiting this IP. Wait a few minutes; cached results keep working."
        res.append(_r("Yahoo Finance", "error", msg, fix))

    # NSE (optional)
    try:
        from data_sources import NSEDirectFetcher
        q = await NSEDirectFetcher().get_quote("RELIANCE")
        res.append(_r("NSE India", "ok" if q else "warn", f"RELIANCE price {q.get('price')}" if q else "empty reply"))
    except Exception as e:
        res.append(_r("NSE India", "warn", f"{e}", "Optional source (Indian prices only). NSE often blocks automated requests; Yahoo covers .NS tickers."))

    # AI (Pollinations, keyless). A live test uses one of the free tier's 1-per-30s slots, so it is opt-in.
    import ai_analyst
    if not ai_analyst.AI_ENABLED:
        res.append(_r("AI (Pollinations)", "skip", "Switched off (CN_AI=0)"))
    elif test_ai:
        ok, msg = await ai_analyst.ping()
        res.append(_r("AI (Pollinations)", "ok" if ok else "warn", msg,
                      None if ok else "Free AI is best-effort. Data, scores and stress tests still work; AI text retries later."))
    else:
        res.append(_r("AI (Pollinations)", "skip", f"Not tested (saves a rate-limit slot). Last error: {ai_analyst.STATE['last_error'] or 'none'}",
                      "Click 'Test AI too' to run a live check."))

    # Credit engine — deterministic self-test with known output band
    try:
        from credit_engine import generate_credit_report
        strong = {"rev": 9e11, "cogs": 5e11, "ebitda": 2e11, "ebit": 1.5e11, "ni": 8e10, "intExp": 2e10,
                  "debt": 3e11, "cash": 1e11, "ca": 4e11, "cl": 3e11, "assets": 1.5e12, "equity": 8e11,
                  "ocf": 1.8e11, "capex": 8e10, "re": 5e11, "mktCap": 2e12}
        s = generate_credit_report(strong)["summary"]
        good = s["score"] >= 70 and s["verdict"] == "APPROVE"
        res.append(_r("Credit engine", "ok" if good else "error", f"self-test score {s['score']} {s['grade']} {s['verdict']}",
                      None if good else "credit_engine.py modified or corrupted — re-extract the zip"))
    except Exception as e:
        res.append(_r("Credit engine", "error", e, "Re-extract the zip"))

    errors = sum(r["status"] == "error" for r in res)
    return {"results": res, "summary": {
        "ok": sum(r["status"] == "ok" for r in res),
        "warnings": sum(r["status"] == "warn" for r in res),
        "errors": errors, "verdict": "ready" if errors == 0 else "issues"}}


if __name__ == "__main__":
    d = asyncio.run(run_full_diagnosis())
    icons = {"ok": "OK  ", "warn": "WARN", "error": "FAIL", "skip": "SKIP"}
    for r in d["results"]:
        print(f"  [{icons[r['status']]}] {r['component']}: {r['detail']}")
        if r["fix"]:
            print(f"         fix: {r['fix']}")
    print(f"\n  {d['summary']}")
