"""
Credit Analysis Engine — Credit Nexus
Deterministic credit risk analysis on hard financial data.
No AI involved — auditable, reproducible, explainable.

Modules:
1. Credit Scoring Model (weighted multi-factor, 0-100)
2. Stress Testing (base/adverse/severe scenarios)
3. Default Probability (Altman Z, Merton-inspired, empirical mapping)
4. Credit Migration Risk (upgrade/downgrade probability)
5. Peer Benchmarking (percentile ranking vs sector)
6. Early Warning System (deterioration flags)
7. Recovery Rate Estimation (LGD)
"""

import math
import logging
from typing import Optional

log = logging.getLogger("credit_engine")


def _n(v) -> float:
    """Parse any value to float, return 0 on failure."""
    if v is None or v == "":
        return 0.0
    try:
        s = str(v).replace(",", "").replace("%", "").strip()
        # Handle suffixes
        mult = 1
        su = s.upper()
        if su.endswith("T"): mult = 1e12; s = s[:-1]
        elif su.endswith("B"): mult = 1e9; s = s[:-1]
        elif su.endswith("CR"): mult = 1e7; s = s[:-2]
        elif su.endswith("M"): mult = 1e6; s = s[:-1]
        elif su.endswith("L"): mult = 1e5; s = s[:-1]
        elif su.endswith("K"): mult = 1e3; s = s[:-1]
        return float(s) * mult
    except:
        return 0.0


def _r(num: float, den: float) -> Optional[float]:
    """Safe ratio."""
    if den == 0:
        return None
    return round(num / den, 4)


def _pct(num: float, den: float) -> Optional[float]:
    """Safe percentage."""
    if den == 0:
        return None
    return round((num / den) * 100, 2)


# ═══════════════════════════════════════════════
# 1. CREDIT SCORING MODEL
# ═══════════════════════════════════════════════

# Scoring rubric: each metric maps to a 0-10 score
# based on credit-quality thresholds

METRIC_RUBRICS = {
    "nd_ebitda": {  # Net Debt / EBITDA
        "thresholds": [1, 2, 3, 4, 5, 7],
        "scores":     [10, 8, 6, 4, 2, 1, 0],
        "lower_is_better": True,
    },
    "interest_coverage": {  # EBIT / Interest
        "thresholds": [1, 2, 3, 5, 8, 12],
        "scores":     [0, 1, 3, 5, 7, 9, 10],
        "lower_is_better": False,
    },
    "dscr": {  # FCF / Interest
        "thresholds": [0.5, 1, 1.25, 1.5, 2, 3],
        "scores":     [0, 1, 3, 5, 7, 9, 10],
        "lower_is_better": False,
    },
    "current_ratio": {
        "thresholds": [0.5, 0.8, 1, 1.2, 1.5, 2.5],
        "scores":     [0, 1, 3, 5, 7, 9, 10],
        "lower_is_better": False,
    },
    "debt_equity": {
        "thresholds": [0.5, 1, 1.5, 2, 3, 5],
        "scores":     [10, 8, 6, 4, 2, 1, 0],
        "lower_is_better": True,
    },
    "ebitda_margin": {
        "thresholds": [5, 10, 15, 20, 30, 40],
        "scores":     [0, 2, 4, 6, 8, 9, 10],
        "lower_is_better": False,
    },
    "roe": {
        "thresholds": [0, 5, 10, 15, 20, 30],
        "scores":     [0, 2, 4, 6, 8, 9, 10],
        "lower_is_better": False,
    },
    "fcf_positive": {  # Binary: is FCF positive?
        "thresholds": [0],
        "scores":     [0, 10],
        "lower_is_better": False,
    },
    "altman_z": {
        "thresholds": [1.1, 1.8, 2.7, 3.0, 4.0, 6.0],
        "scores":     [0, 1, 3, 6, 8, 9, 10],
        "lower_is_better": False,
    },
}


def _score_metric(value: Optional[float], rubric: dict) -> int:
    """Score a single metric against its rubric."""
    if value is None:
        return 5  # neutral if data missing
    thresholds = rubric["thresholds"]
    scores = rubric["scores"]
    for i, t in enumerate(thresholds):
        if value <= t:
            return scores[i]
    return scores[-1]


