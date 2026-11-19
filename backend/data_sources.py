"""
Data layer: Yahoo Finance -> NSE India.
Only real, sourced data. Every section carries _sources so the UI shows provenance.
All sources are free and keyless.
"""

import time
import asyncio
import logging
from typing import Optional

log = logging.getLogger("data_sources")

try:
    import yfinance as yf
    HAS_YF = True
except ImportError:  # autofix installs it
    yf = None
    HAS_YF = False

try:
    import httpx
except ImportError:
    httpx = None

# Common names -> Yahoo symbols (skips a search round-trip; search handles everything else)
ALIASES = {
    "reliance": "RELIANCE.NS", "reliance industries": "RELIANCE.NS", "reliance ind": "RELIANCE.NS",
    "tcs": "TCS.NS", "tata consultancy services": "TCS.NS",
    "hdfc bank": "HDFCBANK.NS", "icici bank": "ICICIBANK.NS", "sbi": "SBIN.NS",
    "state bank of india": "SBIN.NS", "infosys": "INFY.NS", "adani ports": "ADANIPORTS.NS",
    "bharti airtel": "BHARTIARTL.NS", "airtel": "BHARTIARTL.NS", "l&t": "LT.NS",
    "larsen & toubro": "LT.NS", "larsen and toubro": "LT.NS", "tata steel": "TATASTEEL.NS",
    "tata motors": "TATAMOTORS.NS", "itc": "ITC.NS", "wipro": "WIPRO.NS",
    "apple": "AAPL", "microsoft": "MSFT", "amazon": "AMZN", "alphabet": "GOOGL", "google": "GOOGL",
    "tesla": "TSLA", "hsbc": "HSBA.L",
    "bp": "BP.L", "shell": "SHEL.L", "unilever": "ULVR.L", "barclays": "BARC.L", "astrazeneca": "AZN.L",
    "lloyds": "LLOY.L", "vodafone": "VOD.L", "gsk": "GSK.L", "rio tinto": "RIO.L", "tesco": "TSCO.L",
    "jpmorgan": "JPM", "jp morgan": "JPM", "nvidia": "NVDA", "meta": "META", "berkshire hathaway": "BRK-B",
    "exxon": "XOM", "exxonmobil": "XOM", "goldman sachs": "GS", "coca cola": "KO", "boeing": "BA",
}

# Supported markets (prototype scope: US, UK, India). Listings elsewhere are not offered.
MARKETS = {
    "us": {"label": "United States", "suffix": (), "exch": ("nasdaq", "nyse", "nysearca", "amex", "nms", "nyq", "ngm", "ncm", "ase", "pcx", "bats")},
    "uk": {"label": "United Kingdom", "suffix": (".L", ".IL"), "exch": ("london", "lse")},
    "in": {"label": "India", "suffix": (".NS", ".BO"), "exch": ("nse", "bse", "bombay", "national stock exchange of india")},
}
MINOR_UNITS = {"GBp": ("GBP", 100), "GBX": ("GBP", 100), "ZAc": ("ZAR", 100), "ILA": ("ILS", 100)}


def _in_market(sym: str, exch: str, market: str) -> bool:
    m = MARKETS.get(market)
    if not m:  # "any" = any SUPPORTED market
        return any(_in_market(sym, exch, k) for k in MARKETS)
    if market == "us":
        return "." not in sym or any(e == (exch or "").lower() for e in m["exch"])
    return sym.upper().endswith(m["suffix"]) or any(e in (exch or "").lower() for e in m["exch"])

CACHE_TTL = 600  # seconds


def _num(v) -> Optional[float]:
    try:
        f = float(v)
        return None if f != f else f  # NaN -> None
    except (TypeError, ValueError):
        return None


def _pct(v) -> str:
    f = _num(v)
    return f"{f * 100:.1f}%" if f is not None else ""


def _row(df, col: int, *names):
    """First non-null value among row names in a yfinance statement column."""
    if df is None or getattr(df, "empty", True) or df.shape[1] <= col:
        return None
    for n in names:
        if n in df.index:
            v = _num(df.iloc[:, col].get(n))
            if v is not None:
                return v
    return None


