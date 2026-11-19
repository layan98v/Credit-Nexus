"""Quick live system check (real network).  python check.py"""
import os, sys, asyncio
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))
from diagnose import run_full_diagnosis
d = asyncio.run(run_full_diagnosis())
for r in d["results"]:
    print(f"  [{r['status'].upper():5}] {r['component']}: {r['detail']}" + (f"\n          fix: {r['fix']}" if r["fix"] else ""))
print("\n  READY" if d["summary"]["errors"] == 0 else "\n  Fix the ERROR lines above")
