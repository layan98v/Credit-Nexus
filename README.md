# Credit Nexus

### ▶ [Open the live demo](https://credit-nexus.onrender.com)
<!-- After publishing on Render, replace the link above with your own Render address if it differs. -->

> **First load can take about 1 minute.** The demo runs on a free hosting plan that sleeps when nobody has used it for 15 minutes; the first visit wakes it up. After that it responds in seconds.
>
> **Try:** `AAPL` (US) · `HSBA.L` (UK) · `TCS.NS` (India). Numbers, credit score, stress test and warnings appear first; AI commentary follows 30–90 seconds later (free AI service, one request every 30 seconds).

Credit-research dashboard prototype. Type a company or ticker → live financials, a deterministic credit score, 3-scenario stress test, probability of default, early-warning flags, live peer comparison, and AI commentary that is checked against the real numbers.

**No accounts, no API keys, no signups.**

## Use it

| Option | What you do | Needs |
|---|---|---|
| **Website** | open the link | nothing |
| **Desktop app** | double-click `CreditNexus.exe` (Mac/Linux: `CreditNexus`) | nothing — Python is packed inside |
| From source | Windows: `START.bat` · Mac/Linux: `bash start.sh` | Python 3.10+ |

### Publish it (one time, both free)
1. Upload this folder to a GitHub repository.
2. **Website:** render.com → sign in with GitHub → **New → Blueprint** → pick the repo. `render.yaml` does the rest. Free plan sleeps after 15 min idle and takes ~1 min to wake.
3. **Desktop app:** push a tag like `v4.0.0` (or Actions → *Build desktop apps* → Run). GitHub builds and tests the Windows, macOS and Linux files and attaches them to a Release. Or run `build_app.bat` on any Windows PC that has Python.
   Windows shows "Windows protected your PC" for unsigned apps → *More info → Run anyway*.

## Where the numbers come from

| Source | Provides |
|---|---|
| Yahoo Finance (yfinance) | statements (latest 12 months + quarterly balance sheet), market data, ownership, officers, headlines, analyst consensus |
| NSE India | live price / ISIN for NSE listings (optional; often throttled) |

**Markets:** US (`AAPL`), UK (`HSBA.L`) and India (`TCS.NS`, `RELIANCE.NS`). Pick a market in the search bar to restrict matches. The app shows what your search matched ("hsbc" → `HSBA.L` · HSBC Holdings plc) and offers the company's other listings. London prices quoted in pence are converted to pounds, and when the share price and the financial statements are in different currencies, market cap is converted at Yahoo's live FX rate (or left out of ratios if no rate is available) — currencies are never mixed.

A **"Data as of"** bar shows the statement period and its age, the balance-sheet date, the price time and the fetch time. **↻ Refresh now** bypasses the 10-minute cache. Statements older than 15 months are flagged.

## AI: Pollinations, free and keyless

- Endpoint: `text.pollinations.ai/openai` (Pollinations' free tier). **Limit: one request per network every 30 seconds**, best-effort, no uptime guarantee.
- So the app makes **one AI request per company** that fills every AI section (commentary, outlook, debt notes, risks, industry KPIs to watch, governance, peer names, news sentiment). Requests are queued 30 s apart, cached 10 min and shared between duplicate requests. Expect AI sections to appear 30–90 s after the data; data tabs work immediately.
- If the AI is busy or down, every number, score, stress test and warning still works.

### No invented data (strict mode)
- Credit score, stress test, default probability and warnings are pure maths on real figures.
- AI never supplies financials or ratings. Every figure the AI writes is checked against the real data at the precision written; unmatched figures are deleted and listed on the card.
- Peers: AI only names tickers; all peer figures are fetched live and non-existent tickers are dropped.
- Headlines, officers and consensus come from Yahoo; AI only tags headline sentiment.
- AI wording without numbers can still be wrong; it is labelled "AI — verify".

## Self-healing
- `run.py` installs/repairs packages, picks a free port, opens the browser when ready, and restarts the server if it crashes or stops responding.
- `/health` tests every component (AI test is opt-in to save the 30-second slot) with an **Auto-repair** button. `python check.py` does the same in a terminal.
- `python test_all.py` runs the offline suite, including end-to-end runs against a fake Yahoo Finance and a fake Pollinations (rate limits, timeouts, garbage replies, invented figures).

## Optional settings (environment variables)
`CN_AI=0` AI off · `CN_STRICT=0` keep (but flag) unverified AI figures · `CN_POLLINATIONS_KEY` lifts the 30-second limit (key from enter.pollinations.ai) · `CN_PORT` port.

## Layout
```
run.py               launcher + watchdog
backend/             API, data layer, credit engine, AI + grounding check, health page
frontend/            React source; frontend/dist is the prebuilt UI
packaging/           one-file app spec (PyInstaller)
.github/workflows/   automatic Windows/macOS/Linux app builds
render.yaml          free website deployment
tests/               end-to-end tests with fake Yahoo + fake Pollinations
```

*Prototype for research and education. Not investment advice.*