def _statement_set(inc, bs, cf, col: int) -> dict:
    d = {
        "rev": _row(inc, col, "Total Revenue", "Operating Revenue"),
        "cogs": _row(inc, col, "Cost Of Revenue"),
        "gp": _row(inc, col, "Gross Profit"),
        "ebitda": _row(inc, col, "EBITDA", "Normalized EBITDA"),
        "ebit": _row(inc, col, "EBIT", "Operating Income"),
        "ni": _row(inc, col, "Net Income", "Net Income Common Stockholders"),
        "intExp": _row(inc, col, "Interest Expense", "Interest Expense Non Operating"),
        "assets": _row(bs, col, "Total Assets"),
        "ca": _row(bs, col, "Current Assets"),
        "cl": _row(bs, col, "Current Liabilities"),
        "equity": _row(bs, col, "Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest"),
        "debt": _row(bs, col, "Total Debt"),
        "stDebt": _row(bs, col, "Current Debt", "Current Debt And Capital Lease Obligation"),
        "cash": _row(bs, col, "Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"),
        "inv": _row(bs, col, "Inventory"),
        "recv": _row(bs, col, "Accounts Receivable", "Receivables"),
        "pay": _row(bs, col, "Accounts Payable", "Payables"),
        "re": _row(bs, col, "Retained Earnings"),
        "ocf": _row(cf, col, "Operating Cash Flow", "Cash Flow From Continuing Operating Activities"),
        "capex": _row(cf, col, "Capital Expenditure"),
        "fcf": _row(cf, col, "Free Cash Flow"),
        "icf": _row(cf, col, "Investing Cash Flow"),
    }
    if d["intExp"] is not None:
        d["intExp"] = abs(d["intExp"])
    if d["capex"] is not None:
        d["capex"] = abs(d["capex"])
    if d["debt"] is not None and d["cash"] is not None:
        d["netDebt"] = d["debt"] - d["cash"]
    try:
        d["period"] = str(inc.columns[col].date()) if inc is not None and inc.shape[1] > col else ""
    except Exception:
        d["period"] = ""
    return {k: v for k, v in d.items() if v not in (None, "")}


FLOW_KEYS = ("rev", "cogs", "gp", "ebitda", "ebit", "ni", "intExp", "ocf", "capex", "fcf", "icf")
STOCK_KEYS = ("assets", "ca", "cl", "equity", "debt", "stDebt", "cash", "inv", "recv", "pay", "re")
STALE_DAYS = 456  # > 15 months since the period end = older than one full reporting cycle


def _col_date(df, col: int = 0):
    try:
        if df is not None and not df.empty and df.shape[1] > col:
            return df.columns[col].date()
    except Exception:
        pass
    return None