# Weighted scoring factors
SCORING_WEIGHTS = {
    "leverage": {
        "weight": 0.25,
        "metrics": ["nd_ebitda", "debt_equity"],
    },
    "coverage": {
        "weight": 0.20,
        "metrics": ["interest_coverage", "dscr"],
    },
    "liquidity": {
        "weight": 0.15,
        "metrics": ["current_ratio", "fcf_positive"],
    },
    "profitability": {
        "weight": 0.15,
        "metrics": ["ebitda_margin", "roe"],
    },
    "stability": {
        "weight": 0.15,
        "metrics": ["altman_z"],
    },
    "scale": {
        "weight": 0.10,
        "metrics": [],  # scored separately based on revenue/market cap
    },
}


def compute_credit_score(financials: dict) -> dict:
    """
    Compute deterministic credit score (0-100) from financial data.
    Returns score, grade, factor breakdown, and explanation.
    """
    f = financials
    rev = _n(f.get("rev"))
    cogs = _n(f.get("cogs"))
    ebitda = _n(f.get("ebitda"))
    ebit = _n(f.get("ebit"))
    ni = _n(f.get("ni"))
    ie = _n(f.get("intExp"))
    td = _n(f.get("debt"))
    cash = _n(f.get("cash"))
    ca = _n(f.get("ca"))
    cl = _n(f.get("cl"))
    ta = _n(f.get("assets"))
    eq = _n(f.get("equity"))
    ocf = _n(f.get("ocf"))
    capex = abs(_n(f.get("capex")))
    re = _n(f.get("re"))
    mk = _n(f.get("mktCap"))

    nd = td - cash
    fcf = ocf - capex
    wc = ca - cl
    gp = rev - cogs

    # Compute raw metrics
    metrics = {
        "nd_ebitda": _r(nd, ebitda),
        "interest_coverage": _r(ebit, ie),
        "dscr": _r(fcf, ie) if ie else None,
        "current_ratio": _r(ca, cl),
        "debt_equity": _r(td, eq),
        "ebitda_margin": _pct(ebitda, rev),
        "roe": _pct(ni, eq),
        "fcf_positive": 1 if fcf > 0 else -1,
        "altman_z": (1.2 * _r(wc, ta or 1) + 1.4 * _r(re, ta or 1) +
                     3.3 * _r(ebit, ta or 1) + 0.6 * _r(mk, td or 1) +
                     1.0 * _r(rev, ta or 1)) if ta else None,
    }

    # Score each factor
    factor_scores = {}
    factor_details = {}

    for factor_name, factor_cfg in SCORING_WEIGHTS.items():
        if factor_name == "scale":
            # Scale score based on revenue
            if rev > 1e11:
                scale_score = 10  # >100B
            elif rev > 1e10:
                scale_score = 8
            elif rev > 1e9:
                scale_score = 6
            elif rev > 1e8:
                scale_score = 4
            else:
                scale_score = 2
            factor_scores[factor_name] = scale_score
            factor_details[factor_name] = {"score": scale_score, "max": 10, "metrics": {}}
            continue

        metric_scores = {}
        for metric_name in factor_cfg["metrics"]:
            rubric = METRIC_RUBRICS[metric_name]
            raw = metrics.get(metric_name)
            s = _score_metric(raw, rubric)
            metric_scores[metric_name] = {"raw": raw, "score": s}

        # Factor score = average of its metric scores
        if metric_scores:
            avg = sum(m["score"] for m in metric_scores.values()) / len(metric_scores)
        else:
            avg = 5
        factor_scores[factor_name] = avg
        factor_details[factor_name] = {"score": round(avg, 1), "max": 10, "metrics": metric_scores}

    # Weighted total (0-100)
    total = 0
    for factor_name, factor_cfg in SCORING_WEIGHTS.items():
        total += factor_scores[factor_name] * factor_cfg["weight"] * 10

    total = max(0, min(100, round(total)))

    # Map to grade
    grade_map = [
        (90, "AAA"), (80, "AA+"), (75, "AA"), (70, "AA-"),
        (65, "A+"), (60, "A"), (55, "A-"),
        (50, "BBB+"), (45, "BBB"), (40, "BBB-"),
        (35, "BB+"), (30, "BB"), (25, "BB-"),
        (20, "B+"), (15, "B"), (10, "B-"),
        (5, "CCC"), (0, "D"),
    ]
    grade = "D"
    for threshold, g in grade_map:
        if total >= threshold:
            grade = g
            break

    # Recommendation
    if total >= 60:
        rec = "APPROVE"
    elif total >= 40:
        rec = "CONDITIONAL"
    else:
        rec = "DECLINE"

    return {
        "score": total,
        "grade": grade,
        "rec": rec,
        "factors": factor_details,
        "metrics": metrics,
    }


