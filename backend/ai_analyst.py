"""
AI layer — Pollinations, keyless (no signup).  https://text.pollinations.ai/openai

Pollinations' free tier allows ONE request per IP at least 30 s apart (excess -> HTTP 402 + Retry-After).
So the app asks ONE combined question per company that fills every AI section, queues calls to respect
the spacing, caches answers for 10 minutes, and shares one in-flight call between duplicate requests.

Every figure in the answer is checked against the real data (grounding.verify) — strict mode.
Optional env: CN_POLLINATIONS_KEY (enter.pollinations.ai) lifts the rate limit; CN_AI=0 turns AI off.
"""

import os
import re
import json
import time
import asyncio
import hashlib
import logging

import httpx

from grounding import verify

log = logging.getLogger("ai_analyst")

KEY = os.environ.get("CN_POLLINATIONS_KEY", "").strip()
URL = os.environ.get("CN_AI_URL") or ("https://gen.pollinations.ai/v1/chat/completions" if KEY else "https://text.pollinations.ai/openai")
MODELS = ["openai", None]           # None = let the service pick its default model
MIN_GAP = 0 if KEY else 31          # seconds between calls on the free tier
CALL_TIMEOUT = 120
AI_ENABLED = os.environ.get("CN_AI", "1") != "0"
STRICT = os.environ.get("CN_STRICT", "1") != "0"
CACHE_TTL = 600

STATE = {"last_call": 0.0, "queue": 0, "last_error": ""}
_LOCKS: dict = {}


def _lock() -> asyncio.Lock:
    """One lock per event loop (tests and servers may run several loops)."""
    loop = asyncio.get_running_loop()
    if id(loop) not in _LOCKS:
        _LOCKS[id(loop)] = asyncio.Lock()
    return _LOCKS[id(loop)]
_CACHE: dict = {}
_INFLIGHT: dict = {}

INSIGHTS_PROMPT = """You are a senior credit analyst. Company: "{c}". Today is {today}.
REAL DATA (the only facts you may use): {ctx}

Return ONE JSON object, no markdown, with exactly these keys:
{{
 "credit": {{"rationale": "2-3 sentences", "strengths": ["", "", ""], "risks": ["", "", ""], "score": 1-100, "grade": "AAA..D", "rec": "APPROVE|CONDITIONAL|DECLINE"}},
 "outlook": {{"outlook": "2 sentences", "guidance": "", "revision": ""}},
 "debt": {{"capStructure": "1-2 sentences", "liquiditySummary": "1 sentence", "covenants": "1 sentence on typical covenant risks for this profile"}},
 "risk": {{"overall": "high|med|low", "risks": [{{"cat": "market|credit|operational|regulatory|country|ESG", "factor": "", "sev": "high|med|low", "desc": "1 sentence", "mitigant": ""}}]}},
 "industry": {{"industry": "", "moat": "", "position": "", "kpis": [{{"name": "sector-specific KPI to watch", "why": "1 sentence"}}]}},
 "governance": {{"quality": "strong|adequate|weak", "governance": "1-2 sentences"}},
 "peers": [{{"name": "", "symbol": "exact Yahoo Finance ticker of a US, UK or Indian listing: US no suffix (JPM), London .L (HSBA.L), India .NS (INFY.NS)"}}],
 "news": [{{"t": "headline copied exactly", "sent": "positive|neutral|negative", "imp": "high|med|low", "why": "1 short sentence"}}],
 "newsSentiment": "positive|neutral|negative"
}}
Rules: 4 risks, 3 KPIs, 5 peers, one news entry per headline given (none if no headlines).
Use ONLY figures that appear in the REAL DATA; otherwise describe qualitatively. Never invent numbers, dates,
ratings, deals or events. Unknown -> empty string. Figures not found in the real data are deleted automatically."""


def extract_json(text: str):
    """First JSON object in free text; tolerates code fences, preamble and truncation."""
    if not text:
        return None
    t = re.sub(r"```(?:json)?", "", text).strip()
    start = t.find("{")
    if start < 0:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(t[start:])
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    s = t[start:]
    s = re.sub(r',\s*"[^"]*$', "", s)
    s = re.sub(r':\s*"[^"]*$', ': ""', s)
    s = re.sub(r",\s*$", "", s)
    stack, in_str, esc = [], False, False
    for ch in s:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]" and stack:
            stack.pop()
    s += ('"' if in_str else "") + "".join(reversed(stack))
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None


