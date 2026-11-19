"""
Credit Nexus launcher + watchdog.
  python run.py
- installs/repairs dependencies (autofix)
- picks a free port, starts the server, opens the browser when it's actually ready
- watchdog: if the server crashes or stops answering, it repairs and restarts it (max 5 times)
"""
import os
import sys
import time
import threading
import subprocess
import webbrowser
import urllib.request

SELF = os.path.abspath(__file__)
FROZEN = getattr(sys, "frozen", False)  # True inside the one-file app built by PyInstaller
HERE = getattr(sys, "_MEIPASS", None) or os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
sys.path.insert(0, HERE)
if not FROZEN:
    os.chdir(HERE)

from autofix import auto_fix_all, find_free_port  # noqa: E402

HOST = os.environ.get("CN_HOST", "127.0.0.1")
MAX_RESTARTS = 5


def alive(port, timeout=5):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def start(port):
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    cmd = [sys.executable] if FROZEN else [sys.executable, SELF]
    return subprocess.Popen(cmd + ["--server", str(port)], env=env)


def serve(port):
    """Child process: the actual web server."""
    import uvicorn
    import main as app_module
    uvicorn.run(app_module.app, host=HOST, port=port, log_level="info")


def main():
    print("\n  Credit Nexus - starting\n", flush=True)
    for a in auto_fix_all():
        print(f"  -> {a}", flush=True)
    port = find_free_port(int(os.environ.get("CN_PORT", "8000")))
    url = f"http://127.0.0.1:{port}"
    restarts, opened = 0, False
    proc = start(port)
    print(f"\n  Server: {url}   (keep this window open; close it to stop)", flush=True)
    print("  Numbers, credit score, stress test and warnings appear within seconds.", flush=True)
    print("  AI commentary uses Pollinations' free service (no key): ONE request per company,", flush=True)
    print("  max one request every 30 s, so AI sections fill in about 30-90 s later.\n", flush=True)
    try:
        misses = 0
        while True:
            time.sleep(2)
            if proc.poll() is not None:  # crashed
                if restarts >= MAX_RESTARTS:
                    print("  !! Server keeps crashing. Run: python backend/diagnose.py  and read the FAIL lines.", flush=True)
                    return 1
                restarts += 1
                print(f"  !! Server stopped (exit {proc.returncode}). Repairing and restarting ({restarts}/{MAX_RESTARTS})...", flush=True)
                auto_fix_all()
                for _ in range(20):  # give the OS a moment to release the old port
                    if find_free_port(port) == port:
                        break
                    time.sleep(0.5)
                port = find_free_port(port)
                url = f"http://127.0.0.1:{port}"
                proc, opened, misses = start(port), False, 0
                continue
            if alive(port):
                misses = 0
                if not opened and os.environ.get("CN_NO_BROWSER") != "1":
                    webbrowser.open(url)
                    opened = True
            elif opened:
                misses += 1
                if misses >= 6:  # ~40s unresponsive
                    print("  !! Server not responding - restarting...", flush=True)
                    proc.kill()
    except KeyboardInterrupt:
        pass
    finally:
        if proc.poll() is None:
            proc.terminate()
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--server":
        serve(int(sys.argv[2]))
    else:
        import multiprocessing
        multiprocessing.freeze_support()
        sys.exit(main())