# ═══════════════════════════════════════════════
# 2. STRESS TESTING
# ═══════════════════════════════════════════════

STRESS_SCENARIOS = {
    "base": {
        "label": "Base Case",
        "rev_shock": 0,
        "ebitda_margin_shock": 0,
        "rate_shock": 0,
        "description": "Current trajectory maintained",
    },
    "adverse": {
        "label": "Adverse",
        "rev_shock": -0.15,      # 15% revenue decline
        "ebitda_margin_shock": -5,  # 500bps margin compression
        "rate_shock": 2.0,       # 200bps rate increase
        "description": "Moderate recession, margin pressure, rate hikes",
    },
    "severe": {
        "label": "Severe",
        "rev_shock": -0.30,      # 30% revenue decline
        "ebitda_margin_shock": -10,  # 1000bps margin compression
        "rate_shock": 4.0,       # 400bps rate increase
        "description": "Deep recession, demand collapse, liquidity crisis",
    },
}


def run_stress_test(financials: dict) -> dict:
    """
    Run 3-scenario stress test on the company's credit metrics.
    Shows how key ratios deteriorate under adverse conditions.
    """
    f = financials
    rev = _n(f.get("rev"))
    ebitda = _n(f.get("ebitda"))
    ebit = _n(f.get("ebit"))
    ie = _n(f.get("intExp"))
    td = _n(f.get("debt"))
    cash = _n(f.get("cash"))
    ocf = _n(f.get("ocf"))
    capex = abs(_n(f.get("capex")))

    if not rev or not ebitda:
        return {"error": "Insufficient data for stress test"}

    ebitda_margin = ebitda / rev if rev else 0
    results = {}

    for scenario_key, scenario in STRESS_SCENARIOS.items():
        # Apply shocks
        stressed_rev = rev * (1 + scenario["rev_shock"])
        stressed_margin = max(0, ebitda_margin + scenario["ebitda_margin_shock"] / 100)
        stressed_ebitda = stressed_rev * stressed_margin
        stressed_ebit = stressed_ebitda * (ebit / ebitda if ebitda else 0.7)
        stressed_ie = ie * (1 + scenario["rate_shock"] / (ie / td * 100 if td and ie else 5))
        stressed_ocf = ocf * (stressed_ebitda / ebitda if ebitda else 1)
        stressed_fcf = stressed_ocf - capex
        nd = td - cash

        results[scenario_key] = {
            "label": scenario["label"],
            "description": scenario["description"],
            "revenue": round(stressed_rev),
            "ebitda": round(stressed_ebitda),
            "ebitda_margin": round(stressed_margin * 100, 1),
            "nd_ebitda": round(nd / stressed_ebitda, 2) if stressed_ebitda else None,
            "interest_coverage": round(stressed_ebit / stressed_ie, 2) if stressed_ie else None,
            "dscr": round(stressed_fcf / stressed_ie, 2) if stressed_ie else None,
            "fcf": round(stressed_fcf),
            "survives": stressed_ebitda > stressed_ie and stressed_fcf > 0,
            "score": compute_credit_score({
                **f,
                "rev": str(stressed_rev),
                "ebitda": str(stressed_ebitda),
                "ebit": str(stressed_ebit),
                "ocf": str(stressed_ocf),
            })["score"],
        }

    return results


# ═══════════════════════════════════════════════
# 3. DEFAULT PROBABILITY
# ═══════════════════════════════════════════════

# Empirical 1-year default rates by rating (Moody's historical averages)
HISTORICAL_DEFAULT_RATES = {
    "AAA": 0.00, "AA+": 0.02, "AA": 0.03, "AA-": 0.04,
    "A+": 0.05, "A": 0.07, "A-": 0.09,
    "BBB+": 0.15, "BBB": 0.22, "BBB-": 0.35,
    "BB+": 0.55, "BB": 0.85, "BB-": 1.30,
    "B+": 2.10, "B": 3.50, "B-": 5.80,
    "CCC": 12.0, "D": 100.0,
}

# Altman Z-Score to PD mapping (empirical)
Z_SCORE_PD = [
    (3.0, 0.05), (2.7, 0.5), (2.0, 3.0), (1.8, 5.0),
    (1.5, 10.0), (1.0, 20.0), (0.5, 35.0), (0.0, 50.0),
]