async def _post(body: dict):
    headers = {"Content-Type": "application/json"}
    if KEY:
        headers["Authorization"] = f"Bearer {KEY}"
    async with httpx.AsyncClient(timeout=CALL_TIMEOUT) as client:
        r = await client.post(URL, headers=headers, json=body)
    try:
        data = r.json()
    except Exception:
        data = {"_raw": r.text[:4000]}
    return r.status_code, data, r.headers


def _text_of(data) -> str:
    if isinstance(data, dict):
        ch = data.get("choices")
        if isinstance(ch, list) and ch and isinstance(ch[0], dict):
            return (ch[0].get("message") or {}).get("content") or ""
        return data.get("_raw", "")
    return ""


async def ask_json(prompt: str, max_wait: float = 240) -> tuple:
    """Queue behind other calls (30 s spacing); retry after 402/429; fall back to the service's default model.
    Returns (obj|None, error|None)."""
    if not AI_ENABLED:
        return None, "AI is switched off on this server."
    deadline = time.monotonic() + max_wait
    STATE["queue"] += 1
    try:
        async with _lock():
            last = "no response"
            for model in MODELS:
                for attempt in range(2):
                    gap = STATE["last_call"] + MIN_GAP - time.time()
                    if gap > 0:
                        if time.monotonic() + gap > deadline - 20:
                            return None, "Free AI is busy (1 request per 30 s). Press Retry shortly."
                        await asyncio.sleep(gap)
                    body = {"messages": [{"role": "system", "content": "Reply with JSON only."},
                                         {"role": "user", "content": prompt}], "temperature": 0.2}
                    if model:
                        body["model"] = model
                    STATE["last_call"] = time.time()
                    try:
                        code, data, hdrs = await _post(body)
                    except httpx.TimeoutException:
                        last = "Pollinations did not answer in time"
                        break
                    except httpx.HTTPError as e:
                        last = f"Could not reach Pollinations ({e.__class__.__name__}) — check internet/firewall"
                        break
                    if code == 200:
                        obj = extract_json(_text_of(data))
                        if obj is not None:
                            return obj, None
                        last = "Pollinations reply was not valid JSON"
                        break
                    msg = str((data.get("error") if isinstance(data, dict) else "") or data)[:200]
                    if code in (402, 429):
                        try:
                            wait = float(hdrs.get("retry-after") or MIN_GAP or 30)
                        except ValueError:
                            wait = 30.0
                        STATE["last_call"] = time.time() + wait - MIN_GAP  # push the next slot back
                        last = "Free AI rate limit (1 request per 30 s per network)"
                        continue
                    if code in (400, 404) and model and "model" in msg.lower():
                        last = f"model '{model}' not accepted"
                        break  # try the service's default model
                    last = f"Pollinations HTTP {code}: {msg}"
                    break
            return None, last
    finally:
        STATE["queue"] -= 1


async def get_insights(company: str, context: dict) -> tuple:
    """All AI sections for one company in one call. Returns (insights|None, error|None). Cached + de-duplicated."""
    ctx = json.dumps(context, default=str)[:3500]
    ck = hashlib.sha256(f"{company.lower()}|{ctx}".encode()).hexdigest()
    hit = _CACHE.get(ck)
    if hit and time.time() - hit[0] < CACHE_TTL:
        return hit[1], None
    if ck in _INFLIGHT:
        return await asyncio.shield(_INFLIGHT[ck])
    fut = asyncio.get_running_loop().create_future()
    _INFLIGHT[ck] = fut
    try:
        prompt = INSIGHTS_PROMPT.format(c=company, today=time.strftime("%Y-%m-%d"), ctx=ctx)
        obj, err = await ask_json(prompt)
        if obj is not None and not any(k in obj for k in ("credit", "risk", "outlook", "peers")):
            obj, err = None, "AI reply did not contain the expected sections"
        if obj is not None:
            obj = verify(obj, context, STRICT)
            obj["_source"] = "ai"
            _CACHE[ck] = (time.time(), obj)
        STATE["last_error"] = err or ""
        fut.set_result((obj, err))
        return obj, err
    except Exception as e:  # never let a bad reply crash a request
        log.exception("insights failed")
        res = (None, f"AI step failed ({e.__class__.__name__})")
        fut.set_result(res)
        return res
    finally:
        _INFLIGHT.pop(ck, None)


async def ping() -> tuple:
    """Tiny live check (uses one rate-limit slot)."""
    obj, err = await ask_json('Return exactly this JSON: {"ok": true}', max_wait=90)
    return (obj is not None), (err or "Pollinations answered")
