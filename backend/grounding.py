"""
Grounding check for AI output.

Every figure an AI writes is compared with the real figures it was given (the context).
Figures that cannot be matched within tolerance are treated as invented:
strict mode (default) removes them from the text and records them in `_unverified`.

Exempt: years, small counts, and fields that are the AI's own judgement (score, sub-scores, grade).
"""

import re
from math import floor, log10

TOL = 0.005  # 0.5% for numbers stored without precision info
# A written figure matches a real one if the real value, rounded to the digits the AI wrote, equals it:
# "₹2.6 lakh Cr" matches 2.62e12 (2 significant digits); "₹50,000 Cr" does NOT match 5.1e11 (5 digits written).

UNITS = [  # longest first
    (r"lakh\s*crores?|lakh\s*cr|l\s*cr", 1e12), (r"trillion|tn", 1e12), (r"crores?|cr", 1e7),
    (r"billion|bn|b", 1e9), (r"million|mn|mm|m", 1e6), (r"lakhs?|lac", 1e5), (r"thousand|k", 1e3),
]
NUM_RE = re.compile(
    r"(?<![A-Za-z0-9.])(?P<cur>[$₹£€¥])?\s?(?P<num>-?\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|-?\d+(?:\.\d+)?)"
    r"\s?(?P<unit>%|x\b|" + "|".join(u for u, _ in UNITS) + r")?(?![A-Za-z0-9])",
    re.I,
)
EXEMPT_KEYS = {"score", "sb", "grade", "rec", "fin", "cf", "mkt", "mg", "ind", "ext", "year", "sev", "status", "imp", "sent",
               "name", "symbol", "ticker", "t", "title", "src", "date", "url"}


def _ref_numbers(obj, out=None):
    """All numbers in the context, including numbers inside strings like '21.3%'."""
    out = [] if out is None else out
    if isinstance(obj, bool):
        return out
    if isinstance(obj, (int, float)):
        out.append(float(obj))
    elif isinstance(obj, str):
        for m in NUM_RE.finditer(obj):
            v = _value(m)
            if v is not None:
                out.append(v)
    elif isinstance(obj, dict):
        for v in obj.values():
            _ref_numbers(v, out)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _ref_numbers(v, out)
    return out


def _value(m):
    try:
        v = float(m.group("num").replace(",", ""))
    except ValueError:
        return None
    unit = (m.group("unit") or "").lower().replace(" ", "")
    for pat, mult in UNITS:
        if unit and re.fullmatch(pat.replace(r"\s*", ""), unit):
            return v * mult
    return v


def _is_exempt(m, text):
    raw = m.group("num").replace(",", "")
    unit = (m.group("unit") or "").lower()
    try:
        v = float(raw)
    except ValueError:
        return True
    if not unit and not m.group("cur"):
        if v.is_integer() and 1900 <= v <= 2100:  # a year
            return True
        if v.is_integer() and abs(v) <= 12:       # counts, quarters, months
            return True
    start = m.start()
    if start > 0 and text[start - 1] in "QH":     # Q3, H1
        return True
    return False


def _sig(raw: str) -> int:
    d = raw.replace(",", "").replace("-", "").replace(".", "").lstrip("0")
    return max(len(d), 1)


def _round_sig(x: float, n: int) -> float:
    return x if x == 0 else round(x, -int(floor(log10(abs(x)))) + (n - 1))


def _close(c, r, n):
    if r == 0:
        return c == 0
    for a in (r, -r):
        if abs(_round_sig(a, n) - c) <= abs(c) * 1e-9 + 1e-12 or abs(c - a) / abs(a) <= TOL:
            return True
    return False


def _matches(m, refs):
    v = _value(m)
    if v is None:
        return True
    n = _sig(m.group("num"))
    unit = (m.group("unit") or "").lower()
    cands = [v]
    if unit == "%":
        cands += [v / 100]
    elif not unit and not m.group("cur"):
        cands += [v * k for k in (1e3, 1e5, 1e6, 1e7, 1e9, 1e12)]
    elif m.group("cur") and not unit:
        cands += [v * k for k in (1e7, 1e9, 1e6)]
    for c in cands:
        for r in refs:
            if _close(c, r, n):
                return True
    return False


def verify(ai: dict, context, strict: bool = True) -> dict:
    """Return ai with unverifiable figures removed (strict) or listed (non-strict) in `_unverified`."""
    if not isinstance(ai, dict):
        return ai
    refs = _ref_numbers(context)
    flagged = []

    def walk(o, path):
        if isinstance(o, dict):
            return {k: (v if k in EXEMPT_KEYS or k.startswith("_") else walk(v, f"{path}.{k}" if path else k)) for k, v in o.items()}
        if isinstance(o, list):
            return [walk(v, f"{path}[{i}]") for i, v in enumerate(o)]
        if isinstance(o, (int, float)) and not isinstance(o, bool):
            ok = any(_close(float(o), r, _sig(repr(o))) for r in refs) or (float(o).is_integer() and abs(o) <= 12)
            if not ok:
                flagged.append({"field": path, "value": str(o)})
                return None if strict else o
            return o
        if isinstance(o, str):
            def repl(m):
                if _is_exempt(m, o) or _matches(m, refs):
                    return m.group(0)
                flagged.append({"field": path, "value": m.group(0).strip()})
                return "[unverified figure removed]" if strict else m.group(0)
            return NUM_RE.sub(repl, o)
        return o

    out = walk(ai, "")
    out["_unverified"] = flagged
    out["_strict"] = strict
    return out