class YFinanceFetcher:
    """Yahoo Finance via yfinance. One network bundle per company, cached 10 min."""

    def __init__(self):
        self._cache: dict = {}

    def candidates(self, query: str, market: str = "", exact: bool = False) -> list:
        """Ranked Yahoo listings for a name or ticker: [{symbol, name, exchange}]. Market filter applied when given."""
        q = query.strip()
        out, seen = [], set()

        def add(sym, name="", exch=""):
            if sym and sym.upper() not in seen and _in_market(sym, exch, market):
                seen.add(sym.upper()); out.append({"symbol": sym, "name": name, "exchange": exch})

        if exact:  # an exact listing was clicked: open precisely that ticker (if in a supported market)
            if _in_market(q.upper(), "", ""):
                seen.add(q.upper()); out.append({"symbol": q.upper(), "name": "", "exchange": ""})
        elif q.lower() in ALIASES:
            add(ALIASES[q.lower()])
        if " " not in q and (q.isupper() or "." in q or any(ch.isdigit() for ch in q)) and len(q) <= 15:
            add(q.upper())
        try:
            res = yf.Search(q, max_results=10, news_count=0)
            for x in (res.quotes or []):
                if x.get("quoteType") == "EQUITY":
                    add(x.get("symbol"), x.get("longname") or x.get("shortname") or "", x.get("exchDisp") or x.get("exchange") or "")
        except Exception as e:
            log.info(f"yfinance search failed for {q}: {e}")
        if not out and not market and " " not in q and "." not in q:
            add(q.upper())  # bare US-style ticker Yahoo search didn't index
        return out

    def resolve(self, query: str, market: str = "") -> Optional[str]:
        c = self.candidates(query, market)
        return c[0]["symbol"] if c else None

    def _fx(self, src: str, dst: str) -> Optional[float]:
        """Live FX rate from Yahoo (e.g. GBPUSD=X). Cached with the data cache."""
        if src == dst:
            return 1.0
        key = f"fx:{src}{dst}"
        hit = self._cache.get(key)
        if hit and time.time() - hit[0] < CACHE_TTL:
            return hit[1]
        rate = None
        try:
            i = yf.Ticker(f"{src}{dst}=X").info or {}
            rate = _num(i.get("regularMarketPrice") or i.get("previousClose"))
        except Exception as e:
            log.info(f"FX {src}->{dst} unavailable: {e}")
        self._cache[key] = (time.time(), rate)
        return rate

    def _bundle(self, query: str, fresh: bool = False, market: str = "", exact: bool = False) -> dict:
        key = f"{query.strip().lower()}|{market}|{exact}"
        hit = self._cache.get(key)
        if hit and not fresh and time.time() - hit[0] < CACHE_TTL:
            return hit[1]

        cands = self.candidates(query, "" if exact else market, exact)
        if not cands:
            where = f" in {MARKETS[market]['label']}" if market in MARKETS else ""
            raise LookupError(f"No US, UK or Indian listing found for '{query}'{where} on Yahoo Finance")
        t, info, sym, tried = None, {}, None, []
        for c in (cands[:1] if exact else cands[:4]):  # first candidate that actually has data
            tried.append(c["symbol"])
            tt = yf.Ticker(c["symbol"])
            ii = tt.info or {}
            if ii.get("longName") or ii.get("shortName"):
                t, info, sym = tt, ii, c["symbol"]
                break
        if not sym:
            raise LookupError(f"Yahoo Finance has no data for '{query}' (tried {', '.join(tried)})")
        others = [c for c in cands if c["symbol"].upper() != sym.upper()][:6]

        def safe(attr):
            try:
                return getattr(t, attr)
            except Exception as e:
                log.info(f"{sym}.{attr} unavailable: {e}")
                return None

        inc, bs, cf = safe("income_stmt"), safe("balance_sheet"), safe("cashflow")
        cur = info.get("financialCurrency") or info.get("currency") or ""

        # Most recent figures first: trailing-12-month P&L / cash flow and latest quarterly balance sheet,
        # when Yahoo has them and they are newer than the last annual report.
        annual = _statement_set(inc, bs, cf, 0)
        fin = dict(annual)
        prev = _statement_set(inc, bs, cf, 1)
        ann_date = _col_date(inc) or _col_date(bs)
        flow_basis, flow_date = (f"FY ending {ann_date}", ann_date) if ann_date else ("", None)
        bs_date = _col_date(bs)
        ttm_inc, ttm_cf, q_bs = safe("ttm_income_stmt"), safe("ttm_cashflow"), safe("quarterly_balance_sheet")
        t_date = _col_date(ttm_inc)
        if t_date and (not ann_date or t_date > ann_date):
            ttm = _statement_set(ttm_inc, None, ttm_cf, 0)
            if ttm.get("rev") or ttm.get("ni"):
                for k in FLOW_KEYS:
                    if k in ttm:
                        fin[k] = ttm[k]
                flow_basis, flow_date = f"Trailing 12 months to {t_date}", t_date
                prev = annual  # compare TTM against the last full year
        q_date = _col_date(q_bs)
        if q_date and (not bs_date or q_date > bs_date):
            q = _statement_set(None, q_bs, None, 0)
            if q.get("assets"):
                for k in STOCK_KEYS:
                    if k in q:
                        fin[k] = q[k]
                bs_date = q_date
        if fin.get("debt") is not None and fin.get("cash") is not None:
            fin["netDebt"] = fin["debt"] - fin["cash"]
        fin["period"] = flow_basis
        today = time.gmtime()
        import datetime as _dt
        age = (_dt.date(today.tm_year, today.tm_mon, today.tm_mday) - flow_date).days if flow_date else None
        px_t = info.get("regularMarketTime")
        freshness = {
            "fetched_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
            "statements": flow_basis,
            "statements_age_days": age,
            "statements_stale": bool(age is not None and age > STALE_DAYS),
            "balance_sheet_date": str(bs_date) if bs_date else "",
            "price_time": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(px_t)) if isinstance(px_t, (int, float)) else "",
            "source": "Yahoo Finance",
        }
        # Price/market cap are in the QUOTE currency; statements in financialCurrency. Never mix them.
        qcur = info.get("currency") or cur
        price = _num(info.get("currentPrice") or info.get("regularMarketPrice"))
        mk_q = _num(info.get("marketCap"))
        if qcur in MINOR_UNITS:  # e.g. London prices in pence (GBp)
            major, div = MINOR_UNITS[qcur]
            price = price / div if price is not None else None
            sh = _num(info.get("sharesOutstanding"))
            mk_q = sh * price if sh and price else mk_q
            qcur = major
        fx_note, mk = "", mk_q
        if mk_q is not None and cur and qcur and qcur != cur:
            rate = self._fx(qcur, cur)
            if rate:
                mk = mk_q * rate
                fx_note = f"Market cap converted {qcur}→{cur} at {rate:.4g} (Yahoo FX)"
            else:
                mk, fx_note = None, f"Market cap is in {qcur} but statements are in {cur}; FX rate unavailable, so it is left out of ratios"
        fin.update({k: v for k, v in {
            "mktCap": mk,
            "eps": _num(info.get("trailingEps")),
            "revGr": _pct(info.get("revenueGrowth")),
            "gpM": _pct(info.get("grossMargins")),
            "ebitdaM": _pct(info.get("ebitdaMargins")),
            "evEbitda": _num(info.get("enterpriseToEbitda")),
            "pe": _num(info.get("trailingPE")),
            "pbv": _num(info.get("priceToBook")),
            "pRev": _num(info.get("priceToSalesTrailing12Months")),
            "roe": _pct(info.get("returnOnEquity")),
            "currency": cur,
        }.items() if v not in (None, "")})
        if fin.get("debt") and fin.get("ebitda"):
            fin["ndEbitda"] = round((fin["debt"] - fin.get("cash", 0)) / fin["ebitda"], 2)
        if prev.get("debt") and fin.get("debt"):
            ch = (fin["debt"] - prev["debt"]) / abs(prev["debt"]) * 100
            fin["debtTrend"] = f"{'↑' if ch > 0 else '↓'} {abs(ch):.0f}% YoY"
        if prev.get("cash") and fin.get("cash"):
            ch = (fin["cash"] - prev["cash"]) / abs(prev["cash"]) * 100
            fin["cashTrend"] = f"{'↑' if ch > 0 else '↓'} {abs(ch):.0f}% YoY"

        profile = {k: v for k, v in {
            "name": info.get("longName") or info.get("shortName"),
            "ticker": sym,
            "exchange": info.get("exchange"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "country": info.get("country"),
            "employees": info.get("fullTimeEmployees"),
            "summary": (info.get("longBusinessSummary") or "")[:700],
            "website": info.get("website"),
            "currency": cur,
            "nseCode": sym[:-3] if sym.endswith(".NS") else "",
            "bseCode": sym[:-3] if sym.endswith(".BO") else "",
        }.items() if v not in (None, "")}

        holders = {k: v for k, v in {
            "promoter": _pct(info.get("heldPercentInsiders")),
            "fii": _pct(info.get("heldPercentInstitutions")),
            "price": price,
            "sharesOut": _num(info.get("sharesOutstanding")),
            "freeFloat": _num(info.get("floatShares")),
            "divYield": f"{_num(info.get('dividendYield')):.2f}%" if _num(info.get("dividendYield")) is not None else "",
            "currency": qcur,
        }.items() if v not in (None, "")}
        top = []
        ih = safe("institutional_holders")
        try:
            if ih is not None and not ih.empty:
                for _, r in ih.head(6).iterrows():
                    pct = _num(r.get("pctHeld"))
                    top.append({"name": str(r.get("Holder", "")), "stake": f"{pct * 100:.2f}%" if pct is not None else ""})
        except Exception:
            pass
        holders["holders"] = top

        officers = [
            {"name": o.get("name") or "", "title": o.get("title") or "",
             "since": str(o.get("yearBorn") and f"b. {o['yearBorn']}" or ""),
             "pay": o.get("totalPay")}
            for o in (info.get("companyOfficers") or [])[:8] if isinstance(o, dict) and o.get("name")
        ]

        news = []
        for n in (safe("news") or [])[:8]:
            c = n.get("content") if isinstance(n.get("content"), dict) else n
            title = c.get("title", "")
            if not title:
                continue
            prov = c.get("provider")
            url = (c.get("canonicalUrl") or {}).get("url") if isinstance(c.get("canonicalUrl"), dict) else c.get("link", "")
            pub = c.get("pubDate") or ""
            if not pub and c.get("providerPublishTime"):
                pub = time.strftime("%Y-%m-%d", time.gmtime(c["providerPublishTime"]))
            news.append({
                "t": title,
                "src": prov.get("displayName", "") if isinstance(prov, dict) else (c.get("publisher") or ""),
                "date": str(pub)[:10],
                "url": url or "",
                "sum": (c.get("summary") or "")[:300],
            })

        consensus = {k: v for k, v in {
            "targetMean": _num(info.get("targetMeanPrice")),
            "targetHigh": _num(info.get("targetHighPrice")),
            "targetLow": _num(info.get("targetLowPrice")),
            "recommendation": info.get("recommendationKey"),
            "analysts": info.get("numberOfAnalystOpinions"),
            "forwardEps": _num(info.get("forwardEps")),
            "forwardPE": _num(info.get("forwardPE")),
            "earningsGrowth": _pct(info.get("earningsGrowth")),
            "revenueGrowth": _pct(info.get("revenueGrowth")),
        }.items() if v not in (None, "", "none")}

        match = {"query": query.strip(), "symbol": sym, "name": profile.get("name"), "exchange": info.get("fullExchangeName") or info.get("exchange") or "",
                 "quote_currency": qcur, "statement_currency": cur, "fx_note": fx_note, "others": others,
                 "market": "" if exact else MARKETS.get(market, {}).get("label", ""), "exact": exact}
        bundle = {"symbol": sym, "match": match, "freshness": freshness, "profile": profile, "financials": fin, "prev_financials": prev,
                  "holders": holders, "officers": officers, "news": news, "consensus": consensus}
        self._cache[key] = (time.time(), bundle)
        return bundle

    async def bundle(self, query: str, timeout: float = 60, fresh: bool = False, market: str = "", exact: bool = False) -> dict:
        if not HAS_YF:
            raise RuntimeError("yfinance not installed")
        return await asyncio.wait_for(asyncio.to_thread(self._bundle, query, fresh, market, exact), timeout)


class NSEDirectFetcher:
    """nseindia.com public quote endpoint — keyless, needs a cookie warm-up, often rate-limited."""

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com/",
    }

    async def get_quote(self, symbol: str) -> dict:
        if httpx is None or not symbol:
            return {}
        async with httpx.AsyncClient(timeout=8, follow_redirects=True, headers=self.HEADERS) as c:
            await c.get("https://www.nseindia.com/")
            r = await c.get(f"https://www.nseindia.com/api/quote-equity?symbol={symbol.upper()}")
            if r.status_code != 200:
                raise RuntimeError(f"NSE HTTP {r.status_code}")
            d = r.json()
        info, px = d.get("info", {}), d.get("priceInfo", {})
        return {k: v for k, v in {
            "isin": info.get("isin"), "industry": info.get("industry"),
            "price": _num(px.get("lastPrice")), "nseCode": info.get("symbol"),
        }.items() if v not in (None, "")}


