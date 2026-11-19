# PyInstaller spec — builds ONE self-contained file (Python + all packages + UI inside).
#   pyinstaller packaging/credit-nexus.spec        (run from the project root)
# Output: dist/CreditNexus(.exe)
import os, importlib.util
from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
datas = [(os.path.join(ROOT, "backend", "pages"), "pages"),
         (os.path.join(ROOT, "frontend", "dist"), "frontend_dist")]
binaries, hidden = [], ["main", "config", "data_sources", "ai_analyst", "grounding", "credit_engine",
                        "autofix", "diagnose"]
hidden += collect_submodules("uvicorn")
for pkg in ("yfinance", "curl_cffi", "certifi"):
    if importlib.util.find_spec(pkg):
        d, b, h = collect_all(pkg)
        datas += d; binaries += b; hidden += h

a = Analysis([os.path.join(ROOT, "run.py")], pathex=[os.path.join(ROOT, "backend")],
             datas=datas, binaries=binaries, hiddenimports=hidden,
             excludes=["tkinter", "matplotlib", "IPython", "pytest"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="CreditNexus",
          console=True, upx=False, runtime_tmpdir=None)
