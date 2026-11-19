"""
Auto-fix — runs before the server starts (and on demand via /api/repair).
Installs missing packages, fixes SSL certificate paths, creates the config dir.
No network calls besides pip, so startup stays fast.
"""

import os
import sys
import socket
import logging
import importlib
import subprocess
from pathlib import Path

log = logging.getLogger("autofix")

REQUIRED = {  # import name -> pip spec
    "fastapi": "fastapi>=0.110",
    "uvicorn": "uvicorn>=0.29",
    "httpx": "httpx>=0.27",
    "yfinance": "yfinance>=0.2.54",
    "certifi": "certifi",
}


def _pip(*args) -> bool:
    base = [sys.executable, "-m", "pip", "install", "--quiet", "--disable-pip-version-check", *args]
    for extra in ([], ["--user"], ["--break-system-packages"]):
        try:
            subprocess.check_call(base + extra, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=600)
            return True
        except Exception:
            continue
    return False


def auto_fix_all() -> list:
    actions = []
    if getattr(sys, "frozen", False) or os.environ.get("CN_PUBLIC") == "1":
        try:
            import certifi
            os.environ.setdefault("SSL_CERT_FILE", certifi.where())
        except Exception:
            pass
        return ["Packaged build - dependencies are bundled"]

    for mod, spec in REQUIRED.items():
        try:
            importlib.import_module(mod)
        except ImportError:
            ok = _pip(spec)
            actions.append(f"{'Installed' if ok else 'FAILED to install'} {spec}")

    # yfinance < 0.2.54 breaks against current Yahoo endpoints — upgrade in place.
    try:
        import yfinance
        parts = [int(p) for p in yfinance.__version__.split(".")[:3] if p.isdigit()]
        if parts and tuple(parts) < (0, 2, 54):
            ok = _pip("--upgrade", "yfinance")
            actions.append(f"{'Upgraded' if ok else 'FAILED to upgrade'} yfinance {yfinance.__version__} (outdated)")
    except Exception:
        pass

    # Corporate Windows machines often lack a CA bundle Python can find.
    try:
        import certifi
        os.environ.setdefault("SSL_CERT_FILE", certifi.where())
        os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
    except Exception:
        pass

    try:
        from config import CONFIG_DIR
        Path(CONFIG_DIR).mkdir(parents=True, exist_ok=True)
    except Exception as e:
        actions.append(f"Could not create config dir: {e}")

    if not actions:
        actions.append("All checks passed - no fixes needed")
    return actions


def find_free_port(preferred: int = 8000) -> int:
    for port in range(preferred, preferred + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return preferred


if __name__ == "__main__":
    for a in auto_fix_all():
        print(f"  -> {a}")