def _merge(base: dict, overlay: dict) -> dict:
    """Fill only empty fields; never overwrite a higher-priority source."""
    for k, v in (overlay or {}).items():
        if k.startswith("_") or v in (None, "", [], {}):
            continue
        if base.get(k) in (None, "", [], {}, 0):
            base[k] = v
    return base


class DataOrchestrator:
    def __init__(self):
        self.yf = YFinanceFetcher()
        self.nse = NSEDirectFetcher()

    async def get_all(self, company: str, fresh: bool = False, market: str = "", exact: bool = False) -> dict:
        out = {"profile": {}, "financials": {}, "prev_financials": {}, "holders": {},
               "officers": [], "news": [], "consensus": {}, "sources": [], "errors": {}, "freshness": {}}

        # 1. Yahoo Finance
        try:
            y = await self.yf.bundle(company, fresh=fresh, market=market, exact=exact)
            out["match"] = y.get("match", {})
            out["freshness"] = y.get("freshness", {})
            for sec in ("profile", "financials", "prev_financials", "holders", "consensus"):
                _merge(out[sec], y[sec])
            out["officers"] = out["officers"] or y["officers"]
            out["news"] = y["news"]
            out["sources"].append("yahoo")
        except Exception as e:
            out["errors"]["yahoo"] = f"{e.__class__.__name__}: {str(e)[:200]}"

        # 2. NSE India (Indian listings only)
        sym = out["profile"].get("nseCode")
        if sym:
            try:
                n = await self.nse.get_quote(sym)
                if n:
                    _merge(out["profile"], n)
                    _merge(out["holders"], {"price": n.get("price")})
                    out["sources"].append("nse")
            except Exception as e:
                out["errors"]["nse"] = str(e)[:200]

        return out
