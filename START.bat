@echo off
title Credit Nexus
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
echo.
echo   Credit Nexus - Credit Research Dashboard
echo   ========================================
echo.

set "PY="
python --version >nul 2>&1 && set "PY=python"
if not defined PY py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY (
    echo   Python not found. Trying automatic install with winget...
    winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements --silent
    if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set PY="%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
)
if not defined PY (
    echo.
    echo   Could not install Python automatically.
    echo   1. Open https://python.org/downloads and install Python 3.12
    echo   2. TICK "Add python.exe to PATH" on the first installer screen
    echo   3. Double-click START.bat again
    pause
    exit /b 1
)
echo   [OK] Python: %PY%

echo   Installing / checking packages (first run takes about a minute)...
%PY% -m pip install --disable-pip-version-check --quiet -r backend\requirements.txt
if errorlevel 1 %PY% -m pip install --user --disable-pip-version-check --quiet -r backend\requirements.txt

if not exist "%USERPROFILE%\Desktop\Credit Nexus.lnk" call "%~dp0create_shortcut.bat"

echo.
echo   Starting. Your browser opens automatically when ready.
echo   Data and scores show in seconds; AI commentary follows in about 30-90 s
echo   (free AI, no key needed: one request per company, one request every 30 s).
echo   KEEP THIS WINDOW OPEN. Close it to stop Credit Nexus.
echo.
%PY% run.py
echo.
echo   Credit Nexus stopped. If this was unexpected run:  %PY% backend\diagnose.py
pause
