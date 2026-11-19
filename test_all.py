"""
Credit Nexus — full offline test suite.   python test_all.py   (exit 0 = safe to ship)
1. structure & syntax   2. no leftover branding   3. credit-engine bands
4. launchers (CRLF on .bat)   5. end-to-end API run with mocked network (tests/e2e_mock.py)
"""
import os, sys, ast, glob, re, subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "backend"))
F = []
def ok(n, c, info=""):
    print(f"  {'PASS' if c else 'FAIL'}  {n}{'' if c else '  -> ' + str(info)}")
    c or F.append(n)

print("\n-- structure")
for f in ["run.py", "START.bat", "start.sh", "create_shortcut.bat", "README.md", "QUICKSTART.md", "SETUP-GUIDE.html",
          "backend/main.py", "backend/data_sources.py", "backend/ai_analyst.py", "backend/grounding.py", "backend/config.py",
          "backend/credit_engine.py", "backend/autofix.py", "backend/diagnose.py",
          "backend/pages/health.html", "backend/requirements.txt",
          "frontend/dist/index.html", "frontend/src/App.jsx", "tests/e2e_mock.py", "tests/e2e_public.py",
          "render.yaml", ".github/workflows/build-apps.yml", "packaging/credit-nexus.spec", "build_app.bat"]:
    ok(f, os.path.exists(os.path.join(ROOT, f)))
ok("frontend bundle built", bool(glob.glob(os.path.join(ROOT, "frontend/dist/assets/*.js"))))

print("\n-- syntax")
for f in glob.glob(os.path.join(ROOT, "backend/*.py")) + [os.path.join(ROOT, "run.py")]:
    try: ast.parse(open(f, encoding="utf-8").read()); ok(os.path.basename(f), True)
    except SyntaxError as e: ok(os.path.basename(f), False, f"line {e.lineno}: {e.msg}")

print("\n-- branding / secrets")
hits = []
for f in glob.glob(os.path.join(ROOT, "**/*"), recursive=True):
    if "node_modules" in f or os.path.isdir(f) or f.endswith((".png", ".ico")) or f.endswith("test_all.py"): continue
    t = open(f, encoding="utf-8", errors="ignore").read()
    if re.search(r"elara|INZ000206738", t, re.I): hits.append(os.path.relpath(f, ROOT))
    if re.search(r"sk-ant-api\d\d-[A-Za-z0-9_-]{20,}|gsk_[A-Za-z0-9]{20,}", t): hits.append("KEY in " + os.path.relpath(f, ROOT))
ok("no company branding or API keys in any file", not hits, hits)

print("\n-- credit engine")
from credit_engine import generate_credit_report, compute_credit_score
strong = {"rev": 9e11, "cogs": 5e11, "ebitda": 2e11, "ebit": 1.5e11, "ni": 8e10, "intExp": 2e10, "debt": 3e11, "cash": 1e11,
          "ca": 4e11, "cl": 3e11, "assets": 1.5e12, "equity": 8e11, "ocf": 1.8e11, "capex": 8e10, "re": 5e11, "mktCap": 2e12}
weak = {"rev": 1e10, "cogs": 9e9, "ebitda": 5e8, "ebit": 2e8, "ni": -1e8, "intExp": 8e8, "debt": 5e9, "cash": 1e8,
        "ca": 1e9, "cl": 2e9, "assets": 6e9, "equity": -5e8, "ocf": -2e8, "capex": 3e8, "re": -2e9, "mktCap": 1e9}
s = compute_credit_score(strong); ok(f"strong -> APPROVE ({s['score']} {s['grade']})", s["rec"] == "APPROVE" and s["score"] >= 70)
w = compute_credit_score(weak); ok(f"weak -> DECLINE ({w['score']} {w['grade']})", w["rec"] == "DECLINE")
r = generate_credit_report(strong)
ok("stress: severe < base", r["stress_test"]["severe"]["score"] < r["stress_test"]["base"]["score"])
ok("weak -> >=3 critical warnings", sum(x["level"] == "critical" for x in generate_credit_report(weak)["early_warnings"]) >= 3)
ok("string inputs accepted", compute_credit_score({k: str(v) for k, v in strong.items()})["score"] == s["score"])
ok("empty input no crash", isinstance(compute_credit_score({})["score"], int))

print("\n-- launchers")
for b in ("START.bat", "create_shortcut.bat", "build_app.bat"):
    raw = open(os.path.join(ROOT, b), "rb").read()
    ok(f"{b} uses CRLF", raw.count(b"\n") == raw.count(b"\r\n") and raw.count(b"\n") > 0)
ok("start.sh has LF only", b"\r" not in open(os.path.join(ROOT, "start.sh"), "rb").read())

print("\n-- end-to-end (mocked network)")
p = subprocess.run([sys.executable, os.path.join(ROOT, "tests", "e2e_mock.py")], capture_output=True, text=True, timeout=600)
for line in p.stdout.splitlines():
    if line.strip().startswith(("PASS", "FAIL")): print(line)
ok("e2e suite", p.returncode == 0, (p.stdout + p.stderr)[-800:])

print("\n-- website mode (mocked network)")
p = subprocess.run([sys.executable, os.path.join(ROOT, "tests", "e2e_public.py")], capture_output=True, text=True, timeout=600)
for line in p.stdout.splitlines():
    if line.strip().startswith(("PASS", "FAIL")): print(line)
ok("website-mode suite", p.returncode == 0, (p.stdout + p.stderr)[-800:])

print(f"\n  {'ALL TESTS PASS' if not F else str(len(F)) + ' FAILED: ' + ', '.join(F)}\n")
sys.exit(1 if F else 0)