def estimate_default_probability(financials: dict, credit_score: int, grade: str) -> dict:
    """
    Estimate probability of default using multiple models:
    1. Rating-implied PD (from grade)
    2. Z-Score implied PD
    3. Blended PD
    Also estimates Expected Loss = PD × LGD × EAD.
    """
    f = financials
    score_result = compute_credit_score(f)
    z = score_result["metrics"].get("altman_z")
    td = _n(f.get("debt"))
    eq = _n(f.get("equity"))

    # 1. Rating-implied PD
    rating_pd = HISTORICAL_DEFAULT_RATES.get(grade, 5.0)

    # 2. Z-Score PD
    z_pd = 50.0  # default if no Z
    if z is not None:
        for threshold, pd in Z_SCORE_PD:
            if z >= threshold:
                z_pd = pd
                break

    # 3. Score-implied PD (our internal model)
    # Exponential mapping: score 100→0.01%, score 0→50%
    score_pd = round(50 * math.exp(-0.06 * credit_score), 3)

    # Blended PD (weighted average)
    blended_pd = round(rating_pd * 0.3 + z_pd * 0.3 + score_pd * 0.4, 3)

    # LGD estimation (recovery rate based on seniority and asset coverage)
    asset_coverage = _r(_n(f.get("assets")), td) if td else None
    if asset_coverage and asset_coverage > 2:
        lgd = 25  # good asset coverage → high recovery
    elif asset_coverage and asset_coverage > 1:
        lgd = 40
    else:
        lgd = 60  # unsecured/undercollateralized

    # Expected Loss
    ead = td  # Exposure at Default ≈ total debt
    expected_loss = round(blended_pd / 100 * lgd / 100 * ead)

    return {
        "rating_pd": f"{rating_pd:.3f}%",
        "zscore_pd": f"{z_pd:.3f}%",
        "model_pd": f"{score_pd:.3f}%",
        "blended_pd": f"{blended_pd:.3f}%",
        "pd_band": "Investment Grade" if blended_pd < 2 else "Speculative" if blended_pd < 10 else "Distressed",
        "lgd": f"{lgd}%",
        "lgd_reasoning": f"Asset coverage {asset_coverage:.1f}x" if asset_coverage else "Insufficient data",
        "ead": ead,
        "expected_loss": expected_loss,
        "altman_z": z,
        "altman_zone": "Safe" if z and z > 2.99 else "Grey" if z and z > 1.81 else "Distress" if z else "N/A",
    }


# ═══════════════════════════════════════════════
# 4. EARLY WARNING SYSTEM
# ═══════════════════════════════════════════════

