"""Website mode (CN_PUBLIC=1): same app, no runtime package installs.  python tests/e2e_public.py"""
import os, sys
os.environ["CN_PUBLIC"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "e2e_mock.py"), encoding="utf-8").read()
exec(src[:src.index("from fastapi.testclient")], {"__file__": os.path.join(HERE, "e2e_mock.py"), "__name__": "mocks"})
from fastapi.testclient import TestClient
import main
F = []
def check(n, c, info=""):
    print(f"  {'PASS' if c else 'FAIL'}  {n}{'' if c else '  -> ' + str(info)[:300]}"); c or F.append(n)
with TestClient(main.app) as c:
    st = c.get("/api/status").json()
    check("website mode reported", st["public"] is True, st)
    check("no pip installs on the website", main.startup_actions == ["Packaged build - dependencies are bundled"], main.startup_actions)
    check("dashboard opens directly", c.get("/", follow_redirects=False).status_code == 200)
    a = c.get("/api/analyze", params={"company": "Tata Consultancy"}).json()
    check("analysis works", a["credit_report"]["summary"]["score"] >= 70)
    check("insights work keyless", c.get("/api/insights", params={"company": "Tata Consultancy"}).json()["data"] is not None)
    check("repair skips pip", "Cleared data cache" in c.post("/api/repair").json()["actions"])
print("\n  ALL PASS" if not F else f"\n  {len(F)} FAILED"); sys.exit(1 if F else 0)