def check_early_warnings(financials: dict, prev_financials: dict = None) -> list:
    """
    Flag credit deterioration signals.
    Uses current data + optional previous period for trend detection.
    """
    f = financials
    warnings = []

    rev = _n(f.get("rev"))
    ebitda = _n(f.get("ebitda"))
    ni = _n(f.get("ni"))
    td = _n(f.get("debt"))
    cash = _n(f.get("cash"))
    ca = _n(f.get("ca"))
    cl = _n(f.get("cl"))
    ie = _n(f.get("intExp"))
    ocf = _n(f.get("ocf"))
    capex = abs(_n(f.get("capex")))
    eq = _n(f.get("equity"))
    ta = _n(f.get("assets"))

    fcf = ocf - capex
    nd = td - cash

    # ── Level 1: Critical (immediate action) ──
    if ni < 0:
        warnings.append({"level": "critical", "flag": "Net Loss", "detail": "Company is loss-making", "action": "Review viability and debt serviceability"})

    if fcf < 0 and ocf < 0:
        warnings.append({"level": "critical", "flag": "Negative Operating Cash Flow", "detail": "Not generating cash from operations", "action": "Assess burn rate and liquidity runway"})

    if ca and cl and ca < cl:
        warnings.append({"level": "critical", "flag": "Working Capital Deficit", "detail": f"Current ratio {_r(ca, cl):.2f}x < 1.0x", "action": "Evaluate short-term refinancing risk"})

    if eq < 0:
        warnings.append({"level": "critical", "flag": "Negative Net Worth", "detail": "Accumulated losses exceed capital", "action": "Assess going concern status"})

    if ie and ebitda and ebitda < ie:
        warnings.append({"level": "critical", "flag": "Cannot Service Debt", "detail": f"EBITDA ({ebitda:.0f}) < Interest ({ie:.0f})", "action": "Restructuring risk — monitor closely"})

    # ── Level 2: High (needs attention) ──
    nd_ebitda = _r(nd, ebitda)
    if nd_ebitda and nd_ebitda > 5:
        warnings.append({"level": "high", "flag": "Excessive Leverage", "detail": f"Net Debt/EBITDA {nd_ebitda:.1f}x > 5.0x", "action": "Monitor deleveraging plan"})

    ic = _r(ebitda, ie) if ie else None
    if ic and ic < 2:
        warnings.append({"level": "high", "flag": "Thin Interest Coverage", "detail": f"EBITDA/Interest {ic:.1f}x < 2.0x", "action": "Review debt terms and covenants"})

    if fcf < 0:
        warnings.append({"level": "high", "flag": "Negative Free Cash Flow", "detail": "Capex exceeds operating cash flow", "action": "Assess capex flexibility"})

    if td and eq and td / eq > 3:
        warnings.append({"level": "high", "flag": "High Gearing", "detail": f"D/E {td/eq:.1f}x > 3.0x", "action": "Compare vs sector norms"})

    # ── Level 3: Watch (monitor) ──
    if rev and ebitda and ebitda / rev < 0.10:
        warnings.append({"level": "watch", "flag": "Low Margins", "detail": f"EBITDA margin {ebitda/rev*100:.1f}% < 10%", "action": "Assess margin improvement levers"})

    if cash and td and cash / td < 0.05:
        warnings.append({"level": "watch", "flag": "Low Cash Buffer", "detail": f"Cash is {cash/td*100:.1f}% of debt", "action": "Monitor upcoming maturities"})

    # ── Trend warnings (if previous data available) ──
    if prev_financials:
        p = prev_financials
        prev_rev = _n(p.get("rev"))
        prev_ebitda = _n(p.get("ebitda"))
        prev_debt = _n(p.get("debt"))

        if prev_rev and rev and (rev - prev_rev) / prev_rev < -0.10:
            warnings.append({"level": "high", "flag": "Revenue Decline >10%", "detail": f"Revenue fell {((rev-prev_rev)/prev_rev)*100:.0f}% YoY", "action": "Assess whether cyclical or structural"})

        if prev_ebitda and ebitda and (ebitda - prev_ebitda) / prev_ebitda < -0.20:
            warnings.append({"level": "high", "flag": "EBITDA Decline >20%", "detail": f"EBITDA fell {((ebitda-prev_ebitda)/prev_ebitda)*100:.0f}% YoY", "action": "Review cost structure"})

        if prev_debt and td and (td - prev_debt) / prev_debt > 0.25:
            warnings.append({"level": "watch", "flag": "Debt Growing >25% YoY", "detail": f"Debt grew {((td-prev_debt)/prev_debt)*100:.0f}% YoY", "action": "Check if funded by asset growth"})

    # Sort by severity
    level_order = {"critical": 0, "high": 1, "watch": 2}
    warnings.sort(key=lambda w: level_order.get(w["level"], 3))

    return warnings


# ═══════════════════════════════════════════════
# 5. FULL CREDIT REPORT
# ═══════════════════════════════════════════════

def generate_credit_report(financials: dict, prev_financials: dict = None) -> dict:
    """
    Generate complete deterministic credit analysis.
    Combines: scoring + stress test + default probability + early warnings.
    """
    # 1. Score
    score_result = compute_credit_score(financials)

    # 2. Stress test
    stress = run_stress_test(financials)

    # 3. Default probability
    pd_result = estimate_default_probability(
        financials, score_result["score"], score_result["grade"]
    )

    # 4. Early warnings
    warnings = check_early_warnings(financials, prev_financials)

    # 5. Summary
    critical_count = sum(1 for w in warnings if w["level"] == "critical")
    survives_adverse = stress.get("adverse", {}).get("survives", True)
    survives_severe = stress.get("severe", {}).get("survives", True)

    summary = {
        "verdict": score_result["rec"],
        "score": score_result["score"],
        "grade": score_result["grade"],
        "stress_resilience": "Strong" if survives_severe else "Adequate" if survives_adverse else "Weak",
        "default_risk": pd_result["pd_band"],
        "warnings_critical": critical_count,
        "warnings_total": len(warnings),
    }

    return {
        "summary": summary,
        "score": score_result,
        "stress_test": stress,
        "default_probability": pd_result,
        "early_warnings": warnings,
    }
